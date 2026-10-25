from argparse import BooleanOptionalAction
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from gigs.models import Gig

from ...evaluation import modes, readiness, report
from ...evaluation.fitting import EvaluationError
from ...evaluation.run import prepare_split, reports_folder


class Command(BaseCommand):
    help = (
        'Check whether the training data has anything for the collaborative model to learn: the share of the matrix '
        'that k hidden factors explain, against random matrices of the same shape. Reads the train part of the split '
        'only, and writes a report to datasets/reports/.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-synthetic', action=BooleanOptionalAction, default=None,
            help='Use the synthetic seed rows (default: the RECOMMENDER_INCLUDE_SYNTHETIC setting).',
        )
        parser.add_argument('--draws', type=int, default=readiness.DEFAULT_DRAWS, help='Random matrices per kind.')
        parser.add_argument('--seed', type=int, default=42, help='Seed for the split.')
        parser.add_argument('--rebuild-split', action='store_true', help='Build a new split instead of loading it.')
        parser.add_argument('--output-dir', help='Write the report here instead of <data dir>/reports.')

    def handle(self, *args, **options):
        try:
            split, how, note, include_synthetic = prepare_split(
                options['include_synthetic'], options['seed'], options['rebuild_split'], None,
            )
        except EvaluationError as error:
            raise CommandError(str(error)) from error
        if note:
            self.stdout.write(self.style.WARNING(note))
        mode = modes.current_mode()
        if mode == modes.SYNTHETIC_PLANTED:
            self.stdout.write(self.style.WARNING(modes.PLANTED_LABEL))

        found = readiness.check(split, include_synthetic, draws=options['draws'])
        command = f'python manage.py check_collaborative_readiness --draws {options["draws"]}'
        folder = reports_folder(None, options['output_dir'])
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'{report.next_stem(folder, prefix=modes.report_prefix("readiness", mode))}.md'
        path.write_text(readiness.markdown(
            found, split, modes.label_lines(mode), command, date.today().isoformat(), Gig.objects.count(),
        ), encoding='utf-8')

        rows, columns = found.shape
        self.stdout.write(f'Matrix {rows} x {columns}, {found.filled} filled cells, density {found.density:.1%}.')
        self.stdout.write('k   real    uniform random    same-counts random')
        for row in found.rows:
            self.stdout.write(
                f'{row.k:<3} {row.real:6.1%}  {row.uniform_mean:6.1%} sd {row.uniform_sd:4.1%}    '
                f'{row.degree_mean:6.1%} sd {row.degree_sd:4.1%}'
            )
        self.stdout.write(f'Structure above uniform random: {"yes" if found.above_uniform else "no"}. '
                          f'Above same-counts random: {"yes" if found.above_degree else "no"}.')
        self.stdout.write(self.style.SUCCESS(f'Report: {path}'))
