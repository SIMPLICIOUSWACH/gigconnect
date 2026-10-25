from argparse import BooleanOptionalAction

from django.core.management.base import BaseCommand, CommandError

from ...evaluation import report_markdown
from ...evaluation import split as ev
from ...evaluation.compare import DEFAULT_RANDOM_SEEDS
from ...evaluation.fitting import EvaluationError
from ...evaluation.report import metric_columns, results_table
from ...evaluation.run import run_evaluation


class Command(BaseCommand):
    help = (
        'Measure the recommender. Builds (or loads) the 70/15/15 split, fits the models on the train part only, '
        'scores the validation part (the default) or the test part, and writes a report and a CSV of every number to '
        'datasets/reports/. The test part is scored only with --final, and every test run is recorded. Nothing is '
        'tuned or saved by this command.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--split', choices=[ev.VALIDATION, ev.TEST], default=ev.VALIDATION,
            help='Which held-out part to score (default: validation).',
        )
        parser.add_argument(
            '--final', action='store_true',
            help='Required for --split test. Use it once, after tuning on validation is finished.',
        )
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
        part = options['split']
        # Fail before anything is fitted, so a refused test run costs nothing and is not recorded.
        if part == ev.TEST and not options['final']:
            raise CommandError(
                'The test part is only scored with --final, once, after tuning on the validation part is finished. '
                'Scoring it while tuning would make it useless as an honest estimate.'
            )
        if part == ev.TEST:
            self.stdout.write(self.style.WARNING('Scoring the TEST part. This run will be recorded.'))

        command = 'python manage.py evaluate_recommender ' + ' '.join(self._arguments(options))
        try:
            run = run_evaluation(
                part=part, final=options['final'], include_synthetic=options['include_synthetic'],
                seed=options['seed'], random_seeds=options['random_seeds'], rebuild_split=options['rebuild_split'],
                data_dir=options['data_dir'], output_dir=options['output_dir'], command=command.strip(),
            )
        except (EvaluationError, ValueError) as error:
            raise CommandError(str(error)) from error

        comparison = run.comparison
        if run.split_note:
            self.stdout.write(self.style.WARNING(run.split_note))
        for line in report_markdown.warning_lines(comparison):
            if line:
                self.stdout.write(self.style.WARNING(line.lstrip('> ').replace('**', '')))
        self.stdout.write(
            f'Split {run.split_how}, fingerprint {run.split.fingerprint()}. Scored the {part} part: '
            f'{comparison.group_sizes["all"]} freelancers, {comparison.info["relevant"]} right answers.'
        )
        self.stdout.write('')
        columns = metric_columns(report_markdown.HEADLINE_KS, report_markdown.HEADLINE_METRICS)
        for line in results_table(comparison, columns):
            self.stdout.write(line)
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Report: {run.markdown_path}'))
        self.stdout.write(self.style.SUCCESS(f'Every number: {run.csv_path}'))

    @staticmethod
    def _arguments(options):
        found = [f'--split {options["split"]}']
        if options['final']:
            found.append('--final')
        if options['include_synthetic'] is not None:
            found.append('--include-synthetic' if options['include_synthetic'] else '--no-include-synthetic')
        found.append(f'--seed {options["seed"]}')
        if options['random_seeds'] != DEFAULT_RANDOM_SEEDS:
            found.append(f'--random-seeds {options["random_seeds"]}')
        if options['rebuild_split']:
            found.append('--rebuild-split')
        return found
