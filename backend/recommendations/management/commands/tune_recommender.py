from argparse import BooleanOptionalAction

from django.core.management.base import BaseCommand, CommandError

from ...evaluation.compare import DEFAULT_RANDOM_SEEDS
from ...evaluation.fitting import EvaluationError
from ...evaluation.tuning_run import run_tuning


class Command(BaseCommand):
    help = (
        'Try 240 combinations of the hybrid settings (largest collaborative weight, ramp, hidden factors and '
        'cold-start threshold) on the VALIDATION part of the split, write every result to datasets/reports/, and say '
        'whether the defaults should change. It never touches the test part and never changes a setting itself.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-synthetic', action=BooleanOptionalAction, default=None,
            help='Use the synthetic seed rows (default: the RECOMMENDER_INCLUDE_SYNTHETIC setting).',
        )
        parser.add_argument('--seed', type=int, default=42, help='Seed for the split, tie-breaks and the intervals.')
        parser.add_argument(
            '--random-seeds', type=int, default=DEFAULT_RANDOM_SEEDS,
            help=f'How many seeds the random baseline is averaged over (default {DEFAULT_RANDOM_SEEDS}).',
        )
        parser.add_argument(
            '--rebuild-split', action='store_true', help='Build a new split instead of loading the saved one.',
        )
        parser.add_argument('--data-dir', help='Use this folder instead of the RECOMMENDER_DATA_DIR setting.')
        parser.add_argument('--output-dir', help='Write the report and CSV here instead of <data dir>/reports.')

    def handle(self, *args, **options):
        command = 'python manage.py tune_recommender' + (
            ' --rebuild-split' if options['rebuild_split'] else ''
        ) + f' --seed {options["seed"]}'
        try:
            run = run_tuning(
                include_synthetic=options['include_synthetic'], seed=options['seed'],
                random_seeds=options['random_seeds'], rebuild_split=options['rebuild_split'],
                data_dir=options['data_dir'], output_dir=options['output_dir'], command=command,
            )
        except (EvaluationError, ValueError) as error:
            raise CommandError(str(error)) from error

        if run.split_note:
            self.stdout.write(self.style.WARNING(run.split_note))
        decision = run.decision
        self.stdout.write(f'Tried {len(run.trials)} combinations on the validation part.')
        for reason in decision.reasons:
            self.stdout.write(f'  {reason}')
        if run.suggested_bands:
            self.stdout.write(
                f'Match bands re-derived (provisional): good {run.suggested_bands["good"]}, '
                f'strong {run.suggested_bands["strong"]}.'
            )
        self.stdout.write(self.style.SUCCESS(f'Report: {run.markdown_path}'))
        self.stdout.write(self.style.SUCCESS(f'All combinations: {run.csv_path}'))
        self.stdout.write('No setting was changed. The test part was not used.')
