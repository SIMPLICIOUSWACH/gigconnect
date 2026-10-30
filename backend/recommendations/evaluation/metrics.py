"""
Ranking metrics: Precision@K, Recall@K, F1@K and hit rate@K, averaged over freelancers.

Each function takes a ranked list of gig ids (best first) and the set of gig ids that were relevant to one
freelancer, and has no database or model access, so it can be checked against small cases worked out by hand.

The definitions, so that no number is read another way:

- Precision@K is the relevant gigs in the first K, divided by K. If a freelancer has fewer than K candidates
  the divisor is still K, so a short list cannot score 1. Every method is ranked over the same candidates, so
  this never changes which method is ahead.
- Recall@K is the relevant gigs in the first K, divided by all the relevant gigs.
- F1@K is the harmonic mean of the two for that freelancer, and 0 when both are 0. It is worked out for each
  freelancer and then averaged, not worked out from the averaged precision and recall.
- Hit rate@K is 1 if at least one relevant gig is in the first K and 0 if not, averaged: the share of
  freelancers who got at least one right answer.

A freelancer with no relevant gigs has no answer to find. Their recall is undefined, so `freelancer_metrics`
leaves them out for every metric and they are not counted in the number of freelancers behind an average.

Averages come with a 95% bootstrap interval over freelancers: the freelancers are resampled with replacement
many times and the interval is the middle 95% of the resampled means. It says how much the average could move
with a different set of freelancers. With few freelancers it is wide, and that is the honest answer.
"""

from dataclasses import dataclass

import numpy as np

METRICS = ('precision', 'recall', 'f1', 'hit')


def hits_in_top_k(ranked, relevant, k):
    """How many of the first k ranked gigs are relevant."""
    return sum(1 for gig_id in list(ranked)[:k] if gig_id in relevant)


def precision_at_k(ranked, relevant, k):
    return hits_in_top_k(ranked, relevant, k) / k


def recall_at_k(ranked, relevant, k):
    """The share of the relevant gigs found in the first k, or None when there are none to find."""
    if not relevant:
        return None
    return hits_in_top_k(ranked, relevant, k) / len(relevant)


def f1_at_k(ranked, relevant, k):
    recall = recall_at_k(ranked, relevant, k)
    if recall is None:
        return None
    precision = precision_at_k(ranked, relevant, k)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def hit_at_k(ranked, relevant, k):
    if not relevant:
        return None
    return 1.0 if hits_in_top_k(ranked, relevant, k) > 0 else 0.0


def freelancer_metrics(ranked, relevant, ks):
    """
    All the metrics for one freelancer as {(k, metric name): value}, or None if they have nothing relevant.
    """
    if not relevant:
        return None
    functions = {'precision': precision_at_k, 'recall': recall_at_k, 'f1': f1_at_k, 'hit': hit_at_k}
    return {(k, name): function(ranked, relevant, k) for k in ks for name, function in functions.items()}


@dataclass(frozen=True)
class Summary:
    mean: float
    low: float  # the lower end of the 95% bootstrap interval
    high: float
    n: int  # the freelancers the average is over


def bootstrap_interval(values, seed=42, resamples=2000, level=0.95):
    """
    The (low, high) ends of the bootstrap interval for the mean of these values. Fixed seed, so the same values
    always give the same interval. One value has no spread to resample, so its interval is just that value.
    """
    values = np.asarray(list(values), dtype=float)
    if values.size == 0:
        raise ValueError('There are no values to take an interval of.')
    if values.size == 1:
        return float(values[0]), float(values[0])
    rng = np.random.RandomState(seed)
    picks = rng.randint(0, values.size, size=(resamples, values.size))
    means = values[picks].mean(axis=1)
    tail = (1 - level) / 2 * 100
    low, high = np.percentile(means, [tail, 100 - tail])
    return float(low), float(high)


def summarise(values, seed=42, resamples=2000):
    """The mean of the values, its bootstrap interval and how many values it is over. None if there are none."""
    values = list(values)
    if not values:
        return None
    low, high = bootstrap_interval(values, seed=seed, resamples=resamples)
    return Summary(mean=float(np.mean(values)), low=low, high=high, n=len(values))


def summarise_all(per_freelancer, seed=42, resamples=2000):
    """
    Average a set of freelancers' metrics. per_freelancer is {freelancer: {(k, metric): value}} (freelancers
    with None are left out). Returns {(k, metric): Summary}.
    """
    kept = [values for values in per_freelancer.values() if values is not None]
    if not kept:
        return {}
    return {key: summarise([values[key] for values in kept], seed=seed, resamples=resamples) for key in kept[0]}
