"""
Tuning the hybrid on the validation part, and nothing else.

What is tuned, and the values tried (every combination is run and written down, not only the winner):

- the largest weight on the collaborative score: 0, 0.25, 0.5, 0.75 and 1.0
- how many gigs the weight takes to rise to that largest value (the ramp): 5, 20 and 50
- the number of hidden factors in the collaborative model: 2, 5, 10 and the cap (half the smaller side of the matrix)
- the cold-start threshold, the number of different gigs below which only the content score is used: 0, 3, 5 and 10

That is 5 x 3 x 4 x 4 = 240 combinations. The interaction weights are not tuned: with this little data, changing
four numbers to fit 90 right answers would be overfitting, and the report says so.

The rule is fixed before any result is looked at. A combination is chosen by the average, over freelancers, of F1@5
and F1@10 on the validation part (both are headline figures). The live defaults change only if the best
combination beats the current settings by more than the spread of the random baseline AND by more than the
bootstrap interval, meaning the 95% interval of the paired per-freelancer difference lies wholly above zero.
Picking the best of 240 is optimistic, so a small gain is expected from luck alone, and the rule asks for more.

There is no way to ask this module for the test part. The context is built from the validation part only.
"""

import itertools
from dataclasses import dataclass, field

import numpy as np
from django.conf import settings

from .. import collaborative as collab
from .. import content, hybrid
from . import metrics, rankers
from . import split as ev
from .compare import build_cases
from .fitting import FittedModels, Scorer, fit_models
from .training_input import training_input

CAP = 'cap'  # as many factors as the matrix allows: half its smaller side
UNLIMITED = 10 ** 6  # asking for this many factors gives the cap, because fit() never goes above half the smaller side

MAX_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
RAMPS = (5, 20, 50)
FACTORS = (2, 5, 10, CAP)
COLD_STARTS = (0, 3, 5, 10)

KS = (5, 10, 20)
SELECTION_KS = (5, 10)  # the combination is picked by the mean of F1 at these K


@dataclass(frozen=True)
class Setting:
    max_weight: float
    ramp: int
    factors: object  # an int, or CAP
    cold_start: int


def grid():
    """All 240 combinations, in a fixed order."""
    return [Setting(*values) for values in itertools.product(MAX_WEIGHTS, RAMPS, FACTORS, COLD_STARTS)]


def current_setting():
    """The live settings, as one combination."""
    return Setting(
        max_weight=settings.RECOMMENDER_BLEND_MAX_WEIGHT, ramp=settings.RECOMMENDER_BLEND_RAMP_GIGS,
        factors=settings.RECOMMENDER_SVD_COMPONENTS, cold_start=settings.RECOMMENDER_COLD_START_MIN_GIGS,
    )


@dataclass
class Context:
    """Everything that does not change between combinations, worked out once."""

    cases: list
    models: FittedModels
    scorer: Scorer
    content: dict  # freelancer id -> {gig id: content score or None}
    history: dict  # freelancer id -> different gigs in their training data
    collaborative: dict  # factors value -> fitted model or None
    raw: dict  # factors value -> {freelancer id: {gig id: raw collaborative score or None}}
    seed: int = 42


@dataclass
class Trial:
    setting: Setting
    components: object  # the factors actually used, or None when the collaborative model could not be fitted
    means: dict  # (k, metric) -> mean over freelancers
    selection: float  # mean over freelancers of the mean of F1@5 and F1@10
    per_freelancer: dict = field(repr=False, default_factory=dict)  # freelancer id -> their selection value

    def key(self):
        """The setting with the factors actually used, so CAP and 15 on a matrix capped at 15 are the same."""
        return (self.setting.max_weight, self.setting.ramp, self.components, self.setting.cold_start)


def build_context(split, include_synthetic=True, data_dir=None, seed=42):
    """Fit the models on the train part and score the validation part's candidates. Validation only."""
    models = fit_models(split, include_synthetic, data_dir)
    scorer = Scorer(models, include_synthetic)
    cases = [case for case in build_cases(split, ev.VALIDATION, models, include_synthetic) if case.relevant]
    weights = training_input(split, include_synthetic).weights

    wanted = list(FACTORS)
    if current_setting().factors not in wanted:
        wanted.append(current_setting().factors)
    fitted = {}
    for factors in wanted:
        try:
            fitted[factors] = collab.fit(weights, n_components=UNLIMITED if factors == CAP else factors)
        except collab.NotEnoughData:
            fitted[factors] = None
    raw = {
        factors: {
            case.freelancer_id: scorer.collaborative_scores(model, case.freelancer_id, case.candidates)
            for case in cases
        }
        for factors, model in fitted.items()
    }
    return Context(
        cases=cases, models=models, scorer=scorer,
        content={case.freelancer_id: scorer.content_scores(case.freelancer_id, case.candidates) for case in cases},
        history={case.freelancer_id: models.history.get(case.freelancer_id, 0) for case in cases},
        collaborative=fitted, raw=raw, seed=seed,
    )


