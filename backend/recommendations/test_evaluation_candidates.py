import uuid
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone

from django.test import SimpleTestCase, TestCase

from accounts.models import User
from gigs.models import Category, Gig

from .evaluation import split as ev
from .evaluation.candidates import GigRecord, candidates_for, load_gig_records

START = datetime(2026, 10, 1, 12, 0, tzinfo=dt_timezone.utc)
ME = uuid.UUID(int=1)


def uid(n):
    return uuid.UUID(int=n)


def day(n):
    return START + timedelta(days=n)


def on_day(n):
    return day(n).date()


def gig(number, created=0, deadline=100, client=999):
    """A gig record. created and deadline are days from the start; deadline None means none."""
    return GigRecord(uid(number), uid(client), day(created), None if deadline is None else on_day(deadline))


class CandidateTests(SimpleTestCase):
    """
    One freelancer, 10 positives on gigs 101 to 110 on days 1 to 10: train is 101 to 106, validation is 107 (day 7)
    and 108 (day 8), test is 109 (day 9) and 110 (day 10).
    """

    def setUp(self):
        positives = [ev.Positive(ME, uid(100 + n), day(n), 'pending', False) for n in range(1, 11)]
        self.split = ev.build_split(positives)

    def ids(self, part, gigs):
        found, _ = candidates_for(self.split, ME, part, gigs)
        return {g.int for g in found}

    def outside(self, part, gigs):
        _, outside = candidates_for(self.split, ME, part, gigs)
        return {g.int for g in outside}

    def with_positives(self, extra):
        """The ten gigs the freelancer applied to, posted early and open for a long time, plus these."""
        return [gig(100 + n, created=0, deadline=100) for n in range(1, 11)] + extra

    def test_an_ordinary_open_gig_is_a_candidate(self):
        self.assertIn(5, self.ids('validation', self.with_positives([gig(5)])))

    def test_a_gig_posted_after_the_part_ended_is_not_a_candidate(self):
        gigs = self.with_positives([gig(5, created=9), gig(6, created=8)])
        # Validation runs days 7 to 8: gig 6 (posted day 8) is in, gig 5 (posted day 9) is not.
        self.assertEqual(self.ids('validation', gigs) & {5, 6}, {6})

    def test_a_gig_posted_during_the_part_is_a_candidate_for_the_part_it_was_posted_in(self):
        gigs = self.with_positives([gig(5, created=9)])
        self.assertNotIn(5, self.ids('validation', gigs))
        self.assertIn(5, self.ids('test', gigs))  # test runs days 9 to 10

    def test_a_gig_whose_deadline_passed_before_the_part_began_is_not_a_candidate(self):
        gigs = self.with_positives([gig(5, deadline=3), gig(6, deadline=7)])
        # Validation begins day 7: a deadline of day 3 had passed, and a deadline of day 7 is still open that day.
        self.assertEqual(self.ids('validation', gigs) & {5, 6}, {6})

    def test_a_deadline_on_the_first_day_of_the_part_counts_as_open(self):
        self.assertIn(6, self.ids('validation', self.with_positives([gig(6, deadline=7)])))

    def test_a_gig_with_no_deadline_counts_as_open(self):
        self.assertIn(5, self.ids('validation', self.with_positives([gig(5, deadline=None)])))

    def test_the_freelancers_own_gig_is_never_a_candidate(self):
        own = gig(5, client=1)
        self.assertNotIn(5, self.ids('validation', self.with_positives([own])))

    def test_gigs_applied_to_in_train_are_not_candidates(self):
        found = self.ids('validation', self.with_positives([]))
        self.assertEqual(found & {101, 102, 103, 104, 105, 106}, set())

    def test_the_other_held_out_parts_positives_are_not_candidates(self):
        gigs = self.with_positives([])
        self.assertEqual(self.ids('validation', gigs) & {109, 110}, set())
        self.assertEqual(self.ids('test', gigs) & {107, 108}, set())

    def test_the_parts_own_positives_are_always_candidates(self):
        gigs = self.with_positives([])
        self.assertEqual(self.ids('validation', gigs) & {107, 108}, {107, 108})
        self.assertEqual(self.ids('test', gigs) & {109, 110}, {109, 110})

    def test_a_positive_that_fails_the_rules_is_still_included_and_reported(self):
        # Gig 107 is dated as posted on day 50, long after the validation part: inconsistent data.
        gigs = [gig(100 + n) for n in range(1, 11) if n != 7] + [gig(107, created=50)]
        found, outside = candidates_for(self.split, ME, 'validation', gigs)
        self.assertIn(uid(107), found)
        self.assertEqual([g.int for g in outside], [107])

    def test_consistent_data_reports_nothing_outside_the_rules(self):
        self.assertEqual(self.outside('validation', self.with_positives([gig(5), gig(6)])), set())

    def test_the_result_is_sorted_and_has_no_repeats(self):
        found, _ = candidates_for(self.split, ME, 'test', self.with_positives([gig(5), gig(6), gig(7)]))
        self.assertEqual(found, sorted(set(found), key=str))

    def test_train_is_not_a_part_candidates_are_built_for(self):
        with self.assertRaises(ValueError):
            candidates_for(self.split, ME, 'train', [])

    def test_a_freelancer_who_is_not_evaluated_has_no_candidates(self):
        self.assertEqual(candidates_for(self.split, uid(999), 'validation', [gig(5)]), ([], []))

    def test_no_gigs_gives_just_the_positives(self):
        found, outside = candidates_for(self.split, ME, 'validation', [])
        self.assertEqual({g.int for g in found}, {107, 108})
        self.assertEqual({g.int for g in outside}, {107, 108})  # none of them passed the (empty) rules

    def test_the_window_follows_each_freelancer(self):
        # A second freelancer whose validation positive is on day 20 has a different window.
        other = uid(2)
        positives = [ev.Positive(other, uid(300 + n), day(n + 15), 'pending', False) for n in range(1, 6)]
        split = ev.build_split(positives)  # train 1 to 3 (days 16 to 18), validation 304 (day 19), test 305 (day 20)
        gigs = [gig(300 + n, created=0) for n in range(1, 6)] + [gig(5, created=19), gig(6, created=21)]
        found, _ = candidates_for(split, other, 'validation', gigs)
        self.assertIn(uid(5), found)  # posted on day 19, the end of the validation window
        self.assertNotIn(uid(6), found)  # posted on day 21, after it


class LoadGigRecordsTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Candidate Records Category')
        self.client_user = User.objects.create_user(
            email='records-client@example.com', password='x-Records-pass-1', full_name='Client',
            phone='254700009301', role='client',
        )
        self.open = Gig.objects.create(
            client=self.client_user, category=category, title='Open', description='A gig.', budget_min=1, budget_max=2,
            deadline=date.today() + timedelta(days=30),
        )
        self.closed = Gig.objects.create(
            client=self.client_user, category=category, title='Closed', description='A gig.', budget_min=1,
            budget_max=2, deadline=date.today() + timedelta(days=30), status=Gig.Status.CLOSED,
        )
        self.synthetic = Gig.objects.create(
            client=self.client_user, category=category, title='Synthetic', description='A gig.', budget_min=1,
            budget_max=2, deadline=date.today() + timedelta(days=30), is_synthetic=True,
        )

    def test_every_gig_is_loaded_whatever_its_status(self):
        ids = {record.id for record in load_gig_records()}
        self.assertEqual(ids, {self.open.id, self.closed.id, self.synthetic.id})

    def test_synthetic_gigs_can_be_left_out(self):
        ids = {record.id for record in load_gig_records(include_synthetic=False)}
        self.assertEqual(ids, {self.open.id, self.closed.id})

    def test_a_record_has_what_the_rules_need(self):
        record = next(r for r in load_gig_records() if r.id == self.open.id)
        self.assertEqual(record.client_id, self.client_user.id)
        self.assertEqual(record.application_deadline, self.open.application_deadline)
        self.assertEqual(record.created_at, self.open.created_at)

    def test_loading_takes_one_query(self):
        with self.assertNumQueries(1):
            load_gig_records()
