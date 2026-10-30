import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings

from accounts.models import User
from applications.models import Application
from config import recommender_profiles as rp
from gigs.models import GigInteraction

from . import checks, snapshot
from .evaluation.run import run_evaluation
from .test_evaluation_compare import SMALL_COLLABORATIVE, BlockWorld

DEMO_LABEL = 'synthetic_planted - demonstrates pipeline mechanics, not real-world accuracy'


class ResolveTests(SimpleTestCase):
    def test_production_is_the_default_when_the_variable_is_missing_or_empty(self):
        self.assertEqual(rp.resolve({})[0], 'production')
        self.assertEqual(rp.resolve({'RECOMMENDER_PROFILE': ''})[0], 'production')

    def test_demo_is_chosen_by_name_whatever_the_case(self):
        self.assertEqual(rp.resolve({'RECOMMENDER_PROFILE': ' Demo '})[0], 'demo')

    def test_an_unknown_profile_refuses_to_start(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'the profiles are demo, production'):
            rp.resolve({'RECOMMENDER_PROFILE': 'staging'})

    def test_this_test_run_uses_production_settings(self):
        values = rp.load()['production']
        self.assertEqual(settings.RECOMMENDER_PROFILE, 'production')
        self.assertEqual(settings.RECOMMENDER_BLEND_MAX_WEIGHT, values['blend_max_weight'])
        self.assertEqual(settings.RECOMMENDER_BAND_GOOD, values['band_good'])
        self.assertEqual(settings.RECOMMENDER_PROFILE_LABEL, '')


class ProfileValuesTests(SimpleTestCase):
    """The values are the tuning picks: skill-overlap for production, planted for demo."""

    def setUp(self):
        self.profiles = rp.load()

    def test_production_is_the_skill_overlap_pick_content_only(self):
        values = self.profiles['production']
        self.assertEqual(values['blend_max_weight'], 0.0)
        self.assertEqual((values['band_good'], values['band_strong']), (0.13, 0.27))
        self.assertIsNone(values['database'])
        self.assertEqual((values['artifact_folder'], values['snapshot_folder']), ('', 'platform'))

    def test_demo_is_the_planted_pick_including_its_cold_start_threshold(self):
        values = self.profiles['demo']
        picked = (values['blend_max_weight'], values['blend_ramp_gigs'], values['svd_components'],
                  values['cold_start_min_gigs'])
        self.assertEqual(picked, (0.5, 50, 2, 10))
        self.assertEqual((values['band_good'], values['band_strong']), (0.35, 0.6))
        self.assertEqual(values['database'], 'gigconnect_planted')
        self.assertEqual(values['label'], DEMO_LABEL)

    def test_demo_has_its_own_model_and_snapshot_folders(self):
        demo, production = self.profiles['demo'], self.profiles['production']
        self.assertNotEqual(demo['artifact_folder'], production['artifact_folder'])
        self.assertNotEqual(demo['snapshot_folder'], production['snapshot_folder'])
        self.assertTrue(demo['artifact_folder'] and demo['snapshot_folder'].startswith('platform/'))

    def test_demo_always_uses_the_planted_database_whatever_db_name_says(self):
        self.assertEqual(rp.database_name(self.profiles['demo'], {'DB_NAME': 'gigconnect'}), 'gigconnect_planted')
        self.assertEqual(rp.database_name(self.profiles['production'], {'DB_NAME': 'other'}), 'other')
        self.assertEqual(rp.database_name(self.profiles['production'], {}), 'gigconnect')

    def test_demo_switches_recommendations_on_and_production_follows_the_variable(self):
        self.assertTrue(rp.recommendations_enabled(self.profiles['demo'], {}))
        self.assertFalse(rp.recommendations_enabled(self.profiles['production'], {}))
        self.assertTrue(rp.recommendations_enabled(self.profiles['production'], {'RECOMMENDATIONS_ENABLED': 'True'}))

    def test_a_profile_missing_a_value_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profiles.json'
            broken = dict(self.profiles)
            broken['demo'] = {k: v for k, v in self.profiles['demo'].items() if k != 'band_good'}
            path.write_text(json.dumps(broken), encoding='utf-8')
            with self.assertRaisesMessage(ImproperlyConfigured, 'band_good'):
                rp.load(path)


