from unittest import mock

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from accounts.services import CLOSED_FOR_OTHER_PARTY
from accounts.testing import DeletionWorld
from applications.models import Application
from gigs.models import Gig
from notifications.models import Notification

from .models import AdminAction
from .moderation import mask_email


def suspend(user):
    User.objects.filter(pk=user.pk).update(account_status='suspended', suspended_at=timezone.now())
    user.refresh_from_db()
    return user


class AdminDeleteTestCase(DeletionWorld, APITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.person('admin@example.com', 'admin', 'Asha Admin', is_staff=True)

    def delete(self, user, as_admin=None, **body):
        self.client.force_authenticate(as_admin or self.admin)
        data = {'reason': 'Repeated fraud reports.', 'confirm_email': user.email, **body}
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/admin/users/{user.pk}/delete/', data, format='json')
        self.client.force_authenticate(None)
        return response


class SameEffectsAsSelfDeletionTests(AdminDeleteTestCase):
    """The same checks as accounts.test_deletion.SelfDeletionTests, through the admin path."""

    def test_a_freelancer_is_erased(self):
        world = self.build_world('freelancer')
        response = self.delete(suspend(world['user']))
        self.assertEqual(response.status_code, 200, response.data)
        self.assert_erased()
        summary = response.data['summary']
        self.assertEqual((summary['id_files_deleted'], summary['id_number_deleted']), (2, True))
        self.assertEqual((summary['applications_emptied'], summary['conversations_read_only']), (2, 1))

    def test_a_client_is_erased_and_their_open_gigs_close(self):
        world = self.build_world('client')
        response = self.delete(suspend(world['user']))
        self.assertEqual(response.status_code, 200, response.data)
        self.assert_erased()
        summary = response.data['summary']
        self.assertEqual((summary['gigs_closed'], summary['applicants_notified']), (1, 2))


class RulesTests(AdminDeleteTestCase):
    def setUp(self):
        super().setUp()
        self.target = self.person('otieno@example.com', 'freelancer', 'Otieno Designs')

    def refused(self, response, message):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], message)
        self.assertIsNone(User.objects.get(pk=self.target.pk).deleted_at)

    def test_an_active_account_must_be_suspended_first(self):
        self.refused(self.delete(self.target), 'Suspend this account first. Only suspended accounts can be deleted.')

    def test_not_yourself_and_not_another_admin(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/api/admin/users/{self.admin.pk}/delete/', {
            'reason': 'x', 'confirm_email': self.admin.email,
        })
        self.assertEqual((response.status_code, response.data['detail']), (400, "You can't delete your own account."))
        other = suspend(self.person('admin2@example.com', 'admin', 'Baraka Admin', is_staff=True))
        response = self.delete(other)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], "Admin accounts can't be deleted here.")
        self.assertIsNone(User.objects.get(pk=other.pk).deleted_at)

    def test_the_typed_email_must_match_exactly(self):
        suspend(self.target)
        self.refused(self.delete(self.target, confirm_email='OTIENO@example.com'),
                     "The email you typed doesn't match this account's email.")

    def test_a_reason_is_required(self):
        suspend(self.target)
        self.refused(self.delete(self.target, reason='  '), 'Give a reason. The person affected is told what it says.')

    def test_only_admins(self):
        suspend(self.target)
        other = self.person('wanjiru@example.com', 'client', 'Wanjiru Bakers')
        self.client.force_authenticate(other)
        url = f'/api/admin/users/{self.target.pk}/'
        body = {'reason': 'x', 'confirm_email': self.target.email}
        self.assertEqual(self.client.post(url + 'delete/', body).status_code, 403)
        self.assertEqual(self.client.get(url + 'delete-preview/').status_code, 403)
        self.assertIsNone(User.objects.get(pk=self.target.pk).deleted_at)

    def test_the_preview_says_what_will_happen_and_what_stops_it(self):
        self.client.force_authenticate(self.admin)
        url = f'/api/admin/users/{self.target.pk}/delete-preview/'
        preview = self.client.get(url).data
        self.assertEqual((preview['can_delete'], preview['refusal']),
                         (False, 'Suspend this account first. Only suspended accounts can be deleted.'))
        suspend(self.target)
        preview = self.client.get(url).data
        self.assertTrue(preview['can_delete'])
        self.assertEqual((preview['applications_emptied'], preview['active_work']), (0, []))


