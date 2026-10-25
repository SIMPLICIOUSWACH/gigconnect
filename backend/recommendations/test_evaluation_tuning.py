import csv
import inspect
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from accounts.models import User

from . import hybrid
from .evaluation import compare as cmp
from .evaluation import tuning as tn
from .evaluation import tuning_report
from .evaluation.tuning_run import run_tuning
from .test_evaluation_compare import SMALL_COLLABORATIVE, BlockWorld


def trial(selection, per_freelancer=None, setting=None, components=15):
    """A made-up trial, for testing the decision on its own."""
    setting = setting or tn.Setting(0.5, 20, 15, 5)
    return tn.Trial(
        setting=setting, components=components, means={}, selection=selection,
        per_freelancer=per_freelancer or {i: selection for i in range(10)},
    )


class GridTests(SimpleTestCase):
    def test_there_are_240_distinct_combinations(self):
        combinations = tn.grid()
        self.assertEqual(len(combinations), 5 * 3 * 4 * 4)
        self.assertEqual(len(set(combinations)), 240)

    def test_every_value_is_tried_with_every_other(self):
        combinations = tn.grid()
        for weight in (0.0, 0.25, 0.5, 0.75, 1.0):
            self.assertEqual(sum(1 for c in combinations if c.max_weight == weight), 3 * 4 * 4)
        for ramp in (5, 20, 50):
            self.assertEqual(sum(1 for c in combinations if c.ramp == ramp), 5 * 4 * 4)
        for factors in (2, 5, 10, tn.CAP):
            self.assertEqual(sum(1 for c in combinations if c.factors == factors), 5 * 3 * 4)
        for cold in (0, 3, 5, 10):
            self.assertEqual(sum(1 for c in combinations if c.cold_start == cold), 5 * 3 * 4)

    def test_the_order_is_fixed(self):
        self.assertEqual(tn.grid(), tn.grid())
        self.assertEqual(tn.grid()[0], tn.Setting(0.0, 5, 2, 0))

    def test_the_current_setting_is_read_from_the_settings(self):
        with override_settings(
            RECOMMENDER_BLEND_MAX_WEIGHT=0.3, RECOMMENDER_BLEND_RAMP_GIGS=7, RECOMMENDER_SVD_COMPONENTS=9,
            RECOMMENDER_COLD_START_MIN_GIGS=4,
        ):
            self.assertEqual(tn.current_setting(), tn.Setting(0.3, 7, 9, 4))


class QuantileTests(SimpleTestCase):
    def test_percentiles_of_one_to_nine_are_worked_out_by_hand(self):
        # Linear interpolation: the 50th is the middle value 5, the 75th is 7, the 90th sits at position 7.2 of 0 to 8
        # so 8 + 0.2 = 8.2, and the 95th at position 7.6, so 8.6.
        found = tn.quantiles(list(range(1, 10)))
        self.assertEqual(found['n'], 9)
        self.assertAlmostEqual(found['p50'], 5.0)
        self.assertAlmostEqual(found['p75'], 7.0)
        self.assertAlmostEqual(found['p90'], 8.2)
        self.assertAlmostEqual(found['p95'], 8.6)

    def test_no_scores_gives_nothing_to_derive(self):
        found = tn.quantiles([])
        self.assertEqual(found['n'], 0)
        self.assertIsNone(found['p50'])
        self.assertIsNone(tn.suggested_bands({'candidates': found, 'applicants': found}))

    def test_good_is_the_median_and_strong_the_90th_percentile_to_two_places(self):
        evidence = {'candidates': tn.quantiles(list(range(1, 10))), 'applicants': tn.quantiles([])}
        self.assertEqual(tn.suggested_bands(evidence), {'good': 5.0, 'strong': 8.2})


