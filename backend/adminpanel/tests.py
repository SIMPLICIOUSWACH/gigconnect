import os
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase

from accounts.models import User

from .management.commands.create_admin import PASSWORD_ENV


class CreateAdminCommandTests(TestCase):
    def run_command(self, *args, password='AdminPass123!'):
        with mock.patch.dict(os.environ, {PASSWORD_ENV: password}):
            call_command('create_admin', *args, '--noinput', stdout=StringIO())

    def test_creates_a_verified_staff_admin(self):
        self.run_command('--email', 'Boss@Example.com', '--full-name', 'Platform Admin')
        admin = User.objects.get(email='Boss@example.com')
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.is_staff)
        self.assertFalse(admin.is_superuser)
        self.assertTrue(admin.is_email_verified)
        self.assertTrue(admin.is_phone_verified)
        self.assertTrue(admin.is_profile_complete)
        self.assertTrue(admin.check_password('AdminPass123!'))
        self.assertEqual(admin.full_name, 'Platform Admin')

    def test_prompts_for_the_password_twice(self):
        with mock.patch('getpass.getpass', side_effect=['AdminPass123!', 'AdminPass123!']):
            call_command('create_admin', '--email', 'admin@example.com', stdout=StringIO())
        self.assertTrue(User.objects.get(email='admin@example.com').check_password('AdminPass123!'))

    def test_refuses_mismatched_passwords(self):
        with mock.patch('getpass.getpass', side_effect=['AdminPass123!', 'Different123!']):
            with self.assertRaisesMessage(CommandError, 'did not match'):
                call_command('create_admin', '--email', 'admin@example.com', stdout=StringIO())
        self.assertFalse(User.objects.exists())

    def test_refuses_a_weak_password(self):
        with self.assertRaises(CommandError):
            self.run_command('--email', 'admin@example.com', password='123')
        self.assertFalse(User.objects.exists())

    def test_refuses_an_email_that_is_taken(self):
        User.objects.create_user(
            email='taken@example.com', password='x', full_name='T', phone='1', role=User.Role.CLIENT,
        )
        with self.assertRaisesMessage(CommandError, 'already exists'):
            self.run_command('--email', 'TAKEN@example.com')
        self.assertEqual(User.objects.get(email='taken@example.com').role, User.Role.CLIENT)

    def test_noinput_needs_the_environment_variable(self):
        with mock.patch.dict(os.environ, {PASSWORD_ENV: ''}):
            with self.assertRaisesMessage(CommandError, PASSWORD_ENV):
                call_command('create_admin', '--email', 'admin@example.com', '--noinput', stdout=StringIO())
