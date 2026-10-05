from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import User
from gigs.models import Category, Gig

from .models import FreelancerProfile, PortfolioItem, Skill, SkillAlias


class ProfileCompleteTests(APITestCase):
    def setUp(self):
        self.skill = Skill.objects.create(name='Test Skill', category='Technology')

    def make_freelancer(self):
        user = User.objects.create_user(
            email='freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000001', role='freelancer',
        )
        user.freelancer_profile.skills.set([self.skill])
        return user

    def make_client(self):
        return User.objects.create_user(
            email='client@example.com', password='StrongPass123!',
            full_name='Client', phone='254700000002', role='client',
        )

    def test_freelancer_profile_complete_requires_bio(self):
        user = self.make_freelancer()
        self.client.force_authenticate(user=user)
        response = self.client.patch('/api/profile/complete/', {'profile_photo': ''}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertFalse(user.is_profile_complete)

    def test_freelancer_profile_complete_with_bio(self):
        user = self.make_freelancer()
        self.client.force_authenticate(user=user)
        response = self.client.patch('/api/profile/complete/', {'bio': 'Experienced developer.'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_profile_complete)

    def test_client_profile_complete_without_required_fields(self):
        user = self.make_client()
        self.client.force_authenticate(user=user)
        response = self.client.patch('/api/profile/complete/', {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_profile_complete)


class PortfolioItemTests(APITestCase):
    def setUp(self):
        self.skill = Skill.objects.create(name='Test Skill', category='Technology')
        self.freelancer = User.objects.create_user(
            email='freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000001', role='freelancer',
        )
        self.freelancer.freelancer_profile.skills.set([self.skill])
        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!',
            full_name='Client', phone='254700000002', role='client',
        )

    def test_freelancer_can_create_portfolio_item(self):
        self.client.force_authenticate(user=self.freelancer)
        response = self.client.post('/api/profile/portfolio-items/', {'title': 'My Project'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PortfolioItem.objects.count(), 1)

    def test_freelancer_can_delete_own_portfolio_item(self):
        self.client.force_authenticate(user=self.freelancer)
        item = PortfolioItem.objects.create(freelancer=self.freelancer.freelancer_profile, title='My Project')
        response = self.client.delete(f'/api/profile/portfolio-items/{item.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(PortfolioItem.objects.count(), 0)

    def test_client_cannot_access_portfolio_endpoints(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post('/api/profile/portfolio-items/', {'title': 'Not allowed'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class IdentityVerificationTests(APITestCase):
    def setUp(self):
        self.skill = Skill.objects.create(name='Test Skill', category='Technology')
        self.freelancer = User.objects.create_user(
            email='freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000001', role='freelancer',
        )
        self.freelancer.freelancer_profile.skills.set([self.skill])
        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!',
            full_name='Client', phone='254700000002', role='client',
        )
        self.admin = User.objects.create_user(
            email='admin@example.com', password='StrongPass123!',
            full_name='Admin', phone='254700000003', role='admin',
        )

    def _submit_verification(self):
        self.client.force_authenticate(user=self.freelancer)
        id_document = SimpleUploadedFile('id.pdf', b'fake-pdf-bytes', content_type='application/pdf')
        return self.client.post('/api/profile/submit-verification/', {
            'id_number': '12345678', 'id_document': id_document,
        }, format='multipart')

    def test_submit_verification_sets_pending_status(self):
        response = self._submit_verification()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.freelancer.freelancer_profile.refresh_from_db()
        self.assertEqual(
            self.freelancer.freelancer_profile.verification_status,
            FreelancerProfile.VerificationStatus.PENDING,
        )

    def test_submit_verification_response_never_includes_id_number(self):
        response = self._submit_verification()
        self.assertNotIn('id_number', response.data)
        self.assertNotIn('id_document', response.data)

    def test_own_profile_view_never_includes_id_number(self):
        self._submit_verification()
        self.client.force_authenticate(user=self.freelancer)
        response = self.client.get('/api/skills/')  # sanity: auth works
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        from accounts.serializers import UserSerializer
        data = UserSerializer(self.freelancer).data
        self.assertNotIn('id_number', data['profile'])
        self.assertNotIn('id_document', data['profile'])

    def test_only_admin_can_approve_verification(self):
        self._submit_verification()
        profile = self.freelancer.freelancer_profile
        self.client.force_authenticate(user=self.client_user)
        response = self.client.patch(f'/api/admin/verifications/{profile.id}/', {'verification_status': 'verified'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.freelancer)
        response = self.client.patch(f'/api/admin/verifications/{profile.id}/', {'verification_status': 'verified'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_approve_verification(self):
        self._submit_verification()
        profile = self.freelancer.freelancer_profile
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(f'/api/admin/verifications/{profile.id}/', {'verification_status': 'verified'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile.refresh_from_db()
        self.assertTrue(profile.verified)

    def test_admin_can_reject_verification(self):
        self._submit_verification()
        profile = self.freelancer.freelancer_profile
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(f'/api/admin/verifications/{profile.id}/', {'verification_status': 'rejected'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile.refresh_from_db()
        self.assertEqual(profile.verification_status, FreelancerProfile.VerificationStatus.REJECTED)
        self.assertFalse(profile.verified)


class PublicProfileViewTests(APITestCase):
    def setUp(self):
        self.skill = Skill.objects.create(name='Test Skill', category='Technology')
        self.freelancer = User.objects.create_user(
            email='freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000001', role='freelancer',
        )
        self.freelancer.freelancer_profile.skills.set([self.skill])
        self.freelancer.freelancer_profile.bio = 'A bio.'
        self.freelancer.freelancer_profile.id_number = '12345678'
        self.freelancer.freelancer_profile.save()
        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!',
            full_name='Client', phone='254700000002', role='client',
        )

    def test_requires_authentication(self):
        response = self.client.get(f'/api/profiles/{self.freelancer.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_any_authenticated_user_can_view_another_users_public_profile(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(f'/api/profiles/{self.freelancer.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['full_name'], 'Freelancer')
        self.assertEqual(response.data['profile']['bio'], 'A bio.')

    def test_public_profile_never_includes_id_number_email_or_phone(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(f'/api/profiles/{self.freelancer.id}/')
        self.assertNotIn('id_number', response.data['profile'])
        self.assertNotIn('id_document', response.data['profile'])
        self.assertNotIn('email', response.data)
        self.assertNotIn('phone', response.data)

    def test_public_profile_for_client_role(self):
        self.client.force_authenticate(user=self.freelancer)
        response = self.client.get(f'/api/profiles/{self.client_user.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('company_name', response.data['profile'])


class SkillCreateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000001', role='freelancer',
        )

    def test_requires_authentication(self):
        response = self.client.post('/api/skills/', {'name': 'Drone Photography'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creates_a_new_skill(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/skills/', {'name': 'Drone Photography', 'category': 'Media'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Skill.objects.filter(name='Drone Photography').count(), 1)

    def test_defaults_category_when_not_given(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/skills/', {'name': 'Drone Photography'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['category'], 'Other')

    def test_duplicate_name_case_insensitive_returns_existing_skill(self):
        existing = Skill.objects.create(name='Drone Photography', category='Media')
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/skills/', {'name': 'drone photography'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['id'], str(existing.id))
        self.assertEqual(Skill.objects.filter(name__iexact='drone photography').count(), 1)

    def test_blank_name_is_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/skills/', {'name': '   '})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CountyTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='county-freelancer@example.com', password='StrongPass123!',
            full_name='County Freelancer', phone='254700000077', role='freelancer',
        )

    def test_counties_endpoint_lists_all_47_without_auth(self):
        response = self.client.get('/api/meta/counties/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        values = [c['value'] for c in response.data]
        self.assertEqual(len(values), 47)
        self.assertEqual(len(set(values)), 47)
        self.assertIn('Nairobi', values)
        self.assertIn("Murang'a", values)

    def test_freelancer_can_set_county(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch('/api/profile/complete/', {'county': 'Kisumu'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.freelancer_profile.refresh_from_db()
        self.assertEqual(self.user.freelancer_profile.county, 'Kisumu')

    def test_unknown_county_is_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch('/api/profile/complete/', {'county': 'Atlantis'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('county', response.data)

    def test_blank_county_clears_it(self):
        self.user.freelancer_profile.county = 'Nairobi'
        self.user.freelancer_profile.save()
        self.client.force_authenticate(user=self.user)
        response = self.client.patch('/api/profile/complete/', {'county': ''}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.freelancer_profile.refresh_from_db()
        self.assertIsNone(self.user.freelancer_profile.county)


class SkillNormalizationTests(APITestCase):
    def setUp(self):
        cache.clear()  # throttle counters live in the cache
        self.user = User.objects.create_user(
            email='skill-user@example.com', password='StrongPass123!',
            full_name='Skill User', phone='254700000066', role='freelancer',
        )
        self.client.force_authenticate(user=self.user)

    def post(self, name):
        return self.client.post('/api/skills/', {'name': name})

    def test_whitespace_is_trimmed_and_collapsed_but_display_casing_is_kept(self):
        response = self.post('  Drone    Photography ')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        skill = Skill.objects.get(id=response.data['id'])
        self.assertEqual(skill.name, 'Drone Photography')
        self.assertEqual(skill.normalized_name, 'drone photography')

    def test_spacing_and_case_variants_return_the_existing_skill(self):
        existing = self.post('Drone Photography').data['id']
        for variant in ['drone photography', 'DRONE   PHOTOGRAPHY', ' Drone Photography ']:
            self.assertEqual(self.post(variant).data['id'], existing)
        self.assertEqual(Skill.objects.filter(normalized_name='drone photography').count(), 1)

    def test_seeded_alias_resolves_to_the_canonical_skill(self):
        react = Skill.objects.get(name='React')
        for alias in ['ReactJS', 'react.js', 'REACT JS']:
            response = self.post(alias)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data['id'], str(react.id))
        self.assertFalse(Skill.objects.filter(name__iexact='reactjs').exists())

    def test_common_aliases_are_seeded(self):
        expected = {'JS': 'JavaScript', 'Py': 'Python', 'MS Excel': 'Excel', 'ReactJS': 'React', 'React.js': 'React'}
        for alias, canonical in expected.items():
            self.assertEqual(SkillAlias.objects.get(alias=alias).skill.name, canonical)

    def test_name_that_is_too_long_is_rejected(self):
        self.assertEqual(self.post('x' * 51).status_code, status.HTTP_400_BAD_REQUEST)

    def test_name_that_is_too_short_is_rejected(self):
        self.assertEqual(self.post('a').status_code, status.HTTP_400_BAD_REQUEST)

    def test_name_made_only_of_symbols_is_rejected(self):
        for name in ['!!!', '---', '+++ ###']:
            self.assertEqual(self.post(name).status_code, status.HTTP_400_BAD_REQUEST, name)

    def test_names_containing_urls_are_rejected(self):
        for name in ['https://spam.example', 'www.spam-site', 'buy followers at spam.com']:
            response = self.post(name)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, name)
            self.assertIn('name', response.data)

    def test_legitimate_names_with_punctuation_are_accepted(self):
        for name in ['Node.js', 'C++', 'UI/UX Design', 'Next.js']:
            self.assertEqual(self.post(name).status_code, status.HTTP_201_CREATED, name)

    def test_creating_skills_is_rate_limited(self):
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', {'skill_create': '3/hour'}):
            codes = [self.post(f'Skill number {n}').status_code for n in range(5)]
        self.assertEqual(codes[:3], [status.HTTP_201_CREATED] * 3)
        self.assertEqual(codes[3:], [status.HTTP_429_TOO_MANY_REQUESTS] * 2)

    def test_listing_skills_is_not_rate_limited(self):
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', {'skill_create': '1/hour'}):
            codes = [self.client.get('/api/skills/').status_code for _ in range(4)]
        self.assertEqual(codes, [status.HTTP_200_OK] * 4)

    def test_still_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.post('Drone Photography').status_code, status.HTTP_401_UNAUTHORIZED)


class MergeSkillsCommandTests(TestCase):
    def setUp(self):
        self.keep = Skill.objects.create(name='Photography Pro', category='Media')
        self.dupe = Skill.objects.create(name='Photo graphy Pro', category='Media')
        category = Category.objects.create(name='Merge Test Category')
        owner = User.objects.create_user(
            email='merge-owner@example.com', password='StrongPass123!',
            full_name='Owner', phone='254700000044', role='client',
        )
        self.freelancer = User.objects.create_user(
            email='merge-freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000045', role='freelancer',
        )

        def make_gig(title):
            return Gig.objects.create(
                client=owner, category=category, title=title, description='Merge test gig.',
                budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30),
            )

        self.gig_dupe_only = make_gig('Uses the duplicate')
        self.gig_dupe_only.skills.set([self.dupe])
        self.gig_both = make_gig('Uses both')
        self.gig_both.skills.set([self.keep, self.dupe])
        self.freelancer.freelancer_profile.skills.set([self.dupe])

    def run_command(self, *args, **options):
        out = StringIO()
        call_command('merge_skills', *args, stdout=out, **options)
        return out.getvalue()

    def test_repoints_gigs_profiles_and_deletes_the_duplicate(self):
        self.run_command('Photo graphy Pro', 'Photography Pro')

        self.assertFalse(Skill.objects.filter(pk=self.dupe.pk).exists())
        self.assertEqual(list(self.gig_dupe_only.skills.all()), [self.keep])
        self.assertEqual(list(self.gig_both.skills.all()), [self.keep])  # no duplicate row
        self.assertEqual(list(self.freelancer.freelancer_profile.skills.all()), [self.keep])

    def test_old_name_becomes_an_alias_of_the_kept_skill(self):
        self.run_command('Photo graphy Pro', 'Photography Pro')
        self.assertEqual(SkillAlias.objects.get(alias='Photo graphy Pro').skill, self.keep)

    def test_search_reflects_the_merge(self):
        from django.contrib.postgres.search import SearchQuery

        self.run_command('Photo graphy Pro', 'Photography Pro')
        found = Gig.objects.filter(search_vector=SearchQuery('photography', search_type='websearch'))
        self.assertIn(self.gig_dupe_only, found)

    def test_accepts_ids(self):
        self.run_command(str(self.dupe.id), str(self.keep.id))
        self.assertFalse(Skill.objects.filter(pk=self.dupe.pk).exists())

    def test_dry_run_changes_nothing(self):
        output = self.run_command('Photo graphy Pro', 'Photography Pro', dry_run=True)
        self.assertIn('Would merge', output)
        self.assertTrue(Skill.objects.filter(pk=self.dupe.pk).exists())
        self.assertEqual(list(self.gig_dupe_only.skills.all()), [self.dupe])

    def test_merging_a_skill_into_itself_is_an_error(self):
        with self.assertRaises(CommandError):
            self.run_command('Photography Pro', 'photography pro')

    def test_unknown_skill_is_an_error(self):
        with self.assertRaises(CommandError):
            self.run_command('Nonexistent Skill', 'Photography Pro')


class ReportDuplicateSkillsTests(TestCase):
    def run_report(self):
        out = StringIO()
        call_command('report_duplicate_skills', stdout=out)
        return out.getvalue()

    def test_reports_spelling_variants_without_changing_anything(self):
        Skill.objects.create(name='Photo graphy Pro', category='Media')
        Skill.objects.create(name='Photography Pro', category='Media')
        before = Skill.objects.count()

        output = self.run_report()

        self.assertIn('Photo graphy Pro', output)
        self.assertIn('Photography Pro', output)
        self.assertEqual(Skill.objects.count(), before)

    def test_says_so_when_there_is_nothing_to_report(self):
        # The seeded skills are all distinct enough that none should be flagged.
        self.assertIn('No likely duplicate skills found', self.run_report())
