from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .email import send_verification_email
from .models import User

# The same answer whether or not the address has an account, so this can't be used to find out who is registered.
SIGNED_OUT_ANSWER = "If an account with that email still needs verifying, we've sent it a new link."
SEND_FAILED = "We couldn't send the email. Try again in a few minutes."


class ResendRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResendVerificationView(APIView):
    """
    POST /api/auth/resend-verification/

    Signed in: resends to your own address and says whether it worked. Signed out: give {"email": ...}; the reply is
    always the same. Limited to a few a hour per person (see DEFAULT_THROTTLE_RATES).
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'verification_resend'

    def post(self, request):
        if request.user.is_authenticated:
            return self._resend_own(request.user)

        body = ResendRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=body.validated_data['email'], is_email_verified=False, is_active=True,
            deleted_at__isnull=True,
        ).first()
        if user is not None:
            send_verification_email(user)
        return Response({'detail': SIGNED_OUT_ANSWER})

    @staticmethod
    def _resend_own(user):
        if user.is_email_verified:
            return Response({'detail': 'Your email is already verified.'}, status=status.HTTP_400_BAD_REQUEST)
        if not send_verification_email(user):
            return Response({'detail': SEND_FAILED, 'sent': False}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'detail': f"We've sent a new link to {user.email}.", 'sent': True})
