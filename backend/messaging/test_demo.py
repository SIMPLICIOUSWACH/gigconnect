import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from accounts.models import User
from applications.models import Application
from gigs.models import Gig
from notifications.models import Notification
from recommendations import planted, planted_demo, registry
from recommendations.platform import (
    applications_for_training,
    freelancers_for_training,
    gigs_for_training,
    interactions_for_training,
)
from recommendations.recommend import gigs_interacted_with
from recommendations.testing import profile_settings
from recommendations.training import train

from .demo import DEMO_CLIENT
from .models import Conversation

SIZES = planted.Sizes(freelancers=60, gigs=80, clients=20, favourite_pool=5)


class OutsideThePlantedDatabaseTests(TestCase):
    def test_it_refuses(self):
        with self.assertRaisesMessage(CommandError, 'only exist in the planted database'):
            call_command('seed_demo_conversations', stdout=StringIO())
        self.assertFalse(Conversation.objects.exists())


@override_settings(DEBUG=True, RECOMMENDATIONS_ENABLED=True, **profile_settings('demo'))
class DemoConversationTests(TestCase):
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
        planted.write_world(planted.plan_world(seed=13, sizes=SIZES))
        train(include_synthetic=True)
        accounts = planted_demo.create_demo_accounts(registry.availability().model)
        self.demo_freelancers = [accounts[group] for group in planted_demo.DEMO_GROUPS]

    def training_world(self):
        """Everything training and evaluation read, as counts, and each demo freelancer's interaction count."""
        return {
            'gigs': gigs_for_training().count(),
            'applications': applications_for_training().count(),
            'interactions': interactions_for_training().count(),
            'freelancers': freelancers_for_training().count(),
            'interacted': [gigs_interacted_with(user) for user in self.demo_freelancers],
        }

    def seed(self):
        output = StringIO()
        call_command('seed_demo_conversations', stdout=output)
        return output.getvalue()

    def test_the_recommender_sees_the_same_world_after_seeding(self):
        before = self.training_world()
        self.seed()
        self.assertEqual(Gig.objects.filter(is_demo_extra=True).count(), 3)  # the rows really are there
        self.assertEqual(self.training_world(), before)

    def test_three_in_progress_hires_with_chats_the_client_started(self):
        output = self.seed()
        self.assertIn('3 sample chats for Baraka Home Services', output)
        client = User.objects.get(email=DEMO_CLIENT[0])
        self.assertTrue(client.check_password(planted_demo.DEMO_PASSWORD))
        conversations = Conversation.objects.filter(client=client)
        self.assertEqual({c.freelancer for c in conversations}, set(self.demo_freelancers))
        for conversation in conversations:
            self.assertEqual(conversation.gig.status, 'in_progress')
            self.assertEqual(conversation.application.status, 'hired')
            first = conversation.messages.order_by('id').first()
            self.assertEqual(first.sender, client)
            self.assertGreaterEqual(conversation.messages.count(), 2)
        self.assertFalse(Notification.objects.exists())  # seeding is quiet

    def test_running_it_again_replaces_the_chats(self):
        self.seed()
        self.seed()
        self.assertEqual(Conversation.objects.count(), 3)
        self.assertEqual(Application.objects.filter(is_demo_extra=True).count(), 3)
        self.assertEqual(User.objects.filter(email=DEMO_CLIENT[0]).count(), 1)
