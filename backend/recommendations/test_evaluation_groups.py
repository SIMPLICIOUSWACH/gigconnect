import tempfile

from django.test import SimpleTestCase, TestCase, override_settings

from . import planted
from .evaluation import groups
from .evaluation import split as ev
from .evaluation import tuning as tn


class AucTests(SimpleTestCase):
    def test_the_mann_whitney_auc_by_hand(self):
        self.assertEqual(groups.auc([3, 1, 2], [True, False, False]), 1.0)
        self.assertEqual(groups.auc([1, 3, 2], [True, False, False]), 0.0)
        self.assertEqual(groups.auc([2, 2, 2], [True, False, False]), 0.5)

    def test_one_empty_side_has_no_auc(self):
        self.assertIsNone(groups.auc([1, 2], [True, True]))
        self.assertIsNone(groups.auc([1, 2], [False, False]))


class PairAucTests(SimpleTestCase):
    def test_groups_that_sit_apart_are_recovered_perfectly(self):
        vectors = {i: [1.0, 0.0] if i < 3 else [0.0, 1.0] for i in range(6)}
        labels = {i: 'a' if i < 3 else 'b' for i in range(6)}
        self.assertEqual(groups.pair_auc(vectors, labels), 1.0)
        self.assertEqual(groups.per_group_auc(vectors, labels), {'a': 1.0, 'b': 1.0})

    def test_a_worked_case_where_same_group_pairs_are_further_apart(self):
        # Groups a = {1, 2} and b = {3, 4}. Vectors 1 and 3 point one way, 2 and 4 the other. The same-group pairs
        # (1, 2) and (3, 4) have similarity 0. The other pairs: (1, 3) 1, (1, 4) 0, (2, 3) 0, (2, 4) 1. Each
        # same-group pair loses to two and ties with two, so the AUC is (0 + 0.5 + 0.5 + 0) / 4 = 0.25.
        vectors = {1: [1, 0], 2: [0, 1], 3: [1, 0], 4: [0, 1]}
        labels = {1: 'a', 2: 'a', 3: 'b', 4: 'b'}
        self.assertAlmostEqual(groups.pair_auc(vectors, labels), 0.25)

    def test_identical_vectors_tell_nothing(self):
        vectors = {i: [1.0, 1.0] for i in range(6)}
        labels = {i: 'a' if i % 2 else 'b' for i in range(6)}
        self.assertEqual(groups.pair_auc(vectors, labels), 0.5)

    def test_shuffled_labels_give_about_one_half(self):
        vectors = {i: [1.0, 0.0] if i < 10 else [0.0, 1.0] for i in range(20)}
        labels = {i: 'a' if i < 10 else 'b' for i in range(20)}
        mean, sd = groups.shuffled_auc(vectors, labels, draws=40)
        self.assertAlmostEqual(mean, 0.5, delta=0.1)
        self.assertGreater(sd, 0)

    def test_freelancers_missing_from_either_side_are_left_out_and_zero_vectors_do_not_break_it(self):
        vectors = {1: [1, 0], 2: [1, 0], 3: [0, 1], 4: [0, 1], 5: [0, 0]}
        labels = {1: 'a', 2: 'a', 3: 'b', 4: 'b', 9: 'a'}
        self.assertEqual(groups.pair_auc(vectors, labels), 1.0)
        self.assertIsNone(groups.pair_auc({1: [1, 0]}, {1: 'a'}))


@override_settings(DEBUG=True)
class RecoveryOnAPlantedWorldTests(TestCase):
    """A smaller planted world than the default, so the test stays quick, with every step the real run takes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(RECOMMENDER_DATA_DIR=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)
        sizes = planted.Sizes(freelancers=120, gigs=150, clients=30, favourite_pool=6)
        planted.write_world(planted.plan_world(seed=5, sizes=sizes))
        context = tn.build_context(ev.build_split(ev.load_positives(True)), include_synthetic=True)
        self.recovery = groups.recovery(context, planted.read_ground_truth(), tn.FACTORS)
        self.rows = {row['label']: row for row in self.recovery['rows']}

    def test_the_collaborative_factors_recover_the_planted_groups_well_above_chance(self):
        mean, sd = self.recovery['chance']
        best = max(row['auc'] for label, row in self.rows.items() if label.startswith('Collaborative'))
        self.assertGreater(best, 0.6)
        self.assertGreater(best, mean + 10 * sd)

    def test_the_content_profile_does_not_recover_the_groups_because_they_are_not_in_the_text(self):
        content = self.rows['Content profile (skills and bio)']['auc']
        self.assertAlmostEqual(content, 0.5, delta=0.05)

    def test_chance_is_about_one_half(self):
        mean, _ = self.recovery['chance']
        self.assertAlmostEqual(mean, 0.5, delta=0.02)

    def test_every_group_is_scored(self):
        for row in self.recovery['rows']:
            self.assertEqual(set(row['per_group']), set(planted.GROUPS))


