from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from accounts.email import send_verification_email
from accounts.otp import issue_otp
from accounts.serializers import UserSerializer
from gigs.models import GigInteraction

from .models import NotificationPreference, UserSession
from .serializers import AccountSettingsSerializer, NotificationPreferenceSerializer, UserSessionSerializer


def _blacklist_all_tokens(user):
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
    UserSession.objects.filter(user=user).delete()


class AccountSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        user = request.user
        old_email, old_phone = user.email, user.phone

        serializer = AccountSettingsSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if user.email != old_email:
            user.is_email_verified = False
            user.save(update_fields=['is_email_verified'])
            send_verification_email(user)

        if user.phone != old_phone:
            user.is_phone_verified = False
            user.save(update_fields=['is_phone_verified'])
            issue_otp(user)

        return Response(UserSerializer(user).data)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('current_password', '')
        new_password = request.data.get('new_password', '')

        if not user.check_password(current_password):
            return Response({'current_password': 'Incorrect password.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            return Response({'new_password': exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save(update_fields=['password'])
        _blacklist_all_tokens(user)

        return Response({'detail': 'Password changed. All sessions have been logged out.'})


class SessionListView(generics.ListAPIView):
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user)


class SessionRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        try:
            session = UserSession.objects.get(id=pk, user=request.user)
        except UserSession.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            token = OutstandingToken.objects.get(jti=session.jti)
            BlacklistedToken.objects.get_or_create(token=token)
        except OutstandingToken.DoesNotExist:
            pass

        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutAllView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        _blacklist_all_tokens(request.user)
        return Response({'detail': 'Logged out of all devices.'})


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        preference, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        return preference


class ExportDataView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        preference, _ = NotificationPreference.objects.get_or_create(user=user)
        interactions = GigInteraction.objects.filter(user=user).select_related('gig').order_by('created_at')
        # Applications are left out rather than faked as an empty list: that feature isn't built yet.
        return Response({
            'user': UserSerializer(user).data,
            'notification_preferences': NotificationPreferenceSerializer(preference).data,
            'gig_interactions': [
                {
                    'type': i.type,
                    'gig_id': str(i.gig_id),
                    'gig_title': i.gig.title,
                    'query': i.query,
                    'position': i.position,
                    'created_at': i.created_at,
                }
                for i in interactions
            ],
        })


class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        password = request.data.get('password', '')

        if not user.check_password(password):
            return Response({'password': 'Incorrect password.'}, status=status.HTTP_400_BAD_REQUEST)

        # Browsing history is personal data and has no use once the account is gone, so it is
        # deleted outright rather than anonymised.
        GigInteraction.objects.filter(user=user).delete()

        user.full_name = 'Deleted User'
        user.email = f'deleted-{user.id}@gigconnect.invalid'
        user.phone = ''
        user.is_active = False
        user.deleted_at = timezone.now()
        user.set_unusable_password()
        user.save()

        _blacklist_all_tokens(user)

        return Response({'detail': 'Account deleted.'})