class DecisionTests(SimpleTestCase):
    """The rule: change only if the gain beats the random spread AND the paired interval is wholly above zero."""

    def test_nothing_better_than_the_current_settings_changes_nothing(self):
        current = trial(0.05)
        decision = tn.decide([current, trial(0.04), trial(0.03)], current, random_sd=0.01)
        self.assertFalse(decision.changed)
        self.assertEqual(decision.gain, 0.0)
        self.assertIs(decision.best, current)

    def test_a_gain_smaller_than_the_random_spread_is_not_enough_even_if_it_is_steady(self):
        current = trial(0.05)
        better = trial(0.06, {i: 0.06 for i in range(10)})  # +0.01 for every freelancer, so the interval is above 0
        decision = tn.decide([better], current, random_sd=0.02)
        self.assertFalse(decision.changed)
        self.assertGreater(decision.paired_low, 0)
        self.assertAlmostEqual(decision.gain, 0.01)

    def test_a_gain_larger_than_the_spread_is_not_enough_if_the_interval_includes_zero(self):
        # Half the freelancers gain 0.3 and half lose 0.2: the average gain is 0.05 but it is not steady.
        current = trial(0.1, {i: 0.1 for i in range(10)})
        swings = {i: 0.4 if i % 2 == 0 else -0.1 for i in range(10)}
        better = trial(0.15, {i: swings[i] for i in range(10)})
        decision = tn.decide([better], current, random_sd=0.01)
        self.assertAlmostEqual(decision.gain, 0.05)
        self.assertLess(decision.paired_low, 0)
        self.assertFalse(decision.changed)
        self.assertIn('includes zero', ' '.join(decision.reasons))

    def test_both_conditions_together_change_the_defaults(self):
        current = trial(0.05)
        better = trial(0.15, {i: 0.15 for i in range(10)})
        decision = tn.decide([better], current, random_sd=0.02)
        self.assertTrue(decision.changed)
        self.assertAlmostEqual(decision.gain, 0.10)
        self.assertEqual((decision.paired_low, decision.paired_high), (decision.gain, decision.gain))
        self.assertIn('the defaults change', decision.reasons[-1])

    def test_equal_scores_go_to_the_combination_closest_to_the_current_settings(self):
        current = trial(0.02, setting=tn.Setting(0.5, 20, 15, 5), components=15)
        far = trial(0.09, setting=tn.Setting(0.0, 5, 2, 0), components=2)  # four settings differ
        near = trial(0.09, setting=tn.Setting(0.0, 20, 15, 5), components=15)  # only the weight differs
        for ordering in ([far, near], [near, far]):
            self.assertIs(tn.decide(ordering, current, random_sd=0.01).best, near)

    def test_it_counts_the_combinations_that_beat_the_current_ones_and_that_cannot_be_told_from_the_best(self):
        current = trial(0.05)
        trials = [trial(0.10), trial(0.095), trial(0.085), trial(0.055), trial(0.04)]
        decision = tn.decide(trials, current, random_sd=0.02)
        # Beat the current 0.05 by more than 0.02: 0.10, 0.095 and 0.085. Within 0.02 of the best 0.10: the same three.
        self.assertEqual(decision.beat_by_more_than_luck, 3)
        self.assertEqual(decision.within_luck_of_best, 3)

    def test_the_paired_interval_uses_the_same_freelancers_for_both(self):
        current = trial(0.1, {'a': 0.1, 'b': 0.2})
        better = trial(0.3, {'a': 0.3, 'b': 0.3})
        decision = tn.decide([better], current, random_sd=0.0)
        # The differences are 0.2 and 0.1, so the average gain is 0.15 and the interval is inside 0.1 to 0.2.
        self.assertAlmostEqual(decision.gain, 0.2)  # selections are given directly, as 0.3 and 0.1
        self.assertGreaterEqual(decision.paired_low, 0.1 - 1e-9)
        self.assertLessEqual(decision.paired_high, 0.2 + 1e-9)


