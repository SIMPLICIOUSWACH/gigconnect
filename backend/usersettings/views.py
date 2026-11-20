from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from accounts.email import send_verification_email_on_commit
from accounts.serializers import UserSerializer
from accounts.services import AccountDeletionBlocked, delete_account
from applications.privacy import export_applications
from gigs.models import GigInteraction
from messaging.privacy import export_messages
from notifications import events
from notifications.serializers import NotificationSerializer

from .models import NotificationPreference, UserSession
from .serializers import AccountSettingsSerializer, NotificationPreferenceSerializer, UserSessionSerializer
from .sessions import revoke_all_sessions


class AccountSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        user = request.user
        old_email = user.email

        serializer = AccountSettingsSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        outcome = {}
        if user.email != old_email:
            user.is_email_verified = False
            user.save(update_fields=['is_email_verified'])
            outcome = send_verification_email_on_commit(user)

        data = UserSerializer(user).data
        # Only present when the email changed: whether the new verification link could be sent.
        if 'sent' in outcome:
            data['verification_email_sent'] = outcome['sent']
        return Response(data)


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
        revoke_all_sessions(user)
        events.password_changed(user)

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
        revoke_all_sessions(request.user)
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
        return Response({
            'user': UserSerializer(user).data,
            'notification_preferences': NotificationPreferenceSerializer(preference).data,
            'applications': export_applications(user),
            'notifications': NotificationSerializer(user.notifications.order_by('created_at'), many=True).data,
            # Messages the user sent. The other person's messages are theirs, so they aren't included.
            'messages_sent': export_messages(user),
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

        # The same deletion an admin's uses (accounts/services.py). People can't force past in-progress work.
        try:
            delete_account(user)
        except AccountDeletionBlocked as blocked:
            return Response(
                {'detail': str(blocked), 'code': 'active_work', 'active_work': blocked.work},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'detail': 'Account deleted.'})
