from unittest import mock

from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import User
from adminpanel import moderation
from adminpanel.testing import LETTER, PASSWORD, AdminTestMixin
from profiles.models import Skill
from usersettings.models import NotificationPreference

from .models import Notification
from .service import TITLE_MAX_LENGTH, notify

Kind = Notification.Kind


class NotificationTestCase(AdminTestMixin, APITestCase):
    def setUp(self):
        self.client_user = self.make_user('client@example.com', User.Role.CLIENT, full_name='Wanjiru Bakers')
        self.freelancer = self.make_user('freelancer@example.com', User.Role.FREELANCER, full_name='Otieno Designs')
        self.gig = self.make_gig(self.client_user)

    def prefs(self, user, **values):
        NotificationPreference.objects.filter(user=user).update(**values)

    def kinds(self, user):
        return list(Notification.objects.filter(recipient=user).order_by('created_at').values_list('kind', flat=True))


class NotifyTests(NotificationTestCase):
    def test_writes_the_row_and_sends_the_email_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            note = notify(
                self.freelancer, Kind.NEW_GIG_MATCH, 'A title', 'The body.', link='/gigs/1',
                email_preference='new_match_email', inapp_preference='new_match_inapp',
            )
        self.assertEqual((note.title, note.body, note.link), ('A title', 'The body.', '/gigs/1'))
        self.assertEqual(mail.outbox[0].subject, 'GigConnect: A title')
        self.assertIn('/gigs/1', mail.outbox[0].body)

    def test_each_channel_follows_its_own_setting(self):
        self.prefs(self.freelancer, new_match_inapp=False)
        with self.captureOnCommitCallbacks(execute=True):
            note = notify(self.freelancer, Kind.NEW_GIG_MATCH, 'T', 'B', email_preference='new_match_email',
                          inapp_preference='new_match_inapp')
        self.assertIsNone(note)
        self.assertEqual(len(mail.outbox), 1)

        self.prefs(self.freelancer, new_match_inapp=True, new_match_email=False)
        with self.captureOnCommitCallbacks(execute=True):
            note = notify(self.freelancer, Kind.NEW_GIG_MATCH, 'T', 'B', email_preference='new_match_email',
                          inapp_preference='new_match_inapp')
        self.assertIsNotNone(note)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_long_title_with_a_line_break_is_made_safe(self):
        with self.captureOnCommitCallbacks(execute=True):
            note = notify(self.freelancer, Kind.GIG_REMOVED, 'Your gig\n"' + 'x' * 300 + '"', 'B',
                          email_preference='status_change_email')
        self.assertEqual(len(note.title), TITLE_MAX_LENGTH)
        self.assertNotIn('\n', note.title)
        self.assertEqual(len(mail.outbox), 1)

    def test_removing_a_gig_with_the_longest_title_works(self):
        admin = self.make_admin()
        gig = self.make_gig(self.client_user, title='y' * 200)
        moderation.remove_gig(admin, gig, 'Spam.')
        self.assertEqual(self.kinds(self.client_user), ['gig_removed'])

    def test_a_mail_failure_does_not_fail_the_action(self):
        with mock.patch('notifications.service.send_mail', side_effect=OSError('mail server down')):
            with self.captureOnCommitCallbacks(execute=True):
                note = notify(self.freelancer, Kind.GIG_REMOVED, 'T', 'B', email_preference='status_change_email')
        self.assertIsNotNone(note)