@override_settings(**SMALL_COLLABORATIVE)
class BlockWorldTuningTests(BlockWorld):
    """The block world again: one right answer each, 33 candidates, history of 6 gigs for every freelancer."""

    def context(self):
        if not hasattr(self, '_context'):
            self._context = tn.build_context(self.make_split(), include_synthetic=True)
        return self._context

    def test_it_scores_the_12_validation_freelancers_and_nobody_else(self):
        context = self.context()
        self.assertEqual(len(context.cases), 12)
        self.assertEqual({len(case.candidates) for case in context.cases}, {33})
        self.assertEqual(set(context.history.values()), {6})

    def test_the_factors_asked_for_and_the_factors_used_follow_the_cap_of_half_the_smaller_side(self):
        # 12 freelancers by 40 gigs: the cap is 12 // 2 = 6, so 10 and the cap both give 6, and 2 gives 2.
        used = {factors: model.n_components for factors, model in self.context().collaborative.items()}
        self.assertEqual(used, {2: 2, 5: 5, 10: 6, tn.CAP: 6, 20: 6})

    def test_the_current_settings_give_exactly_the_hybrid_the_comparison_reports(self):
        context = self.context()
        mine = tn.run_trial(context, tn.current_setting())
        theirs = cmp.compare(self.make_split(), random_seeds=1).results['hybrid'].groups['all']
        for key, summary in theirs.items():
            self.assertAlmostEqual(mine.means[key], summary.mean, msg=str(key))

    def test_a_largest_weight_of_zero_is_the_content_model_exactly(self):
        context = self.context()
        zero = tn.run_trial(context, tn.Setting(0.0, 20, tn.CAP, 5))
        content = cmp.compare(self.make_split(), random_seeds=1).results['content'].groups['all']
        for key, summary in content.items():
            self.assertAlmostEqual(zero.means[key], summary.mean, msg=str(key))

    def test_when_the_largest_weight_is_zero_the_other_settings_make_no_difference(self):
        context = self.context()
        values = {
            round(tn.run_trial(context, tn.Setting(0.0, ramp, factors, cold)).selection, 12)
            for ramp in tn.RAMPS for factors in tn.FACTORS for cold in tn.COLD_STARTS
        }
        self.assertEqual(len(values), 1)

    def test_the_selection_value_follows_from_the_hit_rates(self):
        # One right answer each, so F1@K is 2 * hit / (K + 1) for every freelancer, and the selection value is the mean
        # of F1@5 and F1@10: (2 * hit5 / 6 + 2 * hit10 / 11) / 2.
        result = tn.run_trial(self.context(), tn.current_setting())
        expected = (2 * result.means[(5, 'hit')] / 6 + 2 * result.means[(10, 'hit')] / 11) / 2
        self.assertAlmostEqual(result.selection, expected)

    def test_the_blend_is_the_weighted_sum_with_the_weight_worked_out_by_hand(self):
        # Six gigs of history, cold start below 5, ramp 50, largest weight 0.5: step 2 of 50, so w = 0.5 * 2 / 50.
        context = self.context()
        setting = tn.Setting(0.5, 50, tn.CAP, 5)
        self.assertAlmostEqual(hybrid.blend_weight(6, minimum=5, ramp=50, maximum=0.5), 0.02)
        case = context.cases[0]
        model = context.collaborative[tn.CAP]
        scores = tn.blended_scores(context, setting, case)
        for gig_id, content_score in context.content[case.freelancer_id].items():
            raw = context.raw[tn.CAP][case.freelancer_id][gig_id]
            expected = 0.02 * min(1.0, max(0.0, raw / model.scale)) + 0.98 * content_score
            self.assertAlmostEqual(scores[gig_id], expected)

    def test_a_cold_start_threshold_above_the_history_means_content_only(self):
        context = self.context()
        case = context.cases[0]
        scores = tn.blended_scores(context, tn.Setting(1.0, 5, tn.CAP, 10), case)  # 6 gigs is below 10
        self.assertEqual(scores, context.content[case.freelancer_id])

    def test_a_quicker_ramp_puts_more_weight_on_the_collaborative_score(self):
        quick = hybrid.blend_weight(6, minimum=5, ramp=5, maximum=0.5)
        slow = hybrid.blend_weight(6, minimum=5, ramp=50, maximum=0.5)
        self.assertGreater(quick, slow)

    def test_the_collaborative_scores_beat_chance_in_the_world_built_to_have_a_pattern(self):
        # Chance by hand: one right answer among 33, so a random top 5 holds it 5/33 of the time and a top 10 10/33.
        # F1 is then 2/6 and 2/11, so the selection value is (2/6 * 5/33 + 2/11 * 10/33) / 2, about 0.053. The best
        # possible is (2/6 + 2/11) / 2, about 0.258. Twenty seeds keep the estimate of the spread steady; five did not.
        chance = (2 / 6 * 5 / 33 + 2 / 11 * 10 / 33) / 2
        context = self.context()
        spread = tn.random_spread(context, seeds=20)
        full = tn.run_trial(context, tn.Setting(1.0, 5, tn.CAP, 0))
        self.assertAlmostEqual(spread['mean'], chance, delta=0.03)
        self.assertGreater(full.selection, spread['mean'] + 4 * spread['sd'])
        self.assertGreater(full.selection, 3 * chance)

    def test_the_random_spread_is_a_standard_deviation_across_seeds_and_repeats(self):
        context = self.context()
        first, again = tn.random_spread(context, seeds=6), tn.random_spread(context, seeds=6)
        self.assertEqual(first, again)
        self.assertGreater(first['sd'], 0)
        self.assertLessEqual(first['low'], first['mean'])
        self.assertGreaterEqual(first['high'], first['mean'])
        self.assertEqual(tn.random_spread(context, seeds=1)['sd'], 0.0)

    def test_best_hybrid_against_content_only_uses_the_best_weighted_combination_and_a_weight_of_zero(self):
        context = self.context()
        trials = tn.run_grid(context)
        current = tn.run_trial(context, tn.current_setting())
        comparisons = dict(tn.against_content(context, trials, current, random_sd=0.01))
        found = comparisons['Best hybrid']
        self.assertGreater(found.better.setting.max_weight, 0)
        self.assertAlmostEqual(found.better.selection, max(t.selection for t in trials if t.setting.max_weight > 0))
        self.assertEqual(found.baseline.setting.max_weight, 0.0)
        content_only = cmp.compare(self.make_split(), random_seeds=1).results['content'].groups['all']
        self.assertAlmostEqual(found.baseline.means[(10, 'f1')], content_only[(10, 'f1')].mean)
        self.assertAlmostEqual(found.gain, found.better.selection - found.baseline.selection)

    def test_the_current_settings_get_their_own_row_only_when_they_blend_and_are_not_the_best(self):
        context = self.context()
        blending_current = tn.run_trial(context, tn.current_setting())  # largest weight 0.5 here
        other = tn.run_trial(context, tn.Setting(1.0, 5, tn.CAP, 0))
        labels = [label for label, _ in tn.against_content(context, [other], blending_current, random_sd=0.01)]
        self.assertEqual(labels, ['Best hybrid', 'Current settings'])
        content_current = tn.run_trial(context, tn.Setting(0.0, 20, tn.CAP, 5))
        labels = [label for label, _ in tn.against_content(context, [other], content_current, random_sd=0.01)]
        self.assertEqual(labels, ['Best hybrid'])

    def test_the_band_evidence_counts_only_pairs_that_share_a_skill(self):
        # Each freelancer shares a skill with their own block's 13 candidates (20 gigs, less 6 in train and 1 held out
        # in the other part) and none of the other block's 20, and their one right answer is in their own block.
        evidence = tn.band_evidence(self.context())
        self.assertEqual(evidence['candidates']['n'], 12 * 13)
        self.assertEqual(evidence['applicants']['n'], 12)
        self.assertGreater(evidence['candidates']['p50'], 0.0)
        self.assertLessEqual(evidence['candidates']['p50'], evidence['candidates']['p90'])


