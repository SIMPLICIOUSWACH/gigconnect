"""
Every change an admin can make, in one place. Each function checks the change is allowed, makes it, writes its
AdminAction row and tells the affected user, all in one transaction: either all of that happens or none of it.

The views turn ModerationError into a 400. Removing and suspending are reversible. Deleting an account is not: it
erases the person's details through accounts/services.delete_account, the same code as deleting your own account.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from accounts.services import delete_account
from applications.models import Application
from gigs.models import Gig
from notifications.models import Notification
from notifications.service import notify
from profiles import decisions
from profiles.models import FreelancerProfile
from reviews.models import Review
from reviews.service import refresh_rating
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


def _record(admin, action, target_type, target_id, reason, target_label=''):
    return AdminAction.objects.create(
        admin=admin, action=action, target_type=target_type, target_id=target_id, reason=reason,
        target_label=target_label,
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


def mask_email(email):
    """j***@gmail.com: enough to recognise an account in the audit log, not enough to contact the person."""
    local, _, domain = (email or '').partition('@')
    return f'{local[:1]}***@{domain}' if local and domain else '***'


def _send_deletion_email(address, name, reason):
    contact = settings.PRIVACY_CONTACT_EMAIL
    message = (
        f'Hi {name},\n\nYour GigConnect account has been deleted by an administrator. Reason: {reason}\n\n'
        "Your personal details have been erased and the account can't be recovered."
    )
    if contact:
        message += f'\n\nQuestions about your data: {contact}'
    send_mail(
        subject='GigConnect: Your account has been deleted', message=message,
        from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[address],
    )


def deletion_refusal(admin, user):
    """Why this admin can't delete this account at all, or None. The delete preview shows the same message."""
    if user.pk == admin.pk:
        return "You can't delete your own account."
    if user.role == User.Role.ADMIN:
        return "Admin accounts can't be deleted here."
    if user.deleted_at is not None:
        return 'This account has already been deleted.'
    if not user.is_suspended:
        return 'Suspend this account first. Only suspended accounts can be deleted.'
    return None


def delete_user(admin, user, reason, confirm_email, force=False):
    """
    Erase a suspended account. The admin types the account's email to confirm. In-progress work blocks it unless
    force is set, which closes that work (accounts.services.AccountDeletionBlocked otherwise). Returns the summary.
    """
    refusal = deletion_refusal(admin, user)
    if refusal:
        raise ModerationError(refusal)
    reason = clean_reason(reason, required=True)
    if (confirm_email or '').strip() != user.email:
        raise ModerationError("The email you typed doesn't match this account's email.")

    # Taken before the details are erased: the email goes to the old address, the log keeps only a masked one.
    address, name = user.email, user.full_name
    with transaction.atomic():
        summary = delete_account(user, force=force)
        _record(
            admin, Action.DELETE_USER, Target.USER, user.pk, reason,
            target_label=f'Deleted user · {mask_email(address)}',
        )
        # Sent once the deletion is saved, so a deletion that fails never tells anyone it happened. A mail failure
        # is logged and changes nothing.
        transaction.on_commit(lambda: _send_deletion_email(address, name, reason), robust=True)
    return summary


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

