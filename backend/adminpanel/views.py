"""
The GigConnect admin API, under /api/admin/. Every view here uses IsPlatformAdmin: anonymous users get 401 and
anyone who isn't an active admin gets 403. Changes go through moderation.py, which writes the audit log row and
tells the affected user in the same transaction.
"""

import mimetypes

from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsPlatformAdmin
from applications.models import Application
from applications.transitions import Status as ApplicationStatus
from gigs.models import Gig
from gigs.pagination import GigPagination
from profiles.models import FreelancerProfile

from . import moderation
from .models import AdminAction
from .recommender_info import recommender_overview
from .serializers import (
    AdminActionSerializer,
    AdminApplicationSerializer,
    AdminGigDetailSerializer,
    AdminGigListSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
    AdminVerificationSerializer,
    ReasonSerializer,
    VerificationDecisionSerializer,
    target_labels,
)
from .stats import platform_stats

HISTORY_LIMIT = 50


class AdminPagination(GigPagination):
    page_size = 20
    max_page_size = 100


class AdminView(APIView):
    permission_classes = [IsPlatformAdmin]


class AdminListView(generics.ListAPIView):
    permission_classes = [IsPlatformAdmin]
    pagination_class = AdminPagination


class FilterSerializer(serializers.Serializer):
    """Turns a bad filter value into a 400 instead of an empty list or a server error."""

    def __init__(self, view, **fields):
        super().__init__(data=view.request.query_params)
        for name, field in fields.items():
            self.fields[name] = field

    def values(self):
        self.is_valid(raise_exception=True)
        return {key: value for key, value in self.validated_data.items() if value not in (None, '')}


def optional(field_class, **kwargs):
    return field_class(required=False, allow_null=True, **kwargs)


def run_action(action, *args, reason=None):
    """Call a moderation function, turning a refusal into a 400 {"detail": "..."}."""
    try:
        return action(*args, reason)
    except moderation.ModerationError as error:
        raise ValidationError({'detail': str(error)}) from error


def reason_from(request):
    body = ReasonSerializer(data=request.data)
    body.is_valid(raise_exception=True)
    return body.validated_data['reason']


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

class StatsView(AdminView):
    def get(self, request):
        return Response(platform_stats())


class RecommenderView(AdminView):
    def get(self, request):
        return Response(recommender_overview())


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserListView(AdminListView):
    serializer_class = AdminUserListSerializer

    def get_queryset(self):
        params = FilterSerializer(
            self,
            search=optional(serializers.CharField, allow_blank=True),
            role=optional(serializers.ChoiceField, choices=User.Role.values),
            status=optional(serializers.ChoiceField, choices=['active', 'suspended', 'deleted']),
            verified=optional(serializers.BooleanField),
        ).values()
        users = User.objects.select_related('freelancer_profile').order_by('-created_at')
        if 'search' in params:
            users = users.filter(Q(full_name__icontains=params['search']) | Q(email__icontains=params['search']))
        if 'role' in params:
            users = users.filter(role=params['role'])
        if params.get('status') == 'deleted':
            users = users.filter(deleted_at__isnull=False)
        elif 'status' in params:
            users = users.filter(deleted_at__isnull=True, account_status=params['status'])
        if 'verified' in params:
            # "Verified" means a freelancer whose ID an admin approved. Clients have no ID check.
            verified = Q(freelancer_profile__verification_status=FreelancerProfile.VerificationStatus.VERIFIED)
            users = users.filter(verified) if params['verified'] else users.exclude(verified)
        return users


