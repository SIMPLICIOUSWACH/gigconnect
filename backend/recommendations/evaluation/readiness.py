"""
Is there anything for a collaborative model to learn? A check to run before trusting, or tuning, the collaborative part.

It takes the matrix the collaborative model would be trained on (the train part of the split, all interactions) and
asks how much of it k hidden factors explain, for several k. The same is asked of random matrices built from it:

- uniform: the same shape, the same number of filled cells and the same values, in random places.
- degree-preserving: the same filled cells per freelancer and per gig, shuffled by swapping pairs of cells. This keeps
  popularity (some gigs get many applicants) and activity (some freelancers apply a lot), so beating it means there is
  structure beyond those: freelancers who go for the same kinds of gigs.

The data shows structure when, at some k, the real share is above the random one by more than three standard
deviations of the random draws and by at least one percentage point. Below that, the factors are fitting noise.
"""

from dataclasses import dataclass, field
from statistics import median

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

from .. import collaborative as collab
from .split import TRAIN
from .training_input import training_input

DEFAULT_KS = (2, 5, 10, 15, 25, 50)
DEFAULT_DRAWS = 20
STANDARD_DEVIATIONS = 3
MARGIN = 0.01


def explained(matrix, k, seed=42):
    """The share of the matrix that k hidden factors explain, from 0 to 1."""
    return float(TruncatedSVD(n_components=k, random_state=seed).fit(matrix).explained_variance_ratio_.sum())


