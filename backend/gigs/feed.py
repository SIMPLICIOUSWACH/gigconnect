from datetime import date

from django.conf import settings

from accounts.models import User

from .models import Gig


def apply_feed_rules(queryset, include_closed=False):
    """
    The rules for which gigs a visitor is shown: open gigs whose application deadline has not
    passed, and no synthetic gigs unless SHOW_SYNTHETIC is on. include_closed lifts the first rule.
    Gigs an admin removed, and gigs whose client is suspended, are never shown.

    The public feed and the recommender both call this, so a gig that is not in the feed can never
    be recommended.
    """
    queryset = queryset.filter(
        moderation_status=Gig.Moderation.VISIBLE, client__account_status=User.AccountStatus.ACTIVE,
    )
    if not include_closed:
        queryset = queryset.filter(status=Gig.Status.OPEN, application_deadline__gte=date.today())
    if not settings.SHOW_SYNTHETIC:
        queryset = queryset.filter(is_synthetic=False)
    return queryset


def hidden_from(gig, user):
    """
    True if this gig, reached directly by its ID, should look like it doesn't exist to `user`: it was removed or its
    client is suspended. Its owner and admins still see it.
    """
    if not gig.is_removed and not gig.client.is_suspended:
        return False
    if user.is_authenticated and (user.pk == gig.client_id or user.role == User.Role.ADMIN):
        return False
    return True
