"""Helpers for tests that need an ID check with a selfie. The picture is drawn in code: never a real face."""

from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from .models import FreelancerProfile
from .verification import send_for_review_if_ready

CHALLENGE_TEXT = 'Hold your ID next to your face and show 3 fingers.'


def synthetic_selfie_bytes(size=(720, 960)):
    image = Image.new('RGB', size, (180, 140, 120))
    buffer = BytesIO()
    image.save(buffer, format='JPEG')
    return buffer.getvalue()


def add_selfie(profile):
    """Give the profile a selfie as if it had been sent through the app, and send the check for review if ready."""
    profile = FreelancerProfile.objects.get(pk=profile.pk)
    now = timezone.now()
    profile.selfie.save(f'{profile.pk}.jpg', ContentFile(synthetic_selfie_bytes()), save=False)
    profile.selfie_challenge = CHALLENGE_TEXT
    profile.selfie_challenge_issued_at = now
    profile.selfie_consent_at = now
    profile.selfie_submitted_at = now
    profile.needs_new_selfie = False
    changed = send_for_review_if_ready(profile)
    profile.save()
    return profile, changed
