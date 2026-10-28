"""
Every change an admin can make, in one place. Each function checks the change is allowed, makes it, writes its
AdminAction row and tells the affected user, all in one transaction: either all of that happens or none of it.

The views turn ModerationError into a 400. Removing and suspending are reversible: nothing here deletes anything.
"""

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from applications.models import Application
from gigs.models import Gig
from notifications.models import Notification
from notifications.service import notify
from profiles.models import FreelancerProfile
from usersettings.sessions import revoke_all_sessions

from .models import AdminAction

REASON_MAX_LENGTH = 1000

Action = AdminAction.Action
Target = AdminAction.TargetType
Kind = Notification.Kind


class ModerationError(ValueError):
    """The change isn't allowed. The message is shown to the admin."""


def clean_reason(reason, required):
    reason = (reason or '').strip() if isinstance(reason, str) else ''
    if required and not reason:
        raise ModerationError('Give a reason. The person affected is told what it says.')
    if len(reason) > REASON_MAX_LENGTH:
        raise ModerationError(f'Keep the reason under {REASON_MAX_LENGTH} characters.')
    return reason


def _record(admin, action, target_type, target_id, reason):
    return AdminAction.objects.create(
        admin=admin, action=action, target_type=target_type, target_id=target_id, reason=reason,
    )


def _because(reason):
    return f' Reason: {reason}' if reason else ''


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def suspend_user(admin, user, reason):
    reason = clean_reason(reason, required=True)
    if user.pk == admin.pk:
        raise ModerationError("You can't suspend your own account.")
    if user.role == User.Role.ADMIN:
        raise ModerationError("Admin accounts can't be suspended here.")
    if user.deleted_at is not None:
        raise ModerationError('This account has been deleted.')
    if user.is_suspended:
        raise ModerationError('This account is already suspended.')

    with transaction.atomic():
        user.account_status = User.AccountStatus.SUSPENDED
        user.suspended_reason = reason
        user.suspended_at = timezone.now()
        user.save(update_fields=['account_status', 'suspended_reason', 'suspended_at'])
        action = _record(admin, Action.SUSPEND_USER, Target.USER, user.pk, reason)
        notify(
            user, Kind.ACCOUNT_SUSPENDED, 'Your account has been suspended',
            f'An administrator suspended your GigConnect account, so you cannot log in for now. Any open gigs you '
            f'posted are hidden while it is suspended.{_because(reason)}',
            email_preference='security_alert_email',
        )
        revoke_all_sessions(user)
    return action


def reinstate_user(admin, user, reason=''):
    reason = clean_reason(reason, required=False)
    if not user.is_suspended:
        raise ModerationError('This account is not suspended.')

    with transaction.atomic():
        user.account_status = User.AccountStatus.ACTIVE
        user.suspended_reason = ''
        user.suspended_at = None
        user.save(update_fields=['account_status', 'suspended_reason', 'suspended_at'])
        action = _record(admin, Action.REINSTATE_USER, Target.USER, user.pk, reason)
        notify(
            user, Kind.ACCOUNT_REINSTATED, 'Your account is active again',
            'An administrator lifted the suspension on your GigConnect account. You can log in again.'
            f'{_because(reason)}',
            link='/login', email_preference='security_alert_email',
        )
    return action


# ---------------------------------------------------------------------------
# Gigs
# ---------------------------------------------------------------------------

def remove_gig(admin, gig, reason):
    reason = clean_reason(reason, required=True)
    if gig.is_removed:
        raise ModerationError('This gig has already been removed.')

    with transaction.atomic():
        gig.moderation_status = Gig.Moderation.REMOVED
        gig.removed_reason = reason
        gig.removed_at = timezone.now()
        # update_fields leaves updated_at alone, so the recommender's cached copy of the gig stays valid. The gig
        # drops out of the candidates through gigs.feed anyway.
        gig.save(update_fields=['moderation_status', 'removed_reason', 'removed_at'])
        action = _record(admin, Action.REMOVE_GIG, Target.GIG, gig.pk, reason)
        notify(
            gig.client, Kind.GIG_REMOVED, f'Your gig "{gig.title}" was removed',
            f'An administrator removed your gig "{gig.title}". Freelancers can no longer see it or apply, and you '
            f'cannot edit it.{_because(reason)}',
            link='/gigs/mine', email_preference='status_change_email',
        )
    return action


