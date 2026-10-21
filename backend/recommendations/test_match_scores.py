from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from applications.models import Application

from . import registry
from .models import RecommenderModelVersion
from .recommend import recommend
from .test_base import RecommenderTestBase
from .training import train

LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'
MATCH_FIELDS = {'match_score', 'match_reasons', 'match_band'}


class MatchScoreBase(RecommenderTestBase):
    def setUp(self):
        super().setUp()
        self.enterContext(self.settings(RECOMMENDER_SVD_COMPONENTS=2))
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.api = APIClient()
        # The gig being applied to belongs to the client and asks for the Python-ish skills.
        self.gig = self.gigs['P'][12]
        self.same_skills = self.freelancers['P'][1]
        self.other_skills = self.freelancers['X'][1]
        self.nothing_to_compare = self.make_user('rec-blank@example.com', 'freelancer')  # no skills, no bio
        self.apps = {
            'same': self.apply(self.same_skills),
            'other': self.apply(self.other_skills),
            'blank': self.apply(self.nothing_to_compare),
        }

    def apply(self, user):
        return Application.objects.create(gig=self.gig, freelancer=user, cover_letter=LETTER)

    def applicants(self, user=None, **params):
        self.api.force_authenticate(user=user or self.client_user)
        return self.api.get(reverse('gig-applications', args=[self.gig.id]), params)

    def rows(self, **params):
        return {row['id']: row for row in self.applicants(**params).data['results']}


class MatchScoreTests(MatchScoreBase):
    def test_every_applicant_row_has_the_three_match_fields(self):
        for row in self.rows().values():
            self.assertTrue(MATCH_FIELDS <= set(row))

    def test_an_applicant_with_the_gigs_skills_gets_a_score_the_skills_and_a_band(self):
        row = self.rows()[str(self.apps['same'].id)]
        self.assertGreater(row['match_score'], 0)
        self.assertLessEqual(row['match_score'], 1)
        self.assertEqual(row['match_reasons'], ['Pyskill 1', 'Pyskill 2'])
        self.assertIn(row['match_band'], ('strong', 'good', 'some'))

    def test_an_applicant_who_shares_no_skill_has_a_real_score_of_zero_and_no_band(self):
        row = self.rows()[str(self.apps['other'].id)]
        self.assertEqual(row['match_score'], 0.0)
        self.assertEqual(row['match_reasons'], [])
        self.assertIsNone(row['match_band'])

    def test_an_applicant_with_nothing_to_compare_gets_no_score_not_zero(self):
        row = self.rows()[str(self.apps['blank'].id)]
        self.assertIsNone(row['match_score'])
        self.assertEqual(row['match_reasons'], [])
        self.assertIsNone(row['match_band'])

    def test_the_score_is_the_content_models_score_for_that_freelancer_and_that_gig(self):
        row = self.rows()[str(self.apps['same'].id)]
        model = registry.availability().model
        expected = recommend(model, self.same_skills, candidates=[self.gig]).results[0].content_score
        self.assertAlmostEqual(row['match_score'], expected, places=3)

    def test_the_response_says_scores_are_available(self):
        self.assertEqual(self.applicants().data['match_scores'], {'available': True, 'reason': None})

    def test_the_rest_of_the_response_is_unchanged(self):
        data = self.applicants().data
        self.assertEqual(data['status_counts']['total'], 3)
        self.assertEqual(data['count'], 3)
        self.assertIn('allowed_next_statuses', data['results'][0])

    def test_the_status_filter_still_works_with_scores(self):
        Application.objects.filter(pk=self.apps['other'].pk).update(status='shortlisted')
        self.assertEqual(len(self.applicants(status='shortlisted').data['results']), 1)


class NoScoreWhenThereIsNoModelTests(MatchScoreBase):
    def assertNoScores(self, reason):
        data = self.applicants().data
        self.assertEqual(data['match_scores'], {'available': False, 'reason': reason})
        for row in data['results']:
            self.assertIsNone(row['match_score'])
            self.assertEqual(row['match_reasons'], [])
            self.assertIsNone(row['match_band'])

    @override_settings(RECOMMENDATIONS_ENABLED=False)
    def test_switched_off(self):
        self.assertNoScores('disabled')

    def test_no_trained_model(self):
        RecommenderModelVersion.objects.all().delete()
        registry.clear_cache()
        self.assertNoScores('model_unavailable')

    def test_the_list_still_works_with_no_applicants(self):
        Application.objects.all().delete()
        data = self.applicants().data
        self.assertEqual(data['results'], [])
        self.assertTrue(data['match_scores']['available'])


class WhoCanSeeScoresTests(MatchScoreBase):
    def test_only_the_gigs_owner_can_open_the_list(self):
        other_client = self.make_user('rec-other-client@example.com', 'client')
        self.assertEqual(self.applicants(user=other_client).status_code, 403)
        self.assertEqual(self.applicants(user=self.same_skills).status_code, 403)

    def test_an_applicant_never_sees_a_match_field_on_their_own_application(self):
        self.api.force_authenticate(user=self.same_skills)
        detail = self.api.get(reverse('application-detail', args=[self.apps['same'].id])).data
        self.assertFalse(MATCH_FIELDS & set(detail))
        listing = self.api.get(reverse('my-applications')).data
        for row in listing['results']:
            self.assertFalse(MATCH_FIELDS & set(row))

    def test_the_gigs_owner_does_not_get_a_match_field_on_a_single_application_either(self):
        self.api.force_authenticate(user=self.client_user)
        detail = self.api.get(reverse('application-detail', args=[self.apps['same'].id])).data
        self.assertFalse(MATCH_FIELDS & set(detail))


class QueryCountTests(MatchScoreBase):
    def queries(self):
        self.applicants()  # warm the model cache
        with CaptureQueriesContext(connection) as queries:
            response = self.applicants()
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def test_the_number_of_queries_does_not_grow_with_the_number_of_applicants(self):
        before = self.queries()
        for index in range(8):
            user = self.make_user(f'rec-more-{index}@example.com', 'freelancer')
            user.freelancer_profile.skills.set(self.skills['P'])
            self.apply(user)
        self.assertEqual(self.queries(), before)

    def test_scoring_adds_only_two_queries_over_not_scoring(self):
        with_model = self.queries()
        with override_settings(RECOMMENDATIONS_ENABLED=False):
            without_model = self.queries()
        self.assertEqual(with_model - without_model, 2)  # the gig's category and skills
