from argparse import BooleanOptionalAction
from statistics import median

from django.conf import settings
from django.core.management.base import BaseCommand

from ...evaluation import split as ev
from ...evaluation.candidates import candidates_for, load_gig_records


class Command(BaseCommand):
    help = (
        'Build the 70/15/15 evaluation split, per freelancer by time, from the applications of active '
        'freelancers, and save it to datasets/platform/evaluation/. A saved split is loaded again on later runs '
        'so results stay comparable, unless --rebuild-split is given. Then print what is in it. Nothing is '
        'trained or scored here.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-synthetic', action=BooleanOptionalAction, default=None,
            help='Use the synthetic seed rows (default: the RECOMMENDER_INCLUDE_SYNTHETIC setting).',
        )
        parser.add_argument('--seed', type=int, default=42, help='Seed for the order of positives at the same moment.')
        parser.add_argument(
            '--rebuild-split', action='store_true', help='Build a new split instead of loading the saved one.',
        )

    def handle(self, *args, **options):
        include_synthetic = options['include_synthetic']
        if include_synthetic is None:
            include_synthetic = settings.RECOMMENDER_INCLUDE_SYNTHETIC
        split, how, note = ev.load_or_build(
            include_synthetic=include_synthetic, seed=options['seed'], rebuild=options['rebuild_split'],
        )
        if note:
            self.stdout.write(self.style.WARNING(note))
        self.stdout.write(f'Split {how}. Saved in {ev.default_directory()}. Fingerprint {split.fingerprint()}.')
        self.stdout.write(f'Seed {split.seed}. Synthetic data {"included" if split.include_synthetic else "left out"}.')

        counts = ev.describe(split)
        self.stdout.write('')
        self.stdout.write(f'{"Part":<12}{"Freelancers":>12}{"Positives":>11}{"Synthetic":>11}{"Strictly relevant":>19}')
        for part in (ev.TRAIN, ev.VALIDATION, ev.TEST):
            c = counts[part]
            self.stdout.write(
                f'{part:<12}{c["freelancers"]:>12}{c["positives"]:>11}{c["synthetic"]:>11}{c["strictly_relevant"]:>19}'
            )
        self.stdout.write('')
        self.stdout.write(
            f'{counts["evaluated_freelancers"]} freelancer(s) can be evaluated '
            f'(at least {split.min_positives} positives). {counts["too_few_freelancers"]} have fewer and stay in '
            f'train only ({counts["too_few_positives"]} positives).'
        )
        self._candidate_summary(split, include_synthetic)

    def _candidate_summary(self, split, include_synthetic):
        gigs = load_gig_records(include_synthetic)
        for part in (ev.VALIDATION, ev.TEST):
            sizes, outside = [], 0
            for freelancer_id in split.evaluated_freelancers():
                found, not_passing = candidates_for(split, freelancer_id, part, gigs)
                sizes.append(len(found))
                outside += len(not_passing)
            if sizes:
                self.stdout.write(
                    f'{part}: candidate gigs per freelancer, median {median(sizes):.0f} '
                    f'(smallest {min(sizes)}, largest {max(sizes)}); {outside} positive(s) outside the as-of rules.'
                )
