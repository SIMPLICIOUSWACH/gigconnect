import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import User
from applications.models import Application
from gigs.models import Category, Gig

from .models import FreelancerProfile, Skill

URL = '/api/freelancers/'


class SearchTestCase(APITestCase):
    def setUp(self):
        cache.clear()  # the search throttle counts live in the cache
        self.count = 0
        self.client_user = self.user('client@example.com', 'client', 'Wanjiru Bakers')
        self.client.force_authenticate(self.client_user)

    def user(self, email, role, name, **extra):
        self.count += 1
        defaults = {'is_email_verified': True, **extra}
        return User.objects.create_user(
            email=email, password='x-Search-test-1', full_name=name, phone=f'2547120{self.count:05d}', role=role,
            **defaults,
        )

    def freelancer(self, name, skills=(), rating=None, user=None, **profile):
        """A findable freelancer. rating is (average, count); user holds changes to the account itself."""
        person = self.user(f'{name.lower().replace(" ", ".")}@example.com', 'freelancer', name, **(user or {}))
        row = person.freelancer_profile
        for field, value in profile.items():
            setattr(row, field, value)
        if rating:
            row.rating_avg, row.rating_count = Decimal(str(rating[0])), rating[1]
        row.save()
        if skills:
            row.skills.set([Skill.objects.get_or_create(name=skill)[0] for skill in skills])
        return person

    def names(self, **params):
        response = self.client.get(URL, params)
        self.assertEqual(response.status_code, 200, response.data)
        return [row['full_name'] for row in response.data['results']]


