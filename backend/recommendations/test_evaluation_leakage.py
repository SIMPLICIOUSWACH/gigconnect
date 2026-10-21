import random
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone

from django.test import SimpleTestCase, TestCase

from accounts.models import User
from applications.models import Application, ApplicationStatusEvent
from gigs.models import Category, Gig, GigInteraction

from . import collaborative
from .evaluation import split as ev
from .evaluation.training_input import status_as_of, training_input, vectoriser_gig_ids

START = datetime(2026, 10, 1, 12, 0, tzinfo=dt_timezone.utc)


def day(n):
    return START + timedelta(days=n)


class StatusAsOfTests(SimpleTestCase):
    EVENTS = [(day(2), 'pending'), (day(4), 'under_review'), (day(7), 'shortlisted'), (day(9), 'hired')]

    def test_with_no_events_it_falls_back_to_the_final_status(self):
        self.assertEqual(status_as_of([], day(5), 'hired'), 'hired')

    def test_before_the_first_event_it_is_pending(self):
        self.assertEqual(status_as_of(self.EVENTS, day(1), 'hired'), 'pending')

    def test_it_is_the_last_status_on_or_before_the_moment(self):
        self.assertEqual(status_as_of(self.EVENTS, day(5), 'hired'), 'under_review')
        self.assertEqual(status_as_of(self.EVENTS, day(8), 'hired'), 'shortlisted')

    def test_a_change_at_exactly_the_moment_counts(self):
        self.assertEqual(status_as_of(self.EVENTS, day(7), 'hired'), 'shortlisted')

    def test_after_the_last_event_it_is_the_final_status(self):
        self.assertEqual(status_as_of(self.EVENTS, day(30), 'hired'), 'hired')

    def test_the_order_the_events_are_given_in_does_not_matter(self):
        self.assertEqual(status_as_of(list(reversed(self.EVENTS)), day(5), 'hired'), 'under_review')


class LeakageBase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Leakage Test Category')
        self.client_user = self.make_user('leak-client@example.com', 'client')
        self.gigs = {n: self.make_gig(f'Leak gig {n}') for n in range(1, 13)}
        Gig.objects.update(created_at=day(-30))

    def make_user(self, email, role, **extra):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password='x-Leak-pass-1', full_name=email.split('@')[0],
            phone=f'2547000092{number:02d}', role=role, **extra,
        )

    def make_gig(self, title):
        return Gig.objects.create(
            client=self.client_user, category=self.category, title=title, description='A gig.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=60),
        )

    def apply(self, user, gig_number, days, final_status='pending', events=()):
        """An application made on a given day, with its status changes on given days."""
        application = Application.objects.create(
            gig=self.gigs[gig_number], freelancer=user, cover_letter='x' * 60, status=final_status,
        )
        Application.objects.filter(pk=application.pk).update(created_at=day(days))
        previous = ''
        for when, status in events:
            event = ApplicationStatusEvent.objects.create(
                application=application, from_status=previous, to_status=status, changed_by=user,
            )
            ApplicationStatusEvent.objects.filter(pk=event.pk).update(created_at=day(when))
            previous = status
        interaction = GigInteraction.objects.create(gig=self.gigs[gig_number], user=user, type='apply')
        GigInteraction.objects.filter(pk=interaction.pk).update(created_at=day(days))
        return application

    def interact(self, user, gig_number, kind, days):
        row = GigInteraction.objects.create(gig=self.gigs[gig_number], user=user, type=kind)
        GigInteraction.objects.filter(pk=row.pk).update(created_at=day(days))

    def make_split(self):
        return ev.build_split(ev.load_positives())


