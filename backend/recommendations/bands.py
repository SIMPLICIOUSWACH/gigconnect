"""
Describing a client's match score in words.

A bare number such as 0.18 looks more precise than a skill-overlap score is, so the API also gives a band.
It is named after what is measured, skill overlap, and it is only given when the freelancer and the gig
really share at least one skill; a score that comes from the wording of a bio alone gets no band.

The cut-offs are settings, fixed from scores measured on the development data (see settings.py), and
provisional until Sprint 6 rechecks them on real data.
"""

from django.conf import settings

STRONG = 'strong'
GOOD = 'good'
SOME = 'some'


def match_band(score, match_reasons):
    """'strong', 'good' or 'some' skill overlap, or None when there is no score or no shared skill."""
    if score is None or not match_reasons:
        return None
    if score >= settings.RECOMMENDER_BAND_STRONG:
        return STRONG
    if score >= settings.RECOMMENDER_BAND_GOOD:
        return GOOD
    return SOME
