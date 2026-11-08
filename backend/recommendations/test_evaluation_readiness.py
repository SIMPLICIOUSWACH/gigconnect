import tempfile
from collections import Counter
from io import StringIO
from pathlib import Path

import numpy as np
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from scipy.sparse import csr_matrix

from . import planted
from .evaluation import readiness
from .test_evaluation_compare import BlockWorld


def sparse_random(rows, columns, density, seed):
    rng = np.random.RandomState(seed)
    dense = (rng.random_sample((rows, columns)) < density) * rng.choice([1.0, 2.0, 3.0], size=(rows, columns))
    return csr_matrix(dense)


def planted_blocks(seed):
    """40 freelancers and 60 gigs in 4 blocks: a freelancer fills half their own block and 2% of the rest."""
    rng = np.random.RandomState(seed)
    dense = np.zeros((40, 60))
    for row in range(40):
        group = row % 4
        for column in range(60):
            chance = 0.5 if column // 15 == group else 0.02
            dense[row, column] = 3.0 if rng.random_sample() < chance else 0.0
    return csr_matrix(dense)


class NullTests(SimpleTestCase):
    def setUp(self):
        self.matrix = sparse_random(30, 50, 0.1, seed=1)
        self.rng = np.random.RandomState(0)

    def test_the_uniform_null_keeps_the_shape_the_count_and_the_values(self):
        null = readiness.uniform_null(self.matrix, self.rng)
        self.assertEqual(null.shape, self.matrix.shape)
        self.assertEqual(null.nnz, self.matrix.nnz)
        self.assertEqual(sorted(null.data), sorted(self.matrix.data))

    def test_the_same_counts_null_keeps_every_freelancer_and_gig_count_exactly(self):
        null = readiness.degree_preserving_null(self.matrix, self.rng)
        self.assertEqual(null.nnz, self.matrix.nnz)  # a duplicate cell would have been summed into one
        self.assertEqual(list(np.diff(null.indptr)), list(np.diff(self.matrix.indptr)))
        self.assertEqual(list((null > 0).sum(axis=0).A1), list((self.matrix > 0).sum(axis=0).A1))

    def test_the_same_counts_null_keeps_each_freelancers_values(self):
        null = readiness.degree_preserving_null(self.matrix, self.rng)
        for row in range(self.matrix.shape[0]):
            self.assertEqual(
                Counter(null.getrow(row).data.tolist()), Counter(self.matrix.getrow(row).data.tolist()), row,
            )

    def test_the_same_counts_null_really_moves_cells(self):
        null = readiness.degree_preserving_null(self.matrix, self.rng)
        moved = (null != self.matrix).nnz
        self.assertGreater(moved, self.matrix.nnz // 2)


class CurveTests(SimpleTestCase):
    def test_planted_blocks_are_well_above_both_random_matrices(self):
        rows = readiness.curve(planted_blocks(3), ks=[2, 4], draws=5)
        for row in rows:
            self.assertTrue(row.above_uniform, row)
            self.assertTrue(row.above_degree, row)

    def test_a_random_matrix_is_not_above_either(self):
        rows = readiness.curve(sparse_random(40, 60, 0.08, seed=4), ks=[2, 5, 10], draws=10)
        for row in rows:
            self.assertFalse(row.above_uniform, row)
            self.assertFalse(row.above_degree, row)

    def test_the_rule_needs_three_standard_deviations_and_one_point(self):
        above = readiness.CurveRow(k=2, real=0.30, uniform_mean=0.28, uniform_sd=0.005, degree_mean=0.288,
                                   degree_sd=0.005, )
        self.assertTrue(above.above_uniform)  # 0.02 beats both 3 x 0.005 = 0.015 and 0.01
        self.assertFalse(above.above_degree)  # 0.012 is below 0.015
        tiny_spread = readiness.CurveRow(k=2, real=0.30, uniform_mean=0.291, uniform_sd=0.001, degree_mean=0.2895,
                                         degree_sd=0.0)
        self.assertFalse(tiny_spread.above_uniform)  # 0.009 is below the one point margin
        self.assertTrue(tiny_spread.above_degree)  # 0.0105 is above it, and with no spread that is enough

    def test_the_ks_checked_fit_the_matrix(self):
        self.assertEqual(readiness.ks_for((31, 242)), [2, 5, 10, 15])
        self.assertEqual(readiness.ks_for((250, 251)), [2, 5, 10, 15, 25, 50, 125])
        self.assertEqual(readiness.ks_for((4, 10)), [2])


class CheckOnTheBlockWorldTests(BlockWorld):
    def test_it_reads_the_train_part_and_reports_the_matrix(self):
        found = readiness.check(self.make_split(), True, draws=3)
        self.assertEqual(found.shape, (12, 40))
        self.assertEqual(found.filled, 72)  # 12 freelancers x 6 train applications
        self.assertEqual(found.applications_per_freelancer, (6, 6, 6))
        self.assertEqual(found.gigs_with_applicants, 40)
        self.assertEqual([row.k for row in found.rows], readiness.ks_for((12, 40)))

    def test_the_command_writes_a_report_without_the_planted_label(self):
        out = StringIO()
        call_command('check_collaborative_readiness', '--include-synthetic', '--draws', '3', stdout=out)
        report = next((Path(self.tmp.name) / 'reports').glob('readiness-*.md'))
        self.assertTrue(report.name.startswith('readiness-2'))
        text = report.read_text(encoding='utf-8')
        self.assertIn('## Explained variance against random matrices', text)
        self.assertNotIn('synthetic_planted', text)
        self.assertIn('Structure above uniform random', out.getvalue())


@override_settings(DEBUG=True)
class CheckOnAPlantedWorldTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(RECOMMENDER_DATA_DIR=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)
        sizes = planted.Sizes(freelancers=80, gigs=100, clients=20, favourite_pool=5)
        planted.write_world(planted.plan_world(seed=3, sizes=sizes))

    def test_the_planted_world_shows_structure_above_both_random_matrices_and_is_labelled(self):
        out = StringIO()
        call_command('check_collaborative_readiness', '--draws', '5', stdout=out)
        report = next((Path(self.tmp.name) / 'reports').glob('readiness-synthetic_planted-*.md'))
        text = report.read_text(encoding='utf-8')
        self.assertIn('synthetic_planted - demonstrates pipeline mechanics, not real-world accuracy', text)
        self.assertIn('Structure above a uniform random matrix: **yes**', text)
        self.assertIn('Structure above a random matrix with the same counts: **yes**', text)
        self.assertTrue((Path(self.tmp.name) / 'platform' / 'evaluation' / 'synthetic_planted' / 'split.csv').is_file())
        self.assertFalse((Path(self.tmp.name) / 'platform' / 'evaluation' / 'split.csv').exists())
