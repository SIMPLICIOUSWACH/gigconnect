from datetime import date, timedelta
from io import StringIO

from django.contrib.postgres.search import SearchQuery
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
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
