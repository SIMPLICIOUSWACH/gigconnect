import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings

from . import planted
from .evaluation import modes, report
from .evaluation import tuning as tn
from .evaluation.run import run_evaluation
from .evaluation.tuning_run import run_tuning
from .test_evaluation_compare import SMALL_COLLABORATIVE, BlockWorld

LABEL = 'synthetic_planted - demonstrates pipeline mechanics, not real-world accuracy'


class ModeHelperTests(SimpleTestCase):
    def test_the_label_is_exactly_the_agreed_wording(self):
        self.assertEqual(modes.PLANTED_LABEL, LABEL)
        self.assertEqual(modes.label_lines(modes.SYNTHETIC_PLANTED), [f'**Data: {LABEL}.**', ''])
        self.assertEqual(modes.label_lines(modes.SKILL_OVERLAP), [])

    def test_planted_reports_and_test_runs_have_names_of_their_own(self):
        self.assertEqual(modes.report_prefix('tuning', modes.SYNTHETIC_PLANTED), 'tuning-synthetic_planted')
        self.assertEqual(modes.report_prefix('tuning', modes.SKILL_OVERLAP), 'tuning')
        self.assertEqual(modes.test_runs_name(modes.SKILL_OVERLAP), 'evaluation-test-runs.csv')
        self.assertEqual(modes.test_runs_name(modes.SYNTHETIC_PLANTED), 'evaluation-synthetic_planted-test-runs.csv')


@override_settings(DEBUG=True)
class PlantedRunsTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(RECOMMENDER_DATA_DIR=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)
        # Stand-ins for the ordinary split and test-run log, which a planted run must never touch.
        self.ordinary = Path(self.tmp.name) / 'platform' / 'evaluation'
        self.ordinary.mkdir(parents=True)
        (self.ordinary / 'split.csv').write_text('the ordinary split', encoding='utf-8')
        planted.write_world(planted.plan_world(seed=9, sizes=planted.Sizes(freelancers=60, gigs=80, clients=20,
                                                                             favourite_pool=5)))

    def reports(self):
        return Path(self.tmp.name) / 'reports'

    def test_an_evaluation_on_planted_data_is_labelled_and_never_touches_the_ordinary_split(self):
        run = run_evaluation(include_synthetic=True, random_seeds=2)
        self.assertTrue(run.markdown_path.name.startswith('evaluation-synthetic_planted-'))
        text = run.markdown_path.read_text(encoding='utf-8')
        self.assertIn(LABEL, text.splitlines()[2])  # straight under the title
        self.assertIn('Planted synthetic data', text)
        self.assertNotIn('skill-preferring synthetic applications favour the content model', text)
        self.assertEqual((self.ordinary / 'split.csv').read_text(encoding='utf-8'), 'the ordinary split')
        self.assertTrue((self.ordinary / 'synthetic_planted' / 'split.csv').is_file())

    def test_a_planted_test_report_names_its_own_log(self):
        run = run_evaluation(part='test', final=True, include_synthetic=True, random_seeds=2)
        text = run.markdown_path.read_text(encoding='utf-8')
        self.assertIn('recorded in evaluation-synthetic_planted-test-runs.csv', text)
        self.assertNotIn('recorded in evaluation-test-runs.csv', text)

    def test_the_command_prints_the_planted_warning_not_the_skill_overlap_one(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('evaluate_recommender', '--include-synthetic', '--random-seeds', '2', stdout=out)
        self.assertIn('Planted synthetic data', out.getvalue())
        self.assertNotIn('skill-preferring synthetic applications favour', out.getvalue())

    def test_a_planted_test_run_goes_to_its_own_log(self):
        run_evaluation(part='test', final=True, include_synthetic=True, random_seeds=2)
        self.assertEqual(len(report.read_test_runs(self.reports(), modes.SYNTHETIC_PLANTED)), 1)
        self.assertEqual(report.read_test_runs(self.reports(), modes.SKILL_OVERLAP), [])
        self.assertFalse((self.reports() / 'evaluation-test-runs.csv').exists())

    def test_tuning_on_planted_data_is_labelled_scores_group_recovery_and_never_sets_defaults(self):
        run = run_tuning(include_synthetic=True, random_seeds=2)
        self.assertTrue(run.markdown_path.name.startswith('tuning-synthetic_planted-'))
        text = run.markdown_path.read_text(encoding='utf-8')
        self.assertIn(LABEL, text)
        self.assertIn('Planted data never sets the live defaults', text)
        self.assertIn('## Hidden group recovery (planted data only)', text)
        self.assertIn('## Content only, collaborative only and the hybrids', text)
        self.assertIsNotNone(run.recovery)
        self.assertEqual(run.mode, modes.SYNTHETIC_PLANTED)


@override_settings(**SMALL_COLLABORATIVE)
class OrdinaryTuningTests(BlockWorld):
    def test_ordinary_tuning_has_no_label_and_no_group_recovery(self):
        run = run_tuning(include_synthetic=True, random_seeds=2)
        text = run.markdown_path.read_text(encoding='utf-8')
        self.assertIsNone(run.recovery)
        self.assertNotIn('synthetic_planted', text)
        self.assertNotIn('Hidden group recovery', text)
        self.assertIn('## Content only, collaborative only and the hybrids', text)

    def test_the_references_are_content_only_collaborative_only_and_the_hybrids(self):
        context = tn.build_context(self.make_split(), include_synthetic=True)
        trials = tn.run_grid(context)
        current = tn.run_trial(context, tn.current_setting())
        decision = tn.decide(trials, current, random_sd=0.01)
        found = {reference.label: reference for reference in tn.references(context, trials, decision)}
        content = found['Content only']
        weight_zero = tn.run_trial(context, tn.Setting(0.0, 20, tn.CAP, 5))
        self.assertAlmostEqual(content.selection, weight_zero.selection)
        self.assertIn('Collaborative only, 6 factors (the cap)', found)  # 12 freelancers: the cap is 6
        best_hybrid = next(r for label, r in found.items() if label.startswith('Best hybrid'))
        self.assertAlmostEqual(best_hybrid.selection, max(t.selection for t in trials if t.setting.max_weight > 0))

    def test_collaborative_only_is_the_comparison_reports_collaborative_model(self):
        from .evaluation import compare as cmp

        context = tn.build_context(self.make_split(), include_synthetic=True)
        decision = tn.decide([tn.run_trial(context, tn.current_setting())], tn.run_trial(context, tn.current_setting()),
                             random_sd=0.01)
        found = {reference.label: reference for reference in tn.references(context, [], decision)}
        mine = found['Collaborative only, 6 factors (the cap)'].means
        theirs = cmp.compare(self.make_split(), random_seeds=1).results['collaborative_all'].groups['all']
        for key, summary in theirs.items():
            self.assertAlmostEqual(mine[key], summary.mean, msg=str(key))
