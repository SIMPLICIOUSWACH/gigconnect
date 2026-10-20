"""
The skill match score a client sees for each applicant to their gig.

It is the content model's score for that exact freelancer and that exact gig, so it is only given when a
trained model is loaded and recommendations are switched on. Otherwise every applicant gets an empty match
and the response says why. An applicant with no skills and no bio cannot be compared with anything, and also
gets an empty match, not a score of 0.

Only the gig's owner can reach the applicants list, so only the owner ever sees these.
"""

from gigs.models import Gig

from . import content, registry
from .bands import match_band

# What an applicant gets when there is no score for them.
EMPTY_MATCH = {'match_score': None, 'match_reasons': [], 'match_band': None}


def applicant_matches(gig_id, applications):
    """
    The match fields for each applicant, as ({freelancer user id: fields}, availability).

    availability is {'available': bool, 'reason': None, 'disabled' or 'model_unavailable'}, for the response.
    """
    availability = registry.availability()
    info = {'available': availability.available, 'reason': availability.reason or None}
    applications = list(applications)
    if not availability.available or not applications:
        return {}, info

    gig = Gig.objects.select_related('category').prefetch_related('skills').get(pk=gig_id)
    # A deleted account keeps its skills on the profile, but nothing is worked out from a deleted person's
    # data, so they get no score.
    profiles = [
        profile for profile in (
            getattr(a.freelancer, 'freelancer_profile', None) for a in applications if a.freelancer.deleted_at is None
        )
        if profile is not None
    ]
    matches = content.score_applicants(availability.model.vectoriser, gig, profiles)
    fields = {
        user_id: {
            'match_score': round(match.score, 4),
            'match_reasons': match.match_reasons,
            'match_band': match_band(match.score, match.match_reasons),
        }
        for user_id, match in matches.items()
    }
    return fields, info
