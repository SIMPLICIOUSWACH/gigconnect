import importlib
from datetime import timedelta

from django.apps import apps
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from applications.models import Application, ApplicationStatusEvent
from gigs.models import Gig
from notifications.models import Notification

from . import rules
from .models import Conversation
from .testing import ChatTestMixin


class OpenedOnHireTests(ChatTestMixin, APITestCase):
    def setUp(self):
        self.client_user = self.make_user('client@example.com', User.Role.CLIENT, full_name='Wanjiru Bakers')
        self.freelancer = self.make_user('freelancer@example.com', User.Role.FREELANCER, full_name='Otieno Designs')
        self.gig = self.make_gig(self.client_user)
        self.application = self.apply(self.gig, self.freelancer)
        self.client.force_authenticate(self.client_user)

    def move_to(self, status, application=None):
        application = application or self.application
        return self.client.patch(f'/api/applications/{application.pk}/status/', {'status': status})

    def test_hiring_opens_one_conversation_and_tells_the_client(self):
        for status in ('under_review', 'shortlisted'):
            self.assertEqual(self.move_to(status).status_code, 200)
            self.assertFalse(Conversation.objects.exists())
        self.assertEqual(self.move_to('hired').status_code, 200)

        conversation = Conversation.objects.get()
        self.assertEqual(
            (conversation.application, conversation.gig, conversation.client, conversation.freelancer),
            (self.application, self.gig, self.client_user, self.freelancer),
        )
        self.assertIsNone(conversation.first_message_at)
        note = Notification.objects.get(recipient=self.client_user, kind='chat_opened')
        expected = 'You hired Otieno Designs for "Logo for a bakery". Send them a message to get started.'
        self.assertEqual(note.body, expected)
        self.assertEqual(note.link, f'/messages/{conversation.pk}')
        self.assertFalse(Notification.objects.filter(recipient=self.freelancer, kind='chat_opened').exists())

    def test_a_refused_hire_opens_nothing(self):
        other = self.apply(self.gig, self.make_user('second@example.com', User.Role.FREELANCER))
        for application in (self.application, other):
            self.move_to('under_review', application)
            self.move_to('shortlisted', application)
        self.move_to('hired')
        self.assertEqual(self.move_to('hired', other).status_code, 400)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_rejecting_opens_nothing(self):
        self.move_to('rejected')
        self.assertFalse(Conversation.objects.exists())


class StatusChangedAtTests(ChatTestMixin, APITestCase):
    def test_set_when_the_status_changes_and_not_otherwise(self):
        client = self.make_user('client@example.com', User.Role.CLIENT)
        gig = self.make_gig(client)
        created = gig.status_changed_at
        self.assertIsNotNone(created)
        gig = Gig.objects.get(pk=gig.pk)
        gig.title = 'A new title'
        gig.save()
        self.assertEqual(Gig.objects.get(pk=gig.pk).status_changed_at, created)
        # Put the old time well in the past, so "later" doesn't depend on two clock readings a millisecond apart.
        earlier = created - timedelta(hours=1)
        Gig.objects.filter(pk=gig.pk).update(status_changed_at=earlier)
        self.client.force_authenticate(client)
        self.client.patch(f'/api/gigs/{gig.pk}/status/', {'status': 'closed'})
        self.assertGreater(Gig.objects.get(pk=gig.pk).status_changed_at, created - timedelta(minutes=1))

    def test_completed_and_closed_gigs_are_backfilled_from_updated_at(self):
        client = self.make_user('client@example.com', User.Role.CLIENT)
        closed = self.make_gig(client, title='Closed', status='closed')
        still_open = self.make_gig(client, title='Open')
        Gig.objects.update(status_changed_at=None)
        importlib.import_module('gigs.migrations.0015_backfill_status_changed_at').backfill(apps, None)
        closed.refresh_from_db()
        still_open.refresh_from_db()
        self.assertEqual(closed.status_changed_at, closed.updated_at)
        self.assertIsNone(still_open.status_changed_at)


