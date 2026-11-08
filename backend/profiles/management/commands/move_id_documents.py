import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from profiles.checks import PUBLIC_FOLDER, public_id_documents


class Command(BaseCommand):
    help = (
        'Move every ID document from the public media folder to private storage (PRIVATE_MEDIA_ROOT), including files '
        'no profile points to any more. Stored names do not change, so the database needs no update and all databases '
        'sharing the folder are covered by one run. Safe to run again. A file with the same name already in private '
        'storage is left where it is and reported, so nothing is overwritten.'
    )

    def handle(self, *args, **options):
        source = Path(settings.MEDIA_ROOT) / PUBLIC_FOLDER
        target = Path(settings.PRIVATE_MEDIA_ROOT) / PUBLIC_FOLDER
        moved, conflicts = 0, []
        for path in public_id_documents():
            destination = target / path.relative_to(source)
            if destination.exists():
                conflicts.append(path.name)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(destination))
            moved += 1

        self.stdout.write(self.style.SUCCESS(f'Moved {moved} ID document(s) to private storage.'))
        if conflicts:
            self.stdout.write(self.style.WARNING(
                f'{len(conflicts)} left in the public folder because the name is already taken: '
                f'{", ".join(sorted(conflicts))}'
            ))
