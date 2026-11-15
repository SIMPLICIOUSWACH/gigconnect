from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from sampledata.context import Context
from sampledata.guard import require_debug
from sampledata.ledger import Ledger, undo
from sampledata.models import SampleRecord
from sampledata.runner import guarded, require_main_database
from sampledata.showcase import (
    CLIENT_A,
    CLIENT_B,
    FREELANCER_A,
    FREELANCER_B,
    PASSWORD_PLACEHOLDER,
    SHOWCASE_EMAILS,
    seed_showcase,
)

SEED = 7
BATCH = SampleRecord.Batch.SHOWCASE
LABELS = [
    ('Freelancer A', FREELANCER_A, 'designer, Nairobi'), ('Freelancer B', FREELANCER_B, 'developer, Mombasa'),
    ('Client A', CLIENT_A, 'café, Nairobi'), ('Client B', CLIENT_B, 'school, Mombasa'),
]


def print_logins(write):
    write('\nShowcase logins (the password is SHOWCASE_PASSWORD in backend/.env):')
    for label, spec, what in LABELS:
        write(f'  {label}  {spec["email"]}   {spec.get("company") or spec["name"]} ({what})')


class Command(BaseCommand):
    help = (
        'Create four fully filled showcase accounts for live demos: a designer in Nairobi, a developer in Mombasa, '
        'a café and a school, with completed and rated gigs, chats, applications in every status, notifications and an '
        'approved ID check (placeholder ID and selfie marked SAMPLE). Everything is flagged so the recommender never '
        'trains or is evaluated on it. Development only. Safe to run twice; --reset rebuilds only these accounts. The '
        'password comes from SHOWCASE_PASSWORD in backend/.env.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true', help='Delete the showcase accounts and everything of theirs, then rebuild.',
        )
        parser.add_argument('--dry-run', action='store_true', help='Do everything, report the counts, save nothing.')

    def handle(self, *args, **options):
        require_debug()
        require_main_database()
        dry_run, reset = options['dry_run'], options['reset']
        password = settings.SHOWCASE_PASSWORD
        if not password and not dry_run:
            raise CommandError(
                'SHOWCASE_PASSWORD is not set. Add it to backend/.env (see .env.example), then run this again.'
            )

        exists = Ledger(BATCH).exists()
        if exists and not reset:
            self.stdout.write('The showcase accounts already exist. Use --reset to rebuild them.')
            print_logins(self.stdout.write)
            return
        if not exists and User.objects.filter(email__in=SHOWCASE_EMAILS).exists():
            raise CommandError(
                'An account with a showcase email exists but was not made by this command, so it is left alone. '
                'Rename or delete it first.'
            )

        ctx = Context(batch=BATCH, seed=SEED, dry_run=dry_run)

        def work():
            if reset and exists:
                undo(BATCH)
            seed_showcase(ctx, password or PASSWORD_PLACEHOLDER)
            ctx.ledger.set_anchor(timezone.localdate(ctx.now))

        guarded(work, dry_run=dry_run, stdout=self.stdout, saved_files=ctx.saved_files)
        self.stdout.write(self.style.SUCCESS(
            'Dry run, nothing saved. This is what a real run would add:' if dry_run else 'Done. Added:'
        ))
        for what, number in ctx.stats.items():
            self.stdout.write(f'  {what}: {number}')
        print_logins(self.stdout.write)
