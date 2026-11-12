"""
How long chats are kept: a whole conversation is deleted 12 months after it became read-only (see rules.py for when
that happens). A chat that becomes writable again, for example after a suspension is lifted, starts the clock over.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import Conversation
from .rules import FINISHED_STATUSES, read_only_since

KEEP_AFTER_READ_ONLY = timedelta(days=365)


def due_for_deletion(now=None):
    """Conversations read-only for at least 12 months."""
    cutoff = (now or timezone.now()) - KEEP_AFTER_READ_ONLY
    maybe = (
        Q(gig__status__in=FINISHED_STATUSES) | Q(gig__moderation_status='removed')
        | Q(application__moderation_status='removed')
        | Q(client__account_status='suspended') | Q(freelancer__account_status='suspended')
        | Q(client__deleted_at__isnull=False) | Q(freelancer__deleted_at__isnull=False)
    )
    candidates = Conversation.objects.filter(maybe).select_related('gig', 'application', 'client', 'freelancer')
    return [conversation for conversation in candidates if (since := read_only_since(conversation)) and since <= cutoff]
