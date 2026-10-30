from django.test import SimpleTestCase

from .evaluation import compare as cmp


def case(freelancer_id, candidates, relevant, cold_start=False):
    return cmp.Case(
        freelancer_id=freelancer_id, candidates=list(candidates), relevant=set(relevant), cold_start=cold_start,
    )


class RandomBaselineTests(SimpleTestCase):
    def test_when_every_candidate_is_in_the_list_the_order_cannot_matter(self):
        # 10 candidates, 2 relevant, K = 10: precision 2 / 10, recall 1 and a hit for every seed, so no spread.
        result = cmp.random_baseline([case('f', range(10), {0, 1})], (10,), seeds=5, seed=42)
        summary = result.groups['all']
        self.assertAlmostEqual(summary[(10, 'precision')].mean, 0.2)
        self.assertEqual(summary[(10, 'recall')].mean, 1.0)
        self.assertEqual(summary[(10, 'hit')].mean, 1.0)
        self.assertEqual(result.spread[(10, 'precision')].sd, 0.0)

    def test_at_k_five_of_ten_the_average_is_what_chance_says(self):
        # 2 relevant of 10, 5 shown: on average 1 relevant is shown, so precision is 1 / 5 = 0.2 and recall 0.5.
        # Over 400 seeds the standard error is about 0.007, so a margin of 0.04 is nearly six of them.
        result = cmp.random_baseline([case('f', range(10), {0, 1})], (5,), seeds=400, seed=42)
        summary = result.groups['all']
        self.assertAlmostEqual(summary[(5, 'precision')].mean, 0.2, delta=0.04)
        self.assertAlmostEqual(summary[(5, 'recall')].mean, 0.5, delta=0.1)
        # The chance of at least one of two relevant gigs in 5 of 10 is 1 - (5/10 * 4/9) = 7 / 9.
        self.assertAlmostEqual(summary[(5, 'hit')].mean, 7 / 9, delta=0.06)

    def test_the_spread_across_seeds_is_the_spread_of_the_seed_averages(self):
        # For one freelancer a single seed gives precision 0, 0.2 or 0.4, so the spread is well above zero.
        result = cmp.random_baseline([case('f', range(10), {0, 1})], (5,), seeds=50, seed=42)
        spread = result.spread[(5, 'precision')]
        self.assertGreater(spread.sd, 0.05)
        self.assertLessEqual(spread.low, 0.2)
        self.assertGreaterEqual(spread.high, 0.2)
        self.assertGreaterEqual(spread.low, 0.0)
        self.assertLessEqual(spread.high, 0.4)

    def test_one_seed_has_no_spread_to_measure(self):
        result = cmp.random_baseline([case('f', range(10), {0, 1})], (5,), seeds=1, seed=42)
        self.assertEqual(result.spread[(5, 'precision')].sd, 0.0)

    def test_the_same_seeds_always_give_the_same_baseline(self):
        cases = [case('f', range(20), {3, 4, 5}), case('g', range(20), {1})]
        first = cmp.random_baseline(cases, (5, 10), seeds=10, seed=42)
        second = cmp.random_baseline(cases, (5, 10), seeds=10, seed=42)
        self.assertEqual(first.groups['all'], second.groups['all'])
        self.assertEqual(first.spread, second.spread)

    def test_a_freelancer_with_nothing_relevant_is_not_in_the_average(self):
        cases = [case('f', range(10), {0, 1}), case('empty', range(10), set())]
        result = cmp.random_baseline(cases, (10,), seeds=3, seed=42)
        self.assertEqual(result.groups['all'][(10, 'precision')].n, 1)

    def test_no_freelancers_gives_empty_groups_and_no_spread(self):
        result = cmp.random_baseline([], (5,), seeds=3, seed=42)
        self.assertEqual(result.groups, {'all': {}, 'cold_start': {}, 'not_cold_start': {}})
        self.assertEqual(result.spread, {})


class CoverageTests(SimpleTestCase):
    def test_the_shares_are_worked_out_by_hand(self):
        # First freelancer: 4 candidates, 2 scored (a, c), their one right answer (a) is scored: 0.5 and 1.
        # Second: 2 candidates, 1 scored (f), 2 right answers, 1 of them scored: 0.5 and 0.5.
        cases = [case('one', 'abcd', {'a'}), case('two', 'ef', {'e', 'f'})]
        raw = {'one': {'a': 1.0, 'b': None, 'c': 2.0, 'd': None}, 'two': {'e': None, 'f': 3.0}}
        candidates, answers = cmp.collaborative_coverage(cases, raw)
        self.assertAlmostEqual(candidates, 0.5)  # (0.5 + 0.5) / 2
        self.assertAlmostEqual(answers, 0.75)  # (1 + 0.5) / 2

    def test_a_score_of_zero_is_still_a_score(self):
        cases = [case('one', 'ab', {'a'})]
        candidates, answers = cmp.collaborative_coverage(cases, {'one': {'a': 0.0, 'b': None}})
        self.assertEqual((candidates, answers), (0.5, 1.0))

    def test_nobody_gives_nothing_to_average(self):
        self.assertEqual(cmp.collaborative_coverage([], {}), (None, None))


class GroupTests(SimpleTestCase):
    def setUp(self):
        self.cases = [
            case('a', 'xyz', {'x'}, cold_start=True),
            case('b', 'xyz', {'y'}),
            case('c', 'xyz', {'z'}),
            case('nothing', 'xyz', set()),
        ]

    def test_members_leave_out_freelancers_with_nothing_to_find(self):
        members = cmp.group_members(self.cases)
        self.assertEqual([c.freelancer_id for c in members['all']], ['a', 'b', 'c'])
        self.assertEqual([c.freelancer_id for c in members['cold_start']], ['a'])
        self.assertEqual([c.freelancer_id for c in members['not_cold_start']], ['b', 'c'])

    def test_each_group_is_averaged_over_its_own_freelancers(self):
        per_freelancer = {
            'a': {(5, 'precision'): 0.2}, 'b': {(5, 'precision'): 0.4}, 'c': {(5, 'precision'): 0.6}, 'nothing': None,
        }
        groups = cmp.aggregate(per_freelancer, self.cases, seed=42)
        self.assertAlmostEqual(groups['all'][(5, 'precision')].mean, 0.4)
        self.assertEqual(groups['all'][(5, 'precision')].n, 3)
        self.assertAlmostEqual(groups['cold_start'][(5, 'precision')].mean, 0.2)
        self.assertEqual(groups['cold_start'][(5, 'precision')].n, 1)
        self.assertAlmostEqual(groups['not_cold_start'][(5, 'precision')].mean, 0.5)
        self.assertEqual(groups['not_cold_start'][(5, 'precision')].n, 2)

    def test_a_group_with_nobody_in_it_is_empty_not_zero(self):
        warm_only = [case('b', 'xyz', {'y'})]
        groups = cmp.aggregate({'b': {(5, 'precision'): 0.4}}, warm_only, seed=42)
        self.assertEqual(groups['cold_start'], {})

    def test_scoring_rankings_uses_each_freelancers_own_answers(self):
        cases = [case('a', 'xyz', {'x'}), case('b', 'xyz', {'z'})]
        rankings = {'a': ['x', 'y', 'z'], 'b': ['x', 'y', 'z']}
        scored = cmp.score_rankings(rankings, cases, (1,))
        self.assertEqual(scored['a'][(1, 'hit')], 1.0)
        self.assertEqual(scored['b'][(1, 'hit')], 0.0)
