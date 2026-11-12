"""
Deleting a user's account, for admins. The account must be suspended first, and deleting it erases the person's
details the same way self-deletion does (accounts/services.delete_account). It can't be undone.

    GET  /api/admin/users/<id>/delete-preview/   what deleting would do, and anything that stops it
    POST /api/admin/users/<id>/delete/           {"reason", "confirm_email", "force"}: delete; returns a summary
"""

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response

from accounts.models import User
from accounts.services import AccountDeletionBlocked, deletion_preview

from . import moderation
from .views import AdminView


class DeleteUserSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default='')
    confirm_email = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False, default='')
    force = serializers.BooleanField(required=False, default=False)


class UserDeletePreviewView(AdminView):
    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        refusal = moderation.deletion_refusal(request.user, user)
        data = {'refusal': refusal, 'can_delete': refusal is None}
        if user.deleted_at is None:
            data.update(deletion_preview(user))
        return Response(data)


class DeleteUserView(AdminView):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        body = DeleteUserSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        values = body.validated_data
        try:
            summary = moderation.delete_user(
                request.user, user, values['reason'], values['confirm_email'], force=values['force'],
            )
        except moderation.ModerationError as error:
            return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except AccountDeletionBlocked as blocked:
            return Response(
                {
                    'detail': 'This account has work in progress. Tick the box to close it, or wait until it is done.',
                    'code': 'active_work', 'active_work': blocked.work,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'detail': 'Account deleted.', 'summary': summary})