class DemoDatabaseRuleTests(SimpleTestCase):
    def test_production_never_complains(self):
        self.assertEqual(checks.demo_problems('production', 'anything', 'gigconnect_planted', 99), [])

    def test_demo_refuses_a_database_that_is_not_the_planted_one(self):
        problems = checks.demo_problems('demo', 'gigconnect', 'gigconnect_planted', 0)
        self.assertEqual(len(problems), 1)
        self.assertIn('must run on the planted database', problems[0])

    def test_demo_refuses_a_database_holding_accounts_that_are_not_planted(self):
        problems = checks.demo_problems('demo', 'gigconnect_planted', 'gigconnect_planted', 3)
        self.assertEqual(len(problems), 1)
        self.assertIn('3 account(s) that are not planted', problems[0])

    def test_demo_on_the_planted_database_is_fine_even_before_it_is_migrated(self):
        self.assertEqual(checks.demo_problems('demo', 'gigconnect_planted', 'gigconnect_planted', 0), [])
        self.assertEqual(checks.demo_problems('demo', 'gigconnect_planted', 'gigconnect_planted', None), [])


class DemoDatabaseCheckTests(TestCase):
    """The system check itself, against the test database."""

    def make_user(self, email):
        return User.objects.create_user(
            email=email, password='x-Profile-pass-1', full_name='Someone', phone=f'2547000{User.objects.count():05d}',
            role='freelancer',
        )

    def test_the_check_is_silent_under_production(self):
        self.make_user('someone@example.com')
        self.assertEqual(checks.demo_profile_database(None), [])

    def test_demo_refuses_to_start_on_a_database_that_is_not_the_planted_one(self):
        with override_settings(RECOMMENDER_PROFILE='demo'):
            errors = checks.demo_profile_database(None)
        self.assertTrue(errors)
        self.assertEqual(errors[0].id, 'recommendations.E001')
        self.assertIn('must run on the planted database', errors[0].msg)

    def test_demo_refuses_when_the_database_holds_ordinary_accounts(self):
        self.make_user('someone@example.com')
        here = connection.settings_dict['NAME']
        with override_settings(RECOMMENDER_PROFILE='demo', RECOMMENDER_PLANTED_DATABASE=here):
            errors = checks.demo_profile_database(None)
        self.assertEqual(len(errors), 1)
        self.assertIn('not planted', errors[0].msg)

    def test_demo_starts_on_a_database_with_only_planted_accounts(self):
        self.make_user('planted-freelancer-001@example.test')
        here = connection.settings_dict['NAME']
        with override_settings(RECOMMENDER_PROFILE='demo', RECOMMENDER_PLANTED_DATABASE=here):
            self.assertEqual(checks.demo_profile_database(None), [])


class ProfileShownTests(SimpleTestCase):
    def test_the_admin_says_which_profile_is_running(self):
        self.assertIn('production profile', admin.site.site_header)
        self.assertIn('Recommender profile: production profile', admin.site.index_title)

    def test_the_training_snapshot_goes_to_the_profiles_folder(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(RECOMMENDER_SNAPSHOT_FOLDER='platform/demo'):
            snapshot.write_snapshot(folder, [], [], GigInteraction.objects.none(), Application.objects.none())
            self.assertTrue((Path(folder) / 'platform' / 'demo' / 'gigs.csv').is_file())
            self.assertFalse((Path(folder) / 'platform' / 'gigs.csv').exists())


@override_settings(**SMALL_COLLABORATIVE)
class ProfileInReportsTests(BlockWorld):
    def test_every_report_names_the_profile(self):
        text = run_evaluation(include_synthetic=True, random_seeds=2).markdown_path.read_text(encoding='utf-8')
        self.assertIn('Recommender profile: **production profile**.', text)

    def test_a_demo_report_carries_the_planted_label(self):
        with override_settings(RECOMMENDER_PROFILE='demo', RECOMMENDER_PROFILE_LABEL=DEMO_LABEL):
            text = run_evaluation(include_synthetic=True, random_seeds=2).markdown_path.read_text(encoding='utf-8')
        self.assertIn(f'Recommender profile: **demo profile, {DEMO_LABEL}**.', text)
