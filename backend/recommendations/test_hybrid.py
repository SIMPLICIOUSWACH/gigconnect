import numpy as np
from django.test import SimpleTestCase, override_settings

from . import hybrid

# The starting values from the sprint plan: cold start below 5 gigs, ramp over the next 20, up to 0.5.
PLAN = {
    'RECOMMENDER_COLD_START_MIN_GIGS': 5,
    'RECOMMENDER_BLEND_RAMP_GIGS': 20,
    'RECOMMENDER_BLEND_MAX_WEIGHT': 0.5,
}


class NormaliseTests(SimpleTestCase):
    def test_a_raw_score_is_divided_by_the_scale(self):
        self.assertEqual(hybrid.normalise_collaborative(1.5, 3.0), 0.5)

    def test_scores_above_the_scale_are_clipped_to_one(self):
        self.assertEqual(hybrid.normalise_collaborative(6.0, 3.0), 1.0)

    def test_negative_scores_are_clipped_to_zero(self):
        self.assertEqual(hybrid.normalise_collaborative(-1.0, 3.0), 0.0)

    def test_no_score_stays_no_score_and_is_not_turned_into_zero(self):
        self.assertIsNone(hybrid.normalise_collaborative(None, 3.0))

    def test_without_a_usable_scale_there_is_no_score(self):
        self.assertIsNone(hybrid.normalise_collaborative(1.0, None))
        self.assertIsNone(hybrid.normalise_collaborative(1.0, 0))
        self.assertIsNone(hybrid.normalise_collaborative(1.0, -2.0))

    def test_the_same_raw_score_always_gives_the_same_result(self):
        # The scale is fixed, so a score does not depend on which other gigs are being scored.
        self.assertEqual(hybrid.normalise_collaborative(2.0, 4.0), hybrid.normalise_collaborative(2.0, 4.0))


class CollaborativeScaleTests(SimpleTestCase):
    def test_uses_the_95th_percentile_of_the_positive_scores_on_cells_nobody_touched(self):
        reconstructed = np.array([[3.0, 0.0, 1.0], [0.0, 2.0, 4.0]])
        observed = np.array([[True, False, False], [False, False, True]])
        # Unseen cells hold 0, 1, 0 and 2. The positive ones are 1 and 2, whose 95th percentile is
        # 1 + 0.95 * (2 - 1) = 1.95.
        self.assertAlmostEqual(hybrid.collaborative_scale(reconstructed, observed), 1.95)

    def test_cells_a_freelancer_has_interacted_with_are_ignored(self):
        reconstructed = np.array([[100.0, 1.0]])
        observed = np.array([[True, False]])
        self.assertEqual(hybrid.collaborative_scale(reconstructed, observed), 1.0)

    def test_negative_scores_are_ignored(self):
        reconstructed = np.array([[-5.0, 2.0]])
        observed = np.array([[False, False]])
        self.assertEqual(hybrid.collaborative_scale(reconstructed, observed), 2.0)

    def test_nothing_positive_gives_no_scale(self):
        reconstructed = np.array([[0.0, -1.0]])
        observed = np.array([[False, False]])
        self.assertIsNone(hybrid.collaborative_scale(reconstructed, observed))