def blended_scores(context, setting, case):
    """The hybrid scores of one freelancer's candidates under this combination (the same formula as the live one)."""
    freelancer_id = case.freelancer_id
    content = context.content[freelancer_id]
    model = context.collaborative[setting.factors]
    weight = hybrid.blend_weight(
        context.history[freelancer_id], minimum=setting.cold_start, ramp=setting.ramp, maximum=setting.max_weight,
    )
    if model is None or weight <= 0:
        return content
    raw = context.raw[setting.factors][freelancer_id]
    scores = {}
    for gig_id, content_score in content.items():
        if content_score is None:
            scores[gig_id] = None
            continue
        normalised = hybrid.normalise_collaborative(raw.get(gig_id), model.scale)
        scores[gig_id] = hybrid.hybrid_score(content_score, normalised, weight)[0]
    return scores


def selection_value(values):
    """One freelancer's selection value: the mean of their F1 at each selection K."""
    return float(np.mean([values[(k, 'f1')] for k in SELECTION_KS]))


def run_trial(context, setting):
    """Score the validation part with one combination."""
    per_freelancer = {}
    for case in context.cases:
        ranking = rankers.order_by_score(blended_scores(context, setting, case), context.seed)
        per_freelancer[case.freelancer_id] = metrics.freelancer_metrics(ranking, case.relevant, KS)
    keys = next(iter(per_freelancer.values())).keys()
    means = {key: float(np.mean([values[key] for values in per_freelancer.values()])) for key in keys}
    chosen = {freelancer_id: selection_value(values) for freelancer_id, values in per_freelancer.items()}
    model = context.collaborative[setting.factors]
    return Trial(
        setting=setting, components=model.n_components if model else None, means=means,
        selection=float(np.mean(list(chosen.values()))), per_freelancer=chosen,
    )


def run_grid(context, combinations=None):
    return [run_trial(context, setting) for setting in (combinations or grid())]


def random_spread(context, seeds=20):
    """
    How far the random baseline's selection value moves from seed to seed: the average over freelancers for each
    seed, then the standard deviation of those averages. A gain smaller than this is not worth reading.
    """
    per_seed = []
    for run_seed in range(seeds):
        values = []
        for case in context.cases:
            ranking = rankers.random_order(case.candidates, run_seed, case.freelancer_id)
            values.append(selection_value(metrics.freelancer_metrics(ranking, case.relevant, SELECTION_KS)))
        per_seed.append(float(np.mean(values)))
    return {
        'mean': float(np.mean(per_seed)), 'sd': float(np.std(per_seed, ddof=1)) if seeds > 1 else 0.0,
        'low': min(per_seed), 'high': max(per_seed), 'seeds': seeds,
    }


@dataclass
class Decision:
    current: Trial
    best: Trial
    changed: bool
    gain: float
    random_sd: float
    paired_low: float
    paired_high: float
    beat_by_more_than_luck: int  # combinations that beat the current by more than the random spread
    within_luck_of_best: int  # combinations within the random spread of the best
    reasons: list = field(default_factory=list)


def distance(trial, current):
    """How many of the four settings differ from the current ones (the factors compared as actually used)."""
    return sum(1 for a, b in zip(trial.key(), current.key()) if a != b)


def decide(trials, current, random_sd, seed=42):
    """
    Pick the best combination and say whether the defaults should change. Ties go to the combination closest to
    the current settings, so a result that is no better never changes anything.
    """
    def order(index):
        return (-round(trials[index].selection, 12), distance(trials[index], current), index)

    best = trials[min(range(len(trials)), key=order)]
    if current.selection >= best.selection:
        best = current
    gain = best.selection - current.selection

    differences = [best.per_freelancer[f] - current.per_freelancer[f] for f in current.per_freelancer]
    low, high = metrics.bootstrap_interval(differences, seed=seed)
    beats_luck = gain > random_sd
    beats_interval = low > 0
    reasons = [
        f'The best combination scores {best.selection:.3f} against {current.selection:.3f} for the current settings, '
        f'a gain of {gain:.3f}.',
        f'The random baseline moves by {random_sd:.3f} (one standard deviation across seeds): the gain is '
        f'{"larger" if beats_luck else "not larger"} than that.',
        f'The paired 95% interval of the gain over freelancers is {low:.3f} to {high:.3f}: ' + (
            'above zero.' if beats_interval
            else 'it includes zero, so the gain could be luck with this many freelancers.'
        ),
    ]
    changed = beats_luck and beats_interval and best is not current
    reasons.append(
        'Both conditions hold, so the defaults change.' if changed
        else 'The conditions for changing the defaults are not both met, so the current values stay.'
    )
    return Decision(
        current=current, best=best, changed=changed, gain=gain, random_sd=random_sd, paired_low=low, paired_high=high,
        beat_by_more_than_luck=sum(1 for t in trials if t.selection - current.selection > random_sd),
        within_luck_of_best=sum(1 for t in trials if best.selection - t.selection <= random_sd),
        reasons=reasons,
    )