class ReadOnlyRuleTests(ChatTestMixin, APITestCase):
    def setUp(self):
        self.conversation = self.make_hire()

    def reload(self):
        return Conversation.objects.select_related('gig', 'application', 'client', 'freelancer').get(
            pk=self.conversation.pk,
        )

    def test_an_active_chat_is_writable(self):
        self.assertIsNone(rules.read_only_reason(self.reload()))
        self.assertIsNone(rules.read_only_since(self.reload()))

    def test_a_finished_gig_closes_the_chat_after_30_days(self):
        now = timezone.now()
        gigs = Gig.objects.filter(pk=self.conversation.gig_id)
        gigs.update(status='completed', status_changed_at=now - timedelta(days=29))
        self.assertIsNone(rules.read_only_reason(self.reload()))
        Gig.objects.filter(pk=self.conversation.gig_id).update(status_changed_at=now - timedelta(days=31))
        self.assertIn('completed more than 30 days ago', rules.read_only_reason(self.reload()))
        self.assertEqual(rules.read_only_since(self.reload()).date(), (now - timedelta(days=1)).date())

    def test_removal_suspension_and_deletion_each_close_it(self):
        now = timezone.now()
        cases = [
            (Gig, self.conversation.gig_id, {'moderation_status': 'removed', 'removed_at': now}, 'removed this gig'),
            (Application, self.conversation.application_id, {'moderation_status': 'removed', 'removed_at': now},
             'removed this application'),
            (User, self.conversation.client_id, {'account_status': 'suspended', 'suspended_at': now}, 'suspended'),
            (User, self.conversation.freelancer_id, {'deleted_at': now}, 'account was deleted'),
        ]
        for model, pk, change, words in cases:
            with self.subTest(words=words):
                before = {field: getattr(model.objects.get(pk=pk), field) for field in change}
                model.objects.filter(pk=pk).update(**change)
                self.assertIn(words, rules.read_only_reason(self.reload()))
                model.objects.filter(pk=pk).update(**before)
                self.assertIsNone(rules.read_only_reason(self.reload()))


class ExistingHiresMigrationTests(ChatTestMixin, APITestCase):
    def test_existing_hires_get_a_quiet_conversation_and_it_can_be_undone(self):
        client = self.make_user('client@example.com', User.Role.CLIENT)
        freelancer = self.make_user('freelancer@example.com', User.Role.FREELANCER)
        hired = self.apply(self.make_gig(client, title='Hired'), freelancer, status='hired')
        self.apply(self.make_gig(client, title='Pending'), freelancer)
        module = importlib.import_module('messaging.migrations.0002_conversations_for_existing_hires')

        module.open_for_existing_hires(apps, None)
        module.open_for_existing_hires(apps, None)  # running it again changes nothing
        self.assertEqual(list(Conversation.objects.values_list('application_id', flat=True)), [hired.pk])
        self.assertFalse(Notification.objects.exists())

        module.remove_unused(apps, None)
        self.assertFalse(Conversation.objects.exists())

    def test_existing_hires_are_dated_from_the_hire(self):
        client = self.make_user('client@example.com', User.Role.CLIENT)
        freelancer = self.make_user('freelancer@example.com', User.Role.FREELANCER)
        with_event = self.apply(self.make_gig(client, title='Hired'), freelancer, status='hired')
        hired_on = timezone.now() - timedelta(days=40)
        event = ApplicationStatusEvent.objects.create(
            application=with_event, from_status='shortlisted', to_status='hired',
        )
        ApplicationStatusEvent.objects.filter(pk=event.pk).update(created_at=hired_on)
        without_event = self.apply(self.make_gig(client, title='Old'), freelancer, status='hired')
        updated_on = timezone.now() - timedelta(days=90)
        Application.objects.filter(pk=without_event.pk).update(updated_at=updated_on)

        importlib.import_module('messaging.migrations.0002_conversations_for_existing_hires').open_for_existing_hires(
            apps, None,
        )
        self.assertEqual(Conversation.objects.get(application=with_event).created_at, hired_on)
        self.assertEqual(Conversation.objects.get(application=without_event).created_at, updated_on)

    def test_going_back_keeps_conversations_people_wrote_in(self):
        conversation = self.make_hire()
        self.say(conversation, conversation.client)
        importlib.import_module('messaging.migrations.0002_conversations_for_existing_hires').remove_unused(apps, None)
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())
