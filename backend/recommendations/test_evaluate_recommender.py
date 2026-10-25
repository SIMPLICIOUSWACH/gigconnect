import csv
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from accounts.models import User
from applications.models import Application

from .evaluation import report, report_markdown
from .evaluation.compare import METHODS
from .evaluation.fitting import EvaluationError
from .evaluation.run import run_evaluation
from .test_evaluation_compare import SMALL_COLLABORATIVE, BlockWorld


class FakeComparison(SimpleNamespace):
    """Just enough of a Comparison for the pieces of the report that only read counts."""


def fake(part='validation', positives=100, synthetic=0, sizes=None):
    empty = SimpleNamespace(available=True, groups={}, note='')
    return FakeComparison(
        part=part, info={'positives': positives, 'synthetic_positives': synthetic},
        group_sizes=sizes or {'all': 0, 'cold_start': 0, 'not_cold_start': 0},
        results={method: empty for method in METHODS},
    )


class WarningTests(SimpleTestCase):
    def test_mostly_synthetic_means_more_than_half(self):
        self.assertFalse(report.mostly_synthetic(fake(positives=100, synthetic=50)))
        self.assertTrue(report.mostly_synthetic(fake(positives=100, synthetic=51)))
        self.assertFalse(report.mostly_synthetic(fake(positives=0, synthetic=0)))

    def test_the_warning_names_the_bias_toward_the_content_model(self):
        text = '\n'.join(report_markdown.warning_lines(fake(positives=92, synthetic=92)))
        self.assertIn('Warning: this is mostly synthetic data', text)
        self.assertIn('92 of the 92 applications in the validation part are synthetic (100%)', text)
        self.assertIn('skill-preferring synthetic applications favour the content model by', text)
        self.assertIn('construction', text)

    def test_without_much_synthetic_data_there_is_a_share_but_no_warning(self):
        text = '\n'.join(report_markdown.warning_lines(fake(positives=100, synthetic=10)))
        self.assertNotIn('Warning', text)
        self.assertIn('10 of the 100 applications in the validation part are synthetic (10%)', text)


class StrictSectionTests(SimpleTestCase):
    def strict(self, freelancers, relevant):
        found = fake(sizes={'all': freelancers, 'cold_start': 0, 'not_cold_start': freelancers})
        found.info['relevant'] = relevant
        return found

    def test_too_few_freelancers_is_flagged_as_not_a_finding(self):
        text = '\n'.join(report_markdown.strict_lines(self.strict(12, 13)))
        self.assertIn('13 right answers over 12 freelancers', text)
        self.assertIn('too few to draw a conclusion', text)

    def test_enough_freelancers_has_no_such_flag(self):
        self.assertNotIn('too few', '\n'.join(report_markdown.strict_lines(self.strict(20, 25))))


class ReportNamingAndLogTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def test_the_first_report_of_the_day_has_the_plain_name(self):
        self.assertEqual(report.next_stem(self.folder, date(2026, 10, 25)), 'evaluation-2026-10-25')

    def test_a_second_report_the_same_day_does_not_overwrite_the_first(self):
        (self.folder / 'evaluation-2026-10-25.md').write_text('first')
        self.assertEqual(report.next_stem(self.folder, date(2026, 10, 25)), 'evaluation-2026-10-25-2')
        (self.folder / 'evaluation-2026-10-25-2.csv').write_text('second')
        self.assertEqual(report.next_stem(self.folder, date(2026, 10, 25)), 'evaluation-2026-10-25-3')

    def test_no_test_runs_have_been_recorded_in_a_new_folder(self):
        self.assertEqual(report.read_test_runs(self.folder), [])

    def test_recorded_test_runs_are_read_back_in_order(self):
        report.record_test_run(self.folder, {'when': 'first', 'split_fingerprint': 'abc', 'report': 'a.md'})
        report.record_test_run(self.folder, {'when': 'second', 'split_fingerprint': 'abc', 'report': 'b.md'})
        runs = report.read_test_runs(self.folder)
        self.assertEqual([run['when'] for run in runs], ['first', 'second'])
        self.assertEqual(runs[0]['report'], 'a.md')


