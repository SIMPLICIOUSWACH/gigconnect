from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Gig, GigInteraction

VIEW_DEDUPE_WINDOW = timedelta(hours=24)


def viewer_identity(request):
    """Who is acting: the user if signed in, otherwise the visitor's session."""
    if request.user.is_authenticated:
        return {'user': request.user, 'session_key': ''}
    if not request.session.session_key:
        request.session.create()
    return {'user': None, 'session_key': request.session.session_key}


def record_view_if_new(request, gig):
    """Count and log a view unless it should not count. Returns True if it was counted.

    A view is counted at most once per viewer (user, or session for anonymous visitors) per
    gig per 24 hours, and never when the gig's own client is looking at it. The `view`
    interaction row is both the log entry and the record the next request dedupes against.
    """
    if request.user.is_authenticated and gig.client_id == request.user.id:
        return False

    identity = viewer_identity(request)
    if identity['user']:
        same_viewer = {'user': identity['user']}
    else:
        same_viewer = {'user__isnull': True, 'session_key': identity['session_key']}
    recent = GigInteraction.objects.filter(
        gig=gig,
        type=GigInteraction.Type.VIEW,
        created_at__gte=timezone.now() - VIEW_DEDUPE_WINDOW,
        **same_viewer,
    )

    with transaction.atomic():
        # Lock the gig row so two simultaneous requests from one viewer (a page that fetches
        # twice) can't both pass the check below and both count.
        Gig.objects.select_for_update().get(pk=gig.pk)
        if recent.exists():
            return False
        GigInteraction.objects.create(gig=gig, type=GigInteraction.Type.VIEW, **identity)
        return True
