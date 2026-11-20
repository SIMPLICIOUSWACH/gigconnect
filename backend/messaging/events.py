"""What happens around a chat message apart from storing it: the in-app notice for the other person."""

from django.utils import timezone

from notifications.models import Notification
from notifications.service import clean_title, wants
from usersettings.models import NotificationPreference

from .serializers import display_name

PREVIEW = 140


def conversation_link(conversation):
    return f'/messages/{conversation.pk}'


def message_sent(conversation, message):
    """
    Tell the other person in the app. One notice per chat while it is unread: a new message updates it ("3 new
    messages from ...") and moves it to the top, so a busy chat doesn't fill the bell. Email is separate and slower:
    see emails.py. Called inside the sending transaction.
    """
    recipient = conversation.client if message.sender_id == conversation.freelancer_id else conversation.freelancer
    prefs = NotificationPreference.objects.filter(user=recipient).first()
    if not wants(prefs, 'new_message_inapp'):
        return
    name = display_name(message.sender)
    unread = conversation.messages.filter(read_at__isnull=True, sender=message.sender).count()
    title = clean_title(f'New message from {name}' if unread == 1 else f'{unread} new messages from {name}')
    body = message.body if len(message.body) <= PREVIEW else message.body[:PREVIEW - 1] + '…'
    link = conversation_link(conversation)
    existing = Notification.objects.filter(
        recipient=recipient, kind=Notification.Kind.NEW_MESSAGE, link=link, read_at__isnull=True,
    )
    if not existing.update(title=title, body=body, created_at=timezone.now()):
        Notification.objects.create(
            recipient=recipient, kind=Notification.Kind.NEW_MESSAGE, title=title, body=body, link=link,
        )


def conversation_read(conversation, reader):
    """Reading the chat also clears its notice from the bell."""
    Notification.objects.filter(
        recipient=reader, kind=Notification.Kind.NEW_MESSAGE, link=conversation_link(conversation),
        read_at__isnull=True,
    ).update(read_at=timezone.now())
