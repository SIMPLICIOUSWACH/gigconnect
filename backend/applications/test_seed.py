from datetime import date, timedelta
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from accounts.models import User
from gigs.models import Category, Gig, GigInteraction

from .models import Application
from .transitions import Status, can_transition


def run(*args):
    out = StringIO()
    call_command('seed_applications', *args, stdout=out)
    return out.getvalue()


@override_settings(DEBUG=True)  # the test runner forces DEBUG off, and the command refuses to run then
class SeedApplicationsTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Seed Test Category')
        self.client_user = User.objects.create_user(
            email='seed-client-1@example.test', password='x-Seed-pass-1', full_name='Seed Client',
            phone='254700000401', role='client', is_synthetic=True,
        )
        self.freelancers = [
            User.objects.create_user(
                email=f'seed-freelancer-{n}@example.test', password='x-Seed-pass-1', full_name=f'Seed Freelancer {n}',
                phone=f'25470000041{n}', role='freelancer', is_synthetic=True,
            )
            for n in range(1, 6)
        ]
        self.gigs = [
            Gig.objects.create(
                client=self.client_user, category=category, title=f'Seeded gig {n}', description='Sample.',
                budget_min=2000, budget_max=5000, deadline=date.today() + timedelta(days=30), is_synthetic=True,
            )
            for n in range(4)
        ]

    def test_refuses_to_run_when_debug_is_off(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            run('--count', '5')
        self.assertEqual(Application.objects.count(), 0)

    def test_needs_the_seed_accounts_and_gigs(self):
        Gig.objects.all().delete()
        with self.assertRaises(CommandError):
            run()

    def test_creates_applications_marked_synthetic(self):
        run('--count', '10')
        self.assertEqual(Application.objects.count(), 10)
        self.assertFalse(Application.objects.filter(is_synthetic=False).exists())

    def test_never_creates_a_duplicate_pair_and_stops_when_pairs_run_out(self):
        output = run('--count', '1000')
        self.assertEqual(Application.objects.count(), len(self.gigs) * len(self.freelancers))
        self.assertIn('Stopped early', output)

    def follow_the_chain(self, application):
        """The events in the order they happened, found by following from_status to to_status.

        Sorting by time is not reliable here: on Windows two events created back to back can share
        a timestamp. A status is never visited twice, so each from_status appears once.
        """
        events = list(application.events.all())
        by_from = {event.from_status: event for event in events}
        self.assertEqual(len(by_from), len(events), 'a status was left twice')
        chain = []
        current = by_from.get('')
        while current is not None:
            chain.append(current)
            current = by_from.get(current.to_status)
        self.assertEqual(len(chain), len(events), 'the history is not one unbroken chain')
        return chain

    def test_every_application_has_a_history_that_follows_the_rules(self):
        run('--count', '20')
        for application in Application.objects.prefetch_related('events'):
            events = self.follow_the_chain(application)
            self.assertEqual((events[0].from_status, events[0].to_status), ('', Status.PENDING))
            self.assertEqual(events[-1].to_status, application.status)
            for earlier, later in zip(events, events[1:]):
                self.assertEqual(later.from_status, earlier.to_status)
                self.assertTrue(
                    can_transition(later.from_status, later.to_status, 'client')
                    or can_transition(later.from_status, later.to_status, 'freelancer')
                )

    def test_at_most_one_hire_per_gig_and_a_hire_moves_the_gig_on(self):
        run('--count', '20')
        for gig in Gig.objects.all():
            hired = Application.objects.filter(gig=gig, status=Status.HIRED).count()
            self.assertLessEqual(hired, 1)
            if hired:
                self.assertEqual(gig.status, Gig.Status.IN_PROGRESS)

    def test_logs_a_synthetic_apply_interaction_for_each_application(self):
        run('--count', '8')
        interactions = GigInteraction.objects.filter(type=GigInteraction.Type.APPLY)
        self.assertEqual(interactions.count(), 8)
        self.assertFalse(interactions.filter(is_synthetic=False).exists())

    def test_text_is_clearly_sample_data_and_valid_length(self):
        run('--count', '5')
        for application in Application.objects.all():
            self.assertIn('sample seed data', application.cover_letter)
            self.assertGreaterEqual(len(application.cover_letter), 50)

    def test_delete_removes_only_the_seeded_applications(self):
        real_user = User.objects.create_user(
            email='real-freelancer@example.com', password='x-Real-pass-1', full_name='Real',
            phone='254700000499', role='freelancer',
        )
        real = Application.objects.create(gig=self.gigs[0], freelancer=real_user, cover_letter='x' * 60)
        run('--count', '15')
        run('--delete')
        self.assertEqual(list(Application.objects.all()), [real])
        self.assertEqual(GigInteraction.objects.filter(type=GigInteraction.Type.APPLY).count(), 0)

    def test_delete_reopens_gigs_that_a_seeded_hire_moved_on(self):
        run('--count', '20')
        run('--delete')
        self.assertFalse(Gig.objects.filter(status=Gig.Status.IN_PROGRESS).exists())

    def test_delete_refuses_when_debug_is_off(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            run('--delete')
