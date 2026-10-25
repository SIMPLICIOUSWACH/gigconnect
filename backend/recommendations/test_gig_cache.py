from unittest import mock

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from gigs.models import Gig
from profiles.models import FreelancerProfile

from . import content, registry
from .candidates import candidate_gigs
from .recommend import attach_gigs, recommend
from .test_base import RecommenderTestBase
from .training import train


class GigCacheTests(RecommenderTestBase):
    def setUp(self):
        super().setUp()
        self.enterContext(self.settings(RECOMMENDER_SVD_COMPONENTS=2))
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.model = registry.availability().model
        self.cache = self.model.gig_cache

    def uncached(self, user):
        """The ranking the content model gave before the cache: every candidate loaded and scored from scratch."""
        profile = FreelancerProfile.objects.prefetch_related('skills').get(user=user)
        gigs = candidate_gigs(user).select_related('category').prefetch_related('skills')
        return content.rank_for_freelancer(self.model.vectoriser, profile, gigs)

    def put_skills(self, gig, skills):
        """Edit a gig the way the app does (a full PUT by its owner), changing only its skills."""
        api = APIClient()
        self.client_user.is_email_verified = True
        self.client_user.save(update_fields=['is_email_verified'])
        api.force_authenticate(self.client_user)
        payload = {
            'title': gig.title, 'description': gig.description, 'category': str(gig.category_id),
            'budget_min': str(gig.budget_min), 'budget_max': str(gig.budget_max), 'deadline': gig.deadline.isoformat(),
            'skills': [str(skill.id) for skill in skills],
        }
        return api.put(reverse('gig-detail', args=[gig.id]), payload, format='json')

    def test_the_cached_ranking_is_exactly_the_uncached_one(self):
        newcomer = self.make_user('cache-new@example.com', 'freelancer')
        newcomer.freelancer_profile.skills.set(self.skills['X'])
        for user in (newcomer, self.make_user('cache-p@example.com', 'freelancer')):
            if user != newcomer:
                user.freelancer_profile.skills.set(self.skills['P'] + self.skills['X'][:1])
            cached = recommend(self.model, user).results  # newcomers are in cold start: content scores only
            before = self.uncached(user)
            self.assertEqual([r.gig_id for r in cached], [m.gig.id for m in before])
            for result, match in zip(cached, before):
                self.assertAlmostEqual(result.content_score, match.score)
                self.assertEqual(result.match_reasons, match.match_reasons)

    def test_entries_are_built_on_the_first_request_and_reused_after(self):
        person = self.freelancers['P'][0]
        self.assertEqual(len(self.cache), 0)  # nothing is built until it is needed
        recommend(self.model, person)
        built = self.cache.built
        self.assertEqual(built, candidate_gigs(person).count())
        recommend(self.model, person)
        recommend(self.model, self.freelancers['X'][0])
        self.assertEqual(self.cache.built, built)  # the same gigs, unchanged: nothing built again

    def test_a_warm_request_does_not_load_the_candidate_gigs(self):
        person = self.freelancers['P'][0]
        recommend(self.model, person)
        with CaptureQueriesContext(connection) as queries:
            recommend(self.model, person)
        loaded = [q['sql'] for q in queries if 'FROM "gigs_gig"' in q['sql'] and '"gigs_gig"."title"' in q['sql']]
        self.assertEqual(loaded, [])  # only ids and updated_at were read

    def test_editing_a_gig_through_the_api_rebuilds_its_entry(self):
        person = self.freelancers['P'][0]
        gig = self.gigs['P'][12]  # never interacted with, so a candidate for everyone
        before = {r.gig_id: r for r in recommend(self.model, person).results}[gig.id]
        self.assertTrue(before.match_reasons)
        built = self.cache.built

        response = self.put_skills(gig, self.skills['X'])
        self.assertEqual(response.status_code, 200, response.data)

        after = {r.gig_id: r for r in recommend(self.model, person).results}[gig.id]
        self.assertEqual(self.cache.built, built + 1)  # only the edited gig
        self.assertEqual(after.match_reasons, [])  # its skills are now the other group's
        self.assertLess(after.content_score, before.content_score)

    def test_a_skills_only_edit_still_moves_updated_at_after_the_skills_change(self):
        gig = self.gigs['P'][12]
        before = Gig.objects.get(pk=gig.pk).updated_at
        response = self.put_skills(gig, [self.skills['X'][0]])
        self.assertEqual(response.status_code, 200, response.data)
        gig = Gig.objects.get(pk=gig.pk)
        self.assertGreater(gig.updated_at, before)
        self.assertEqual([s.name for s in gig.skills.all()], [self.skills['X'][0].name])

    def test_the_save_that_moves_updated_at_already_sees_the_new_skills(self):
        # If the skills were set after the save, a request in between could cache the new updated_at with the old
        # skills, and that entry would never be noticed as out of date. Record the skills at the moment of the save.
        gig = self.gigs['P'][12]
        seen = []
        original = Gig.save

        def recording_save(instance, *args, **kwargs):
            seen.append(sorted(instance.skills.values_list('name', flat=True)))
            return original(instance, *args, **kwargs)

        with mock.patch.object(Gig, 'save', recording_save):
            self.assertEqual(self.put_skills(gig, [self.skills['X'][0]]).status_code, 200)
        self.assertEqual(seen, [[self.skills['X'][0].name]])

    def test_a_new_model_version_starts_with_an_empty_cache(self):
        recommend(self.model, self.freelancers['P'][0])
        self.assertGreater(len(self.cache), 0)
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        registry.clear_cache()
        newer = registry.availability().model
        self.assertNotEqual(newer.version.version, self.model.version.version)
        self.assertIsNot(newer.gig_cache, self.cache)
        self.assertEqual(len(newer.gig_cache), 0)

    def test_a_gig_deleted_after_its_id_was_read_is_left_out(self):
        gig = self.gigs['P'][12]
        rows = [(gig.id, gig.updated_at), (self.gigs['P'][11].id, self.gigs['P'][11].updated_at)]
        Gig.objects.filter(pk=gig.pk).delete()
        found = self.cache.entries(rows)
        self.assertEqual(list(found), [self.gigs['P'][11].id])

    def test_only_the_results_shown_get_their_gig_loaded(self):
        results = recommend(self.model, self.freelancers['P'][0]).results
        self.assertTrue(all(r.gig is None for r in results))
        shown = attach_gigs(results[:3])
        self.assertEqual([r.gig.id for r in shown], [r.gig_id for r in results[:3]])
        self.assertTrue(all(r.gig is None for r in results[3:]))

    def test_the_timing_command_measures_and_leaves_no_gig_behind(self):
        from io import StringIO

        from django.core.management import call_command

        before = Gig.objects.count()
        out = StringIO()
        call_command('time_recommendations', '--extra-open-gigs', '15', '--requests', '1', stdout=out)
        self.assertEqual(Gig.objects.count(), before)  # the extra gigs were rolled back
        output = out.getvalue()
        self.assertIn('with 15 extra open gigs added for the measurement and removed after', output)
        self.assertIn('median', output)
        self.assertIn('95th percentile', output)

    def test_without_a_model_nothing_is_cached_and_the_answer_is_still_not_available(self):
        registry.clear_cache()
        self.enterContext(self.settings(RECOMMENDER_ARTIFACT_DIR=self.artifact_dir / 'missing'))
        self.assertEqual(registry.availability().reason, registry.MODEL_UNAVAILABLE)
        self.assertIsNone(registry.availability().model)
