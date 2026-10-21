from datetime import date, datetime, time, timedelta
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from gigs.models import Category, Gig, GigInteraction
from profiles.models import Skill

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


@override_settings(DEBUG=True)
class SeedApplicationsSkillAndDateTests(TestCase):
    """12 seed freelancers in two skill groups and 30 open seeded gigs, half asking for each group's skills."""

    def setUp(self):
        category = Category.objects.create(name='Seed Skill Category')
        self.skills = {
            'P': Skill.objects.create(name='Seedapp Py', category='Test'),
            'X': Skill.objects.create(name='Seedapp Xl', category='Test'),
        }
        self.client_user = User.objects.create_user(
            email='seed-client-1@example.test', password='x-Seed-pass-1', full_name='Seed Client',
            phone='254700000601', role='client', is_synthetic=True,
        )
        self.freelancers = []
        for number in range(1, 13):
            user = User.objects.create_user(
                email=f'seed-freelancer-{number}@example.test', password='x-Seed-pass-1',
                full_name=f'Seed Freelancer {number}', phone=f'254700006{number:02d}', role='freelancer',
                is_synthetic=True,
            )
            user.freelancer_profile.skills.set([self.skills['P' if number <= 6 else 'X']])
            self.freelancers.append(user)
        self.gigs = []
        for number in range(30):
            gig = Gig.objects.create(
                client=self.client_user, category=category, title=f'Seed skill gig {number}', description='Sample.',
                budget_min=2000, budget_max=5000, deadline=date.today() + timedelta(days=30), is_synthetic=True,
            )
            gig.skills.set([self.skills['P' if number < 15 else 'X']])
            self.gigs.append(gig)
        self.group_p_gigs = {gig.id for gig in self.gigs[:15]}
        Gig.objects.update(created_at=timezone.now() - timedelta(days=40))

    def ordered_events(self, application):
        """The events in the order they happened, found by following from_status to to_status."""
        by_from = {event.from_status: event for event in application.events.all()}
        events, current = [], by_from.get('')
        while current is not None:
            events.append(current)
            current = by_from.get(current.to_status)
        return events

    def test_freelancers_favour_gigs_that_share_their_skills(self):
        run('--per-freelancer', '10')
        shares = []
        for number, user in enumerate(self.freelancers, start=1):
            gigs = set(Application.objects.filter(freelancer=user).values_list('gig_id', flat=True))
            own = gigs & self.group_p_gigs if number <= 6 else gigs - self.group_p_gigs
            shares.append(len(own) / len(gigs))
        # Half the gigs share each freelancer's skill, so random picks would give about 0.5. A weight of 5 to 1 is
        # a strong lean and not an absolute rule, so the share is about 0.79, not 1, and varies a little because the
        # ids are random. 0.62 is far from chance and was never reached in 20,000 trials.
        self.assertGreater(sum(shares) / len(shares), 0.62)

    def test_each_freelancer_makes_about_the_requested_number_of_applications(self):
        run('--per-freelancer', '10')
        for user in self.freelancers:
            self.assertTrue(5 <= Application.objects.filter(freelancer=user).count() <= 15)

    def test_the_default_is_about_twenty_each(self):
        run()
        counts = [Application.objects.filter(freelancer=user).count() for user in self.freelancers]
        self.assertTrue(all(15 <= count <= 25 for count in counts), counts)

    def test_the_count_option_is_a_total_cap(self):
        run('--per-freelancer', '10', '--count', '23')
        self.assertEqual(Application.objects.count(), 23)

    def test_no_application_is_dated_before_its_gig_existed(self):
        Gig.objects.update(created_at=timezone.now() - timedelta(days=4))
        run('--per-freelancer', '10')
        for application in Application.objects.select_related('gig'):
            self.assertGreaterEqual(application.created_at, application.gig.created_at)

    def close_half_the_gigs_early(self):
        """Half the gigs closed to applications 25 days ago, a few closed a few days ago, the rest are open."""
        for index, gig in enumerate(self.gigs):
            days_ahead = (-25, -3, 20)[index % 3]
            Gig.objects.filter(pk=gig.pk).update(application_deadline=date.today() + timedelta(days=days_ahead))

    def end_of_deadline_day(self, gig):
        return timezone.make_aware(datetime.combine(gig.application_deadline + timedelta(days=1), time.min))

    def test_no_application_is_dated_after_its_gigs_application_deadline(self):
        self.close_half_the_gigs_early()
        run()
        self.assertGreater(Application.objects.count(), 100)
        for application in Application.objects.select_related('gig'):
            gig = Gig.objects.get(pk=application.gig_id)
            self.assertLess(application.created_at, self.end_of_deadline_day(gig), gig.application_deadline)
            self.assertGreaterEqual(application.created_at, gig.created_at)
            self.assertLessEqual(application.created_at, timezone.now())

    def test_a_gig_that_closed_over_a_month_ago_still_gets_applications_inside_its_window(self):
        Gig.objects.update(created_at=timezone.now() - timedelta(days=50))
        Gig.objects.update(application_deadline=date.today() - timedelta(days=35))
        run('--per-freelancer', '10')
        self.assertGreater(Application.objects.count(), 50)
        for application in Application.objects.select_related('gig'):
            gig = Gig.objects.get(pk=application.gig_id)
            self.assertGreaterEqual(application.created_at, gig.created_at)
            self.assertLess(application.created_at, self.end_of_deadline_day(gig))

    def test_status_changes_may_come_after_the_deadline_because_the_client_acts_later(self):
        self.close_half_the_gigs_early()
        run()
        later = 0
        for application in Application.objects.prefetch_related('events').select_related('gig'):
            gig = Gig.objects.get(pk=application.gig_id)
            for event in application.events.all():
                later += event.created_at >= self.end_of_deadline_day(gig)
        self.assertGreater(later, 0)  # reviewing and hiring happen after applications close

    def test_applications_are_spread_over_the_month(self):
        run()
        days = {(timezone.now() - a.created_at).days for a in Application.objects.all()}
        self.assertGreater(len(days), 15)
        self.assertLessEqual(max(days), 30)

    def test_the_apply_interaction_has_the_same_time_as_its_application(self):
        run('--per-freelancer', '5')
        for application in Application.objects.all():
            interaction = GigInteraction.objects.get(
                user=application.freelancer, gig=application.gig, type=GigInteraction.Type.APPLY,
            )
            self.assertEqual(interaction.created_at, application.created_at)

    def test_each_status_change_happens_after_the_one_before_and_never_in_the_future(self):
        run()
        now = timezone.now()
        later_steps = 0
        for application in Application.objects.prefetch_related('events'):
            events = self.ordered_events(application)
            self.assertEqual(events[0].created_at, application.created_at)
            for earlier, later in zip(events, events[1:]):
                self.assertGreaterEqual(later.created_at, earlier.created_at)
                later_steps += 1
            self.assertLessEqual(events[-1].created_at, now)
            self.assertEqual(application.updated_at, events[-1].created_at)
        self.assertGreater(later_steps, 50)  # plenty of applications went on to have later steps

    def test_a_later_status_comes_hours_or_days_after_the_one_before_not_at_the_same_moment(self):
        run()
        gaps = []
        for application in Application.objects.prefetch_related('events'):
            events = self.ordered_events(application)
            gaps += [later.created_at - earlier.created_at for earlier, later in zip(events, events[1:])]
        long_enough = sum(1 for gap in gaps if gap >= timedelta(hours=1))
        self.assertGreater(len(gaps), 50)
        self.assertGreater(long_enough / len(gaps), 0.8)  # only a step clamped at "now" can be shorter

    def test_running_again_never_repeats_a_pair_or_loses_one(self):
        # A seeded hire moves its gig to in progress, so a second run can have fewer open gigs to choose from
        # and make different picks, and may add more. If nothing was hired it adds nothing. Either way no pair
        # is repeated and none is lost. Use --delete to start over.
        run('--per-freelancer', '8')
        first = set(Application.objects.values_list('freelancer_id', 'gig_id'))
        run('--per-freelancer', '8')
        pairs = list(Application.objects.values_list('freelancer_id', 'gig_id'))
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertTrue(first <= set(pairs))

    def test_the_same_seed_gives_the_same_applications_after_deleting(self):
        run('--per-freelancer', '8', '--seed', '3')
        first = set(Application.objects.values_list('freelancer_id', 'gig_id', 'status'))
        run('--delete')
        run('--per-freelancer', '8', '--seed', '3')
        self.assertEqual(set(Application.objects.values_list('freelancer_id', 'gig_id', 'status')), first)

    def test_at_most_one_hire_per_gig_with_many_applications(self):
        run('--per-freelancer', '25')
        for gig in Gig.objects.all():
            self.assertLessEqual(Application.objects.filter(gig=gig, status=Status.HIRED).count(), 1)
