from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from adminpanel.models import AdminAction
from adminpanel.testing import PASSWORD
from gigs.models import Gig

from .models import ChatReport, Conversation, Message
from .retention import due_for_deletion
from .testing import ChatTestMixin


class ReportedChatTests(ChatTestMixin, APITestCase):
    def setUp(self):
        self.admin = self.make_admin()
        self.conversation = self.make_hire()
        self.say(self.conversation, self.conversation.client, 'Hi, thanks for applying.')
        self.say(self.conversation, self.conversation.freelancer, 'Pay me outside the app please.')
        self.report = ChatReport.objects.create(
            conversation=self.conversation, reporter=self.conversation.client, reason='Asked to pay outside.',
        )
        self.url = f'/api/admin/chat-reports/{self.report.pk}/'
        self.client.force_authenticate(self.admin)

    def viewed(self):
        return AdminAction.objects.filter(action='chat_viewed', target_id=self.conversation.pk)

    def test_only_admins(self):
        for user in (self.conversation.client, self.conversation.freelancer):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get('/api/admin/chat-reports/').status_code, 403)
            self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertFalse(self.viewed().exists())

    def test_the_list_shows_reports_without_messages(self):
        response = self.client.get('/api/admin/chat-reports/')
        self.assertEqual(response.status_code, 200)
        row = response.data['results'][0]
        self.assertEqual(row['reason'], 'Asked to pay outside.')
        self.assertEqual(row['reporter']['full_name'], 'Wanjiru Bakers')
        self.assertNotIn('messages', row)
        self.assertFalse(self.viewed().exists())  # listing reports doesn't open any chat

    def test_every_view_of_a_reported_chat_is_logged(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([m['body'] for m in response.data['messages']],
                         ['Hi, thanks for applying.', 'Pay me outside the app please.'])
        self.assertEqual(response.data['messages'][1]['sender']['full_name'], 'Otieno Designs')
        self.client.get(self.url)
        self.assertEqual(self.viewed().count(), 2)
        self.assertEqual(self.viewed().first().admin, self.admin)

    def test_the_audit_log_names_the_chat(self):
        self.client.get(self.url)
        rows = self.client.get('/api/admin/audit-log/').data['results']
        self.assertEqual(rows[0]['action_label'], 'Viewed reported chat')
        self.assertEqual(rows[0]['target_label'], 'Chat between Wanjiru Bakers and Otieno Designs on "Logo"')

    def test_resolving_is_logged_and_moves_the_report(self):
        response = self.client.post(self.url + 'resolve/', {'note': 'Warned the freelancer.'})
        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual((self.report.resolved_by, self.report.resolution_note), (self.admin, 'Warned the freelancer.'))
        action = AdminAction.objects.get(action='chat_report_resolved')
        self.assertEqual((action.target_id, action.reason), (self.conversation.pk, 'Warned the freelancer.'))
        self.assertEqual(self.client.get('/api/admin/chat-reports/').data['results'], [])
        resolved = self.client.get('/api/admin/chat-reports/?status=resolved').data['results']
        self.assertEqual(len(resolved), 1)
        self.assertEqual(self.client.post(self.url + 'resolve/', {}).status_code, 400)

    def test_one_chats_reports(self):
        other = self.make_hire(client_email='c2@example.com', freelancer_email='f2@example.com', title='Other')
        ChatReport.objects.create(conversation=other, reporter=other.client, reason='Rude.')
        rows = self.client.get('/api/admin/chat-reports/', {'conversation': self.conversation.pk}).data['results']
        self.assertEqual([row['reason'] for row in rows], ['Asked to pay outside.'])
        self.assertEqual(rows[0]['freelancer']['account_status'], 'active')

    def test_admins_still_cannot_open_chats_through_the_chat_api(self):
        self.assertEqual(self.client.get(f'/api/conversations/{self.conversation.pk}/messages/').status_code, 404)


class RetentionTests(ChatTestMixin, APITestCase):
    def setUp(self):
        self.conversation = self.make_hire()
        self.say(self.conversation, self.conversation.client)

    def finish_gig(self, days_ago):
        Gig.objects.filter(pk=self.conversation.gig_id).update(
            status='completed', status_changed_at=timezone.now() - timedelta(days=days_ago),
        )

    def purge(self, *args):
        output = StringIO()
        call_command('purge_old_conversations', *args, stdout=output)
        return output.getvalue()

    def test_deleted_12_months_after_it_became_read_only(self):
        # Completed 396 days ago: read-only for 366 days (30 days of grace first).
        self.finish_gig(days_ago=396)
        self.assertIn('Deleted 1 conversation(s).', self.purge())
        self.assertFalse(Conversation.objects.exists())
        self.assertFalse(Message.objects.exists())

    def test_kept_until_then(self):
        self.finish_gig(days_ago=390)  # read-only for 360 days
        self.assertIn('Deleted 0', self.purge())
        self.assertTrue(Conversation.objects.exists())

    def test_a_chat_that_is_still_open_is_kept(self):
        self.assertEqual(due_for_deletion(now=timezone.now() + timedelta(days=800)), [])

    def test_a_suspension_starts_the_clock(self):
        User.objects.filter(pk=self.conversation.freelancer_id).update(
            account_status='suspended', suspended_at=timezone.now() - timedelta(days=366),
        )
        self.assertEqual(len(due_for_deletion()), 1)

    def test_dry_run_deletes_nothing(self):
        self.finish_gig(days_ago=500)
        self.assertIn('1 conversation(s) would be deleted', self.purge('--dry-run'))
        self.assertTrue(Conversation.objects.exists())


class DeletedAccountTests(ChatTestMixin, APITestCase):
    def setUp(self):
        self.conversation = self.make_hire()
        self.say(self.conversation, self.conversation.client, 'Welcome aboard.')
        self.say(self.conversation, self.conversation.freelancer, 'Thanks, starting today.')
        self.freelancer = self.conversation.freelancer

    def test_the_export_has_the_messages_i_sent(self):
        self.client.force_authenticate(self.freelancer)
        sent = self.client.get('/api/settings/export-data/').data['messages_sent']
        self.assertEqual(len(sent), 1)
        self.assertEqual((sent[0]['body'], sent[0]['to'], sent[0]['gig_title']),
                         ('Thanks, starting today.', 'Wanjiru Bakers', 'Logo'))

    def test_the_other_person_keeps_the_chat_read_only_with_a_deleted_user(self):
        self.client.force_authenticate(self.freelancer)
        response = self.client.post('/api/settings/delete-account/', {'password': PASSWORD})
        self.assertEqual(response.status_code, 200)

        self.client.force_authenticate(self.conversation.client)
        url = f'/api/conversations/{self.conversation.pk}/'
        detail = self.client.get(url).data
        self.assertEqual(detail['other']['full_name'], 'Deleted user')
        self.assertEqual(detail['read_only_reason'], 'This account was deleted, so this chat is read-only.')
        self.assertFalse(detail['can_send'])
        bodies = [m['body'] for m in self.client.get(url + 'messages/').data['results']]
        self.assertEqual(bodies, ['Welcome aboard.', 'Thanks, starting today.'])
        reply = self.client.post(url + 'messages/', {'body': 'Hello?'})
        self.assertEqual((reply.status_code, reply.data['code']), (403, 'read_only'))
