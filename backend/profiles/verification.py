"""
When an ID check is ready for an admin. It needs both parts, the ID document and the selfie, and neither may be one an
admin asked to be redone.
"""

from django.utils import timezone

from .face_match import record_face_match
from .models import FreelancerProfile

Status = FreelancerProfile.VerificationStatus


def ready_for_review(profile):
    return (
        bool(profile.id_document) and bool(profile.selfie)
        and not profile.needs_new_id and not profile.needs_new_selfie
    )


def send_for_review_if_ready(profile):
    """Put the profile in the admin queue once both parts are in. Returns the fields changed, for save()."""
    if profile.verification_status in (Status.PENDING, Status.VERIFIED) or not ready_for_review(profile):
        return []
    profile.verification_status = Status.PENDING
    profile.verification_submitted_at = timezone.now()
    return ['verification_status', 'verification_submitted_at', *record_face_match(profile)]


def progress(profile):
    """What the freelancer still has to send, for their own account page. No files, no ID number."""
    return {
        'has_id_document': bool(profile.id_document),
        'has_selfie': bool(profile.selfie),
        'needs_new_id': profile.needs_new_id,
        'needs_new_selfie': profile.needs_new_selfie,
    }
