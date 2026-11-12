"""
When a chat is read-only, and why. Worked out each time from the gig, the application and the two accounts, so a
reinstated account or a restored gig opens the chat again.
"""

from datetime import timedelta

from django.utils import timezone

GRACE_AFTER_FINISHED = timedelta(days=30)
FINISHED_STATUSES = ('completed', 'closed')


def _reasons(conversation):
    """[(since, message), ...] for every rule that makes this chat read-only now."""
    now = timezone.now()
    gig, application = conversation.gig, conversation.application
    found = []
    if gig.is_removed:
        found.append((gig.removed_at, 'An administrator removed this gig, so this chat is read-only.'))
    if application.is_removed:
        found.append((application.removed_at, 'An administrator removed this application, so this chat is read-only.'))
    for person in (conversation.client, conversation.freelancer):
        if person.deleted_at is not None:
            found.append((person.deleted_at, 'This account was deleted, so this chat is read-only.'))
        elif person.is_suspended:
            found.append((person.suspended_at, 'One of you has a suspended account, so this chat is read-only.'))
    if gig.status in FINISHED_STATUSES and gig.status_changed_at:
        since = gig.status_changed_at + GRACE_AFTER_FINISHED
        if since <= now:
            word = 'completed' if gig.status == 'completed' else 'closed'
            found.append((since, f'This gig was {word} more than 30 days ago, so this chat is read-only.'))
    return found


def read_only_reason(conversation):
    """The message to show if the chat is read-only, or None if both people can write."""
    found = _reasons(conversation)
    return found[0][1] if found else None


def read_only_since(conversation):
    """When the chat became read-only (the earliest rule that still applies), or None if it isn't."""
    times = [since for since, _ in _reasons(conversation) if since is not None]
    return min(times) if times else None