class ActiveWorkTests(AdminDeleteTestCase):
    def setUp(self):
        super().setUp()
        self.client_user = self.person('wanjiru@example.com', 'client', 'Wanjiru Bakers')
        self.freelancer = self.person('otieno@example.com', 'freelancer', 'Otieno Designs')
        self.running = self.gig(self.client_user, 'Shop signage', status='in_progress')
        Application.objects.create(
            gig=self.running, freelancer=self.freelancer, cover_letter='x' * 60, status='hired',
        )

    def test_blocked_and_listed_without_force(self):
        response = self.delete(suspend(self.freelancer))
        self.assertEqual((response.status_code, response.data['code']), (400, 'active_work'))
        self.assertEqual([item['title'] for item in response.data['active_work']], ['Shop signage'])
        self.assertIsNone(User.objects.get(pk=self.freelancer.pk).deleted_at)
        self.assertEqual(Gig.objects.get(pk=self.running.pk).status, 'in_progress')

    def test_force_closes_the_gig_and_tells_the_client(self):
        response = self.delete(suspend(self.freelancer), force=True)
        self.assertEqual(response.status_code, 200, response.data)
        gig = Gig.objects.get(pk=self.running.pk)
        self.assertEqual(gig.status, 'closed')
        self.assertIsNotNone(gig.status_changed_at)
        notice = Notification.objects.get(recipient=self.client_user, kind='gig_closed')
        self.assertEqual(notice.body, CLOSED_FOR_OTHER_PARTY)

    def test_force_on_a_client_tells_the_hired_freelancer(self):
        response = self.delete(suspend(self.client_user), force=True)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Gig.objects.get(pk=self.running.pk).status, 'closed')
        notice = Notification.objects.get(recipient=self.freelancer, kind='gig_closed')
        self.assertEqual(notice.body, 'This gig was closed because the other account was removed.')


@override_settings(PRIVACY_CONTACT_EMAIL='privacy@example.com')
class RecordAndEmailTests(AdminDeleteTestCase):
    def setUp(self):
        super().setUp()
        self.target = suspend(self.person('otieno.designs@gmail.com', 'freelancer', 'Otieno Designs'))

    def test_the_audit_log_keeps_only_a_masked_email(self):
        self.delete(self.target)
        action = AdminAction.objects.get(action='delete_user')
        self.assertEqual((action.admin, action.target_id), (self.admin, self.target.pk))
        self.assertEqual(action.reason, 'Repeated fraud reports.')
        self.assertEqual(action.target_label, 'Deleted user · o***@gmail.com')
        for value in (action.target_label, action.reason):
            self.assertNotIn('otieno.designs', value)
            self.assertNotIn('Otieno Designs', value)
        self.client.force_authenticate(self.admin)
        row = self.client.get('/api/admin/audit-log/').data['results'][0]
        self.assertEqual((row['action_label'], row['target_label']), ('Deleted user', 'Deleted user · o***@gmail.com'))

    def test_the_person_is_emailed_at_their_old_address_after_the_deletion(self):
        self.delete(self.target)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['otieno.designs@gmail.com'])
        self.assertIn('Your GigConnect account has been deleted by an administrator. Reason: Repeated fraud reports.',
                      email.body)
        self.assertIn('privacy@example.com', email.body)

    def test_a_failed_email_does_not_stop_the_deletion(self):
        with mock.patch('adminpanel.moderation.send_mail', side_effect=OSError('SMTP down')):
            response = self.delete(self.target)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(User.objects.get(pk=self.target.pk).deleted_at)

    def test_a_refused_deletion_sends_nothing(self):
        self.delete(self.target, confirm_email='wrong@example.com')
        self.assertEqual(mail.outbox, [])

    def test_the_deleted_filter_shows_what_is_left(self):
        self.delete(self.target)
        self_deleted = self.person('gone@example.com', 'client', 'Gone Client')
        User.objects.filter(pk=self_deleted.pk).update(deleted_at=timezone.now(), is_active=False)
        self.client.force_authenticate(self.admin)
        rows = {row['id']: row['deletion'] for row in
                self.client.get('/api/admin/users/', {'status': 'deleted'}).data['results']}
        self.assertEqual(rows[str(self.target.pk)]['label'], 'Deleted user · o***@gmail.com')
        self.assertEqual(rows[str(self.target.pk)]['by'], 'Asha Admin')
        self.assertEqual((rows[str(self_deleted.pk)]['label'], rows[str(self_deleted.pk)]['by']),
                         ('Deleted user', 'themselves'))


class MaskTests(APITestCase):
    def test_masking(self):
        self.assertEqual(mask_email('jane.doe@gmail.com'), 'j***@gmail.com')
        self.assertEqual(mask_email('x@y.co'), 'x***@y.co')
        self.assertEqual(mask_email('not-an-email'), '***')
