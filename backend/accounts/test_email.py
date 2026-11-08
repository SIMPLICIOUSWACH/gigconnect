import json
import os
import smtplib
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase, APITransactionTestCase

from .checks import SMTP_BACKEND, email_settings
from .email import send_verification_email, send_verification_email_on_commit
from .models import User
from .verification_views import SEND_FAILED, SIGNED_OUT_ANSWER

BACKEND_DIR = Path(settings.BASE_DIR)
RESEND_URL = '/api/auth/resend-verification/'
SMTP_DOWN = smtplib.SMTPAuthenticationError(535, b'Username and Password not accepted')


def make_user(email='person@example.com', verified=False):
    return User.objects.create_user(
        email=email, password='x-Test-pass-1', full_name='Person', role='client', is_email_verified=verified,
    )


def settings_with(env):
    """The email settings Django ends up with for these environment variables, read in a fresh process."""
    code = (
        'import json, django; django.setup(); from django.conf import settings as s; '
        'print(json.dumps({k: getattr(s, k) for k in ("EMAIL_BACKEND", "EMAIL_HOST", "EMAIL_PORT", "EMAIL_USE_TLS", '
        '"EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD", "DEFAULT_FROM_EMAIL", "FRONTEND_URL")}))'
    )
    environment = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'config.settings', **env}
    output = subprocess.run(
        [sys.executable, '-c', code], cwd=BACKEND_DIR, env=environment, capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(output.strip().splitlines()[-1])


class EmailSettingsTests(TestCase):
    def test_every_email_setting_comes_from_the_environment(self):
        values = settings_with({
            'EMAIL_BACKEND': SMTP_BACKEND, 'EMAIL_HOST': 'smtp.gmail.com', 'EMAIL_PORT': '587',
            'EMAIL_USE_TLS': 'True', 'EMAIL_HOST_USER': 'sender@example.com', 'EMAIL_HOST_PASSWORD': 'app-password',
            'DEFAULT_FROM_EMAIL': 'GigConnect <sender@example.com>', 'FRONTEND_URL': 'https://gigconnect.example',
        })
        self.assertEqual(values, {
            'EMAIL_BACKEND': SMTP_BACKEND, 'EMAIL_HOST': 'smtp.gmail.com', 'EMAIL_PORT': 587, 'EMAIL_USE_TLS': True,
            'EMAIL_HOST_USER': 'sender@example.com', 'EMAIL_HOST_PASSWORD': 'app-password',
            'DEFAULT_FROM_EMAIL': 'GigConnect <sender@example.com>', 'FRONTEND_URL': 'https://gigconnect.example',
        })

    def test_empty_values_fall_back_to_printing_emails_to_the_console(self):
        empty = {name: '' for name in (
            'EMAIL_BACKEND', 'EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_USE_TLS', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD',
            'DEFAULT_FROM_EMAIL', 'FRONTEND_URL',
        )}
        values = settings_with(empty)
        self.assertEqual(values['EMAIL_BACKEND'], 'django.core.mail.backends.console.EmailBackend')
        self.assertEqual((values['EMAIL_PORT'], values['EMAIL_USE_TLS']), (25, False))
        self.assertEqual(values['FRONTEND_URL'], 'http://localhost:5173')

    def test_the_example_env_file_holds_placeholders_only(self):
        example = (BACKEND_DIR / '.env.example').read_text(encoding='utf-8')
        self.assertIn('EMAIL_HOST=smtp.gmail.com', example)
        self.assertIn('EMAIL_HOST_PASSWORD=your-16-character-app-password', example)

    @override_settings(EMAIL_BACKEND=SMTP_BACKEND, EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='')
    def test_a_warning_when_smtp_has_no_login(self):
        self.assertEqual([warning.id for warning in email_settings(None)], ['accounts.W001'])

    @override_settings(EMAIL_BACKEND=SMTP_BACKEND, EMAIL_HOST_USER='a@example.com', EMAIL_HOST_PASSWORD='x')
    def test_no_warning_when_smtp_is_set_up(self):
        self.assertEqual(email_settings(None), [])


class SendingTests(TestCase):
    def test_a_failure_is_logged_and_reported_not_raised(self):
        user = make_user()
        with mock.patch('accounts.email.send_mail', side_effect=SMTP_DOWN), self.assertLogs('accounts.email') as logs:
            self.assertFalse(send_verification_email(user))
        self.assertIn(str(user.pk), logs.output[0])
        self.assertNotIn(user.email, logs.output[0])

    def test_nothing_is_sent_for_an_account_that_rolls_back(self):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    send_verification_email_on_commit(make_user())
                    raise RuntimeError('the sign-up failed after the user row was written')
            except RuntimeError:
                pass
        self.assertEqual(mail.outbox, [])

    def test_the_email_waits_for_the_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            outcome = send_verification_email_on_commit(make_user())
        self.assertEqual((mail.outbox, outcome), ([], {}))
        callbacks[0]()
        self.assertEqual((len(mail.outbox), outcome), (1, {'sent': True}))


class RealCommitTestCase(APITransactionTestCase):
    """
    Real commits, as in the running app, where a view is not inside a transaction and the email goes out before the
    response is built. (A plain TestCase wraps each test in a transaction, so the email would only go after the
    response.) The rows the migrations seed are put back after each test.
    """

    serialized_rollback = True


class RegistrationEmailTests(RealCommitTestCase):
    def register(self):
        return self.client.post('/api/auth/register/', {
            'full_name': 'New Client', 'email': 'new@example.com', 'password': 'StrongPass123!',
            'confirm_password': 'StrongPass123!', 'role': 'client', 'phone': '254700000000',
        })

    def test_a_failed_email_does_not_fail_registration(self):
        with mock.patch('accounts.email.send_mail', side_effect=SMTP_DOWN), self.assertLogs('accounts.email'):
            response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertIs(response.data['verification_email_sent'], False)
        self.assertTrue(User.objects.filter(email='new@example.com').exists())

    def test_a_sent_email_is_reported(self):
        response = self.register()
        self.assertIs(response.data['verification_email_sent'], True)
        self.assertEqual(mail.outbox[0].to, ['new@example.com'])


class ResendTests(APITestCase):
    def setUp(self):
        cache.clear()  # the throttle counts live in the cache
        self.user = make_user()

    def test_signed_in_resend_sends_and_says_so(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(RESEND_URL)
        self.assertEqual((response.status_code, response.data['sent']), (200, True))
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_signed_in_resend_reports_a_failure(self):
        self.client.force_authenticate(self.user)
        with mock.patch('accounts.email.send_mail', side_effect=SMTP_DOWN), self.assertLogs('accounts.email'):
            response = self.client.post(RESEND_URL)
        self.assertEqual((response.status_code, response.data['detail']), (503, SEND_FAILED))

    def test_an_already_verified_user_is_told(self):
        self.client.force_authenticate(make_user('done@example.com', verified=True))
        response = self.client.post(RESEND_URL)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(mail.outbox, [])

    def test_signed_out_gets_the_same_answer_whether_or_not_the_account_exists(self):
        found = self.client.post(RESEND_URL, {'email': 'PERSON@example.com'})
        missing = self.client.post(RESEND_URL, {'email': 'nobody@example.com'})
        verified = make_user('done@example.com', verified=True)
        already = self.client.post(RESEND_URL, {'email': verified.email})
        self.assertEqual({r.status_code for r in (found, missing, already)}, {200})
        self.assertEqual({r.data['detail'] for r in (found, missing, already)}, {SIGNED_OUT_ANSWER})
        self.assertEqual([message.to for message in mail.outbox], [[self.user.email]])

    def test_signed_out_failure_is_not_revealed(self):
        with mock.patch('accounts.email.send_mail', side_effect=SMTP_DOWN), self.assertLogs('accounts.email'):
            response = self.client.post(RESEND_URL, {'email': self.user.email})
        self.assertEqual((response.status_code, response.data['detail']), (200, SIGNED_OUT_ANSWER))

    def test_signed_out_needs_an_email(self):
        self.assertEqual(self.client.post(RESEND_URL, {}).status_code, 400)

    def test_it_is_limited_to_five_an_hour(self):
        codes = [self.client.post(RESEND_URL, {'email': self.user.email}).status_code for _ in range(6)]
        self.assertEqual(codes, [200] * 5 + [429])
        self.assertEqual(len(mail.outbox), 5)


class SettingsEmailChangeTests(RealCommitTestCase):
    def test_a_failed_email_after_changing_address_is_reported(self):
        user = make_user(verified=True)
        self.client.force_authenticate(user)
        with mock.patch('accounts.email.send_mail', side_effect=SMTP_DOWN), self.assertLogs('accounts.email'):
            response = self.client.patch('/api/settings/account/', {'email': 'moved@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data['verification_email_sent'], False)

    def test_no_flag_when_the_email_did_not_change(self):
        self.client.force_authenticate(make_user(verified=True))
        response = self.client.patch('/api/settings/account/', {'full_name': 'New Name'})
        self.assertNotIn('verification_email_sent', response.data)
