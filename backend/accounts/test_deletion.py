from django.utils import timezone
from rest_framework.test import APITestCase

from applications.models import Application
from gigs.models import Gig
from notifications.models import Notification

from .models import User
from .services import ACTIVE_WORK_MESSAGE, deletion_preview
from .testing import PASSWORD, DeletionWorld


class SelfDeletionTests(DeletionWorld, APITestCase):
    """Privacy & Data: deleting your own account, through the shared service."""

    def delete(self, user):
        self.client.force_authenticate(user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/settings/delete-account/', {'password': PASSWORD})
        self.client.force_authenticate(None)
        return response

    def test_a_freelancer_is_erased(self):
        world = self.build_world('freelancer')
        self.assertEqual(self.delete(world['user']).status_code, 200)
        self.assert_erased()

    def test_a_client_is_erased_and_their_open_gigs_close_with_the_applicants_told(self):
        world = self.build_world('client')
        self.assertEqual(self.delete(world['user']).status_code, 200)
        self.assert_erased()
        # Both freelancers with a pending application on the open gig get one notice each.
        self.assertEqual(Notification.objects.filter(kind='gig_closed').count(), 2)

    def test_a_wrong_password_deletes_nothing(self):
        world = self.build_world('freelancer')
        self.client.force_authenticate(world['user'])
        response = self.client.post('/api/settings/delete-account/', {'password': 'wrong'})
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(User.objects.get(pk=world['user'].pk).deleted_at)


class ActiveWorkTests(DeletionWorld, APITestCase):
    """In-progress work blocks self-deletion. There is no way for a user to force it."""

    def setUp(self):
        super().setUp()
        self.client_user = self.person('wanjiru@example.com', 'client', 'Wanjiru Bakers')
        self.freelancer = self.person('otieno@example.com', 'freelancer', 'Otieno Designs')
        self.gig_running = self.gig(self.client_user, 'Shop signage', status='in_progress')
        Application.objects.create(
            gig=self.gig_running, freelancer=self.freelancer, cover_letter='x' * 60, status='hired',
        )

    def attempt(self, user, **extra):
        self.client.force_authenticate(user)
        return self.client.post('/api/settings/delete-account/', {'password': PASSWORD, **extra})

    def test_a_client_with_an_in_progress_gig_is_blocked_and_shown_it(self):
        response = self.attempt(self.client_user)
        self.assertEqual(response.status_code, 400)
        self.assertEqual((response.data['code'], response.data['detail']), ('active_work', ACTIVE_WORK_MESSAGE))
        self.assertEqual(response.data['active_work'], [{
            'gig_id': str(self.gig_running.pk), 'title': 'Shop signage', 'as': 'client',
            'other_party': 'Otieno Designs',
        }])
        self.assertIsNone(User.objects.get(pk=self.client_user.pk).deleted_at)
        self.assertEqual(Gig.objects.get(pk=self.gig_running.pk).status, 'in_progress')

    def test_a_hired_freelancer_is_blocked_and_cannot_force_it(self):
        response = self.attempt(self.freelancer, force=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['active_work'][0]['as'], 'freelancer')
        self.assertEqual(response.data['active_work'][0]['other_party'], 'Wanjiru Bakers')
        self.assertIsNone(User.objects.get(pk=self.freelancer.pk).deleted_at)

    def test_finished_work_does_not_block(self):
        Gig.objects.filter(pk=self.gig_running.pk).update(status='completed', status_changed_at=timezone.now())
        self.assertEqual(self.attempt(self.freelancer).status_code, 200)

    def test_the_preview_lists_it(self):
        preview = deletion_preview(self.client_user)
        self.assertEqual([item['title'] for item in preview['active_work']], ['Shop signage'])