class UserDetailView(AdminView):
    def get(self, request, pk):
        user = get_object_or_404(User.objects.select_related('freelancer_profile', 'client_profile'), pk=pk)
        gigs = (
            Gig.objects.filter(client=user).select_related('client', 'category')
            .annotate(application_count=Count('applications')).order_by('-created_at')[:HISTORY_LIMIT]
        )
        applications = (
            Application.objects.filter(freelancer=user).select_related('gig', 'gig__client', 'freelancer')
            .order_by('-created_at')[:HISTORY_LIMIT]
        )
        history = (
            AdminAction.objects.filter(
                Q(target_type=AdminAction.TargetType.USER, target_id=user.pk)
                | Q(target_type=AdminAction.TargetType.GIG, target_id__in=Gig.objects.filter(client=user).values('pk'))
                | Q(
                    target_type=AdminAction.TargetType.APPLICATION,
                    target_id__in=Application.objects.filter(freelancer=user).values('pk'),
                )
            ).select_related('admin')[:HISTORY_LIMIT]
        )
        history = list(history)
        data = AdminUserDetailSerializer(user).data
        data['gigs'] = AdminGigListSerializer(gigs, many=True).data
        data['applications'] = AdminApplicationSerializer(applications, many=True).data
        data['history'] = AdminActionSerializer(
            history, many=True, context={'target_labels': target_labels(history)},
        ).data
        return Response(data)


class SuspendUserView(AdminView):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        run_action(moderation.suspend_user, request.user, user, reason=reason_from(request))
        user.refresh_from_db()
        return Response(AdminUserListSerializer(user).data)


class ReinstateUserView(AdminView):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        run_action(moderation.reinstate_user, request.user, user, reason=reason_from(request))
        user.refresh_from_db()
        return Response(AdminUserListSerializer(user).data)


# ---------------------------------------------------------------------------
# ID verifications
# ---------------------------------------------------------------------------

class VerificationListView(AdminListView):
    serializer_class = AdminVerificationSerializer

    def get_queryset(self):
        params = FilterSerializer(
            self, status=optional(serializers.ChoiceField, choices=FreelancerProfile.VerificationStatus.values),
        ).values()
        wanted = params.get('status', FreelancerProfile.VerificationStatus.PENDING)
        # Oldest submission first, so the queue is worked in the order people sent their IDs in.
        return (
            FreelancerProfile.objects.filter(verification_status=wanted).select_related('user')
            .order_by('verification_submitted_at', 'user__created_at')
        )


class VerificationDetailView(AdminView):
    def get(self, request, pk):
        profile = get_object_or_404(FreelancerProfile.objects.select_related('user'), pk=pk)
        return Response(AdminVerificationSerializer(profile).data)

    def patch(self, request, pk):
        profile = get_object_or_404(FreelancerProfile.objects.select_related('user'), pk=pk)
        body = VerificationDecisionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        approve = body.validated_data['verification_status'] == FreelancerProfile.VerificationStatus.VERIFIED
        run_action(moderation.decide_verification, request.user, profile, approve, reason=body.validated_data['reason'])
        profile.refresh_from_db()
        return Response(AdminVerificationSerializer(profile).data)


class VerificationDocumentView(AdminView):
    """The uploaded ID document, streamed to admins only. Never cached by the browser."""

    def get(self, request, pk):
        profile = get_object_or_404(FreelancerProfile, pk=pk)
        if not profile.id_document:
            raise Http404
        try:
            handle = profile.id_document.open('rb')
        except FileNotFoundError as error:
            raise Http404 from error
        content_type = mimetypes.guess_type(profile.id_document.name)[0] or 'application/octet-stream'
        response = FileResponse(handle, content_type=content_type)
        response['Content-Disposition'] = 'inline'
        response['Cache-Control'] = 'no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


# ---------------------------------------------------------------------------
# Gigs
# ---------------------------------------------------------------------------

def gigs_with_counts():
    return Gig.objects.select_related('client', 'category').annotate(application_count=Count('applications'))


