from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from applications.models import Application
from gigs.models import Gig, GigInteraction

from . import registry
from .models import RecommenderModelVersion
from .test_base import RecommenderTestBase
from .training import train

GIG_CARD_FIELDS = {
    'id', 'title', 'client_id', 'client_name', 'category', 'budget_min', 'budget_max', 'currency', 'deadline',
    'application_deadline', 'is_negotiable', 'county', 'is_remote', 'status', 'skills', 'created_at',
}
EXTRA_FIELDS = {'score', 'match_reasons', 'source'}


class RecommendationsApiBase(RecommenderTestBase):
    def setUp(self):
        super().setUp()
        # The test world has exactly two groups of freelancers, so two hidden factors is the right model for it.
        self.enterContext(self.settings(RECOMMENDER_SVD_COMPONENTS=2))
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.api = APIClient()
        self.url = reverse('recommendations')

    def get(self, user, **params):
        self.api.force_authenticate(user=user)
        return self.api.get(self.url, params)

    def newcomer(self, email='rec-new@example.com', skills=True):
        user = self.make_user(email, 'freelancer')
        if skills:
            user.freelancer_profile.skills.set(self.skills['P'])
        return user


class PermissionTests(RecommendationsApiBase):
    def test_signed_out_is_refused(self):
        self.api.force_authenticate(user=None)
        self.assertEqual(self.api.get(self.url).status_code, 401)

    def test_a_client_is_refused(self):
        self.assertEqual(self.get(self.client_user).status_code, 403)

    def test_an_unverified_freelancer_is_refused(self):
        user = self.make_user('rec-unverified@example.com', 'freelancer')
        user.is_email_verified = False
        user.save(update_fields=['is_email_verified'])
        self.assertEqual(self.get(user).status_code, 403)


class EmptyStateTests(RecommendationsApiBase):
    """Whenever there is nothing honest to show, the answer is a plain 200 saying why, never an error."""

    def assertEmpty(self, response, available, reason):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['available'], available)
        self.assertEqual(response.data['reason'], reason)
        self.assertEqual(response.data['results'], [])
        self.assertEqual(response.data['count'], 0)

    @override_settings(RECOMMENDATIONS_ENABLED=False)
    def test_switched_off(self):
        response = self.get(self.freelancers['P'][0])
        self.assertEmpty(response, False, 'disabled')
        self.assertIsNone(response.data['model'])
        self.assertIsNone(response.data['cold_start'])

    def test_no_trained_model(self):
        RecommenderModelVersion.objects.all().delete()
        registry.clear_cache()
        self.assertEmpty(self.get(self.freelancers['P'][0]), False, 'model_unavailable')

    def test_a_model_whose_files_are_gone(self):
        import shutil
        shutil.rmtree(self.artifact_dir)
        registry.clear_cache()
        with self.assertLogs('recommendations.registry', level='WARNING'):
            response = self.get(self.freelancers['P'][0])
        self.assertEmpty(response, False, 'model_unavailable')

    def test_a_freelancer_with_no_skills_or_bio(self):
        response = self.get(self.newcomer(skills=False))
        self.assertEmpty(response, True, 'no_skills')
        self.assertIsNotNone(response.data['model'])

    def test_no_gig_the_freelancer_could_apply_to(self):
        Gig.objects.update(status=Gig.Status.CLOSED)
        self.assertEmpty(self.get(self.newcomer()), True, None)

    def test_the_empty_answer_has_the_same_shape_as_a_full_one(self):
        with override_settings(RECOMMENDATIONS_ENABLED=False):
            empty = set(self.get(self.freelancers['P'][0]).data)
        full = set(self.get(self.freelancers['P'][0]).data)
        self.assertEqual(empty, full)


