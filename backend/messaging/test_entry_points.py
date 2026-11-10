from rest_framework.test import APITestCase

from .testing import ChatTestMixin


class EntryPointTests(ChatTestMixin, APITestCase):
    """Pages that link into a chat get its id: the client's applicants and My gigs, the freelancer's applications."""

    def setUp(self):
        self.conversation = self.make_hire()
        self.gig = self.conversation.gig
        self.hired = self.conversation.application
        other = self.make_user('other@example.com', 'freelancer', full_name='Achieng Studio')
        self.pending = self.apply(self.gig, other)

    def test_the_client_sees_the_chat_on_the_hired_applicant_only(self):
        self.client.force_authenticate(self.conversation.client)
        rows = self.client.get(f'/api/gigs/{self.gig.pk}/applications/').data['results']
        by_id = {row['id']: row['conversation_id'] for row in rows}
        self.assertEqual(by_id, {str(self.hired.pk): str(self.conversation.pk), str(self.pending.pk): None})

    def test_my_gigs_lists_the_chats(self):
        self.client.force_authenticate(self.conversation.client)
        gigs = self.client.get('/api/gigs/mine/').data
        gigs = gigs['results'] if isinstance(gigs, dict) else gigs
        self.assertEqual(gigs[0]['chats'], [
            {'conversation_id': str(self.conversation.pk), 'freelancer_name': 'Otieno Designs', 'started': False},
        ])

    def test_the_freelancer_sees_the_chat_on_their_application(self):
        self.client.force_authenticate(self.conversation.freelancer)
        rows = self.client.get('/api/applications/mine/').data['results']
        self.assertEqual(rows[0]['conversation_id'], str(self.conversation.pk))
        detail = self.client.get(f'/api/applications/{self.hired.pk}/').data
        self.assertEqual(detail['conversation_id'], str(self.conversation.pk))
