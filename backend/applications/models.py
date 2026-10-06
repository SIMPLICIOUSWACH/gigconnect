import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxLengthValidator, MinLengthValidator, MinValueValidator
from django.db import models, transaction

from .transitions import InvalidTransition, Status, can_transition

COVER_LETTER_MIN_LENGTH = 50
COVER_LETTER_MAX_LENGTH = 3000


class Application(models.Model):
    Status = Status

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gig = models.ForeignKey('gigs.Gig', on_delete=models.CASCADE, related_name='applications')
    # A User, the same way Gig refers to its client.
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='applications'
    )
    cover_letter = models.TextField(
        validators=[
            MinLengthValidator(COVER_LETTER_MIN_LENGTH),
            MaxLengthValidator(COVER_LETTER_MAX_LENGTH),
        ]
    )
    portfolio_link = models.URLField(blank=True)
    # In KES, like every budget in GigConnect. Optional.
    proposed_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_synthetic = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # One application per freelancer per gig.
            models.UniqueConstraint(fields=['gig', 'freelancer'], name='unique_application_per_gig'),
            # A gig has at most one hire.
            models.UniqueConstraint(
                fields=['gig'], condition=models.Q(status='hired'), name='one_hired_application_per_gig'
            ),
        ]
        indexes = [
            models.Index(fields=['freelancer', 'status'], name='app_freelancer_status_idx'),
            models.Index(fields=['gig', 'status'], name='app_gig_status_idx'),
        ]

    def __str__(self):
        return f'{self.freelancer_id} -> {self.gig_id} ({self.status})'

    def change_status(self, new_status, actor, changed_by, note=''):
        """Move to `new_status` as `actor` ('client' or 'freelancer') and record the change.

        Raises InvalidTransition, changing nothing, if the rules in transitions.py don't allow it.
        The row is locked first, so two people acting on it at once can't both succeed from the
        same starting status.
        """
        with transaction.atomic():
            current = Application.objects.select_for_update().get(pk=self.pk).status
            if not can_transition(current, new_status, actor):
                raise InvalidTransition(f'Cannot change an application from "{current}" to "{new_status}".')
            self.status = new_status
            self.save(update_fields=['status', 'updated_at'])
            return ApplicationStatusEvent.objects.create(
                application=self, from_status=current, to_status=new_status,
                changed_by=changed_by, note=note,
            )


class ApplicationStatusEvent(models.Model):
    """One row per status change, so an application's history can be audited."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='events')
    # Blank for the first event, when the application is created.
    from_status = models.CharField(max_length=20, choices=Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Status.choices)
    # Null for changes the system makes itself (for example when an account is deleted).
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.application_id}: {self.from_status or "new"} -> {self.to_status}'
