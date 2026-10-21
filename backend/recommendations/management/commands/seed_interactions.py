import random
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from accounts.models import User
from gigs.models import Gig, GigInteraction

# How the seeded interactions are split. Applications are not made here: seed_applications does that,
# together with the matching `apply` interaction.
TYPES = [
    (GigInteraction.Type.VIEW, 60),
    (GigInteraction.Type.SEARCH_CLICK, 20),
    (GigInteraction.Type.SAVE, 12),
    (GigInteraction.Type.RECOMMENDATION_CLICK, 8),
]
CLICK_TYPES = {GigInteraction.Type.SEARCH_CLICK, GigInteraction.Type.RECOMMENDATION_CLICK}

# A gig that shares a skill with the freelancer is this many times more likely to be picked than one that
# does not, so freelancers with similar skills end up with similar histories. That is the pattern the
# collaborative model looks for. It is made-up sample behaviour, not evidence about real freelancers.
SKILL_PREFERENCE = 5
SPREAD_DAYS = 30


class Command(BaseCommand):
    help = (
        'Seed clearly-fake interactions (views, search clicks, saves and recommendation clicks) from the '
        'seed freelancers on the seeded gigs, mostly on gigs that share their skills, so the collaborative '
        'model has something to learn from. Development only. Every row is marked is_synthetic. Needs the '
        'seed accounts and gigs (run seed_data and seed_gigs first).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--per-freelancer', type=int, default=25,
            help='Different gigs each seed freelancer interacts with (default 25).',
        )
        parser.add_argument('--seed', type=int, default=42, help='Random seed, so a rerun gives the same rows.')
        parser.add_argument(
            '--delete', action='store_true',
            help='Delete the seeded interactions instead of creating any. Seeded apply rows belong to '
                 'seed_applications and are left alone.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_interactions refuses to run when DEBUG is False.')

        if options['delete']:
            deleted, _ = (
                GigInteraction.objects.filter(is_synthetic=True).exclude(type=GigInteraction.Type.APPLY).delete()
            )
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} seeded interaction(s).'))
            return

        freelancers = list(
            User.objects.filter(email__startswith='seed-freelancer-', role=User.Role.FREELANCER)
            .select_related('freelancer_profile').prefetch_related('freelancer_profile__skills')
        )
        gigs = list(
            Gig.objects.filter(is_synthetic=True, client__email__startswith='seed-client-').prefetch_related('skills')
        )
        if not freelancers or not gigs:
            raise CommandError('No seed freelancers or seeded gigs found. Run seed_data and seed_gigs first.')

        already = set(
            GigInteraction.objects.filter(is_synthetic=True, user__in=freelancers).values_list('user_id', 'gig_id')
        )
        gig_skills = {gig.id: {skill.id for skill in gig.skills.all()} for gig in gigs}
        kinds = [kind for kind, _ in TYPES]
        shares = [share for _, share in TYPES]

        rows, days_by_id = [], {}
        for user in freelancers:
            # Each freelancer has their own random stream, from the seed and their id. Their choices then do
            # not depend on anyone else's, so a rerun picks the same gigs and only fills in what is missing.
            rng = random.Random(f'{options["seed"]}-{user.id}')
            own = {skill.id for skill in user.freelancer_profile.skills.all()}
            for gig in self._pick(rng, gigs, gig_skills, own, options['per_freelancer']):
                if (user.id, gig.id) in already:
                    continue
                kind = rng.choices(kinds, weights=shares)[0]
                row = GigInteraction(
                    user=user, gig=gig, type=kind, is_synthetic=True,
                    position=rng.randint(1, 10) if kind in CLICK_TYPES else None,
                )
                rows.append(row)
                days_by_id[row.id] = rng.randint(0, SPREAD_DAYS - 1)
        GigInteraction.objects.bulk_create(rows)
        self._spread_over_days(days_by_id)
        self.stdout.write(self.style.SUCCESS(
            f'Created {len(rows)} seeded interaction(s) for {len(freelancers)} freelancer(s) on {len(gigs)} gig(s).'
        ))

    def _pick(self, rng, gigs, gig_skills, own_skills, count):
        """
        Choose `count` different gigs, favouring those that share a skill. This is weighted sampling without
        replacement: each gig gets a random key raised to the power 1 / weight, and the largest keys win.
        """
        keyed = []
        for gig in gigs:
            weight = SKILL_PREFERENCE if own_skills & gig_skills[gig.id] else 1
            keyed.append((rng.random() ** (1 / weight), str(gig.id), gig))
        keyed.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [gig for _, _, gig in keyed[:count]]

    def _spread_over_days(self, days_by_id):
        """Make the interactions look like they happened over the last month, not all just now."""
        by_day = defaultdict(list)
        for interaction_id, days in days_by_id.items():
            by_day[days].append(interaction_id)
        for days, ids in by_day.items():
            GigInteraction.objects.filter(pk__in=ids).update(created_at=F('created_at') - timedelta(days=days))
