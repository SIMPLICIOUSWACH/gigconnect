"""
Emails about unread chat messages. A message that is still unread 15 minutes after it was sent is emailed to the
other person, if their "New messages" email setting is on, and nobody gets more than one email per chat an hour.
send_message_emails runs this every 5 minutes. The email says who wrote and links to the chat; it doesn't include the
message itself.
"""

from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from notifications.service import wants
from usersettings.models import NotificationPreference

from .models import Conversation, Message
from .serializers import display_name

UNREAD_FOR = timedelta(minutes=15)
AT_MOST_EVERY = timedelta(hours=1)
SIDES = (('client', 'freelancer'), ('freelancer', 'client'))


def _due(conversation, recipient_side, now):
    """The messages this side should be emailed about now: unread, 15 minutes old, and newer than their last email."""
    recipient = getattr(conversation, recipient_side)
    emailed_at = getattr(conversation, f'{recipient_side}_emailed_at')
    if recipient.deleted_at is not None or recipient.is_suspended or not recipient.is_active:
        return Message.objects.none()
    if emailed_at and emailed_at > now - AT_MOST_EVERY:
        return Message.objects.none()
    due = conversation.messages.filter(read_at__isnull=True, created_at__lte=now - UNREAD_FOR).exclude(
        sender=recipient,
    )
    return due.filter(created_at__gt=emailed_at) if emailed_at else due


def _send(recipient, sender_name, count, gig_title, conversation_id):
    words = 'a message' if count == 1 else f'{count} messages'
    send_mail(
        subject=f'GigConnect: New message from {sender_name}',
        message=(
            f'Hi {recipient.full_name},\n\n{sender_name} sent you {words} about "{gig_title}" that you haven\'t read '
            f'yet.\n\nRead and reply: {settings.FRONTEND_URL}/messages/{conversation_id}\n\n'
            'You can turn these emails off in your notification settings.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient.email],
    )


def send_due_emails(now=None, dry_run=False):
    """Send every email that is due. Returns how many were (or, in a dry run, would be) sent."""
    now = now or timezone.now()
    candidates = (
        Conversation.objects.filter(messages__read_at__isnull=True, messages__created_at__lte=now - UNREAD_FOR)
        .select_related('client', 'freelancer', 'gig').distinct()
    )
    sent = 0
    for conversation in candidates:
        for recipient_side, sender_side in SIDES:
            if not _due(conversation, recipient_side, now).exists():
                continue
            recipient = getattr(conversation, recipient_side)
            if not wants(NotificationPreference.objects.filter(user=recipient).first(), 'new_message_email'):
                continue
            if dry_run:
                sent += 1
                continue
            with transaction.atomic():
                # Lock and check again, so two runs at once can't both email the same person.
                locked = Conversation.objects.select_for_update().select_related(
                    'client', 'freelancer', 'gig',
                ).get(pk=conversation.pk)
                due = _due(locked, recipient_side, now)
                count = due.count()
                if not count:
                    continue
                setattr(locked, f'{recipient_side}_emailed_at', now)
                locked.save(update_fields=[f'{recipient_side}_emailed_at'])
                args = (getattr(locked, recipient_side), display_name(getattr(locked, sender_side)), count,
                        locked.gig.title, locked.pk)
                transaction.on_commit(lambda args=args: _send(*args), robust=True)
                sent += 1
    return sent
