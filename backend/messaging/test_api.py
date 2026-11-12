from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from gigs.models import Gig

from .models import ChatReport, Conversation, Message
from .safety import SAFETY_TIP, mentions_contact_or_payment
from .testing import ChatTestMixin


class ChatApiTestCase(ChatTestMixin, APITestCase):
    def setUp(self):
        cache.clear()  # the send throttle counts live in the cache
        self.conversation = self.make_hire()
        self.client_user = self.conversation.client
        self.freelancer = self.conversation.freelancer
        self.url = f'/api/conversations/{self.conversation.pk}/'

    def send(self, user, body='Hello there'):
        self.client.force_authenticate(user)
        return self.client.post(self.url + 'messages/', {'body': body})


class FirstMessageTests(ChatApiTestCase):
    def test_the_freelancer_waits_for_the_client(self):
        response = self.send(self.freelancer)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'waiting_for_client')
        self.assertEqual(response.data['detail'], 'Wait for Wanjiru Bakers to start the conversation.')
        data = self.client.get(self.url).data
        self.assertEqual((data['waiting_for_client'], data['can_send']), (True, False))

    def test_the_client_writes_first_then_both_can(self):
        response = self.send(self.client_user, '  Hi Otieno, thanks for applying.  ')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['body'], 'Hi Otieno, thanks for applying.')
        self.assertEqual(self.send(self.freelancer, 'Thanks!').status_code, 201)
        conversation = Conversation.objects.get(pk=self.conversation.pk)
        self.assertIsNotNone(conversation.first_message_at)
        self.assertEqual(conversation.last_message_at, Message.objects.latest('created_at').created_at)


class PrivacyTests(ChatApiTestCase):
    def test_outsiders_and_admins_get_404_everywhere(self):
        outsider = self.make_user('outsider@example.com', User.Role.FREELANCER)
        admin = self.make_admin()
        self.say(self.conversation, self.client_user)
        for user in (outsider, admin):
            self.client.force_authenticate(user)
            with self.subTest(user=user.role):
                self.assertEqual(self.client.get('/api/conversations/').data['count'], 0)
                for method, path in (('get', ''), ('get', 'messages/'), ('post', 'messages/'), ('post', 'read/'),
                                     ('post', 'report/')):
                    response = getattr(self.client, method)(self.url + path, {'body': 'x', 'reason': 'x'})
                    self.assertEqual(response.status_code, 404, path)
        self.assertEqual(Message.objects.count(), 1)
        self.assertFalse(ChatReport.objects.exists())

    def test_anonymous_gets_401(self):
        self.assertEqual(self.client.get('/api/conversations/').status_code, 401)


class ReadOnlyTests(ChatApiTestCase):
    def test_a_read_only_chat_can_be_read_but_not_written(self):
        self.say(self.conversation, self.client_user)
        Gig.objects.filter(pk=self.conversation.gig_id).update(
            status='closed', status_changed_at=timezone.now() - timedelta(days=31),
        )
        response = self.send(self.client_user)
        self.assertEqual((response.status_code, response.data['code']), (403, 'read_only'))
        self.assertIn('closed more than 30 days ago', response.data['detail'])
        self.assertEqual(self.client.get(self.url + 'messages/').status_code, 200)
        data = self.client.get(self.url).data
        self.assertEqual(data['can_send'], False)
        self.assertIn('read-only', data['read_only_reason'])

    def test_a_suspended_participant_makes_it_read_only(self):
        User.objects.filter(pk=self.freelancer.pk).update(account_status='suspended', suspended_at=timezone.now())
        self.assertEqual(self.send(self.client_user).status_code, 403)

    def test_a_deleted_account_shows_as_deleted_user(self):
        self.say(self.conversation, self.freelancer, 'From before')
        User.objects.filter(pk=self.freelancer.pk).update(deleted_at=timezone.now(), full_name='Deleted User')
        self.client.force_authenticate(self.client_user)
        data = self.client.get(self.url).data
        self.assertEqual(data['other']['full_name'], 'Deleted user')
        self.assertIn('deleted', data['read_only_reason'])
        self.assertEqual(self.client.get(self.url + 'messages/').data['results'][0]['body'], 'From before')


class PollingTests(ChatApiTestCase):
    def test_after_returns_only_newer_messages(self):
        first = self.say(self.conversation, self.client_user, 'one')
        self.say(self.conversation, self.freelancer, 'two')
        self.say(self.conversation, self.client_user, 'three')
        self.client.force_authenticate(self.freelancer)
        rows = self.client.get(self.url + 'messages/', {'after': first.pk}).data['results']
        self.assertEqual([row['body'] for row in rows], ['two', 'three'])
        self.assertEqual([row['from_me'] for row in rows], [True, False])
        last = rows[-1]['id']
        self.assertEqual(self.client.get(self.url + 'messages/', {'after': last}).data['results'], [])

    def test_an_id_from_another_conversation_is_refused(self):
        other = self.make_hire(client_email='c2@example.com', freelancer_email='f2@example.com', title='Other')
        stranger = self.say(other, other.client)
        self.client.force_authenticate(self.client_user)
        self.assertEqual(self.client.get(self.url + 'messages/', {'after': stranger.pk}).status_code, 400)

    def test_the_latest_page_then_earlier_ones(self):
        for index in range(55):
            self.say(self.conversation, self.client_user, f'message {index}')
        self.client.force_authenticate(self.client_user)
        latest = self.client.get(self.url + 'messages/').data
        self.assertEqual((len(latest['results']), latest['has_earlier']), (50, True))
        self.assertEqual(latest['results'][-1]['body'], 'message 54')
        earlier = self.client.get(self.url + 'messages/', {'before': latest['results'][0]['id']}).data
        self.assertEqual([row['body'] for row in earlier['results']], [f'message {i}' for i in range(5)])
        self.assertFalse(earlier['has_earlier'])


