from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from profiles.models import Skill

from .models import Category, Gig


class GigTestBase(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Test Category')
        self.skill = Skill.objects.create(name='Test Skill', category='Technology')

        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!',
            full_name='Client', phone='254700000001', role='client',
        )
        self.client_user.is_email_verified = True
        self.client_user.save(update_fields=['is_email_verified'])

        self.other_client = User.objects.create_user(
            email='other-client@example.com', password='StrongPass123!',
            full_name='Other Client', phone='254700000002', role='client',
        )
        self.other_client.is_email_verified = True
        self.other_client.save(update_fields=['is_email_verified'])

        self.unverified_client = User.objects.create_user(
            email='unverified-client@example.com', password='StrongPass123!',
            full_name='Unverified Client', phone='254700000003', role='client',
        )

        self.freelancer = User.objects.create_user(
            email='freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000004', role='freelancer',
        )
        self.freelancer.freelancer_profile.skills.set([self.skill])

    def valid_payload(self, **overrides):
        payload = {
            'title': 'Build a landing page',
            'description': 'Need a landing page for my restaurant.',
            'category': str(self.category.id),
            'budget_min': '10000.00',
            'budget_max': '20000.00',
            'deadline': str(date.today() + timedelta(days=30)),
            'skills': [str(self.skill.id)],
        }
        payload.update(overrides)
        return payload

    def create_gig(self, client_user=None, **overrides):
        client_user = client_user or self.client_user
        fields = {
            'category': self.category,
            'title': 'Existing gig',
            'description': 'Existing description.',
            'budget_min': 1000,
            'budget_max': 2000,
            'deadline': date.today() + timedelta(days=30),
        }
        fields.update(overrides)
        gig = Gig.objects.create(client=client_user, **fields)
        gig.skills.set([self.skill])
        return gig