class HandWorkedScenarioTests(LeakageBase):
    """
    Freelancer A applies to gigs 1 to 10 on days 1 to 10: train is gigs 1 to 6, validation 7 and 8, test 9 and 10,
    and the cut-off is day 6. Freelancer B has only 3 applications, so is all train and has no cut-off.
    """

    def setUp(self):
        super().setUp()
        self.a = self.make_user('leak-a@example.com', 'freelancer')
        self.b = self.make_user('leak-b@example.com', 'freelancer')

        # Gig 1 ends up hired, but is only shortlisted at the cut-off. Gig 2 was rejected before it.
        # Gig 3 ends up shortlisted, but is only under review at the cut-off.
        self.apply(self.a, 1, 1, 'hired', [(1, 'pending'), (2, 'under_review'), (3, 'shortlisted'), (8, 'hired')])
        self.apply(self.a, 2, 2, 'rejected', [(2, 'pending'), (3, 'under_review'), (4, 'rejected')])
        self.apply(self.a, 3, 3, 'shortlisted', [(3, 'pending'), (4, 'under_review'), (7, 'shortlisted')])
        for number in range(4, 11):
            self.apply(self.a, number, number, 'pending', [(number, 'pending')])

        self.interact(self.a, 1, 'view', 2)  # kept, but beaten by the application
        self.interact(self.a, 2, 'view', 8)  # after the cut-off: left out
        self.interact(self.a, 3, 'save', 5)  # kept, but beaten by the application
        self.interact(self.a, 9, 'view', 1)  # before the cut-off, but gig 9 is held out: left out
        self.interact(self.a, 7, 'view', 2)  # gig 7 is held out: left out
        self.interact(self.a, 11, 'view', 3)  # kept
        self.interact(self.a, 11, 'search_click', 9)  # after the cut-off: left out
        self.interact(self.a, 12, 'view', 6)  # exactly at the cut-off: kept

        self.apply(self.b, 1, 20, 'rejected', [(20, 'pending'), (21, 'rejected')])
        self.apply(self.b, 2, 21, 'pending', [(21, 'pending')])
        self.apply(self.b, 3, 22, 'shortlisted', [(22, 'pending'), (30, 'shortlisted')])
        self.interact(self.b, 4, 'view', 30)  # nobody's cut-off applies to B

        self.split = self.make_split()
        self.result = training_input(self.split)

    def weights_for(self, user):
        return {gig_id: w for (user_id, gig_id), w in self.result.weights.items() if user_id == user.id}

    def by_number(self, user):
        numbers = {gig.id: n for n, gig in self.gigs.items()}
        return {numbers[gig_id]: w for gig_id, w in self.weights_for(user).items()}

    def test_the_split_is_what_the_scenario_describes(self):
        parts = self.split.by_freelancer()[self.a.id]
        numbers = {gig.id: n for n, gig in self.gigs.items()}
        self.assertEqual(sorted(numbers[p.gig_id] for p in parts['train']), [1, 2, 3, 4, 5, 6])
        self.assertEqual(sorted(numbers[p.gig_id] for p in parts['validation']), [7, 8])
        self.assertEqual(sorted(numbers[p.gig_id] for p in parts['test']), [9, 10])
        self.assertEqual(self.split.cutoff(self.a.id), day(6))
        self.assertEqual(self.split.too_few, {self.b.id})

    def test_the_evaluated_freelancers_weights_are_exactly_the_hand_worked_ones(self):
        # Gig 1: shortlisted at the cut-off (4), not the hired it became (5). Gig 2: rejected (3).
        # Gig 3: under review at the cut-off (3), not the shortlisted it became (4), beating the save (2).
        # Gigs 4 to 6: applied (3). Gig 11: viewed (1). Gig 12: viewed at exactly the cut-off (1).
        self.assertEqual(self.by_number(self.a), {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3, 11: 1, 12: 1})

    def test_nothing_about_a_held_out_gig_reaches_training(self):
        held_out = self.split.held_out_gigs(self.a.id)
        self.assertEqual({g for g in self.weights_for(self.a)} & held_out, set())

    def test_no_interaction_after_the_cutoff_reaches_training(self):
        # The view of gig 2 on day 8 and the click on gig 11 on day 9 would have changed these if they got in.
        weights = self.by_number(self.a)
        self.assertEqual(weights[2], 3)  # not raised by anything after day 6
        self.assertEqual(weights[11], 1)  # the click is the same weight, so check the count instead
        self.assertEqual(self.result.stats['left_out_after_cutoff'], 2)

    def test_a_view_of_a_gig_that_was_later_held_out_is_left_out_even_before_the_cutoff(self):
        self.assertEqual(self.result.stats['left_out_held_out_gig'], 2)
        self.assertNotIn(7, self.by_number(self.a))
        self.assertNotIn(9, self.by_number(self.a))

    def test_a_status_reached_only_after_the_cutoff_is_not_used(self):
        self.assertEqual(self.by_number(self.a)[1], 4)  # shortlisted at day 6, not hired from day 8
        self.assertEqual(self.by_number(self.a)[3], 3)  # under review at day 6, not shortlisted from day 7
        self.assertEqual(self.result.stats['statuses_taken_as_of_cutoff'], 2)

    def test_an_interaction_at_exactly_the_cutoff_is_kept(self):
        self.assertEqual(self.by_number(self.a)[12], 1)

    def test_a_freelancer_with_too_few_positives_keeps_everything_with_final_statuses(self):
        self.assertEqual(self.by_number(self.b), {1: 3, 2: 3, 3: 4, 4: 1})

    def test_apply_interactions_are_never_read_as_interactions(self):
        # A held-out application also has an apply interaction. It must not bring the application back in.
        for number in (7, 8, 9, 10):
            self.assertNotIn(number, self.by_number(self.a))

    def test_the_counts_add_up(self):
        stats = self.result.stats
        self.assertEqual(stats['interactions_seen'], 9)
        self.assertEqual(
            stats['interactions_kept'] + stats['left_out_after_cutoff'] + stats['left_out_held_out_gig'], 9,
        )
        self.assertEqual(stats['train_positives'], 9)

    def test_a_naive_training_set_would_leak_which_is_what_this_guards_against(self):
        naive = collaborative.load_weights()
        numbers = {gig.id: n for n, gig in self.gigs.items()}
        leaked = {numbers[g] for (u, g) in naive if u == self.a.id} & {7, 8, 9, 10}
        self.assertEqual(leaked, {7, 8, 9, 10})  # the ordinary matrix includes every held-out gig
        self.assertEqual({numbers[g] for (u, g) in self.result.weights if u == self.a.id} & {7, 8, 9, 10}, set())

    def test_the_vocabulary_only_uses_gigs_that_existed_before_the_earliest_cutoff(self):
        early = self.make_gig('Posted before the cutoff')
        late = self.make_gig('Posted after the cutoff')
        Gig.objects.filter(pk=early.pk).update(created_at=day(5))
        Gig.objects.filter(pk=late.pk).update(created_at=day(8))
        ids = set(vectoriser_gig_ids(self.split))
        self.assertIn(early.id, ids)
        self.assertNotIn(late.id, ids)
        self.assertIn(self.gigs[1].id, ids)  # created long before

    def test_with_nobody_evaluated_every_gig_may_be_used(self):
        nobody = ev.build_split([])
        Gig.objects.filter(pk=self.gigs[1].pk).update(created_at=day(50))
        self.assertIn(self.gigs[1].id, set(vectoriser_gig_ids(nobody)))


