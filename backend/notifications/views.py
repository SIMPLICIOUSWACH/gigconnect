"""
Endpoints, for the signed-in user's own notifications only:
    GET  /api/notifications/               newest first, paginated; ?unread=true for unread ones
    GET  /api/notifications/unread-count/  the number on the bell
    POST /api/notifications/<id>/read/     mark one as read
    POST /api/notifications/read-all/      mark all as read
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from gigs.pagination import GigPagination

from .models import Notification
from .serializers import NotificationSerializer


class NotificationFilterSerializer(serializers.Serializer):
    unread = serializers.BooleanField(required=False, allow_null=True, default=None)


def unread_of(user):
    return Notification.objects.filter(recipient=user, read_at__isnull=True)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = GigPagination

    def get_queryset(self):
        filters = NotificationFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        mine = Notification.objects.filter(recipient=self.request.user)
        if filters.validated_data['unread']:
            mine = mine.filter(read_at__isnull=True)
        return mine.order_by('-created_at', '-id')


class UnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({'unread': unread_of(request.user).count()})


class MarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at'])
        return Response(NotificationSerializer(notification).data)


class MarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        return Response({'marked': unread_of(request.user).update(read_at=timezone.now())})
