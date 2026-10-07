"""
applications/views.py

Endpoints:
    POST  /api/gigs/<gig_id>/applications/             GigApplicationsView (freelancer applies)
    GET   /api/gigs/<gig_id>/applications/             GigApplicationsView (client lists applicants)
    GET   /api/applications/mine/                      MyApplicationsView
    GET   /api/applications/<pk>/                      ApplicationDetailView
    POST  /api/applications/<application_id>/withdraw/ WithdrawApplicationView
    PATCH /api/applications/<application_id>/status/   ApplicationStatusView
"""

import datetime

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsClientRole, IsEmailVerified, IsFreelancer
from gigs.models import Gig, GigInteraction
from gigs.pagination import GigPagination

from .models import Application, ApplicationStatusEvent
from .serializers import (
    ApplicationCreateSerializer,
    ApplicationDetailSerializer,
    ApplicationFilterSerializer,
    ApplicationListSerializer,
    ApplicationStatusUpdateSerializer,
)
from .transitions import Actor, InvalidTransition, Status

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ApplicationRuleError(APIException):
    """A business-rule failure. Renders as 400 {"detail": "..."}."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This application breaks an application rule."
    default_code = "application_rule"


# ---------------------------------------------------------------------------
# Apply to a gig
# ---------------------------------------------------------------------------

def _has_passed(cutoff):
    """True if a date or datetime cutoff is in the past."""
    if isinstance(cutoff, datetime.datetime):
        return cutoff < timezone.now()
    return cutoff < timezone.localdate()


class GigApplicationsView(APIView):
    """
    GET:  the gig's client lists its applicants (see get()).
    POST: a verified freelancer applies to a gig.

    Rules, checked in order (the first failure wins):
      1. The gig exists                                   -> 404
      2. The applicant is not the gig's own client        -> 403
      3. The gig is open                                  -> 400
      4. The application deadline has not passed
         (application_deadline, falling back to deadline) -> 400
      5. The freelancer has not withdrawn from this gig   -> 400
      6. The freelancer has not already applied           -> 400
      7. The request body is valid                        -> 400 (serializer errors)
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsFreelancer(), IsEmailVerified()]
        return [IsAuthenticated(), IsClientRole()]

    def get(self, request, gig_id):
        """The gig owner's view of who applied. Nobody else can see them."""
        gig = get_object_or_404(Gig, pk=gig_id)
        if gig.client_id != request.user.id:
            raise PermissionDenied("You can only see applicants for your own gigs.")

        filters = ApplicationFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        params = filters.validated_data

        base_qs = Application.objects.filter(gig=gig)

        # Counts ignore the status filter so the filter tabs always show every total.
        status_counts = {choice.value: 0 for choice in Status}
        for row in base_qs.order_by().values("status").annotate(n=Count("id")):
            status_counts[row["status"]] = row["n"]
        status_counts["total"] = sum(status_counts.values())

        qs = (
            base_qs.select_related("gig", "gig__client", "freelancer", "freelancer__freelancer_profile")
            .prefetch_related("events__changed_by", "freelancer__freelancer_profile__skills")
            .order_by("-created_at", "-id")
        )
        if params.get("status"):
            qs = qs.filter(status=params["status"])

        paginator = GigPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = ApplicationDetailSerializer(page, many=True, context={"request": request})
        response = paginator.get_paginated_response(serializer.data)
        response.data["status_counts"] = status_counts
        return response

    def post(self, request, gig_id):
        # 1. Gig exists
        try:
            gig = Gig.objects.select_related("client").get(pk=gig_id)
        except Gig.DoesNotExist:
            raise NotFound("This gig does not exist.")

        # 2. Not your own gig
        if gig.client_id == request.user.id:
            raise PermissionDenied("You cannot apply to your own gig.")

        # 3. Gig is open
        if gig.status != Gig.Status.OPEN:
            raise ApplicationRuleError(
                "This gig is no longer accepting applications.", code="gig_not_open"
            )

        # 4. Application deadline not passed. Same rule as the feed:
        #    application_deadline, falling back to the delivery deadline.
        cutoff = gig.application_deadline or gig.deadline
        if cutoff is not None and _has_passed(cutoff):
            raise ApplicationRuleError(
                "The application deadline for this gig has passed.",
                code="deadline_passed",
            )

        # 5 & 6. No earlier application. A withdrawn one gets its own message.
        #    (Fast path; the unique constraint below catches the race where
        #    two requests pass this check together.)
        existing = (
            Application.objects.filter(gig=gig, freelancer=request.user)
            .only("status")
            .first()
        )
        if existing is not None:
            if existing.status == Status.WITHDRAWN:
                raise ApplicationRuleError(
                    "You withdrew your application to this gig and cannot apply again.",
                    code="withdrawn",
                )
            raise ApplicationRuleError(
                "You have already applied to this gig.", code="already_applied"
            )

        # 7. Validate the body
        serializer = ApplicationCreateSerializer(
            data=request.data, context={"request": request, "gig": gig}
        )
        serializer.is_valid(raise_exception=True)

        # Save the application, its first status event and the apply
        # interaction together: all three or none.
        with transaction.atomic():
            # Only the application insert is guarded, so an IntegrityError
            # from the event or interaction surfaces as a real error instead
            # of being reported as a duplicate application.
            try:
                with transaction.atomic():
                    application = serializer.save(gig=gig, freelancer=request.user)
            except IntegrityError:
                # Unique (gig, freelancer) constraint hit by a concurrent request
                raise ApplicationRuleError(
                    "You have already applied to this gig.", code="already_applied"
                )

            ApplicationStatusEvent.objects.create(
                application=application,
                from_status="",
                to_status=application.status,
                changed_by=request.user,
            )

            GigInteraction.objects.create(
                gig=gig,
                user=request.user,
                type=GigInteraction.Type.APPLY,
            )

        out = ApplicationDetailSerializer(application, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# A freelancer's own applications
# ---------------------------------------------------------------------------

class MyApplicationsView(generics.ListAPIView):
    """
    GET: the signed-in freelancer's applications, filtered and paginated,
    with a status_counts summary added to the response.
    """

    serializer_class = ApplicationListSerializer
    permission_classes = [IsAuthenticated, IsFreelancer]
    pagination_class = GigPagination

    def get_queryset(self):
        return (
            Application.objects.filter(freelancer=self.request.user)
            .select_related("gig", "gig__client")
            .order_by("-created_at", "-id")
        )

    def list(self, request, *args, **kwargs):
        filters = ApplicationFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        params = filters.validated_data

        base_qs = self.get_queryset()

        # Counts are taken before the status filter so the tabs always
        # show totals for every status.
        status_counts = {choice.value: 0 for choice in Status}
        for row in base_qs.order_by().values("status").annotate(n=Count("id")):
            status_counts[row["status"]] = row["n"]
        status_counts["total"] = sum(status_counts.values())

        qs = base_qs
        if params.get("status"):
            qs = qs.filter(status=params["status"])

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
        else:
            serializer = self.get_serializer(qs, many=True)
            response = Response({"results": serializer.data})

        response.data["status_counts"] = status_counts
        return response


# ---------------------------------------------------------------------------
# One application
# ---------------------------------------------------------------------------

class ApplicationDetailView(generics.RetrieveAPIView):
    """
    GET: one application. Visible only to the applicant and the gig's client;
    anyone else gets 404, so the endpoint doesn't reveal that it exists.
    """

    serializer_class = ApplicationDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return (
            Application.objects.filter(Q(freelancer=user) | Q(gig__client=user))
            .select_related(
                "gig",
                "gig__client",
                "freelancer",
                "freelancer__freelancer_profile",
            )
            .prefetch_related(
                "events__changed_by",
                "freelancer__freelancer_profile__skills",
            )
        )


# ---------------------------------------------------------------------------
# Withdraw
# ---------------------------------------------------------------------------

class WithdrawApplicationView(APIView):
    """
    POST: the applicant withdraws their own application.
    Illegal transitions (e.g. already accepted or withdrawn) -> 400.
    """

    permission_classes = [IsAuthenticated, IsFreelancer]
    REASON_MAX_LENGTH = 500

    @classmethod
    def _reason(cls, request):
        """The optional reason, as trimmed text. Anything that isn't a string is ignored."""
        data = request.data
        reason = data.get("reason", "") if hasattr(data, "get") else ""
        if not isinstance(reason, str):
            return ""
        return reason.strip()[: cls.REASON_MAX_LENGTH]

    def post(self, request, application_id):
        with transaction.atomic():
            # Lock the row so two withdraws can't both pass the transition check
            application = get_object_or_404(
                Application.objects.select_for_update(),
                pk=application_id,
                freelancer=request.user,
            )

            try:
                application.change_status(
                    Status.WITHDRAWN,
                    actor=Actor.FREELANCER,
                    changed_by=request.user,
                    note=self._reason(request),
                )
            except InvalidTransition:
                raise ApplicationRuleError(
                    "An application can only be withdrawn while it is pending or under review.",
                    code="invalid_transition",
                )

        out = ApplicationDetailSerializer(application, context={"request": request})
        return Response(out.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Client review
# ---------------------------------------------------------------------------

class ApplicationStatusView(APIView):
    """
    PATCH: the gig's client moves an application along the allowed transitions.

    Hiring also moves an open gig to in_progress, in the same transaction. Other
    applications are left alone: the client rejects them when ready. Anyone who
    isn't the gig's client gets 404, so the endpoint doesn't reveal the application.
    """

    permission_classes = [IsAuthenticated, IsClientRole]
    http_method_names = ["patch", "options"]

    def patch(self, request, application_id):
        body = ApplicationStatusUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        new_status = body.validated_data["status"]
        note = body.validated_data.get("note", "").strip()

        application = get_object_or_404(
            Application.objects.select_related(
                "gig", "gig__client", "freelancer", "freelancer__freelancer_profile"
            ),
            pk=application_id,
            gig__client=request.user,
        )

        with transaction.atomic():
            # Lock the gig so two decisions on the same gig are handled one at a time.
            gig = Gig.objects.select_for_update().get(pk=application.gig_id)
            application.gig = gig

            hiring = new_status == Status.HIRED
            if hiring:
                if gig.status not in (Gig.Status.OPEN, Gig.Status.IN_PROGRESS):
                    raise ApplicationRuleError(
                        "You can only hire for a gig that is open or in progress.",
                        code="gig_not_hireable",
                    )
                already_hired = (
                    Application.objects.filter(gig=gig, status=Status.HIRED)
                    .exclude(pk=application.pk)
                    .exists()
                )
                if already_hired:
                    raise ApplicationRuleError(
                        "You have already hired someone for this gig.", code="already_hired"
                    )

            try:
                application.change_status(
                    new_status, actor=Actor.CLIENT, changed_by=request.user, note=note
                )
            except InvalidTransition:
                current = Status(application.status).label.lower()
                raise ApplicationRuleError(
                    f"An application that is {current} cannot be moved to {Status(new_status).label.lower()}.",
                    code="invalid_transition",
                )
            except IntegrityError:
                # The one-hired-per-gig constraint, if the check above was somehow beaten.
                raise ApplicationRuleError(
                    "You have already hired someone for this gig.", code="already_hired"
                )

            if hiring and gig.status == Gig.Status.OPEN:
                gig.status = Gig.Status.IN_PROGRESS
                gig.save(update_fields=["status", "updated_at"])

        out = ApplicationDetailSerializer(application, context={"request": request})
        return Response(out.data, status=status.HTTP_200_OK)