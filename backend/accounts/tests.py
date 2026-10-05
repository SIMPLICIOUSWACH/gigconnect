from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from profiles.models import Skill

from .models import OTP, User
from .tokens import make_email_verification_token


class RegistrationTests(APITestCase):
    def setUp(self):
        self.skill = Skill.objects.create(name='Test Skill', category='Technology')
        self.url = '/api/auth/register/'

    def base_payload(self, **overrides):
        payload = {
            'full_name': 'Test User',
            'email': 'user@example.com',
            'password': 'StrongPass123!',
            'confirm_password': 'StrongPass123!',
            'phone': '254700000000',
            'role': 'freelancer',
        }
        payload.update(overrides)
        return payload

    def test_freelancer_registration_rejects_client_only_fields(self):
        payload = self.base_payload(role='freelancer', company_name='Acme', skills=[str(self.skill.id)])
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('company_name', response.data)

    def test_client_registration_rejects_freelancer_only_fields(self):
        payload = self.base_payload(role='client', skills=[str(self.skill.id)])
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('skills', response.data)

    def test_freelancer_registration_requires_at_least_one_skill(self):
        payload = self.base_payload(role='freelancer')
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('skills', response.data)

    def test_client_registration_succeeds_without_bio_or_portfolio(self):
        payload = self.base_payload(role='client')
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('bio', response.data['profile'])
        self.assertNotIn('portfolio_items', response.data['profile'])

    def test_registration_sends_verification_email(self):
        payload = self.base_payload(role='freelancer', skills=[str(self.skill.id)])
        self.client.post(self.url, payload)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('verify-email', mail.outbox[0].body)

    def test_registration_response_excludes_id_number(self):
        payload = self.base_payload(role='freelancer', skills=[str(self.skill.id)])
        response = self.client.post(self.url, payload)
        self.assertNotIn('id_number', response.data['profile'])
        self.assertNotIn('id_document', response.data['profile'])

    def test_new_user_is_not_email_or_phone_verified(self):
        payload = self.base_payload(role='freelancer', skills=[str(self.skill.id)])
        response = self.client.post(self.url, payload)
        self.assertFalse(response.data['is_email_verified'])
        self.assertFalse(response.data['is_phone_verified'])
        self.assertFalse(response.data['is_profile_complete'])


class EmailVerificationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='verify@example.com', password='StrongPass123!',
            full_name='Verify Me', phone='254700000000', role='client',
        )

    def test_verify_email_with_valid_token(self):
        token = make_email_verification_token(self.user)
        response = self.client.get(f'/api/auth/verify-email/{token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_verify_email_with_invalid_token(self):
        response = self.client.get('/api/auth/verify-email/not-a-real-token/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='login@example.com', password='StrongPass123!',
            full_name='Login User', phone='254700000000', role='client',
        )

    def test_login_returns_jwt(self):
        response = self.client.post('/api/auth/login/', {
            'email': 'login@example.com', 'password': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)


class MeViewTests(APITestCase):
    def test_me_returns_current_user(self):
        user = User.objects.create_user(
            email='me@example.com', password='StrongPass123!',
            full_name='Me User', phone='254700000000', role='client',
        )
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'me@example.com')

    def test_me_requires_authentication(self):
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class OTPTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='otp@example.com', password='StrongPass123!',
            full_name='OTP User', phone='254700000000', role='client',
        )
        self.client.force_authenticate(user=self.user)

    def _latest_otp(self):
        return OTP.objects.filter(user=self.user).order_by('-created_at').first()

    def test_send_otp_invalidates_prior_unused_otp(self):
        self.client.post('/api/auth/send-otp/')
        first_otp = self._latest_otp()
        self.client.post('/api/auth/send-otp/')
        first_otp.refresh_from_db()
        self.assertTrue(first_otp.is_used)

    def test_verify_otp_success(self):
        self.client.post('/api/auth/send-otp/')
        otp = self._latest_otp()
        response = self.client.post('/api/auth/verify-otp/', {'code': otp.code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_phone_verified)

    def test_verify_otp_rejects_expired_code(self):
        self.client.post('/api/auth/send-otp/')
        otp = self._latest_otp()
        otp.expires_at = timezone.now() - timedelta(seconds=1)
        otp.save(update_fields=['expires_at'])
        response = self.client.post('/api/auth/verify-otp/', {'code': otp.code})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_phone_verified)

    def test_verify_otp_rejects_already_used_code(self):
        self.client.post('/api/auth/send-otp/')
        otp = self._latest_otp()
        response = self.client.post('/api/auth/verify-otp/', {'code': otp.code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        second_response = self.client.post('/api/auth/verify-otp/', {'code': otp.code})
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_otp_rejects_wrong_code(self):
        self.client.post('/api/auth/send-otp/')
        response = self.client.post('/api/auth/verify-otp/', {'code': '000000'})
        self.assertIn(response.status_code, (status.HTTP_400_BAD_REQUEST,))


class SeedDataCommandTests(TestCase):
    def setUp(self):
        Skill.objects.create(name='Test Skill', category='Technology')

    def run_command(self, **options):
        call_command('seed_data', stdout=StringIO(), **options)

    def test_seed_creates_requested_count_of_each_role(self):
        self.run_command(count=3)
        self.assertEqual(User.objects.filter(email__startswith='seed-client-').count(), 3)
        self.assertEqual(User.objects.filter(email__startswith='seed-freelancer-').count(), 3)

    def test_seeded_accounts_are_flagged_synthetic_and_real_ones_are_not(self):
        real = User.objects.create_user(
            email='real@example.com', password='StrongPass123!',
            full_name='Real', phone='254700000088', role='client',
        )
        self.run_command(count=2)
        seeded = User.objects.filter(email__startswith='seed-')
        self.assertEqual(seeded.count(), 4)
        self.assertFalse(seeded.filter(is_synthetic=False).exists())
        self.assertFalse(real.is_synthetic)

    def test_seed_is_idempotent(self):
        self.run_command(count=3)
        self.run_command(count=3)
        self.assertEqual(User.objects.filter(email__startswith='seed-client-').count(), 3)
        self.assertEqual(User.objects.filter(email__startswith='seed-freelancer-').count(), 3)

    def test_seeded_freelancers_have_at_least_one_skill(self):
        self.run_command(count=2)
        freelancer = User.objects.filter(email__startswith='seed-freelancer-').first()
        self.assertGreaterEqual(freelancer.freelancer_profile.skills.count(), 1)

    def test_seeded_clients_have_company_info(self):
        self.run_command(count=2)
        client_user = User.objects.filter(email__startswith='seed-client-').first()
        self.assertTrue(client_user.client_profile.company_name)
        self.assertTrue(client_user.client_profile.industry)

    def test_seed_does_nothing_without_skills(self):
        Skill.objects.all().delete()
        self.run_command(count=3)
        self.assertEqual(User.objects.filter(email__startswith='seed-freelancer-').count(), 0)
