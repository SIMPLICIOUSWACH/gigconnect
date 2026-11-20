import os
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from adminpanel.testing import AdminTestMixin
from gigs.models import Gig
from profiles.models import FreelancerProfile, PortfolioItem

from .guard import require_debug
from .ledger import Ledger, undo
from .models import SampleRecord


class LedgerTests(AdminTestMixin, TestCase):
    def setUp(self):
        self.ledger = Ledger('enrich')
        self.client_user = self.make_user('client@example.test', User.Role.CLIENT, is_synthetic=True)
        self.freelancer = self.make_user('freelancer@example.test', User.Role.FREELANCER, is_synthetic=True)

    def test_undo_deletes_only_what_was_recorded(self):
        mine = self.make_gig(self.client_user, title='Made by the command', is_demo_extra=True)
        self.apply(mine, self.freelancer, is_demo_extra=True)
        yours = self.make_gig(self.client_user, title='Was already there')
        self.ledger.created(mine)
        undo('enrich')
        self.assertFalse(Gig.objects.filter(pk=mine.pk).exists())
        self.assertTrue(Gig.objects.filter(pk=yours.pk).exists())
        self.assertEqual(mine.applications.count(), 0)
        self.assertFalse(SampleRecord.objects.exists())

    def test_undo_puts_back_a_changed_field_and_a_date(self):
        profile = self.freelancer.freelancer_profile
        profile.headline = 'Written by me'
        profile.save()
        old_joined = self.freelancer.created_at
        self.ledger.remember(profile, 'headline')
        self.ledger.remember(self.freelancer, 'created_at')
        FreelancerProfile.objects.filter(pk=profile.pk).update(headline='Made up by the command')
        User.objects.filter(pk=self.freelancer.pk).update(created_at=old_joined - timedelta(days=200))
        undo('enrich')
        profile.refresh_from_db()
        self.freelancer.refresh_from_db()
        self.assertEqual(profile.headline, 'Written by me')
        self.assertEqual(self.freelancer.created_at, old_joined)

    def test_the_first_remembered_value_wins(self):
        profile = self.freelancer.freelancer_profile
        profile.headline = 'First'
        profile.save()
        self.ledger.remember(profile, 'headline')
        profile.headline = 'Second'
        profile.save()
        self.ledger.remember(profile, 'headline')
        self.assertEqual(SampleRecord.objects.get(kind='changed', field='headline').old_value, 'First')

    def test_undo_deletes_a_generated_image_and_blanks_the_field(self):
        profile = self.freelancer.freelancer_profile
        self.ledger.remember(profile, 'profile_photo')
        profile.profile_photo.save('sample-test-avatar.png', ContentFile(b'not really a png'), save=True)
        path = profile.profile_photo.path
        self.assertTrue(os.path.exists(path))
        with self.captureOnCommitCallbacks(execute=True):
            undo('enrich')
        profile.refresh_from_db()
        self.assertFalse(profile.profile_photo)
        self.assertFalse(os.path.exists(path))

    def test_batches_do_not_touch_each_other(self):
        gig = self.make_gig(self.client_user, title='A showcase gig', is_demo_extra=True)
        Ledger('showcase').created(gig)
        item = PortfolioItem.objects.create(freelancer=self.freelancer.freelancer_profile, title='Enrich item')
        self.ledger.created(item)
        undo('enrich')
        self.assertTrue(Gig.objects.filter(pk=gig.pk).exists())
        self.assertFalse(PortfolioItem.objects.filter(pk=item.pk).exists())

    def test_done_markers_and_the_anchor(self):
        self.assertFalse(self.ledger.is_done(self.freelancer, 'history'))
        self.ledger.mark_done(self.freelancer, 'history')
        self.ledger.mark_done(self.freelancer, 'history')  # twice is fine
        self.assertTrue(self.ledger.is_done(self.freelancer, 'history'))
        self.assertIsNone(self.ledger.anchor())
        self.ledger.set_anchor(timezone.localdate())
        self.assertEqual(self.ledger.anchor(), timezone.localdate().isoformat())


class GuardTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_nothing_runs_when_debug_is_off(self):
        with self.assertRaises(CommandError):
            require_debug()

    @override_settings(DEBUG=True)
    def test_it_runs_in_development(self):
        require_debug()