@override_settings(**SMALL_COLLABORATIVE)
class TuningRunTests(BlockWorld):
    def run_it(self, **kwargs):
        kwargs.setdefault('include_synthetic', True)
        kwargs.setdefault('random_seeds', 3)
        return run_tuning(**kwargs)

    def rows(self, run):
        with open(run.csv_path, newline='', encoding='utf-8-sig') as handle:
            return list(csv.DictReader(handle))

    def test_it_writes_a_report_and_a_csv_with_all_240_combinations(self):
        run = self.run_it()
        self.assertTrue(run.markdown_path.name.startswith('tuning-'))
        self.assertTrue(run.markdown_path.is_file() and run.csv_path.is_file())
        rows = self.rows(run)
        self.assertEqual(list(rows[0]), tuning_report.CSV_COLUMNS)
        self.assertEqual(len(rows), 240)
        self.assertEqual(len({(r['max_weight'], r['ramp'], r['factors'], r['cold_start']) for r in rows}), 240)

    def test_the_csv_marks_the_current_settings_and_the_best(self):
        rows = self.rows(self.run_it())
        current = [r for r in rows if r['is_current'] == 'True']
        self.assertTrue(current)
        for row in current:
            self.assertEqual((row['max_weight'], row['ramp'], row['cold_start']), ('0.5', '20', '5'))
        self.assertTrue(any(r['is_best'] == 'True' for r in rows))
        self.assertEqual(min(int(r['rank']) for r in rows), 1)

    def test_the_csv_numbers_agree_with_the_run(self):
        run = self.run_it()
        wanted = ('0.0', '5', '2', '0')
        row = next(
            r for r in self.rows(run) if (r['max_weight'], r['ramp'], r['factors'], r['cold_start']) == wanted
        )
        expected = next(t for t in run.trials if t.setting == tn.Setting(0.0, 5, 2, 0))
        self.assertAlmostEqual(float(row['selection']), expected.selection)
        self.assertAlmostEqual(float(row['f1_at_10']), expected.means[(10, 'f1')])
        self.assertAlmostEqual(float(row['hit_at_20']), expected.means[(20, 'hit')])

    def test_the_report_says_what_was_tuned_what_was_not_and_what_it_decided(self):
        text = self.run_it().markdown_path.read_text(encoding='utf-8')
        for expected in (
            '# Tuning on the validation part', '240 combinations', 'Not tuned: the interaction weights',
            'The test part was not used', '## How the choice is made', '## Result',
            '## What each setting does on average', '## Match band cut-offs', 'These stay provisional',
            'Best combination for each largest collaborative weight',
        ):
            self.assertIn(expected, text)
        self.assertTrue('the defaults change' in text or 'the current values stay' in text)
        self.assertNotIn('—', text)

    def test_the_synthetic_warning_appears_only_for_mostly_synthetic_data(self):
        self.assertNotIn('Warning: this is mostly synthetic', self.run_it().markdown_path.read_text(encoding='utf-8'))
        User.objects.update(is_synthetic=True)
        warned = self.run_it(rebuild_split=True).markdown_path.read_text(encoding='utf-8')
        self.assertIn('Warning: this is mostly synthetic data', warned)
        self.assertIn('favour the content model by construction', warned)

    def test_a_second_run_the_same_day_keeps_the_first_report(self):
        first, second = self.run_it(), self.run_it()
        self.assertNotEqual(first.markdown_path, second.markdown_path)
        self.assertTrue(first.markdown_path.is_file())

    def test_tuning_has_no_way_to_ask_for_the_test_part(self):
        self.assertNotIn('part', inspect.signature(run_tuning).parameters)
        with self.assertRaises(CommandError):
            call_command('tune_recommender', '--split', 'test', stdout=StringIO())

    def test_only_the_validation_part_is_ever_scored(self):
        seen = []
        real = tn.build_cases

        def watching(split, part, *args, **kwargs):
            seen.append(part)
            return real(split, part, *args, **kwargs)

        with mock.patch.object(tn, 'build_cases', watching):
            self.run_it()
        self.assertEqual(set(seen), {'validation'})

    def test_it_never_changes_a_setting(self):
        before = (
            settings.RECOMMENDER_BLEND_MAX_WEIGHT, settings.RECOMMENDER_BLEND_RAMP_GIGS,
            settings.RECOMMENDER_SVD_COMPONENTS, settings.RECOMMENDER_COLD_START_MIN_GIGS,
            settings.RECOMMENDER_BAND_GOOD, settings.RECOMMENDER_BAND_STRONG,
        )
        self.run_it()
        after = (
            settings.RECOMMENDER_BLEND_MAX_WEIGHT, settings.RECOMMENDER_BLEND_RAMP_GIGS,
            settings.RECOMMENDER_SVD_COMPONENTS, settings.RECOMMENDER_COLD_START_MIN_GIGS,
            settings.RECOMMENDER_BAND_GOOD, settings.RECOMMENDER_BAND_STRONG,
        )
        self.assertEqual(before, after)

    def test_the_command_prints_the_decision_and_says_nothing_was_changed(self):
        out = StringIO()
        call_command('tune_recommender', '--include-synthetic', '--random-seeds', '3', stdout=out)
        output = out.getvalue()
        self.assertIn('Tried 240 combinations on the validation part.', output)
        self.assertIn('No setting was changed. The test part was not used.', output)
        self.assertIn('All combinations: ', output)
        self.assertTrue(list(Path(self.tmp.name).glob('reports/tuning-*.csv')))


