from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...models import Gig
from ...signals import update_search_vector

BATCH_SIZE = 500


class Command(BaseCommand):
    help = (
        'Recompute Gig.search_vector for rows the post_save/m2m_changed signals never saw '
        '(bulk_create, QuerySet.update(), raw imports) or that changed indirectly (a skill '
        'rename). Idempotent: safe to re-run at any time, including on an unaffected table.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--gig-id', dest='gig_id', default=None,
            help='Rebuild only this gig (by id) instead of the whole table.',
        )

    def handle(self, *args, **options):
        gig_id = options['gig_id']

        if gig_id:
            try:
                gig = Gig.objects.prefetch_related('skills').get(pk=gig_id)
            except Gig.DoesNotExist as exc:
                raise CommandError(f'No gig with id "{gig_id}".') from exc
            update_search_vector(gig)
            self.stdout.write(self.style.SUCCESS(f'Rebuilt search vector for gig {gig_id}.'))
            return

        total = Gig.objects.count()
        rebuilt = 0
        batch = []

        queryset = Gig.objects.prefetch_related('skills').order_by('pk').iterator(chunk_size=BATCH_SIZE)
        for gig in queryset:
            batch.append(gig)
            if len(batch) >= BATCH_SIZE:
                self._rebuild_batch(batch)
                rebuilt += len(batch)
                self.stdout.write(f'Rebuilt {rebuilt}/{total}...')
                batch = []

        if batch:
            self._rebuild_batch(batch)
            rebuilt += len(batch)

        self.stdout.write(self.style.SUCCESS(f'Rebuilt search vectors for {rebuilt} gig(s).'))

    @transaction.atomic
    def _rebuild_batch(self, gigs):
        for gig in gigs:
            update_search_vector(gig)
