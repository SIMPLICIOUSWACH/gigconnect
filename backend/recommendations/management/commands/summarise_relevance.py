from argparse import BooleanOptionalAction

from django.core.management.base import BaseCommand

from gigs.models import GigInteraction

RELEVANT = GigInteraction.Type.RECOMMENDATION_RELEVANT


def summarise(answers):
    """
    Counts from (type, position, gig id, freelancer id) rows, one per freelancer and gig. Positions are 1-based places
    in the "Recommended for You" list when the gig was rated, or None.
    """
    answers = list(answers)
    within = {}
    for k in (5, 10):
        rated = [kind for kind, position, _, _ in answers if position is not None and position <= k]
        within[k] = (sum(1 for kind in rated if kind == RELEVANT), len(rated))
    per_gig = {}
    for kind, _, gig_id, _ in answers:
        relevant, not_relevant = per_gig.get(gig_id, (0, 0))
        per_gig[gig_id] = (relevant + 1, not_relevant) if kind == RELEVANT else (relevant, not_relevant + 1)
    return {
        'answers': len(answers),
        'freelancers': len({freelancer for _, _, _, freelancer in answers}),
        'relevant': sum(1 for kind, _, _, _ in answers if kind == RELEVANT),
        'no_position': sum(1 for _, position, _, _ in answers if position is None),
        'within': within,
        'per_gig': per_gig,
    }


class Command(BaseCommand):
    help = (
        'Summarise the answers to "Is this gig relevant to you?" on recommended gigs: counts overall and per gig, and '
        'how many were rated relevant out of those rated within the top 5 and the top 10. Counts only. Answers from '
        'synthetic accounts are left out unless --include-synthetic is given, because test participants are real.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-synthetic', action=BooleanOptionalAction, default=False,
            help='Count answers from synthetic (seed or planted) accounts too (default: left out).',
        )

    def handle(self, *args, **options):
        rows = GigInteraction.objects.filter(type__in=GigInteraction.RELEVANCE_TYPES, user__isnull=False)
        if not options['include_synthetic']:
            rows = rows.filter(is_synthetic=False, user__is_synthetic=False)
        found = summarise(rows.values_list('type', 'position', 'gig_id', 'user_id'))
        titles = dict(rows.values_list('gig_id', 'gig__title'))

        self.stdout.write(
            f'Answers: {found["answers"]} from {found["freelancers"]} freelancer(s). '
            f'Rated relevant: {found["relevant"]} of {found["answers"]}.'
        )
        for k in (5, 10):
            relevant, rated = found['within'][k]
            self.stdout.write(f'Within the top {k}: {relevant} rated relevant out of {rated} rated.')
        if found['no_position']:
            self.stdout.write(f'Answers with no position, counted overall only: {found["no_position"]}.')
        if found['per_gig']:
            self.stdout.write('')
            self.stdout.write('Relevant  Not relevant  Gig')
            ordered = sorted(found['per_gig'].items(), key=lambda item: (-sum(item[1]), titles.get(item[0], '')))
            for gig_id, (relevant, not_relevant) in ordered:
                self.stdout.write(f'{relevant:>8}  {not_relevant:>12}  {titles.get(gig_id, gig_id)}')
