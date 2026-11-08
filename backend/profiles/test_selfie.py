"""
Tests for the selfie step. Every image here is drawn in code (plain colours and shapes): no real faces. Where a test
needs "a face was found", the Haar detector is replaced with a stub, and the test says so.
"""

import importlib
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest import mock

from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from accounts.models import User
from notifications.models import Notification

from . import selfie as selfie_rules
from .models import FreelancerProfile, VerificationChallenge

CHALLENGE_URL = '/api/profile/verification/challenge/'
SELFIE_URL = '/api/profile/verification/selfie/'
SUBMIT_URL = '/api/profile/submit-verification/'
ONE_FACE = [(200, 120, 260, 260)]


def photo(size=(720, 960), image_format='JPEG', exif=None, colour=(180, 140, 120)):
    """A synthetic picture: a flat colour with a lighter ellipse. Not a face, and never a real person."""
    image = Image.new('RGB', size, colour)
    from PIL import ImageDraw

    oval = (size[0] // 4, size[1] // 5, size[0] * 3 // 4, size[1] * 3 // 5)
    ImageDraw.Draw(image).ellipse(oval, fill=(230, 200, 180))
    buffer = BytesIO()
    kwargs = {'exif': exif} if exif is not None else {}
    image.save(buffer, format=image_format, **kwargs)
    return buffer.getvalue()


def upload(content=None, name='selfie.jpg', content_type='image/jpeg'):
    return SimpleUploadedFile(name, content if content is not None else photo(), content_type=content_type)


def id_upload():
    return SimpleUploadedFile('id.pdf', b'%PDF-1.4 synthetic id', content_type='application/pdf')


class SelfieTestCase(APITestCase):
    def setUp(self):
        self.private = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.private, ignore_errors=True)
        override = override_settings(PRIVATE_MEDIA_ROOT=self.private)
        override.enable()
        self.addCleanup(override.disable)
        self.freelancer = User.objects.create_user(
            email='freelancer@example.com', password='x-Test-pass-1', full_name='Otieno', role='freelancer',
            is_email_verified=True,
        )
        self.client.force_authenticate(self.freelancer)

    def challenge(self):
        return self.client.get(CHALLENGE_URL).data

    def send_selfie(self, challenge_id=None, consent='true', file=None, faces=ONE_FACE):
        data = {'selfie': file or upload(), 'consent': consent}
        if challenge_id is not False:
            data['challenge_id'] = challenge_id or self.challenge()['id']
        # The detector is stubbed: drawn test images contain no real face.
        with mock.patch.object(selfie_rules, 'detect_faces', return_value=faces):
            return self.client.post(SELFIE_URL, data, format='multipart')

    def send_id(self):
        return self.client.post(SUBMIT_URL, {'id_number': '12345678', 'id_document': id_upload()}, format='multipart')

    def profile(self):
        return FreelancerProfile.objects.get(user=self.freelancer)


class ChallengeTests(SelfieTestCase):
    def test_a_challenge_is_a_random_gesture_that_lasts_ten_minutes(self):
        data = self.challenge()
        self.assertTrue(data['text'].startswith('Hold your ID next to your face and '))
        self.assertIn(data['text'][len('Hold your ID next to your face and '):-1], selfie_rules.GESTURES)
        challenge = VerificationChallenge.objects.get(pk=data['id'])
        self.assertEqual(data['expires_at'], challenge.issued_at + timedelta(minutes=10))
        self.assertIn('deleted 90 days after a decision', data['consent_text'])

    def test_only_freelancers_get_one(self):
        client_user = User.objects.create_user(email='c@example.com', password='x', full_name='C', role='client')
        self.client.force_authenticate(client_user)
        self.assertEqual(self.client.get(CHALLENGE_URL).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(CHALLENGE_URL).status_code, 401)

    def test_an_expired_challenge_is_refused(self):
        challenge_id = self.challenge()['id']
        VerificationChallenge.objects.filter(pk=challenge_id).update(issued_at=timezone.now() - timedelta(minutes=11))
        response = self.send_selfie(challenge_id)
        self.assertEqual((response.status_code, response.data['code']), (400, 'challenge_expired'))
        self.assertFalse(self.profile().selfie)

    def test_a_used_challenge_is_refused(self):
        challenge_id = self.challenge()['id']
        self.assertEqual(self.send_selfie(challenge_id).status_code, 200)
        response = self.send_selfie(challenge_id)
        self.assertEqual((response.status_code, response.data['code']), (400, 'challenge_expired'))

    def test_someone_elses_challenge_is_refused(self):
        other = User.objects.create_user(email='o@example.com', password='x', full_name='O', role='freelancer')
        theirs = VerificationChallenge.objects.create(user=other, text='Hold your ID next to your face and wave.')
        self.assertEqual(self.send_selfie(str(theirs.pk)).status_code, 400)