class AccessTests(SearchTestCase):
    def test_clients_and_admins_only(self):
        self.freelancer('Otieno Designs')
        self.assertEqual(self.names(), ['Otieno Designs'])
        admin = self.user('admin@example.com', 'admin', 'Asha Admin', is_staff=True)
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get(URL).status_code, 200)
        self.client.force_authenticate(User.objects.get(full_name='Otieno Designs'))
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_who_is_left_out(self):
        self.freelancer('Shown Person')
        self.freelancer('Hidden Person', search_visible=False)
        self.freelancer('Suspended Person', user={'account_status': 'suspended'})
        self.freelancer('Deleted Person', user={'deleted_at': timezone.now()})
        self.freelancer('Inactive Person', user={'is_active': False})
        self.freelancer('Unverified Email', user={'is_email_verified': False})
        self.freelancer('Seed Person', user={'is_synthetic': True})
        with override_settings(SHOW_SYNTHETIC=False):
            self.assertEqual(self.names(), ['Shown Person'])
        with override_settings(SHOW_SYNTHETIC=True):
            self.assertEqual(set(self.names()), {'Shown Person', 'Seed Person'})

    def test_a_freelancer_can_hide_themselves_and_only_they_see_the_setting(self):
        person = self.freelancer('Otieno Designs')
        self.client.force_authenticate(person)
        self.assertTrue(self.client.get('/api/auth/me/').data['profile']['search_visible'])
        response = self.client.patch('/api/profile/complete/', {'search_visible': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(self.client_user)
        self.assertEqual(self.names(), [])
        public = self.client.get(f'/api/profiles/{person.pk}/')  # still opens from a link
        self.assertEqual(public.status_code, 200)
        self.assertNotIn('search_visible', public.data['profile'])


class PrivacyTests(SearchTestCase):
    def test_a_card_has_public_fields_only(self):
        person = self.freelancer(
            'Otieno Designs', skills=['Logo Design'], headline='Brand designer', county='Nairobi',
            id_number='29876543', id_number_last3='543', id_number_hash='a' * 64, rating=(4.5, 2),
        )
        response = self.client.get(URL)
        row = response.data['results'][0]
        self.assertEqual(set(row), {
            'id', 'full_name', 'profile_photo', 'profile_colour', 'verified', 'headline', 'county', 'skills',
            'skills_total', 'rating_avg', 'rating_count', 'gigs_completed', 'starting_price', 'is_available',
            'open_to_remote',
        })
        body = json.dumps(response.json())
        for private in (person.email, person.phone, '29876543', 'a' * 64, 'id_number', 'id_document', 'selfie'):
            self.assertNotIn(private, body)


class KeywordTests(SearchTestCase):
    def setUp(self):
        super().setUp()
        self.freelancer('Otieno Designs', skills=['Logo Design'], headline='Brand designer', bio='Logos for shops.')
        self.freelancer('Achieng Studio', skills=['Photography'], headline='Wedding photographer',
                        bio='Weddings and events around Kisumu.')
        self.freelancer('Brian Mutua', skills=['Plumbing'], headline='Plumber', bio='Leaks fixed fast.')

    def test_by_name_headline_skill_and_bio(self):
        self.assertEqual(self.names(q='Achieng'), ['Achieng Studio'])
        self.assertEqual(self.names(q='plumber'), ['Brian Mutua'])
        self.assertEqual(self.names(q='logo design'), ['Otieno Designs'])
        self.assertEqual(self.names(q='weddings'), ['Achieng Studio'])

    def test_a_typo_still_finds_someone(self):
        self.assertEqual(self.names(q='photograper'), ['Achieng Studio'])

    def test_the_index_follows_new_skills_and_a_new_name(self):
        self.assertEqual(self.names(q='carpentry'), [])
        brian = User.objects.get(full_name='Brian Mutua')
        brian.freelancer_profile.skills.add(Skill.objects.get_or_create(name='Carpentry')[0])
        self.assertEqual(self.names(q='carpentry'), ['Brian Mutua'])
        brian.full_name = 'Baraka Mutua'
        brian.save()
        self.assertEqual(self.names(q='Baraka'), ['Baraka Mutua'])


class FilterTests(SearchTestCase):
    def setUp(self):
        super().setUp()
        self.freelancer('Amina', skills=['Logo Design', 'Illustration'], county='Nairobi', rating=(4.8, 10),
                        verification_status='verified', is_available=True, open_to_remote=True)
        self.freelancer('Brian', skills=['Plumbing'], county='Kisumu', rating=(3.5, 4),
                        is_available=False, open_to_remote=False)
        self.freelancer('Cynthia', skills=['Logo Design'], county='Kisumu', is_available=True, open_to_remote=True)

    def test_each_filter(self):
        self.assertEqual(set(self.names(skills='Logo Design')), {'Amina', 'Cynthia'})
        self.assertEqual(set(self.names(county='Kisumu')), {'Brian', 'Cynthia'})
        self.assertEqual(set(self.names(remote='true')), {'Amina', 'Cynthia'})
        self.assertEqual(self.names(verified='true'), ['Amina'])
        self.assertEqual(set(self.names(available='true')), {'Amina', 'Cynthia'})

    def test_a_minimum_rating_leaves_out_the_unrated(self):
        self.assertEqual(self.names(min_rating='4'), ['Amina'])
        self.assertEqual(set(self.names(min_rating='3')), {'Amina', 'Brian'})

    def test_filters_combine(self):
        self.assertEqual(self.names(skills='Logo Design', county='Kisumu'), ['Cynthia'])
        self.assertEqual(self.names(skills='Logo Design', county='Kisumu', verified='true'), [])

    def test_more_matching_skills_first(self):
        self.assertEqual(self.names(skills='Logo Design,Illustration')[0], 'Amina')

    def test_bad_values_are_refused(self):
        self.assertEqual(self.client.get(URL, {'county': 'Atlantis'}).status_code, 400)
        self.assertEqual(self.client.get(URL, {'min_rating': '9'}).status_code, 400)
        self.assertEqual(self.client.get(URL, {'sort': 'cheapest'}).status_code, 400)


class SortTests(SearchTestCase):
    def test_one_five_star_review_does_not_outrank_many_high_ratings(self):
        self.freelancer('One Review', rating=(5.0, 1))
        self.freelancer('Twenty Reviews', rating=(4.8, 20))
        self.freelancer('Poorly Rated', rating=(2.0, 8))
        self.freelancer('Brand New')
        # (5*4.0 + 4.8*20)/25 = 4.64; (5*4.0 + 5)/6 = 4.17; new = 4.0; (5*4.0 + 16)/13 = 2.77
        self.assertEqual(self.names(sort='rating'), ['Twenty Reviews', 'One Review', 'Brand New', 'Poorly Rated'])

    def test_someone_new_has_no_rating_rather_than_zero(self):
        self.freelancer('Brand New')
        row = self.client.get(URL).data['results'][0]
        self.assertEqual((row['rating_avg'], row['rating_count']), (None, 0))

    def test_with_nothing_to_match_verified_come_first_then_rating_then_recently_active(self):
        now = timezone.now()
        self.freelancer('Unverified Star', rating=(5.0, 30))
        self.freelancer('Verified Good', rating=(4.5, 10), verification_status='verified')
        self.freelancer('Verified New Recent', verification_status='verified', user={'last_login': now})
        self.freelancer('Verified New Old', verification_status='verified',
                        user={'last_login': now - timedelta(days=30)})
        self.assertEqual(self.names(), ['Verified Good', 'Verified New Recent', 'Verified New Old', 'Unverified Star'])

    def test_most_gigs_completed(self):
        category = Category.objects.create(name='Search Test Category')
        busy = self.freelancer('Busy')
        self.freelancer('Idle')
        for index in range(2):
            gig = Gig.objects.create(
                client=self.client_user, category=category, title=f'Done {index}', description='x' * 30,
                budget_min=1000, budget_max=2000, deadline=timezone.now().date() + timedelta(days=30),
                status='completed',
            )
            Application.objects.create(gig=gig, freelancer=busy, cover_letter='x' * 60, status='hired')
        self.assertEqual(self.names(sort='completed'), ['Busy', 'Idle'])
        self.assertEqual(self.client.get(URL, {'sort': 'completed'}).data['results'][0]['gigs_completed'], 2)

    def test_newest(self):
        self.freelancer('First')
        self.freelancer('Second')
        self.assertEqual(self.names(sort='newest'), ['Second', 'First'])


class LimitsTests(SearchTestCase):
    def test_twelve_per_page(self):
        for index in range(13):
            self.freelancer(f'Person {index:02d}')
        data = self.client.get(URL).data
        self.assertEqual((len(data['results']), data['count'], data['total_pages']), (12, 13, 2))
        self.assertEqual(len(self.client.get(URL, {'page': 2, 'page_size': 50}).data['results']), 1)

    def test_no_paging_past_50_pages_without_a_search_or_filter(self):
        response = self.client.get(URL, {'page': 51})
        self.assertEqual((response.status_code, response.data['code']), (400, 'narrow_your_search'))
        self.assertEqual(self.client.get(URL, {'page': 51, 'sort': 'newest'}).status_code, 400)  # a sort is no filter
        filtered = self.client.get(URL, {'page': 51, 'county': 'Nairobi'})
        self.assertNotEqual(filtered.data.get('code'), 'narrow_your_search')

    def test_the_search_is_throttled(self):
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'freelancer_search': '2/min'}):
            self.assertEqual(self.client.get(URL).status_code, 200)
            self.assertEqual(self.client.get(URL).status_code, 200)
            self.assertEqual(self.client.get(URL).status_code, 429)


class BackfillTests(SearchTestCase):
    def test_the_migration_fills_in_missing_vectors(self):
        import importlib

        from django.apps import apps

        self.freelancer('Otieno Designs', headline='Brand designer')
        FreelancerProfile.objects.update(search_vector=None)
        importlib.import_module('profiles.migrations.0017_backfill_profile_search_vector').backfill(apps, None)
        self.assertIn('design', FreelancerProfile.objects.get().search_vector)
        self.assertEqual(self.names(q='designer'), ['Otieno Designs'])
