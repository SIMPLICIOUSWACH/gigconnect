from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from accounts.models import User
from gigs.models import GigInteraction

from . import collaborative as collab
from .management.commands.summarise_relevance import summarise
from .platform import interactions_for_training
from .recommend import gigs_interacted_with
from .test_api import RecommendationsApiBase

RELEVANT = GigInteraction.Type.RECOMMENDATION_RELEVANT
NOT_RELEVANT = GigInteraction.Type.RECOMMENDATION_NOT_RELEVANT
PASSWORD = 'x-Recommender-pass-1'


class RelevanceBase(RecommendationsApiBase):
    def setUp(self):
        super().setUp()
        self.freelancer = self.freelancers['P'][0]
        self.gig = self.gigs['P'][12]  # never interacted with

    def answer(self, user, relevant, gig=None, position=None):
        self.api.force_authenticate(user=user)
        body = {'relevant': relevant}
        if position is not None:
            body['position'] = position
        return self.api.put(reverse('recommendation-relevance', args=[(gig or self.gig).id]), body, format='json')

    def answers(self, user=None):
        return list(GigInteraction.objects.filter(
            user=user or self.freelancer, type__in=GigInteraction.RELEVANCE_TYPES,
        ).values_list('gig_id', 'type', 'position'))


class RelevancePermissionTests(RelevanceBase):
    def test_signed_out_is_refused(self):
        self.api.force_authenticate(user=None)
        response = self.api.put(reverse('recommendation-relevance', args=[self.gig.id]), {'relevant': True})
        self.assertEqual(response.status_code, 401)

    def test_a_client_is_refused(self):
        self.client_user.is_email_verified = True
        self.client_user.save(update_fields=['is_email_verified'])
        self.assertEqual(self.answer(self.client_user, True).status_code, 403)

    def test_an_unverified_freelancer_is_refused(self):
        User.objects.filter(pk=self.freelancer.pk).update(is_email_verified=False)
        self.freelancer.refresh_from_db()
        self.assertEqual(self.answer(self.freelancer, True).status_code, 403)
        self.assertEqual(self.answers(), [])

    @override_settings(RECOMMENDATIONS_ENABLED=False)
    def test_nothing_is_stored_while_recommendations_are_switched_off(self):
        response = self.answer(self.freelancer, True)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['detail'], 'Recommendations are switched off.')
        self.assertEqual(self.answers(), [])

    def test_an_unknown_gig_is_not_found(self):
        self.api.force_authenticate(user=self.freelancer)
        url = reverse('recommendation-relevance', args=['00000000-0000-0000-0000-000000000000'])
        self.assertEqual(self.api.put(url, {'relevant': True}, format='json').status_code, 404)

    def test_an_answer_must_say_relevant_or_not(self):
        self.api.force_authenticate(user=self.freelancer)
        url = reverse('recommendation-relevance', args=[self.gig.id])
        self.assertEqual(self.api.put(url, {}, format='json').status_code, 400)
        self.assertEqual(self.api.put(url, {'relevant': True, 'position': 0}, format='json').status_code, 400)


class RelevanceAnswerTests(RelevanceBase):
    def test_an_answer_is_stored_with_its_position(self):
        response = self.answer(self.freelancer, True, position=3)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['relevance'], 'relevant')
        self.assertEqual(self.answers(), [(self.gig.id, RELEVANT, 3)])

    def test_the_answer_can_be_changed_and_only_the_latest_is_kept(self):
        self.answer(self.freelancer, True, position=3)
        response = self.answer(self.freelancer, False, position=4)
        self.assertEqual(response.data['relevance'], 'not_relevant')
        self.assertEqual(self.answers(), [(self.gig.id, NOT_RELEVANT, 4)])

    def test_answering_the_same_twice_keeps_one(self):
        self.answer(self.freelancer, True, position=1)
        self.answer(self.freelancer, True, position=1)
        self.assertEqual(len(self.answers()), 1)

    def test_each_freelancer_has_their_own_answer(self):
        other = self.freelancers['P'][1]
        self.answer(self.freelancer, True)
        self.answer(other, False)
        self.assertEqual([kind for _, kind, _ in self.answers()], [RELEVANT])
        self.assertEqual([kind for _, kind, _ in self.answers(other)], [NOT_RELEVANT])

    def test_the_recommendations_show_each_freelancers_own_answer(self):
        rows = self.get(self.freelancer, page_size=50).data['results']
        self.assertTrue(rows)
        self.assertEqual({row['relevance'] for row in rows}, {None})
        first, second = rows[0]['id'], rows[1]['id']
        self.answer(self.freelancer, True, gig=self.gigs_by_id(first))
        self.answer(self.freelancer, False, gig=self.gigs_by_id(second))
        rows = {row['id']: row['relevance'] for row in self.get(self.freelancer, page_size=50).data['results']}
        self.assertEqual((rows[first], rows[second]), ('relevant', 'not_relevant'))
        others = {row['relevance'] for row in self.get(self.freelancers['P'][1], page_size=50).data['results']}
        self.assertEqual(others, {None})

    def gigs_by_id(self, gig_id):
        from gigs.models import Gig

        return Gig.objects.get(pk=gig_id)