class ResultTests(RecommendationsApiBase):
    def test_a_newcomer_gets_content_recommendations_in_cold_start(self):
        response = self.get(self.newcomer())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['available'])
        self.assertIsNone(response.data['reason'])
        self.assertTrue(response.data['cold_start'])
        self.assertEqual({row['source'] for row in response.data['results']}, {'content'})

    def test_the_response_says_which_model_it_came_from(self):
        model = self.get(self.newcomer()).json()['model']  # the rendered JSON, as a browser receives it
        self.assertEqual(model['version'], 1)
        self.assertTrue(model['collaborative'])
        self.assertRegex(model['trained_at'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')

    def test_each_result_has_the_gig_card_fields_plus_score_reasons_and_source(self):
        row = self.get(self.newcomer()).data['results'][0]
        self.assertEqual(set(row), GIG_CARD_FIELDS | EXTRA_FIELDS)

    def test_scores_are_above_zero_up_to_one_and_best_first(self):
        scores = [row['score'] for row in self.get(self.newcomer()).data['results']]
        self.assertTrue(all(0 < score <= 1 for score in scores))
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_gigs_that_share_nothing_with_the_freelancer_are_not_recommended(self):
        response = self.get(self.newcomer(), page_size=50)
        titles = {row['title'] for row in response.data['results']}
        self.assertEqual(response.data['count'], 13)  # only the 13 Python-ish gigs
        self.assertEqual(len(titles), 13)
        self.assertFalse(any(title.startswith('x') for title in titles))

    def test_the_reasons_are_the_skills_really_shared(self):
        for row in self.get(self.newcomer()).data['results']:
            self.assertEqual(row['match_reasons'], ['Pyskill 1', 'Pyskill 2'])

    def test_a_freelancer_with_history_gets_hybrid_results(self):
        response = self.get(self.freelancers['P'][0])
        self.assertFalse(response.data['cold_start'])
        sources = {row['source'] for row in response.data['results']}
        self.assertIn('hybrid', sources)
        self.assertIn('content', sources)  # the gigs nobody had touched before training

    def test_gigs_the_freelancer_cannot_apply_to_are_not_recommended(self):
        person = self.freelancers['P'][0]
        applied, closed, own = self.gigs['P'][10], self.gigs['P'][11], self.make_gig('ptask-own', 'P')
        Application.objects.create(gig=applied, freelancer=person, cover_letter='x' * 60)
        Gig.objects.filter(pk=closed.pk).update(status=Gig.Status.CLOSED)
        Gig.objects.filter(pk=own.pk).update(client=person)
        ids = {row['id'] for row in self.get(person).data['results']}
        for excluded in (applied, closed, own):
            self.assertNotIn(str(excluded.id), ids)

    def test_a_gig_posted_after_training_is_recommended_on_its_text(self):
        new_gig = self.make_gig('ptask-posted-later', 'P')
        rows = {row['id']: row for row in self.get(self.newcomer()).data['results']}
        self.assertEqual(rows[str(new_gig.id)]['source'], 'content')
        self.assertGreater(rows[str(new_gig.id)]['score'], 0)

    def test_nothing_is_stored_about_what_was_recommended(self):
        before = GigInteraction.objects.count()
        self.get(self.newcomer())
        self.assertEqual(GigInteraction.objects.count(), before)


class PaginationTests(RecommendationsApiBase):
    def test_pages_work_like_the_gig_list(self):
        user = self.newcomer()
        first = self.get(user, page_size=5).data
        self.assertEqual((first['count'], first['page'], first['page_size'], first['total_pages']), (13, 1, 5, 3))
        self.assertEqual(len(first['results']), 5)
        self.assertIsNone(first['previous'])
        self.assertIn('page=2', first['next'])
        last = self.get(user, page_size=5, page=3).data
        self.assertEqual(len(last['results']), 3)
        self.assertIsNone(last['next'])

    def test_pages_do_not_overlap(self):
        user = self.newcomer()
        seen = []
        for page in (1, 2, 3):
            seen += [row['id'] for row in self.get(user, page_size=5, page=page).data['results']]
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(seen), 13)

    def test_the_default_page_size_is_the_gig_lists(self):
        self.assertEqual(self.get(self.newcomer()).data['page_size'], 12)

    def test_a_page_past_the_end_is_not_found(self):
        self.assertEqual(self.get(self.newcomer(), page=99).status_code, 404)


class QueryCountTests(RecommendationsApiBase):
    def queries_for(self, user):
        self.get(user)  # warm the model cache so only a request's own queries are counted
        with CaptureQueriesContext(connection) as queries:
            response = self.get(user)
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def test_the_number_of_queries_does_not_grow_with_the_number_of_gigs(self):
        user = self.newcomer()
        before = self.queries_for(user)
        for index in range(25):
            self.make_gig(f'ptask-extra-{index}', 'P')
        self.assertEqual(self.queries_for(user), before)

    def test_the_count_is_small(self):
        # Measured at 6 on the dev data: the profile and its skills, the candidate gigs and their skills,
        # and the freelancer's history. The page's serializer needs nothing more because the gigs arrive
        # with their client, category and skills already loaded.
        self.assertLessEqual(self.queries_for(self.newcomer()), 8)


class ClickLoggingTests(RecommendationsApiBase):
    def click(self, user, gig, **body):
        self.api.force_authenticate(user=user)
        return self.api.post(reverse('gig-interaction-create', args=[gig.id]), body, format='json')

    def test_opening_a_gig_from_the_list_is_logged_with_its_position(self):
        user = self.newcomer()
        response = self.click(user, self.gigs['P'][0], type='recommendation_click', position=3)
        self.assertEqual(response.status_code, 201)
        row = GigInteraction.objects.get(user=user, type='recommendation_click')
        self.assertEqual((row.gig_id, row.position), (self.gigs['P'][0].id, 3))

    def test_the_click_counts_as_interest_for_the_next_training_run(self):
        from . import collaborative
        user = self.newcomer()
        self.click(user, self.gigs['P'][0], type='recommendation_click', position=1)
        weights = collaborative.load_weights()
        self.assertEqual(weights[(user.id, self.gigs['P'][0].id)], 1)

    def test_other_types_still_cannot_be_posted_by_the_client(self):
        for kind in ('view', 'save', 'apply'):
            response = self.click(self.newcomer(f'rec-{kind}@example.com'), self.gigs['P'][0], type=kind)
            self.assertEqual(response.status_code, 400, kind)
        self.assertFalse(GigInteraction.objects.filter(type='apply', user__email__startswith='rec-apply').exists())

    def test_search_clicks_still_work(self):
        response = self.click(self.newcomer(), self.gigs['P'][0], type='search_click', query='django', position=2)
        self.assertEqual(response.status_code, 201)
