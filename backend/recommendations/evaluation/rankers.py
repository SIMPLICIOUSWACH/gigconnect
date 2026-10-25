"""
Putting a freelancer's candidate gigs in order: by a model's score, at random, or by popularity.

These are plain functions of ids, scores and counts with no model or database access, so each can be checked
on a few gigs by hand.

Every method is ranked over the same candidates, and equal scores are broken the same way for all of them: by
a hash of the seed and the gig id. Nothing here favours newer gigs, as the live feed does when scores are equal,
so a method cannot get ahead just because of how ties fall. A gig with no score (None, which is different
from 0) goes after every gig that has one, in the same hashed order.
"""

import random
from collections import defaultdict

from .split import tie_key


def order_by_score(scores, seed=42):
    """The gig ids best first. scores is {gig id: score or None}."""
    scored = [(gig_id, score) for gig_id, score in scores.items() if score is not None]
    unscored = [gig_id for gig_id, score in scores.items() if score is None]
    scored.sort(key=lambda item: (-item[1], tie_key(seed, item[0])))
    unscored.sort(key=lambda gig_id: tie_key(seed, gig_id))
    return [gig_id for gig_id, _ in scored] + unscored


def random_order(gig_ids, seed, freelancer_id):
    """
    The gig ids in a random order that depends only on the seed and the freelancer, not on the order they are
    given in, so the same seed always gives the same ranking.
    """
    ordered = sorted(gig_ids, key=str)
    random.Random(f'{seed}|{freelancer_id}').shuffle(ordered)
    return ordered


def popularity_counts(positives):
    """
    {gig id: how many different freelancers applied to it}, from the positives it is given (the train part of
    a split). A freelancer counts once for a gig.
    """
    people = defaultdict(set)
    for positive in positives:
        people[positive.gig_id].add(positive.freelancer_id)
    return {gig_id: len(found) for gig_id, found in people.items()}


def popularity_order(gig_ids, counts, seed=42):
    """The gig ids by how many applied in train, most first. A gig nobody applied to has a count of 0."""
    return order_by_score({gig_id: float(counts.get(gig_id, 0)) for gig_id in gig_ids}, seed=seed)
