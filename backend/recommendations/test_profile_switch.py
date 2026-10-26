from django.apps import apps
from django.test import override_settings

from gigs.models import GigInteraction

from . import registry
from .models import RecommenderModelVersion
from .recommend import recommend
from .test_base import RecommenderTestBase
from .testing import profile_settings
from .training import train


class NothingIsStoredTests(RecommenderTestBase):
    def test_the_recommendations_app_stores_no_recommendations_per_person(self):
        models = list(apps.get_app_config('recommendations').get_models())
        self.assertEqual(models, [RecommenderModelVersion])
        related = [f for f in RecommenderModelVersion._meta.get_fields() if f.is_relation]
        self.assertEqual(related, [])  # a model version belongs to nobody


class ProfileSwitchTests(RecommenderTestBase):
    """
    Recommendations are worked out on each request from the settings, so switching the profile and restarting the
    server changes the blend at once. There is nothing stored to regenerate.
    """

    def setUp(self):
        super().setUp()
        self.enterContext(self.settings(RECOMMENDER_SVD_COMPONENTS=2))
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.model = registry.availability().model
        # Each freelancer has viewed 9 gigs. One more makes 10, the demo profile's cold-start threshold.
        self.freelancer = self.freelancers['P'][0]
        GigInteraction.objects.create(user=self.freelancer, gig=self.gigs['X'][0], type='view')

    def test_production_gives_content_only(self):
        with override_settings(**profile_settings('production')):
            result = recommend(self.model, self.freelancer)
        self.assertEqual(result.weight, 0.0)
        self.assertEqual({r.source for r in result.results}, {'content'})

    def test_demo_blends_with_the_weight_its_settings_give(self):
        # 10 gigs, cold start below 10, ramp 50, largest weight 0.5: step 1 of 50, so w = 0.5 * 1 / 50 = 0.01.
        with override_settings(**profile_settings('demo')):
            result = recommend(self.model, self.freelancer)
        self.assertAlmostEqual(result.weight, 0.01)
        self.assertIn('hybrid', {r.source for r in result.results})

    def test_switching_profile_changes_the_scores_with_nothing_regenerated(self):
        versions = RecommenderModelVersion.objects.count()
        with override_settings(**profile_settings('production')):
            before = {r.gig_id: r.score for r in recommend(self.model, self.freelancer).results}
        with override_settings(**profile_settings('demo')):
            after = {r.gig_id: r.score for r in recommend(self.model, self.freelancer).results}
        self.assertEqual(set(before), set(after))  # the same gigs, scored again on the spot
        self.assertNotEqual(before, after)
        self.assertEqual(RecommenderModelVersion.objects.count(), versions)  # no retraining, nothing written

    def test_below_the_demo_threshold_a_freelancer_still_gets_content_only(self):
        other = self.freelancers['P'][1]  # 9 gigs, below the demo threshold of 10
        with override_settings(**profile_settings('demo')):
            result = recommend(self.model, other)
        self.assertEqual(result.weight, 0.0)
        self.assertEqual({r.source for r in result.results}, {'content'})
