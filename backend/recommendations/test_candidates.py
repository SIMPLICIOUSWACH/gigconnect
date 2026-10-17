from datetime import date, timedelta

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from applications.models import Application
from applications.transitions import Status
from gigs.models import Category, Gig

from .candidates import candidate_gigs

LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'


@override_settings(SHOW_SYNTHETIC=True)
class CandidateGigTests(APITestCase):
    """The recommender may only suggest gigs the freelancer could really apply to."""

    def setUp(self):
        self.category = Category.objects.create(name='Candidate Test Category')
        self.client_user = self.make_user('candidate-client@example.com', 'client')
        self.freelancer = self.make_user('candidate-freelancer@example.com', 'freelancer')
        self.other_freelancer = self.make_user('candidate-other@example.com', 'freelancer')

        self.open_gig = self.make_gig('Open gig')
        self.closed_gig = self.make_gig('Closed gig', status=Gig.Status.CLOSED)
        self.in_progress_gig = self.make_gig('In progress gig', status=Gig.Status.IN_PROGRESS)
        self.past_deadline_gig = self.make_gig('Past deadline gig')
        Gig.objects.filter(pk=self.past_deadline_gig.pk).update(application_deadline=date.today() - timedelta(days=1))
        self.own_gig = self.make_gig('Own gig', client=self.freelancer)
        self.applied_gig = self.make_gig('Applied gig')
        self.withdrawn_gig = self.make_gig('Withdrawn gig')
        self.rejected_gig = self.make_gig('Rejected gig')
        self.someone_elses_application_gig = self.make_gig('Someone else applied')

        self.apply_to(self.applied_gig, Status.PENDING)
        self.apply_to(self.withdrawn_gig, Status.WITHDRAWN)
        self.apply_to(self.rejected_gig, Status.REJECTED)
        Application.objects.create(
            gig=self.someone_elses_application_gig, freelancer=self.other_freelancer, cover_letter=LETTER,
        )

    def make_user(self, email, role):
        number = User.objects.count() + 1
        user = User.objects.create_user(
            email=email, password='x-Candidate-pass-1', full_name=email.split('@')[0],
            phone=f'2547000006{number:02d}', role=role,
        )
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        return user

    def make_gig(self, title, client=None, **extra):
        return Gig.objects.create(
            client=client or self.client_user, category=self.category, title=title, description='A gig.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30), **extra,
        )

    def apply_to(self, gig, status):
        return Application.objects.create(gig=gig, freelancer=self.freelancer, cover_letter=LETTER, status=status)

    def titles(self, **kwargs):
        return {gig.title for gig in candidate_gigs(self.freelancer, **kwargs)}

    def test_only_gigs_the_freelancer_could_apply_to_are_candidates(self):
        self.assertEqual(self.titles(), {'Open gig', 'Someone else applied'})

    def test_closed_in_progress_and_past_deadline_gigs_are_not_candidates(self):
        titles = self.titles()
        for name in ('Closed gig', 'In progress gig', 'Past deadline gig'):
            self.assertNotIn(name, titles)

    def test_own_gigs_are_not_candidates(self):
        self.assertNotIn('Own gig', self.titles())

    def test_a_gig_with_any_application_of_theirs_is_not_a_candidate_whatever_its_status(self):
        titles = self.titles()
        for name in ('Applied gig', 'Withdrawn gig', 'Rejected gig'):
            self.assertNotIn(name, titles)

    def test_another_freelancers_application_does_not_rule_a_gig_out(self):
        self.assertIn('Someone else applied', self.titles())

    def test_the_other_freelancer_sees_a_different_set(self):
        titles = {gig.title for gig in candidate_gigs(self.other_freelancer)}
        self.assertIn('Applied gig', titles)
        self.assertNotIn('Someone else applied', titles)

    @override_settings(SHOW_SYNTHETIC=False)
    def test_synthetic_gigs_follow_the_feeds_setting(self):
        self.make_gig('Synthetic gig', is_synthetic=True)
        self.assertNotIn('Synthetic gig', self.titles())
        with override_settings(SHOW_SYNTHETIC=True):
            self.assertIn('Synthetic gig', self.titles())

    def test_candidates_match_the_public_feed_for_the_gigs_they_share(self):
        feed = self.client.get(reverse('gig-list-create'), {'page_size': 50}).data['results']
        feed_titles = {gig['title'] for gig in feed}
        self.assertTrue(self.titles() <= feed_titles)

    def test_candidates_agree_with_the_real_apply_endpoint(self):
        """For every gig, applying works exactly when the gig is a candidate."""
        candidates = {gig.id for gig in candidate_gigs(self.freelancer)}
        self.client.force_authenticate(user=self.freelancer)
        for gig in Gig.objects.exclude(client=self.other_freelancer):
            response = self.client.post(
                reverse('gig-applications', args=[gig.id]), {'cover_letter': LETTER}, format='json',
            )
            self.assertEqual(
                response.status_code == 201, gig.id in candidates,
                f'{gig.title}: apply gave {response.status_code}, candidate={gig.id in candidates}',
            )

    def test_the_candidate_query_does_not_grow_with_the_number_of_gigs(self):
        for index in range(10):
            self.make_gig(f'Extra {index}')
        with self.assertNumQueries(2):  # the gigs with their categories joined in, then all their skills
            [(gig.category.name, [s.name for s in gig.skills.all()]) for gig in candidate_gigs(self.freelancer)]
