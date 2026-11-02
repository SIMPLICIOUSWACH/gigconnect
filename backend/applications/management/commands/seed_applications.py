import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from gigs.models import Gig, GigInteraction
from gigs.seed_helpers import application_window_end, ordered_by_preference, skill_ids_by_gig

from ...models import Application, ApplicationStatusEvent
from ...transitions import Actor, Status

# How an application got to its final status, as the steps a client or freelancer would have taken.
# Every step goes through Application.change_status, so the seeded history follows the real rules.
PATHS = {
    Status.PENDING: [],
    Status.UNDER_REVIEW: [Status.UNDER_REVIEW],
    Status.SHORTLISTED: [Status.UNDER_REVIEW, Status.SHORTLISTED],
    Status.HIRED: [Status.UNDER_REVIEW, Status.SHORTLISTED, Status.HIRED],
    Status.REJECTED: [Status.UNDER_REVIEW, Status.REJECTED],
    Status.WITHDRAWN: [Status.WITHDRAWN],
}

# Roughly what a real board looks like: most applications are still waiting, few lead to a hire.
STATUS_WEIGHTS = [
    (Status.PENDING, 40),
    (Status.UNDER_REVIEW, 20),
    (Status.SHORTLISTED, 12),
    (Status.HIRED, 5),
    (Status.REJECTED, 15),
    (Status.WITHDRAWN, 8),
]

COVER_LETTERS = [
    'I have worked on similar projects before and can start straight away. '
    'This is sample seed data, not a real application.',
    'I am confident I can deliver this within your timeline and budget. '
    'This is sample seed data, not a real application.',
    'My experience matches what you are asking for, and I am happy to share examples of my work. '
    'This is sample seed data, not a real application.',
    'I would enjoy working on this and can answer any questions you have before we begin. '
    'This is sample seed data, not a real application.',
]

SPREAD_DAYS = 30  # applications are dated within the last month, inside each gig's application window
MAX_STEP_HOURS = 72  # the longest wait between two status changes
SPREAD_OF_TARGET = 5  # each freelancer makes the target number of applications, give or take this many


