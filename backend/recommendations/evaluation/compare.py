"""
Comparing the methods on one held-out part of a split.

For every freelancer who has positives in the part, each method puts the same candidate gigs in order, and the
metrics are worked out against the gigs they really applied to in that part. The methods:

- random: shuffled with a fixed seed, repeated for many seeds. The average over seeds is the baseline and the
  spread across seeds says how much luck alone can move a result.
- popularity: the gigs most freelancers applied to in the train part.
- content: the content model alone.
- collaborative on applications only: the proposal's reading, trained on train applications and their statuses.
- collaborative on all interactions: as built, trained on applications plus views, clicks and saves.
- hybrid: the live blend at the current settings (the collaborative part uses all interactions).

All of them see the same candidates, the same models are fitted on the train part only, and ties are broken the
same way for every method (see rankers.py). The collaborative models can only score gigs and freelancers they were
trained on, and the share of candidates and of the right answers they can score is reported next to them, because
a gig the model cannot score goes to the back of its list.

Freelancers still in cold start (too few different gigs in their training data for the collaborative part to
count) are reported apart from the rest. The hybrid is content only for them.

Relevance is binary: the gig was applied to. With strict=True only gigs the freelancer was shortlisted or hired
for count as relevant, and the candidates stay the same.

Nothing here reads the test part unless it is asked for by name. Tuning must use validation only.
"""

from dataclasses import dataclass, field
from statistics import median

import numpy as np

from . import metrics, rankers
from .candidates import candidates_for, load_gig_records
from .fitting import Scorer, fit_models
from .split import TEST, TRAIN, VALIDATION

METHODS = (
    'random', 'popularity', 'content', 'collaborative_applications', 'collaborative_all', 'hybrid',
)
GROUPS = ('all', 'cold_start', 'not_cold_start')
DEFAULT_KS = (5, 10, 20)
DEFAULT_RANDOM_SEEDS = 20
COLLABORATIVE_METHODS = ('collaborative_applications', 'collaborative_all')


@dataclass
class Case:
    """One freelancer in the part being scored."""

    freelancer_id: object
    candidates: list
    relevant: set
    cold_start: bool = False
    scorable: bool = True
    outside_the_rules: int = 0


@dataclass(frozen=True)
class SeedSpread:
    sd: float  # the standard deviation of the average across seeds
    low: float
    high: float


@dataclass
class MethodResult:
    method: str
    available: bool = True
    note: str = ''
    groups: dict = field(default_factory=dict)  # group -> {(k, metric): Summary}
    coverage: float = None  # the average share of a freelancer's candidates the model could score
    relevant_coverage: float = None  # the average share of their right answers it could score
    spread: dict = field(default_factory=dict)  # random only: {(k, metric): SeedSpread}


@dataclass
class Comparison:
    part: str
    strict: bool
    ks: tuple
    random_seeds: int
    results: dict  # method -> MethodResult
    group_sizes: dict  # group -> freelancers it is over
    info: dict  # counts and notes the report quotes next to the numbers


def build_cases(split, part, models, include_synthetic=True, strict=False):
    """The freelancers to score in this part, with their candidates and right answers."""
    if part not in (VALIDATION, TEST):
        raise ValueError('Only the validation and test parts are scored.')
    gigs = load_gig_records(include_synthetic)
    cases = []
    for freelancer_id in sorted(split.evaluated_freelancers(), key=str):
        candidates, outside = candidates_for(split, freelancer_id, part, gigs)
        positives = split.by_freelancer()[freelancer_id][part]
        relevant = {p.gig_id for p in positives if p.strictly_relevant or not strict}
        cases.append(Case(
            freelancer_id=freelancer_id, candidates=candidates, relevant=relevant,
            outside_the_rules=len(outside),
        ))
    return cases


def group_members(cases):
    """The freelancers in each group, counting only those with something to find."""
    with_answers = [case for case in cases if case.relevant]
    return {
        'all': with_answers,
        'cold_start': [case for case in with_answers if case.cold_start],
        'not_cold_start': [case for case in with_answers if not case.cold_start],
    }


def aggregate(per_freelancer, cases, seed):
    """{group: {(k, metric): Summary}} from {freelancer id: {(k, metric): value} or None}."""
    result = {}
    for name, members in group_members(cases).items():
        chosen = {case.freelancer_id: per_freelancer.get(case.freelancer_id) for case in members}
        result[name] = metrics.summarise_all(chosen, seed=seed)
    return result


def score_rankings(rankings, cases, ks):
    """{freelancer id: {(k, metric): value} or None} for one method's rankings."""
    return {
        case.freelancer_id: metrics.freelancer_metrics(rankings[case.freelancer_id], case.relevant, ks)
        for case in cases
    }


