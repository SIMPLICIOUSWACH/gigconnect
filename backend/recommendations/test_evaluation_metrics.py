from django.test import SimpleTestCase

from .evaluation import metrics as m

# One freelancer, six ranked gigs, three relevant gigs: b and e are in the list, z is not (it can never be found).
RANKED = ['a', 'b', 'c', 'd', 'e', 'f']
RELEVANT = {'b', 'e', 'z'}


class PrecisionRecallTests(SimpleTestCase):
    """Every expected value is worked out here by hand from the list above, not taken from the code."""

    def test_first_three_hold_one_relevant_gig(self):
        # a, b, c: only b is relevant. Precision 1 / 3, recall 1 / 3 of the 3 relevant, F1 is 1 / 3 too.
        self.assertAlmostEqual(m.precision_at_k(RANKED, RELEVANT, 3), 1 / 3)
        self.assertAlmostEqual(m.recall_at_k(RANKED, RELEVANT, 3), 1 / 3)
        self.assertAlmostEqual(m.f1_at_k(RANKED, RELEVANT, 3), 1 / 3)
        self.assertEqual(m.hit_at_k(RANKED, RELEVANT, 3), 1.0)

    def test_first_five_hold_two_relevant_gigs(self):
        # a to e: b and e. Precision 2 / 5 = 0.4, recall 2 / 3. F1 = 2 * 0.4 * (2/3) / (0.4 + 2/3) = 0.5.
        self.assertAlmostEqual(m.precision_at_k(RANKED, RELEVANT, 5), 0.4)
        self.assertAlmostEqual(m.recall_at_k(RANKED, RELEVANT, 5), 2 / 3)
        self.assertAlmostEqual(m.f1_at_k(RANKED, RELEVANT, 5), 0.5)

    def test_first_one_misses(self):
        self.assertEqual(m.precision_at_k(RANKED, RELEVANT, 1), 0.0)
        self.assertEqual(m.recall_at_k(RANKED, RELEVANT, 1), 0.0)
        self.assertEqual(m.f1_at_k(RANKED, RELEVANT, 1), 0.0)  # 0 and 0 give 0, not a division error
        self.assertEqual(m.hit_at_k(RANKED, RELEVANT, 1), 0.0)

    def test_a_relevant_gig_missing_from_the_list_is_never_found(self):
        # Even with K far past the end of the list, z keeps recall below 1.
        self.assertAlmostEqual(m.recall_at_k(RANKED, RELEVANT, 100), 2 / 3)

    def test_fewer_candidates_than_k_still_divides_by_k(self):
        # Two candidates, both relevant, K = 5: precision 2 / 5 = 0.4, recall 1, F1 = 2 * 0.4 * 1 / 1.4 = 4 / 7.
        ranked, relevant = ['a', 'b'], {'a', 'b'}
        self.assertAlmostEqual(m.precision_at_k(ranked, relevant, 5), 0.4)
        self.assertEqual(m.recall_at_k(ranked, relevant, 5), 1.0)
        self.assertAlmostEqual(m.f1_at_k(ranked, relevant, 5), 4 / 7)

    def test_a_perfect_ranking_has_recall_one_and_precision_by_the_number_relevant(self):
        ranked, relevant = ['x', 'y', 'p', 'q', 'r'], {'x', 'y'}
        self.assertEqual(m.recall_at_k(ranked, relevant, 2), 1.0)
        self.assertEqual(m.precision_at_k(ranked, relevant, 2), 1.0)
        self.assertEqual(m.f1_at_k(ranked, relevant, 2), 1.0)
        self.assertEqual(m.precision_at_k(ranked, relevant, 4), 0.5)  # 2 of 4

    def test_no_relevant_gigs_means_there_is_nothing_to_find(self):
        self.assertEqual(m.precision_at_k(RANKED, set(), 5), 0.0)
        self.assertIsNone(m.recall_at_k(RANKED, set(), 5))
        self.assertIsNone(m.f1_at_k(RANKED, set(), 5))
        self.assertIsNone(m.hit_at_k(RANKED, set(), 5))

    def test_an_empty_ranking_finds_nothing(self):
        self.assertEqual(m.precision_at_k([], {'a'}, 5), 0.0)
        self.assertEqual(m.recall_at_k([], {'a'}, 5), 0.0)
        self.assertEqual(m.hit_at_k([], {'a'}, 5), 0.0)

    def test_order_inside_the_top_k_does_not_matter(self):
        self.assertEqual(
            m.precision_at_k(['e', 'd', 'c', 'b', 'a'], RELEVANT, 5), m.precision_at_k(RANKED, RELEVANT, 5),
        )

    def test_the_ranking_is_not_changed(self):
        ranked = list(RANKED)
        m.precision_at_k(ranked, RELEVANT, 2)
        self.assertEqual(ranked, RANKED)


