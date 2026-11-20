from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from notifications.models import Notification
from usersettings.models import NotificationPreference

from .emails import send_due_emails
from .models import Message
from .testing import ChatTestMixin


class InAppTests(ChatTestMixin, APITestCase):
    def setUp(self):
        self.conversation = self.make_hire()
        self.client.force_authenticate(self.conversation.client)
        self.url = f'/api/conversations/{self.conversation.pk}/'

    def send(self, body):
        return self.client.post(self.url + 'messages/', {'body': body})

    def notices(self):
        return Notification.objects.filter(recipient=self.conversation.freelancer, kind='new_message')

    def test_one_notice_per_chat_that_counts_up(self):
        self.send('First')
        first = self.notices().get()
        self.assertEqual((first.title, first.body), ('New message from Wanjiru Bakers', 'First'))
        self.send('Second')
        self.send('Third')
        note = self.notices().get()
        self.assertEqual((note.title, note.body), ('3 new messages from Wanjiru Bakers', 'Third'))
        self.assertEqual(note.link, f'/messages/{self.conversation.pk}')

    def test_reading_the_chat_clears_the_notice_and_the_next_message_makes_a_new_one(self):
        self.send('First')
        self.client.force_authenticate(self.conversation.freelancer)
        self.client.post(self.url + 'read/')
        self.assertIsNotNone(self.notices().get().read_at)
        self.client.force_authenticate(self.conversation.client)
        self.send('Back again')
        self.assertEqual(self.notices().filter(read_at__isnull=True).get().title, 'New message from Wanjiru Bakers')

    def test_the_in_app_setting_is_respected(self):
        NotificationPreference.objects.filter(user=self.conversation.freelancer).update(new_message_inapp=False)
        self.send('First')
        self.assertFalse(self.notices().exists())


class EmailTests(ChatTestMixin, APITestCase):
    def setUp(self):
        self.conversation = self.make_hire()
        self.now = timezone.now()

    def message(self, minutes_ago, sender=None, read=False):
        message = self.say(self.conversation, sender or self.conversation.client)
        Message.objects.filter(pk=message.pk).update(
            created_at=self.now - timedelta(minutes=minutes_ago), read_at=self.now if read else None,
        )
        return message

    def run_at(self, minutes_later=0, dry_run=False):
        with self.captureOnCommitCallbacks(execute=True):
            return send_due_emails(now=self.now + timedelta(minutes=minutes_later), dry_run=dry_run)

    def test_an_email_after_15_minutes_unread_and_not_before(self):
        self.message(minutes_ago=10)
        self.assertEqual(self.run_at(), 0)
        self.assertEqual(self.run_at(minutes_later=6), 1)
        self.assertEqual(mail.outbox[0].to, [self.conversation.freelancer.email])
        self.assertIn('Wanjiru Bakers sent you a message about "Logo"', mail.outbox[0].body)
        self.assertIn(f'/messages/{self.conversation.pk}', mail.outbox[0].body)

    def test_nothing_once_read(self):
        self.message(minutes_ago=30, read=True)
        self.assertEqual(self.run_at(), 0)

    def test_the_email_setting_is_respected(self):
        NotificationPreference.objects.filter(user=self.conversation.freelancer).update(new_message_email=False)
        self.message(minutes_ago=30)
        self.assertEqual(self.run_at(), 0)
        self.assertEqual(mail.outbox, [])

    def test_running_twice_never_sends_twice(self):
        self.message(minutes_ago=30)
        self.assertEqual(self.run_at(), 1)
        self.assertEqual(self.run_at(), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_at_most_one_email_per_chat_an_hour(self):
        self.message(minutes_ago=30)
        self.run_at()
        self.message(minutes_ago=-10)  # a new message 10 minutes after the email
        self.assertEqual(self.run_at(minutes_later=40), 0)  # 40 minutes after the email: too soon
        self.assertEqual(self.run_at(minutes_later=61), 1)
        self.assertIn('sent you a message', mail.outbox[1].body)

    def test_each_side_is_counted_separately(self):
        self.message(minutes_ago=30)
        self.message(minutes_ago=20, sender=self.conversation.freelancer)
        self.assertEqual(self.run_at(), 2)
        self.assertEqual({email.to[0] for email in mail.outbox},
                         {self.conversation.client.email, self.conversation.freelancer.email})

    def test_the_command_has_a_dry_run(self):
        self.message(minutes_ago=30)
        output = StringIO()
        call_command('send_message_emails', '--dry-run', stdout=output)
        self.assertIn('1 email(s) are due', output.getvalue())
        self.assertEqual(mail.outbox, [])
        self.conversation.refresh_from_db()
        self.assertIsNone(self.conversation.freelancer_emailed_at)
