"""
Recommending gigs to a freelancer with a loaded model: content scores, blended with collaborative scores
once the freelancer has enough history.

For each gig the freelancer could apply to, the content score always exists. The collaborative score exists
only if the model was fitted, the freelancer is in it, and the gig is in it. A gig posted after training is
scored on its text with the saved vectoriser straight away, and has no collaborative score until the next
training run.
"""

from dataclasses import dataclass, field

from applications.models import Application
from gigs.models import GigInteraction
from profiles.models import FreelancerProfile

from . import collaborative as collab
from . import content, hybrid
from .candidates import candidate_gigs
from .features import freelancer_document


@dataclass
class Recommendation:
    gig: object
    score: float
    source: str  # 'content' or 'hybrid'
    match_reasons: list
    content_score: float
    collaborative_score: float = None  # on the 0 to 1 scale, or None if there is none


@dataclass
class Recommendations:
    results: list = field(default_factory=list)
    cold_start: bool = True
    weight: float = 0.0
    gigs_interacted_with: int = 0
    # False when the freelancer has no skills and no bio, so there is nothing to compare gigs with.
    scorable: bool = True


def gigs_interacted_with(user):
    """How many different gigs this freelancer has interacted with, counting their applications too."""
    interacted = set(
        GigInteraction.objects.filter(user=user).values_list('gig_id', flat=True)
    ) | set(Application.objects.filter(freelancer=user).values_list('gig_id', flat=True))
    return len(interacted)


def recommend(model, user, candidates=None):
    """
    Every gig the freelancer could apply to, best first. candidates can be given to score a particular set.

    A freelancer with no skills and no bio cannot be compared with any gig, so they get nothing back.
    """
    profile = FreelancerProfile.objects.prefetch_related('skills').get(user=user)
    candidates = candidate_gigs(user) if candidates is None else candidates
    matches = content.rank_for_freelancer(model.vectoriser, profile, candidates)
    scorable = bool(freelancer_document([skill.name for skill in profile.skills.all()], profile.bio))

    history = gigs_interacted_with(user)
    weight = hybrid.blend_weight(history)
    raw_scores = {}
    if model.collaborative is not None and weight > 0:
        raw_scores = collab.score(model.collaborative, user.id, [match.gig.id for match in matches])

    results = []
    for match in matches:
        collaborative_score = hybrid.normalise_collaborative(
            raw_scores.get(match.gig.id), model.collaborative.scale if model.collaborative else None,
        )
        score, source = hybrid.hybrid_score(match.score, collaborative_score, weight)
        results.append(Recommendation(
            gig=match.gig, score=score, source=source, match_reasons=match.match_reasons,
            content_score=match.score, collaborative_score=collaborative_score,
        ))
    results.sort(key=lambda r: (-r.score, -r.gig.created_at.timestamp(), str(r.gig.id)))
    return Recommendations(
        results=results, cold_start=hybrid.in_cold_start(history), weight=weight,
        gigs_interacted_with=history, scorable=scorable,
    )
