import uuid

from django.conf import settings
from django.db import models

MESSAGE_MAX_LENGTH = 2000


class Conversation(models.Model):
    """
    The chat between a client and the freelancer they hired, one per hired application. Only the two of them can read
    it, and the client writes first. Admins only ever see one that a participant reported (see ChatReport).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        'applications.Application', on_delete=models.CASCADE, related_name='conversation'
    )
    gig = models.ForeignKey('gigs.Gig', on_delete=models.CASCADE, related_name='conversations')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='client_conversations')
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='freelancer_conversations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    first_message_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    # The "keep payments on GigConnect" tip, shown once to each side.
    client_tip_shown = models.BooleanField(default=False)
    freelancer_tip_shown = models.BooleanField(default=False)
    # When each side was last emailed about unread messages, so they get at most one email an hour.
    client_emailed_at = models.DateTimeField(null=True, blank=True)
    freelancer_emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['client', '-last_message_at'], name='conversation_client_idx'),
            models.Index(fields=['freelancer', '-last_message_at'], name='conversation_freelancer_idx'),
        ]

    def __str__(self):
        return f'Conversation<{self.gig_id}: {self.client_id} and {self.freelancer_id}>'

    def is_participant(self, user):
        return user.pk in (self.client_id, self.freelancer_id)

    def other_party(self, user):
        return self.freelancer if user.pk == self.client_id else self.client


class Message(models.Model):
    """
    One plain-text message. No attachments. The id is a plain increasing number, so it gives the true order even
    when two messages share a timestamp, and polling can ask for everything after an id. Access is still checked per
    conversation, so a guessable id reveals nothing.
    """

    id = models.BigAutoField(primary_key=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # When the other person read it. Null until then.
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']
        indexes = [models.Index(fields=['conversation', 'id'], name='message_conversation_idx')]

    def __str__(self):
        return f'Message<{self.conversation_id} from {self.sender_id}>'


class ChatReport(models.Model):
    """A participant's report about a chat. It is the only way an admin can see a chat, and every view is logged."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_reports')
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'ChatReport<{self.conversation_id}>'