def restore_gig(admin, gig, reason=''):
    reason = clean_reason(reason, required=False)
    if not gig.is_removed:
        raise ModerationError('This gig has not been removed.')

    with transaction.atomic():
        gig.moderation_status = Gig.Moderation.VISIBLE
        gig.removed_reason = ''
        gig.removed_at = None
        gig.save(update_fields=['moderation_status', 'removed_reason', 'removed_at'])
        action = _record(admin, Action.RESTORE_GIG, Target.GIG, gig.pk, reason)
        notify(
            gig.client, Kind.GIG_RESTORED, f'Your gig "{gig.title}" is back',
            f'An administrator restored your gig "{gig.title}". It is shown again as it was before.{_because(reason)}',
            link=f'/gigs/{gig.pk}', email_preference='status_change_email',
        )
    return action


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

def remove_application(admin, application, reason):
    reason = clean_reason(reason, required=True)
    if application.is_removed:
        raise ModerationError('This application has already been removed.')

    title = application.gig.title
    with transaction.atomic():
        application.moderation_status = Application.Moderation.REMOVED
        application.removed_reason = reason
        application.removed_at = timezone.now()
        application.save(update_fields=['moderation_status', 'removed_reason', 'removed_at'])
        action = _record(admin, Action.REMOVE_APPLICATION, Target.APPLICATION, application.pk, reason)
        notify(
            application.freelancer, Kind.APPLICATION_REMOVED, f'Your application for "{title}" was removed',
            f'An administrator removed your application for "{title}". The client can no longer see it.'
            f'{_because(reason)}',
            link=f'/applications/{application.pk}', email_preference='status_change_email',
        )
    return action


def restore_application(admin, application, reason=''):
    reason = clean_reason(reason, required=False)
    if not application.is_removed:
        raise ModerationError('This application has not been removed.')

    title = application.gig.title
    with transaction.atomic():
        application.moderation_status = Application.Moderation.VISIBLE
        application.removed_reason = ''
        application.removed_at = None
        application.save(update_fields=['moderation_status', 'removed_reason', 'removed_at'])
        action = _record(admin, Action.RESTORE_APPLICATION, Target.APPLICATION, application.pk, reason)
        notify(
            application.freelancer, Kind.APPLICATION_RESTORED, f'Your application for "{title}" is back',
            f'An administrator restored your application for "{title}". The client can see it again.'
            f'{_because(reason)}',
            link=f'/applications/{application.pk}', email_preference='status_change_email',
        )
    return action


# ---------------------------------------------------------------------------
# ID verification
# ---------------------------------------------------------------------------

def decide_verification(admin, profile, approve, reason=''):
    reason = clean_reason(reason, required=not approve)
    if profile.verification_status != FreelancerProfile.VerificationStatus.PENDING:
        raise ModerationError('This verification has already been decided.')

    Status = FreelancerProfile.VerificationStatus
    with transaction.atomic():
        profile.verification_status = Status.VERIFIED if approve else Status.REJECTED
        profile.save(update_fields=['verification_status'])
        action = _record(
            admin, Action.VERIFY_APPROVE if approve else Action.VERIFY_REJECT, Target.USER, profile.user_id, reason,
        )
        if approve:
            notify(
                profile.user, Kind.VERIFICATION_APPROVED, 'Your ID is verified',
                f'An administrator checked your ID document. Your profile now shows that you are verified.'
                f'{_because(reason)}',
                link=f'/profile/{profile.user_id}', email_preference='status_change_email',
            )
        else:
            notify(
                profile.user, Kind.VERIFICATION_REJECTED, 'Your ID verification was not approved',
                f'An administrator could not approve your ID document. You can submit it again from Settings.'
                f'{_because(reason)}',
                link='/settings/verification', email_preference='status_change_email',
            )
    return action
