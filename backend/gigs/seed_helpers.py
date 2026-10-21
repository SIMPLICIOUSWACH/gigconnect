"""
Helpers shared by the development seed commands (seed_applications and seed_interactions).

Seeded freelancers favour gigs that share a skill with them, so similar freelancers end up with similar
histories. That is made-up behaviour put there so the recommender has a pattern to find. It says nothing
about real freelancers, and the evaluation report states that it favours the content model by construction.
"""

from datetime import datetime, time, timedelta

from django.utils import timezone

# A gig that shares a skill with the freelancer is this many times more likely to be picked than one that
# does not.
SKILL_PREFERENCE = 5


def skill_ids_by_gig(gigs):
    """{gig id: set of its skill ids}. The gigs should have their skills prefetched."""
    return {gig.id: {skill.id for skill in gig.skills.all()} for gig in gigs}


def ordered_by_preference(rng, gigs, gig_skills, own_skills):
    """
    Every gig, in the order a freelancer with these skills would pick them. This is weighted sampling
    without replacement: each gig gets a random key raised to the power 1 / weight, and the largest keys
    come first. Taking the first n gives n different gigs, favouring those that share a skill.
    """
    keyed = []
    # The database returns rows in no fixed order, and that order changes when a row is updated. Random keys
    # handed out in that order would make the same seed give different picks, so go in order of id.
    for gig in sorted(gigs, key=lambda gig: str(gig.id)):
        weight = SKILL_PREFERENCE if own_skills & gig_skills[gig.id] else 1
        keyed.append((rng.random() ** (1 / weight), str(gig.id), gig))
    keyed.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [gig for _, _, gig in keyed]


def room_before_now(gig, now=None):
    """
    How far back from now something can be dated without being dated before the gig existed. Pass the same
    `now` that the date is worked out from, so the two readings of the clock cannot differ.
    """
    return max(timedelta(0), (now or timezone.now()) - gig.created_at)


def application_window_end(gig, now):
    """
    The last moment someone could have applied to the gig: the end of its application deadline day, or now if
    that is later (or there is no deadline). Applications dated after this could not have happened.
    """
    if gig.application_deadline is None:
        return now
    end_of_deadline_day = timezone.make_aware(datetime.combine(gig.application_deadline + timedelta(days=1), time.min))
    return min(now, end_of_deadline_day)