def random_baseline(cases, ks, seeds, seed):
    """
    The random baseline over many seeds, as a MethodResult. Each freelancer's value is their average over the
    seeds. The spread is how the all-freelancer average moves from seed to seed.
    """
    runs = []
    for run_seed in range(seeds):
        rankings = {
            case.freelancer_id: rankers.random_order(case.candidates, run_seed, case.freelancer_id) for case in cases
        }
        runs.append(score_rankings(rankings, cases, ks))

    averaged = {}
    for case in cases:
        values = [run[case.freelancer_id] for run in runs]
        averaged[case.freelancer_id] = (
            None if values[0] is None else {key: float(np.mean([v[key] for v in values])) for key in values[0]}
        )
    result = MethodResult(method='random', groups=aggregate(averaged, cases, seed))

    members = group_members(cases)['all']
    if members:
        for k in ks:
            for name in metrics.METRICS:
                per_seed = [np.mean([run[case.freelancer_id][(k, name)] for case in members]) for run in runs]
                sd = float(np.std(per_seed, ddof=1)) if len(per_seed) > 1 else 0.0
                result.spread[(k, name)] = SeedSpread(sd=sd, low=float(min(per_seed)), high=float(max(per_seed)))
    return result


def collaborative_coverage(cases, raw_scores):
    """
    How much of what a collaborative model was asked about it could score: the average, over freelancers, of the
    share of their candidates with a score and of the share of their right answers with a score.
    """
    candidate_shares, answer_shares = [], []
    for case in cases:
        scores = raw_scores[case.freelancer_id]
        if case.candidates:
            candidate_shares.append(share_scored(case.candidates, scores))
        if case.relevant:
            answer_shares.append(share_scored(case.relevant, scores))
    return average_or_none(candidate_shares), average_or_none(answer_shares)


def share_scored(gig_ids, scores):
    """The share of these gigs that have a score (None means the model has none)."""
    return sum(1 for gig_id in gig_ids if scores.get(gig_id) is not None) / len(gig_ids)


def average_or_none(values):
    return float(np.mean(values)) if values else None


def method_result(method, rankings, cases, ks, seed, **extra):
    """A MethodResult for one method's rankings, with the metrics for each group of freelancers."""
    return MethodResult(
        method=method, groups=aggregate(score_rankings(rankings, cases, ks), cases, seed), **extra,
    )


def compare(
    split, part=VALIDATION, include_synthetic=True, ks=DEFAULT_KS, random_seeds=DEFAULT_RANDOM_SEEDS,
    strict=False, data_dir=None, models=None, seed=42,
):
    """
    Fit the models on the train part (or use `models` if they are given) and compare every method on `part`.
    Returns a Comparison. Pass part=TEST only for the final run: tuning must never look at it.
    """
    if random_seeds < 1:
        raise ValueError('The random baseline needs at least one seed.')
    models = models or fit_models(split, include_synthetic, data_dir)
    scorer = Scorer(models, include_synthetic)
    cases = build_cases(split, part, models, include_synthetic, strict)
    for case in cases:
        case.cold_start = scorer.in_cold_start(case.freelancer_id)
        case.scorable = scorer.scorable(case.freelancer_id)

    results = {'random': random_baseline(cases, ks, random_seeds, seed)}

    counts = rankers.popularity_counts(split.in_part(TRAIN))
    popularity = {case.freelancer_id: rankers.popularity_order(case.candidates, counts, seed) for case in cases}
    results['popularity'] = method_result('popularity', popularity, cases, ks, seed)

    ranked = {
        case.freelancer_id: rankers.order_by_score(scorer.content_scores(case.freelancer_id, case.candidates), seed)
        for case in cases
    }
    results['content'] = method_result('content', ranked, cases, ks, seed)

    for method, attribute, name in (
        ('collaborative_applications', 'collaborative_applications', 'applications'),
        ('collaborative_all', 'collaborative_all', 'all'),
    ):
        model = getattr(models, attribute)
        if model is None:
            results[method] = MethodResult(method=method, available=False, note=models.skipped.get(name, ''))
            continue
        raw = {
            case.freelancer_id: scorer.collaborative_scores(model, case.freelancer_id, case.candidates)
            for case in cases
        }
        ranked = {case.freelancer_id: rankers.order_by_score(raw[case.freelancer_id], seed) for case in cases}
        coverage, relevant_coverage = collaborative_coverage(cases, raw)
        results[method] = method_result(
            method, ranked, cases, ks, seed, coverage=coverage, relevant_coverage=relevant_coverage,
        )

    ranked = {
        case.freelancer_id: rankers.order_by_score(scorer.hybrid_scores(case.freelancer_id, case.candidates), seed)
        for case in cases
    }
    results['hybrid'] = method_result('hybrid', ranked, cases, ks, seed)

    members = group_members(cases)
    sizes = [len(case.candidates) for case in cases]
    positives = [p for case in cases for p in split.by_freelancer()[case.freelancer_id][part]]
    info = {
        'freelancers_in_part': len(cases),
        'unscorable_freelancers': sum(1 for case in cases if not case.scorable),
        'candidates': {'smallest': min(sizes), 'median': median(sizes), 'largest': max(sizes)} if sizes else {},
        'positives': len(positives),
        'synthetic_positives': sum(1 for p in positives if p.is_synthetic),
        'relevant': sum(len(case.relevant) for case in cases),
        'outside_the_rules': sum(case.outside_the_rules for case in cases),
        'models': models.stats,
        'skipped': dict(models.skipped),
        'seed': seed,
        'include_synthetic': include_synthetic,
    }
    return Comparison(
        part=part, strict=strict, ks=tuple(ks), random_seeds=random_seeds, results=results,
        group_sizes={name: len(found) for name, found in members.items()}, info=info,
    )
