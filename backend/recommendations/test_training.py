import csv
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.utils import timezone

from accounts.models import User
from applications.models import Application
from gigs.models import Gig, GigInteraction

from .models import RecommenderModelVersion
from .test_base import RecommenderTestBase
from .training import COLLABORATIVE_FILE, METADATA_FILE, VECTORISER_FILE, TrainingError, train


def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


class TrainTests(RecommenderTestBase):
    def train(self, **kwargs):
        return train(data_dir=self.data_dir, artifact_dir=self.artifact_dir, **kwargs)

    def test_a_run_records_what_it_was_trained_on(self):
        row = self.train(include_synthetic=True)
        self.assertEqual(row.version, 1)
        self.assertEqual(row.platform_gigs, 26)
        self.assertEqual(row.freelancers, 12)
        self.assertEqual(row.interactions, 108)
        self.assertGreater(row.vocabulary_size, 0)
        self.assertTrue(row.collaborative_fitted)
        self.assertEqual(row.collaborative_skipped_reason, '')
        self.assertGreater(row.collaborative_scale, 0)
        self.assertEqual(row.parameters['svd_components_wanted'], 20)
        self.assertEqual(row.parameters['cold_start_min_gigs'], 5)

    def test_the_files_are_saved_in_a_numbered_folder(self):
        row = self.train(include_synthetic=True)
        folder = self.artifact_dir / row.folder
        self.assertEqual(row.folder, 'v0001')
        for name in (VECTORISER_FILE, COLLABORATIVE_FILE, METADATA_FILE):
            self.assertTrue((folder / name).is_file(), name)
        self.assertFalse((self.artifact_dir / 'v0001.tmp').exists())

    def test_each_run_gets_the_next_version_and_the_newest_is_first(self):
        self.train(include_synthetic=True)
        second = self.train(include_synthetic=True)
        self.assertEqual(second.version, 2)
        self.assertEqual(RecommenderModelVersion.objects.first().version, 2)
        self.assertTrue((self.artifact_dir / 'v0001').is_dir())

    def test_the_synthetic_share_is_recorded(self):
        Gig.objects.filter(pk__in=[g.pk for g in self.gigs['P'][:13]]).update(is_synthetic=True)
        GigInteraction.objects.filter(user__in=self.freelancers['P']).update(is_synthetic=True)
        with_synthetic = self.train(include_synthetic=True)
        self.assertEqual(with_synthetic.synthetic_platform_gigs, 13)
        self.assertAlmostEqual(with_synthetic.synthetic_gig_share, 0.5)
        self.assertEqual(with_synthetic.synthetic_interactions, 54)
        self.assertAlmostEqual(with_synthetic.synthetic_interaction_share, 0.5)

    def test_leaving_synthetic_data_out_leaves_it_out_and_records_zero(self):
        Gig.objects.filter(pk__in=[g.pk for g in self.gigs['P']]).update(is_synthetic=True)
        GigInteraction.objects.filter(user__in=self.freelancers['P']).update(is_synthetic=True)
        row = self.train(include_synthetic=False)
        self.assertFalse(row.include_synthetic)
        self.assertEqual(row.platform_gigs, 13)
        self.assertEqual(row.synthetic_platform_gigs, 0)
        self.assertEqual(row.synthetic_interactions, 0)

    def test_the_setting_decides_when_the_option_is_not_given(self):
        with self.settings(RECOMMENDER_INCLUDE_SYNTHETIC=False):
            self.assertFalse(self.train().include_synthetic)
        with self.settings(RECOMMENDER_INCLUDE_SYNTHETIC=True):
            self.assertTrue(self.train().include_synthetic)

    def test_with_too_little_interaction_data_the_collaborative_model_is_skipped_and_the_reason_recorded(self):
        GigInteraction.objects.exclude(user__in=self.freelancers['P'][:3]).delete()
        row = self.train(include_synthetic=True)
        self.assertFalse(row.collaborative_fitted)
        self.assertIn('freelancers with any history', row.collaborative_skipped_reason)
        self.assertIsNone(row.collaborative_scale)
        folder = self.artifact_dir / row.folder
        self.assertTrue((folder / VECTORISER_FILE).is_file())
        self.assertFalse((folder / COLLABORATIVE_FILE).exists())

    def test_with_nothing_at_all_to_train_on_it_says_so(self):
        Gig.objects.all().delete()
        with self.assertRaises(TrainingError):
            self.train(include_synthetic=True)
        self.assertEqual(RecommenderModelVersion.objects.count(), 0)

    def test_the_external_corpus_is_used_when_it_has_been_imported(self):
        processed = self.data_dir / 'processed'
        processed.mkdir(parents=True)
        (processed / 'combined_corpus.csv').write_text(
            'source,source_id,title,description,skills_text,clean_text\n'
            + ''.join(f'upwork,{n},t,d,s,foreign words filler {n}\n' for n in range(40)),
            encoding='utf-8',
        )
        self.assertEqual(self.train(include_synthetic=True).external_documents, 40)

    def test_without_an_imported_corpus_it_fits_on_gigs_only(self):
        self.assertEqual(self.train(include_synthetic=True).external_documents, 0)

    def test_a_failed_run_leaves_no_row_and_no_finished_folder(self):
        with mock.patch('recommendations.training.joblib.dump', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.train(include_synthetic=True)
        self.assertEqual(RecommenderModelVersion.objects.count(), 0)
        self.assertFalse((self.artifact_dir / 'v0001').exists())

    def test_deleted_freelancers_are_not_in_the_model_or_the_snapshot(self):
        gone = self.freelancers['P'][0]
        User.objects.filter(pk=gone.pk).update(is_active=False, deleted_at=timezone.now())
        row = self.train(include_synthetic=True)
        self.assertEqual(row.freelancers, 11)
        self.assertEqual(row.interactions, 108 - 9)
        platform = self.data_dir / 'platform'
        ids = {r['freelancer_id'] for r in read_csv(platform / 'freelancers.csv')}
        ids |= {r['freelancer_id'] for r in read_csv(platform / 'interactions.csv')}
        self.assertNotIn(str(gone.id), ids)


class SnapshotTests(RecommenderTestBase):
    def setUp(self):
        super().setUp()
        self.freelancers['P'][0].freelancer_profile.bio = 'My secret private biography text'
        self.freelancers['P'][0].freelancer_profile.save()
        Application.objects.create(
            gig=self.gigs['P'][11], freelancer=self.freelancers['P'][0],
            cover_letter='A very private cover letter that must never be copied anywhere',
            portfolio_link='https://private.example.org/me', proposed_rate=1234, status='shortlisted',
        )
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.platform = self.data_dir / 'platform'

    def test_the_four_files_are_written_with_the_expected_columns(self):
        self.assertEqual(len(read_csv(self.platform / 'gigs.csv')), 26)
        self.assertEqual(len(read_csv(self.platform / 'freelancers.csv')), 12)
        self.assertEqual(len(read_csv(self.platform / 'interactions.csv')), 108)
        applications = read_csv(self.platform / 'applications.csv')
        self.assertEqual(len(applications), 1)
        self.assertEqual(
            list(applications[0]), ['freelancer_id', 'gig_id', 'status', 'weight', 'is_synthetic', 'created_at'],
        )
        self.assertEqual((applications[0]['status'], applications[0]['weight']), ('shortlisted', '4'))

    def test_no_names_emails_phones_bios_or_cover_letters_are_in_any_file(self):
        everything = ''
        for name in ('gigs', 'freelancers', 'interactions', 'applications'):
            everything += (self.platform / f'{name}.csv').read_text(encoding='utf-8-sig')
        for private in ('rec-p0', '@example.com', 'secret private biography', 'private cover letter',
                        'private.example.org', '1234', '254700009'):
            self.assertNotIn(private, everything, private)

    def test_a_freelancer_row_has_an_id_and_skills_only(self):
        rows = read_csv(self.platform / 'freelancers.csv')
        self.assertEqual(list(rows[0]), ['freelancer_id', 'skills', 'is_synthetic'])
        # The rows are in no fixed order, so check all of them: every freelancer has one of the two skill sets.
        self.assertEqual({row['skills'] for row in rows}, {'Pyskill 1;Pyskill 2', 'Xlskill 1;Xlskill 2'})


class ReportTests(RecommenderTestBase):
    def train(self):
        return train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)

    def test_a_report_is_written_with_the_measured_numbers(self):
        row = self.train()
        reports = list((self.data_dir / 'reports').glob('training-*.md'))
        self.assertEqual(len(reports), 1)
        text = reports[0].read_text(encoding='utf-8')
        self.assertIn(f'model version {row.version}', text)
        self.assertIn('Platform gigs used: 26', text)
        self.assertIn('Freelancer and gig pairs with an interaction: 108', text)
        self.assertIn('Status: fitted', text)
        self.assertIn('gigs.csv: 26 rows', text)
        self.assertNotIn('—', text)

    def test_a_skipped_collaborative_model_is_reported_with_its_reason(self):
        GigInteraction.objects.all().delete()
        self.train()
        text = next((self.data_dir / 'reports').glob('training-*.md')).read_text(encoding='utf-8')
        self.assertIn('Status: skipped', text)
        self.assertIn('Reason:', text)

    def test_a_second_run_on_the_same_day_does_not_overwrite_the_first_report(self):
        self.train()
        self.train()
        self.assertEqual(len(list((self.data_dir / 'reports').glob('training-*.md'))), 2)


class TrainCommandTests(RecommenderTestBase):
    def run_command(self, *args):
        out = StringIO()
        call_command(
            'train_recommender', '--data-dir', str(self.data_dir), '--artifact-dir', str(self.artifact_dir),
            *args, stdout=out,
        )
        return out.getvalue()

    def test_the_command_trains_and_says_which_version(self):
        output = self.run_command('--include-synthetic')
        self.assertIn('Trained model version 1', output)
        self.assertIn('Collaborative model fitted', output)
        self.assertEqual(RecommenderModelVersion.objects.count(), 1)

    def test_no_include_synthetic_is_understood(self):
        self.run_command('--no-include-synthetic')
        self.assertFalse(RecommenderModelVersion.objects.get().include_synthetic)

    def test_nothing_to_train_on_is_a_clear_command_error(self):
        Gig.objects.all().delete()
        with self.assertRaises(CommandError):
            self.run_command()