class GigCreationTests(GigTestBase):
    def test_create_gig_succeeds_with_valid_data(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post('/api/gigs/', self.valid_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Gig.objects.count(), 1)
        self.assertEqual(response.data['status'], 'open')

    def test_create_gig_fails_when_budget_max_less_than_min(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(
            '/api/gigs/', self.valid_payload(budget_min='5000', budget_max='1000'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('budget_max', response.data)

    def test_create_gig_fails_for_past_deadline(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(
            '/api/gigs/', self.valid_payload(deadline=str(date.today() - timedelta(days=1))), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('deadline', response.data)

    def test_create_gig_fails_for_freelancer_role(self):
        self.client.force_authenticate(user=self.freelancer)
        response = self.client.post('/api/gigs/', self.valid_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_gig_fails_for_unverified_client(self):
        self.client.force_authenticate(user=self.unverified_client)
        response = self.client.post('/api/gigs/', self.valid_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_gig_requires_authentication(self):
        response = self.client.post('/api/gigs/', self.valid_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class GigOwnershipTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.gig = self.create_gig()

    def test_owner_can_update_own_gig(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.put(
            f'/api/gigs/{self.gig.id}/', self.valid_payload(title='Updated title'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.gig.refresh_from_db()
        self.assertEqual(self.gig.title, 'Updated title')

    def test_other_client_cannot_update_gig(self):
        self.client.force_authenticate(user=self.other_client)
        response = self.client.put(
            f'/api/gigs/{self.gig.id}/', self.valid_payload(title='Hijacked'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_freelancer_cannot_update_gig(self):
        self.client.force_authenticate(user=self.freelancer)
        response = self.client.put(
            f'/api/gigs/{self.gig.id}/', self.valid_payload(title='Hijacked'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_client_cannot_delete_gig(self):
        self.client.force_authenticate(user=self.other_client)
        response = self.client.delete(f'/api/gigs/{self.gig.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_delete_own_gig(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.delete(f'/api/gigs/{self.gig.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Gig.objects.filter(id=self.gig.id).exists())

    def test_other_client_cannot_change_status(self):
        self.client.force_authenticate(user=self.other_client)
        response = self.client.patch(f'/api/gigs/{self.gig.id}/status/', {'status': 'in_progress'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_on_main_detail_route_not_allowed(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.patch(f'/api/gigs/{self.gig.id}/', {'status': 'in_progress'})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class GigStatusTransitionTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.gig = self.create_gig()
        self.client.force_authenticate(user=self.client_user)

    def status_url(self, gig=None):
        return f'/api/gigs/{(gig or self.gig).id}/status/'

    def test_open_to_completed_directly_is_rejected(self):
        response = self.client.patch(self.status_url(), {'status': 'completed'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.gig.refresh_from_db()
        self.assertEqual(self.gig.status, Gig.Status.OPEN)

    def test_open_to_in_progress_is_allowed(self):
        response = self.client.patch(self.status_url(), {'status': 'in_progress'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.gig.refresh_from_db()
        self.assertEqual(self.gig.status, Gig.Status.IN_PROGRESS)

    def test_in_progress_to_completed_is_allowed(self):
        self.gig.status = Gig.Status.IN_PROGRESS
        self.gig.save(update_fields=['status'])
        response = self.client.patch(self.status_url(), {'status': 'completed'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_open_to_closed_is_allowed_as_cancellation(self):
        response = self.client.patch(self.status_url(), {'status': 'closed'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_completed_is_a_terminal_state(self):
        self.gig.status = Gig.Status.COMPLETED
        self.gig.save(update_fields=['status'])
        response = self.client.patch(self.status_url(), {'status': 'open'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class GigEditLockTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.gig = self.create_gig()
        self.client.force_authenticate(user=self.client_user)

    def test_editing_blocked_once_in_progress(self):
        self.gig.status = Gig.Status.IN_PROGRESS
        self.gig.save(update_fields=['status'])
        response = self.client.put(
            f'/api/gigs/{self.gig.id}/', self.valid_payload(title='Should not apply'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.gig.refresh_from_db()
        self.assertNotEqual(self.gig.title, 'Should not apply')

    def test_editing_blocked_once_completed(self):
        self.gig.status = Gig.Status.COMPLETED
        self.gig.save(update_fields=['status'])
        response = self.client.put(
            f'/api/gigs/{self.gig.id}/', self.valid_payload(title='Should not apply'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class GigSerializationTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.gig = self.create_gig()

    def test_list_payload_excludes_full_description(self):
        response = self.client.get('/api/gigs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('description', response.data[0])

    def test_detail_payload_includes_description(self):
        response = self.client.get(f'/api/gigs/{self.gig.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('description', response.data)

    def test_view_count_increments_on_retrieve(self):
        self.assertEqual(self.gig.view_count, 0)
        self.client.get(f'/api/gigs/{self.gig.id}/')
        self.gig.refresh_from_db()
        self.assertEqual(self.gig.view_count, 1)
        self.client.get(f'/api/gigs/{self.gig.id}/')
        self.gig.refresh_from_db()
        self.assertEqual(self.gig.view_count, 2)

    def test_list_only_shows_open_gigs(self):
        closed_gig = self.create_gig(title='Closed gig', status=Gig.Status.CLOSED)
        response = self.client.get('/api/gigs/')
        ids = [g['id'] for g in response.data]
        self.assertIn(str(self.gig.id), ids)
        self.assertNotIn(str(closed_gig.id), ids)

    def test_my_gigs_shows_all_statuses_for_owner(self):
        closed_gig = self.create_gig(title='Closed gig', status=Gig.Status.CLOSED)
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get('/api/gigs/mine/')
        ids = [g['id'] for g in response.data]
        self.assertIn(str(self.gig.id), ids)
        self.assertIn(str(closed_gig.id), ids)

    def test_my_gigs_forbidden_for_freelancer(self):
        self.client.force_authenticate(user=self.freelancer)
        response = self.client.get('/api/gigs/mine/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CategoryTests(GigTestBase):
    def test_categories_are_publicly_listable(self):
        response = self.client.get('/api/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)


class GigPrerequisiteFieldTests(GigTestBase):
    def test_application_deadline_defaults_to_deadline_when_not_given(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post('/api/gigs/', self.valid_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['application_deadline'], response.data['deadline'])

    def test_application_deadline_can_be_set_explicitly(self):
        self.client.force_authenticate(user=self.client_user)
        earlier = str(date.today() + timedelta(days=10))
        response = self.client.post(
            '/api/gigs/', self.valid_payload(application_deadline=earlier), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['application_deadline'], earlier)

    def test_application_deadline_after_project_deadline_is_rejected(self):
        self.client.force_authenticate(user=self.client_user)
        too_late = str(date.today() + timedelta(days=60))
        response = self.client.post(
            '/api/gigs/', self.valid_payload(application_deadline=too_late), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('application_deadline', response.data)

    def test_is_negotiable_defaults_true(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post('/api/gigs/', self.valid_payload(), format='json')
        self.assertTrue(response.data['is_negotiable'])

    def test_is_negotiable_can_be_set_false(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(
            '/api/gigs/', self.valid_payload(is_negotiable=False), format='json'
        )
        self.assertFalse(response.data['is_negotiable'])

    def test_existing_gig_created_without_application_deadline_gets_backfilled(self):
        gig = self.create_gig()
        self.assertEqual(gig.application_deadline, gig.deadline)


class GigDescriptionIndexTests(APITestCase):
    def test_gin_index_exists_on_description(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexdef FROM pg_indexes WHERE indexname = 'gig_description_gin'"
            )
            row = cursor.fetchone()
        self.assertIsNotNone(row, 'Expected a GIN index named gig_description_gin on gigs_gig')
        self.assertIn('gin', row[0].lower())
