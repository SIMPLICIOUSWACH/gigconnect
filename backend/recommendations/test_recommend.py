from datetime import date, timedelta

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from applications.models import Application
from gigs.models import Gig, GigInteraction

from . import hybrid, registry
from .recommend import gigs_interacted_with, recommend
from .test_base import RecommenderTestBase
from .testing import HYBRID_MECHANICS
from .training import train


@override_settings(**HYBRID_MECHANICS)
class RoundTripTests(RecommenderTestBase):
    """Train, load, then score: the whole path a real request takes."""

    def setUp(self):
        super().setUp()
        # The test world has exactly two groups of freelancers with different tastes, so two hidden factors is
        # the right model for it. (The default is a larger number for real data, and is tuned in Sprint 6.)
        self.enterContext(self.settings(RECOMMENDER_SVD_COMPONENTS=2))
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.model = registry.availability().model

    def by_gig(self, recommendations):
        return {r.gig.id: r for r in recommendations.results}

    def test_a_new_freelancer_is_in_cold_start_and_gets_content_scores_only(self):
        newcomer = self.make_user('rec-new@example.com', 'freelancer')
        newcomer.freelancer_profile.skills.set(self.skills['P'])
        result = recommend(self.model, newcomer)
        self.assertTrue(result.cold_start)
        self.assertEqual(result.weight, 0.0)
        self.assertEqual(result.gigs_interacted_with, 0)
        self.assertEqual({r.source for r in result.results}, {'content'})
        self.assertEqual({r.collaborative_score for r in result.results}, {None})

    def test_results_are_best_first_and_their_own_skill_group_comes_first(self):
        newcomer = self.make_user('rec-new@example.com', 'freelancer')
        newcomer.freelancer_profile.skills.set(self.skills['P'])
        result = recommend(self.model, newcomer)
        scores = [r.score for r in result.results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        first_group_gigs = {gig.id for gig in self.gigs['P']}
        self.assertTrue({r.gig.id for r in result.results[:13]} <= first_group_gigs)

    def test_a_freelancer_with_history_gets_a_blend_for_gigs_the_model_knows(self):
        person = self.freelancers['P'][0]
        result = recommend(self.model, person)
        self.assertFalse(result.cold_start)
        self.assertEqual(result.gigs_interacted_with, 9)
        self.assertAlmostEqual(result.weight, 0.5 * (9 - 5 + 1) / 20)  # 0.125
        unseen = self.by_gig(result)[self.unseen_in_group('P', 0).id]
        self.assertEqual(unseen.source, 'hybrid')
        self.assertIsNotNone(unseen.collaborative_score)
        expected = result.weight * unseen.collaborative_score + (1 - result.weight) * unseen.content_score
        self.assertAlmostEqual(unseen.score, expected, places=9)

    def test_the_collaborative_score_favours_gigs_similar_freelancers_viewed(self):
        person = self.freelancers['P'][0]
        results = self.by_gig(recommend(self.model, person))
        own_group = results[self.unseen_in_group('P', 0).id].collaborative_score
        other_group = [
            results[gig.id].collaborative_score for gig in self.gigs['X'][:10]
        ]
        # The two groups share no gigs, so the other group's gigs score about zero. The exact value for the
        # gig this group viewed depends on which of several equally sized factors the model keeps (the two
        # groups are built identically, so those tie), so only "clearly above zero" is asserted.
        self.assertGreater(own_group, 0.3)
        self.assertLess(max(other_group), 0.1)

    def test_a_gig_posted_after_training_is_scored_on_its_text_with_no_collaborative_score(self):
        new_gig = self.make_gig('ptask-brand-new', 'P')
        result = recommend(self.model, self.freelancers['P'][0])
        scored = self.by_gig(result)[new_gig.id]
        self.assertEqual(scored.source, 'content')
        self.assertIsNone(scored.collaborative_score)
        self.assertGreater(scored.content_score, 0.0)
        self.assertEqual(scored.match_reasons, ['Pyskill 1', 'Pyskill 2'])

    def test_gigs_nobody_touched_before_training_also_have_no_collaborative_score(self):
        untouched = self.gigs['P'][12]
        scored = self.by_gig(recommend(self.model, self.freelancers['P'][0]))[untouched.id]
        self.assertEqual(scored.source, 'content')
        self.assertIsNone(scored.collaborative_score)

    def test_a_freelancer_who_joined_after_training_is_scored_on_content_even_with_history(self):
        newcomer = self.make_user('rec-late@example.com', 'freelancer')
        newcomer.freelancer_profile.skills.set(self.skills['X'])
        GigInteraction.objects.bulk_create([
            GigInteraction(user=newcomer, gig=gig, type='view') for gig in self.gigs['X'][:6]
        ])
        result = recommend(self.model, newcomer)
        self.assertFalse(result.cold_start)  # they have enough history...
        self.assertGreater(result.weight, 0.0)
        self.assertEqual({r.source for r in result.results}, {'content'})  # ...but the model has never seen them

    def test_only_gigs_the_freelancer_could_apply_to_are_scored(self):
        person = self.freelancers['P'][0]
        applied = self.gigs['P'][11]
        Application.objects.create(gig=applied, freelancer=person, cover_letter='x' * 60)
        closed = self.gigs['P'][12]
        Gig.objects.filter(pk=closed.pk).update(status=Gig.Status.CLOSED)
        past = self.make_gig('ptask-past', 'P')
        Gig.objects.filter(pk=past.pk).update(application_deadline=date.today() - timedelta(days=1))
        own = self.make_gig('ptask-own', 'P')
        Gig.objects.filter(pk=own.pk).update(client=person)
        ids = {r.gig.id for r in recommend(self.model, person).results}
        for excluded in (applied, closed, past, own):
            self.assertNotIn(excluded.id, ids)
        self.assertIn(self.gigs['P'][0].id, ids)  # viewing a gig does not rule it out

    def test_an_application_counts_as_history_for_cold_start(self):
        newcomer = self.make_user('rec-applier@example.com', 'freelancer')
        newcomer.freelancer_profile.skills.set(self.skills['P'])
        for gig in self.gigs['P'][:5]:
            Application.objects.create(gig=gig, freelancer=newcomer, cover_letter='x' * 60)
        self.assertEqual(gigs_interacted_with(newcomer), 5)
        self.assertFalse(recommend(self.model, newcomer).cold_start)

    def test_a_gig_viewed_and_applied_to_counts_once(self):
        newcomer = self.make_user('rec-once@example.com', 'freelancer')
        gig = self.gigs['P'][0]
        GigInteraction.objects.create(user=newcomer, gig=gig, type='view')
        GigInteraction.objects.create(user=newcomer, gig=gig, type='apply')
        Application.objects.create(gig=gig, freelancer=newcomer, cover_letter='x' * 60)
        self.assertEqual(gigs_interacted_with(newcomer), 1)

    def test_scores_are_between_zero_and_one(self):
        for group in ('P', 'X'):
            for person in self.freelancers[group]:
                for r in recommend(self.model, person).results:
                    self.assertGreaterEqual(r.score, 0.0)
                    self.assertLessEqual(r.score, 1.0)

    def test_the_same_request_gives_the_same_answer(self):
        person = self.freelancers['X'][2]
        first = [(r.gig.id, r.score, r.source) for r in recommend(self.model, person).results]
        second = [(r.gig.id, r.score, r.source) for r in recommend(self.model, person).results]
        self.assertEqual(first, second)

    def test_a_freelancer_with_no_skills_and_no_bio_gets_nothing(self):
        person = self.make_user('rec-blank@example.com', 'freelancer')
        result = recommend(self.model, person)
        self.assertEqual(result.results, [])
        self.assertTrue(result.cold_start)

    def test_the_number_of_queries_does_not_grow_with_the_number_of_gigs(self):
        person = self.freelancers['P'][0]
        with CaptureQueriesContext(connection) as before:
            recommend(self.model, person)
        for index in range(20):
            self.make_gig(f'ptask-extra-{index}', 'P')
        with CaptureQueriesContext(connection) as after:
            recommend(self.model, person)
        self.assertEqual(len(before), len(after))


class ContentOnlyModelTests(RecommenderTestBase):
    """A model trained while there was too little interaction data has no collaborative part."""

    def test_recommendations_still_work_and_say_content(self):
        GigInteraction.objects.all().delete()
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        model = registry.availability().model
        self.assertIsNone(model.collaborative)
        result = recommend(model, self.freelancers['P'][0])
        self.assertTrue(result.results)
        self.assertEqual({r.source for r in result.results}, {'content'})
        self.assertEqual(hybrid.hybrid_score(0.5, None, 0.5), (0.5, 'content'))
