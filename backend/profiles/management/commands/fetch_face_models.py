import hashlib
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from profiles.face_match import MODELS

CHUNK = 1024 * 1024


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(CHUNK), b''):
            digest.update(block)
    return digest.hexdigest()


class Command(BaseCommand):
    help = (
        'Download the two face models for the advisory face-match score from the official OpenCV Zoo repository into '
        'FACE_MODELS_DIR, and check each one against the SHA-256 published there. A file that does not match is '
        'deleted. Files already in place and correct are left alone. Safe to run again.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Download again even if a correct copy is there.')

    def handle(self, *args, **options):
        folder = Path(settings.FACE_MODELS_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        for name, (url, expected, size, licence) in MODELS.items():
            target = folder / name
            if target.is_file() and not options['force'] and sha256_of(target) == expected:
                self.stdout.write(f'{name}: already in place, SHA-256 matches.')
                continue
            partial = target.with_suffix('.part')
            self.stdout.write(f'{name}: downloading {size:,} bytes ({licence}) from {url}')
            try:
                with urllib.request.urlopen(url, timeout=60) as response, open(partial, 'wb') as out:
                    for block in iter(lambda: response.read(CHUNK), b''):
                        out.write(block)
            except OSError as error:
                partial.unlink(missing_ok=True)
                raise CommandError(f'{name}: download failed: {error}') from error
            actual = sha256_of(partial)
            if actual != expected:
                partial.unlink(missing_ok=True)
                raise CommandError(f'{name}: SHA-256 {actual} does not match the published {expected}. Deleted.')
            partial.replace(target)
            self.stdout.write(self.style.SUCCESS(f'{name}: saved, SHA-256 {actual} matches.'))
