"""
What happens to a freelancer's applications when they export their data or delete their account.

Applications belong to two people: the freelancer who wrote them and the client who is reviewing
them. So deleting an account removes the freelancer's personal text but keeps the rows and the
status history, which keeps the client's counts and records honest.
"""

from django.db import transaction
from django.utils import timezone

from .models import Application, ApplicationStatusEvent
from .transitions import Status

# Statuses a client can still be working on. A deleted freelancer can't take part in these any more.
OPEN_STATUSES = (Status.PENDING, Status.UNDER_REVIEW, Status.SHORTLISTED)

ACCOUNT_DELETED_NOTE = 'Applicant deleted their account'


def export_applications(user):
    """Everything the user wrote or caused, for the data export: their applications and the history of each."""
    applications = (
        Application.objects.filter(freelancer=user)
        .select_related('gig')
        .prefetch_related('events')
        .order_by('created_at', 'id')
    )
    return [
        {
            'id': str(application.id),
            'gig_id': str(application.gig_id),
            'gig_title': application.gig.title,
            'status': application.status,
            'cover_letter': application.cover_letter,
            'portfolio_link': application.portfolio_link,
            'proposed_rate': application.proposed_rate,
            'created_at': application.created_at,
            'updated_at': application.updated_at,
            'status_history': [
                {
                    'from_status': event.from_status,
                    'to_status': event.to_status,
                    'note': event.note,
                    'created_at': event.created_at,
                    # The user's own name is theirs to see; anyone else is only named by role.
                    'changed_by': 'you' if event.changed_by_id == user.id else 'client or system',
                }
                for event in application.events.all()
            ],
        }
        for application in applications
    ]


@transaction.atomic
def erase_applications(user):
    """
    Called when a freelancer deletes their account. Returns how many applications were touched.

    - Pending, under review and shortlisted applications are withdrawn, each with a system status
      event (no person is named as the one who did it).
    - Cover letter, portfolio link and proposed rate are cleared on every application.
    - Any reason the freelancer typed when withdrawing is cleared from the history.
    - Rows and history stay. A hired application stays hired, because that is final.

    This is a system action rather than a freelancer transition, so it does not go through
    Application.change_status: the rules there only let a freelancer withdraw while pending or
    under review, and a shortlisted application also has to close when its owner leaves.
    """
    now = timezone.now()
    applications = Application.objects.filter(freelancer=user)

    still_open = list(applications.filter(status__in=OPEN_STATUSES).values_list('id', 'status'))
    ApplicationStatusEvent.objects.bulk_create([
        ApplicationStatusEvent(
            application_id=application_id,
            from_status=status,
            to_status=Status.WITHDRAWN,
            changed_by=None,
            note=ACCOUNT_DELETED_NOTE,
        )
        for application_id, status in still_open
    ])
    applications.filter(status__in=OPEN_STATUSES).update(status=Status.WITHDRAWN, updated_at=now)

    ApplicationStatusEvent.objects.filter(application__freelancer=user, changed_by=user).update(note='')
    return applications.update(cover_letter='', portfolio_link='', proposed_rate=None, updated_at=now)
