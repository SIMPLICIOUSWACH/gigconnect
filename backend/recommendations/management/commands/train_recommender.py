from argparse import BooleanOptionalAction

from django.core.management.base import BaseCommand, CommandError

from ...training import TrainingError, train


class Command(BaseCommand):
    help = (
        'Train the recommender on GigConnect data and the external job-posting corpus, save the models '
        '(to RECOMMENDER_ARTIFACT_DIR), and record the run. Writes a snapshot of the data used to '
        'datasets/platform/ and a report to datasets/reports/. Run import_job_corpus first to use the '
        'external corpus; without it the vocabulary is fitted on gigs only.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-synthetic', action=BooleanOptionalAction, default=None,
            help='Learn from the synthetic seed rows (default: the RECOMMENDER_INCLUDE_SYNTHETIC setting, '
                 'which is on when DEBUG is on). The synthetic share is recorded on the model either way.',
        )
        parser.add_argument('--data-dir', help='Use this folder instead of the RECOMMENDER_DATA_DIR setting.')
        parser.add_argument('--artifact-dir', help='Save the models here instead of RECOMMENDER_ARTIFACT_DIR.')

    def handle(self, *args, **options):
        try:
            row = train(
                include_synthetic=options['include_synthetic'],
                data_dir=options['data_dir'],
                artifact_dir=options['artifact_dir'],
                log=self.stdout.write,
            )
        except TrainingError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f'Trained model version {row.version}.'))
