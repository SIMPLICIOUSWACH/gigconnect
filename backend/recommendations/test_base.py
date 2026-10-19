import tempfile
from datetime import date, timedelta
from pathlib import Path

from django.test import TestCase, override_settings

from accounts.models import User
from gigs.models import Category, Gig, GigInteraction
from profiles.models import Skill

from . import registry

PER_GROUP = 6  # freelancers in each skill group
GIGS_PER_GROUP = 13  # the first 10 are interacted with, the last 3 are never touched (new gigs)
INTERACTED = 10
VIEWED_EACH = 9  # each freelancer viewed 9 of the 10 interacted gigs


class RecommenderTestBase(TestCase):
    """
    A small world that meets the real minimums for the collaborative model: 12 freelancers, 20 gigs with
    interactions and 108 pairs. Freelancers come in two groups (Python-ish and Excel-ish skills), and each
    freelancer has viewed 9 of their group's 10 gigs, so each has one gig in their group they have not seen.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = Path(self.tmp.name) / 'datasets'
        self.artifact_dir = Path(self.tmp.name) / 'artifacts'
        self.enterContext(override_settings(
            RECOMMENDER_DATA_DIR=self.data_dir,
            RECOMMENDER_ARTIFACT_DIR=self.artifact_dir,
            RECOMMENDER_TFIDF_MIN_DF=1,
            RECOMMENDER_TFIDF_MAX_DF=1.0,
            RECOMMENDATIONS_ENABLED=True,
            SHOW_SYNTHETIC=True,
            RECOMMENDER_MODEL_CACHE_SECONDS=60,
        ))
        registry.clear_cache()
        self.addCleanup(registry.clear_cache)

        self.category = Category.objects.create(name='Recommender Test Category')
        self.skills = {
            'P': [Skill.objects.create(name=f'Pyskill {n}', category='Test') for n in (1, 2)],
            'X': [Skill.objects.create(name=f'Xlskill {n}', category='Test') for n in (1, 2)],
        }
        self.client_user = self.make_user('rec-client@example.com', 'client')
        self.freelancers = {'P': [], 'X': []}
        for group in ('P', 'X'):
            for index in range(PER_GROUP):
                user = self.make_user(f'rec-{group.lower()}{index}@example.com', 'freelancer')
                user.freelancer_profile.skills.set(self.skills[group])
                self.freelancers[group].append(user)
        self.gigs = {'P': [], 'X': []}
        for group in ('P', 'X'):
            for index in range(GIGS_PER_GROUP):
                self.gigs[group].append(self.make_gig(f'{group.lower()}task{index}', group))
        self.add_history()

    def make_user(self, email, role, **extra):
        number = User.objects.count() + 1
        user = User.objects.create_user(
            email=email, password='x-Recommender-pass-1', full_name=email.split('@')[0],
            phone=f'254700009{number:03d}', role=role, **extra,
        )
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        return user

    def make_gig(self, title, group, **extra):
        gig = Gig.objects.create(
            client=self.client_user, category=self.category, title=title,
            description=f'Please help with the {title} work for our team',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30), **extra,
        )
        gig.skills.set(self.skills[group])
        return gig

    def add_history(self):
        # The Python-ish group only views gigs and the Excel-ish group saves them (a stronger signal). That
        # makes the two groups' patterns different in strength. Built identically they would tie exactly,
        # and the SVD may then return an arbitrary mix of the two, which real data would never do.
        kind = {'P': 'view', 'X': 'save'}
        rows = []
        for group in ('P', 'X'):
            for position, user in enumerate(self.freelancers[group]):
                for step in range(VIEWED_EACH):
                    gig = self.gigs[group][(position + step) % INTERACTED]
                    rows.append(GigInteraction(user=user, gig=gig, type=kind[group]))
        GigInteraction.objects.bulk_create(rows)

    def unseen_in_group(self, group, position):
        """The one interacted gig in this freelancer's group that they have not viewed."""
        seen = {self.gigs[group][(position + step) % INTERACTED].id for step in range(VIEWED_EACH)}
        return next(gig for gig in self.gigs[group][:INTERACTED] if gig.id not in seen)
