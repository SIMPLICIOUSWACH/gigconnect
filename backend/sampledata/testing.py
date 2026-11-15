"""Helpers for the sampledata tests: a small sample world like the one the seed commands make."""

import shutil
import tempfile
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from accounts.models import User
from adminpanel.testing import AdminTestMixin
from applications.models import Application
from gigs.models import Category, Gig
from profiles.models import Skill

from .text import GROUP_CATEGORY, SKILL_CATEGORY_OVERRIDE, SKILL_GROUP

SKILL_SETS = [
    ['Graphic Design', 'Logo Design'], ['React', 'JavaScript'], ['Content Writing'], ['Photography', 'Video Editing'],
    ['Social Media Management', 'Digital Marketing'], ['Excel', 'Bookkeeping'], ['Carpentry'], ['Python', 'Web Development'],
]


def ensure_skills():
    """Every skill the sample data uses, since the test database only holds what the migrations add."""
    for name, group in SKILL_GROUP.items():
        Skill.objects.get_or_create(name=name, defaults={'category': group.title()})


def ensure_categories():
    for name in set(GROUP_CATEGORY.values()) | set(SKILL_CATEGORY_OVERRIDE.values()):
        Category.objects.get_or_create(name=name)


class SampleWorld(AdminTestMixin):
    """Sample freelancers and clients in the shape seed_data makes, plus enough applications to split and train on."""

    freelancer_count = 10
    client_count = 6

    def build_sample_world(self):
        ensure_skills()
        ensure_categories()
        self.clients = [
            self.make_user(f'seed-client-{n}@example.test', User.Role.CLIENT, is_synthetic=True,
                           full_name=f'Client Person {n}')
            for n in range(1, self.client_count + 1)
        ]
        for client in self.clients:
            client.client_profile.company_name = f'Pwani {client.full_name.split()[-1]} Traders'
            client.client_profile.industry = 'retail'
            client.client_profile.save()
        self.freelancers = []
        for number in range(1, self.freelancer_count + 1):
            freelancer = self.make_user(f'seed-freelancer-{number}@example.test', User.Role.FREELANCER,
                                        is_synthetic=True, full_name=f'Free Lancer{number}')
            freelancer.freelancer_profile.bio = 'Experienced professional who delivers reliable work on time.'
            freelancer.freelancer_profile.save()
            freelancer.freelancer_profile.skills.set(Skill.objects.filter(name__in=SKILL_SETS[number % len(SKILL_SETS)]))
            self.freelancers.append(freelancer)
        # Ordinary training data: the old seeded gigs, applied to over a month, so the evaluation split has something.
        now = timezone.now()
        category = Category.objects.first()
        for number in range(8):
            gig = Gig.objects.create(
                client=self.clients[number % len(self.clients)], category=category, title=f'Seeded gig {number}',
                description='A seeded gig from the original data.', budget_min=1000, budget_max=3000,
                deadline=now.date() + timedelta(days=20), is_synthetic=True,
            )
            for freelancer in self.freelancers[:6]:
                application = Application.objects.create(
                    gig=gig, freelancer=freelancer, cover_letter='I have done this before and can start this week.',
                    is_synthetic=True,
                )
                Application.objects.filter(pk=application.pk).update(created_at=now - timedelta(days=40 - number))
        # A real person: never touched.
        self.real = self.make_user('real.person@gmail.com', User.Role.FREELANCER, full_name='Real Person')

    def run_command(self, *args):
        output = StringIO()
        call_command(*args, stdout=output)
        return output.getvalue()


class TempMedia:
    """Run a test with its own media folders and its own recommender data folder, so nothing touches real files."""

    def setUp(self):
        super().setUp()
        self._folders = [tempfile.mkdtemp() for _ in range(3)]
        override = override_settings(
            MEDIA_ROOT=self._folders[0], PRIVATE_MEDIA_ROOT=self._folders[1], RECOMMENDER_DATA_DIR=self._folders[2],
            DEBUG=True,
        )
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(lambda: [shutil.rmtree(folder, ignore_errors=True) for folder in self._folders])
