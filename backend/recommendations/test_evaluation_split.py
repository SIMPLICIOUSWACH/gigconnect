import random
import tempfile
import uuid
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from accounts.models import User
from applications.models import Application
from gigs.models import Category, Gig, GigInteraction

from .evaluation import split as ev

START = datetime(2026, 10, 1, 12, 0, tzinfo=dt_timezone.utc)


def uid(n):
    return uuid.UUID(int=n)


def day(n):
    return START + timedelta(days=n)


def positive(freelancer, gig, days, status='pending', synthetic=False):
    return ev.Positive(uid(freelancer), uid(gig), day(days), status, synthetic)


def freelancer_with(freelancer, count):
    """`count` positives for one freelancer, one per day, on gigs 101, 102, and so on."""
    return [positive(freelancer, 100 + n, n) for n in range(1, count + 1)]


class SplitSizeTests(SimpleTestCase):
    """The sizes are worked out here by hand: about 15% held out for each of validation and test, at least 1."""

    def test_too_few_positives_are_not_split(self):
        for count in (0, 1, 4):
            self.assertIsNone(ev.split_sizes(count))

    def test_the_smallest_split_is_three_one_one(self):
        self.assertEqual(ev.split_sizes(5), (3, 1, 1))

    def test_a_few_more_positives_still_hold_out_one_each(self):
        self.assertEqual(ev.split_sizes(6), (4, 1, 1))
        self.assertEqual(ev.split_sizes(7), (5, 1, 1))

    def test_ten_positives_hold_out_two_each(self):
        self.assertEqual(ev.split_sizes(10), (6, 2, 2))  # 15% of 10 is 1.5, rounded up to 2

    def test_thirty_hold_out_five_each_because_halves_round_up(self):
        self.assertEqual(ev.split_sizes(30), (20, 5, 5))  # 15% of 30 is 4.5, rounded up to 5

    def test_a_hundred_gives_exactly_70_15_15(self):
        self.assertEqual(ev.split_sizes(100), (70, 15, 15))

    def test_the_parts_always_add_up(self):
        for count in range(5, 200):
            self.assertEqual(sum(ev.split_sizes(count)), count)

    def test_the_minimum_can_be_changed(self):
        self.assertEqual(ev.split_sizes(3, min_positives=3), (1, 1, 1))