class Command(BaseCommand):
    help = (
        'Seed realistic, clearly-fake applications on seeded open gigs, in a mix of statuses with matching '
        'status history. Seeded freelancers favour gigs that share a skill with them (about five times more '
        'likely), which is made-up behaviour that gives the recommender a pattern to find and favours the '
        'content model by construction. Dates are never before the gig existed. Development only. Every row is '
        'marked is_synthetic. Needs the seed accounts and gigs (run seed_data and seed_gigs first).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--per-freelancer', type=int, default=20,
            help='About how many applications each seed freelancer makes, 5 more or fewer (default 20).',
        )
        parser.add_argument('--count', type=int, help='Stop after this many applications in total (default: no limit).')
        parser.add_argument('--seed', type=int, default=42, help='Random seed, so a rerun gives the same rows.')
        parser.add_argument(
            '--delete', action='store_true',
            help='Delete all previously seeded applications instead of creating any.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_applications refuses to run when DEBUG is False.')

        if options['delete']:
            self._delete()
            return

        freelancers = list(
            User.objects.filter(email__startswith='seed-freelancer-', role=User.Role.FREELANCER)
            .select_related('freelancer_profile').prefetch_related('freelancer_profile__skills')
            .order_by('email')
        )
        gigs = list(
            Gig.objects.filter(is_synthetic=True, status=Gig.Status.OPEN, client__email__startswith='seed-client-')
            .select_related('client').prefetch_related('skills')
        )
        if not freelancers or not gigs:
            raise CommandError('No seed freelancers or open seeded gigs found. Run seed_data and seed_gigs first.')

        wanted = options['count']
        statuses = [status for status, _ in STATUS_WEIGHTS]
        status_shares = [share for _, share in STATUS_WEIGHTS]
        gig_skills = skill_ids_by_gig(gigs)
        taken = set(Application.objects.values_list('gig_id', 'freelancer_id'))
        hired_gigs = set(Application.objects.filter(status=Status.HIRED).values_list('gig_id', flat=True))
        target = options['per_freelancer']

        created = 0
        for user in freelancers:
            if wanted is not None and created >= wanted:
                break
            # Each freelancer has their own random stream, from the seed and their id, so what one freelancer
            # does does not depend on anyone else, and a rerun only fills in what is missing.
            rng = random.Random(f'{options["seed"]}-{user.id}')
            own_skills = {skill.id for skill in user.freelancer_profile.skills.all()}
            goal = rng.randint(max(1, target - SPREAD_OF_TARGET), target + SPREAD_OF_TARGET)
            # The first `goal` gigs in this freelancer's order of preference. Gigs they already applied to are
            # skipped and not replaced, so running again adds nothing that is already there.
            for gig in ordered_by_preference(rng, gigs, gig_skills, own_skills)[:goal]:
                if wanted is not None and created >= wanted:
                    break
                if (gig.id, user.id) in taken:
                    continue
                status = rng.choices(statuses, weights=status_shares)[0]
                if status == Status.HIRED and gig.id in hired_gigs:
                    status = Status.SHORTLISTED  # a gig can only have one hire
                taken.add((gig.id, user.id))

                with transaction.atomic():
                    self._create(gig, user, status, rng)
                if status == Status.HIRED:
                    hired_gigs.add(gig.id)
                created += 1

        self.stdout.write(self.style.SUCCESS(f'Created {created} seeded application(s).'))
        if wanted is not None and created < wanted:
            self.stdout.write(f'Stopped early: only {created} unused gig and freelancer pairs were found.')

    def _create(self, gig, freelancer, status, rng):
        has_rate = rng.random() < 0.6
        application = Application.objects.create(
            gig=gig,
            freelancer=freelancer,
            cover_letter=rng.choice(COVER_LETTERS),
            portfolio_link=f'https://portfolio.example.test/{freelancer.id}' if rng.random() < 0.5 else '',
            proposed_rate=rng.randrange(
                int(gig.budget_min), int(gig.budget_max) + 1, 500
            ) if has_rate else None,
            is_synthetic=True,
        )
        ApplicationStatusEvent.objects.create(
            application=application, from_status='', to_status=Status.PENDING, changed_by=freelancer,
        )
        for step in PATHS[status]:
            if step == Status.WITHDRAWN:
                application.change_status(step, actor=Actor.FREELANCER, changed_by=freelancer)
            else:
                application.change_status(step, actor=Actor.CLIENT, changed_by=gig.client)

        if status == Status.HIRED:
            Gig.objects.filter(pk=gig.pk, status=Gig.Status.OPEN).update(status=Gig.Status.IN_PROGRESS)

        # Real apply flow logs this for the recommender, so a seeded application does too, flagged synthetic.
        interaction = GigInteraction.objects.create(
            gig=gig, user=freelancer, type=GigInteraction.Type.APPLY, is_synthetic=True,
        )
        self._date(application, interaction, gig, rng)

    def _date(self, application, interaction, gig, rng):
        """
        Give the application, its apply interaction and each status change believable times. The application is
        dated inside the gig's application window: after the gig was posted, no later than the end of its
        application deadline day and never in the future, and within the last month where that allows. Each later
        status comes a few hours to a few days after the one before, never in the future.
        """
        now = timezone.now()
        latest = application_window_end(gig, now)
        earliest = max(gig.created_at, now - timedelta(days=SPREAD_DAYS))
        if earliest > latest:  # the window closed more than a month ago: use all of it
            earliest = gig.created_at
        applied_at = earliest + (latest - earliest) * rng.random()

        # The events in the order they happened, found by following from_status to to_status, because
        # two events made back to back can share a timestamp.
        by_from = {event.from_status: event for event in application.events.all()}
        events, current = [], by_from.get('')
        while current is not None:
            events.append(current)
            current = by_from.get(current.to_status)

        moment = applied_at
        for index, event in enumerate(events):
            if index > 0:
                moment = min(moment + timedelta(hours=rng.randint(1, MAX_STEP_HOURS)), now)
            type(event).objects.filter(pk=event.pk).update(created_at=moment)
        Application.objects.filter(pk=application.pk).update(created_at=applied_at, updated_at=moment)
        GigInteraction.objects.filter(pk=interaction.pk).update(created_at=applied_at)

    def _delete(self):
        # A seeded hire moved its gig to in_progress; put those gigs back to open so the seed can run again.
        hired_gig_ids = list(
            Application.objects.filter(is_synthetic=True, status=Status.HIRED).values_list('gig_id', flat=True)
        )
        deleted, _ = Application.objects.filter(is_synthetic=True).delete()
        Gig.objects.filter(
            pk__in=hired_gig_ids, is_synthetic=True, status=Gig.Status.IN_PROGRESS,
        ).update(status=Gig.Status.OPEN, updated_at=timezone.now())
        GigInteraction.objects.filter(type=GigInteraction.Type.APPLY, is_synthetic=True).delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} seeded row(s) (applications + their history).'))
