"""
The advisory face score. All images are drawn in code; no real faces. The tests that run the real models are skipped
when the model files are not installed (as in CI); run fetch_face_models to include them.
"""

import hashlib
import shutil
import tempfile
from io import BytesIO, StringIO
from pathlib import Path
from unittest import mock, skipUnless

from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from PIL import Image

from accounts.models import User

from . import face_match
from .models import FreelancerProfile
from .testing import add_selfie

REAL_MODELS = face_match.models_installed()


def drawn_png():
    image = Image.new('RGB', (800, 600), (90, 120, 160))
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


class FaceMatchTestCase(TestCase):
    def setUp(self):
        self.private = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.private, ignore_errors=True)
        override = override_settings(PRIVATE_MEDIA_ROOT=self.private)
        override.enable()
        self.addCleanup(override.disable)
        user = User.objects.create_user(email='f@example.com', password='x', full_name='F', role='freelancer')
        self.profile = user.freelancer_profile

    def give_id(self, name='id.png', content=None):
        self.profile.id_document.save(name, ContentFile(content or drawn_png()), save=True)


class CompareTests(FaceMatchTestCase):
    def test_a_pdf_id_has_no_score(self):
        self.give_id('id.pdf', b'%PDF-1.4 synthetic')
        profile, _ = add_selfie(self.profile)
        self.assertEqual((profile.face_match_score, profile.face_match_model), (None, face_match.NOT_AVAILABLE_PDF))

    def test_no_models_no_score(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty, ignore_errors=True)
        self.give_id()
        with override_settings(FACE_MODELS_DIR=empty):
            profile, _ = add_selfie(self.profile)
        self.assertEqual((profile.face_match_score, profile.face_match_model), (None, face_match.NOT_AVAILABLE_MODELS))

    @skipUnless(REAL_MODELS, 'face models not installed; run fetch_face_models')
    def test_the_real_models_find_no_face_on_a_drawn_id(self):
        self.give_id()
        profile, _ = add_selfie(self.profile)
        self.assertEqual((profile.face_match_score, profile.face_match_model), (None, face_match.NOT_AVAILABLE_ID_FACE))

    def test_a_failure_inside_opencv_is_logged_and_gives_no_score(self):
        self.give_id()
        with mock.patch.object(face_match, 'models_installed', return_value=True), \
                mock.patch.object(face_match, '_read', side_effect=RuntimeError('broken model')), \
                self.assertLogs('profiles.face_match'):
            score, label = face_match.compare(self.profile.id_document, self.profile.id_document)
        self.assertEqual((score, label), (None, face_match.NOT_AVAILABLE_ERROR))


class AdvisoryOnlyTests(FaceMatchTestCase):
    def test_the_score_never_changes_the_status_however_high_or_low(self):
        for score in (0.99, -0.5):
            with self.subTest(score=score):
                profile = FreelancerProfile.objects.get(pk=self.profile.pk)
                profile.verification_status = 'unverified'
                profile.save(update_fields=['verification_status'])
                self.give_id()
                with mock.patch.object(face_match, 'compare', return_value=(score, face_match.MODEL_NAME)):
                    profile, _ = add_selfie(profile)
                self.assertEqual(profile.face_match_score, score)
                self.assertEqual(profile.face_match_model, face_match.MODEL_NAME)
                self.assertEqual(profile.verification_status, 'pending')


class FetchModelsTests(TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        override = override_settings(FACE_MODELS_DIR=self.folder)
        override.enable()
        self.addCleanup(override.disable)
        self.good = b'synthetic model bytes'
        self.models = {'model.onnx': ('https://example.invalid/model.onnx', hashlib.sha256(self.good).hexdigest(),
                                      len(self.good), 'MIT')}

    def fetch(self, body):
        response = mock.MagicMock()
        response.__enter__.return_value = BytesIO(body)
        with mock.patch('profiles.management.commands.fetch_face_models.MODELS', self.models), \
                mock.patch('urllib.request.urlopen', return_value=response) as opened:
            call_command('fetch_face_models', stdout=StringIO())
        return opened

    def test_a_file_whose_hash_does_not_match_is_refused_and_deleted(self):
        with self.assertRaisesMessage(CommandError, 'does not match'):
            self.fetch(b'tampered bytes')
        self.assertEqual(list(Path(self.folder).iterdir()), [])

    def test_a_good_file_is_saved_and_not_downloaded_again(self):
        self.fetch(self.good)
        self.assertEqual((Path(self.folder) / 'model.onnx').read_bytes(), self.good)
        self.assertFalse(self.fetch(self.good).called)

    def test_the_published_hashes_are_recorded(self):
        recorded = {name: values[1] for name, values in face_match.MODELS.items()}
        yunet, sface = 'face_detection_yunet_2023mar.onnx', 'face_recognition_sface_2021dec.onnx'
        self.assertEqual(recorded[yunet], '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4')
        self.assertEqual(recorded[sface], '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79')
