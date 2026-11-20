import json

from django.test import override_settings
from rest_framework.test import APIClient

from applications.models import Application
from gigs.models import GigInvite

from . import content, registry
from .test_base import RecommenderTestBase
from .training import train

LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'


class SuggestedFreelancersTests(RecommenderTestBase):
    """ "Suggested for this gig": the content model's ranking of findable freelancers for one open gig. """

    def setUp(self):
        super().setUp()
        self.enterContext(self.settings(RECOMMENDER_SVD_COMPONENTS=2))
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.api = APIClient()
        self.api.force_authenticate(self.client_user)
        self.gig = self.gigs['P'][12]  # asks for the Python-ish skills; nobody has touched it
        self.url = f'/api/gigs/{self.gig.pk}/suggested-freelancers/'

    def suggested(self):
        response = self.api.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def ids(self):
        return [row['id'] for row in self.suggested()['results']]

    def test_up_to_six_with_the_gigs_skills_and_the_same_labels_as_applicant_cards(self):
        data = self.suggested()
        self.assertEqual(data['suggestions'], {'available': True, 'reason': None})
        self.assertEqual(set(self.ids()), {str(user.pk) for user in self.freelancers['P']})
        for row in data['results']:
            self.assertGreater(row['match_score'], 0)
            self.assertEqual(row['match_reasons'], ['Pyskill 1', 'Pyskill 2'])
            self.assertIn(row['match_band'], ('strong', 'good', 'some'))
            self.assertFalse(row['invited'])

    def test_the_scores_are_the_content_models_scores_best_first(self):
        # One freelancer with only half the gig's skills must come after those with both.
        partial = self.make_user('rec-partial@example.com', 'freelancer')
        partial.freelancer_profile.skills.set(self.skills['P'][:1])
        applicant = self.freelancers['P'][0]
        Application.objects.create(gig=self.gig, freelancer=applicant, cover_letter=LETTER)

        rows = self.suggested()['results']
        scores = [row['match_score'] for row in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(rows[-1]['id'], str(partial.pk))

        profiles = [user.freelancer_profile for user in [*self.freelancers['P'][1:], partial]]
        expected = content.score_applicants(registry.availability().model.vectoriser, self.gig, profiles)
        for row in rows:
            user_id = next(key for key in expected if str(key) == row['id'])
            self.assertAlmostEqual(row['match_score'], round(expected[user_id].score, 4))

    def test_people_who_already_applied_are_left_out(self):
        applicant = self.freelancers['P'][0]
        Application.objects.create(gig=self.gig, freelancer=applicant, cover_letter=LETTER)
        ids = self.ids()
        self.assertNotIn(str(applicant.pk), ids)
        self.assertEqual(len(ids), 5)

    def test_nobody_with_nothing_in_common_is_suggested(self):
        other_group = {str(user.pk) for user in self.freelancers['X']}
        self.assertFalse(other_group & set(self.ids()))

    def test_hidden_and_suspended_freelancers_are_never_suggested(self):
        hidden, suspended = self.freelancers['P'][0], self.freelancers['P'][1]
        hidden.freelancer_profile.search_visible = False
        hidden.freelancer_profile.save()
        suspended.account_status = 'suspended'
        suspended.save()
        ids = self.ids()
        self.assertNotIn(str(hidden.pk), ids)
        self.assertNotIn(str(suspended.pk), ids)

    def test_at_most_six(self):
        for index in range(4):
            extra = self.make_user(f'rec-extra{index}@example.com', 'freelancer')
            extra.freelancer_profile.skills.set(self.skills['P'])
        self.assertEqual(len(self.ids()), 6)

    def test_an_invited_freelancer_stays_and_is_marked(self):
        invited = self.freelancers['P'][2]
        GigInvite.objects.create(gig=self.gig, client=self.client_user, freelancer=invited)
        rows = {row['id']: row['invited'] for row in self.suggested()['results']}
        self.assertTrue(rows[str(invited.pk)])
        self.assertEqual(sum(rows.values()), 1)

    def test_only_the_owner_and_only_open_gigs(self):
        other = self.make_user('rec-other-client@example.com', 'client')
        self.api.force_authenticate(other)
        self.assertEqual(self.api.get(self.url).status_code, 404)
        self.api.force_authenticate(self.freelancers['P'][0])
        self.assertEqual(self.api.get(self.url).status_code, 403)
        self.api.force_authenticate(self.client_user)
        self.gig.status = 'in_progress'
        self.gig.save()
        data = self.suggested()
        self.assertEqual((data['results'], data['suggestions']['reason']), ([], 'gig_not_open'))

    def test_no_model_means_no_suggestions_and_says_why(self):
        with override_settings(RECOMMENDATIONS_ENABLED=False):
            data = self.suggested()
        self.assertEqual(data['results'], [])
        self.assertEqual(data['suggestions'], {'available': False, 'reason': 'disabled'})

    def test_cards_carry_no_private_fields(self):
        body = json.dumps(self.api.get(self.url).json())
        for user in self.freelancers['P']:
            self.assertNotIn(user.email, body)
            self.assertNotIn(user.phone, body)
        self.assertNotIn('id_number', body)
