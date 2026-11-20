import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from applications.models import Application
from gigs.models import Gig
from messaging.models import Conversation
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

from .models import Review

SIZES = planted.Sizes(freelancers=60, gigs=80, clients=20, favourite_pool=5)


class OutsideThePlantedDatabaseTests(TestCase):
    def test_it_refuses(self):
        with self.assertRaisesMessage(CommandError, 'only exist in the planted database'):
            call_command('seed_demo_reviews', stdout=StringIO())
        self.assertFalse(Review.objects.exists())


@override_settings(DEBUG=True, RECOMMENDATIONS_ENABLED=True, **profile_settings('demo'))
class DemoReviewTests(TestCase):
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

    def seed(self, command='seed_demo_reviews'):
        output = StringIO()
        call_command(command, stdout=output)
        return output.getvalue()

    def test_the_recommender_sees_the_same_world_after_seeding(self):
        before = self.training_world()
        self.seed()
        self.assertGreater(Gig.objects.filter(is_demo_extra=True, status='completed').count(), 0)
        self.assertEqual(self.training_world(), before)

    def test_reviews_are_on_completed_demo_gigs_and_the_averages_follow(self):
        output = self.seed()
        self.assertIn('sample reviews for 8 freelancers', output)
        self.assertEqual(Review.objects.count(), 15)
        for review in Review.objects.select_related('gig'):
            self.assertEqual((review.gig.status, review.gig.is_demo_extra), ('completed', True))
            self.assertTrue(Application.objects.filter(
                gig=review.gig, freelancer=review.freelancer, status='hired', is_demo_extra=True,
            ).exists())
        amina = self.demo_freelancers[0].freelancer_profile
        amina.refresh_from_db()
        self.assertEqual((amina.rating_avg, amina.rating_count), (Decimal('4.67'), 3))
        self.assertTrue(Review.objects.exclude(freelancer_reply='').exists())
        self.assertFalse(Notification.objects.exists())  # seeding is quiet

    def test_running_it_again_replaces_the_reviews(self):
        self.seed()
        self.seed()
        self.assertEqual(Review.objects.count(), 15)
        amina = self.demo_freelancers[0].freelancer_profile
        amina.refresh_from_db()
        self.assertEqual(amina.rating_count, 3)

    def test_the_sample_chats_and_the_sample_reviews_leave_each_other_alone(self):
        self.seed('seed_demo_conversations')
        self.seed()
        self.seed('seed_demo_conversations')
        self.assertEqual(Conversation.objects.count(), 3)
        self.assertEqual(Review.objects.count(), 15)
        self.seed()
        self.assertEqual(Conversation.objects.count(), 3)
