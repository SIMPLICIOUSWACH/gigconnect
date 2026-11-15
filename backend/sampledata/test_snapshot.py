from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from adminpanel.testing import AdminTestMixin
from applications.models import Application
from gigs.models import Gig, GigInteraction
from recommendations.platform import freelancers_for_training

from .snapshot import differences, training_snapshot


class TrainingWorld(AdminTestMixin):
    """Two freelancers with enough applications to be split, on real (unflagged) gigs."""

    def build_world(self):
        self.client_user = self.make_user('client@example.test', User.Role.CLIENT, is_synthetic=True)
        self.freelancers = [
            self.make_user(f'freelancer{n}@example.test', User.Role.FREELANCER, is_synthetic=True) for n in (1, 2)
        ]
        now = timezone.now()
        for number in range(9):
            gig = self.make_gig(self.client_user, title=f'Gig {number}', is_synthetic=True)
            for freelancer in self.freelancers:
                application = self.apply(gig, freelancer, is_synthetic=True)
                Application.objects.filter(pk=application.pk).update(created_at=now - timedelta(days=30 - number))
                GigInteraction.objects.create(user=freelancer, gig=gig, type='view', is_synthetic=True)

    def snapshot(self):
        return training_snapshot(check_saved=False)


class SnapshotTests(TrainingWorld, TestCase):
    def setUp(self):
        self.build_world()

    def test_it_counts_the_training_world(self):
        snapshot = self.snapshot()
        self.assertEqual(snapshot['freelancers_for_training'], 2)
        self.assertEqual(snapshot['gigs_for_training'], 9)
        self.assertEqual(snapshot['applications_for_training'], 18)
        self.assertEqual(snapshot['evaluated_freelancers'], 2)
        self.assertEqual(self.snapshot(), snapshot)  # reading it twice gives the same answer

    def test_flagged_rows_change_nothing(self):
        before = self.snapshot()
        showcase = self.make_user('showcase@example.test', User.Role.FREELANCER, is_synthetic=True, is_demo_extra=True)
        gig = self.make_gig(self.client_user, title='Showcase gig', is_synthetic=True, is_demo_extra=True)
        for freelancer in (showcase, *self.freelancers):
            self.apply(gig, freelancer, is_synthetic=True, is_demo_extra=True)
        GigInteraction.objects.create(user=showcase, gig=gig, type='view', is_synthetic=True)
        self.assertEqual(differences(before, self.snapshot()), {})

    def test_the_showcase_accounts_are_not_training_freelancers(self):
        self.make_user('showcase@example.test', User.Role.FREELANCER, is_synthetic=True, is_demo_extra=True)
        self.assertEqual(freelancers_for_training().count(), 2)

    def test_it_notices_an_unflagged_change(self):
        before = self.snapshot()
        gig = self.make_gig(self.client_user, title='Ordinary new gig', is_synthetic=True)
        self.apply(gig, self.freelancers[0], is_synthetic=True)
        changed = differences(before, self.snapshot())
        self.assertIn('applications_for_training', changed)
        self.assertIn('split_fingerprint', changed)

    def test_nothing_is_flagged_by_default(self):
        self.assertEqual(Gig.objects.filter(is_demo_extra=True).count(), 0)
