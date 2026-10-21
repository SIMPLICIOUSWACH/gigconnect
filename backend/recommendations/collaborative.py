"""
The collaborative model: what freelancers with similar history went on to show interest in.

A matrix is built with one row per freelancer and one column per gig, holding how strongly that
freelancer has shown interest in that gig (a view is worth little, an application more, a hire most).
Truncated SVD finds a few hidden factors that explain the pattern, and multiplying them back together
fills in a score for gigs a freelancer has not touched yet.

Two things are deliberately left out of the answer rather than guessed:

- A gig that nobody has interacted with has no column, so it gets no collaborative score at all (the
  score is absent, not zero). The hybrid model falls back to content for it.
- A freelancer with no history has no row, so they get no collaborative score either.

When there is too little data for this to mean anything, fitting raises NotEnoughData and the
recommender uses content scores only. With a small or mostly synthetic dataset this is what should
happen, and the reason is recorded; the limits are settings, not tuned to make results look good.

The functions that build the weights and the matrix take plain values, so they can be tested on a
small hand-made matrix. The scores here are raw values from the SVD and are not yet on a 0 to 1 scale;
scaling them is the job of the hybrid model.
"""

from dataclasses import dataclass

import numpy as np
from django.conf import settings
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

from . import hybrid
from .platform import applications_for_training, interactions_for_training


class NotEnoughData(Exception):
    """There is too little interaction data to learn from. The message says what was too small."""


@dataclass
class CollaborativeModel:
    svd: TruncatedSVD
    user_index: dict  # freelancer user id -> row
    gig_index: dict  # gig id -> column
    user_factors: np.ndarray  # one row of hidden-factor values per freelancer
    n_interactions: int
    scale: float  # the raw score that counts as 1.0, fixed at training time (see hybrid.py)

    @property
    def n_components(self):
        return self.svd.n_components

    @property
    def explained_variance(self):
        """The share of the matrix the hidden factors account for, from 0 to 1."""
        return float(self.svd.explained_variance_ratio_.sum())


def build_weights(interactions, applications):
    """
    How strongly each freelancer has shown interest in each gig, as {(user_id, gig_id): weight}.

    interactions is (user_id, gig_id, type) rows and applications is (user_id, gig_id, status) rows.
    The strongest signal for a pair wins. A type or status with no weight in the settings is ignored.
    """
    interaction_weights = settings.RECOMMENDER_INTERACTION_WEIGHTS
    application_weights = settings.RECOMMENDER_APPLICATION_WEIGHTS
    weights = {}

    def keep_strongest(user_id, gig_id, weight):
        key = (user_id, gig_id)
        if weight > weights.get(key, 0):
            weights[key] = weight

    for user_id, gig_id, kind in interactions:
        if kind in interaction_weights:
            keep_strongest(user_id, gig_id, interaction_weights[kind])
    for user_id, gig_id, status in applications:
        if status in application_weights:
            keep_strongest(user_id, gig_id, application_weights[status])
    return weights


def load_weights(include_synthetic=True):
    """The weights for everything the recommender is allowed to learn from (see platform.py)."""
    interactions = interactions_for_training(include_synthetic).values_list('user_id', 'gig_id', 'type')
    applications = applications_for_training(include_synthetic).values_list('freelancer_id', 'gig_id', 'status')
    return build_weights(interactions, applications)


def build_matrix(weights):
    """Turn {(user_id, gig_id): weight} into a sparse matrix, with the ids for each row and column."""
    user_ids = sorted({user_id for user_id, _ in weights}, key=str)
    gig_ids = sorted({gig_id for _, gig_id in weights}, key=str)
    user_index = {user_id: row for row, user_id in enumerate(user_ids)}
    gig_index = {gig_id: column for column, gig_id in enumerate(gig_ids)}
    rows = [user_index[user_id] for user_id, _ in weights]
    columns = [gig_index[gig_id] for _, gig_id in weights]
    matrix = csr_matrix((list(weights.values()), (rows, columns)), shape=(len(user_ids), len(gig_ids)), dtype=float)
    return matrix, user_index, gig_index


def too_little_data(matrix):
    """Why the matrix is too small to learn from, or an empty string if it is big enough."""
    users, gigs = matrix.shape
    # Whatever the settings say, one freelancer has nobody to learn from and one gig has nothing to
    # compare, and the SVD needs at least two columns to run at all.
    minimums = (
        (users, max(2, settings.RECOMMENDER_SVD_MIN_FREELANCERS), 'freelancers with any history'),
        (gigs, max(2, settings.RECOMMENDER_SVD_MIN_GIGS), 'gigs with any interaction'),
        (matrix.nnz, settings.RECOMMENDER_SVD_MIN_INTERACTIONS, 'freelancer and gig pairs with an interaction'),
    )
    for have, need, what in minimums:
        if have < need:
            return f'only {have} {what}, and at least {need} are needed'
    return ''


def fit(weights, n_components=None):
    """
    Learn the hidden factors from {(user_id, gig_id): weight}.

    Raises NotEnoughData, with the reason, if the data is below the settings' minimums. The number of
    factors is capped at half the smaller side of the matrix, so the model has to compress the data.
    """
    matrix, user_index, gig_index = build_matrix(weights)
    reason = too_little_data(matrix)
    if reason:
        raise NotEnoughData(reason)
    wanted = settings.RECOMMENDER_SVD_COMPONENTS if n_components is None else n_components
    # Never more than half the smaller side. With nearly as many factors as the matrix has rows, the model
    # simply reproduces the data it was given, so a gig a freelancer has not touched scores about zero and
    # the scores are noise. Fewer factors force it to find the pattern instead of copying the cells.
    components = max(1, min(wanted, min(matrix.shape) // 2))
    svd = TruncatedSVD(n_components=components, random_state=settings.RECOMMENDER_RANDOM_SEED)
    user_factors = svd.fit_transform(matrix)
    scale = _scale(svd, user_factors, matrix)
    if scale is None:
        raise NotEnoughData('no freelancer has a gig left to recommend: every gig in the data has been touched')
    return CollaborativeModel(
        svd=svd, user_index=user_index, gig_index=gig_index, user_factors=user_factors,
        n_interactions=matrix.nnz, scale=scale,
    )


def _scale(svd, user_factors, matrix, block=500):
    """The 95th percentile of the positive scores on untouched cells, worked out a block of rows at a time."""
    pieces = []
    for start in range(0, matrix.shape[0], block):
        rows = slice(start, start + block)
        reconstructed = user_factors[rows] @ svd.components_
        observed = matrix[rows].toarray() > 0
        pieces.append(hybrid.unseen_positive_scores(reconstructed, observed))
    scores = np.concatenate(pieces) if pieces else np.zeros(0)
    return hybrid.scale_from_scores(scores)


def score(model, user_id, gig_ids):
    """
    The raw collaborative score of each gig for one freelancer, as {gig_id: score or None}.

    None means there is no collaborative score: the freelancer has no history in the model, or the gig
    has no interactions in it. That is different from a score of zero.
    """
    row = model.user_index.get(user_id)
    if row is None:
        return {gig_id: None for gig_id in gig_ids}
    result = {}
    for gig_id in gig_ids:
        column = model.gig_index.get(gig_id)
        result[gig_id] = None if column is None else float(model.user_factors[row] @ model.svd.components_[:, column])
    return result
