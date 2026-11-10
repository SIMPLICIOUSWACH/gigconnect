from django.core.management.base import BaseCommand

from messaging.models import Conversation
from messaging.retention import due_for_deletion


class Command(BaseCommand):
    help = (
        'Delete whole conversations (messages and reports) 12 months after they became read-only: a gig completed or '
        'closed, a gig or application removed, or an account suspended or deleted. Run it daily.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only say how many would be deleted.')

    def handle(self, *args, **options):
        due = due_for_deletion()
        if options['dry_run']:
            self.stdout.write(f'{len(due)} conversation(s) would be deleted. Nothing was deleted (dry run).')
            return
        deleted, _ = Conversation.objects.filter(pk__in=[conversation.pk for conversation in due]).delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {len(due)} conversation(s).'))
