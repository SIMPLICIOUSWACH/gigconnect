import os

from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User
from profiles.models import ClientProfile, FreelancerProfile, PortfolioItem
from recommendations.platform import freelancers_for_training

from .models import SampleRecord
from .snapshot import differences, training_snapshot
from .testing import SampleWorld, TempMedia


class EnrichProfilesTests(TempMedia, SampleWorld, TestCase):
    def setUp(self):
        super().setUp()
        self.build_sample_world()

    def snapshot(self):
        return training_snapshot()

    def profile_of(self, user):
        return FreelancerProfile.objects.get(user=user)

    def test_it_fills_the_profiles_and_leaves_bios_and_skills_alone(self):
        bios = {p.pk: (p.bio, sorted(s.name for s in p.skills.all())) for p in FreelancerProfile.objects.all()}
        self.run_command('enrich_sample_data')
        for freelancer in self.freelancers:
            profile = self.profile_of(freelancer)
            self.assertTrue(profile.headline)
            self.assertGreaterEqual(profile.starting_price, 1000)
            self.assertEqual(profile.starting_price % 500, 0)
            self.assertTrue(profile.county)
            self.assertTrue(profile.profile_photo and os.path.exists(profile.profile_photo.path))
            self.assertTrue(2 <= profile.portfolio_items.count() <= 4)
            for item in profile.portfolio_items.all():
                self.assertTrue(item.title and item.description and os.path.exists(item.image.path))
        for profile in FreelancerProfile.objects.all():
            self.assertEqual((profile.bio, sorted(s.name for s in profile.skills.all())), bios[profile.pk])

    def test_availability_and_remote_are_a_mix(self):
        self.run_command('enrich_sample_data')
        profiles = [self.profile_of(f) for f in self.freelancers]
        self.assertGreater(len({p.profile_colour for p in profiles}), 1)

    def test_clients_get_a_logo(self):
        self.run_command('enrich_sample_data')
        for client in self.clients:
            profile = ClientProfile.objects.get(user=client)
            self.assertTrue(profile.company_logo and os.path.exists(profile.company_logo.path))

    def test_a_filled_field_is_never_overwritten(self):
        profile = self.profile_of(self.freelancers[0])
        profile.headline, profile.starting_price, profile.county = 'My own headline', 12345, 'Kisumu'
        profile.save()
        self.run_command('enrich_sample_data')
        profile.refresh_from_db()
        self.assertEqual((profile.headline, profile.starting_price, profile.county), ('My own headline', 12345, 'Kisumu'))

    def test_real_accounts_are_untouched(self):
        self.run_command('enrich_sample_data')
        profile = self.profile_of(self.real)
        self.assertEqual((profile.headline, profile.starting_price, bool(profile.profile_photo)), ('', None, False))
        self.assertEqual(profile.portfolio_items.count(), 0)

    def test_running_it_twice_adds_nothing(self):
        self.run_command('enrich_sample_data')
        counts = (PortfolioItem.objects.count(), SampleRecord.objects.count(), len(os.listdir(self.media_folder())))
        output = self.run_command('enrich_sample_data')
        self.assertEqual(
            counts, (PortfolioItem.objects.count(), SampleRecord.objects.count(), len(os.listdir(self.media_folder()))),
        )
        self.assertIn('nothing new', output)

    def media_folder(self):
        from django.conf import settings
        return os.path.join(settings.MEDIA_ROOT, 'portfolio')

    def test_it_makes_the_same_choices_every_time(self):
        self.run_command('enrich_sample_data')
        first = [(p.headline, p.starting_price, p.county) for p in FreelancerProfile.objects.order_by('user__email')]
        self.run_command('enrich_sample_data', '--undo')
        self.run_command('enrich_sample_data')
        second = [(p.headline, p.starting_price, p.county) for p in FreelancerProfile.objects.order_by('user__email')]
        self.assertEqual(first, second)

    def test_a_dry_run_saves_nothing(self):
        before = list(FreelancerProfile.objects.values_list('pk', 'headline', 'county', 'profile_photo'))
        output = self.run_command('enrich_sample_data', '--dry-run')
        self.assertIn('Dry run', output)
        self.assertEqual(list(FreelancerProfile.objects.values_list('pk', 'headline', 'county', 'profile_photo')), before)
        self.assertEqual(PortfolioItem.objects.count(), 0)
        self.assertEqual(SampleRecord.objects.count(), 0)
        from django.conf import settings
        self.assertFalse(os.path.exists(os.path.join(settings.MEDIA_ROOT, 'profile_photos')))

    def test_undo_removes_only_what_it_added(self):
        own = self.profile_of(self.freelancers[1])
        own.headline = 'Mine'
        own.save()
        before = list(FreelancerProfile.objects.order_by('pk').values(
            'pk', 'headline', 'county', 'starting_price', 'is_available', 'open_to_remote', 'profile_colour',
            'profile_photo',
        ))
        self.run_command('enrich_sample_data')
        with self.captureOnCommitCallbacks(execute=True):
            self.run_command('enrich_sample_data', '--undo')
        after = list(FreelancerProfile.objects.order_by('pk').values(
            'pk', 'headline', 'county', 'starting_price', 'is_available', 'open_to_remote', 'profile_colour',
            'profile_photo',
        ))
        self.assertEqual(after, before)
        self.assertEqual(PortfolioItem.objects.count(), 0)
        self.assertEqual(SampleRecord.objects.count(), 0)

    def test_the_training_world_is_identical_before_and_after(self):
        before = self.snapshot()
        self.run_command('enrich_sample_data')
        self.assertEqual(differences(before, self.snapshot()), {})
        self.assertEqual(freelancers_for_training().count(), before['freelancers_for_training'])

    @override_settings(DEBUG=False)
    def test_nothing_runs_when_debug_is_off(self):
        with self.assertRaises(CommandError):
            self.run_command('enrich_sample_data')
        self.assertEqual(SampleRecord.objects.count(), 0)

    def test_it_refuses_the_planted_demo_database(self):
        self.make_user('planted-freelancer-1@example.test', User.Role.FREELANCER, is_synthetic=True)
        with self.assertRaises(CommandError):
            self.run_command('enrich_sample_data')
