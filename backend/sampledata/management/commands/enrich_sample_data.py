from django.core.management.base import BaseCommand
from django.utils import timezone

from sampledata.context import Context
from sampledata.guard import require_debug
from sampledata.history import enrich_history
from sampledata.ledger import undo
from sampledata.models import SampleRecord
from sampledata.profiles_fill import enrich_profiles
from sampledata.runner import guarded, require_main_database

SEED = 2026
BATCH = SampleRecord.Batch.ENRICH


def steps():
    """The parts of the enrichment, in order. Each skips what it has already done."""
    return [enrich_profiles, enrich_history]


class Command(BaseCommand):
    help = (
        'Make the sample accounts feel complete: profiles, avatars, logos and portfolios, and a history of completed '
        'gigs with reviews. Everything it adds is flagged so the recommender never trains or is evaluated on it, and '
        'it stops and rolls back if that is ever not true. Development only. Safe to run twice. --undo removes only '
        'what it added and puts back what it filled in. Bios and skills are never changed.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Do everything, report the counts, save nothing.')
        parser.add_argument('--undo', action='store_true', help='Remove what this command added.')

    def handle(self, *args, **options):
        require_debug()
        require_main_database()
        dry_run = options['dry_run']

        if options['undo']:
            _, _, summary = guarded(lambda: undo(BATCH), dry_run=dry_run, stdout=self.stdout)
            self.stdout.write(self.style.SUCCESS('Undone.' if not dry_run else 'Dry run: nothing was undone.'))
            for what, number in summary.items():
                self.stdout.write(f'  {what}: {number}')
            return

        ctx = Context(batch=BATCH, seed=SEED, dry_run=dry_run)

        def work():
            for step in steps():
                step(ctx)
            if ctx.stats.get('completed gigs') and ctx.ledger.anchor() is None:
                ctx.ledger.set_anchor(timezone.localdate(ctx.now))

        guarded(work, dry_run=dry_run, stdout=self.stdout, saved_files=ctx.saved_files)
        self.stdout.write(self.style.SUCCESS(
            'Dry run, nothing saved. This is what a real run would add:' if dry_run else 'Done. Added:'
        ))
        if not ctx.stats:
            self.stdout.write('  nothing new: everything was already done.')
        for what, number in ctx.stats.items():
            self.stdout.write(f'  {what}: {number}')
