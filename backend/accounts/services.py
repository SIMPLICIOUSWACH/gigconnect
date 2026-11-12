"""
Deleting an account. Self-deletion (Privacy & Data) and an admin's deletion both call delete_account, so an account is
deleted the same way whoever does it. Deleting means erasing: the row stays, anonymised, so the other side of a chat
or an application still makes sense, but the person's details are gone and the account can't be recovered.

What happens, all in one transaction:
- In-progress work blocks the deletion (gigs the user is running as a client, or a hire on an in-progress gig as a
  freelancer). Only an admin can go ahead anyway (force=True): those gigs are closed and the other person is told.
- The user's open gigs are closed, and freelancers still waiting on them are told.
- Gig browsing history and notifications are deleted.
- Applications are emptied of their text and open ones withdrawn (applications/privacy.py).
- ID images, selfie and the plain ID number are deleted; the keyed hash stays (profiles/id_privacy.py).
- Chats stay for the other person, who sees "Deleted user" and a read-only chat (messaging/privacy.py).
- Name, email and phone are replaced, the password made unusable, and every session revoked.
"""

from django.db import transaction
from django.utils import timezone

from applications.models import Application
from applications.privacy import OPEN_STATUSES, erase_applications
from gigs.models import Gig, GigInteraction
from messaging.models import Conversation
from messaging.rules import read_only_reason
from notifications.models import Notification
from notifications.service import notify
from profiles.id_privacy import erase_id_images
from usersettings.sessions import revoke_all_sessions

from .models import User

ACTIVE_WORK_MESSAGE = 'Finish or close these first, or contact support.'
CLOSED_FOR_APPLICANTS = "This gig was closed because the client's account was removed."
CLOSED_FOR_OTHER_PARTY = 'This gig was closed because the other account was removed.'


class AccountDeletionBlocked(Exception):
    """The account has in-progress work. `work` lists it, as active_work returns it."""

    def __init__(self, work):
        super().__init__(ACTIVE_WORK_MESSAGE)
        self.work = work


def _in_progress_gigs(user):
    return Gig.objects.filter(client=user, status=Gig.Status.IN_PROGRESS).order_by('created_at')


def _in_progress_hires(user):
    return (
        Application.objects.filter(freelancer=user, status=Application.Status.HIRED, gig__status=Gig.Status.IN_PROGRESS)
        .select_related('gig__client').order_by('created_at')
    )


def _hired_freelancer(gig):
    hire = gig.applications.filter(status=Application.Status.HIRED).select_related('freelancer').first()
    return hire.freelancer if hire else None


def active_work(user):
    """In-progress gigs the user runs as a client, and in-progress gigs they are hired on as a freelancer."""
    work = []
    for gig in _in_progress_gigs(user):
        freelancer = _hired_freelancer(gig)
        work.append({
            'gig_id': str(gig.pk), 'title': gig.title, 'as': 'client',
            'other_party': freelancer.full_name if freelancer else None,
        })
    for application in _in_progress_hires(user):
        work.append({
            'gig_id': str(application.gig_id), 'title': application.gig.title, 'as': 'freelancer',
            'other_party': application.gig.client.full_name,
        })
    return work


def _open_gig_applicants(gigs):
    return Application.objects.filter(gig__in=gigs, status__in=OPEN_STATUSES).select_related('freelancer', 'gig')


def _open_conversations(user):
    conversations = Conversation.objects.filter(client=user) | Conversation.objects.filter(freelancer=user)
    conversations = conversations.select_related('gig', 'application', 'client', 'freelancer')
    return [conversation for conversation in conversations if read_only_reason(conversation) is None]


def _id_files(user):
    profile = getattr(user, 'freelancer_profile', None)
    if profile is None:
        return 0, False
    return sum(1 for field in (profile.id_document, profile.selfie) if field), bool(profile.id_number)