def uniform_null(matrix, rng):
    """The same shape, number of filled cells and values, in random cells."""
    rows, columns = matrix.shape
    cells = rng.choice(rows * columns, size=matrix.nnz, replace=False)
    values = rng.permutation(matrix.data)
    return csr_matrix((values, (cells // columns, cells % columns)), shape=matrix.shape)


def degree_preserving_null(matrix, rng, swaps_per_cell=10):
    """
    Shuffle the matrix by swapping the gigs of two filled cells, (a, x) and (b, y) to (a, y) and (b, x), whenever both
    new cells are empty. Every freelancer keeps their number of gigs and every gig its number of freelancers. A value
    stays with its freelancer.
    """
    coo = matrix.tocoo()
    rows, columns, values = coo.row.copy(), coo.col.copy(), coo.data.copy()
    filled = set(zip(rows.tolist(), columns.tolist()))
    count = len(rows)
    if count < 2:
        return matrix.copy()
    for i, j in rng.randint(0, count, size=(swaps_per_cell * count, 2)):
        a, x, b, y = rows[i], columns[i], rows[j], columns[j]
        if a == b or x == y or (a, y) in filled or (b, x) in filled:
            continue
        filled.difference_update({(a, x), (b, y)})
        filled.update({(a, y), (b, x)})
        columns[i], columns[j] = y, x
    return csr_matrix((values, (rows, columns)), shape=matrix.shape)


def ks_for(shape, wanted=DEFAULT_KS):
    """The k to check: the default ones that fit, and the cap the model uses (half the smaller side)."""
    cap = max(1, min(shape) // 2)
    found = sorted({k for k in wanted if k < cap} | {cap})
    return [k for k in found if k < min(shape)]


@dataclass(frozen=True)
class CurveRow:
    k: int
    real: float
    uniform_mean: float
    uniform_sd: float
    degree_mean: float
    degree_sd: float

    @staticmethod
    def _above(real, mean, sd):
        return real - mean > max(STANDARD_DEVIATIONS * sd, MARGIN)

    @property
    def above_uniform(self):
        return self._above(self.real, self.uniform_mean, self.uniform_sd)

    @property
    def above_degree(self):
        return self._above(self.real, self.degree_mean, self.degree_sd)


def curve(matrix, ks, draws=DEFAULT_DRAWS, seed=0):
    rng = np.random.RandomState(seed)
    uniform = [uniform_null(matrix, rng) for _ in range(draws)]
    degree = [degree_preserving_null(matrix, rng) for _ in range(draws)]
    rows = []
    for k in ks:
        u = [explained(m, k) for m in uniform]
        d = [explained(m, k) for m in degree]
        rows.append(CurveRow(
            k=k, real=explained(matrix, k), uniform_mean=float(np.mean(u)), uniform_sd=float(np.std(u)),
            degree_mean=float(np.mean(d)), degree_sd=float(np.std(d)),
        ))
    return rows


@dataclass
class Readiness:
    shape: tuple
    filled: int
    applications_per_freelancer: tuple  # (fewest, median, most) in the train part
    applicants_per_gig: tuple  # (fewest, median, most) over gigs with any train applicant
    gigs_with_applicants: int
    rows: list = field(default_factory=list)

    @property
    def density(self):
        return self.filled / (self.shape[0] * self.shape[1]) if self.filled else 0.0

    @property
    def above_uniform(self):
        return any(row.above_uniform for row in self.rows)

    @property
    def above_degree(self):
        return any(row.above_degree for row in self.rows)


def check(split, include_synthetic=True, ks=None, draws=DEFAULT_DRAWS, seed=0):
    """The readiness of the training data this split allows. Reads nothing from the held-out parts."""
    weights = training_input(split, include_synthetic).weights
    if not weights:
        return Readiness(shape=(0, 0), filled=0, applications_per_freelancer=(0, 0, 0), applicants_per_gig=(0, 0, 0),
                         gigs_with_applicants=0)
    matrix, _, _ = collab.build_matrix(weights)
    per_freelancer, per_gig = {}, {}
    for positive in split.in_part(TRAIN):
        per_freelancer[positive.freelancer_id] = per_freelancer.get(positive.freelancer_id, 0) + 1
        per_gig[positive.gig_id] = per_gig.get(positive.gig_id, 0) + 1

    def spread(values):
        values = list(values)
        return (min(values), median(values), max(values)) if values else (0, 0, 0)

    return Readiness(
        shape=matrix.shape, filled=matrix.nnz, applications_per_freelancer=spread(per_freelancer.values()),
        applicants_per_gig=spread(per_gig.values()), gigs_with_applicants=len(per_gig),
        rows=curve(matrix, ks or ks_for(matrix.shape), draws, seed),
    )


def markdown(readiness, split, mode_lines, command, day, total_gigs):
    rows, columns = readiness.shape
    lines = [
        f'# Collaborative readiness check, {day}', '', *mode_lines,
        f'- Command: `{command}`',
        f'- Split: fingerprint `{split.fingerprint()}`. Only the train part was read.',
        f'- Matrix (train part, all interactions): {rows} freelancers x {columns} gigs, {readiness.filled} filled '
        f'cells, density {readiness.density:.1%}.',
        f'- Train applications per freelancer: fewest {readiness.applications_per_freelancer[0]}, median '
        f'{readiness.applications_per_freelancer[1]:g}, most {readiness.applications_per_freelancer[2]}.',
        f'- Train applicants per gig, over the {readiness.gigs_with_applicants} of {total_gigs} gigs with any: fewest '
        f'{readiness.applicants_per_gig[0]}, median {readiness.applicants_per_gig[1]:g}, most '
        f'{readiness.applicants_per_gig[2]}.', '',
        '## Explained variance against random matrices', '',
        'The share of the matrix that k hidden factors explain, for the real data and for random matrices built from '
        'it (mean and standard deviation over the draws). "Uniform" puts the same values in random cells. "Same '
        'counts" keeps every freelancer\'s and every gig\'s number of cells, so it keeps popularity.', '',
        '| k | Real data | Uniform random | Same counts random | Above uniform | Above same counts |',
        '|---|---|---|---|---|---|',
    ]
    for row in readiness.rows:
        lines.append(
            f'| {row.k} | {row.real:.1%} | {row.uniform_mean:.1%} (sd {row.uniform_sd:.1%}) | '
            f'{row.degree_mean:.1%} (sd {row.degree_sd:.1%}) | {"yes" if row.above_uniform else "no"} | '
            f'{"yes" if row.above_degree else "no"} |'
        )
    lines += [
        '',
        '## Verdict', '',
        f'- Structure above a uniform random matrix: **{"yes" if readiness.above_uniform else "no"}**.',
        f'- Structure above a random matrix with the same counts: **{"yes" if readiness.above_degree else "no"}**. '
        'This is the one that says whether freelancers share tastes, not just popular gigs.',
        f'- The rule: at some k, the real share beats the random mean by more than {STANDARD_DEVIATIONS} standard '
        f'deviations and by at least {MARGIN:.0%}.',
        '',
    ]
    return '\n'.join(lines) + '\n'
