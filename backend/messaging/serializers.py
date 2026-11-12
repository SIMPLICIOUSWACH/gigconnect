from rest_framework import serializers

from .models import MESSAGE_MAX_LENGTH, Message
from .rules import read_only_reason

PREVIEW_LENGTH = 100
DELETED_NAME = 'Deleted user'


def display_name(user):
    return DELETED_NAME if user.deleted_at is not None else user.full_name


class ConversationSerializer(serializers.Serializer):
    """One conversation as one of its two participants sees it. Needs `request` in the context."""

    def to_representation(self, conversation):
        me = self.context['request'].user
        i_am_client = me.pk == conversation.client_id
        other = conversation.freelancer if i_am_client else conversation.client
        reason = read_only_reason(conversation)
        waiting = conversation.first_message_at is None
        last = getattr(conversation, 'last_body', None)
        return {
            'id': str(conversation.pk),
            'gig': {'id': str(conversation.gig_id), 'title': conversation.gig.title},
            'application_id': str(conversation.application_id),
            'other': {'id': str(other.pk), 'full_name': display_name(other), 'role': other.role},
            'my_role': 'client' if i_am_client else 'freelancer',
            'hired_at': conversation.created_at,
            'first_message_at': conversation.first_message_at,
            'last_message_at': conversation.last_message_at,
            'last_message': None if last is None else {
                'body': last[:PREVIEW_LENGTH],
                'from_me': conversation.last_sender_id == me.pk,
                'created_at': conversation.last_message_at,
            },
            'unread_count': getattr(conversation, 'unread_count', 0),
            'read_only_reason': reason,
            # The freelancer waits for the client's first message.
            'waiting_for_client': waiting and not i_am_client,
            'can_send': reason is None and (i_am_client or not waiting),
        }


class MessageSerializer(serializers.ModelSerializer):
    from_me = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'body', 'from_me', 'created_at', 'read_at']

    def get_from_me(self, obj):
        return obj.sender_id == self.context['request'].user.pk


class NewMessageSerializer(serializers.Serializer):
    body = serializers.CharField(
        max_length=MESSAGE_MAX_LENGTH, trim_whitespace=True,
        error_messages={
            'blank': 'Write a message first.',
            'max_length': f'Keep messages to {MESSAGE_MAX_LENGTH:,} characters.',
        },
    )


class ReportSerializer(serializers.Serializer):
    reason = serializers.CharField(
        max_length=1000, trim_whitespace=True, error_messages={'blank': 'Say what is wrong, so an admin can help.'},
    )
