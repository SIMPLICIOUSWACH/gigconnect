from datetime import date, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from applications.models import Application
from gigs.models import Category, Gig, GigInteraction

from . import collaborative as collab

LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'

SMALL = {
    'RECOMMENDER_SVD_MIN_FREELANCERS': 1,
    'RECOMMENDER_SVD_MIN_GIGS': 1,
    'RECOMMENDER_SVD_MIN_INTERACTIONS': 1,
}


class LoadWeightsTests(TestCase):
    """The weights are built only from data the recommender may learn from (see platform.py)."""

    def setUp(self):
        self.category = Category.objects.create(name='Collaborative Test Category')
        self.client_user = self.make_user('collab-client@example.com', 'client')
        self.real = self.make_user('collab-real@example.com', 'freelancer')
        self.synthetic = self.make_user('collab-synthetic@example.com', 'freelancer', is_synthetic=True)
        self.deleted = self.make_user('collab-deleted@example.com', 'freelancer')
        self.gig_one = self.make_gig('Gig one')
        self.gig_two = self.make_gig('Gig two')

    def make_user(self, email, role, **extra):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password='x-Collab-pass-1', full_name=email.split('@')[0],
            phone=f'2547000008{number:02d}', role=role, **extra,
        )

    def make_gig(self, title):
        return Gig.objects.create(
            client=self.client_user, category=self.category, title=title, description='A gig.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30),
        )

    def delete_account(self, user):
        User.objects.filter(pk=user.pk).update(is_active=False, deleted_at=timezone.now())

    def interact(self, user, gig, kind, **extra):
        return GigInteraction.objects.create(gig=gig, user=user, type=kind, **extra)

    def test_interactions_and_applications_become_weights(self):
        self.interact(self.real, self.gig_one, 'view')
        self.interact(self.real, self.gig_two, 'save')
        Application.objects.create(gig=self.gig_two, freelancer=self.real, cover_letter=LETTER, status='shortlisted')
        weights = collab.load_weights()
        self.assertEqual(weights, {(self.real.id, self.gig_one.id): 1, (self.real.id, self.gig_two.id): 4})

    def test_a_deleted_freelancer_drops_out_of_the_weights(self):
        self.interact(self.deleted, self.gig_one, 'apply')
        Application.objects.create(gig=self.gig_two, freelancer=self.deleted, cover_letter='', status='withdrawn')
        self.assertEqual(len(collab.load_weights()), 2)  # while the account exists, both count
        self.delete_account(self.deleted)
        self.assertEqual(collab.load_weights(), {})

    def test_deleting_an_account_removes_only_that_freelancers_rows(self):
        self.interact(self.real, self.gig_one, 'view')
        self.interact(self.deleted, self.gig_one, 'view')
        self.delete_account(self.deleted)
        self.assertEqual(collab.load_weights(), {(self.real.id, self.gig_one.id): 1})

    def test_anonymous_visitors_clients_and_unknown_types_are_ignored(self):
        GigInteraction.objects.create(gig=self.gig_one, session_key='anonymous-visitor', type='view')
        self.interact(self.client_user, self.gig_one, 'view')
        self.interact(self.real, self.gig_one, 'something_new')
        self.assertEqual(collab.load_weights(), {})

    def test_synthetic_rows_and_people_can_be_left_out(self):
        self.interact(self.real, self.gig_one, 'view')
        self.interact(self.real, self.gig_two, 'view', is_synthetic=True)
        self.interact(self.synthetic, self.gig_one, 'view')
        Application.objects.create(gig=self.gig_two, freelancer=self.synthetic, cover_letter=LETTER, is_synthetic=True)
        self.assertEqual(len(collab.load_weights(include_synthetic=True)), 4)
        self.assertEqual(collab.load_weights(include_synthetic=False), {(self.real.id, self.gig_one.id): 1})

    def test_the_weights_feed_straight_into_the_model(self):
        # Two freelancers and two gigs is enough to fit once the limits are lowered.
        other = self.make_user('collab-other@example.com', 'freelancer')
        self.interact(self.real, self.gig_one, 'view')
        self.interact(self.real, self.gig_two, 'apply')
        self.interact(other, self.gig_one, 'view')  # other has not touched gig two, so there is something to score
        with override_settings(**SMALL):
            model = collab.fit(collab.load_weights())
        scores = collab.score(model, self.real.id, [self.gig_one.id, self.gig_two.id])
        self.assertTrue(all(value is not None for value in scores.values()))

    def test_loading_the_weights_takes_two_queries_however_much_data_there_is(self):
        for index in range(20):
            self.interact(self.real, self.make_gig(f'Extra {index}'), 'view')
        with self.assertNumQueries(2):
            collab.load_weights()