class GigListView(AdminListView):
    serializer_class = AdminGigListSerializer

    def get_queryset(self):
        params = FilterSerializer(
            self,
            search=optional(serializers.CharField, allow_blank=True),
            status=optional(serializers.ChoiceField, choices=Gig.Status.values),
            category=optional(serializers.CharField, allow_blank=True),
            moderation=optional(serializers.ChoiceField, choices=Gig.Moderation.values),
            client=optional(serializers.UUIDField),
        ).values()
        gigs = gigs_with_counts().order_by('-created_at')
        if 'search' in params:
            text = params['search']
            gigs = gigs.filter(
                Q(title__icontains=text) | Q(client__full_name__icontains=text) | Q(client__email__icontains=text)
            )
        if 'status' in params:
            gigs = gigs.filter(status=params['status'])
        if 'category' in params:
            gigs = gigs.filter(category__slug=params['category'])
        if 'moderation' in params:
            gigs = gigs.filter(moderation_status=params['moderation'])
            if params['moderation'] == Gig.Moderation.REMOVED:
                gigs = gigs.order_by('-removed_at')
        if 'client' in params:
            gigs = gigs.filter(client_id=params['client'])
        return gigs


class GigDetailView(AdminView):
    def get(self, request, pk):
        gig = get_object_or_404(gigs_with_counts().prefetch_related('skills'), pk=pk)
        return Response(AdminGigDetailSerializer(gig).data)


class RemoveGigView(AdminView):
    action = staticmethod(moderation.remove_gig)

    def post(self, request, pk):
        gig = get_object_or_404(Gig.objects.select_related('client'), pk=pk)
        run_action(self.action, request.user, gig, reason=reason_from(request))
        return Response(AdminGigListSerializer(gigs_with_counts().get(pk=pk)).data)


class RestoreGigView(RemoveGigView):
    action = staticmethod(moderation.restore_gig)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

def applications_with_people():
    return Application.objects.select_related('gig', 'gig__client', 'freelancer')


class ApplicationListView(AdminListView):
    serializer_class = AdminApplicationSerializer

    def get_queryset(self):
        params = FilterSerializer(
            self,
            id=optional(serializers.UUIDField),
            gig=optional(serializers.UUIDField),
            freelancer=optional(serializers.UUIDField),
            status=optional(serializers.ChoiceField, choices=ApplicationStatus.values),
            moderation=optional(serializers.ChoiceField, choices=Application.Moderation.values),
        ).values()
        applications = applications_with_people().order_by('-created_at')
        if 'id' in params:
            applications = applications.filter(pk=params['id'])
        if 'gig' in params:
            applications = applications.filter(gig_id=params['gig'])
        if 'freelancer' in params:
            applications = applications.filter(freelancer_id=params['freelancer'])
        if 'status' in params:
            applications = applications.filter(status=params['status'])
        if 'moderation' in params:
            applications = applications.filter(moderation_status=params['moderation'])
            if params['moderation'] == Application.Moderation.REMOVED:
                applications = applications.order_by('-removed_at')
        return applications


class RemoveApplicationView(AdminView):
    action = staticmethod(moderation.remove_application)

    def post(self, request, pk):
        application = get_object_or_404(applications_with_people(), pk=pk)
        run_action(self.action, request.user, application, reason=reason_from(request))
        application.refresh_from_db()
        return Response(AdminApplicationSerializer(application).data)


class RestoreApplicationView(RemoveApplicationView):
    action = staticmethod(moderation.restore_application)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AuditLogView(AdminListView):
    serializer_class = AdminActionSerializer

    def get_queryset(self):
        params = FilterSerializer(
            self,
            admin=optional(serializers.UUIDField),
            action=optional(serializers.ChoiceField, choices=AdminAction.Action.values),
            target_type=optional(serializers.ChoiceField, choices=AdminAction.TargetType.values),
        ).values()
        actions = AdminAction.objects.select_related('admin').order_by('-created_at')
        if 'admin' in params:
            actions = actions.filter(admin_id=params['admin'])
        if 'action' in params:
            actions = actions.filter(action=params['action'])
        if 'target_type' in params:
            actions = actions.filter(target_type=params['target_type'])
        return actions

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        serializer = self.get_serializer(page, many=True, context={'target_labels': target_labels(page)})
        return self.get_paginated_response(serializer.data)

