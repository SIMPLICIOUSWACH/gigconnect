from django.test import SimpleTestCase, override_settings

from .bands import match_band
from .testing import BAND_CUT_OFFS

SHARED = ['Django']


@override_settings(**BAND_CUT_OFFS)
class MatchBandTests(SimpleTestCase):
    def test_no_score_gives_no_band(self):
        self.assertIsNone(match_band(None, SHARED))

    def test_no_shared_skill_gives_no_band_however_high_the_score(self):
        # A score that comes only from the wording of a bio is not skill overlap.
        self.assertIsNone(match_band(0.9, []))

    def test_the_cut_offs_are_inclusive(self):
        self.assertEqual(match_band(0.30, SHARED), 'strong')
        self.assertEqual(match_band(0.15, SHARED), 'good')

    def test_just_below_a_cut_off_falls_to_the_band_below(self):
        self.assertEqual(match_band(0.2999, SHARED), 'good')
        self.assertEqual(match_band(0.1499, SHARED), 'some')

    def test_a_shared_skill_with_a_tiny_score_is_still_some_overlap(self):
        self.assertEqual(match_band(0.0001, SHARED), 'some')
        self.assertEqual(match_band(0.0, SHARED), 'some')

    def test_high_scores_are_strong(self):
        self.assertEqual(match_band(0.62, SHARED), 'strong')
        self.assertEqual(match_band(1.0, SHARED), 'strong')

    def test_the_cut_offs_come_from_the_settings(self):
        with override_settings(RECOMMENDER_BAND_STRONG=0.5, RECOMMENDER_BAND_GOOD=0.4):
            self.assertEqual(match_band(0.45, SHARED), 'good')
            self.assertEqual(match_band(0.5, SHARED), 'strong')
            self.assertEqual(match_band(0.39, SHARED), 'some')
