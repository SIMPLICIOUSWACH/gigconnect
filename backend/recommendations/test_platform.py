from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from applications.models import Application
from gigs.models import Category, Gig, GigInteraction

from .platform import (
    applications_for_training,
    freelancers_for_training,
    gigs_for_training,
    interactions_for_training,
)

LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'


class PlatformDataTests(TestCase):
    """Who and what the recommender may learn from: deleted people drop out, synthetic rows are a choice."""

    def setUp(self):
        self.category = Category.objects.create(name='Platform Test Category')
        self.client_user = self.make_user('platform-client@example.com', 'client')
        self.real = self.make_user('platform-real@example.com', 'freelancer')
        self.synthetic = self.make_user('platform-synthetic@example.com', 'freelancer', is_synthetic=True)
        self.deleted = self.make_user('platform-deleted@example.com', 'freelancer')
        User.objects.filter(pk=self.deleted.pk).update(is_active=False, deleted_at=timezone.now())
        self.deleted.refresh_from_db()

        self.real_gig = self.make_gig('Real gig')
        self.synthetic_gig = self.make_gig('Synthetic gig', is_synthetic=True)

    def make_user(self, email, role, **extra):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password='x-Platform-pass-1', full_name=email.split('@')[0],
            phone=f'2547000005{number:02d}', role=role, **extra,
        )

    def make_gig(self, title, **extra):
        return Gig.objects.create(
            client=self.client_user, category=self.category, title=title, description='A gig.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30), **extra,
        )

    def emails(self, profiles):
        return {profile.user.email for profile in profiles}

    def test_freelancers_exclude_deleted_accounts_and_non_freelancers(self):
        emails = self.emails(freelancers_for_training())
        self.assertEqual(emails, {self.real.email, self.synthetic.email})

    def test_freelancers_can_leave_out_synthetic_ones(self):
        self.assertEqual(self.emails(freelancers_for_training(include_synthetic=False)), {self.real.email})

    def test_gigs_can_leave_out_synthetic_ones(self):
        self.assertEqual({g.title for g in gigs_for_training()}, {'Real gig', 'Synthetic gig'})
        self.assertEqual({g.title for g in gigs_for_training(include_synthetic=False)}, {'Real gig'})

    def test_gigs_are_included_whatever_their_status(self):
        Gig.objects.filter(pk=self.real_gig.pk).update(status=Gig.Status.CLOSED)
        self.assertIn('Real gig', {g.title for g in gigs_for_training()})

    def test_interactions_exclude_deleted_people_anonymous_visitors_and_clients(self):
        for user in (self.real, self.synthetic, self.deleted, self.client_user):
            GigInteraction.objects.create(gig=self.real_gig, user=user, type='view')
        GigInteraction.objects.create(gig=self.real_gig, session_key='anonymous-visitor', type='view')
        users = {i.user.email for i in interactions_for_training()}
        self.assertEqual(users, {self.real.email, self.synthetic.email})

    def test_interactions_leave_out_synthetic_rows_and_synthetic_people(self):
        GigInteraction.objects.create(gig=self.real_gig, user=self.real, type='view')
        GigInteraction.objects.create(gig=self.real_gig, user=self.real, type='view', is_synthetic=True)
        GigInteraction.objects.create(gig=self.real_gig, user=self.synthetic, type='view')
        self.assertEqual(interactions_for_training().count(), 3)
        self.assertEqual(interactions_for_training(include_synthetic=False).count(), 1)

    def test_applications_of_a_deleted_freelancer_are_not_training_data(self):
        Application.objects.create(gig=self.real_gig, freelancer=self.real, cover_letter=LETTER)
        Application.objects.create(gig=self.real_gig, freelancer=self.deleted, cover_letter='')
        owners = {a.freelancer.email for a in applications_for_training()}
        self.assertEqual(owners, {self.real.email})

    def test_applications_can_leave_out_synthetic_rows_and_synthetic_people(self):
        Application.objects.create(gig=self.real_gig, freelancer=self.real, cover_letter=LETTER)
        Application.objects.create(gig=self.synthetic_gig, freelancer=self.real, cover_letter=LETTER, is_synthetic=True)
        Application.objects.create(gig=self.real_gig, freelancer=self.synthetic, cover_letter=LETTER)
        self.assertEqual(applications_for_training().count(), 3)
        self.assertEqual(applications_for_training(include_synthetic=False).count(), 1)