class FreelancerMetricsTests(SimpleTestCase):
    def test_every_metric_at_every_k(self):
        result = m.freelancer_metrics(RANKED, RELEVANT, (3, 5))
        self.assertEqual(set(result), {(k, name) for k in (3, 5) for name in m.METRICS})
        self.assertAlmostEqual(result[(5, 'precision')], 0.4)
        self.assertAlmostEqual(result[(3, 'recall')], 1 / 3)
        self.assertAlmostEqual(result[(5, 'f1')], 0.5)
        self.assertEqual(result[(3, 'hit')], 1.0)

    def test_a_freelancer_with_nothing_relevant_is_left_out(self):
        self.assertIsNone(m.freelancer_metrics(RANKED, set(), (5,)))


class BootstrapTests(SimpleTestCase):
    def test_values_that_are_all_equal_have_no_spread(self):
        self.assertEqual(m.bootstrap_interval([0.25] * 12), (0.25, 0.25))

    def test_one_value_is_its_own_interval(self):
        self.assertEqual(m.bootstrap_interval([0.7]), (0.7, 0.7))

    def test_no_values_is_an_error_not_a_made_up_interval(self):
        with self.assertRaises(ValueError):
            m.bootstrap_interval([])

    def test_the_interval_holds_the_mean_and_stays_inside_the_data(self):
        values = [0.0, 0.2, 0.4, 0.4, 0.6, 1.0, 0.0, 0.2]
        low, high = m.bootstrap_interval(values)
        mean = sum(values) / len(values)
        self.assertLessEqual(low, mean)
        self.assertGreaterEqual(high, mean)
        self.assertGreaterEqual(low, min(values))
        self.assertLessEqual(high, max(values))
        self.assertLess(low, high)

    def test_the_same_values_and_seed_give_the_same_interval(self):
        values = [0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]
        self.assertEqual(m.bootstrap_interval(values, seed=3), m.bootstrap_interval(values, seed=3))

    def test_more_freelancers_give_a_narrower_interval(self):
        few = [0.0, 1.0] * 5
        many = [0.0, 1.0] * 50
        few_low, few_high = m.bootstrap_interval(few)
        many_low, many_high = m.bootstrap_interval(many)
        self.assertLess(many_high - many_low, few_high - few_low)

    def test_a_coin_flip_sample_gives_an_interval_near_the_known_one(self):
        # 50 zeros and ones, half each: the standard error of the mean is 0.5 / sqrt(100) = 0.05, so the middle 95%
        # is about 0.5 plus or minus 1.96 * 0.05, which is 0.402 to 0.598.
        low, high = m.bootstrap_interval([0.0, 1.0] * 50, resamples=4000)
        self.assertAlmostEqual(low, 0.402, delta=0.02)
        self.assertAlmostEqual(high, 0.598, delta=0.02)


class SummariseTests(SimpleTestCase):
    def test_summary_has_the_mean_the_interval_and_the_count(self):
        summary = m.summarise([0.2, 0.4, 0.6])
        self.assertAlmostEqual(summary.mean, 0.4)
        self.assertEqual(summary.n, 3)
        self.assertLessEqual(summary.low, summary.mean)
        self.assertGreaterEqual(summary.high, summary.mean)

    def test_no_values_has_no_summary(self):
        self.assertIsNone(m.summarise([]))

    def test_averaging_freelancers_skips_those_with_nothing_relevant(self):
        per_freelancer = {
            'one': {(5, 'precision'): 0.2},
            'nothing relevant': None,
            'two': {(5, 'precision'): 0.4},
        }
        summary = m.summarise_all(per_freelancer)[(5, 'precision')]
        self.assertAlmostEqual(summary.mean, 0.3)
        self.assertEqual(summary.n, 2)

    def test_averaging_nobody_gives_nothing(self):
        self.assertEqual(m.summarise_all({}), {})
        self.assertEqual(m.summarise_all({'x': None}), {})
