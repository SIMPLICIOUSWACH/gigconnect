"""The one place that says which application status changes are allowed, and who may make them.

Like ALLOWED_STATUS_TRANSITIONS for gigs, everything else (models, views, the frontend's
copy of these rules) is built from this table.
"""

from django.db import models


class Status(models.TextChoices):
    PENDING = 'pending', 'Pending'
    UNDER_REVIEW = 'under_review', 'Under review'
    SHORTLISTED = 'shortlisted', 'Shortlisted'
    HIRED = 'hired', 'Hired'
    REJECTED = 'rejected', 'Rejected'
    WITHDRAWN = 'withdrawn', 'Withdrawn'


class Actor:
    CLIENT = 'client'
    FREELANCER = 'freelancer'


# The client moves an application forward one step at a time, and can reject it from any of the
# three live stages. No skipping: pending cannot jump straight to shortlisted or hired.
CLIENT_TRANSITIONS = {
    Status.PENDING: {Status.UNDER_REVIEW, Status.REJECTED},
    Status.UNDER_REVIEW: {Status.SHORTLISTED, Status.REJECTED},
    Status.SHORTLISTED: {Status.HIRED, Status.REJECTED},
}

# The freelancer can only withdraw, and only before the client has shortlisted them.
FREELANCER_TRANSITIONS = {
    Status.PENDING: {Status.WITHDRAWN},
    Status.UNDER_REVIEW: {Status.WITHDRAWN},
}

TRANSITIONS = {
    Actor.CLIENT: CLIENT_TRANSITIONS,
    Actor.FREELANCER: FREELANCER_TRANSITIONS,
}

# hired, rejected and withdrawn have no way out for anyone.
FINAL_STATUSES = frozenset({Status.HIRED, Status.REJECTED, Status.WITHDRAWN})


class InvalidTransition(ValueError):
    """Raised when someone tries a status change the rules above do not allow."""


def allowed_next_statuses(current_status, actor):
    """The statuses `actor` may move an application to from `current_status` (possibly none)."""
    return set(TRANSITIONS[actor].get(current_status, set()))


def can_transition(current_status, new_status, actor):
    return new_status in allowed_next_statuses(current_status, actor)
