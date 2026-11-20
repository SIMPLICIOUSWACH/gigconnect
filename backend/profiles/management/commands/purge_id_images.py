from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from profiles.id_privacy import due_for_purge, erase_id_images


class Command(BaseCommand):
    help = (
        'Delete ID documents, selfies and plain ID numbers 90 days after an admin\'s final decision (approved or '
        'rejected). Keeps the decision, its times, the face score and model name, and the keyed hash of the ID '
        'number. Pending checks are never touched. Run it daily, for example with Windows Task Scheduler.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only say how many checks would be cleared.')

    def handle(self, *args, **options):
        now = timezone.now()
        due = list(due_for_purge(now))
        if options['dry_run']:
            self.stdout.write(f'{len(due)} ID check(s) would be cleared. Nothing was deleted (dry run).')
            return
        files = 0
        for profile in due:
            with transaction.atomic():
                files += len(erase_id_images(profile, now))
        self.stdout.write(self.style.SUCCESS(f'Cleared {len(due)} ID check(s) and deleted {files} file(s).'))
