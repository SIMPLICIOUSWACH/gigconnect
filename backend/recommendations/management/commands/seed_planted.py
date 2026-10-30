from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ... import planted
from ...evaluation import modes


class Command(BaseCommand):
    help = (
        'Seed the synthetic_planted world: about 250 freelancers with hidden taste groups, 300 gigs and 15 to 25 '
        'applications each, for checking that the collaborative model finds a pattern when one exists. It only '
        'writes into an empty database of its own (run with DB_NAME set to it), never next to other data. The '
        'groups go to datasets/synthetic_planted/ground_truth.csv and never into the database. Development only.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--seed', type=int, default=42, help='Random seed, so the same world can be made again.')
        parser.add_argument('--freelancers', type=int, default=planted.Sizes.freelancers)
        parser.add_argument('--gigs', type=int, default=planted.Sizes.gigs)
        parser.add_argument('--clients', type=int, default=planted.Sizes.clients)
        parser.add_argument('--delete', action='store_true', help='Remove the planted world and its ground truth.')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_planted refuses to run when DEBUG is False.')
        if options['delete']:
            count = planted.delete_world()
            self.stdout.write(self.style.SUCCESS(f'Deleted the planted world ({count} accounts) and its ground truth.'))
            return

        sizes = planted.Sizes(freelancers=options['freelancers'], gigs=options['gigs'], clients=options['clients'])
        world = planted.plan_world(seed=options['seed'], sizes=sizes)
        try:
            planted.write_world(world)
        except planted.PlantedError as error:
            raise CommandError(str(error)) from error

        summary = planted.summarise(world)
        low, middle, high = summary['applicants_per_gig']
        shares = ', '.join(f'{reason} {share:.0%}' for reason, share in summary['reason_shares'].items())
        self.stdout.write(self.style.WARNING(modes.PLANTED_LABEL))
        self.stdout.write(
            f'Created {summary["freelancers"]} freelancers, {summary["clients"]} clients, {summary["gigs"]} gigs and '
            f'{summary["applications"]} applications (seed {options["seed"]}).'
        )
        self.stdout.write(f'Applicants per gig: median {middle:g} (fewest {low}, most {high}).')
        self.stdout.write(f'How the applications were picked: {shares}.')
        self.stdout.write(f'Groups: {", ".join(f"{name} {count}" for name, count in summary["groups"].items())}.')
        self.stdout.write(f'Ground truth: {modes.planted_directory() / planted.GROUND_TRUTH_FILE}')