class RandomWorldPropertyTests(LeakageBase):
    """In a larger random world, the training input is exactly what the rules allow, and nothing else."""

    def build_world(self, seed):
        rng = random.Random(seed)
        self.people = [self.make_user(f'leak-p{seed}-{n}@example.com', 'freelancer') for n in range(6)]
        for person in self.people:
            gigs = rng.sample(range(1, 13), rng.randint(5, 12))
            for index, gig_number in enumerate(gigs):
                status = rng.choice(['pending', 'under_review', 'shortlisted', 'rejected', 'withdrawn'])
                self.apply(person, gig_number, rng.randint(1, 30), status, [(rng.randint(1, 40), status)])
            for _ in range(rng.randint(5, 15)):
                kind = rng.choice(['view', 'save', 'search_click'])
                self.interact(person, rng.randint(1, 12), kind, rng.randint(0, 40))
        return ev.build_split(ev.load_positives())

    def allowed_pairs(self, split, person):
        """The pairs the rules allow for one freelancer, worked out here without using training_input."""
        cutoff = split.cutoff(person.id)
        held_out = split.held_out_gigs(person.id)
        pairs = {p.gig_id for p in split.in_part('train') if p.freelancer_id == person.id}
        for row in GigInteraction.objects.filter(user=person).exclude(type='apply'):
            if cutoff is not None and (row.created_at > cutoff or row.gig_id in held_out):
                continue
            pairs.add(row.gig_id)
        return pairs

    def test_for_several_random_worlds_the_training_pairs_are_exactly_the_allowed_ones(self):
        for seed in (1, 2, 3):
            split = self.build_world(seed)
            result = training_input(split)
            for person in self.people:
                trained = {g for (u, g) in result.weights if u == person.id}
                self.assertEqual(trained, self.allowed_pairs(split, person), f'seed {seed}')
            User.objects.filter(email__startswith=f'leak-p{seed}-').update(is_active=False)

    def test_no_held_out_validation_or_test_positive_is_ever_a_training_pair(self):
        for seed in (4, 5, 6):
            split = self.build_world(seed)
            result = training_input(split)
            for person in self.people:
                held_out = split.held_out_gigs(person.id)
                trained = {g for (u, g) in result.weights if u == person.id}
                self.assertEqual(trained & held_out, set(), f'seed {seed}')
            User.objects.filter(email__startswith=f'leak-p{seed}-').update(is_active=False)

    def test_the_result_does_not_depend_on_the_order_things_are_read_in(self):
        split = self.build_world(7)
        first = training_input(split).weights
        again = training_input(ev.build_split(list(reversed(ev.load_positives())))).weights
        self.assertEqual(first, again)
