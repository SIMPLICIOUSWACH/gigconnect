from unittest import mock

from django.core import mail
from django.db import IntegrityError, transaction
from rest_framework.test import APITestCase

from accounts.models import User
from gigs.models import Gig
from notifications.models import Notification
from profiles.models import FreelancerProfile
from recommendations.candidates import candidate_gigs
from recommendations.platform import applications_for_training, gigs_for_training
from usersettings.models import NotificationPreference, UserSession

from . import moderation
from .models import AdminAction
from .moderation import ModerationError
from .testing import PASSWORD, AdminTestMixin


class ModerationTestCase(AdminTestMixin, APITestCase):
    def setUp(self):
        self.admin = self.make_admin()
        self.client_user = self.make_user('client@example.com', User.Role.CLIENT)
        self.freelancer = self.make_user('freelancer@example.com', User.Role.FREELANCER)
        self.gig = self.make_gig(self.client_user)

    def feed_ids(self, **params):
        self.client.force_authenticate(self.freelancer)
        response = self.client.get('/api/gigs/', params)
        self.client.force_authenticate(None)
        return {row['id'] for row in response.data['results']}


class SuspendUserTests(ModerationTestCase):
    def login(self, user):
        return self.client.post('/api/auth/login/', {'email': user.email, 'password': PASSWORD}).data

    def test_suspending_records_the_reason_and_tells_the_user(self):
        with self.captureOnCommitCallbacks(execute=True):
            action = moderation.suspend_user(self.admin, self.client_user, '  Posted scam gigs.  ')

        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.is_suspended)
        self.assertEqual(self.client_user.suspended_reason, 'Posted scam gigs.')
        self.assertIsNotNone(self.client_user.suspended_at)
        self.assertEqual(
            (action.admin, action.action, action.target_type, action.target_id, action.reason),
            (self.admin, 'suspend_user', 'user', self.client_user.pk, 'Posted scam gigs.'),
        )
        note = Notification.objects.get(recipient=self.client_user)
        self.assertEqual(note.kind, Notification.Kind.ACCOUNT_SUSPENDED)
        self.assertIn('Posted scam gigs.', note.body)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.client_user.email])
        self.assertIn('Posted scam gigs.', mail.outbox[0].body)

    def test_suspending_logs_the_user_out_everywhere_and_blocks_login(self):
        tokens = self.login(self.client_user)
        self.assertEqual(UserSession.objects.filter(user=self.client_user).count(), 1)

        moderation.suspend_user(self.admin, self.client_user, 'Posted scam gigs.')

        self.assertFalse(UserSession.objects.filter(user=self.client_user).exists())
        self.assertEqual(self.client.post('/api/auth/token/refresh/', {'refresh': tokens['refresh']}).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/auth/login/', {
            'email': self.client_user.email, 'password': PASSWORD,
        }).status_code, 401)

    def test_a_suspended_clients_open_gigs_are_hidden_until_reinstated(self):
        moderation.suspend_user(self.admin, self.client_user, 'Posted scam gigs.')
        self.assertNotIn(str(self.gig.pk), self.feed_ids())
        self.assertNotIn(self.gig, candidate_gigs(self.freelancer))
        self.client.force_authenticate(self.freelancer)
        self.assertEqual(self.client.get(f'/api/gigs/{self.gig.pk}/').status_code, 404)

        moderation.reinstate_user(self.admin, self.client_user)
        self.assertIn(str(self.gig.pk), self.feed_ids())
        self.assertIn(self.gig, candidate_gigs(self.freelancer))

    def test_reinstating_clears_the_suspension_and_lets_them_log_in(self):
        moderation.suspend_user(self.admin, self.client_user, 'Posted scam gigs.')
        action = moderation.reinstate_user(self.admin, self.client_user, 'Appeal accepted.')

        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_suspended)
        self.assertEqual(self.client_user.suspended_reason, '')
        self.assertIsNone(self.client_user.suspended_at)
        self.assertEqual((action.action, action.reason), ('reinstate_user', 'Appeal accepted.'))
        self.assertIn('access', self.login(self.client_user))

    def test_a_reason_is_required_and_nothing_changes_without_one(self):
        for reason in ('', '   ', None):
            with self.assertRaises(ModerationError):
                moderation.suspend_user(self.admin, self.client_user, reason)
        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_suspended)
        self.assertFalse(AdminAction.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_admins_cannot_suspend_themselves_or_another_admin(self):
        other_admin = self.make_admin('other-admin@example.com')
        with self.assertRaisesMessage(ModerationError, 'your own account'):
            moderation.suspend_user(self.admin, self.admin, 'Testing.')
        with self.assertRaisesMessage(ModerationError, 'Admin accounts'):
            moderation.suspend_user(self.admin, other_admin, 'Testing.')
        self.assertFalse(User.objects.filter(account_status=User.AccountStatus.SUSPENDED).exists())

    def test_suspending_twice_or_reinstating_an_active_user_is_refused(self):
        with self.assertRaises(ModerationError):
            moderation.reinstate_user(self.admin, self.client_user)
        moderation.suspend_user(self.admin, self.client_user, 'Posted scam gigs.')
        with self.assertRaises(ModerationError):
            moderation.suspend_user(self.admin, self.client_user, 'Again.')
        self.assertEqual(AdminAction.objects.count(), 1)

    def test_no_email_when_the_setting_is_off_but_the_notification_is_still_written(self):
        NotificationPreference.objects.filter(user=self.client_user).update(security_alert_email=False)
        with self.captureOnCommitCallbacks(execute=True):
            moderation.suspend_user(self.admin, self.client_user, 'Posted scam gigs.')
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(Notification.objects.filter(recipient=self.client_user).exists())

    def test_the_change_the_log_row_and_the_notification_are_one_transaction(self):
        with mock.patch('adminpanel.moderation.notify', side_effect=RuntimeError('mail server down')):
            with self.assertRaises(RuntimeError):
                moderation.suspend_user(self.admin, self.client_user, 'Posted scam gigs.')
        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_suspended)
        self.assertFalse(AdminAction.objects.exists())


