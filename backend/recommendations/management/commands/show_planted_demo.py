from django.core.management.base import BaseCommand, CommandError

from ... import planted_demo, registry


class Command(BaseCommand):
    help = (
        'Print the demo accounts\' top 5 recommendations from the live demo model, without rebuilding anything. Run it '
        'with RECOMMENDER_PROFILE=demo after refresh_planted_demo.'
    )

    def handle(self, *args, **options):
        model = registry.availability().model
        if model is None:
            raise CommandError(
                'No demo model is loaded. Run refresh_planted_demo first, with RECOMMENDER_PROFILE=demo.'
            )
        try:
            lines = planted_demo.demo_lines(model)
        except planted_demo.DemoError as error:
            raise CommandError(str(error)) from error
        for line in lines:
            self.stdout.write(line)
