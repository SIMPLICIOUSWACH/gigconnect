from django.core import mail
from rest_framework import status
from rest_framework.test import APITestCase

from profiles.models import Skill

from .models import User
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
