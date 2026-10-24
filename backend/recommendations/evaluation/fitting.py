"""
Fitting the models for an evaluation, on the training part of a split only, and scoring candidates with them.

This follows the same steps as `train_recommender` (the same cleaning, the same vectoriser settings, the same
SVD code), with the one difference that what goes in is decided by `training_input`, so nothing from a
freelancer's held-out period reaches a model. Nothing is saved: the models live for one evaluation.

Two collaborative models are fitted, so both readings can be compared on the same split:

- "applications and hiring only": the train applications with their status at the cut-off, as the proposal
  describes the collaborative data.
- "all interactions": the same plus views, clicks and saves, as the live system is built.

A model that cannot be fitted (too little data) is None with the reason recorded, never a made-up stand-in.

A limit worth knowing. A freelancer's skills and bio are read as they are today. Profiles are not versioned, so
the evaluation cannot know what a profile said at the cut-off.
"""

from dataclasses import dataclass, field

import numpy as np
from django.conf import settings

from .. import collaborative as collab
from .. import content, hybrid, training
from ..features import freelancer_document, gig_document
from ..platform import freelancers_for_training, gigs_for_training
from .training_input import training_input, vectoriser_gig_ids


class EvaluationError(Exception):
    """The evaluation cannot run. The message says why in plain language."""


@dataclass
class FittedModels:
    vectoriser: object
    collaborative_all: object = None  # fitted on applications and interactions, or None
    collaborative_applications: object = None  # fitted on applications only, or None
    skipped: dict = field(default_factory=dict)  # {'all' or 'applications': why it was not fitted}
    history: dict = field(default_factory=dict)  # {freelancer id: different gigs in their training data}
    stats: dict = field(default_factory=dict)


def fit_models(split, include_synthetic=True, data_dir=None):
    """Fit the vectoriser and both collaborative models on the training data this split allows."""
    allowed = set(vectoriser_gig_ids(split, include_synthetic))
    gigs = [gig for gig in gigs_for_training(include_synthetic) if gig.id in allowed]
    documents, dropped = training.build_platform_documents(gigs)
    external = training.read_external_corpus(data_dir or settings.RECOMMENDER_DATA_DIR)
    try:
        vectoriser = content.fit_vectoriser([record['clean_text'] for record in documents], external)
    except ValueError as error:
        raise EvaluationError(f'The content model could not be fitted on the training gigs: {error}') from error

    everything = training_input(split, include_synthetic)
    applications_only = training_input(split, include_synthetic, include_interactions=False)

    models = FittedModels(vectoriser=vectoriser)
    for name, weights in (('all', everything.weights), ('applications', applications_only.weights)):
        try:
            fitted = collab.fit(weights)
        except collab.NotEnoughData as error:
            models.skipped[name] = str(error)
            continue
        setattr(models, 'collaborative_all' if name == 'all' else 'collaborative_applications', fitted)

    gigs_per_freelancer = {}
    for freelancer_id, gig_id in everything.weights:
        gigs_per_freelancer.setdefault(freelancer_id, set()).add(gig_id)
    models.history = {freelancer_id: len(found) for freelancer_id, found in gigs_per_freelancer.items()}
    models.stats = {
        'vectoriser_gigs': len(documents),
        'external_documents': len(external),
        'vocabulary_size': len(vectoriser.vocabulary_),
        'training_input_all': everything.stats,
        'training_input_applications': applications_only.stats,
        'pairs_all': len(everything.weights),
        'pairs_applications': len(applications_only.weights),
    }
    return models


class Scorer:
    """
    Scores a freelancer's candidate gigs with each model. Gig and freelancer documents are worked out once, so
    scoring many freelancers does not repeat the text cleaning.
    """

    def __init__(self, models, include_synthetic=True):
        self.models = models
        gigs = list(gigs_for_training(include_synthetic))
        self.gig_row = {gig.id: row for row, gig in enumerate(gigs)}
        texts = [
            gig_document(gig.title, gig.description, [skill.name for skill in gig.skills.all()], gig.category.name)
            for gig in gigs
        ]
        self.gig_vectors = models.vectoriser.transform(texts) if texts else None
        self.freelancer_text = {
            profile.user_id: freelancer_document([skill.name for skill in profile.skills.all()], profile.bio)
            for profile in freelancers_for_training(include_synthetic)
        }
        self._freelancer_vector = {}

    def scorable(self, freelancer_id):
        """False for a freelancer with no skills and no bio, who cannot be compared with any gig."""
        return bool(self.freelancer_text.get(freelancer_id))

    def content_scores(self, freelancer_id, gig_ids):
        """{gig id: cosine similarity from 0 to 1}, or None for every gig when the freelancer is not scorable."""
        if not self.scorable(freelancer_id):
            return {gig_id: None for gig_id in gig_ids}
        if freelancer_id not in self._freelancer_vector:
            self._freelancer_vector[freelancer_id] = self.models.vectoriser.transform(
                [self.freelancer_text[freelancer_id]],
            )
        rows = [self.gig_row[gig_id] for gig_id in gig_ids]
        found = np.asarray((self.gig_vectors[rows] @ self._freelancer_vector[freelancer_id].T).todense()).ravel()
        return {gig_id: float(score) for gig_id, score in zip(gig_ids, np.clip(found, 0.0, 1.0))}

    def collaborative_scores(self, model, freelancer_id, gig_ids):
        """{gig id: raw collaborative score, or None where the model has none}. Empty scores if no model."""
        if model is None:
            return {gig_id: None for gig_id in gig_ids}
        return collab.score(model, freelancer_id, gig_ids)

    def hybrid_scores(self, freelancer_id, gig_ids):
        """
        The live blend at the current settings: content, plus the "all interactions" collaborative score once the
        freelancer has enough different gigs in their training data. The blend weight is worked out from that
        training data, not from everything the freelancer has done since.
        """
        content_scores = self.content_scores(freelancer_id, gig_ids)
        model = self.models.collaborative_all
        weight = hybrid.blend_weight(self.models.history.get(freelancer_id, 0))
        raw = self.collaborative_scores(model, freelancer_id, gig_ids) if weight > 0 else {}
        scores = {}
        for gig_id in gig_ids:
            if content_scores[gig_id] is None:
                scores[gig_id] = None
                continue
            normalised = hybrid.normalise_collaborative(raw.get(gig_id), model.scale if model else None)
            scores[gig_id] = hybrid.hybrid_score(content_scores[gig_id], normalised, weight)[0]
        return scores

    def in_cold_start(self, freelancer_id):
        return hybrid.in_cold_start(self.models.history.get(freelancer_id, 0))
