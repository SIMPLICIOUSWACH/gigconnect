"""
Keeping as little of someone's ID as possible.

- The ID number is also stored as a keyed hash (HMAC-SHA256 with ID_HASH_KEY) plus its last 3 characters. The hash
  cannot be turned back into the number without the key, but the same number always gives the same hash, so a second
  account using the same ID can still be spotted after the number itself is gone.
- 90 days after an admin's final decision, the ID document, the selfie, the plain number and the challenge text are
  deleted (purge_id_images). The decision, the times, the face score and its model name, and the hash are kept.
- Deleting an account deletes the same things straight away.
"""

import hashlib
import hmac
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import FreelancerProfile

RETENTION = timedelta(days=90)
Status = FreelancerProfile.VerificationStatus


def hash_key():
    """ID_HASH_KEY, or a key derived from SECRET_KEY when it is not set (manage.py check warns)."""
    configured = settings.ID_HASH_KEY
    if configured:
        return configured.encode()
    return hashlib.sha256(f'gigconnect-id-hash:{settings.SECRET_KEY}'.encode()).digest()


def normalise_id_number(value):
    return re.sub(r'[\s\-./]', '', value or '').upper()


def hash_id_number(value):
    number = normalise_id_number(value)
    if not number:
        return ''
    return hmac.new(hash_key(), number.encode(), hashlib.sha256).hexdigest()


def fingerprint_fields(id_number):
    """{'id_number_hash': ..., 'id_number_last3': ...} for a newly sent ID number."""
    number = normalise_id_number(id_number)
    return {'id_number_hash': hash_id_number(number), 'id_number_last3': number[-3:]}


def other_accounts_with_same_id(profile):
    if not profile.id_number_hash:
        return FreelancerProfile.objects.none()
    return FreelancerProfile.objects.filter(id_number_hash=profile.id_number_hash).exclude(pk=profile.pk)


def erase_id_images(profile, now=None):
    """
    Delete the ID document and selfie files and clear the plain number and the challenge text. Keeps the decision,
    times, score, model name, hash and last 3 characters. The files are removed once the change is saved.
    """
    # Read the stored file names again, so a stale copy of the profile can never leave a file behind.
    profile.refresh_from_db(fields=['id_document', 'selfie'])
    files = [field.name for field in (profile.id_document, profile.selfie) if field]
    profile.id_document = None
    profile.selfie = None
    profile.id_number = ''
    profile.selfie_challenge = ''
    profile.id_images_purged_at = now or timezone.now()
    profile.save(update_fields=['id_document', 'selfie', 'id_number', 'selfie_challenge', 'id_images_purged_at'])
    storage = FreelancerProfile._meta.get_field('id_document').storage
    transaction.on_commit(lambda: [storage.delete(name) for name in files])
    return files


def due_for_purge(now=None):
    """Checks decided at least 90 days ago that still hold an image or the plain number."""
    cutoff = (now or timezone.now()) - RETENTION
    has_data = (
        FreelancerProfile.objects.exclude(id_document='').exclude(id_document__isnull=True)
        | FreelancerProfile.objects.exclude(selfie='').exclude(selfie__isnull=True)
        | FreelancerProfile.objects.exclude(id_number='')
    )
    return has_data.filter(
        verification_status__in=[Status.VERIFIED, Status.REJECTED], verification_decided_at__lte=cutoff,
    ).distinct()
