"""
"Invite to apply" and "Suggested for this gig", the two ways a client reaches out from one of their open gigs.

Inviting sends the freelancer a notification (and an email, by their "Invitations to apply" setting) with a link to
the gig. One invite per freelancer per gig, and a client can send 20 in any 24 hours. It does not open a chat: chat
still starts when someone is hired, with the client writing first.

Suggestions use the content model only: the cosine similarity between the gig's text and each freelancer's profile,
the same score and labels a client sees on applicant cards. The collaborative model isn't used here on purpose. It
learns which gigs a freelancer goes for from what freelancers did; it has no view of which freelancers a client
wants, an open gig that is new has no history for it to work from, and ranking people by how much they resemble past
applicants would only push forward those who are already busy.
"""

from datetime import date, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from applications.models import Application
from notifications.models import Notification
from notifications.service import notify
from profiles.search import card, findable_freelancers
from recommendations import content, registry
from recommendations.bands import match_band

from .models import Gig, GigInvite


class InviteError(ValueError):
    """The invitation isn't allowed. `status` is the HTTP status the view answers with."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def takes_invites(gig):
    """An open gig that freelancers can still see and apply to."""
    return gig.status == Gig.Status.OPEN and not gig.is_removed and gig.application_deadline >= date.today()


def invites_left(client, now=None):
    since = (now or timezone.now()) - timedelta(hours=24)
    used = GigInvite.objects.filter(client=client, created_at__gte=since).count()
    return max(0, settings.INVITES_PER_DAY - used)


def invite(client, gig, freelancer_id):
    """Invite one freelancer to apply to the client's gig. Returns the GigInvite."""
    if gig.client_id != client.pk:
        raise InviteError('You can only invite freelancers to your own gigs.', status=404)
    if not takes_invites(gig):
        raise InviteError('Only open gigs can take invitations.')
    profile = findable_freelancers().filter(user_id=freelancer_id).select_related('user').first()
    if profile is None:
        raise InviteError("This freelancer can't be invited.", status=404)
    freelancer = profile.user
    if Application.objects.filter(gig=gig, freelancer=freelancer).exists():
        raise InviteError(f'{freelancer.full_name} has already applied to this gig.')
    if GigInvite.objects.filter(gig=gig, freelancer=freelancer).exists():
        raise InviteError(f'You have already invited {freelancer.full_name} to this gig.')
    if invites_left(client) <= 0:
        raise InviteError(
            f'You can send {settings.INVITES_PER_DAY} invitations a day. Try again tomorrow.', status=429,
        )

    try:
        with transaction.atomic():
            row = GigInvite.objects.create(gig=gig, client=client, freelancer=freelancer)
            notify(
                freelancer, Notification.Kind.GIG_INVITE,
                f'{client.full_name} invited you to apply for "{gig.title}"',
                f'{client.full_name} thinks you could be a good fit for "{gig.title}" and invited you to apply.',
                link=f'/gigs/{gig.pk}', email_preference='invite_email', inapp_preference='invite_inapp',
            )
    except IntegrityError as error:  # two clicks at once
        raise InviteError(f'You have already invited {freelancer.full_name} to this gig.') from error
    return row


def invitable_gigs(client, freelancer_id):
    """The client's open gigs, each with whether this freelancer was already invited or has applied."""
    gigs = [gig for gig in Gig.objects.filter(client=client, status=Gig.Status.OPEN).order_by('-created_at')
            if takes_invites(gig)]
    invited = set(GigInvite.objects.filter(gig__in=gigs, freelancer_id=freelancer_id).values_list('gig_id', flat=True))
    applied = set(
        Application.objects.filter(gig__in=gigs, freelancer_id=freelancer_id).values_list('gig_id', flat=True)
    )
    return [
        {'id': str(gig.pk), 'title': gig.title, 'invited': gig.pk in invited, 'applied': gig.pk in applied}
        for gig in gigs
    ]


def suggested_freelancers(gig, request=None, limit=None):
    """
    Up to `limit` findable freelancers for an open gig, best content score first, as (cards, availability). People
    who already applied are left out; someone already invited stays, marked `invited`. Nobody with a score of 0 is
    suggested, and with no trained model there are no suggestions, with the reason.
    """
    limit = limit or settings.SUGGESTED_FREELANCERS
    availability = registry.availability()
    info = {'available': availability.available, 'reason': availability.reason or None}
    if not availability.available:
        return [], info
    if not takes_invites(gig):
        return [], {'available': False, 'reason': 'gig_not_open'}

    applied = Application.objects.filter(gig=gig).values('freelancer_id')
    profiles = list(
        findable_freelancers().exclude(user_id__in=applied).select_related('user').prefetch_related('skills')
    )
    matches = content.score_applicants(availability.model.vectoriser, gig, profiles)
    by_user = {str(profile.user_id): profile for profile in profiles}
    best = sorted(
        ((match.score, str(user_id)) for user_id, match in matches.items() if match.score > 0), reverse=True,
    )[:limit]
    chosen = [user_id for _, user_id in best]

    completed = dict(
        Application.objects.filter(
            freelancer_id__in=chosen, status=Application.Status.HIRED, gig__status=Gig.Status.COMPLETED,
        ).values_list('freelancer_id').annotate(n=Count('id'))
    )
    invited = set(GigInvite.objects.filter(gig=gig, freelancer_id__in=chosen).values_list('freelancer_id', flat=True))
    cards = []
    for score, user_id in best:
        profile = by_user[user_id]
        match = matches[profile.user_id]
        cards.append({
            **card(profile, request, gigs_completed=completed.get(profile.user_id, 0)),
            'match_score': round(score, 4),
            'match_reasons': match.match_reasons,
            'match_band': match_band(score, match.match_reasons),
            'invited': profile.user_id in invited,
        })
    return cards, info
