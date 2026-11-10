"""
Chat between a client and the freelancer they hired. Every endpoint is for the two participants only: anyone else,
admins included, gets 404, so the endpoint doesn't reveal that a chat exists. (Admins can only see a chat someone
reported, through /api/admin/chat-reports/.)

    GET  /api/conversations/                      newest activity first, paginated
    GET  /api/conversations/unread-count/         {"unread": n} for the navbar badge
    GET  /api/conversations/<id>/                 one conversation
    GET  /api/conversations/<id>/messages/        the latest 50; ?before=<message id> for earlier ones,
                                                  ?after=<message id> for newer ones (polling)
    POST /api/conversations/<id>/messages/        send {"body"}: 20 a minute at most
    POST /api/conversations/<id>/read/            mark the other person's messages as read
    POST /api/conversations/<id>/report/          {"reason"}: flag the chat for an admin
"""

from django.db import transaction
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from gigs.pagination import GigPagination

from . import events
from .models import ChatReport, Conversation, Message
from .rules import read_only_reason
from .safety import SAFETY_TIP, mentions_contact_or_payment
from .serializers import ConversationSerializer, MessageSerializer, NewMessageSerializer, ReportSerializer, display_name

PAGE = 50
MAX_NEWER = 200


def conversations_of(user):
    """The user's conversations, with the last message and their unread count worked out in the same query."""
    latest = Message.objects.filter(conversation=OuterRef('pk')).order_by('-created_at', '-id')
    unread = Q(messages__read_at__isnull=True) & ~Q(messages__sender=user)
    return (
        Conversation.objects.filter(Q(client=user) | Q(freelancer=user))
        .select_related('gig', 'application', 'client', 'freelancer')
        .annotate(
            last_body=Subquery(latest.values('body')[:1]),
            last_sender_id=Subquery(latest.values('sender_id')[:1]),
            unread_count=Count('messages', filter=unread),
        )
        .order_by(F('last_message_at').desc(nulls_last=True), '-created_at')
    )


def conversation_or_404(user, pk):
    return get_object_or_404(conversations_of(user), pk=pk)


class ConversationListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = GigPagination
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return conversations_of(self.request.user)


class ConversationDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        conversation = conversation_or_404(request.user, pk)
        return Response(ConversationSerializer(conversation, context={'request': request}).data)


class UnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        count = Message.objects.filter(
            Q(conversation__client=user) | Q(conversation__freelancer=user), read_at__isnull=True,
        ).exclude(sender=user).count()
        return Response({'unread': count})


class MessageQuerySerializer(serializers.Serializer):
    after = serializers.UUIDField(required=False)
    before = serializers.UUIDField(required=False)


class MessagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if self.request.method == 'POST':
            self.throttle_scope = 'message_send'
            return [ScopedRateThrottle()]
        return []

    def get(self, request, pk):
        conversation = conversation_or_404(request.user, pk)
        query = MessageQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        messages = conversation.messages.all()

        def anchor(key):
            message = messages.filter(pk=query.validated_data[key]).first()
            if message is None:
                raise serializers.ValidationError({key: 'That message is not in this conversation.'})
            return Q(created_at=message.created_at, id__gt=message.id) | Q(created_at__gt=message.created_at), \
                Q(created_at=message.created_at, id__lt=message.id) | Q(created_at__lt=message.created_at)

        has_earlier = False
        if 'after' in query.validated_data:
            newer, _ = anchor('after')
            rows = list(messages.filter(newer).order_by('created_at', 'id')[:MAX_NEWER])
        else:
            if 'before' in query.validated_data:
                _, older = anchor('before')
                messages = messages.filter(older)
            page = list(messages.order_by('-created_at', '-id')[:PAGE + 1])
            has_earlier = len(page) > PAGE
            rows = list(reversed(page[:PAGE]))
        data = MessageSerializer(rows, many=True, context={'request': request}).data
        return Response({'results': data, 'has_earlier': has_earlier})

    def post(self, request, pk):
        conversation = conversation_or_404(request.user, pk)
        body = NewMessageSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        me = request.user
        i_am_client = me.pk == conversation.client_id

        reason = read_only_reason(conversation)
        if reason:
            return Response({'detail': reason, 'code': 'read_only'}, status=status.HTTP_403_FORBIDDEN)
        if not i_am_client and conversation.first_message_at is None:
            name = display_name(conversation.client)
            return Response(
                {'detail': f'Wait for {name} to start the conversation.', 'code': 'waiting_for_client'},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            locked = Conversation.objects.select_for_update().get(pk=conversation.pk)
            message = Message.objects.create(conversation=locked, sender=me, body=body.validated_data['body'])
            locked.last_message_at = message.created_at
            locked.first_message_at = locked.first_message_at or message.created_at
            changed = ['last_message_at', 'first_message_at']
            tip_field = 'client_tip_shown' if i_am_client else 'freelancer_tip_shown'
            show_tip = mentions_contact_or_payment(message.body) and not getattr(locked, tip_field)
            if show_tip:
                setattr(locked, tip_field, True)
                changed.append(tip_field)
            locked.save(update_fields=changed)
            events.message_sent(locked, message)

        data = MessageSerializer(message, context={'request': request}).data
        data['safety_tip'] = SAFETY_TIP if show_tip else None
        return Response(data, status=status.HTTP_201_CREATED)


class MarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        conversation = conversation_or_404(request.user, pk)
        marked = conversation.messages.filter(read_at__isnull=True).exclude(sender=request.user).update(
            read_at=timezone.now(),
        )
        events.conversation_read(conversation, request.user)
        return Response({'marked': marked})


class ReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        conversation = conversation_or_404(request.user, pk)
        body = ReportSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        ChatReport.objects.create(
            conversation=conversation, reporter=request.user, reason=body.validated_data['reason'],
        )
        return Response(
            {'detail': 'Thanks. An administrator will look at this chat and may contact you.'},
            status=status.HTTP_201_CREATED,
        )