class EventTests(NotificationTestCase):
    def apply_as_freelancer(self):
        self.client.force_authenticate(self.freelancer)
        response = self.client.post(f'/api/gigs/{self.gig.pk}/applications/', {'cover_letter': LETTER})
        self.assertEqual(response.status_code, 201)
        return response.data['id']

    def test_the_client_hears_about_a_new_application(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.apply_as_freelancer()
        note = Notification.objects.get(recipient=self.client_user)
        self.assertEqual((note.kind, note.link), ('new_application', f'/gigs/{self.gig.pk}/applicants'))
        self.assertIn('Otieno Designs', note.body)
        self.assertEqual(mail.outbox[0].to, [self.client_user.email])

    def test_the_client_hears_about_a_withdrawal(self):
        application_id = self.apply_as_freelancer()
        self.assertEqual(self.client.post(f'/api/applications/{application_id}/withdraw/', {}).status_code, 200)
        self.assertEqual(self.kinds(self.client_user), ['new_application', 'application_withdrawn'])

    def test_the_freelancer_hears_about_every_status_change(self):
        application_id = self.apply_as_freelancer()
        self.client.force_authenticate(self.client_user)
        for status in ('under_review', 'shortlisted', 'hired'):
            response = self.client.patch(f'/api/applications/{application_id}/status/', {'status': status})
            self.assertEqual(response.status_code, 200)
        notes = Notification.objects.filter(recipient=self.freelancer).order_by('created_at')
        self.assertEqual([n.kind for n in notes], ['application_status'] * 3)
        self.assertIn('Hired', notes[2].title)
        self.assertIn('hired you', notes[2].body)
        self.assertEqual(notes[0].link, f'/applications/{application_id}')

    def test_a_refused_status_change_tells_nobody(self):
        application = self.apply(self.gig, self.freelancer)
        self.client.force_authenticate(self.client_user)
        response = self.client.patch(f'/api/applications/{application.pk}/status/', {'status': 'hired'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.kinds(self.freelancer), [])

    def test_settings_switch_off_application_notifications(self):
        self.prefs(self.client_user, new_application_inapp=False, new_application_email=False)
        with self.captureOnCommitCallbacks(execute=True):
            self.apply_as_freelancer()
        self.assertEqual(self.kinds(self.client_user), [])
        self.assertEqual(mail.outbox, [])

    def test_changing_your_password_is_a_security_alert(self):
        self.client.force_authenticate(self.freelancer)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/settings/change-password/', {
                'current_password': PASSWORD, 'new_password': 'A-different-pass-2',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.kinds(self.freelancer), ['password_changed'])
        self.assertEqual(len(mail.outbox), 1)


class NewGigMatchTests(NotificationTestCase):
    def setUp(self):
        super().setUp()
        self.skill = Skill.objects.create(name='Notification Test Skill', category='Technology')
        self.freelancer.freelancer_profile.skills.set([self.skill])

    def post_gig(self, skills=None):
        self.client.force_authenticate(self.client_user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/gigs/', {
                'title': 'Build a shop', 'description': 'A small online shop for a bakery in Nakuru.',
                'category': str(self.gig.category_id), 'budget_min': '1000', 'budget_max': '2000',
                'deadline': self.gig.deadline.isoformat(), 'skills': skills or [str(self.skill.pk)],
            }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def test_freelancers_with_a_shared_skill_are_told(self):
        gig_id = self.post_gig()
        note = Notification.objects.get(recipient=self.freelancer)
        self.assertEqual((note.kind, note.link), ('new_gig_match', f'/gigs/{gig_id}'))
        self.assertEqual(mail.outbox[0].to, [self.freelancer.email])

    def test_others_are_not(self):
        other_skill = Skill.objects.create(name='Unrelated Test Skill', category='Technology')
        self.post_gig(skills=[str(other_skill.pk)])
        self.assertEqual(self.kinds(self.freelancer), [])
        self.assertEqual(mail.outbox, [])

    def test_suspended_and_unverified_freelancers_are_not_told(self):
        User.objects.filter(pk=self.freelancer.pk).update(account_status=User.AccountStatus.SUSPENDED)
        unverified = self.make_user('unverified@example.com', User.Role.FREELANCER)
        User.objects.filter(pk=unverified.pk).update(is_email_verified=False)
        unverified.freelancer_profile.skills.set([self.skill])
        self.post_gig()
        self.assertFalse(Notification.objects.filter(kind='new_gig_match').exists())

    def test_settings_are_respected_per_person(self):
        self.prefs(self.freelancer, new_match_email=False)
        self.post_gig()
        self.assertEqual(self.kinds(self.freelancer), ['new_gig_match'])
        self.assertEqual(mail.outbox, [])

    @override_settings(NOTIFICATION_MATCH_LIMIT=1)
    def test_the_batch_has_a_limit(self):
        second = self.make_user('second@example.com', User.Role.FREELANCER)
        second.freelancer_profile.skills.set([self.skill])
        self.post_gig()
        self.assertEqual(Notification.objects.filter(kind='new_gig_match').count(), 1)

    def test_the_query_count_does_not_grow_with_the_people_told(self):
        def posting_queries():
            from django.db import connection
            from django.test.utils import CaptureQueriesContext

            with CaptureQueriesContext(connection) as context:
                self.post_gig()
            return len(context)

        first = posting_queries()
        for index in range(5):
            person = self.make_user(f'match-{index}@example.com', User.Role.FREELANCER)
            person.freelancer_profile.skills.set([self.skill])
        self.assertEqual(posting_queries(), first)


class EndpointTests(NotificationTestCase):
    def setUp(self):
        super().setUp()
        self.first = notify(self.freelancer, Kind.GIG_RESTORED, 'First', 'B')
        self.second = notify(self.freelancer, Kind.GIG_REMOVED, 'Second', 'B')
        self.theirs = notify(self.client_user, Kind.GIG_REMOVED, 'Not yours', 'B')

    def test_login_is_required(self):
        self.assertEqual(self.client.get('/api/notifications/').status_code, 401)
        self.assertEqual(self.client.get('/api/notifications/unread-count/').status_code, 401)
        self.assertEqual(self.client.post('/api/notifications/read-all/').status_code, 401)
        self.assertEqual(self.client.post(f'/api/notifications/{self.first.pk}/read/').status_code, 401)

    def test_lists_only_your_own_newest_first(self):
        self.client.force_authenticate(self.freelancer)
        data = self.client.get('/api/notifications/').data
        self.assertEqual([row['title'] for row in data['results']], ['Second', 'First'])
        self.assertEqual(data['results'][0]['is_read'], False)

    def test_marking_one_read_changes_the_count_and_the_filter(self):
        self.client.force_authenticate(self.freelancer)
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['unread'], 2)
        response = self.client.post(f'/api/notifications/{self.first.pk}/read/')
        self.assertEqual((response.status_code, response.data['is_read']), (200, True))
        read_at = response.data['read_at']
        again = self.client.post(f'/api/notifications/{self.first.pk}/read/')
        self.assertEqual(again.data['read_at'], read_at)
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['unread'], 1)
        unread = self.client.get('/api/notifications/', {'unread': 'true'}).data['results']
        self.assertEqual([row['title'] for row in unread], ['Second'])

    def test_someone_elses_is_a_404(self):
        self.client.force_authenticate(self.freelancer)
        self.assertEqual(self.client.post(f'/api/notifications/{self.theirs.pk}/read/').status_code, 404)
        self.theirs.refresh_from_db()
        self.assertIsNone(self.theirs.read_at)

    def test_read_all_only_touches_your_own(self):
        self.client.force_authenticate(self.freelancer)
        self.assertEqual(self.client.post('/api/notifications/read-all/').data['marked'], 2)
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['unread'], 0)
        self.theirs.refresh_from_db()
        self.assertIsNone(self.theirs.read_at)

    def test_admin_notices_ignore_the_in_app_setting(self):
        self.prefs(self.client_user, security_alert_inapp=False, status_change_inapp=False)
        moderation.remove_gig(self.make_admin(), self.gig, 'Spam.')
        self.assertIn('gig_removed', self.kinds(self.client_user))

    def test_your_data_export_includes_them(self):
        self.client.force_authenticate(self.freelancer)
        exported = self.client.get('/api/settings/export-data/').data['notifications']
        self.assertEqual([row['title'] for row in exported], ['First', 'Second'])

    def test_deleting_your_account_deletes_them(self):
        self.client.force_authenticate(self.freelancer)
        response = self.client.post('/api/settings/delete-account/', {'password': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Notification.objects.filter(recipient=self.freelancer).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.client_user).exists())
