"""
Reported chats. Admins can't browse chats: they only see a conversation a participant reported, and every time they
open one an AdminAction (chat_viewed) is written. All under /api/admin/, IsPlatformAdmin like the rest.

    GET  /api/admin/chat-reports/?status=open|resolved|all   the reports, newest first (no messages);
                                                             &conversation=<id> for one chat's reports
    GET  /api/admin/chat-reports/<id>/                       the report and the whole chat; logged as chat_viewed
    POST /api/admin/chat-reports/<id>/resolve/               {"note"}: close the report; logged
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from messaging.models import ChatReport
from messaging.serializers import display_name

from .models import AdminAction
from .views import AdminListView, AdminView


def person(user):
    if user is None:
        return None
    return {'id': str(user.pk), 'full_name': display_name(user), 'account_status': user.account_status}


def report_row(report):
    conversation = report.conversation
    return {
        'id': str(report.pk),
        'conversation_id': str(conversation.pk),
        'gig': {'id': str(conversation.gig_id), 'title': conversation.gig.title},
        'client': person(conversation.client),
        'freelancer': person(conversation.freelancer),
        'reporter': person(report.reporter),
        'reason': report.reason,
        'created_at': report.created_at,
        'resolved_at': report.resolved_at,
        'resolved_by': person(report.resolved_by),
        'resolution_note': report.resolution_note,
    }


def reports():
    return ChatReport.objects.select_related(
        'conversation__gig', 'conversation__client', 'conversation__freelancer', 'reporter', 'resolved_by',
    )


class ReportFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['open', 'resolved', 'all'], required=False, default='open')
    conversation = serializers.UUIDField(required=False)


class ChatReportListView(AdminListView):
    def get_queryset(self):
        query = ReportFilterSerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        status = query.validated_data['status']
        rows = reports().order_by('-created_at')
        if 'conversation' in query.validated_data:
            rows = rows.filter(conversation_id=query.validated_data['conversation'])
        if status == 'open':
            rows = rows.filter(resolved_at__isnull=True)
        elif status == 'resolved':
            rows = rows.filter(resolved_at__isnull=False)
        return rows

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([report_row(report) for report in page])


class ChatReportDetailView(AdminView):
    def get(self, request, pk):
        report = get_object_or_404(reports(), pk=pk)
        conversation = report.conversation
        # Opening a reported chat is itself recorded, every time.
        AdminAction.objects.create(
            admin=request.user, action=AdminAction.Action.CHAT_VIEWED,
            target_type=AdminAction.TargetType.CONVERSATION, target_id=conversation.pk,
        )
        messages = conversation.messages.select_related('sender').order_by('id')
        all_reports = reports().filter(conversation=conversation).order_by('created_at')
        data = report_row(report)
        data['reports'] = [report_row(other) for other in all_reports]
        data['messages'] = [
            {'id': message.pk, 'sender': person(message.sender), 'body': message.body, 'created_at': message.created_at}
            for message in messages
        ]
        return Response(data)


class ResolveSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000, default='')


class ResolveChatReportView(AdminView):
    def post(self, request, pk):
        report = get_object_or_404(reports(), pk=pk)
        if report.resolved_at is not None:
            raise ValidationError({'detail': 'This report is already resolved.'})
        body = ResolveSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        note = body.validated_data['note'].strip()
        with transaction.atomic():
            report.resolved_at = timezone.now()
            report.resolved_by = request.user
            report.resolution_note = note
            report.save(update_fields=['resolved_at', 'resolved_by', 'resolution_note'])
            AdminAction.objects.create(
                admin=request.user, action=AdminAction.Action.CHAT_REPORT_RESOLVED,
                target_type=AdminAction.TargetType.CONVERSATION, target_id=report.conversation_id, reason=note,
            )
        return Response(report_row(report))
