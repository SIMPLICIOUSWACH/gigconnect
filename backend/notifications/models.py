import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    A message to one user, shown in the app. Sprint 7 adds the list endpoint and the bell; for now the admin
    actions write these, so nothing an admin does to someone's account goes unexplained.
    """

    class Kind(models.TextChoices):
        ACCOUNT_SUSPENDED = 'account_suspended', 'Account suspended'
        ACCOUNT_REINSTATED = 'account_reinstated', 'Account reinstated'
        GIG_REMOVED = 'gig_removed', 'Gig removed'
        GIG_RESTORED = 'gig_restored', 'Gig restored'
        APPLICATION_REMOVED = 'application_removed', 'Application removed'
        APPLICATION_RESTORED = 'application_restored', 'Application restored'
        VERIFICATION_APPROVED = 'verification_approved', 'ID verification approved'
        VERIFICATION_REJECTED = 'verification_rejected', 'ID verification rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=40, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.TextField()
    # A path in the frontend, such as /gigs/mine. Blank when there is nothing to open.
    link = models.CharField(max_length=300, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['recipient', 'read_at'], name='notification_unread_idx')]

    def __str__(self):
        return f'{self.kind} -> {self.recipient_id}'
