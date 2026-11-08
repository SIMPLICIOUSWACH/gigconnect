import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

# The actions that take something away from someone (AdminAction.Action values). Each needs a reason.
NEGATIVE_ACTIONS = ('verify_reject', 'suspend_user', 'remove_gig', 'remove_application')


class AdminAction(models.Model):
    """
    The audit log: one row for every change an admin makes, written in the same transaction as the change.
    Rows are never edited or deleted.
    """

    class Action(models.TextChoices):
        VERIFY_APPROVE = 'verify_approve', 'Approved ID verification'
        VERIFY_REJECT = 'verify_reject', 'Rejected ID verification'
        SUSPEND_USER = 'suspend_user', 'Suspended user'
        REINSTATE_USER = 'reinstate_user', 'Reinstated user'
        REMOVE_GIG = 'remove_gig', 'Removed gig'
        RESTORE_GIG = 'restore_gig', 'Restored gig'
        REMOVE_APPLICATION = 'remove_application', 'Removed application'
        RESTORE_APPLICATION = 'restore_application', 'Restored application'

    class TargetType(models.TextChoices):
        # ID verification decisions target the freelancer's user account.
        USER = 'user', 'User'
        GIG = 'gig', 'Gig'
        APPLICATION = 'application', 'Application'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Kept if the admin's account is ever deleted, so the log still shows what happened.
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='admin_actions'
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.UUIDField()
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_type', 'target_id'], name='admin_action_target_idx'),
            models.Index(fields=['action', '-created_at'], name='admin_action_action_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(action__in=NEGATIVE_ACTIONS) | ~Q(reason=''),
                name='admin_action_negative_needs_reason',
            ),
        ]

    NEGATIVE_ACTIONS = NEGATIVE_ACTIONS

    def __str__(self):
        return f'{self.action} {self.target_type}:{self.target_id}'