def decide_verification(admin, profile, approve, reason='', checklist=None, reason_code='', redo=''):
    """
    Approve or reject an ID check. Approving needs both parts and every checklist item ticked. Rejecting needs a reason
    and the part to send again (decisions.REDO_CHOICES); only that part is asked for, and the other is kept.
    """
    Status = FreelancerProfile.VerificationStatus
    if profile.verification_status != Status.PENDING:
        raise ModerationError('This verification has already been decided.')

    if approve:
        reason = clean_reason(reason, required=False)
        if not (profile.id_document and profile.selfie):
            raise ModerationError('Both the ID and the selfie are needed before this can be approved.')
        unticked = [label for key, label in decisions.CHECKLIST.items() if not (checklist or {}).get(key)]
        if unticked:
            raise ModerationError(f'Tick every check before approving. Still unticked: {"; ".join(unticked)}.')
    else:
        if reason_code not in decisions.REJECTION_REASONS:
            raise ModerationError('Choose a reason for the rejection.')
        reason = clean_reason(decisions.rejection_text(reason_code, reason or ''), required=True)
        if redo not in decisions.REDO_CHOICES:
            raise ModerationError('Choose what they need to send again: the ID, the selfie or both.')

    with transaction.atomic():
        profile.verification_status = Status.VERIFIED if approve else Status.REJECTED
        profile.verification_decided_at = timezone.now()
        profile.needs_new_id = not approve and redo in (decisions.REDO_ID, decisions.REDO_BOTH)
        profile.needs_new_selfie = not approve and redo in (decisions.REDO_SELFIE, decisions.REDO_BOTH)
        profile.save(update_fields=[
            'verification_status', 'verification_decided_at', 'needs_new_id', 'needs_new_selfie',
        ])
        action = _record(
            admin, Action.VERIFY_APPROVE if approve else Action.VERIFY_REJECT, Target.USER, profile.user_id, reason,
        )
        if approve:
            notify(
                profile.user, Kind.VERIFICATION_APPROVED, 'Your ID is verified',
                f'An administrator checked your ID and selfie. Your profile now shows that you are verified.'
                f'{_because(reason)}',
                link=f'/profile/{profile.user_id}', email_preference='status_change_email',
            )
        else:
            notify(
                profile.user, Kind.VERIFICATION_REJECTED, 'Your ID verification was not approved',
                f'An administrator could not approve your ID check.{_because(reason)} To try again, '
                f'{decisions.REDO_WORDS[redo]} from Settings. Everything else you sent is kept.',
                link='/settings/verification', email_preference='status_change_email',
            )
    return action


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

def _tell_about_review(review, kind, title, body, reason):
    """Both people hear about it: the freelancer who was rated and the client who wrote it (unless deleted)."""
    for person, link in ((review.freelancer, f'/profile/{review.freelancer_id}'), (review.client, '/gigs/mine')):
        if person.deleted_at is None:
            notify(person, kind, title, f'{body}{_because(reason)}', link=link, email_preference='status_change_email')


def remove_review(admin, review, reason):
    reason = clean_reason(reason, required=True)
    if review.is_removed:
        raise ModerationError('This review has already been removed.')

    title = review.gig.title
    with transaction.atomic():
        review.moderation_status = Review.Moderation.REMOVED
        review.removed_reason = reason
        review.removed_at = timezone.now()
        review.save(update_fields=['moderation_status', 'removed_reason', 'removed_at'])
        refresh_rating(review.freelancer)  # a removed review no longer counts towards the average
        action = _record(admin, Action.REMOVE_REVIEW, Target.REVIEW, review.pk, reason)
        _tell_about_review(
            review, Kind.REVIEW_REMOVED, f'The review of "{title}" was removed',
            f'An administrator removed the review of "{title}". It is no longer shown and no longer counts towards '
            'the rating.', reason,
        )
    return action


def restore_review(admin, review, reason=''):
    reason = clean_reason(reason, required=False)
    if not review.is_removed:
        raise ModerationError('This review has not been removed.')

    title = review.gig.title
    with transaction.atomic():
        review.moderation_status = Review.Moderation.VISIBLE
        review.removed_reason = ''
        review.removed_at = None
        review.save(update_fields=['moderation_status', 'removed_reason', 'removed_at'])
        refresh_rating(review.freelancer)
        action = _record(admin, Action.RESTORE_REVIEW, Target.REVIEW, review.pk, reason)
        _tell_about_review(
            review, Kind.REVIEW_RESTORED, f'The review of "{title}" is back',
            f'An administrator restored the review of "{title}". It is shown again and counts towards the rating.',
            reason,
        )
    return action