@override_settings(**PLAN)
class BlendWeightTests(SimpleTestCase):
    def test_cold_start_gives_zero(self):
        for gigs in range(0, 5):
            self.assertEqual(hybrid.blend_weight(gigs), 0.0)

    def test_the_weight_starts_small_at_the_minimum_and_rises_in_equal_steps(self):
        self.assertAlmostEqual(hybrid.blend_weight(5), 0.5 * 1 / 20)  # 0.025
        self.assertAlmostEqual(hybrid.blend_weight(14), 0.5 * 10 / 20)  # 0.25
        self.assertAlmostEqual(hybrid.blend_weight(24), 0.5)  # the 20th step reaches the maximum

    def test_it_never_goes_above_the_maximum(self):
        for gigs in (25, 50, 1000):
            self.assertAlmostEqual(hybrid.blend_weight(gigs), 0.5)

    def test_it_never_falls_as_history_grows(self):
        weights = [hybrid.blend_weight(n) for n in range(0, 60)]
        self.assertEqual(weights, sorted(weights))

    def test_the_numbers_come_from_the_settings(self):
        with override_settings(
            RECOMMENDER_COLD_START_MIN_GIGS=2, RECOMMENDER_BLEND_RAMP_GIGS=4, RECOMMENDER_BLEND_MAX_WEIGHT=0.8,
        ):
            self.assertEqual(hybrid.blend_weight(1), 0.0)
            self.assertAlmostEqual(hybrid.blend_weight(2), 0.2)
            self.assertAlmostEqual(hybrid.blend_weight(3), 0.4)
            self.assertAlmostEqual(hybrid.blend_weight(5), 0.8)
            self.assertAlmostEqual(hybrid.blend_weight(9), 0.8)

    def test_a_ramp_of_zero_does_not_divide_by_zero(self):
        with override_settings(RECOMMENDER_BLEND_RAMP_GIGS=0):
            self.assertAlmostEqual(hybrid.blend_weight(5), 0.5)

    def test_cold_start_is_the_same_boundary(self):
        self.assertTrue(hybrid.in_cold_start(4))
        self.assertFalse(hybrid.in_cold_start(5))

    def test_the_numbers_can_be_given_instead_of_read_from_the_settings(self):
        # Minimum 0, ramp 5, maximum 1.0: the first gig is step 1 of 5 (0.2), the fifth reaches the maximum.
        self.assertAlmostEqual(hybrid.blend_weight(0, minimum=0, ramp=5, maximum=1.0), 0.2)
        self.assertAlmostEqual(hybrid.blend_weight(2, minimum=0, ramp=5, maximum=1.0), 0.6)
        self.assertAlmostEqual(hybrid.blend_weight(4, minimum=0, ramp=5, maximum=1.0), 1.0)
        self.assertAlmostEqual(hybrid.blend_weight(40, minimum=0, ramp=5, maximum=1.0), 1.0)
        # Minimum 3, ramp 5, maximum 0.75: nothing below 3 gigs, then 0.75 / 5 = 0.15 per step.
        self.assertEqual(hybrid.blend_weight(2, minimum=3, ramp=5, maximum=0.75), 0.0)
        self.assertAlmostEqual(hybrid.blend_weight(3, minimum=3, ramp=5, maximum=0.75), 0.15)
        self.assertAlmostEqual(hybrid.blend_weight(7, minimum=3, ramp=5, maximum=0.75), 0.75)

    def test_a_maximum_of_zero_means_the_collaborative_score_is_never_used(self):
        for gigs in (0, 5, 24, 500):
            self.assertEqual(hybrid.blend_weight(gigs, maximum=0.0), 0.0)

    def test_given_numbers_beat_the_settings_and_left_out_ones_still_come_from_them(self):
        with override_settings(
            RECOMMENDER_COLD_START_MIN_GIGS=2, RECOMMENDER_BLEND_RAMP_GIGS=4, RECOMMENDER_BLEND_MAX_WEIGHT=0.8,
        ):
            self.assertAlmostEqual(hybrid.blend_weight(2, ramp=2), 0.4)  # minimum 2 and maximum 0.8 from settings
            self.assertAlmostEqual(hybrid.blend_weight(2, minimum=0, ramp=4, maximum=1.0), 0.75)


class HybridScoreTests(SimpleTestCase):
    def test_the_blend_is_w_times_collaborative_plus_the_rest_times_content(self):
        score, source = hybrid.hybrid_score(content_score=0.8, collaborative_score=0.4, weight=0.5)
        self.assertAlmostEqual(score, 0.6)
        self.assertEqual(source, 'hybrid')

    def test_another_weight(self):
        score, _ = hybrid.hybrid_score(0.8, 0.4, 0.25)  # 0.25 * 0.4 + 0.75 * 0.8
        self.assertAlmostEqual(score, 0.7)

    def test_a_weight_of_one_is_all_collaborative(self):
        self.assertAlmostEqual(hybrid.hybrid_score(0.8, 0.4, 1.0)[0], 0.4)

    def test_cold_start_weight_gives_the_content_score_labelled_content(self):
        self.assertEqual(hybrid.hybrid_score(0.8, 0.4, 0.0), (0.8, 'content'))

    def test_no_collaborative_score_gives_the_content_score_whatever_the_weight(self):
        self.assertEqual(hybrid.hybrid_score(0.8, None, 0.5), (0.8, 'content'))

    def test_zero_collaborative_is_not_the_same_as_none(self):
        # A real collaborative score of 0 pulls the blend down; no score does not.
        self.assertAlmostEqual(hybrid.hybrid_score(0.8, 0.0, 0.5)[0], 0.4)
        self.assertEqual(hybrid.hybrid_score(0.8, None, 0.5)[0], 0.8)

    def test_scores_in_the_range_stay_in_the_range(self):
        for content in (0.0, 0.3, 1.0):
            for collab in (0.0, 0.6, 1.0):
                for weight in (0.0, 0.25, 0.5, 1.0):
                    score, _ = hybrid.hybrid_score(content, collab, weight)
                    self.assertGreaterEqual(score, 0.0)
                    self.assertLessEqual(score, 1.0)
