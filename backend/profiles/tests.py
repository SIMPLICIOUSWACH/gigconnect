from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import FreelancerProfile, PortfolioItem, Skill


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
