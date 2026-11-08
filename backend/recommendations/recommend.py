"""
Recommending gigs to a freelancer with a loaded model: content scores, blended with collaborative scores
once the freelancer has enough history.

For each gig the freelancer could apply to, the content score always exists. The collaborative score exists
only if the model was fitted, the freelancer is in it, and the gig is in it. A gig posted after training is
scored on its text with the saved vectoriser straight away, and has no collaborative score until the next
training run.

Only the candidates' ids and `updated_at` are read from the database. What the content model needs from each gig
comes from the loaded model's gig cache (gig_cache.py), so the cost of a request does not grow with loading and
cleaning every candidate. The gigs themselves are loaded afterwards, only for the results that are shown
(attach_gigs).
"""

from dataclasses import dataclass, field

from django.db.models import QuerySet

from applications.models import Application
from gigs.models import Gig, GigInteraction
from profiles.models import FreelancerProfile

from . import collaborative as collab
from . import hybrid
from .candidates import candidate_gigs
from .features import freelancer_document, skill_token
from .gig_cache import content_scores, shared_skills


@dataclass
class Recommendation:
    gig_id: object
    created_at: object  # when the gig was posted, which orders equal scores
    score: float
    source: str  # 'content' or 'hybrid'
    match_reasons: list
    content_score: float
    collaborative_score: float = None  # on the 0 to 1 scale, or None if there is none
    gig: object = None  # the Gig, attached only for results that are shown (see attach_gigs)


@dataclass
class Recommendations:
    results: list = field(default_factory=list)
    cold_start: bool = True
    weight: float = 0.0
    gigs_interacted_with: int = 0
    # False when the freelancer has no skills and no bio, so there is nothing to compare gigs with.
    scorable: bool = True


def gigs_interacted_with(user):
    """
    How many different gigs this freelancer has interacted with, counting their applications too. Rating a
    recommended gig as relevant or not does not count, so answering the question never changes the blend.
    """
    interacted = set(
        GigInteraction.objects.filter(user=user).exclude(type__in=GigInteraction.RELEVANCE_TYPES)
        .values_list('gig_id', flat=True)
    ) | set(Application.objects.filter(freelancer=user).values_list('gig_id', flat=True))
    return len(interacted)


def candidate_rows(candidates):
    """[(gig id, updated_at), ...] for a queryset of gigs (one small query) or a list of Gig objects."""
    if isinstance(candidates, QuerySet):
        return list(candidates.values_list('id', 'updated_at'))
    return [(gig.id, gig.updated_at) for gig in candidates]


def recommend(model, user, candidates=None):
    """
    Every gig the freelancer could apply to, best first. candidates can be given to score a particular set: a
    queryset of gigs or a list of them.

    A freelancer with no skills and no bio cannot be compared with any gig, so they get nothing back. The results
    carry gig ids; call attach_gigs for the ones to show.
    """
    profile = FreelancerProfile.objects.prefetch_related('skills').get(user=user)
    skill_names = [skill.name for skill in profile.skills.all()]
    freelancer_text = freelancer_document(skill_names, profile.bio)
    scorable = bool(freelancer_text)

    history = gigs_interacted_with(user)
    weight = hybrid.blend_weight(history)
    results = []
    if scorable:
        candidates = candidate_gigs(user) if candidates is None else candidates
        entries = model.gig_cache.entries(candidate_rows(candidates))
        gig_ids = list(entries)
        contents = content_scores(model.gig_cache, freelancer_text, [entries[gig_id] for gig_id in gig_ids])
        raw_scores = {}
        if model.collaborative is not None and weight > 0:
            raw_scores = collab.score(model.collaborative, user.id, gig_ids)
        mine = {skill_token(name) for name in skill_names}
        for gig_id, content_score in zip(gig_ids, contents):
            content_score = float(content_score)
            collaborative_score = hybrid.normalise_collaborative(
                raw_scores.get(gig_id), model.collaborative.scale if model.collaborative else None,
            )
            score, source = hybrid.hybrid_score(content_score, collaborative_score, weight)
            results.append(Recommendation(
                gig_id=gig_id, created_at=entries[gig_id].created_at, score=score, source=source,
                match_reasons=shared_skills(mine, entries[gig_id]), content_score=content_score,
                collaborative_score=collaborative_score,
            ))
        # Equal scores are ordered newest first, then by id, so the order never changes between requests.
        results.sort(key=lambda r: (-r.score, -r.created_at.timestamp(), str(r.gig_id)))
    return Recommendations(
        results=results, cold_start=hybrid.in_cold_start(history), weight=weight,
        gigs_interacted_with=history, scorable=scorable,
    )


def attach_gigs(recommendations):
    """Load the gigs of these results in one go (with what the gig card shows) and attach them. Returns the list."""
    recommendations = list(recommendations)
    wanted = [r.gig_id for r in recommendations if r.gig is None]
    if wanted:
        gigs = Gig.objects.select_related('client', 'category').prefetch_related('skills').in_bulk(wanted)
        for recommendation in recommendations:
            if recommendation.gig is None:
                recommendation.gig = gigs.get(recommendation.gig_id)
    return recommendations
