from django.core.management.base import BaseCommand, CommandError

from recommendations.planted_demo import DemoError
from reviews.demo import seed


class Command(BaseCommand):
    help = (
        'Planted demo only: completed sample gigs with reviews for Amina, Brian, Cynthia and a few other planted '
        'freelancers, so Find freelancers has ratings to show. The gigs and applications are flagged is_demo_extra '
        'and never used to train or evaluate the recommender. Running it again replaces the sample reviews.'
    )

    def handle(self, *args, **options):
        try:
            summary = seed()
        except DemoError as error:
            raise CommandError(str(error)) from error
        total = sum(count for _, count in summary)
        self.stdout.write(self.style.SUCCESS(f'{total} sample reviews for {len(summary)} freelancers:'))
        for freelancer, count in summary:
            profile = freelancer.freelancer_profile
            profile.refresh_from_db()
            self.stdout.write(f'  {freelancer.full_name}: {count} review(s), average {profile.rating_avg}')
