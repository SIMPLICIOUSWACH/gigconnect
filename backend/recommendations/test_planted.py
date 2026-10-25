import dataclasses
import random
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings

from accounts.models import User
from applications.models import Application
from gigs.models import Gig
from profiles.models import ClientProfile, FreelancerProfile

from . import planted
from .evaluation import modes

SMALL = planted.Sizes(freelancers=60, gigs=80, clients=20, favourite_pool=5)
# Words that would let the content model see a habit if they were in a gig's text.
HABIT_WORDS = (
    'urgent', 'quick', 'short', 'remote', 'premium', 'budget', 'negotiable', 'verified', 'loyal', 'cash', 'cross',
    'client', 'nairobi', 'mombasa', 'kisumu', 'nakuru', 'uasin', 'kes', 'ksh',
)


class PlanTests(SimpleTestCase):
    """The plan is plain data, so it is checked without a database."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.world = planted.plan_world(seed=42)

    def test_the_same_seed_gives_the_same_world(self):
        self.assertEqual(planted.plan_world(seed=42), self.world)

    def test_another_seed_gives_another_world(self):
        other = planted.plan_world(seed=43)
        self.assertNotEqual(other.applications, self.world.applications)
        self.assertNotEqual(other.freelancers, self.world.freelancers)

    def test_the_default_world_has_the_size_asked_for(self):
        summary = planted.summarise(self.world)
        self.assertEqual((summary['freelancers'], summary['gigs'], summary['clients']), (250, 300, 60))
        fewest, _, most = summary['applications_per_freelancer']
        self.assertGreaterEqual(fewest, 15)
        self.assertLessEqual(most, 25)

    def test_popularity_skew_gives_the_median_gig_at_least_five_applicants(self):
        _, middle, most = planted.summarise(self.world)['applicants_per_gig']
        self.assertGreaterEqual(middle, 5)
        self.assertGreater(most, 4 * middle)  # a long tail: a few gigs get many applicants

    def test_about_40_percent_habit_40_percent_skill_and_20_percent_random(self):
        shares = planted.summarise(self.world)['reason_shares']
        self.assertAlmostEqual(shares['habit'], 0.4, delta=0.04)
        self.assertAlmostEqual(shares['skill'], 0.4, delta=0.04)
        self.assertAlmostEqual(shares['random'], 0.2, delta=0.04)

    def test_the_five_groups_are_the_same_size(self):
        self.assertEqual(set(planted.summarise(self.world)['groups'].values()), {50})

    def test_a_freelancer_never_applies_to_the_same_gig_twice(self):
        pairs = [(a.freelancer, a.gig) for a in self.world.applications]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_every_habit_application_fits_the_habit_and_every_skill_one_shares_a_skill(self):
        freelancers = {f.index: f for f in self.world.freelancers}
        gigs = {g.index: g for g in self.world.gigs}
        for application in self.world.applications:
            freelancer, gig = freelancers[application.freelancer], gigs[application.gig]
            if application.reason == 'habit':
                self.assertTrue(planted.is_habit(freelancer, gig, self.world.clients), freelancer.group)
            if application.reason == 'skill':
                self.assertTrue(planted.shares_skill(freelancer, gig))

    def test_applications_fall_inside_the_gig_window_and_never_in_the_future(self):
        gigs = {g.index: g for g in self.world.gigs}
        for application in self.world.applications:
            gig = gigs[application.gig]
            self.assertLessEqual(application.applied_days_ago, gig.posted_days_ago)
            self.assertGreaterEqual(application.applied_days_ago, gig.posted_days_ago - gig.window_days - 1e-9)
            self.assertGreaterEqual(application.applied_days_ago, 0)

    def test_habits_never_look_at_title_description_or_skills(self):
        # Change the text and the skills of every gig: no habit outcome may change, except cross_field, which
        # only uses skills to leave out gigs that skill overlap would already explain.
        for freelancer in self.world.freelancers:
            for gig in self.world.gigs[:40]:
                changed = dataclasses.replace(gig, title='x', description='y', skills=('Plumbing',))
                text_only = dataclasses.replace(gig, title='x', description='y')
                before = planted.is_habit(freelancer, gig, self.world.clients)
                self.assertEqual(before, planted.is_habit(freelancer, text_only, self.world.clients))
                if freelancer.group != 'cross_field':
                    self.assertEqual(before, planted.is_habit(freelancer, changed, self.world.clients))

    def test_gig_text_comes_only_from_its_own_random_stream_and_the_skills(self):
        # Rebuild every title from a fresh text stream: if anything else had touched it, they would not match.
        text_rng = random.Random('planted-42-text')
        for gig in self.world.gigs:
            self.assertEqual(gig.title, text_rng.choice(planted.TITLE_TEMPLATES).format(skill=gig.skills[0]))
            self.assertEqual(
                gig.description,
                planted.DESCRIPTION_TEMPLATE.format(category=gig.category, skills=' and '.join(gig.skills)),
            )

    def test_no_gig_text_carries_a_habit_word(self):
        for gig in self.world.gigs:
            text = f'{gig.title} {gig.description}'.lower()
            for word in HABIT_WORDS:
                self.assertNotIn(word, text, (word, text))

    def test_the_timeline_changes_only_the_dates(self):
        def without_dates(world):
            return (
                [dataclasses.replace(g, posted_days_ago=0) for g in world.gigs],
                [dataclasses.replace(a, applied_days_ago=0) for a in world.applications],
                world.freelancers, world.clients,
            )

        with mock.patch.object(planted, 'POSTED_DAYS_AGO', (10, 150)):
            older = planted.plan_world(seed=42)
        self.assertEqual(without_dates(older), without_dates(self.world))
        self.assertNotEqual([g.posted_days_ago for g in older.gigs], [g.posted_days_ago for g in self.world.gigs])

    def test_about_a_third_of_the_gigs_are_open_on_the_day_and_nearly_all_have_applicants(self):
        open_gigs = [g for g in self.world.gigs if g.posted_days_ago < g.window_days]
        self.assertGreaterEqual(len(open_gigs) / len(self.world.gigs), 0.30)
        self.assertLessEqual(len(open_gigs) / len(self.world.gigs), 0.40)
        applied = {a.gig for a in self.world.applications}
        self.assertGreaterEqual(sum(1 for g in open_gigs if g.index in applied) / len(open_gigs), 0.9)

    def test_every_gig_skill_belongs_to_its_category(self):
        for gig in self.world.gigs:
            self.assertTrue(set(gig.skills) <= set(planted.CATEGORY_SKILLS[gig.category]))

    def test_client_loyal_freelancers_share_favourites_from_a_small_pool(self):
        loyal = [f for f in self.world.freelancers if f.group == 'client_loyal']
        self.assertTrue(all(len(f.favourite_clients) == 2 for f in loyal))
        self.assertTrue(all(max(f.favourite_clients) < 10 for f in loyal))
        others = [f for f in self.world.freelancers if f.group != 'client_loyal']
        self.assertTrue(all(f.favourite_clients == () for f in others))


@override_settings(DEBUG=True)
class WriteWorldTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(RECOMMENDER_DATA_DIR=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)
        self.world = planted.plan_world(seed=7, sizes=SMALL)

    def test_it_writes_every_planned_row_marked_synthetic(self):
        planted.write_world(self.world)
        self.assertEqual(User.objects.filter(role='freelancer').count(), 60)
        self.assertEqual(User.objects.filter(role='client').count(), 20)
        self.assertEqual(Gig.objects.count(), 80)
        self.assertEqual(Application.objects.count(), len(self.world.applications))
        self.assertFalse(User.objects.filter(is_synthetic=False).exists())
        self.assertFalse(Gig.objects.filter(is_synthetic=False).exists())
        self.assertFalse(Application.objects.filter(is_synthetic=False).exists())
        self.assertFalse(User.objects.exclude(email__startswith='planted-').exists())
        self.assertFalse(any(user.has_usable_password() for user in User.objects.all()))

    def test_every_application_is_dated_inside_its_gig_window(self):
        planted.write_world(self.world)
        for application in Application.objects.select_related('gig'):
            self.assertGreaterEqual(application.created_at, application.gig.created_at)
            self.assertLessEqual(application.created_at.date(), application.gig.application_deadline)

    def test_on_the_day_it_is_written_about_a_third_of_the_gigs_are_open_and_nothing_is_in_the_future(self):
        from django.utils import timezone

        before = timezone.now()
        planted.write_world(planted.plan_world(seed=42))
        today = timezone.localdate()
        share = Gig.objects.filter(application_deadline__gte=today).count() / Gig.objects.count()
        self.assertGreaterEqual(share, 0.30)
        self.assertLessEqual(share, 0.40)
        self.assertFalse(Application.objects.filter(created_at__gt=timezone.now()).exists())
        self.assertFalse(Gig.objects.filter(created_at__gt=before).exists())

    def test_the_ground_truth_file_has_every_freelancer_and_their_group(self):
        ids = planted.write_world(self.world)
        truth = planted.read_ground_truth()
        self.assertEqual(len(truth), 60)
        for freelancer in self.world.freelancers:
            self.assertEqual(truth[ids['freelancers'][freelancer.index]], freelancer.group)
        self.assertTrue((Path(self.tmp.name) / 'synthetic_planted' / planted.WORLD_FILE).is_file())

    def test_the_same_seed_writes_the_same_world_again(self):
        def snapshot():
            return sorted(
                (a.freelancer.email, a.gig.client.email, a.gig.title, int(a.gig.budget_max), a.gig.category.name)
                for a in Application.objects.select_related('freelancer', 'gig__client', 'gig__category')
            )

        planted.write_world(self.world)
        first = snapshot()
        planted.delete_world()
        planted.write_world(planted.plan_world(seed=7, sizes=SMALL))
        self.assertEqual(snapshot(), first)

    def test_it_refuses_a_database_that_holds_other_accounts(self):
        User.objects.create_user(
            email='someone@example.com', password='x-Planted-pass-1', full_name='Someone', phone='254700009901',
            role='freelancer',
        )
        with self.assertRaisesMessage(planted.PlantedError, 'not planted'):
            planted.write_world(self.world)
        self.assertEqual(Gig.objects.count(), 0)

    def test_it_refuses_to_write_a_second_world_over_the_first(self):
        planted.write_world(self.world)
        with self.assertRaisesMessage(planted.PlantedError, 'already here'):
            planted.write_world(self.world)

    def test_delete_removes_every_planted_row_and_the_ground_truth(self):
        planted.write_world(self.world)
        planted.delete_world()
        self.assertEqual((User.objects.count(), Gig.objects.count(), Application.objects.count()), (0, 0, 0))
        self.assertFalse((Path(self.tmp.name) / 'synthetic_planted' / planted.GROUND_TRUTH_FILE).exists())

    def test_the_database_is_in_planted_mode_once_written(self):
        self.assertEqual(modes.current_mode(), modes.SKILL_OVERLAP)
        planted.write_world(self.world)
        self.assertEqual(modes.current_mode(), modes.SYNTHETIC_PLANTED)
        self.assertEqual(modes.split_directory(), Path(self.tmp.name) / 'platform' / 'evaluation' / 'synthetic_planted')

    def test_the_command_prints_the_label_and_the_shape(self):
        out = StringIO()
        call_command('seed_planted', '--freelancers', '60', '--gigs', '80', '--clients', '20', stdout=out)
        output = out.getvalue()
        self.assertIn(modes.PLANTED_LABEL, output)
        self.assertIn('Created 60 freelancers, 20 clients, 80 gigs', output)

    def test_the_command_refuses_when_debug_is_off(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command('seed_planted', stdout=StringIO())


@override_settings(DEBUG=True)
class LabelsNeverReachModelInputsTests(TestCase):
    """The hidden groups are in a file, read only to score the models. Nothing the models read may carry them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(RECOMMENDER_DATA_DIR=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)
        self.world = planted.plan_world(seed=11, sizes=SMALL)
        planted.write_world(self.world)

    def test_no_text_the_models_read_mentions_a_group(self):
        # The group names and their distinctive words. Plain words such as "client" or "only" are left out: client
        # accounts are called clients, and that says nothing about anyone's group.
        words = set(planted.GROUPS) | {'quick', 'cash', 'premium', 'loyal', 'cross-field', 'remote-only'}
        texts = []
        texts += [f'{u.email} {u.full_name}' for u in User.objects.all()]
        texts += [p.bio for p in FreelancerProfile.objects.all()]
        texts += [p.company_name for p in ClientProfile.objects.all()]
        texts += [f'{g.title} {g.description}' for g in Gig.objects.all()]
        texts += [a.cover_letter for a in Application.objects.all()]
        for text in texts:
            for word in words:
                self.assertNotIn(word, text.lower(), (word, text))

    def test_fitting_gives_the_same_models_with_or_without_the_ground_truth_file(self):
        import numpy as np

        from .evaluation import split as ev
        from .evaluation.fitting import fit_models
        from .evaluation.training_input import training_input

        split = ev.build_split(ev.load_positives(True))
        with_file = fit_models(split, True)
        weights_with = training_input(split, True).weights
        truth = Path(self.tmp.name) / 'synthetic_planted' / planted.GROUND_TRUTH_FILE
        # Swap every label, then remove the file altogether: neither may change what the models learn.
        truth.write_text(truth.read_text(encoding='utf-8').replace('premium', 'remote_only'), encoding='utf-8')
        swapped = fit_models(split, True)
        truth.unlink()
        without_file = fit_models(split, True)
        self.assertEqual(training_input(split, True).weights, weights_with)
        for other in (swapped, without_file):
            self.assertEqual(other.vectoriser.vocabulary_, with_file.vectoriser.vocabulary_)
            self.assertTrue(np.allclose(other.collaborative_all.user_factors, with_file.collaborative_all.user_factors))
            self.assertEqual(other.collaborative_all.user_index, with_file.collaborative_all.user_index)

    def test_no_module_on_the_training_path_reads_the_ground_truth(self):
        here = Path(__file__).parent
        training_path = [
            'collaborative.py', 'content.py', 'features.py', 'platform.py', 'training.py', 'recommend.py',
            'candidates.py', 'evaluation/fitting.py', 'evaluation/training_input.py', 'evaluation/split.py',
            'evaluation/compare.py', 'evaluation/candidates.py', 'evaluation/tuning.py', 'evaluation/readiness.py',
        ]
        for name in training_path:
            source = (here / name).read_text(encoding='utf-8')
            for forbidden in ('ground_truth', 'read_ground_truth', 'GROUND_TRUTH', 'planted.'):
                self.assertNotIn(forbidden, source, name)