class SubmissionRulesTests(SelfieTestCase):
    def test_no_consent_no_selfie(self):
        for consent in ('false', ''):
            with self.subTest(consent=consent):
                response = self.send_selfie(consent=consent)
                self.assertEqual(response.status_code, 400)
                self.assertIn('consent', response.data)
        self.assertFalse(self.profile().selfie)

    def test_a_gallery_style_upload_without_a_challenge_is_refused(self):
        response = self.send_selfie(challenge_id=False)
        self.assertEqual(response.status_code, 400)
        self.assertIn('challenge_id', response.data)
        self.assertFalse(self.profile().selfie)

    def test_only_jpeg_or_png_photos_of_a_useful_size(self):
        gif = photo(image_format='GIF')
        for file, message in (
            (upload(b'not an image at all'), 'not a photo'),
            (upload(gif, 'selfie.gif', 'image/gif'), 'JPEG or PNG'),
            (upload(photo(size=(600, 450))), 'too small'),
            (upload(photo() + b'0' * selfie_rules.MAX_SIZE_BYTES), '5 MB'),
        ):
            with self.subTest(message=message):
                response = self.send_selfie(file=file)
                self.assertEqual(response.status_code, 400)
                self.assertIn(message, str(response.data))
        self.assertTrue(self.send_selfie(file=upload(photo(size=(640, 480)))).status_code == 200)

    def test_location_and_camera_details_are_stripped_and_the_photo_re_encoded(self):
        exif = Image.Exif()
        exif[0x010F] = 'Phone maker'  # Make
        exif[0x8825] = {2: (1.0, 17.0, 0.0)}  # GPS latitude
        self.assertEqual(self.send_selfie(file=upload(photo(image_format='PNG', exif=exif), 'me.png', 'image/png'))
                         .status_code, 200)
        with self.profile().selfie.open('rb') as handle:
            stored = Image.open(BytesIO(handle.read()))
            self.assertEqual(stored.format, 'JPEG')
            self.assertEqual(dict(stored.getexif()), {})

    def test_no_face_asks_for_a_retake_and_the_challenge_still_works(self):
        challenge_id = self.challenge()['id']
        response = self.send_selfie(challenge_id, faces=[])
        self.assertEqual((response.status_code, response.data['code']), (400, 'retake'))
        self.assertIn('could not find your face', response.data['selfie'][0])
        self.assertEqual(self.send_selfie(challenge_id).status_code, 200)

    def test_two_people_ask_for_a_retake(self):
        response = self.send_selfie(faces=[(100, 100, 250, 250), (420, 120, 230, 230)])
        self.assertEqual((response.status_code, response.data['code']), (400, 'retake'))
        self.assertIn('more than one face', response.data['selfie'][0])

    def test_the_small_face_on_the_id_card_is_not_a_second_person(self):
        self.assertEqual(self.send_selfie(faces=[(200, 120, 260, 260), (520, 600, 60, 60)]).status_code, 200)

    def test_counting_keeps_faces_at_least_a_third_of_the_largest(self):
        self.assertEqual(selfie_rules.counted_faces([]), [])
        self.assertEqual(selfie_rules.counted_faces([(0, 0, 300, 300), (0, 0, 99, 99)]), [(0, 0, 300, 300)])
        self.assertEqual(len(selfie_rules.counted_faces([(0, 0, 300, 300), (0, 0, 100, 100)])), 2)

    def test_the_real_detector_finds_no_face_in_a_drawn_picture(self):
        image = Image.open(BytesIO(photo()))
        self.assertEqual(selfie_rules.face_problem(image), selfie_rules.RETAKE_NO_FACE)