class PairedTests(SimpleTestCase):
    def test_the_gain_and_its_paired_interval_by_hand(self):
        # Every freelancer gains exactly 0.05, so the gain is 0.05 and the interval has no width.
        better = trial(0.15, {i: 0.15 for i in range(8)})
        baseline = trial(0.10, {i: 0.10 for i in range(8)})
        found = tn.paired(better, baseline, random_sd=0.02)
        self.assertAlmostEqual(found.gain, 0.05)
        self.assertAlmostEqual(found.low, 0.05)
        self.assertAlmostEqual(found.high, 0.05)
        self.assertTrue(found.beats_luck and found.above_zero)

    def test_an_unsteady_gain_has_an_interval_that_reaches_below_zero(self):
        better = trial(0.15, {i: 0.4 if i % 2 == 0 else -0.1 for i in range(10)})
        baseline = trial(0.10, {i: 0.10 for i in range(10)})
        found = tn.paired(better, baseline, random_sd=0.2)
        self.assertLess(found.low, 0)
        self.assertFalse(found.above_zero)
        self.assertFalse(found.beats_luck)  # 0.05 is not above 0.2


class MarginalTests(SimpleTestCase):
    def test_the_averages_are_over_the_combinations_with_that_value(self):
        trials = [
            trial(0.10, setting=tn.Setting(0.0, 5, 2, 0)), trial(0.10, setting=tn.Setting(0.0, 20, 2, 0)),
            trial(0.02, setting=tn.Setting(0.5, 5, 2, 0)), trial(0.04, setting=tn.Setting(0.5, 20, 2, 0)),
        ]
        text = '\n'.join(tuning_report.marginal_lines(trials))
        self.assertIn('| Largest collaborative weight | 0 | 0.100 |', text)
        self.assertIn('| Largest collaborative weight | 0.5 | 0.030 |', text)
        # The ramp only counts combinations with a weight above 0: ramp 5 is 0.02 and ramp 20 is 0.04.
        self.assertIn('| Ramp (gigs) | 5 | 0.020 |', text)
        self.assertIn('| Ramp (gigs) | 20 | 0.040 |', text)

