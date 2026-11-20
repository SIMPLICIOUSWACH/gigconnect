from django.core.management.base import BaseCommand

from messaging.emails import send_due_emails


class Command(BaseCommand):
    help = (
        'Email people about chat messages still unread 15 minutes after they were sent, if their "New messages" email '
        'setting is on. At most one email per chat an hour. Safe to run again or twice at once: nobody is emailed '
        'twice for the same messages. Schedule it every 5 minutes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only say how many emails are due.')

    def handle(self, *args, **options):
        count = send_due_emails(dry_run=options['dry_run'])
        if options['dry_run']:
            self.stdout.write(f'{count} email(s) are due. Nothing was sent (dry run).')
        else:
            self.stdout.write(self.style.SUCCESS(f'Sent {count} email(s).'))
