from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ... import planted, planted_demo, registry
from ...training import TrainingError, train


class Command(BaseCommand):
    help = (
        'Rebuild the planted demo for today: the same planted world (same seed) dated up to today, the demo model '
        'retrained, the demo accounts made again, and the open-gig count and the demo printout shown. Run it with '
        'RECOMMENDER_PROFILE=demo, for example the day before a presentation. Development only.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--seed', type=int, default=42, help='The seed of the planted world (default 42).')

    def handle(self, *args, **options):
        if settings.RECOMMENDER_PROFILE != 'demo':
            raise CommandError('refresh_planted_demo only runs with RECOMMENDER_PROFILE=demo, on the planted database.')
        if not settings.DEBUG:
            raise CommandError('refresh_planted_demo refuses to run when DEBUG is False.')

        removed = planted.delete_world()
        self.stdout.write(f'Removed the old planted world ({removed} accounts).')
        try:
            planted.write_world(planted.plan_world(seed=options['seed']))
            row = train(include_synthetic=True)
        except (planted.PlantedError, TrainingError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f'Rebuilt the planted world for today and trained demo model version {row.version}.')

        registry.clear_cache()
        model = registry.availability().model
        if model is None:
            raise CommandError('The demo model could not be loaded after training.')
        try:
            planted_demo.create_demo_accounts(model)
        except planted_demo.DemoError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f'Open gigs today: {planted_demo.open_gig_count()}.'))
        self.stdout.write('')
        for line in planted_demo.demo_lines(model):
            self.stdout.write(line)