@override_settings(**SMALL_COLLABORATIVE)
class RunEvaluationTests(BlockWorld):
    """The block world from the comparison tests, run all the way through to the files."""

    def run_it(self, **kwargs):
        kwargs.setdefault('include_synthetic', True)
        kwargs.setdefault('random_seeds', 3)
        kwargs.setdefault('command', 'python manage.py evaluate_recommender --split validation')
        return run_evaluation(**kwargs)

    def folder(self):
        return Path(self.tmp.name) / 'reports'

    def read_csv(self, run):
        with open(run.csv_path, newline='', encoding='utf-8-sig') as handle:
            return list(csv.DictReader(handle))

    def test_it_writes_a_report_and_a_csv_with_todays_name(self):
        run = self.run_it()
        today = date.today().isoformat()
        self.assertEqual(run.markdown_path, self.folder() / f'evaluation-{today}.md')
        self.assertEqual(run.csv_path, self.folder() / f'evaluation-{today}.csv')
        self.assertTrue(run.markdown_path.is_file() and run.csv_path.is_file())

    def test_a_second_run_the_same_day_keeps_the_first_report(self):
        first, second = self.run_it(), self.run_it()
        self.assertNotEqual(first.markdown_path, second.markdown_path)
        self.assertTrue(first.markdown_path.is_file() and second.markdown_path.is_file())
        self.assertTrue(second.markdown_path.name.endswith('-2.md'))

    def test_the_report_has_every_section_and_every_method(self):
        text = self.run_it().markdown_path.read_text(encoding='utf-8')
        for heading in (
            '# Recommender evaluation: validation part', '## What was run', '## The data', '## Models and parameters',
            '## Headline results (K = 5 and 10)', '## Supplementary: K = 20 and hit rate',
            '## Random baseline: how far luck alone moves a result', '## What the collaborative models could score',
            '## Cold start', '## Strict relevance', '## How to read these numbers',
        ):
            self.assertIn(heading, text, heading)
        for label in report.LABELS.values():
            self.assertIn(f'| {label} |', text, label)
        self.assertIn('fingerprint', text)
        self.assertIn('--split validation', text)

    def test_the_report_has_no_em_dashes(self):
        self.assertNotIn('—', self.run_it().markdown_path.read_text(encoding='utf-8'))

    def test_no_warning_when_the_data_is_not_synthetic_and_a_warning_when_it_is(self):
        plain = self.run_it().markdown_path.read_text(encoding='utf-8')
        self.assertNotIn('Warning: this is mostly synthetic', plain)
        User.objects.update(is_synthetic=True)
        warned = self.run_it(rebuild_split=True).markdown_path.read_text(encoding='utf-8')
        self.assertIn('Warning: this is mostly synthetic data', warned)
        self.assertIn('favour the content model by', warned)

    def test_the_second_run_loads_the_saved_split_and_says_so(self):
        self.assertEqual(self.run_it().split_how, 'built')
        second = self.run_it()
        self.assertEqual(second.split_how, 'loaded')
        self.assertIn('Split: loaded', second.markdown_path.read_text(encoding='utf-8'))

    def test_a_saved_split_that_no_longer_matches_the_data_is_flagged_not_silently_reused(self):
        self.run_it()
        unchanged = self.run_it()
        self.assertEqual(unchanged.split_note, '')
        Application.objects.create(gig=self.gigs['B'][19], freelancer=self.people['A'][0], cover_letter='x' * 60)
        changed = self.run_it()
        self.assertEqual(changed.split_how, 'loaded')
        self.assertIn('applications have changed since this split was saved', changed.split_note)
        self.assertIn('--rebuild-split', changed.markdown_path.read_text(encoding='utf-8'))
        self.assertEqual(self.run_it(rebuild_split=True).split_note, '')

    def test_the_csv_holds_every_number_and_agrees_with_the_run(self):
        Application.objects.filter(freelancer=self.people['A'][0], gig=self.gigs['A'][6]).update(status='shortlisted')
        Application.objects.filter(freelancer=self.people['A'][1], gig=self.gigs['A'][9]).update(status='shortlisted')
        run = self.run_it()
        rows = self.read_csv(run)
        self.assertEqual(list(rows[0]), report.CSV_COLUMNS)
        # 6 methods x 2 groups (all, not in cold start) x 3 K x 4 metrics, for each of the two relevance readings.
        for relevance in ('applied', 'strict'):
            self.assertEqual(len([r for r in rows if r['relevance'] == relevance]), 6 * 2 * 12, relevance)
        wanted = ('applied', 'all', 'content', '20', 'hit')
        row = next(
            r for r in rows if (r['relevance'], r['group'], r['method'], r['k'], r['metric']) == wanted
        )
        expected = run.comparison.results['content'].groups['all'][(20, 'hit')]
        self.assertAlmostEqual(float(row['mean']), expected.mean)
        self.assertAlmostEqual(float(row['ci_low']), expected.low)
        self.assertAlmostEqual(float(row['ci_high']), expected.high)
        self.assertEqual(int(row['freelancers']), 12)

    def test_the_csv_has_the_random_spread_and_the_collaborative_coverage(self):
        rows = self.read_csv(self.run_it())
        random_row = next(r for r in rows if r['method'] == 'random' and r['group'] == 'all' and r['metric'] == 'hit')
        self.assertNotEqual(random_row['random_sd'], '')
        collaborative_row = next(r for r in rows if r['method'] == 'collaborative_all' and r['group'] == 'all')
        self.assertEqual(float(collaborative_row['candidates_scored']), 1.0)
        self.assertEqual(float(collaborative_row['right_answers_scored']), 1.0)

    def test_a_split_nobody_can_be_scored_on_stops_with_a_clear_message(self):
        Application.objects.all().delete()
        with self.assertRaisesMessage(EvaluationError, 'No freelancer has at least 5 applications'):
            self.run_it()


