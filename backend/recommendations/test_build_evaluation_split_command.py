import tempfile
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from applications.models import Application
from gigs.models import Category, Gig

from .evaluation import split as ev


class BuildEvaluationSplitCommandTests(TestCase):
    """Two freelancers apply to 10 of 14 gigs, one a day over the last 10 days, so each splits 6, 2, 2."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(RECOMMENDER_DATA_DIR=self.tmp.name, RECOMMENDER_INCLUDE_SYNTHETIC=True)
        override.enable()
        self.addCleanup(override.disable)

        category = Category.objects.create(name='Split Command Category')
        client = self.make_user('split-command-client@example.com', 'client')
        self.people = [
            self.make_user('split-command-one@example.com', 'freelancer', synthetic=True),
            self.make_user('split-command-two@example.com', 'freelancer'),
        ]
        self.gigs = [
            Gig.objects.create(
                client=client, category=category, title=f'Split command gig {n}', description='A gig.',
                budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=60),
            )
            for n in range(14)
        ]
        Gig.objects.update(created_at=timezone.now() - timedelta(days=40))
        for person in self.people:
            for number, gig in enumerate(self.gigs[:10]):
                application = Application.objects.create(gig=gig, freelancer=person, cover_letter='x' * 60)
                Application.objects.filter(pk=application.pk).update(
                    created_at=timezone.now() - timedelta(days=10 - number),
                )

    def make_user(self, email, role, synthetic=False):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password='x-Split-pass-1', full_name=email.split('@')[0],
            phone=f'2547000092{number:02d}', role=role, is_synthetic=synthetic,
        )

    def run_command(self, *args):
        out = StringIO()
        call_command('build_evaluation_split', *args, stdout=out)
        return out.getvalue()

    def saved_files(self):
        directory = Path(self.tmp.name) / 'platform' / 'evaluation'
        return directory / ev.SPLIT_FILE, directory / ev.META_FILE

    def test_the_first_run_builds_and_saves_the_split(self):
        output = self.run_command()
        self.assertIn('Split built.', output)
        for path in self.saved_files():
            self.assertTrue(path.is_file(), path)

    def test_a_second_run_loads_the_saved_split_and_a_rebuild_builds_a_new_one(self):
        self.run_command()
        self.assertIn('Split loaded.', self.run_command())
        self.assertIn('Split built.', self.run_command('--rebuild-split'))

    def test_the_table_has_the_counts_worked_out_by_hand(self):
        output = self.run_command()
        rows = [line.split() for line in output.splitlines()]
        lines = {row[0]: row for row in rows if row and row[0] in ('train', 'validation', 'test')}
        # part, freelancers, positives, synthetic, strictly relevant. Only the first freelancer is synthetic.
        self.assertEqual(lines['train'][1:], ['2', '12', '6', '0'])
        self.assertEqual(lines['validation'][1:], ['2', '4', '2', '0'])
        self.assertEqual(lines['test'][1:], ['2', '4', '2', '0'])
        self.assertIn('2 freelancer(s) can be evaluated (at least 5 positives). 0 have fewer', output)

    def test_it_says_how_many_candidates_each_freelancer_gets_and_that_none_break_the_rules(self):
        output = self.run_command()
        # Each part's own 2 positives, plus the 4 gigs nobody applied to, and not the other part's positives.
        for part in ('validation', 'test'):
            expected = f'{part}: candidate gigs per freelancer, median 6 (smallest 6, largest 6); 0 positive(s)'
            self.assertIn(expected, output)

    def test_leaving_synthetic_data_out_drops_the_synthetic_freelancer(self):
        output = self.run_command('--no-include-synthetic')
        self.assertIn('Synthetic data left out.', output)
        self.assertIn('1 freelancer(s) can be evaluated', output)

    def test_the_synthetic_setting_is_used_when_the_option_is_not_given(self):
        with override_settings(RECOMMENDER_INCLUDE_SYNTHETIC=False):
            output = self.run_command()
        self.assertIn('Synthetic data left out.', output)
        self.assertIn('1 freelancer(s) can be evaluated', output)

    def test_it_runs_with_no_applications_at_all(self):
        Application.objects.all().delete()
        output = self.run_command()
        self.assertIn('0 freelancer(s) can be evaluated', output)
        self.assertNotIn('candidate gigs per freelancer', output)