QUANTILES = (50, 75, 90, 95)


def quantiles(values):
    """The count and the 50th, 75th, 90th and 95th percentiles of some scores. Nones when there are none."""
    result = {'n': len(values)}
    for q in QUANTILES:
        result[f'p{q}'] = float(np.percentile(values, q)) if values else None
    return result


def band_evidence(context):
    """
    The content scores that the match bands are read against, in two groups, both for pairs that really share at
    least one skill (a band is shown only then):

    - every candidate gig of every validation freelancer: the scores of freelancers and gigs that share a skill.
      This is how the first cut-offs were found in Sprint 5 (the median and the 90th percentile).
    - only the gigs they went on to apply to. Applicants lean towards gigs that suit them, so these run higher.
    """
    scorer = context.scorer
    candidate_scores, applicant_scores = [], []
    for case in context.cases:
        mine = scorer.freelancer_skills.get(case.freelancer_id, [])
        for gig_id, score in context.content[case.freelancer_id].items():
            if score is None or not content.match_reasons(mine, scorer.gig_skills.get(gig_id, [])):
                continue
            candidate_scores.append(score)
            if gig_id in case.relevant:
                applicant_scores.append(score)
    return {'candidates': quantiles(candidate_scores), 'applicants': quantiles(applicant_scores)}


def suggested_bands(evidence):
    """The cut-offs the evidence gives: good at the median and strong at the 90th percentile, to two places."""
    found = evidence['candidates']
    if not found['n']:
        return None
    return {'good': round(found['p50'], 2), 'strong': round(found['p90'], 2)}


@dataclass
class Reference:
    """A point to compare the combinations with. Not a candidate for the defaults."""

    label: str
    means: dict
    selection: float
    components: object = None


def score_ranking(context, rank):
    """(means, selection value) for a ranking function, on the same validation candidates as every combination."""
    per_freelancer = {
        case.freelancer_id: metrics.freelancer_metrics(rank(case), case.relevant, KS) for case in context.cases
    }
    keys = next(iter(per_freelancer.values())).keys()
    means = {key: float(np.mean([values[key] for values in per_freelancer.values()])) for key in keys}
    return means, float(np.mean([selection_value(values) for values in per_freelancer.values()]))


def short_setting(trial):
    s = trial.setting
    return f'weight {s.max_weight:g}, ramp {s.ramp}, {trial.components} factors, cold start below {s.cold_start}'


def references(context, trials, decision):
    """Content only, collaborative only at each number of factors, and the hybrids to read the result against."""
    seed = context.seed
    found = []
    means, selection = score_ranking(
        context, lambda case: rankers.order_by_score(context.content[case.freelancer_id], seed),
    )
    found.append(Reference('Content only', means, selection))
    for factors in FACTORS:
        model = context.collaborative[factors]
        if model is None:
            found.append(Reference(f'Collaborative only, {factors} factors: could not be fitted', {}, None))
            continue
        raw = context.raw[factors]
        means, selection = score_ranking(
            context, lambda case, raw=raw: rankers.order_by_score(raw[case.freelancer_id], seed),
        )
        suffix = ' (the cap)' if factors == CAP else ''
        found.append(Reference(
            f'Collaborative only, {model.n_components} factors{suffix}', means, selection, model.n_components,
        ))
    found.append(Reference(
        f'Current settings ({short_setting(decision.current)})', decision.current.means, decision.current.selection,
        decision.current.components,
    ))
    hybrids = [t for t in trials if t.setting.max_weight > 0]
    if hybrids:
        index = min(
            range(len(hybrids)),
            key=lambda i: (-round(hybrids[i].selection, 12), distance(hybrids[i], decision.current), i),
        )
        best = hybrids[index]
        found.append(Reference(
            f'Best hybrid with a collaborative weight above 0 ({short_setting(best)})', best.means, best.selection,
            best.components,
        ))
    found.append(Reference(
        f'Best combination by the rule ({short_setting(decision.best)})', decision.best.means,
        decision.best.selection, decision.best.components,
    ))
    return found
