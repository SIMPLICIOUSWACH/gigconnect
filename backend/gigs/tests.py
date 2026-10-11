from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.contrib.postgres.search import SearchQuery
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import User
from profiles.models import Skill

from .models import Category, Gig, GigInteraction


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


class CurrencyLockTests(GigTestBase):
    def test_create_without_currency_defaults_to_kes(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post('/api/gigs/', self.valid_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Gig.objects.get().currency, 'KES')

    def test_create_with_non_kes_currency_rejected(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(
            '/api/gigs/', self.valid_payload(currency='USD'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('currency', response.data)
        self.assertEqual(Gig.objects.count(), 0)

    def test_budget_filter_excludes_non_kes_rows_even_when_numbers_overlap(self):
        # Bypasses the serializer (which now rejects this) to model a pre-existing or imported
        # non-KES row and prove the budget filter doesn't compare its raw numbers as if KES.
        usd_gig = self.create_gig(title='USD gig', budget_min=10000, budget_max=20000, currency='USD')
        kes_gig = self.create_gig(title='KES gig', budget_min=10000, budget_max=20000)

        response = self.client.get('/api/gigs/', {'budget_min': '15000', 'budget_max': '30000'})
        titles = [g['title'] for g in response.data['results']]
        self.assertIn('KES gig', titles)
        self.assertNotIn('USD gig', titles)
        self.assertTrue(Gig.objects.filter(pk=usd_gig.pk).exists())  # the row itself is untouched
        self.assertTrue(Gig.objects.filter(pk=kes_gig.pk).exists())


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
        self.assertNotIn('description', response.data['results'][0])

    def test_detail_payload_includes_description(self):
        response = self.client.get(f'/api/gigs/{self.gig.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('description', response.data)

    def test_view_count_increments_on_retrieve(self):
        self.assertEqual(self.gig.view_count, 0)
        self.client.get(f'/api/gigs/{self.gig.id}/')
        self.gig.refresh_from_db()
        self.assertEqual(self.gig.view_count, 1)
        # A second, different visitor counts; the same visitor again would not (see ViewCountDedupeTests).
        self.client.force_authenticate(user=self.freelancer)
        self.client.get(f'/api/gigs/{self.gig.id}/')
        self.gig.refresh_from_db()
        self.assertEqual(self.gig.view_count, 2)

    def test_list_only_shows_open_gigs(self):
        closed_gig = self.create_gig(title='Closed gig', status=Gig.Status.CLOSED)
        response = self.client.get('/api/gigs/')
        ids = [g['id'] for g in response.data['results']]
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


class GigFilterSearchTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.other_category = Category.objects.create(name='Other Test Category')
        self.other_skill = Skill.objects.create(name='Other Test Skill', category='Design')

        self.bakery_gig = self.create_gig(
            title='Bakery website in Nairobi',
            description='Simple site for a bakery',
            budget_min=10000, budget_max=20000,
        )
        self.logo_gig = self.create_gig(
            title='Logo design',
            description='Need a bakery logo',
            budget_min=5000, budget_max=8000,
            category=self.other_category,
        )
        self.logo_gig.skills.set([self.other_skill])

    def test_filter_by_category(self):
        response = self.client.get('/api/gigs/', {'category': self.other_category.slug})
        titles = [g['title'] for g in response.data['results']]
        self.assertEqual(titles, ['Logo design'])

    def test_filter_by_skills_matches_any(self):
        response = self.client.get('/api/gigs/', {'skills': str(self.skill.id)})
        titles = [g['title'] for g in response.data['results']]
        self.assertEqual(titles, ['Bakery website in Nairobi'])

    def test_filter_by_skill_name_case_insensitive(self):
        response = self.client.get('/api/gigs/', {'skills': 'other test skill'})
        titles = [g['title'] for g in response.data['results']]
        self.assertEqual(titles, ['Logo design'])

    def test_budget_overlap_matches(self):
        response = self.client.get('/api/gigs/', {'budget_min': '15000', 'budget_max': '30000'})
        titles = [g['title'] for g in response.data['results']]
        self.assertEqual(titles, ['Bakery website in Nairobi'])

    def test_budget_no_overlap_excludes(self):
        response = self.client.get('/api/gigs/', {'budget_min': '25000', 'budget_max': '30000'})
        self.assertEqual(response.data['count'], 0)

    def test_negotiable_filter(self):
        self.logo_gig.is_negotiable = False
        self.logo_gig.save()
        response = self.client.get('/api/gigs/', {'negotiable': 'false'})
        titles = [g['title'] for g in response.data['results']]
        self.assertEqual(titles, ['Logo design'])

    def test_deadline_before_filter(self):
        self.create_gig(title='Near deadline gig', deadline=date.today() + timedelta(days=1))
        response = self.client.get('/api/gigs/', {'deadline_before': str(date.today() + timedelta(days=2))})
        titles = [g['title'] for g in response.data['results']]
        self.assertEqual(titles, ['Near deadline gig'])

    def test_posted_within_filter(self):
        from django.utils import timezone
        old_gig = self.create_gig(title='Old gig')
        Gig.objects.filter(pk=old_gig.pk).update(created_at=timezone.now() - timedelta(days=10))
        response = self.client.get('/api/gigs/', {'posted_within': '7'})
        titles = [g['title'] for g in response.data['results']]
        self.assertNotIn('Old gig', titles)

    def test_filters_combine_with_and(self):
        response = self.client.get('/api/gigs/', {
            'category': str(self.category.slug),
            'budget_min': '15000', 'budget_max': '30000',
        })
        titles = [g['title'] for g in response.data['results']]
        self.assertEqual(titles, ['Bakery website in Nairobi'])

    def test_only_open_gigs_appear_in_feed(self):
        for gig_status in [Gig.Status.IN_PROGRESS, Gig.Status.COMPLETED, Gig.Status.CLOSED]:
            self.create_gig(title=f'{gig_status} gig', status=gig_status)
        response = self.client.get('/api/gigs/')
        titles = [g['title'] for g in response.data['results']]
        self.assertEqual(set(titles), {'Bakery website in Nairobi', 'Logo design'})

    def test_gig_past_application_deadline_excluded_from_feed_but_retrievable_by_id(self):
        expired = self.create_gig(
            title='Expired gig',
            deadline=date.today() + timedelta(days=30),
            application_deadline=date.today() - timedelta(days=1),
        )
        response = self.client.get('/api/gigs/')
        titles = [g['title'] for g in response.data['results']]
        self.assertNotIn('Expired gig', titles)

        detail_response = self.client.get(f'/api/gigs/{expired.id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['title'], 'Expired gig')

    def test_search_ranks_title_match_above_description_only_match(self):
        response = self.client.get('/api/gigs/', {'q': 'bakery', 'sort': 'relevance'})
        titles = [g['title'] for g in response.data['results']]
        self.assertEqual(titles, ['Bakery website in Nairobi', 'Logo design'])

    def test_search_handles_punctuation_without_error(self):
        response = self.client.get('/api/gigs/', {'q': 'bakery!! -- (()) stray quote follows'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_handles_empty_string(self):
        response = self.client.get('/api/gigs/', {'q': ''})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_relevance_sort_without_query_falls_back_to_newest(self):
        response = self.client.get('/api/gigs/', {'sort': 'relevance'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Same order as an explicit sort=newest, not merely "didn't error": logo_gig was
        # created after bakery_gig, so newest-first puts it first.
        titles = [g['title'] for g in response.data['results']]
        self.assertEqual(titles, ['Logo design', 'Bakery website in Nairobi'])

    def test_invalid_category_returns_400_with_field_error(self):
        response = self.client.get('/api/gigs/', {'category': 'does-not-exist'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('category', response.data)

    def test_invalid_posted_within_returns_400(self):
        response = self.client.get('/api/gigs/', {'posted_within': '5'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('posted_within', response.data)

    def test_budget_min_greater_than_budget_max_returns_400(self):
        response = self.client.get('/api/gigs/', {'budget_min': '50000', 'budget_max': '1000'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('budget_min', response.data)

    def test_invalid_sort_returns_400(self):
        response = self.client.get('/api/gigs/', {'sort': 'not-a-real-sort'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pagination_metadata(self):
        for i in range(15):
            self.create_gig(title=f'Paginated gig {i}')
        response = self.client.get('/api/gigs/', {'page_size': '5'})
        self.assertEqual(response.data['page_size'], 5)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['total_pages'], 4)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])

    def test_page_size_is_capped_at_50(self):
        response = self.client.get('/api/gigs/', {'page_size': '200'})
        self.assertEqual(response.data['page_size'], 50)

    def test_default_page_size_is_12(self):
        for i in range(20):
            self.create_gig(title=f'Default page size gig {i}')
        response = self.client.get('/api/gigs/')
        self.assertEqual(len(response.data['results']), 12)

    def test_list_endpoint_has_no_n_plus_1_query(self):
        for i in range(10):
            gig = self.create_gig(title=f'N+1 test gig {i}')
            gig.skills.set([self.skill, self.other_skill])
        # 1 count query (pagination) + 1 joined select (client/client_profile/category via
        # select_related) + 1 prefetch for skills — flat regardless of how many gigs are on
        # the page, which is the actual thing this test is guarding against.
        with self.assertNumQueries(3):
            response = self.client.get('/api/gigs/', {'page_size': 50})
            self.assertEqual(response.status_code, status.HTTP_200_OK)


class ViewCountDedupeTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.gig = self.create_gig()
        self.url = f'/api/gigs/{self.gig.id}/'

    def views(self):
        self.gig.refresh_from_db()
        return self.gig.view_count

    def test_same_user_counts_once_within_24_hours(self):
        self.client.force_authenticate(user=self.freelancer)
        for _ in range(3):
            self.client.get(self.url)
        self.assertEqual(self.views(), 1)

    def test_same_user_counts_again_after_24_hours(self):
        self.client.force_authenticate(user=self.freelancer)
        self.client.get(self.url)
        GigInteraction.objects.update(created_at=timezone.now() - timedelta(hours=25))
        self.client.get(self.url)
        self.assertEqual(self.views(), 2)

    def test_different_users_each_count(self):
        for user in (self.freelancer, self.other_client):
            self.client.force_authenticate(user=user)
            self.client.get(self.url)
        self.assertEqual(self.views(), 2)

    def test_owner_viewing_their_own_gig_never_counts(self):
        self.client.force_authenticate(user=self.client_user)
        for _ in range(3):
            self.client.get(self.url)
        self.assertEqual(self.views(), 0)
        self.assertEqual(GigInteraction.objects.count(), 0)

    def test_anonymous_visitor_is_deduped_by_session(self):
        self.client.get(self.url)
        self.client.get(self.url)  # same client keeps its session cookie
        self.assertEqual(self.views(), 1)

    def test_different_anonymous_sessions_each_count(self):
        APIClient().get(self.url)
        APIClient().get(self.url)
        self.assertEqual(self.views(), 2)

    def test_counted_view_is_logged_as_an_interaction(self):
        self.client.force_authenticate(user=self.freelancer)
        self.client.get(self.url)
        self.client.get(self.url)
        interaction = GigInteraction.objects.get()
        self.assertEqual(interaction.type, GigInteraction.Type.VIEW)
        self.assertEqual(interaction.user, self.freelancer)
        self.assertEqual(interaction.gig, self.gig)

    def test_anonymous_view_is_logged_with_a_session_key(self):
        self.client.get(self.url)
        interaction = GigInteraction.objects.get()
        self.assertIsNone(interaction.user)
        self.assertTrue(interaction.session_key)

    def test_response_reports_the_updated_count(self):
        self.client.force_authenticate(user=self.freelancer)
        first = self.client.get(self.url).data['view_count']
        again = self.client.get(self.url).data['view_count']
        self.assertEqual((first, again), (1, 1))


class SyntheticFlagTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.real_gig = self.create_gig(title='Real gig')
        self.synthetic_gig = self.create_gig(title='Synthetic gig', is_synthetic=True)

    def titles(self, **params):
        return [g['title'] for g in self.client.get('/api/gigs/', params).data['results']]

    def test_gigs_are_not_synthetic_by_default(self):
        self.assertFalse(self.real_gig.is_synthetic)

    @override_settings(SHOW_SYNTHETIC=True)
    def test_feed_shows_synthetic_gigs_when_enabled(self):
        self.assertEqual(set(self.titles()), {'Real gig', 'Synthetic gig'})

    @override_settings(SHOW_SYNTHETIC=False)
    def test_feed_hides_synthetic_gigs_when_disabled(self):
        self.assertEqual(self.titles(), ['Real gig'])

    @override_settings(SHOW_SYNTHETIC=False)
    def test_hiding_applies_with_include_closed_and_search_too(self):
        self.assertEqual(self.titles(include_closed='true'), ['Real gig'])
        self.assertEqual(self.titles(q='gig'), ['Real gig'])

    @override_settings(SHOW_SYNTHETIC=False)
    def test_a_hidden_synthetic_gig_is_still_reachable_by_id(self):
        response = self.client.get(f'/api/gigs/{self.synthetic_gig.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(SHOW_SYNTHETIC=False)
    def test_clients_still_see_their_own_synthetic_gigs_in_my_gigs(self):
        self.client.force_authenticate(user=self.client_user)
        titles = [g['title'] for g in self.client.get('/api/gigs/mine/').data]  # not paginated
        self.assertIn('Synthetic gig', titles)


class MyApplicationFieldTests(GigTestBase):
    LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'

    def setUp(self):
        super().setUp()
        self.gig = self.create_gig()
        self.url = f'/api/gigs/{self.gig.id}/'

    def apply(self, user, **overrides):
        from applications.models import Application

        return Application.objects.create(gig=self.gig, freelancer=user, cover_letter=self.LETTER, **overrides)

    def test_is_null_for_a_freelancer_who_has_not_applied(self):
        self.client.force_authenticate(user=self.freelancer)
        self.assertIsNone(self.client.get(self.url).data['my_application'])

    def test_shows_the_id_and_status_for_a_freelancer_who_applied(self):
        application = self.apply(self.freelancer)
        self.client.force_authenticate(user=self.freelancer)
        self.assertEqual(
            self.client.get(self.url).data['my_application'],
            {'id': str(application.id), 'status': 'pending'},
        )

    def test_reflects_the_current_status(self):
        self.apply(self.freelancer, status='shortlisted')
        self.client.force_authenticate(user=self.freelancer)
        self.assertEqual(self.client.get(self.url).data['my_application']['status'], 'shortlisted')

    def test_only_ever_shows_the_viewers_own_application(self):
        other = User.objects.create_user(
            email='second-freelancer@example.com', password='StrongPass123!',
            full_name='Second', phone='254700000047', role='freelancer',
        )
        self.apply(other)
        self.client.force_authenticate(user=self.freelancer)
        self.assertIsNone(self.client.get(self.url).data['my_application'])

    def test_is_null_for_anonymous_visitors(self):
        self.apply(self.freelancer)
        self.assertIsNone(self.client.get(self.url).data['my_application'])

    def test_is_null_for_clients_even_the_gigs_owner(self):
        self.apply(self.freelancer)
        self.client.force_authenticate(user=self.client_user)
        self.assertIsNone(self.client.get(self.url).data['my_application'])

    def test_the_create_response_includes_the_field_as_null(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post('/api/gigs/', self.valid_payload(), format='json')
        self.assertIn('my_application', response.data)
        self.assertIsNone(response.data['my_application'])


class GigInteractionEndpointTests(GigTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()  # throttle counters live in the cache
        self.gig = self.create_gig()
        self.url = f'/api/gigs/{self.gig.id}/interactions/'

    def post(self, **body):
        return self.client.post(self.url, {'type': 'search_click', **body}, format='json')

    def test_logs_a_search_click_with_query_and_position(self):
        self.client.force_authenticate(user=self.freelancer)
        response = self.post(query='logo design', position=4)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        interaction = GigInteraction.objects.get()
        self.assertEqual(interaction.type, 'search_click')
        self.assertEqual((interaction.query, interaction.position), ('logo design', 4))
        self.assertEqual(interaction.user, self.freelancer)

    def test_query_and_position_are_optional(self):
        self.client.force_authenticate(user=self.freelancer)
        self.assertEqual(self.post().status_code, status.HTTP_201_CREATED)
        interaction = GigInteraction.objects.get()
        self.assertIsNone(interaction.query)
        self.assertIsNone(interaction.position)

    def test_anonymous_visitor_is_logged_by_session(self):
        self.assertEqual(self.post(position=1).status_code, status.HTTP_201_CREATED)
        interaction = GigInteraction.objects.get()
        self.assertIsNone(interaction.user)
        self.assertTrue(interaction.session_key)

    def test_every_click_is_logged_not_deduped(self):
        self.client.force_authenticate(user=self.freelancer)
        self.post()
        self.post()
        self.assertEqual(GigInteraction.objects.count(), 2)

    def test_clients_cannot_post_view_save_or_apply(self):
        for kind in ('view', 'save', 'apply'):
            response = self.client.post(self.url, {'type': kind}, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, kind)
        self.assertEqual(GigInteraction.objects.count(), 0)

    def test_rejects_bad_position_and_overlong_query(self):
        self.assertEqual(self.post(position=0).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.post(query='x' * 201).status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_gig_is_a_404(self):
        response = self.client.post(
            '/api/gigs/00000000-0000-0000-0000-000000000000/interactions/',
            {'type': 'search_click'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_endpoint_is_rate_limited(self):
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', {'gig_interaction': '2/hour'}):
            codes = [self.post().status_code for _ in range(3)]
        self.assertEqual(codes, [201, 201, 429])


class GigInteractionModelTests(GigTestBase):
    def test_anonymous_interaction_needs_no_user(self):
        gig = self.create_gig()
        interaction = GigInteraction.objects.create(
            gig=gig, session_key='abc123', type=GigInteraction.Type.VIEW
        )
        self.assertIsNone(interaction.user)
        self.assertFalse(interaction.is_synthetic)
        self.assertIsNone(interaction.query)
        self.assertIsNone(interaction.position)

    def test_search_click_can_carry_the_query_and_rank(self):
        gig = self.create_gig()
        interaction = GigInteraction.objects.create(
            gig=gig, user=self.freelancer, type=GigInteraction.Type.SEARCH_CLICK, query='logo', position=3
        )
        interaction.refresh_from_db()
        self.assertEqual((interaction.query, interaction.position), ('logo', 3))

    def test_type_choices_are_the_four_agreed_values(self):
        self.assertEqual(
            set(GigInteraction.Type.values), {'view', 'search_click', 'save', 'apply'}
        )

    def test_indexes_for_the_collaborative_filter_exist(self):
        names = {index.name for index in GigInteraction._meta.indexes}
        self.assertEqual(names, {'interaction_user_gig_idx', 'interaction_type_created_idx'})

    def test_deleting_a_gig_deletes_its_interactions(self):
        gig = self.create_gig()
        GigInteraction.objects.create(gig=gig, user=self.freelancer, type=GigInteraction.Type.VIEW)
        gig.delete()
        self.assertEqual(GigInteraction.objects.count(), 0)


class TypoToleranceTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.python_gig = self.create_gig(
            title='Python developer for a REST API', description='Backend work in Django.'
        )

    def titles(self, **params):
        response = self.client.get('/api/gigs/', params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [g['title'] for g in response.data['results']]

    def test_typo_finds_gig_that_full_text_search_misses(self):
        self.assertIn('Python developer for a REST API', self.titles(q='pyhton'))

    def test_exact_matches_rank_above_fuzzy_matches(self):
        self.create_gig(title='Pyhton data cleaning', description='Tidy a spreadsheet.')
        titles = self.titles(q='python', sort='relevance')
        self.assertEqual(titles[0], 'Python developer for a REST API')
        self.assertIn('Pyhton data cleaning', titles)

    def test_unrelated_gigs_are_not_pulled_in(self):
        self.create_gig(title='Wedding photography', description='Capture the day.')
        self.assertNotIn('Wedding photography', self.titles(q='pyhton'))

    @override_settings(SEARCH_FALLBACK_MIN_RESULTS=1)
    def test_no_fuzzy_results_when_enough_exact_matches(self):
        self.create_gig(title='Pyhton data cleaning', description='Tidy a spreadsheet.')
        self.assertEqual(self.titles(q='python'), ['Python developer for a REST API'])

    @override_settings(SEARCH_TRIGRAM_THRESHOLD=0.9)
    def test_threshold_setting_is_respected(self):
        self.assertNotIn('Python developer for a REST API', self.titles(q='pyhton'))


class SkillsModeTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.react = Skill.objects.get(name='React')  # seeded by profiles migration 0005
        self.python = Skill.objects.get(name='Python')
        self.both = self.create_gig(title='Needs both')
        self.both.skills.set([self.react, self.python])
        self.react_only = self.create_gig(title='React only')
        self.react_only.skills.set([self.react])
        self.python_only = self.create_gig(title='Python only')
        self.python_only.skills.set([self.python])

    def titles(self, **params):
        response = self.client.get('/api/gigs/', params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [g['title'] for g in response.data['results']]

    def test_default_mode_is_any(self):
        titles = self.titles(skills='React,Python')
        self.assertEqual(set(titles), {'Needs both', 'React only', 'Python only'})
        self.assertEqual(len(titles), 3)  # a gig with two matching skills is still listed once

    def test_all_mode_requires_every_skill(self):
        self.assertEqual(self.titles(skills='React,Python', skills_mode='all'), ['Needs both'])

    def test_all_mode_with_a_single_skill_matches_like_any(self):
        self.assertEqual(set(self.titles(skills='React', skills_mode='all')), {'Needs both', 'React only'})

    def test_all_mode_with_an_unknown_skill_returns_nothing(self):
        self.assertEqual(self.titles(skills='React,Cobol', skills_mode='all'), [])

    def test_any_mode_ignores_an_unknown_skill(self):
        self.assertEqual(set(self.titles(skills='React,Cobol')), {'Needs both', 'React only'})

    def test_relevance_ranks_by_number_of_matched_skills(self):
        titles = self.titles(skills='React,Python', sort='relevance')
        self.assertEqual(titles[0], 'Needs both')
        self.assertEqual(set(titles[1:]), {'React only', 'Python only'})

    def test_relevance_with_skills_but_no_q_does_not_fall_back_to_newest(self):
        # newest-first would put 'Python only' first; matched-skill ranking puts 'Needs both' first.
        self.assertEqual(self.titles(skills='React,Python', sort='relevance')[0], 'Needs both')

    def test_skill_filter_resolves_aliases_and_spacing(self):
        js = Skill.objects.get(name='JavaScript')
        gig = self.create_gig(title='Needs JavaScript')
        gig.skills.set([js])
        for token in ['JS', 'js', 'javascript', '  JavaScript ']:
            self.assertEqual(self.titles(skills=token), ['Needs JavaScript'], token)

    def test_invalid_skills_mode_is_a_400(self):
        response = self.client.get('/api/gigs/', {'skills': 'React', 'skills_mode': 'some'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('skills_mode', response.data)


class LocationTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.nairobi_gig = self.create_gig(title='Nairobi gig', county='Nairobi')
        self.remote_gig = self.create_gig(title='Remote gig', is_remote=True)
        self.unplaced_gig = self.create_gig(title='Unplaced gig')

    def titles(self, **params):
        response = self.client.get('/api/gigs/', params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [g['title'] for g in response.data['results']]

    def test_filter_by_county(self):
        self.assertEqual(self.titles(county='Nairobi'), ['Nairobi gig'])

    def test_unknown_county_is_a_400(self):
        response = self.client.get('/api/gigs/', {'county': 'Atlantis'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('county', response.data)

    def test_remote_true_only_returns_remote_gigs(self):
        self.assertEqual(self.titles(remote='true'), ['Remote gig'])

    def test_remote_false_excludes_remote_gigs(self):
        self.assertEqual(set(self.titles(remote='false')), {'Nairobi gig', 'Unplaced gig'})

    def test_county_and_remote_combine_with_and(self):
        self.assertEqual(self.titles(county='Nairobi', remote='true'), [])

    def test_create_gig_with_county_and_remote(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post(
            '/api/gigs/', self.valid_payload(county='Mombasa', is_remote=True), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['county'], 'Mombasa')
        self.assertTrue(response.data['is_remote'])

    def test_create_gig_rejects_unknown_county(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post('/api/gigs/', self.valid_payload(county='Atlantis'), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('county', response.data)

    def test_listing_includes_location_fields(self):
        response = self.client.get('/api/gigs/', {'county': 'Nairobi'})
        gig = response.data['results'][0]
        self.assertEqual(gig['county'], 'Nairobi')
        self.assertFalse(gig['is_remote'])


class IncludeClosedFilterTests(GigTestBase):
    def setUp(self):
        super().setUp()
        self.open_gig = self.create_gig(title='Still open')
        self.closed_status_gig = self.create_gig(title='Cancelled gig', status=Gig.Status.CLOSED)
        self.expired_gig = self.create_gig(
            title='Expired application gig',
            deadline=date.today() + timedelta(days=30),
            application_deadline=date.today() - timedelta(days=1),
        )

    def test_default_feed_excludes_closed_status_and_expired_application_deadline(self):
        response = self.client.get('/api/gigs/')
        titles = [g['title'] for g in response.data['results']]
        self.assertIn('Still open', titles)
        self.assertNotIn('Cancelled gig', titles)
        self.assertNotIn('Expired application gig', titles)

    def test_include_closed_true_shows_everything(self):
        response = self.client.get('/api/gigs/', {'include_closed': 'true'})
        titles = [g['title'] for g in response.data['results']]
        self.assertIn('Still open', titles)
        self.assertIn('Cancelled gig', titles)
        self.assertIn('Expired application gig', titles)

    def test_include_closed_combines_with_other_filters(self):
        other_category = Category.objects.create(name='Include-Closed Other Category')
        self.closed_status_gig.category = other_category
        self.closed_status_gig.save(update_fields=['category'])

        response = self.client.get(
            '/api/gigs/', {'include_closed': 'true', 'category': self.category.slug}
        )
        titles = [g['title'] for g in response.data['results']]
        self.assertIn('Still open', titles)
        self.assertNotIn('Cancelled gig', titles)  # different category, still filtered out


@override_settings(DEBUG=True)  # Django forces DEBUG=False during tests by default.
class SeedGigsCommandTests(TestCase):
    def setUp(self):
        Category.objects.create(name='Seed Test Category')
        Skill.objects.create(name='Seed Test Skill', category='Technology')
        self.seed_client = User.objects.create_user(
            email='seed-client-1@example.test', password='SeedPass123!',
            full_name='Seed Client', phone='254700000099', role='client',
        )

    def run_command(self, **options):
        call_command('seed_gigs', stdout=StringIO(), **options)

    @override_settings(DEBUG=False)
    def test_refuses_to_run_when_debug_is_false(self):
        with self.assertRaises(CommandError):
            self.run_command(count=3)
        self.assertEqual(Gig.objects.count(), 0)

    def test_requires_seed_client_accounts(self):
        User.objects.filter(email='seed-client-1@example.test').delete()
        with self.assertRaises(CommandError):
            self.run_command(count=3)

    def test_creates_requested_count(self):
        self.run_command(count=5)
        self.assertEqual(Gig.objects.filter(client__email__startswith='seed-client-').count(), 5)

    def test_seeded_gigs_belong_to_seed_clients_and_are_open(self):
        self.run_command(count=3)
        for gig in Gig.objects.all():
            self.assertTrue(gig.client.email.startswith('seed-client-'))
            self.assertEqual(gig.status, Gig.Status.OPEN)
            self.assertGreaterEqual(gig.skills.count(), 1)

    def test_seeded_gigs_are_flagged_synthetic(self):
        self.run_command(count=3)
        self.assertEqual(Gig.objects.filter(is_synthetic=True).count(), 3)
        self.assertFalse(Gig.objects.filter(is_synthetic=False).exists())

    def test_delete_removes_only_seeded_gigs(self):
        real_client = User.objects.create_user(
            email='real-client@example.com', password='StrongPass123!',
            full_name='Real Client', phone='254700000098', role='client',
        )
        real_gig = Gig.objects.create(
            client=real_client, category=Category.objects.first(),
            title='Real gig', description='Not seed data.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30),
        )
        self.run_command(count=3)
        self.run_command(delete=True)
        self.assertEqual(Gig.objects.filter(client__email__startswith='seed-client-').count(), 0)
        self.assertTrue(Gig.objects.filter(pk=real_gig.pk).exists())


def _findable(term):
    return Gig.objects.filter(search_vector=SearchQuery(term, search_type='websearch'))


class RebuildSearchVectorsTests(TestCase):
    """post_save/m2m_changed never fire for bulk_create, so search_vector is left null for
    anything created that way until this command backfills it."""

    def setUp(self):
        self.category = Category.objects.create(name='Rebuild Test Category')
        self.skill = Skill.objects.create(name='Beekeeping', category='Agriculture')
        self.client_user = User.objects.create_user(
            email='bulk-client@example.com', password='StrongPass123!',
            full_name='Bulk Client', phone='254700000055', role='client',
        )

    def _bulk_create_gig(self, **overrides):
        fields = {
            'client': self.client_user,
            'category': self.category,
            'title': 'Honey harvest consulting',
            'description': 'Need advice on scaling a smallholder apiary.',
            'budget_min': 5000,
            'budget_max': 9000,
            'deadline': date.today() + timedelta(days=30),
        }
        fields.update(overrides)
        gig = Gig.objects.bulk_create([Gig(**fields)])[0]
        return gig

    def test_bulk_created_gig_has_no_search_vector_until_rebuilt(self):
        self._bulk_create_gig()
        self.assertIsNone(Gig.objects.get().search_vector)

    def test_rebuild_makes_bulk_created_gig_findable_by_title_skill_and_description(self):
        gig = self._bulk_create_gig()
        gig.skills.set([self.skill])  # m2m_changed fires here and already rebuilds it...
        Gig.objects.filter(pk=gig.pk).update(search_vector=None)  # ...so force it back to null.

        call_command('rebuild_search_vectors')

        self.assertTrue(_findable('Honey harvest').filter(pk=gig.pk).exists())
        self.assertTrue(_findable('Beekeeping').filter(pk=gig.pk).exists())
        self.assertTrue(_findable('smallholder apiary').filter(pk=gig.pk).exists())

    def test_gig_id_option_rebuilds_only_that_gig(self):
        gig = self._bulk_create_gig()
        other = self._bulk_create_gig(title='A second gig')

        call_command('rebuild_search_vectors', gig_id=str(gig.pk))

        gig.refresh_from_db()
        other.refresh_from_db()
        self.assertIsNotNone(gig.search_vector)
        self.assertIsNone(other.search_vector)

    def test_unknown_gig_id_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command('rebuild_search_vectors', gig_id='00000000-0000-0000-0000-000000000000')

    def test_skill_rename_is_reflected_after_rebuild(self):
        gig = self._bulk_create_gig()
        gig.skills.set([self.skill])

        self.skill.name = 'Apiculture'
        self.skill.save()  # renaming the Skill does not touch Gig, so its vector is now stale.

        self.assertFalse(_findable('Apiculture').filter(pk=gig.pk).exists())

        call_command('rebuild_search_vectors')

        self.assertTrue(_findable('Apiculture').filter(pk=gig.pk).exists())

    def test_rebuild_is_idempotent(self):
        self._bulk_create_gig()
        call_command('rebuild_search_vectors')
        call_command('rebuild_search_vectors')  # must not error or duplicate anything
        self.assertEqual(Gig.objects.count(), 1)


@override_settings(DEBUG=True)  # Django forces DEBUG=False during tests by default.
class PerfSeedCommandTests(TestCase):
    def run_command(self, **options):
        call_command('perf_seed', stdout=StringIO(), **options)

    @override_settings(DEBUG=False)
    def test_refuses_to_run_when_debug_is_false(self):
        with self.assertRaises(CommandError):
            self.run_command(size=5)
        self.assertEqual(Gig.objects.count(), 0)

    def test_creates_exactly_the_requested_number_of_gigs(self):
        self.run_command(size=30)
        self.assertEqual(Gig.objects.count(), 30)

    def test_running_again_replaces_rather_than_adds(self):
        self.run_command(size=30)
        self.run_command(size=12)
        self.assertEqual(Gig.objects.count(), 12)

    def test_every_gig_is_synthetic_has_skills_and_a_search_vector(self):
        self.run_command(size=30)
        self.assertFalse(Gig.objects.filter(is_synthetic=False).exists())
        self.assertFalse(Gig.objects.filter(search_vector__isnull=True).exists())
        for gig in Gig.objects.all():
            self.assertGreaterEqual(gig.skills.count(), 1)

    def test_same_seed_gives_the_same_gigs(self):
        self.run_command(size=25, seed=7)
        first = sorted(Gig.objects.values_list('title', 'description', 'budget_min'))
        self.run_command(size=25, seed=7)
        self.assertEqual(sorted(Gig.objects.values_list('title', 'description', 'budget_min')), first)

    def test_data_exercises_the_filters(self):
        self.run_command(size=200)
        self.assertTrue(Gig.objects.filter(is_remote=True).exists())
        self.assertTrue(Gig.objects.exclude(status=Gig.Status.OPEN).exists())
        self.assertTrue(Gig.objects.filter(application_deadline__lt=date.today()).exists())
        self.assertTrue(Gig.objects.filter(county='Nairobi').exists())

    def test_created_at_is_spread_out(self):
        self.run_command(size=50)
        newest = Gig.objects.order_by('-created_at').first().created_at
        oldest = Gig.objects.order_by('created_at').first().created_at
        self.assertGreater(newest - oldest, timedelta(days=5))

    def test_delete_removes_only_perf_gigs(self):
        owner = User.objects.create_user(
            email='real-owner@example.com', password='StrongPass123!',
            full_name='Owner', phone='254700000021', role='client',
        )
        real = Gig.objects.create(
            client=owner, category=Category.objects.first(), title='Real gig', description='Keep me.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30),
        )
        self.run_command(size=20)
        self.run_command(delete=True)
        self.assertEqual(list(Gig.objects.all()), [real])
        self.assertFalse(User.objects.filter(email__startswith='perf-client-').exists())