class RemoveGigTests(ModerationTestCase):
    def test_a_removed_gig_disappears_from_feed_search_categories_and_recommendations(self):
        self.assertIn(str(self.gig.pk), self.feed_ids(q='bakery'))
        moderation.remove_gig(self.admin, self.gig, 'Asks for payment up front.')

        self.assertNotIn(str(self.gig.pk), self.feed_ids())
        self.assertNotIn(str(self.gig.pk), self.feed_ids(q='bakery'))
        self.assertNotIn(str(self.gig.pk), self.feed_ids(include_closed='true'))
        self.assertNotIn(self.gig, candidate_gigs(self.freelancer))
        self.assertNotIn(self.gig, gigs_for_training())
        counts = {row['slug']: row['open_gig_count'] for row in self.client.get('/api/categories/').data}
        self.assertEqual(counts[self.gig.category.slug], 0)
        self.client.force_authenticate(self.freelancer)
        self.assertEqual(self.client.get(f'/api/gigs/{self.gig.pk}/').status_code, 404)

    def test_restoring_brings_it_back_everywhere(self):
        moderation.remove_gig(self.admin, self.gig, 'Asks for payment up front.')
        action = moderation.restore_gig(self.admin, self.gig, 'Client fixed the wording.')

        self.gig.refresh_from_db()
        self.assertEqual((self.gig.moderation_status, self.gig.removed_reason), ('visible', ''))
        self.assertEqual((action.action, action.reason), ('restore_gig', 'Client fixed the wording.'))
        self.assertIn(str(self.gig.pk), self.feed_ids(q='bakery'))
        self.assertIn(self.gig, candidate_gigs(self.freelancer))
        kinds = list(Notification.objects.filter(recipient=self.client_user).values_list('kind', flat=True))
        self.assertEqual(sorted(kinds), ['gig_removed', 'gig_restored'])

    def test_the_owner_still_sees_it_marked_removed_but_cannot_change_it(self):
        moderation.remove_gig(self.admin, self.gig, 'Asks for payment up front.')
        self.client.force_authenticate(self.client_user)

        mine = self.client.get('/api/gigs/mine/').data
        self.assertEqual(
            [(row['id'], row['moderation_status'], row['removed_reason']) for row in mine],
            [(str(self.gig.pk), 'removed', 'Asks for payment up front.')],
        )
        detail = self.client.get(f'/api/gigs/{self.gig.pk}/')
        self.assertEqual((detail.status_code, detail.data['moderation_status']), (200, 'removed'))
        self.assertEqual(self.client.patch(f'/api/gigs/{self.gig.pk}/status/', {'status': 'closed'}).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/gigs/{self.gig.pk}/').status_code, 403)
        self.assertTrue(Gig.objects.filter(pk=self.gig.pk).exists())

    def test_freelancers_cannot_apply_to_a_removed_gig(self):
        moderation.remove_gig(self.admin, self.gig, 'Asks for payment up front.')
        self.client.force_authenticate(self.freelancer)
        response = self.client.post(f'/api/gigs/{self.gig.pk}/applications/', {'cover_letter': 'x' * 80})
        self.assertEqual(response.status_code, 404)

    def test_removing_needs_a_reason_and_cannot_happen_twice(self):
        with self.assertRaises(ModerationError):
            moderation.remove_gig(self.admin, self.gig, '')
        moderation.remove_gig(self.admin, self.gig, 'Spam.')
        with self.assertRaises(ModerationError):
            moderation.remove_gig(self.admin, self.gig, 'Spam again.')
        with self.assertRaises(ModerationError):
            moderation.restore_gig(self.admin, self.make_gig(self.client_user, title='Fine gig'))
        self.assertEqual(AdminAction.objects.count(), 1)


class RemoveApplicationTests(ModerationTestCase):
    def setUp(self):
        super().setUp()
        self.application = self.apply(self.gig, self.freelancer)

    def test_a_removed_application_is_hidden_from_the_client(self):
        moderation.remove_application(self.admin, self.application, 'Abusive cover letter.')
        self.client.force_authenticate(self.client_user)

        listing = self.client.get(f'/api/gigs/{self.gig.pk}/applications/').data
        self.assertEqual(listing['results'], [])
        self.assertEqual(listing['status_counts']['total'], 0)
        self.assertEqual(self.client.get('/api/gigs/mine/').data[0]['application_count'], 0)
        self.assertEqual(self.client.get(f'/api/applications/{self.application.pk}/').status_code, 404)
        response = self.client.patch(f'/api/applications/{self.application.pk}/status/', {'status': 'under_review'})
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(self.application, applications_for_training())

    def test_the_freelancer_still_sees_it_marked_removed(self):
        moderation.remove_application(self.admin, self.application, 'Abusive cover letter.')
        self.client.force_authenticate(self.freelancer)

        row = self.client.get('/api/applications/mine/').data['results'][0]
        self.assertEqual((row['moderation_status'], row['removed_reason']), ('removed', 'Abusive cover letter.'))
        self.assertEqual(self.client.get(f'/api/applications/{self.application.pk}/').status_code, 200)
        note = Notification.objects.get(recipient=self.freelancer)
        self.assertEqual((note.kind, note.link), ('application_removed', f'/applications/{self.application.pk}'))

    def test_restoring_shows_it_to_the_client_again(self):
        moderation.remove_application(self.admin, self.application, 'Abusive cover letter.')
        moderation.restore_application(self.admin, self.application)
        self.client.force_authenticate(self.client_user)
        listing = self.client.get(f'/api/gigs/{self.gig.pk}/applications/').data
        self.assertEqual([row['id'] for row in listing['results']], [str(self.application.pk)])
        self.assertEqual(
            list(AdminAction.objects.order_by('created_at').values_list('action', flat=True)),
            ['remove_application', 'restore_application'],
        )


class VerificationDecisionTests(ModerationTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.freelancer.freelancer_profile
        self.profile.verification_status = FreelancerProfile.VerificationStatus.PENDING
        self.profile.save(update_fields=['verification_status'])

    def test_approving_records_it_against_the_freelancer(self):
        action = moderation.decide_verification(self.admin, self.profile, approve=True)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.verification_status, 'verified')
        self.assertEqual(
            (action.action, action.target_type, action.target_id), ('verify_approve', 'user', self.freelancer.pk),
        )
        self.assertEqual(Notification.objects.get(recipient=self.freelancer).kind, 'verification_approved')

    def test_rejecting_needs_a_reason(self):
        with self.assertRaises(ModerationError):
            moderation.decide_verification(self.admin, self.profile, approve=False)
        action = moderation.decide_verification(self.admin, self.profile, approve=False, reason='The photo is blurred.')
        self.assertEqual((action.action, action.reason), ('verify_reject', 'The photo is blurred.'))

    def test_only_pending_verifications_can_be_decided(self):
        moderation.decide_verification(self.admin, self.profile, approve=True)
        with self.assertRaisesMessage(ModerationError, 'already been decided'):
            moderation.decide_verification(self.admin, self.profile, approve=False, reason='Changed my mind.')


class AdminActionConstraintTests(ModerationTestCase):
    def test_the_database_refuses_a_negative_action_without_a_reason(self):
        for action in AdminAction.NEGATIVE_ACTIONS:
            with self.subTest(action=action), self.assertRaises(IntegrityError), transaction.atomic():
                AdminAction.objects.create(
                    admin=self.admin, action=action, target_type='user', target_id=self.client_user.pk, reason='',
                )

    def test_restores_and_approvals_may_have_no_reason(self):
        AdminAction.objects.create(
            admin=self.admin, action=AdminAction.Action.RESTORE_GIG, target_type='gig', target_id=self.gig.pk,
        )
        self.assertEqual(AdminAction.objects.count(), 1)

    def test_every_negative_action_value_is_an_action(self):
        self.assertTrue(set(AdminAction.NEGATIVE_ACTIONS) <= set(AdminAction.Action.values))
