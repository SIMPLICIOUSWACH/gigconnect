"""
How well a model's picture of freelancers recovers the hidden groups of the planted world.

For every pair of freelancers, take the cosine similarity of their vectors (the collaborative model's hidden factors,
or the content model's profile vector). The pair AUC is the chance that a pair from the same group is more similar
than a pair from different groups: 0.5 is chance and 1.0 means every same-group pair is closer than every other.

The labels are only read here, after the models are fitted, and only to score them. They never reach a model.
"""

import numpy as np
from scipy.stats import rankdata


def _pairs(vectors, labels):
    ids = sorted(set(vectors) & set(labels), key=str)
    if len(ids) < 2:
        return ids, None, None
    matrix = np.array([np.asarray(vectors[i], dtype=float).ravel() for i in ids])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)
    upper = np.triu_indices(len(ids), k=1)
    similarity = (matrix @ matrix.T)[upper]
    groups = np.array([labels[i] for i in ids])
    return ids, similarity, (groups[upper[0]], groups[upper[1]])


def auc(scores, positive):
    """The Mann-Whitney AUC of scores for positive against the rest. None if either side is empty."""
    positive = np.asarray(positive, dtype=bool)
    count_positive, count_negative = positive.sum(), (~positive).sum()
    if not count_positive or not count_negative:
        return None
    ranks = rankdata(scores)
    above = ranks[positive].sum() - count_positive * (count_positive + 1) / 2
    return float(above / (count_positive * count_negative))


def pair_auc(vectors, labels):
    """Same-group pairs against different-group pairs. vectors and labels are {freelancer id: ...}."""
    _, similarity, pairs = _pairs(vectors, labels)
    if similarity is None:
        return None
    first, second = pairs
    return auc(similarity, first == second)


def per_group_auc(vectors, labels):
    """For each group, its own pairs against pairs with exactly one member in it."""
    _, similarity, pairs = _pairs(vectors, labels)
    found = {}
    for group in sorted(set(labels.values())):
        if similarity is None:
            found[group] = None
            continue
        first, second = pairs
        inside, one = (first == group) & (second == group), (first == group) ^ (second == group)
        chosen = inside | one
        found[group] = auc(similarity[chosen], inside[chosen])
    return found


def shuffled_auc(vectors, labels, draws=20, seed=0):
    """The pair AUC with the labels shuffled among the same freelancers: what chance gives. (mean, sd)."""
    rng = np.random.RandomState(seed)
    ids = sorted(set(vectors) & set(labels), key=str)
    values = [labels[i] for i in ids]
    found = []
    for _ in range(draws):
        shuffled = dict(zip(ids, rng.permutation(values)))
        found.append(pair_auc(vectors, shuffled))
    return float(np.mean(found)), float(np.std(found))


def recovery(context, labels, factors_order, draws=20):
    """
    The pair AUC of each fitted collaborative model, of the content profiles, and of shuffled labels (chance), for the
    freelancers the models were trained on. `labels` is {freelancer id: group}, read after fitting.
    """
    rows = []
    reference = None
    for factors in factors_order:
        model = context.collaborative.get(factors)
        if model is None:
            continue
        vectors = collaborative_vectors(model)
        reference = reference or vectors
        rows.append({
            'label': f'Collaborative factors, {model.n_components}' + (' (the cap)' if factors == 'cap' else ''),
            'auc': pair_auc(vectors, labels), 'per_group': per_group_auc(vectors, labels),
        })
    content = content_vectors(context.scorer)
    content = {user_id: vector for user_id, vector in content.items() if reference is None or user_id in reference}
    rows.append({
        'label': 'Content profile (skills and bio)', 'auc': pair_auc(content, labels),
        'per_group': per_group_auc(content, labels),
    })
    chance = shuffled_auc(reference or content, labels, draws=draws)
    return {'rows': rows, 'chance': chance, 'freelancers': len(set(reference or content) & set(labels))}


def collaborative_vectors(model):
    """{freelancer id: their row of hidden factors} from a fitted collaborative model."""
    return {user_id: model.user_factors[row] for user_id, row in model.user_index.items()}


def content_vectors(scorer):
    """{freelancer id: their TF-IDF profile vector} from the content model, for freelancers with a profile."""
    found = {}
    for user_id, text in scorer.freelancer_text.items():
        if text:
            found[user_id] = scorer.models.vectoriser.transform([text]).toarray().ravel()
    return found
