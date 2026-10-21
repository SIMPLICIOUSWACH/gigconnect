from datetime import date

from django.conf import settings

from .models import Gig


def apply_feed_rules(queryset, include_closed=False):
    """
    The rules for which gigs a visitor is shown: open gigs whose application deadline has not
    passed, and no synthetic gigs unless SHOW_SYNTHETIC is on. include_closed lifts the first rule.

    The public feed and the recommender both call this, so a gig that is not in the feed can never
    be recommended.
    """
    if not include_closed:
        queryset = queryset.filter(status=Gig.Status.OPEN, application_deadline__gte=date.today())
    if not settings.SHOW_SYNTHETIC:
        queryset = queryset.filter(is_synthetic=False)
    return queryset
