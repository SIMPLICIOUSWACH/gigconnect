import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import User
from gigs.models import Gig, GigInteraction

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


class Command(BaseCommand):
    help = (
        'Seed realistic, clearly-fake applications on seeded open gigs, in a mix of statuses with '
        'matching status history. Development only. Every row is marked is_synthetic. '
        'Needs the seed accounts and gigs (run seed_data and seed_gigs first).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=150, help='Number of applications to create (default 150).')
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

        freelancers = list(User.objects.filter(email__startswith='seed-freelancer-', role=User.Role.FREELANCER))
        gigs = list(
            Gig.objects.filter(is_synthetic=True, status=Gig.Status.OPEN, client__email__startswith='seed-client-')
            .select_related('client')
        )
        if not freelancers or not gigs:
            raise CommandError('No seed freelancers or open seeded gigs found. Run seed_data and seed_gigs first.')

        wanted = options['count']
        statuses = [status for status, _ in STATUS_WEIGHTS]
        weights = [weight for _, weight in STATUS_WEIGHTS]
        taken = set(Application.objects.values_list('gig_id', 'freelancer_id'))
        hired_gigs = set(Application.objects.filter(status=Status.HIRED).values_list('gig_id', flat=True))

        created = 0
        attempts = 0
        while created < wanted and attempts < wanted * 10:
            attempts += 1
            gig = random.choice(gigs)
            freelancer = random.choice(freelancers)
            if (gig.id, freelancer.id) in taken:
                continue
            status = random.choices(statuses, weights=weights)[0]
            if status == Status.HIRED and gig.id in hired_gigs:
                status = Status.SHORTLISTED  # a gig can only have one hire
            taken.add((gig.id, freelancer.id))

            with transaction.atomic():
                self._create(gig, freelancer, status)
            if status == Status.HIRED:
                hired_gigs.add(gig.id)
            created += 1

        self.stdout.write(self.style.SUCCESS(f'Created {created} seeded application(s).'))
        if created < wanted:
            self.stdout.write(f'Stopped early: only {created} unused gig and freelancer pairs were found.')

    def _create(self, gig, freelancer, status):
        has_rate = random.random() < 0.6
        application = Application.objects.create(
            gig=gig,
            freelancer=freelancer,
            cover_letter=random.choice(COVER_LETTERS),
            portfolio_link=f'https://portfolio.example.test/{freelancer.id}' if random.random() < 0.5 else '',
            proposed_rate=random.randrange(
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
        GigInteraction.objects.create(
            gig=gig, user=freelancer, type=GigInteraction.Type.APPLY, is_synthetic=True,
        )

        # Spread the applications over the last month so dates and ordering look natural.
        shift = timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
        Application.objects.filter(pk=application.pk).update(
            created_at=F('created_at') - shift, updated_at=F('updated_at') - shift,
        )
        ApplicationStatusEvent.objects.filter(application=application).update(created_at=F('created_at') - shift)

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