class ModelNotFittedReportTests(BlockWorld):
    """With the default minimums this world is too small for the collaborative models."""

    def test_the_report_and_csv_say_which_models_could_not_be_fitted_and_why(self):
        run = run_evaluation(include_synthetic=True, random_seeds=2)
        text = run.markdown_path.read_text(encoding='utf-8')
        self.assertIn('**not fitted**', text)
        self.assertIn('not available: only 72 freelancer and gig pairs', text)
        with open(run.csv_path, newline='', encoding='utf-8-sig') as handle:
            notes = [r['note'] for r in csv.DictReader(handle) if r['note']]
        self.assertTrue(any(note.startswith('not available: only 72') for note in notes))
        self.assertIn('There is no saved live model.', text)


@override_settings(**SMALL_COLLABORATIVE)
class TestPartGuardTests(BlockWorld):
    def run_it(self, **kwargs):
        return run_evaluation(include_synthetic=True, random_seeds=2, **kwargs)

    def logged(self):
        return report.read_test_runs(Path(self.tmp.name) / 'reports')

    def test_the_test_part_is_refused_without_final_and_nothing_is_written_or_recorded(self):
        with self.assertRaises(EvaluationError):
            self.run_it(part='test')
        self.assertFalse((Path(self.tmp.name) / 'reports').exists())
        self.assertEqual(self.logged(), [])

    def test_the_command_refuses_the_test_part_without_final_before_doing_anything(self):
        with self.assertRaisesMessage(CommandError, '--final'):
            call_command('evaluate_recommender', '--split', 'test', stdout=StringIO())
        self.assertFalse((Path(self.tmp.name) / 'reports').exists())

    def test_the_train_part_cannot_be_scored(self):
        with self.assertRaises(EvaluationError):
            self.run_it(part='train', final=True)
        with self.assertRaises(CommandError):
            call_command('evaluate_recommender', '--split', 'train', stdout=StringIO())

    def test_a_final_test_run_is_recorded_and_the_report_says_so(self):
        run = self.run_it(part='test', final=True)
        self.assertEqual(len(self.logged()), 1)
        self.assertEqual(self.logged()[0]['report'], run.markdown_path.name)
        text = run.markdown_path.read_text(encoding='utf-8')
        self.assertIn('# Recommender evaluation: test part', text)
        self.assertIn('This is a test run.', text)
        self.assertIn('scored 1 time(s)', text)
        self.assertIn('## Test runs recorded', text)

    def test_every_further_test_run_is_added_and_listed(self):
        self.run_it(part='test', final=True)
        second = self.run_it(part='test', final=True)
        self.assertEqual(len(self.logged()), 2)
        text = second.markdown_path.read_text(encoding='utf-8')
        self.assertIn('scored 2 time(s)', text)
        self.assertEqual(text.count('| evaluation-'), 0 + len(self.logged()))  # one table row per recorded run

    def test_a_validation_run_reports_how_often_the_test_part_has_been_looked_at_and_adds_nothing(self):
        self.run_it(part='test', final=True)
        validation = self.run_it(part='validation')
        self.assertEqual(len(self.logged()), 1)
        text = validation.markdown_path.read_text(encoding='utf-8')
        self.assertIn('The test part has been scored 1 time(s) so far. This run did not look at it.', text)
        self.assertNotIn('## Test runs recorded', text)

    def test_the_test_report_scores_the_test_applications(self):
        run = self.run_it(part='test', final=True)
        self.assertEqual(run.comparison.part, 'test')
        self.assertEqual(run.comparison.info['positives'], 12)


@override_settings(**SMALL_COLLABORATIVE)
class CommandTests(BlockWorld):
    def run_command(self, *args):
        out = StringIO()
        call_command('evaluate_recommender', '--include-synthetic', '--random-seeds', '2', *args, stdout=out)
        return out.getvalue()

    def test_it_prints_the_headline_table_and_where_the_files_are(self):
        output = self.run_command()
        self.assertIn('Scored the validation part: 12 freelancers, 12 right answers.', output)
        self.assertIn('| Content only |', output)
        self.assertIn('Report: ', output)
        self.assertIn('Every number: ', output)
        self.assertTrue(list((Path(self.tmp.name) / 'reports').glob('evaluation-*.md')))

    def test_the_command_line_is_recorded_in_the_report(self):
        self.run_command('--seed', '7')
        text = next((Path(self.tmp.name) / 'reports').glob('evaluation-*.md')).read_text(encoding='utf-8')
        self.assertIn('python manage.py evaluate_recommender --split validation --include-synthetic --seed 7', text)
        self.assertIn('--random-seeds 2', text)

    def test_the_synthetic_warning_is_printed_too(self):
        User.objects.update(is_synthetic=True)
        self.assertIn('mostly synthetic data', self.run_command())

    def test_final_allows_the_test_part_and_says_it_is_recorded(self):
        output = self.run_command('--split', 'test', '--final')
        self.assertIn('Scoring the TEST part. This run will be recorded.', output)
        self.assertEqual(len(report.read_test_runs(Path(self.tmp.name) / 'reports')), 1)
