import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.urls import re_path
from django.views.static import serve
from rest_framework.test import APITestCase

from accounts.models import User

from .checks import id_documents_are_private
from .id_documents import MAX_SIZE_BYTES, content_type_for

PDF = b'%PDF-1.4 fake id'
PNG = b'\x89PNG\r\n\x1a\n fake id'
JPEG = b'\xff\xd8\xff fake id'


def public_media(request, path):
    """What Django serves at /media/ while DEBUG is on, reading the setting at request time."""
    from django.conf import settings

    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [re_path(r'^media/(?P<path>.*)$', public_media)]


class IdDocumentTestCase(APITestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.media = self.root / 'media'
        self.private = self.root / 'private'
        override = override_settings(MEDIA_ROOT=self.media, PRIVATE_MEDIA_ROOT=self.private)
        override.enable()
        self.addCleanup(override.disable)
        self.freelancer = User.objects.create_user(
            email='freelancer@example.com', password='x-Test-pass-1', full_name='Otieno', phone='254700000001',
            role='freelancer',
        )

    def submit(self, name='id.pdf', content=PDF, content_type='application/pdf'):
        self.client.force_authenticate(self.freelancer)
        document = SimpleUploadedFile(name, content, content_type=content_type)
        return self.client.post(
            '/api/profile/submit-verification/', {'id_number': '12345678', 'id_document': document}, format='multipart',
        )


class PrivateStorageTests(IdDocumentTestCase):
    def test_an_upload_goes_to_private_storage_and_not_the_media_folder(self):
        self.assertEqual(self.submit().status_code, 200)
        document = self.freelancer.freelancer_profile.id_document
        self.assertTrue((self.private / document.name).is_file())
        self.assertFalse((self.media / document.name).exists())

    def test_a_document_has_no_url_to_hand_out(self):
        self.submit()
        self.freelancer.refresh_from_db()
        with self.assertRaises(ValueError):
            self.freelancer.freelancer_profile.id_document.url

    @override_settings(ROOT_URLCONF='profiles.test_id_documents')
    def test_media_id_documents_returns_404_while_other_media_is_served(self):
        (self.media / 'profile_photos').mkdir(parents=True)
        (self.media / 'profile_photos' / 'me.png').write_bytes(PNG)
        self.assertEqual(self.client.get('/media/profile_photos/me.png').status_code, 200)  # the route does work

        (self.private / 'id_documents').mkdir(parents=True)
        (self.private / 'id_documents' / 'id.pdf').write_bytes(PDF)
        self.assertEqual(self.client.get('/media/id_documents/id.pdf').status_code, 404)

    def test_the_private_folder_is_outside_the_public_one_in_the_real_settings(self):
        from config import settings as real

        self.assertNotIn(Path(real.MEDIA_ROOT).resolve(), Path(real.PRIVATE_MEDIA_ROOT).resolve().parents)


class UploadRulesTests(IdDocumentTestCase):
    def test_real_pdf_jpeg_and_png_are_accepted(self):
        for name, content, kind in (
            ('id.pdf', PDF, 'application/pdf'), ('id.jpg', JPEG, 'image/jpeg'), ('ID.JPEG', JPEG, 'image/jpeg'),
            ('id.png', PNG, 'image/png'),
        ):
            with self.subTest(name=name):
                self.assertEqual(self.submit(name, content, kind).status_code, 200)

    def test_files_that_could_carry_a_script_are_refused(self):
        script = b'<script>alert(1)</script>'
        for name, kind in (('id.html', 'text/html'), ('id.svg', 'image/svg+xml'), ('id.js', 'text/javascript')):
            with self.subTest(name=name):
                response = self.submit(name, script, kind)
                self.assertEqual(response.status_code, 400)
                self.assertIn('id_document', response.data)
        self.assertFalse(self.private.exists())

    def test_a_renamed_file_is_refused_whatever_the_browser_says_it_is(self):
        response = self.submit('id.pdf', b'<script>alert(1)</script>', 'application/pdf')
        self.assertEqual(response.status_code, 400)
        self.assertIn('not a real', str(response.data['id_document']))
        self.freelancer.freelancer_profile.refresh_from_db()
        self.assertEqual(self.freelancer.freelancer_profile.verification_status, 'unverified')

    def test_a_file_over_the_limit_is_refused(self):
        response = self.submit('id.pdf', PDF + b'x' * MAX_SIZE_BYTES)
        self.assertEqual(response.status_code, 400)
        self.assertIn('5 MB', str(response.data['id_document']))


class DocumentEndpointTests(IdDocumentTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            email='admin@example.com', password='x-Test-pass-1', full_name='Admin', phone='254700000002', role='admin',
        )
        self.profile = self.freelancer.freelancer_profile

    def url(self):
        return f'/api/admin/verifications/{self.profile.pk}/document/'

    def store(self, name, content):
        (self.private / 'id_documents').mkdir(parents=True, exist_ok=True)
        (self.private / 'id_documents' / name).write_bytes(content)
        self.profile.id_document = f'id_documents/{name}'
        self.profile.save(update_fields=['id_document'])

    def test_only_admins_get_the_file(self):
        self.store('id.pdf', PDF)
        self.assertEqual(self.client.get(self.url()).status_code, 401)
        self.client.force_authenticate(self.freelancer)
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), PDF)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('inline'))

    def test_an_old_file_of_another_type_downloads_and_is_never_shown_inline(self):
        self.store('old.html', b'<script>alert(1)</script>')
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.url())
        self.assertEqual(response['Content-Type'], 'application/octet-stream')
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        b''.join(response.streaming_content)

    def test_a_missing_file_is_a_404(self):
        self.profile.id_document = 'id_documents/gone.pdf'
        self.profile.save(update_fields=['id_document'])
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_content_types(self):
        self.assertEqual(content_type_for('a.PDF'), 'application/pdf')
        self.assertEqual(content_type_for('a.svg'), 'application/octet-stream')


