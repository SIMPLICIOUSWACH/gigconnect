from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from gigs.models import Gig
from sampledata.dates import shift_batch
from sampledata.guard import require_debug
from sampledata.ledger import Ledger
from sampledata.models import SampleRecord
from sampledata.runner import guarded, require_main_database

BATCHES = [SampleRecord.Batch.SHOWCASE, SampleRecord.Batch.ENRICH]


class Command(BaseCommand):
    help = (
        'Move the showcase timeline (and the enriched sample history) forward to today, so open gigs stay open and '
        'their deadlines are in the future. Run it the day before a presentation. Everything moves by the same number '
        'of days, so the order of events never changes. Only rows the sample-data commands made are touched. '
        'Development only.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, help='Move forward by this many days instead of since the last run.')
        parser.add_argument('--only-showcase', action='store_true', help='Leave the enriched sample history alone.')
        parser.add_argument('--dry-run', action='store_true', help='Say what would move, change nothing.')

    def handle(self, *args, **options):
        require_debug()
        require_main_database()
        today = timezone.localdate()
        batches = BATCHES[:1] if options['only_showcase'] else BATCHES
        plans = []
        for batch in batches:
            ledger = Ledger(batch)
            if not ledger.exists():
                continue
            anchor = ledger.anchor()
            days = options['days'] if options['days'] is not None else (
                (today - date.fromisoformat(anchor)).days if anchor else 0
            )
            plans.append((batch, ledger, days))
        if not plans:
            raise CommandError('Nothing to move: neither seed_showcase nor enrich_sample_data has been run here.')

        def work():
            results = []
            for batch, ledger, days in plans:
                if days > 0 or (options['days'] is not None and days != 0):
                    results.append((batch, days, shift_batch(batch, days)))
                    ledger.set_anchor(today)
                else:
                    results.append((batch, 0, None))
            return results

        _, _, results = guarded(work, dry_run=options['dry_run'], stdout=None)
        for batch, days, moved in results:
            if moved is None:
                self.stdout.write(f'{batch}: already up to date, nothing to move.')
                continue
            verb = 'Would move' if options['dry_run'] else 'Moved'
            self.stdout.write(self.style.SUCCESS(f'{batch}: {verb} everything forward by {days} day(s).'))
            for what, number in moved.items():
                self.stdout.write(f'  {what}: {number}')
        stale = Gig.objects.filter(is_demo_extra=True, status='open', application_deadline__lt=today).count()
        self.stdout.write(f'Open sample gigs with a deadline already past: {stale}.')
