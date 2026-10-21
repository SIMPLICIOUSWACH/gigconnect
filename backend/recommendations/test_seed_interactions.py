import tempfile
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from applications.models import Application
from gigs.models import Category, Gig, GigInteraction
from profiles.models import Skill

from . import registry
from .recommend import recommend
from .training import train

NON_APPLY_TYPES = {'view', 'search_click', 'save', 'recommendation_click'}


def run(*args):
    out = StringIO()
    call_command('seed_interactions', *args, stdout=out)
    return out.getvalue()


@override_settings(DEBUG=True)  # the test runner forces DEBUG off, and the command refuses to run then
class SeedInteractionsTests(TestCase):
    """12 seed freelancers in two skill groups, and 30 seeded gigs, half asking for each group's skills."""

    def setUp(self):
        category = Category.objects.create(name='Seed Interactions Category')
        self.skills = {
            'P': Skill.objects.create(name='Seedpy Skill', category='Test'),
            'X': Skill.objects.create(name='Seedxl Skill', category='Test'),
        }
        self.client_user = self.make_user('seed-client-1@example.test', 'client')
        self.freelancers = []
        for number in range(1, 13):
            user = self.make_user(f'seed-freelancer-{number}@example.test', 'freelancer')
            user.freelancer_profile.skills.set([self.skills['P' if number <= 6 else 'X']])
            self.freelancers.append(user)
        self.gigs = []
        for number in range(30):
            gig = Gig.objects.create(
                client=self.client_user, category=category, title=f'Seeded interaction gig {number}',
                description='Sample.', budget_min=2000, budget_max=5000,
                deadline=date.today() + timedelta(days=30), is_synthetic=True,
            )
            gig.skills.set([self.skills['P' if number < 15 else 'X']])
            self.gigs.append(gig)
        # The gigs were posted 40 days ago, so there is a month of room to date interactions in.
        Gig.objects.update(created_at=timezone.now() - timedelta(days=40))
        self.group_p_gigs = {gig.id for gig in self.gigs[:15]}

    def make_user(self, email, role):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password='x-Seed-pass-1', full_name=email.split('@')[0],
            phone=f'254700050{number:03d}', role=role, is_synthetic=True,
        )

    def pairs(self):
        return set(GigInteraction.objects.values_list('user_id', 'gig_id'))

    def test_refuses_to_run_when_debug_is_off(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            run()
        self.assertEqual(GigInteraction.objects.count(), 0)

    def test_deleting_also_refuses_when_debug_is_off(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            run('--delete')

    def test_needs_the_seed_freelancers_and_gigs(self):
        Gig.objects.all().delete()
        with self.assertRaises(CommandError):
            run()

    def test_every_row_is_marked_synthetic_and_belongs_to_a_seed_freelancer_on_a_seeded_gig(self):
        run('--per-freelancer', '10')
        rows = GigInteraction.objects.all()
        self.assertEqual(rows.count(), 120)
        self.assertFalse(rows.filter(is_synthetic=False).exists())
        self.assertEqual({row.user_id for row in rows}, {u.id for u in self.freelancers})
        self.assertEqual({row.gig_id for row in rows} - {g.id for g in self.gigs}, set())

    def test_each_freelancer_interacts_with_different_gigs_and_only_the_four_kinds(self):
        run('--per-freelancer', '10')
        for user in self.freelancers:
            gigs = list(GigInteraction.objects.filter(user=user).values_list('gig_id', flat=True))
            self.assertEqual(len(gigs), 10)
            self.assertEqual(len(set(gigs)), 10)
        self.assertTrue(set(GigInteraction.objects.values_list('type', flat=True)) <= NON_APPLY_TYPES)
        self.assertFalse(GigInteraction.objects.filter(type='apply').exists())

    def test_clicks_have_a_position_and_views_and_saves_do_not(self):
        run('--per-freelancer', '15')
        for row in GigInteraction.objects.all():
            if row.type in ('search_click', 'recommendation_click'):
                self.assertTrue(1 <= row.position <= 10, row.type)
            else:
                self.assertIsNone(row.position, row.type)

    def test_freelancers_favour_gigs_that_share_their_skills(self):
        run('--per-freelancer', '15')
        own_share = []
        for number, user in enumerate(self.freelancers, start=1):
            gigs = set(GigInteraction.objects.filter(user=user).values_list('gig_id', flat=True))
            in_group = gigs & self.group_p_gigs if number <= 6 else gigs - self.group_p_gigs
            own_share.append(len(in_group) / len(gigs))
        # Half the gigs share each freelancer's skill, so picking at random would give about 0.5 (give or take
        # 0.03 for this average). A preference of 5 to 1 gives about 0.76 when 15 of 30 gigs are chosen, and the
        # ids are random so it varies a little. 0.62 is far from chance and was never reached in 20,000 trials.
        self.assertGreater(sum(own_share) / len(own_share), 0.62)

    def test_the_same_seed_gives_the_same_rows(self):
        run('--per-freelancer', '10', '--seed', '7')
        first = self.pairs()
        run('--delete')
        run('--per-freelancer', '10', '--seed', '7')
        self.assertEqual(self.pairs(), first)

    def test_running_again_adds_only_pairs_that_are_not_there_yet(self):
        run('--per-freelancer', '10')
        before = GigInteraction.objects.count()
        output = run('--per-freelancer', '10')
        self.assertEqual(GigInteraction.objects.count(), before)
        self.assertIn('Created 0', output)
        pairs = list(GigInteraction.objects.values_list('user_id', 'gig_id'))
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_the_interactions_are_spread_over_the_last_month(self):
        run('--per-freelancer', '15')
        now = timezone.now()
        ages = [(now - row.created_at).days for row in GigInteraction.objects.all()]
        self.assertGreaterEqual(min(ages), 0)
        self.assertLessEqual(max(ages), 30)
        self.assertGreater(len(set(ages)), 10)  # not all on one day

    def test_no_interaction_is_dated_before_its_gig_existed(self):
        # Gigs posted only 3 days ago leave only 3 days of room, so nothing may be dated earlier than that.
        Gig.objects.update(created_at=timezone.now() - timedelta(days=3))
        run('--per-freelancer', '15')
        for row in GigInteraction.objects.select_related('gig'):
            self.assertGreaterEqual(row.created_at, row.gig.created_at)

    def test_gigs_posted_just_now_leave_no_room_so_everything_is_dated_now(self):
        Gig.objects.update(created_at=timezone.now())
        run('--per-freelancer', '5')
        for row in GigInteraction.objects.select_related('gig'):
            self.assertGreaterEqual(row.created_at, row.gig.created_at)

    def test_delete_removes_only_seeded_interactions_not_real_ones_or_seeded_applies(self):
        real = User.objects.create_user(
            email='real-person@example.com', password='x-Real-pass-1', full_name='Real', phone='254700050999',
            role='freelancer',
        )
        real_row = GigInteraction.objects.create(gig=self.gigs[0], user=real, type='view')
        seeded_apply = GigInteraction.objects.create(
            gig=self.gigs[1], user=self.freelancers[0], type='apply', is_synthetic=True,
        )
        run('--per-freelancer', '10')
        run('--delete')
        self.assertEqual(set(GigInteraction.objects.all()), {real_row, seeded_apply})


@override_settings(DEBUG=True, RECOMMENDER_TFIDF_MIN_DF=1, RECOMMENDER_TFIDF_MAX_DF=1.0, RECOMMENDATIONS_ENABLED=True)
class SeedThenTrainTests(SeedInteractionsTests):
    """The point of the command: seeded data plus training gives a model where both parts run."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(registry.clear_cache)
        registry.clear_cache()
        self.data_dir = Path(self.tmp.name) / 'datasets'
        self.artifact_dir = Path(self.tmp.name) / 'artifacts'
        self.enterContext(override_settings(
            RECOMMENDER_DATA_DIR=self.data_dir, RECOMMENDER_ARTIFACT_DIR=self.artifact_dir, SHOW_SYNTHETIC=True,
        ))

    def test_the_seeded_data_meets_the_real_minimums_so_the_collaborative_model_is_fitted(self):
        run('--per-freelancer', '15')
        row = train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.assertTrue(row.collaborative_fitted, row.collaborative_skipped_reason)
        self.assertEqual(row.freelancers, 12)
        self.assertEqual(row.interactions, 180)
        self.assertEqual(row.synthetic_interactions, 180)  # all of it is synthetic, and the model says so
        self.assertAlmostEqual(row.synthetic_interaction_share, 1.0)

    def test_the_trained_model_recommends_gigs_that_share_the_freelancers_skills_first(self):
        run('--per-freelancer', '15')
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        model = registry.availability().model
        result = recommend(model, self.freelancers[0])  # a group P freelancer
        self.assertFalse(result.cold_start)  # 15 gigs of history
        top = [r.gig.id for r in result.results[:5]]
        self.assertTrue(set(top) <= self.group_p_gigs)
        self.assertIn('hybrid', {r.source for r in result.results})

    def test_applications_seeded_alongside_still_count(self):
        run('--per-freelancer', '10')
        # Which gigs were seeded for a freelancer depends on their random id, so pick one that has no interaction.
        taken = self.pairs()
        untouched = next(gig for gig in self.gigs if (self.freelancers[0].id, gig.id) not in taken)
        Application.objects.create(gig=untouched, freelancer=self.freelancers[0], cover_letter='x' * 60)
        row = train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.assertEqual(row.interactions, 121)  # 120 interactions plus one application on a new pair
