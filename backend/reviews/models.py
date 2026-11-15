import uuid

from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import Q

from gigs.models import ModerationStatus

REVIEW_MAX_LENGTH = 1000
REPLY_MAX_LENGTH = 500


class Review(models.Model):
    """
    A client's rating of the freelancer they hired, written after the gig was completed. One per gig. The freelancer
    can answer once. An admin can remove it, which takes it out of the freelancer's average until it is restored.
    """

    Moderation = ModerationStatus

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # One review per gig: a gig has one hire, and the client rates that work once.
    gig = models.OneToOneField('gigs.Gig', on_delete=models.CASCADE, related_name='review')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_written')
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_received'
    )
    rating = models.PositiveSmallIntegerField()
    text = models.TextField(blank=True, validators=[MaxLengthValidator(REVIEW_MAX_LENGTH)])
    freelancer_reply = models.TextField(blank=True, validators=[MaxLengthValidator(REPLY_MAX_LENGTH)])
    reply_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    moderation_status = models.CharField(
        max_length=10, choices=ModerationStatus.choices, default=ModerationStatus.VISIBLE
    )
    removed_reason = models.TextField(blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=Q(rating__gte=1) & Q(rating__lte=5), name='review_rating_1_to_5'),
        ]
        indexes = [
            models.Index(fields=['freelancer', 'moderation_status', '-created_at'], name='review_freelancer_idx'),
        ]

    def __str__(self):
        return f'Review<{self.gig_id}: {self.rating}>'

    @property
    def is_removed(self):
        return self.moderation_status == ModerationStatus.REMOVED