class QueueTests(SelfieTestCase):
    def test_the_check_only_joins_the_queue_once_both_parts_are_in(self):
        response = self.send_id()
        self.assertEqual((response.status_code, response.data['verification_status']), (200, 'unverified'))
        self.assertEqual(response.data['verification'], {
            'has_id_document': True, 'has_selfie': False, 'needs_new_id': False, 'needs_new_selfie': False,
        })
        response = self.send_selfie()
        self.assertEqual(response.data['verification_status'], 'pending')
        profile = self.profile()
        self.assertIsNotNone(profile.verification_submitted_at)
        self.assertTrue(profile.selfie_challenge.startswith('Hold your ID'))
        self.assertIsNotNone(profile.selfie_consent_at)

    def test_the_selfie_can_come_first(self):
        self.assertEqual(self.send_selfie().data['verification_status'], 'unverified')
        self.assertEqual(self.send_id().data['verification_status'], 'pending')

    def test_nothing_more_can_be_sent_while_it_is_with_an_admin(self):
        self.send_id()
        self.send_selfie()
        self.assertEqual(self.send_selfie().status_code, 400)
        self.assertEqual(self.send_id().status_code, 400)

    def test_me_shows_progress_but_never_the_files(self):
        self.send_id()
        data = self.client.get('/api/auth/me/').data
        self.assertEqual(data['verification']['has_id_document'], True)
        text = str(data)
        self.assertNotIn('selfie', ''.join(k for k in data['profile']))
        self.assertNotIn('id_documents/', text)
        self.assertNotIn('12345678', text)


class PrivacyOfTheFileTests(SelfieTestCase):
    def test_the_selfie_is_in_private_storage_with_no_url(self):
        self.send_selfie()
        selfie = self.profile().selfie
        self.assertTrue((self.private / selfie.name).is_file())
        self.assertTrue(selfie.name.startswith('selfies/'))
        with self.assertRaises(ValueError):
            selfie.url

    def test_the_public_profile_never_mentions_it(self):
        self.send_selfie()
        viewer = User.objects.create_user(email='v@example.com', password='x', full_name='V', role='client')
        self.client.force_authenticate(viewer)
        response = self.client.get(f'/api/profiles/{self.freelancer.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('selfie', str(response.data))


class SendBackForSelfieMigrationTests(TestCase):
    def test_pending_checks_without_a_selfie_go_back_and_are_told(self):
        waiting = User.objects.create_user(email='w@example.com', password='x', full_name='W', role='freelancer')
        done = User.objects.create_user(email='d@example.com', password='x', full_name='D', role='freelancer')
        profiles = FreelancerProfile.objects
        profiles.filter(user=waiting).update(verification_status='pending', id_document='id_documents/a.pdf')
        profiles.filter(user=done).update(verification_status='verified', id_document='id_documents/b.pdf')

        module = importlib.import_module('profiles.migrations.0010_send_pending_checks_back_for_a_selfie')
        module.ask_for_selfies(apps, None)

        profile = FreelancerProfile.objects.get(user=waiting)
        self.assertEqual(profile.verification_status, 'unverified')
        self.assertEqual(profile.id_document.name, 'id_documents/a.pdf')
        note = Notification.objects.get(recipient=waiting)
        self.assertEqual(note.kind, 'verification_selfie_needed')
        self.assertEqual(note.body, "We've added a selfie step to ID verification. Please complete it to finish.")
        self.assertEqual(FreelancerProfile.objects.get(user=done).verification_status, 'verified')
        self.assertFalse(Notification.objects.filter(recipient=done).exists())
