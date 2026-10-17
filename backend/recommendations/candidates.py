"""
Which gigs a freelancer could actually apply to, and so which gigs may be recommended.

The rules are the ones the rest of the app already uses, not a copy: the feed's rules for what counts as
an open gig with a live application deadline come from gigs.feed, and the rest mirror the checks in
applications.views.GigApplicationsView (not your own gig, not already applied, not withdrawn). The
tests apply to each kind of gig through the real apply endpoint and check the two agree, so they
cannot drift apart.
"""

from gigs.feed import apply_feed_rules
from gigs.models import Gig


def candidate_gigs(user):
    """Open gigs with a live deadline that this freelancer did not post and has no application to."""
    gigs = apply_feed_rules(Gig.objects.select_related('category').prefetch_related('skills'))
    # Any application at all, whatever its status, rules a gig out: a withdrawn application means the
    # freelancer cannot apply again, so the gig is not something they could act on.
    return gigs.exclude(client=user).exclude(applications__freelancer=user)
