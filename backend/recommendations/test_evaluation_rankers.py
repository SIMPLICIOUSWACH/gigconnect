import uuid

from django.test import SimpleTestCase

from .evaluation import rankers as r
from .evaluation.split import Positive, tie_key


def uid(n):
    return uuid.UUID(int=n)


def applied(freelancer, gig):
    return Positive(uid(freelancer), uid(gig), None, 'pending', False)


class OrderByScoreTests(SimpleTestCase):
    def test_best_score_first(self):
        self.assertEqual(r.order_by_score({'a': 0.1, 'b': 0.9, 'c': 0.5}), ['b', 'c', 'a'])

    def test_a_gig_with_no_score_goes_after_every_scored_gig_even_a_zero(self):
        self.assertEqual(r.order_by_score({'none': None, 'zero': 0.0, 'some': 0.2}), ['some', 'zero', 'none'])

    def test_equal_scores_are_ordered_by_the_hash_of_the_seed_and_gig(self):
        result = r.order_by_score({'a': 0.5, 'b': 0.5, 'c': 0.5}, seed=7)
        self.assertEqual(result, sorted(['a', 'b', 'c'], key=lambda gig: tie_key(7, gig)))

    def test_the_order_does_not_depend_on_the_order_of_the_input(self):
        forward = r.order_by_score({'a': 0.5, 'b': 0.5, 'c': 0.5, 'd': 0.1})
        backward = r.order_by_score({'d': 0.1, 'c': 0.5, 'b': 0.5, 'a': 0.5})
        self.assertEqual(forward, backward)

    def test_a_different_seed_can_break_ties_differently(self):
        scores = {n: 0.5 for n in range(20)}
        self.assertNotEqual(r.order_by_score(scores, seed=1), r.order_by_score(scores, seed=2))

    def test_nothing_gives_nothing(self):
        self.assertEqual(r.order_by_score({}), [])


class RandomOrderTests(SimpleTestCase):
    def test_every_gig_appears_once(self):
        result = r.random_order(range(30), seed=1, freelancer_id='f')
        self.assertEqual(sorted(result), list(range(30)))

    def test_the_same_seed_and_freelancer_give_the_same_order_whatever_the_input_order(self):
        first = r.random_order(['a', 'b', 'c', 'd', 'e', 'f'], seed=1, freelancer_id='f')
        second = r.random_order(['f', 'e', 'd', 'c', 'b', 'a'], seed=1, freelancer_id='f')
        self.assertEqual(first, second)

    def test_another_seed_or_another_freelancer_gives_another_order(self):
        gigs = list(range(30))
        base = r.random_order(gigs, seed=1, freelancer_id='f')
        self.assertNotEqual(base, r.random_order(gigs, seed=2, freelancer_id='f'))
        self.assertNotEqual(base, r.random_order(gigs, seed=1, freelancer_id='g'))

    def test_the_input_is_not_changed(self):
        gigs = [3, 1, 2]
        r.random_order(gigs, seed=1, freelancer_id='f')
        self.assertEqual(gigs, [3, 1, 2])

    def test_random_picks_hit_the_relevant_gigs_at_the_rate_chance_says(self):
        # 100 gigs, 10 relevant, top 10 picked at random: the expected precision is 10 / 100 = 0.1. Averaged over
        # 400 seeds, the standard error is about 0.0095 for one freelancer, so 0.1 plus or minus 0.03 holds.
        gigs, relevant = list(range(100)), set(range(10))
        hits = sum(len(set(r.random_order(gigs, seed, 'f')[:10]) & relevant) for seed in range(400))
        self.assertAlmostEqual(hits / (400 * 10), 0.1, delta=0.03)


class PopularityTests(SimpleTestCase):
    def test_counts_are_different_freelancers_per_gig(self):
        positives = [applied(1, 100), applied(2, 100), applied(3, 100), applied(1, 101), applied(2, 102)]
        self.assertEqual(r.popularity_counts(positives), {uid(100): 3, uid(101): 1, uid(102): 1})

    def test_the_same_freelancer_twice_counts_once(self):
        self.assertEqual(r.popularity_counts([applied(1, 100), applied(1, 100)]), {uid(100): 1})

    def test_no_positives_gives_no_counts(self):
        self.assertEqual(r.popularity_counts([]), {})

    def test_most_applied_first_and_unseen_gigs_last(self):
        counts = {'a': 5, 'b': 2, 'c': 9}
        self.assertEqual(r.popularity_order(['a', 'b', 'c', 'new'], counts), ['c', 'a', 'b', 'new'])

    def test_gigs_with_the_same_count_are_ordered_by_the_hash(self):
        result = r.popularity_order(['x', 'y', 'z'], {'x': 4, 'y': 4, 'z': 4}, seed=5)
        self.assertEqual(result, sorted(['x', 'y', 'z'], key=lambda gig: tie_key(5, gig)))

    def test_popularity_does_not_depend_on_who_is_asking(self):
        counts = {'a': 3, 'b': 1}
        self.assertEqual(r.popularity_order(['b', 'a'], counts), r.popularity_order(['a', 'b'], counts))
