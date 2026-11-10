"""
Chats in the data export, and what happens to them when an account is deleted.

A chat belongs to two people, so deleting one account doesn't delete it: the other person keeps the messages, the
deleted person shows as "Deleted user" (serializers.display_name) and the chat becomes read-only (rules.py). The whole
conversation is then deleted 12 months later (retention.py). Before deleting their account a user can download their
data export, which includes every message they sent.
"""

from .models import Message
from .serializers import display_name


def export_messages(user):
    """Every message the user sent, oldest first, with which chat it was in."""
    messages = (
        Message.objects.filter(sender=user)
        .select_related('conversation__gig', 'conversation__client', 'conversation__freelancer')
        .order_by('id')
    )
    return [
        {
            'conversation_id': str(message.conversation_id),
            'gig_title': message.conversation.gig.title,
            'to': display_name(message.conversation.other_party(user)),
            'body': message.body,
            'created_at': message.created_at,
            'read_at': message.read_at,
        }
        for message in messages
    ]