def deletion_preview(user):
    """What deleting this account would do, without doing it."""
    open_gigs = Gig.objects.filter(client=user, status=Gig.Status.OPEN)
    files, has_number = _id_files(user)
    return {
        'active_work': active_work(user),
        'open_gigs_closed': open_gigs.count(),
        'applicants_notified': _open_gig_applicants(open_gigs).count(),
        'applications_emptied': Application.objects.filter(freelancer=user).count(),
        'id_files_deleted': files,
        'id_number_deleted': has_number,
        'conversations_made_read_only': len(_open_conversations(user)),
        'notifications_deleted': Notification.objects.filter(recipient=user).count(),
        'gig_history_deleted': GigInteraction.objects.filter(user=user).count(),
    }


def _close(gig):
    gig.status = Gig.Status.CLOSED
    gig.save(update_fields=['status', 'updated_at'])


def _tell(person, gig, body, link=''):
    notify(
        person, Notification.Kind.GIG_CLOSED, f'"{gig.title}" was closed', body, link=link,
        email_preference='status_change_email', inapp_preference='status_change_inapp',
    )


def _close_active_work(user):
    """For an admin's forced deletion: close the in-progress gigs and tell the person on the other side."""
    closed = 0
    for gig in _in_progress_gigs(user):
        freelancer = _hired_freelancer(gig)
        _close(gig)
        closed += 1
        if freelancer is not None:
            _tell(freelancer, gig, CLOSED_FOR_OTHER_PARTY, link=f'/gigs/{gig.pk}')
    for application in _in_progress_hires(user):
        gig = application.gig
        _close(gig)
        closed += 1
        _tell(gig.client, gig, CLOSED_FOR_OTHER_PARTY, link='/gigs/mine')
    return closed


def _close_open_gigs(user):
    """Close the user's open gigs and tell each freelancer still waiting on one. Returns (gigs, applicants)."""
    gigs = list(Gig.objects.filter(client=user, status=Gig.Status.OPEN))
    applicants = list(_open_gig_applicants(gigs))
    for gig in gigs:
        _close(gig)
    for application in applicants:
        _tell(application.freelancer, application.gig, CLOSED_FOR_APPLICANTS, link=f'/applications/{application.pk}')
    return len(gigs), len(applicants)


def delete_account(user, force=False):
    """
    Erase the account. Raises AccountDeletionBlocked if there is in-progress work and force is False. Returns a summary
    of what was done. Call it inside the caller's transaction or on its own; either way it is all or nothing.
    """
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        work = active_work(user)
        if work and not force:
            raise AccountDeletionBlocked(work)

        conversations = len(_open_conversations(user))
        in_progress_closed = _close_active_work(user) if work else 0
        open_closed, applicants = _close_open_gigs(user)

        # Browsing history is personal data with no use once the account is gone, so it is deleted outright.
        interactions, _ = GigInteraction.objects.filter(user=user).delete()
        notifications, _ = Notification.objects.filter(recipient=user).delete()

        # Applications are shared with the client reviewing them, so they are emptied and closed, not deleted.
        applications = erase_applications(user)

        # ID images and the plain ID number go now; the keyed hash stays, so the same ID can't simply be reused.
        files, has_number = _id_files(user)
        profile = getattr(user, 'freelancer_profile', None)
        if profile is not None:
            erase_id_images(profile)

        # Chats need nothing here: deleted_at makes them read-only, with the sender shown as "Deleted user".
        user.full_name = 'Deleted User'
        user.email = f'deleted-{user.id}@gigconnect.invalid'
        user.phone = ''
        user.is_active = False
        user.deleted_at = timezone.now()
        user.set_unusable_password()
        user.save()
        revoke_all_sessions(user)

    return {
        'gigs_closed': in_progress_closed + open_closed,
        'applicants_notified': applicants,
        'applications_emptied': applications,
        'id_files_deleted': files,
        'id_number_deleted': has_number,
        'conversations_made_read_only': conversations,
        'notifications_deleted': notifications,
        'gig_history_deleted': interactions,
    }