class MoveCommandTests(IdDocumentTestCase):
    def run_command(self):
        output = StringIO()
        call_command('move_id_documents', stdout=output)
        return output.getvalue()

    def public_file(self, name, content=PDF):
        path = self.media / 'id_documents' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_moves_everything_and_a_profile_still_finds_its_file(self):
        public = self.public_file('real.pdf')
        self.public_file('orphan.pdf')
        profile = self.freelancer.freelancer_profile
        profile.id_document = 'id_documents/real.pdf'
        profile.save(update_fields=['id_document'])

        self.assertIn('Moved 2', self.run_command())

        self.assertFalse(public.exists())
        self.assertTrue((self.private / 'id_documents' / 'orphan.pdf').is_file())
        profile.refresh_from_db()
        with profile.id_document.open('rb') as handle:
            self.assertEqual(handle.read(), PDF)

    def test_other_media_is_left_alone(self):
        photo = self.media / 'profile_photos' / 'me.png'
        photo.parent.mkdir(parents=True)
        photo.write_bytes(PNG)
        self.run_command()
        self.assertTrue(photo.is_file())

    def test_running_it_again_does_nothing(self):
        self.public_file('real.pdf')
        self.run_command()
        self.assertIn('Moved 0', self.run_command())

    def test_it_never_overwrites_a_private_file(self):
        self.public_file('same.pdf', b'%PDF-public')
        target = self.private / 'id_documents' / 'same.pdf'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'%PDF-private')
        output = self.run_command()
        self.assertIn('same.pdf', output)
        self.assertEqual(target.read_bytes(), b'%PDF-private')
        self.assertTrue((self.media / 'id_documents' / 'same.pdf').is_file())

    def test_the_system_check_warns_until_the_files_are_moved(self):
        self.assertEqual(id_documents_are_private(None), [])
        self.public_file('real.pdf')
        warnings = id_documents_are_private(None)
        self.assertEqual([warning.id for warning in warnings], ['profiles.W001'])
        self.run_command()
        self.assertEqual(id_documents_are_private(None), [])