class RelevanceNeverFeedsTrainingTests(RelevanceBase):
    def test_answers_are_left_out_of_the_training_data(self):
        before = collab.load_weights()
        self.answer(self.freelancer, True)
        self.answer(self.freelancers['X'][0], False)
        self.assertEqual(collab.load_weights(), before)
        kinds = set(interactions_for_training().values_list('type', flat=True))
        self.assertFalse(kinds & set(GigInteraction.RELEVANCE_TYPES))

    def test_answering_does_not_count_as_history_so_it_never_changes_the_blend(self):
        before = gigs_interacted_with(self.freelancer)
        for gig in self.gigs['X'][:5]:
            self.answer(self.freelancer, True, gig=gig)
        self.assertEqual(gigs_interacted_with(self.freelancer), before)

    def test_neither_type_has_a_training_weight(self):
        from django.conf import settings

        for kind in GigInteraction.RELEVANCE_TYPES:
            self.assertNotIn(kind, settings.RECOMMENDER_INTERACTION_WEIGHTS)


class RelevancePrivacyTests(RelevanceBase):
    def test_answers_are_in_the_data_export(self):
        self.answer(self.freelancer, True, position=2)
        self.api.force_authenticate(user=self.freelancer)
        exported = self.api.get(reverse('settings-export-data')).data['gig_interactions']
        self.assertIn(RELEVANT, {row['type'] for row in exported})

    def test_answers_are_deleted_with_the_account(self):
        self.answer(self.freelancer, True)
        self.api.force_authenticate(user=self.freelancer)
        response = self.api.post(reverse('settings-delete-account'), {'password': PASSWORD}, format='json')
        self.assertIn(response.status_code, (200, 204), response.data)
        self.assertEqual(self.answers(), [])


class SummariseTests(SimpleTestCase):
    """Counts worked out by hand. Rows are (type, position, gig, freelancer)."""

    def setUp(self):
        self.rows = [
            (RELEVANT, 1, 'g1', 'a'), (NOT_RELEVANT, 2, 'g2', 'a'), (RELEVANT, 6, 'g3', 'a'),
            (NOT_RELEVANT, 11, 'g1', 'b'), (RELEVANT, None, 'g2', 'b'),
        ]

    def test_overall(self):
        found = summarise(self.rows)
        self.assertEqual((found['answers'], found['freelancers'], found['relevant']), (5, 2, 3))
        self.assertEqual(found['no_position'], 1)

    def test_within_the_top_5_and_top_10(self):
        found = summarise(self.rows)
        self.assertEqual(found['within'][5], (1, 2))  # positions 1 and 2: one relevant
        self.assertEqual(found['within'][10], (2, 3))  # positions 1, 2 and 6: two relevant

    def test_per_gig(self):
        self.assertEqual(summarise(self.rows)['per_gig'], {'g1': (1, 1), 'g2': (1, 1), 'g3': (1, 0)})

    def test_nothing_to_summarise(self):
        found = summarise([])
        self.assertEqual((found['answers'], found['within'][5], found['per_gig']), (0, (0, 0), {}))


class SummariseCommandTests(RelevanceBase):
    def run_command(self, *args):
        out = StringIO()
        call_command('summarise_relevance', *args, stdout=out)
        return out.getvalue()

    def test_it_counts_real_answers_and_leaves_synthetic_accounts_out_unless_asked(self):
        self.answer(self.freelancer, True, position=1)
        self.answer(self.freelancers['P'][1], False, position=7)
        synthetic = self.freelancers['X'][0]
        User.objects.filter(pk=synthetic.pk).update(is_synthetic=True)
        synthetic.refresh_from_db()
        self.answer(synthetic, True, position=2)

        output = self.run_command()
        self.assertIn('Answers: 2 from 2 freelancer(s). Rated relevant: 1 of 2.', output)
        self.assertIn('Within the top 5: 1 rated relevant out of 1 rated.', output)
        self.assertIn('Within the top 10: 1 rated relevant out of 2 rated.', output)
        self.assertNotIn('%', output)

        output = self.run_command('--include-synthetic')
        self.assertIn('Answers: 3 from 3 freelancer(s). Rated relevant: 2 of 3.', output)
