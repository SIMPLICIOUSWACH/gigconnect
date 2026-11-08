"""
GET  /api/profile/verification/challenge/  a new random gesture for the selfie, good for ten minutes
POST /api/profile/verification/selfie/     the selfie (multipart): `selfie`, `challenge_id`, `consent`

Freelancers only. Nothing here returns the photo; only admins can read it.
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsFreelancer

from . import selfie as selfie_rules
from .models import FreelancerProfile, VerificationChallenge
from .verification import progress, send_for_review_if_ready

CONSENT_TEXT = (
    'I agree that GigConnect may use this photo to confirm my identity. It is only seen by administrators and deleted '
    '90 days after a decision.'
)


def consent_text():
    """The consent wording, with the privacy contact when one is set."""
    contact = settings.PRIVACY_CONTACT_EMAIL
    return f'{CONSENT_TEXT} Questions or deletion requests: {contact}.' if contact else CONSENT_TEXT


class ChallengeView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFreelancer]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'selfie_challenge'

    def get(self, request):
        challenge = VerificationChallenge.objects.create(user=request.user, text=selfie_rules.new_challenge_text())
        return Response({
            'id': str(challenge.id),
            'text': challenge.text,
            'expires_at': challenge.issued_at + selfie_rules.CHALLENGE_LIFETIME,
            'consent_text': consent_text(),
        })


class SelfieSubmissionSerializer(serializers.Serializer):
    selfie = serializers.FileField()
    challenge_id = serializers.UUIDField(error_messages={'required': 'Start again to get a new challenge.'})
    consent = serializers.BooleanField()

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError('Tick the box to agree before you send the photo.')
        return value


class SelfieView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFreelancer]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        body = SelfieSubmissionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        profile = request.user.freelancer_profile
        if profile.verification_status in (FreelancerProfile.VerificationStatus.PENDING,
                                           FreelancerProfile.VerificationStatus.VERIFIED):
            return Response({'detail': 'Your ID check is already with us.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            challenge = (
                VerificationChallenge.objects.select_for_update()
                .filter(pk=body.validated_data['challenge_id'], user=request.user).first()
            )
            if challenge is None or not selfie_rules.challenge_is_usable(challenge):
                return Response(
                    {'challenge_id': ['This challenge has expired or was already used. Start again for a new one.'],
                     'code': 'challenge_expired'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            photo, image = selfie_rules.process_selfie(body.validated_data['selfie'])
            problem = selfie_rules.face_problem(image)
            if problem:
                # The challenge stays usable, so a retake within the ten minutes needs no new one.
                return Response({'selfie': [problem], 'code': 'retake'}, status=status.HTTP_400_BAD_REQUEST)

            now = timezone.now()
            challenge.used_at = now
            challenge.save(update_fields=['used_at'])
            old = profile.selfie.name if profile.selfie else None
            profile.selfie.save(f'{profile.pk}.jpg', photo, save=False)
            profile.selfie_challenge = challenge.text
            profile.selfie_challenge_issued_at = challenge.issued_at
            profile.selfie_consent_at = now
            profile.selfie_submitted_at = now
            profile.needs_new_selfie = False
            changed = send_for_review_if_ready(profile)
            profile.save(update_fields=[
                'selfie', 'selfie_challenge', 'selfie_challenge_issued_at', 'selfie_consent_at', 'selfie_submitted_at',
                'needs_new_selfie', *changed,
            ])
            if old and old != profile.selfie.name:
                transaction.on_commit(lambda: profile.selfie.storage.delete(old))

        return Response({
            'detail': 'Selfie received.',
            'verification_status': profile.verification_status,
            'verification': progress(profile),
        })
