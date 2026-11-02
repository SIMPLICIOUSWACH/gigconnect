"""
A cache of what the content model needs from each gig, so a request does not rebuild it for every candidate.

Measured in Sprint 6 (`time_recommendations`): without it a request took a median of about 1 second at 3,000 open
gigs and 1.8 seconds at 5,000. The vectoriser itself was a small part of that. Most of the time went on loading every
candidate gig with its category and skills, cleaning its text and turning its skills into tokens, again on every
request. The cache keeps, per gig:

- its TF-IDF vector (from the gig's title, description, category and skills),
- its skills, each with the token used to find the skills a freelancer really shares with it,
- when it was posted (used to order equal scores, newest first).

A request then only reads the candidates' ids and `updated_at` from the database. An entry is used while the gig's
`updated_at` matches; editing a gig saves it, which changes `updated_at`, so the next request builds the entry again.
No signals are needed. (Gig edits set the skills before the save, so the new `updated_at` always comes with the new
skills. See gigs/serializers.py.)

The cache is filled lazily, in one batch per request for whatever is missing or out of date, and belongs to one
loaded model: a new model version starts with an empty cache, because its vectoriser is different. Each server
process has its own. Two things do not change a gig's `updated_at` and are not noticed until the gig is next edited
or a new model is loaded: renaming a category, and renaming or merging a skill.
"""

import threading
from dataclasses import dataclass

import numpy as np
from scipy.sparse import vstack

from .features import gig_document, skill_token


@dataclass(frozen=True)
class GigEntry:
    updated_at: object
    created_at: object
    vector: object  # a 1 x vocabulary sparse row
    skills: tuple  # ((skill name, token), ...)


class GigVectorCache:
    def __init__(self, vectoriser):
        self.vectoriser = vectoriser
        self._entries = {}
        self._lock = threading.Lock()
        self.built = 0  # entries built so far, for tests and measurements

    def __len__(self):
        return len(self._entries)

    def entries(self, rows):
        """
        The entries for these gigs, as {gig id: GigEntry}. rows is [(gig id, updated_at), ...]. Entries that are missing
        or older than the gig are built first, in one batch. A gig deleted since the rows were read is left out.
        """
        rows = list(rows)
        stale = [gig_id for gig_id, updated_at in rows if self._is_stale(gig_id, updated_at)]
        if stale:
            self._build(stale)
        found = {}
        for gig_id, _ in rows:
            entry = self._entries.get(gig_id)
            if entry is not None:
                found[gig_id] = entry
        return found

    def _is_stale(self, gig_id, updated_at):
        entry = self._entries.get(gig_id)
        return entry is None or entry.updated_at != updated_at

    def _build(self, gig_ids):
        from gigs.models import Gig

        gigs = list(Gig.objects.filter(id__in=gig_ids).select_related('category').prefetch_related('skills'))
        if not gigs:
            return
        names = [[skill.name for skill in gig.skills.all()] for gig in gigs]
        texts = [
            gig_document(gig.title, gig.description, skills, gig.category.name) for gig, skills in zip(gigs, names)
        ]
        vectors = self.vectoriser.transform(texts).tocsr()
        built = {
            gig.id: GigEntry(
                updated_at=gig.updated_at, created_at=gig.created_at, vector=vectors[row],
                skills=tuple((name, skill_token(name)) for name in skills),
            )
            for row, (gig, skills) in enumerate(zip(gigs, names))
        }
        with self._lock:
            self._entries.update(built)
            self.built += len(built)


def content_scores(cache, freelancer_text, entries):
    """The cosine similarity of the freelancer's document to each entry's gig, clipped to 0 to 1, in entry order."""
    if not entries:
        return np.zeros(0)
    freelancer_vector = cache.vectoriser.transform([freelancer_text])
    gig_vectors = vstack([entry.vector for entry in entries]).tocsr()
    return np.clip(np.asarray((gig_vectors @ freelancer_vector.T).todense()).ravel(), 0.0, 1.0)


def shared_skills(freelancer_tokens, entry):
    """The gig's skills the freelancer really has, named as the gig names them (the same as content.match_reasons)."""
    return sorted((name for name, token in entry.skills if token in freelancer_tokens), key=str.casefold)
