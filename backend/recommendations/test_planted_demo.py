import tempfile
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from accounts.models import User
from applications.models import Application
from gigs.models import Gig

from . import planted, planted_demo, registry
from .evaluation import modes
from .testing import profile_settings
from .training import train

SIZES = planted.Sizes(freelancers=60, gigs=80, clients=20, favourite_pool=5)


class DemoAccountRulesTests(TestCase):
    def test_every_demo_account_is_a_planted_account_so_it_can_only_live_in_the_planted_database(self):
        emails = [email for email, _ in planted_demo.DEMO_ACCOUNTS.values()] + [planted_demo.COLD_START_ACCOUNT[0]]
        for email in emails:
            self.assertTrue(email.startswith(modes.PLANTED_EMAIL_PREFIX), email)

    def test_the_demo_accounts_are_refused_in_a_database_that_is_not_planted(self):
        User.objects.create_user(
            email='someone@example.com', password='x-Demo-pass-1', full_name='Someone', phone='254700008801',
            role='freelancer',
        )
        with self.assertRaisesMessage(planted_demo.DemoError, 'only exist in the planted database'):
            planted_demo.create_demo_accounts(model=None)
        self.assertFalse(User.objects.filter(email__startswith='planted-').exists())

    def test_the_refresh_refuses_to_run_under_the_production_profile(self):
        with self.assertRaisesMessage(CommandError, 'RECOMMENDER_PROFILE=demo'):
            call_command('refresh_planted_demo', stdout=StringIO())


@override_settings(DEBUG=True, RECOMMENDATIONS_ENABLED=True, **profile_settings('demo'))
class DemoOnAPlantedWorldTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(
            RECOMMENDER_DATA_DIR=self.tmp.name, RECOMMENDER_ARTIFACT_DIR=Path(self.tmp.name) / 'artifacts',
            RECOMMENDER_SVD_COMPONENTS=2,
        )
        override.enable()
        self.addCleanup(override.disable)
        registry.clear_cache()
        self.addCleanup(registry.clear_cache)
        self.world = planted.plan_world(seed=13, sizes=SIZES)
        self.ids = planted.write_world(self.world)
        train(include_synthetic=True)
        self.model = registry.availability().model

    def test_the_habit_check_on_database_gigs_is_the_generators_rule(self):
        gigs = Gig.objects.select_related('client', 'category').in_bulk(list(self.ids['gigs'].values()))
        for planned in self.world.gigs:
            gig = gigs[self.ids['gigs'][planned.index]]
            for group in planted_demo.DEMO_GROUPS:
                freelancer = SimpleNamespace(group=group, favourite_clients=(), neighbour_category=None, skills=())
                expected = planted.is_habit(freelancer, planned, self.world.clients)
                self.assertEqual(planted_demo.fits_habit(group, gig), expected, (group, planned.index))

    def test_the_demo_accounts_are_made_with_readable_names_and_the_demo_password(self):
        accounts = planted_demo.create_demo_accounts(self.model)
        truth = planted.read_ground_truth()
        for group in planted_demo.DEMO_GROUPS:
            email, name = planted_demo.DEMO_ACCOUNTS[group]
            user = User.objects.get(email=email)
            self.assertEqual(user.full_name, name)
            self.assertTrue(user.check_password(planted_demo.DEMO_PASSWORD))
            self.assertEqual(truth[user.id], group)  # really a member of the group it shows
            self.assertGreaterEqual(Application.objects.filter(freelancer=user).count(), 15)
        newcomer = accounts['cold_start']
        self.assertEqual(Application.objects.filter(freelancer=newcomer).count(), 0)
        self.assertTrue(newcomer.check_password(planted_demo.DEMO_PASSWORD))
        self.assertEqual(
            sorted(s.name for s in newcomer.freelancer_profile.skills.all()), sorted(planted_demo.COLD_START_SKILLS),
        )

    def test_each_chosen_freelancer_has_the_clearest_habit_in_their_top_5(self):
        truth = planted.read_ground_truth()
        chosen = planted_demo.choose_demo_freelancers(self.model)
        for group, user in chosen.items():
            def fits(member):
                return sum(1 for r in planted_demo.top(self.model, member) if planted_demo.fits_habit(group, r.gig))

            members = User.objects.filter(id__in=[i for i, g in truth.items() if g == group])
            self.assertEqual(fits(user), max(fits(member) for member in members), group)

    def test_the_ground_truth_file_follows_the_renamed_emails(self):
        planted_demo.create_demo_accounts(self.model)
        text = (modes.planted_directory() / planted.GROUND_TRUTH_FILE).read_text(encoding='utf-8')
        for email, _ in planted_demo.DEMO_ACCOUNTS.values():
            self.assertIn(email, text)

    def test_the_printout_shows_each_account_and_the_cold_start_check(self):
        planted_demo.create_demo_accounts(self.model)
        text = '\n'.join(planted_demo.demo_lines(self.model))
        self.assertIn(modes.PLANTED_LABEL, text)
        for _, name in planted_demo.DEMO_ACCOUNTS.values():
            self.assertIn(name, text)
        self.assertIn('below: David Kamau, 0 gigs, collaborative share 0% (expected 0%), sources in the top 5: content',
                      text)
        self.assertIn('above: Amina Wanjiru', text)
        self.assertIn('Open gigs today:', text)
        for column in ('budget', 'urgency', 'client', 'content ', 'collab '):
            self.assertIn(column, text)
