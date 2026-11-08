"""Keeping as little of an ID as possible. Every file here is synthetic."""

import importlib
import shutil
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.apps import apps
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User

from .checks import id_hash_key_is_set
from .id_privacy import hash_id_number, other_accounts_with_same_id
from .models import FreelancerProfile
from .testing import add_selfie

KEY = 'test-id-hash-key'


@override_settings(ID_HASH_KEY=KEY)
class PrivacyTestCase(APITestCase):
    def setUp(self):
        self.private = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.private, ignore_errors=True)
        override = override_settings(PRIVATE_MEDIA_ROOT=self.private)
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_user(
            email='f@example.com', password='x-Test-pass-1', full_name='Otieno', role='freelancer',
        )

    def send_id(self, user=None, number='12 345 678', content=b'%PDF-1.4 synthetic id'):
        self.client.force_authenticate(user or self.user)
        document = SimpleUploadedFile('id.pdf', content, content_type='application/pdf')
        response = self.client.post(
            '/api/profile/submit-verification/', {'id_number': number, 'id_document': document}, format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        return FreelancerProfile.objects.get(user=user or self.user)

    def decided(self, profile, days_ago, status='verified'):
        FreelancerProfile.objects.filter(pk=profile.pk).update(
            verification_status=status, verification_decided_at=timezone.now() - timedelta(days=days_ago),
            face_match_score=0.71, face_match_model='OpenCV SFace',
        )
        return FreelancerProfile.objects.get(pk=profile.pk)


class HashTests(PrivacyTestCase):
    def test_the_same_number_written_differently_gives_the_same_hash(self):
        self.assertEqual(hash_id_number('12 345 678'), hash_id_number('12-345-678'))
        self.assertNotEqual(hash_id_number('12345678'), hash_id_number('12345679'))
        self.assertEqual(len(hash_id_number('12345678')), 64)
        self.assertEqual(hash_id_number(''), '')

    def test_the_hash_depends_on_the_secret_key(self):
        with override_settings(ID_HASH_KEY='another-key'):
            other = hash_id_number('12345678')
        self.assertNotEqual(hash_id_number('12345678'), other)

    def test_sending_an_id_stores_the_hash_and_last_three(self):
        profile = self.send_id()
        self.assertEqual(profile.id_number_hash, hash_id_number('12345678'))
        self.assertEqual(profile.id_number_last3, '678')
        self.assertNotIn('12345678', profile.id_number_hash)

    def test_a_replaced_id_file_is_deleted(self):
        first = self.send_id().id_document.name
        second = self.send_id(content=b'%PDF-1.4 a newer synthetic id').id_document.name
        self.assertNotEqual(first, second)
        self.assertFalse((self.private / first).exists())
        self.assertTrue((self.private / second).exists())

    def test_admins_are_warned_when_the_same_id_is_on_another_account(self):
        mine = self.send_id(number='12345678')
        other_user = User.objects.create_user(email='o@example.com', password='x', full_name='Other', role='freelancer')
        self.send_id(other_user, number='12 345 678')
        self.assertEqual(list(other_accounts_with_same_id(mine).values_list('user_id', flat=True)), [other_user.pk])
        add_selfie(mine)
        admin = User.objects.create_user(email='a@example.com', password='x', full_name='Admin', role='admin')
        self.client.force_authenticate(admin)
        row = self.client.get('/api/admin/verifications/').data['results'][0]
        self.assertEqual(row['same_id_elsewhere'], [{'id': str(other_user.pk), 'full_name': 'Other'}])
        self.assertEqual(row['id_number_last3'], '678')


class PurgeTests(PrivacyTestCase):
    def setUp(self):
        super().setUp()
        profile, _ = add_selfie(self.send_id())
        self.files = [profile.id_document.name, profile.selfie.name]

    def purge(self, *args):
        output = StringIO()
        with self.captureOnCommitCallbacks(execute=True):
            call_command('purge_id_images', *args, stdout=output)
        return output.getvalue()

    def test_images_and_number_go_90_days_after_a_decision_and_the_record_stays(self):
        profile = self.decided(FreelancerProfile.objects.get(user=self.user), days_ago=91)
        hashed = profile.id_number_hash
        self.assertIn('Cleared 1', self.purge())
        profile.refresh_from_db()
        for name in self.files:
            self.assertFalse((self.private / name).exists(), name)
        self.assertFalse(profile.id_document or profile.selfie or profile.id_number or profile.selfie_challenge)
        self.assertIsNotNone(profile.id_images_purged_at)
        # What stays: the decision, its times, the score and model, the hash.
        self.assertEqual(profile.verification_status, 'verified')
        self.assertIsNotNone(profile.verification_decided_at)
        self.assertIsNotNone(profile.selfie_submitted_at)
        self.assertEqual((profile.face_match_score, profile.face_match_model), (0.71, 'OpenCV SFace'))
        self.assertEqual((profile.id_number_hash, profile.id_number_last3), (hashed, '678'))

    def test_rejected_checks_are_purged_too(self):
        self.decided(FreelancerProfile.objects.get(user=self.user), days_ago=120, status='rejected')
        self.assertIn('Cleared 1', self.purge())

    def test_nothing_goes_before_90_days_or_while_pending(self):
        profile = FreelancerProfile.objects.get(user=self.user)
        self.decided(profile, days_ago=89)
        self.assertIn('Cleared 0', self.purge())
        FreelancerProfile.objects.filter(pk=profile.pk).update(
            verification_status='pending', verification_decided_at=timezone.now() - timedelta(days=400),
        )
        self.assertIn('Cleared 0', self.purge())
        for name in self.files:
            self.assertTrue((self.private / name).exists(), name)

    def test_a_dry_run_deletes_nothing_and_a_second_run_finds_nothing(self):
        self.decided(FreelancerProfile.objects.get(user=self.user), days_ago=91)
        self.assertIn('1 ID check(s) would be cleared', self.purge('--dry-run'))
        self.assertTrue((self.private / self.files[0]).exists())
        self.purge()
        self.assertIn('Cleared 0', self.purge())


class AccountDeletionTests(PrivacyTestCase):
    def test_deleting_the_account_removes_the_id_images_and_number_but_keeps_the_hash(self):
        profile, _ = add_selfie(self.send_id())
        files = [profile.id_document.name, profile.selfie.name]
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/settings/delete-account/', {'password': 'x-Test-pass-1'})
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        for name in files:
            self.assertFalse((self.private / name).exists(), name)
        self.assertFalse(profile.id_document or profile.selfie or profile.id_number)
        self.assertEqual(profile.id_number_hash, hash_id_number('12345678'))


class PrivacyContactTests(PrivacyTestCase):
    @override_settings(PRIVACY_CONTACT_EMAIL='privacy@example.com')
    def test_the_contact_is_on_the_privacy_endpoint_and_in_the_consent_text(self):
        self.client.force_authenticate(None)
        info = self.client.get('/api/meta/privacy/').data
        self.assertEqual(info, {'contact_email': 'privacy@example.com', 'id_image_retention_days': 90})
        self.client.force_authenticate(self.user)
        consent = self.client.get('/api/profile/verification/challenge/').data['consent_text']
        self.assertIn('Questions or deletion requests: privacy@example.com.', consent)

    @override_settings(PRIVACY_CONTACT_EMAIL='')
    def test_no_contact_set_means_no_contact_line(self):
        self.client.force_authenticate(self.user)
        consent = self.client.get('/api/profile/verification/challenge/').data['consent_text']
        self.assertNotIn('Questions or deletion requests', consent)


class HashKeyCheckTests(TestCase):
    @override_settings(ID_HASH_KEY='')
    def test_a_missing_key_is_warned_about(self):
        self.assertEqual([warning.id for warning in id_hash_key_is_set(None)], ['profiles.W002'])

    @override_settings(ID_HASH_KEY=KEY)
    def test_a_set_key_is_fine(self):
        self.assertEqual(id_hash_key_is_set(None), [])

    @override_settings(ID_HASH_KEY=KEY)
    def test_existing_numbers_get_a_hash_when_migrating(self):
        user = User.objects.create_user(email='old@example.com', password='x', full_name='Old', role='freelancer')
        FreelancerProfile.objects.filter(user=user).update(id_number='87 654 321', id_document='id_documents/old.pdf')
        module = importlib.import_module('profiles.migrations.0014_hash_existing_id_numbers')
        module.hash_existing(apps, None)
        profile = FreelancerProfile.objects.get(user=user)
        self.assertEqual((profile.id_number_hash, profile.id_number_last3), (hash_id_number('87654321'), '321'))

    def test_the_document_field_is_still_in_private_storage(self):
        user = User.objects.create_user(email='p@example.com', password='x', full_name='P', role='freelancer')
        private = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, private, ignore_errors=True)
        with override_settings(PRIVATE_MEDIA_ROOT=private):
            user.freelancer_profile.id_document.save('id.pdf', ContentFile(b'%PDF-1.4'), save=True)
            self.assertTrue((Path(private) / user.freelancer_profile.id_document.name).exists())


class RehashTests(PrivacyTestCase):
    def test_rehashing_uses_the_current_key_for_numbers_still_stored(self):
        profile = self.send_id()
        with override_settings(ID_HASH_KEY='a-new-key'):
            output = StringIO()
            call_command('rehash_id_numbers', stdout=output)
            expected = hash_id_number('12345678')
        profile.refresh_from_db()
        self.assertIn('Updated 1', output.getvalue())
        self.assertEqual(profile.id_number_hash, expected)

    def test_numbers_already_deleted_are_reported_not_changed(self):
        profile = self.send_id()
        FreelancerProfile.objects.filter(pk=profile.pk).update(id_number='')
        output = StringIO()
        call_command('rehash_id_numbers', stdout=output)
        self.assertIn('1 hash(es) belong to numbers already deleted', output.getvalue())
