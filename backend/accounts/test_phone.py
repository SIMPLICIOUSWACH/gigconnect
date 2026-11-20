import importlib
import os
from io import StringIO
from unittest import mock

from django.apps import apps
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APITestCase

from adminpanel.management.commands.create_admin import PASSWORD_ENV
from adminpanel.testing import LETTER, AdminTestMixin
from gigs.models import Category
from profiles.models import Skill

from .models import User
from .phones import normalise_phone

REGISTER_URL = '/api/auth/register/'


class NormalisePhoneTests(SimpleTestCase):
    def test_every_accepted_form_becomes_plus_254(self):
        for value, expected in (
            ('0712345678', '+254712345678'),
            ('0112345678', '+254112345678'),
            ('712345678', '+254712345678'),
            ('112345678', '+254112345678'),
            ('254712345678', '+254712345678'),
            ('+254712345678', '+254712345678'),
            ('+254112345678', '+254112345678'),
            ('0712 345 678', '+254712345678'),
            ('+254-712-345-678', '+254712345678'),
        ):
            with self.subTest(value=value):
                self.assertEqual(normalise_phone(value), expected)

    def test_no_number_is_allowed(self):
        self.assertEqual(normalise_phone(''), '')
        self.assertEqual(normalise_phone('   '), '')
        self.assertEqual(normalise_phone(None), '')

    def test_landlines_and_anything_else_are_refused(self):
        for value in (
            '0202345678', '+254202345678', '0412345678', '0000000000', '07182782342', '76138949', '567568799',
            '+255712345678', '+14155552671', '07123456789', 'phone', '+254', '071234567a',
        ):
            with self.subTest(value=value):
                self.assertIsNone(normalise_phone(value))


class OtpIsGoneTests(APITestCase):
    def test_the_otp_urls_return_404(self):
        user = User.objects.create_user(email='a@example.com', password='x-Test-pass-1', full_name='A', role='client')
        self.client.force_authenticate(user)
        for url in ('/api/auth/send-otp/', '/api/auth/verify-otp/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {'code': '123456'}).status_code, 404)

    def test_the_model_field_and_response_field_are_gone(self):
        self.assertFalse(any(model.__name__ == 'OTP' for model in apps.get_app_config('accounts').get_models()))
        self.assertNotIn('is_phone_verified', {field.name for field in User._meta.get_fields()})
        user = User.objects.create_user(email='a@example.com', password='x-Test-pass-1', full_name='A', role='client')
        self.client.force_authenticate(user)
        self.assertNotIn('is_phone_verified', self.client.get('/api/auth/me/').data)


class RegistrationPhoneTests(APITestCase):
    def payload(self, **extra):
        return {
            'full_name': 'New Client', 'email': 'new@example.com', 'password': 'StrongPass123!',
            'confirm_password': 'StrongPass123!', 'role': 'client', **extra,
        }

    def test_registration_works_without_a_phone(self):
        response = self.client.post(REGISTER_URL, self.payload())
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(User.objects.get(email='new@example.com').phone, '')

    def test_registration_works_with_a_blank_phone(self):
        self.assertEqual(self.client.post(REGISTER_URL, self.payload(phone='')).status_code, 201)

    def test_a_phone_is_stored_normalised(self):
        response = self.client.post(REGISTER_URL, self.payload(phone='0712345678'))
        self.assertEqual(response.data['phone'], '+254712345678')

    def test_a_landline_gets_a_clear_message(self):
        response = self.client.post(REGISTER_URL, self.payload(phone='0202345678'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('Landlines are not accepted', str(response.data['phone']))
        self.assertFalse(User.objects.filter(email='new@example.com').exists())


class EmailVerificationIsEnoughTests(AdminTestMixin, APITestCase):
    """Nobody needs a phone to act on the platform: a verified email is what posting and applying ask for."""

    def setUp(self):
        self.poster = self.make_user('client@example.com', User.Role.CLIENT)
        self.applicant = self.make_user('freelancer@example.com', User.Role.FREELANCER)
        self.gig = self.make_gig(self.poster)

    def post_gig(self):
        self.client.force_authenticate(self.poster)
        return self.client.post('/api/gigs/', {
            'title': 'Build a shop', 'description': 'A small online shop for a bakery in Nakuru.',
            'category': str(Category.objects.first().pk), 'budget_min': '1000', 'budget_max': '2000',
            'deadline': self.gig.deadline.isoformat(),
            'skills': [str(Skill.objects.create(name='Phone Test Skill', category='Technology').pk)],
        }, format='json')

    def apply_to_gig(self):
        self.client.force_authenticate(self.applicant)
        return self.client.post(f'/api/gigs/{self.gig.pk}/applications/', {'cover_letter': LETTER})

    def test_a_client_with_no_phone_can_post_a_gig(self):
        User.objects.filter(pk=self.poster.pk).update(phone='')
        self.assertEqual(self.post_gig().status_code, 201)

    def test_a_freelancer_with_no_phone_can_apply(self):
        User.objects.filter(pk=self.applicant.pk).update(phone='')
        self.assertEqual(self.apply_to_gig().status_code, 201)

    def test_an_unverified_email_is_still_refused(self):
        User.objects.filter(pk__in=[self.poster.pk, self.applicant.pk]).update(is_email_verified=False)
        self.poster.refresh_from_db()
        self.applicant.refresh_from_db()
        self.assertEqual(self.post_gig().status_code, 403)
        self.assertEqual(self.apply_to_gig().status_code, 403)


class CreateAdminPhoneTests(TestCase):
    def create(self, *args):
        with mock.patch.dict(os.environ, {PASSWORD_ENV: 'AdminPass123!'}):
            call_command('create_admin', '--email', 'boss@example.com', '--noinput', *args, stdout=StringIO())

    def test_phone_is_optional_and_normalised(self):
        self.create('--phone', '0712345678')
        self.assertEqual(User.objects.get(email='boss@example.com').phone, '+254712345678')

    def test_a_bad_phone_is_refused(self):
        with self.assertRaisesMessage(CommandError, 'Landlines'):
            self.create('--phone', '0202345678')
        self.assertFalse(User.objects.exists())


class PhoneMigrationTests(TestCase):
    def test_numbers_are_normalised_and_unreadable_ones_blanked(self):
        rows = {
            'a@example.com': ('254712345678', '+254712345678'),
            'b@example.com': ('0712345678', '+254712345678'),
            'c@example.com': ('+254112345678', '+254112345678'),
            'd@example.com': ('07182782342', ''),
            'e@example.com': ('76138949', ''),
            'f@example.com': ('0000000000', ''),
            'g@example.com': ('', ''),
        }
        for email, (old, _) in rows.items():
            User.objects.create_user(email=email, password='x', full_name='X', role='client', phone=old)

        module = importlib.import_module('accounts.migrations.0006_remove_otp_and_phone_verification')
        module.normalise_phones(apps, None)

        for email, (_, expected) in rows.items():
            self.assertEqual(User.objects.get(email=email).phone, expected, email)
