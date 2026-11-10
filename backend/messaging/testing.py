"""Helpers for the chat tests."""

from accounts.models import User
from adminpanel.testing import AdminTestMixin
from applications.models import Application

from .models import Conversation, Message


class ChatTestMixin(AdminTestMixin):
    def make_hire(self, client_email='client@example.com', freelancer_email='freelancer@example.com', title='Logo'):
        """A gig with a hired application and its conversation, as if the client had hired through the app."""
        client = User.objects.filter(email=client_email).first() or self.make_user(
            client_email, User.Role.CLIENT, full_name='Wanjiru Bakers',
        )
        freelancer = User.objects.filter(email=freelancer_email).first() or self.make_user(
            freelancer_email, User.Role.FREELANCER, full_name='Otieno Designs',
        )
        gig = self.make_gig(client, title=title, status='in_progress')
        application = self.apply(gig, freelancer, status=Application.Status.HIRED)
        conversation = Conversation.objects.create(
            application=application, gig=gig, client=client, freelancer=freelancer,
        )
        return conversation

    def say(self, conversation, sender, body='Hello there'):
        """Write a message straight into the database, keeping the conversation's times in step."""
        message = Message.objects.create(conversation=conversation, sender=sender, body=body)
        Conversation.objects.filter(pk=conversation.pk, first_message_at__isnull=True).update(
            first_message_at=message.created_at,
        )
        Conversation.objects.filter(pk=conversation.pk).update(last_message_at=message.created_at)
        conversation.refresh_from_db()
        return message