class UnreadTests(ChatApiTestCase):
    def test_unread_counts_and_marking_read(self):
        self.say(self.conversation, self.client_user, 'one')
        self.say(self.conversation, self.client_user, 'two')
        self.client.force_authenticate(self.freelancer)
        self.assertEqual(self.client.get('/api/conversations/unread-count/').data['unread'], 2)
        row = self.client.get('/api/conversations/').data['results'][0]
        self.assertEqual((row['unread_count'], row['last_message']['body'], row['last_message']['from_me']),
                         (2, 'two', False))
        self.client.force_authenticate(self.client_user)
        self.assertEqual(self.client.get('/api/conversations/unread-count/').data['unread'], 0)

        self.client.force_authenticate(self.freelancer)
        self.assertEqual(self.client.post(self.url + 'read/').data['marked'], 2)
        self.assertEqual(self.client.get('/api/conversations/unread-count/').data['unread'], 0)
        self.client.force_authenticate(self.client_user)
        rows = self.client.get(self.url + 'messages/').data['results']
        self.assertTrue(all(row['read_at'] for row in rows))  # the client sees "Seen"

    def test_seen_up_to_comes_with_polling(self):
        first = self.say(self.conversation, self.client_user, 'one')
        second = self.say(self.conversation, self.client_user, 'two')
        self.client.force_authenticate(self.client_user)
        self.assertIsNone(self.client.get(self.url + 'messages/', {'after': second.pk}).data['seen_up_to'])
        self.client.force_authenticate(self.freelancer)
        self.client.post(self.url + 'read/')
        self.client.force_authenticate(self.client_user)
        polled = self.client.get(self.url + 'messages/', {'after': second.pk}).data
        self.assertEqual((polled['results'], polled['seen_up_to']), ([], second.pk))
        self.assertGreater(second.pk, first.pk)

    def test_the_list_puts_the_latest_activity_first(self):
        older = self.make_hire(client_email='client@example.com', freelancer_email='f2@example.com', title='Older')
        self.say(older, older.client, 'earlier')
        self.say(self.conversation, self.client_user, 'later')
        self.client.force_authenticate(self.client_user)
        titles = [row['gig']['title'] for row in self.client.get('/api/conversations/').data['results']]
        self.assertEqual(titles, ['Logo', 'Older'])


class SendingRulesTests(ChatApiTestCase):
    def test_length_limits(self):
        self.assertEqual(self.send(self.client_user, '   ').status_code, 400)
        self.assertEqual(self.send(self.client_user, 'x' * 2000).status_code, 201)
        response = self.send(self.client_user, 'x' * 2001)
        self.assertEqual(response.status_code, 400)
        self.assertIn('2,000', str(response.data['body']))

    def test_twenty_messages_a_minute(self):
        codes = [self.send(self.client_user, f'm{i}').status_code for i in range(21)]
        self.assertEqual(codes, [201] * 20 + [429])
        self.assertEqual(Message.objects.count(), 20)

    def test_the_payment_tip_shows_once_per_person_and_the_message_still_goes(self):
        response = self.send(self.client_user, 'Call me on 0712 345 678')
        self.assertEqual((response.status_code, response.data['safety_tip']), (201, SAFETY_TIP))
        self.assertIsNone(self.send(self.client_user, 'Or email me at a@b.co').data['safety_tip'])
        self.assertEqual(self.send(self.freelancer, 'M-Pesa till 123456?').data['safety_tip'], SAFETY_TIP)
        self.assertEqual(Message.objects.count(), 3)

    def test_what_counts_as_contact_or_payment_details(self):
        for text in ('0712345678', '+254 712 345 678', 'me@example.com', 'pay via mpesa 5555', 'Paybill 400200'):
            with self.subTest(text=text):
                self.assertTrue(mentions_contact_or_payment(text))
        for text in ('See you at 10', 'The logo has 3 colours', 'mpesa later', 'Budget is KES 5000'):
            with self.subTest(text=text):
                self.assertFalse(mentions_contact_or_payment(text))


class ReportTests(ChatApiTestCase):
    def test_a_participant_can_report_with_a_reason(self):
        self.client.force_authenticate(self.freelancer)
        self.assertEqual(self.client.post(self.url + 'report/', {'reason': ''}).status_code, 400)
        self.assertEqual(self.client.post(self.url + 'report/', {'reason': 'Asked me to pay a fee.'}).status_code, 201)
        report = ChatReport.objects.get()
        self.assertEqual((report.reporter, report.reason), (self.freelancer, 'Asked me to pay a fee.'))