class BuildSplitTests(SimpleTestCase):
    def setUp(self):
        # Freelancer 1 has 10 positives, freelancer 2 has 5, freelancer 3 has only 4.
        self.positives = freelancer_with(1, 10) + freelancer_with(2, 5) + freelancer_with(3, 4)
        self.split = ev.build_split(self.positives)

    def gigs(self, freelancer, part):
        return sorted(
            p.gig_id.int for p in self.split.in_part(part) if p.freelancer_id == uid(freelancer)
        )

    def test_the_oldest_go_to_train_then_validation_then_test(self):
        self.assertEqual(self.gigs(1, 'train'), [101, 102, 103, 104, 105, 106])
        self.assertEqual(self.gigs(1, 'validation'), [107, 108])
        self.assertEqual(self.gigs(1, 'test'), [109, 110])

    def test_five_positives_split_three_one_one(self):
        self.assertEqual(self.gigs(2, 'train'), [101, 102, 103])
        self.assertEqual(self.gigs(2, 'validation'), [104])
        self.assertEqual(self.gigs(2, 'test'), [105])

    def test_a_freelancer_with_too_few_stays_in_train_only_and_is_counted(self):
        self.assertEqual(self.gigs(3, 'train'), [101, 102, 103, 104])
        self.assertEqual(self.gigs(3, 'validation'), [])
        self.assertEqual(self.gigs(3, 'test'), [])
        self.assertEqual(self.split.too_few, {uid(3)})

    def test_only_freelancers_with_held_out_positives_are_evaluated(self):
        self.assertEqual(self.split.evaluated_freelancers(), {uid(1), uid(2)})

    def test_every_positive_is_in_exactly_one_part(self):
        self.assertEqual(len(self.split.rows), len(self.positives))
        pairs = [(r.positive.freelancer_id, r.positive.gig_id) for r in self.split.rows]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_for_each_freelancer_train_is_before_validation_which_is_before_test(self):
        for parts in self.split.by_freelancer().values():
            if not parts['validation']:
                continue
            self.assertLess(max(p.timestamp for p in parts['train']), min(p.timestamp for p in parts['validation']))
            self.assertLess(max(p.timestamp for p in parts['validation']), min(p.timestamp for p in parts['test']))

    def test_the_cutoff_is_the_time_of_the_last_train_positive(self):
        self.assertEqual(self.split.cutoff(uid(1)), day(6))
        self.assertEqual(self.split.cutoff(uid(2)), day(3))

    def test_a_freelancer_who_is_not_evaluated_has_no_cutoff(self):
        self.assertIsNone(self.split.cutoff(uid(3)))
        self.assertIsNone(self.split.cutoff(uid(999)))

    def test_the_held_out_gigs_are_validation_and_test_together(self):
        self.assertEqual(self.split.held_out_gigs(uid(1)), {uid(n) for n in (107, 108, 109, 110)})
        self.assertEqual(self.split.held_out_gigs(uid(3)), set())

    def test_the_order_the_positives_arrive_in_does_not_matter(self):
        shuffled = list(self.positives)
        random.Random(4).shuffle(shuffled)
        again = ev.build_split(shuffled)
        self.assertEqual([(r.positive, r.part) for r in again.rows], [(r.positive, r.part) for r in self.split.rows])

    def test_the_same_data_and_seed_always_give_the_same_split(self):
        again = ev.build_split(self.positives)
        self.assertEqual([(r.positive, r.part) for r in again.rows], [(r.positive, r.part) for r in self.split.rows])
        self.assertEqual(again.fingerprint(), self.split.fingerprint())

    def test_positives_at_the_same_moment_are_ordered_by_the_seed_not_by_chance(self):
        same_time = [positive(1, 100 + n, 1) for n in range(1, 11)]  # ten at exactly the same time
        first = ev.build_split(same_time, seed=1)
        again = ev.build_split(list(reversed(same_time)), seed=1)
        other = ev.build_split(same_time, seed=2)
        order = [(r.positive.gig_id, r.part) for r in first.rows]
        self.assertEqual(order, [(r.positive.gig_id, r.part) for r in again.rows])
        self.assertNotEqual(order, [(r.positive.gig_id, r.part) for r in other.rows])

    def test_the_fingerprint_changes_when_the_data_changes(self):
        changed = ev.build_split(self.positives + [positive(4, 500, 3)])
        self.assertNotEqual(changed.fingerprint(), self.split.fingerprint())

    def test_the_strict_reading_counts_only_shortlisted_and_hired(self):
        self.assertTrue(positive(1, 1, 1, status='shortlisted').strictly_relevant)
        self.assertTrue(positive(1, 1, 1, status='hired').strictly_relevant)
        for status in ('pending', 'under_review', 'rejected', 'withdrawn', 'applied'):
            self.assertFalse(positive(1, 1, 1, status=status).strictly_relevant, status)

    def test_no_positives_gives_an_empty_split(self):
        empty = ev.build_split([])
        self.assertEqual((empty.rows, empty.too_few), ([], set()))


class SaveAndLoadTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / 'evaluation'
        self.split = ev.build_split(freelancer_with(1, 10) + freelancer_with(3, 4), seed=9, include_synthetic=False)

    def test_a_saved_split_loads_back_the_same(self):
        ev.save_split(self.split, self.directory)
        loaded = ev.load_split(self.directory)
        self.assertEqual([(r.positive, r.part) for r in loaded.rows], [(r.positive, r.part) for r in self.split.rows])
        self.assertEqual((loaded.seed, loaded.include_synthetic, loaded.too_few), (9, False, {uid(3)}))
        self.assertEqual(loaded.fingerprint(), self.split.fingerprint())

    def test_the_csv_has_the_agreed_columns_and_one_row_per_positive(self):
        ev.save_split(self.split, self.directory)
        lines = (self.directory / ev.SPLIT_FILE).read_text(encoding='utf-8-sig').splitlines()
        self.assertEqual(lines[0], 'freelancer_id,gig_id,timestamp,part,status,is_synthetic')
        self.assertEqual(len(lines) - 1, 14)

    def test_saving_twice_gives_the_same_csv(self):
        ev.save_split(self.split, self.directory)
        first = (self.directory / ev.SPLIT_FILE).read_bytes()
        ev.save_split(self.split, self.directory)
        self.assertEqual((self.directory / ev.SPLIT_FILE).read_bytes(), first)

    def test_there_is_nothing_to_load_before_one_is_saved(self):
        self.assertIsNone(ev.load_split(self.directory))

    def test_the_description_records_the_seed_and_the_fingerprint(self):
        import json
        ev.save_split(self.split, self.directory)
        meta = json.loads((self.directory / ev.META_FILE).read_text(encoding='utf-8'))
        self.assertEqual((meta['seed'], meta['fingerprint']), (9, self.split.fingerprint()))


class LoadPositivesTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Evaluation Split Category')
        self.client_user = self.make_user('split-client@example.com', 'client')
        self.person = self.make_user('split-person@example.com', 'freelancer')
        self.synthetic = self.make_user('split-synthetic@example.com', 'freelancer', is_synthetic=True)
        self.gig = self.make_gig('First gig')
        self.other_gig = self.make_gig('Second gig')

    def make_user(self, email, role, **extra):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password='x-Split-pass-1', full_name=email.split('@')[0],
            phone=f'2547000090{number:02d}', role=role, **extra,
        )

    def make_gig(self, title):
        return Gig.objects.create(
            client=self.client_user, category=self.category, title=title, description='A gig.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30),
        )

    def apply(self, user, gig, status='pending', **extra):
        return Application.objects.create(gig=gig, freelancer=user, cover_letter='x' * 60, status=status, **extra)

    def pairs(self, **kwargs):
        return {(p.freelancer_id, p.gig_id): p for p in ev.load_positives(**kwargs)}

    def test_an_application_of_any_status_is_a_positive(self):
        for status in ('pending', 'under_review', 'shortlisted', 'hired', 'rejected', 'withdrawn'):
            self.apply(self.person, self.make_gig(f'Gig for {status}'), status)
        statuses = {p.status for p in ev.load_positives()}
        self.assertEqual(statuses, {'pending', 'under_review', 'shortlisted', 'hired', 'rejected', 'withdrawn'})

    def test_views_clicks_and_saves_are_not_positives(self):
        for kind in ('view', 'search_click', 'save', 'recommendation_click'):
            GigInteraction.objects.create(gig=self.gig, user=self.person, type=kind)
        self.assertEqual(ev.load_positives(), [])

    def test_an_apply_interaction_with_no_application_row_is_still_a_positive(self):
        GigInteraction.objects.create(gig=self.gig, user=self.person, type='apply')
        found = self.pairs()[(self.person.id, self.gig.id)]
        self.assertEqual(found.status, ev.APPLIED)

    def test_an_application_and_its_apply_interaction_are_one_positive_with_the_earlier_time_and_the_real_status(self):
        application = self.apply(self.person, self.gig, 'shortlisted')
        interaction = GigInteraction.objects.create(gig=self.gig, user=self.person, type='apply')
        earlier = timezone.now() - timedelta(days=3)
        GigInteraction.objects.filter(pk=interaction.pk).update(created_at=earlier)
        positives = ev.load_positives()
        self.assertEqual(len(positives), 1)
        self.assertEqual((positives[0].status, positives[0].timestamp), ('shortlisted', earlier))
        self.assertGreater(application.created_at, earlier)

    def test_a_deleted_freelancer_is_never_included(self):
        self.apply(self.person, self.gig)
        User.objects.filter(pk=self.person.pk).update(is_active=False, deleted_at=timezone.now())
        self.assertEqual(ev.load_positives(), [])

    def test_clients_are_never_included(self):
        GigInteraction.objects.create(gig=self.gig, user=self.client_user, type='apply')
        self.assertEqual(ev.load_positives(), [])

    def test_synthetic_positives_are_flagged_and_can_be_left_out(self):
        self.apply(self.person, self.gig)
        self.apply(self.synthetic, self.gig)
        flags = {p.freelancer_id: p.is_synthetic for p in ev.load_positives()}
        self.assertEqual(flags, {self.person.id: False, self.synthetic.id: True})
        self.assertEqual({p.freelancer_id for p in ev.load_positives(include_synthetic=False)}, {self.person.id})

    def test_a_row_flagged_synthetic_on_a_real_freelancer_counts_as_synthetic(self):
        self.apply(self.person, self.gig, is_synthetic=True)
        self.assertTrue(ev.load_positives()[0].is_synthetic)


class LoadOrBuildTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / 'evaluation'
        self.category = Category.objects.create(name='Evaluation Load Category')
        self.client_user = self.make_user('load-client@example.com', 'client')
        self.people = [self.make_user(f'load-person-{n}@example.com', 'freelancer') for n in range(2)]
        self.gigs = [self.make_gig(f'Load gig {n}') for n in range(12)]
        for person in self.people:
            for number, gig in enumerate(self.gigs[:10]):
                application = Application.objects.create(gig=gig, freelancer=person, cover_letter='x' * 60)
                when = timezone.now() - timedelta(days=30 - number)
                Application.objects.filter(pk=application.pk).update(created_at=when)

    def make_user(self, email, role):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password='x-Load-pass-1', full_name=email.split('@')[0],
            phone=f'2547000091{number:02d}', role=role,
        )

    def make_gig(self, title):
        return Gig.objects.create(
            client=self.client_user, category=self.category, title=title, description='A gig.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=60),
        )

    def load(self, **kwargs):
        return ev.load_or_build(directory=self.directory, **kwargs)

    def test_the_first_call_builds_and_saves_and_the_second_loads_the_same_split(self):
        built, how, _ = self.load()
        self.assertEqual(how, 'built')
        loaded, how, _ = self.load()
        self.assertEqual(how, 'loaded')
        self.assertEqual([(r.positive, r.part) for r in loaded.rows], [(r.positive, r.part) for r in built.rows])

    def test_a_loaded_split_is_not_changed_by_new_data_until_it_is_rebuilt(self):
        built, _, _ = self.load()
        Application.objects.create(gig=self.gigs[10], freelancer=self.people[0], cover_letter='x' * 60)
        loaded, how, _ = self.load()
        self.assertEqual((how, len(loaded.rows)), ('loaded', len(built.rows)))
        rebuilt, how, _ = self.load(rebuild=True)
        self.assertEqual((how, len(rebuilt.rows)), ('built', len(built.rows) + 1))

    def test_a_different_synthetic_setting_rebuilds_instead_of_loading_the_wrong_split(self):
        self.load(include_synthetic=True)
        split, how, note = self.load(include_synthetic=False)
        self.assertEqual(how, 'built')
        self.assertIn('different synthetic setting', note)
        self.assertFalse(split.include_synthetic)

    def test_someone_who_deleted_their_account_after_the_split_was_saved_is_removed_from_it(self):
        self.load()
        gone = self.people[0]
        User.objects.filter(pk=gone.pk).update(is_active=False, deleted_at=timezone.now())
        loaded, how, note = self.load()
        self.assertEqual(how, 'loaded')
        self.assertIn('1 freelancer(s) who deleted their account', note)
        self.assertNotIn(gone.id, {r.positive.freelancer_id for r in loaded.rows})
        self.assertIn(self.people[1].id, {r.positive.freelancer_id for r in loaded.rows})

    def test_a_deleted_freelancer_is_not_in_a_new_split_either(self):
        User.objects.filter(pk=self.people[0].pk).update(is_active=False, deleted_at=timezone.now())
        built, _, _ = self.load()
        self.assertEqual({r.positive.freelancer_id for r in built.rows}, {self.people[1].id})

    def test_the_real_data_is_split_the_way_the_rules_say(self):
        built, _, _ = self.load()
        parts = built.by_freelancer()[self.people[0].id]
        self.assertEqual((len(parts['train']), len(parts['validation']), len(parts['test'])), (6, 2, 2))
        self.assertEqual({p.gig_id for p in parts['test']}, {self.gigs[8].id, self.gigs[9].id})

    def test_building_twice_from_the_same_data_gives_the_same_csv(self):
        self.load()
        first = (self.directory / ev.SPLIT_FILE).read_bytes()
        self.load(rebuild=True)
        self.assertEqual((self.directory / ev.SPLIT_FILE).read_bytes(), first)
