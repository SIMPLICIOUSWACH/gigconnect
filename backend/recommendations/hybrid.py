"""
Combining the content score and the collaborative score into one.

    hybrid = w * collaborative + (1 - w) * content

Everything here is a pure function with no database or file access, and `w` is always passed in, so
Sprint 6 can tune it on a validation split without touching the scoring.

Both scores are put on the same fixed 0 to 1 scale before they are blended. The content score is a cosine
similarity, which is already on that scale. The collaborative score is a raw value from the SVD, so it is
divided by a scale fixed at training time (a high percentile of the scores the model gave to gigs people had
not touched) and clipped to 0 to 1. The scale is fixed, not worked out from whichever gigs are being scored,
so the same freelancer and gig always get the same score.

Cold start: a freelancer with little history gives the collaborative model little to go on. Below
RECOMMENDER_COLD_START_MIN_GIGS different gigs they get content scores only. From there the weight w ramps up
linearly over the next RECOMMENDER_BLEND_RAMP_GIGS gigs to RECOMMENDER_BLEND_MAX_WEIGHT.
"""

import numpy as np
from django.conf import settings

CONTENT = 'content'
HYBRID = 'hybrid'


def normalise_collaborative(raw, scale):
    """A raw collaborative score on the 0 to 1 scale, or None when there is no collaborative score."""
    if raw is None or scale is None or scale <= 0:
        return None
    return float(min(1.0, max(0.0, raw / scale)))


def unseen_positive_scores(reconstructed, observed_mask):
    """
    The positive raw scores the model gave to gigs a freelancer has not interacted with. These are the
    scores it produces when it recommends, so they are the ones the scale is taken from. Works on a block
    of the matrix, so a big matrix can be handled a piece at a time.
    """
    unseen = reconstructed[~observed_mask]
    return unseen[unseen > 0]


def scale_from_scores(positive_scores, percentile=95):
    """The raw score that counts as 1.0: a high percentile of the positive scores, or None if there are none."""
    if positive_scores.size == 0:
        return None
    return float(np.percentile(positive_scores, percentile))


def collaborative_scale(reconstructed, observed_mask, percentile=95):
    """The scale for a whole matrix at once: reconstructed holds the raw scores, observed_mask the cells touched."""
    return scale_from_scores(unseen_positive_scores(reconstructed, observed_mask), percentile)


def blend_weight(gigs_interacted_with):
    """
    The weight w on the collaborative score for a freelancer who has interacted with this many different
    gigs: 0 in cold start, then rising by equal steps to the maximum.
    """
    minimum = settings.RECOMMENDER_COLD_START_MIN_GIGS
    if gigs_interacted_with < minimum:
        return 0.0
    ramp = max(1, settings.RECOMMENDER_BLEND_RAMP_GIGS)
    steps_in = gigs_interacted_with - minimum + 1
    return float(settings.RECOMMENDER_BLEND_MAX_WEIGHT * min(1.0, steps_in / ramp))


def in_cold_start(gigs_interacted_with):
    return gigs_interacted_with < settings.RECOMMENDER_COLD_START_MIN_GIGS


def hybrid_score(content_score, collaborative_score, weight):
    """
    The blended score and where it came from, as (score, source).

    With no collaborative score (a new gig, a new freelancer, no model) or a weight of 0 (cold start), the
    score is the content score and the source is 'content'. Otherwise it is the blend and the source is
    'hybrid'.
    """
    if collaborative_score is None or weight <= 0:
        return content_score, CONTENT
    return weight * collaborative_score + (1 - weight) * content_score, HYBRID
