import csv

from django.urls import reverse
from rest_framework.test import APIClient

from applications.models import Application
from gigs.models import GigInteraction

from . import collaborative, registry
from .test_base import RecommenderTestBase
from .training import train

PASSWORD = 'x-Recommender-pass-1'
LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'


def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


class DeletedFreelancerTests(RecommenderTestBase):
    """A freelancer who deletes their account drops out of the recommender at the next training run."""

    def setUp(self):
        super().setUp()
        self.enterContext(self.settings(RECOMMENDER_SVD_COMPONENTS=2))
        self.api = APIClient()
        self.leaver = self.freelancers['P'][0]
        # Their history includes a click on a recommendation, which must go with them.
        GigInteraction.objects.create(user=self.leaver, gig=self.gigs['P'][11], type='recommendation_click', position=2)

    def train(self):
        return train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)

    def delete_account(self, user):
        self.api.force_authenticate(user=user)
        return self.api.post(reverse('settings-delete-account'), {'password': PASSWORD}, format='json')

    def test_their_interactions_including_recommendation_clicks_are_deleted_with_the_account(self):
        self.assertTrue(GigInteraction.objects.filter(user=self.leaver).exists())
        self.assertEqual(self.delete_account(self.leaver).status_code, 200)
        self.assertFalse(GigInteraction.objects.filter(user=self.leaver).exists())

    def add_pairs_so_the_data_stays_above_the_minimum_after_they_leave(self):
        """Eleven more pairs: everyone else saves one gig nobody had touched. 109 + 11 = 120, and 110 once they go."""
        rows = []
        for group in ('P', 'X'):
            for user in self.freelancers[group]:
                if user != self.leaver:
                    rows.append(GigInteraction(user=user, gig=self.gigs[group][10], type='save'))
        GigInteraction.objects.bulk_create(rows)

    def test_deleting_enough_people_can_leave_too_little_data_and_the_run_says_so(self):
        # 109 pairs, 99 once the freelancer is gone: below the minimum of 100, so there is no collaborative part.
        first = self.train()
        self.assertTrue(first.collaborative_fitted)
        self.delete_account(self.leaver)
        second = self.train()
        self.assertEqual(second.interactions, 99)
        self.assertFalse(second.collaborative_fitted)
        self.assertIn('pairs with an interaction', second.collaborative_skipped_reason)
        registry.clear_cache()
        self.assertIsNone(registry.availability().model.collaborative)
        self.assertTrue(registry.availability().available)  # the content model still works

    def test_the_next_training_run_does_not_contain_them_anywhere(self):
        self.add_pairs_so_the_data_stays_above_the_minimum_after_they_leave()
        before = self.train()
        registry.clear_cache()
        self.assertIn(self.leaver.id, registry.availability().model.collaborative.user_index)

        self.delete_account(self.leaver)
        after = self.train()
        registry.clear_cache()

        self.assertEqual((before.freelancers, after.freelancers), (12, 11))
        # Their ten pairs, and nothing else: nine views plus the click on a recommendation added in setUp.
        self.assertEqual(after.interactions, before.interactions - 10)
        self.assertNotIn(self.leaver.id, registry.availability().model.collaborative.user_index)
        self.assertNotIn(self.leaver.id, {user for user, _ in collaborative.load_weights()})
        platform = self.data_dir / 'platform'
        for name in ('freelancers', 'interactions', 'applications'):
            ids = {row['freelancer_id'] for row in read_csv(platform / f'{name}.csv')}
            self.assertNotIn(str(self.leaver.id), ids, name)

    def test_until_the_next_run_the_old_model_still_holds_their_row_of_numbers(self):
        # This is a known limit, and it is documented: deletion does not rewrite a model already trained.
        # What the model holds for them is a row of factor values, not their interactions or profile.
        self.train()
        self.delete_account(self.leaver)
        registry.clear_cache()
        self.assertIn(self.leaver.id, registry.availability().model.collaborative.user_index)

    def test_their_erased_applications_do_not_count_as_training_data(self):
        Application.objects.create(gig=self.gigs['P'][12], freelancer=self.leaver, cover_letter=LETTER)
        self.delete_account(self.leaver)
        self.assertNotIn(self.leaver.id, {user for user, _ in collaborative.load_weights()})
        self.train()
        applications = read_csv(self.data_dir / 'platform' / 'applications.csv')
        self.assertNotIn(str(self.leaver.id), {row['freelancer_id'] for row in applications})

    def test_other_freelancers_are_untouched_by_someone_elses_deletion(self):
        before = {user for user, _ in collaborative.load_weights()}
        self.delete_account(self.leaver)
        self.assertEqual({user for user, _ in collaborative.load_weights()}, before - {self.leaver.id})


class DataExportTests(RecommenderTestBase):
    """Nothing about recommendations is stored per person, so there is nothing extra to export."""

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.person = self.freelancers['P'][1]
        GigInteraction.objects.create(user=self.person, gig=self.gigs['P'][11], type='recommendation_click', position=4)

    def export(self):
        self.api.force_authenticate(user=self.person)
        return self.api.get(reverse('settings-export-data')).data

    def test_their_clicks_on_recommendations_are_in_the_export_like_any_other_interaction(self):
        clicks = [row for row in self.export()['gig_interactions'] if row['type'] == 'recommendation_click']
        self.assertEqual(len(clicks), 1)
        self.assertEqual((clicks[0]['position'], clicks[0]['gig_title']), (4, self.gigs['P'][11].title))

    def test_no_recommendations_are_stored_so_the_export_has_no_such_section(self):
        data = self.export()
        self.assertNotIn('recommendations', data)
        self.assertNotIn('recommendation', ' '.join(key for key in data if key != 'gig_interactions'))

    def test_training_a_model_does_not_add_anything_about_a_person_to_the_export(self):
        before = self.export()
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.assertEqual(self.export(), before)


class DeletedApplicantMatchTests(RecommenderTestBase):
    """A client is never shown a match score worked out from a deleted person's data."""

    def setUp(self):
        super().setUp()
        self.enterContext(self.settings(RECOMMENDER_SVD_COMPONENTS=2))
        train(include_synthetic=True, data_dir=self.data_dir, artifact_dir=self.artifact_dir)
        self.api = APIClient()
        self.gig = self.gigs['P'][12]
        self.stayer = self.freelancers['P'][1]
        self.leaver = self.freelancers['P'][2]
        for user in (self.stayer, self.leaver):
            Application.objects.create(gig=self.gig, freelancer=user, cover_letter=LETTER)

    def rows(self):
        self.api.force_authenticate(user=self.client_user)
        results = self.api.get(reverse('gig-applications', args=[self.gig.id])).data['results']
        return {row['applicant']['id']: row for row in results}

    def test_a_deleted_applicant_gets_no_score_and_the_others_still_do(self):
        self.api.force_authenticate(user=self.leaver)
        self.api.post(reverse('settings-delete-account'), {'password': PASSWORD}, format='json')
        rows = self.rows()
        gone = rows[str(self.leaver.id)]
        self.assertIsNone(gone['match_score'])
        self.assertEqual(gone['match_reasons'], [])
        self.assertIsNone(gone['match_band'])
        self.assertEqual(gone['applicant']['full_name'], 'Deleted User')
        self.assertIsNotNone(rows[str(self.stayer.id)]['match_score'])
