"""
The content-based model: how much a freelancer's skills and bio look like a gig's text.

A TF-IDF vectoriser is fitted on gig documents (plus the external job-posting corpus, so it knows how
skill and job words relate before GigConnect has many gigs of its own). A freelancer is turned into a
vector in the same space from their skills and bio, and the score for a gig is the cosine similarity of
the two vectors, from 0 (nothing in common) to 1 (the same words in the same proportions).

The vectors are length-normalised, so cosine similarity is just their dot product and a given
freelancer and gig always get the same score, whatever other gigs are being scored with them.

Everything here is a plain function of its arguments, with no database access of its own, so it can be
tested on a tiny hand-made corpus.
"""

from dataclasses import dataclass

import numpy as np
from django.conf import settings
from sklearn.feature_extraction.text import TfidfVectorizer

from .features import freelancer_document, gig_document, skill_token


@dataclass
class ContentMatch:
    gig: object
    score: float
    match_reasons: list


def repeat_to_share(platform_documents, external_count, share):
    """
    The platform's documents, repeated so they are about `share` of all documents once the external ones
    are added. A few hundred real gigs would otherwise vanish among tens of thousands of foreign postings.
    """
    platform_documents = list(platform_documents)
    if not platform_documents or external_count == 0 or share <= 0:
        return platform_documents
    if share >= 1:
        raise ValueError('The platform share must be below 1.')
    wanted = share / (1 - share) * external_count
    repeats = max(1, round(wanted / len(platform_documents)))
    return platform_documents * repeats


def fit_vectoriser(platform_documents, external_documents=(), platform_share=None, min_df=None, max_df=None):
    """
    Fit the TF-IDF vectoriser. Words that appear in fewer than min_df documents are ignored, and so are
    words that appear in more than max_df of them (the share, from 0 to 1). The settings give the defaults.
    """
    share = settings.RECOMMENDER_PLATFORM_SHARE if platform_share is None else platform_share
    external_documents = list(external_documents)
    documents = external_documents + repeat_to_share(platform_documents, len(external_documents), share)
    if not documents:
        raise ValueError('There are no documents to fit the vectoriser on.')
    vectoriser = TfidfVectorizer(
        sublinear_tf=True,
        norm='l2',
        lowercase=False,  # the documents are already lowercased
        token_pattern=r'(?u)\b\w\w+\b',  # keeps machine_learning as one token
        min_df=settings.RECOMMENDER_TFIDF_MIN_DF if min_df is None else min_df,
        max_df=settings.RECOMMENDER_TFIDF_MAX_DF if max_df is None else max_df,
    )
    vectoriser.fit(documents)
    return vectoriser


def cosine_scores(vectoriser, freelancer_text, gig_texts):
    """The cosine similarity of one freelancer document to each gig document, as an array from 0 to 1."""
    gig_texts = list(gig_texts)
    if not gig_texts:
        return np.zeros(0)
    freelancer_vector = vectoriser.transform([freelancer_text])
    gig_vectors = vectoriser.transform(gig_texts)
    scores = np.asarray((gig_vectors @ freelancer_vector.T).todense()).ravel()
    return np.clip(scores, 0.0, 1.0)


def match_reasons(freelancer_skill_names, gig_skill_names):
    """
    The skills a freelancer and a gig really share, named as the gig names them. Only skills that are on
    both lists: a reason is never worked out from the score or made up.
    """
    mine = {skill_token(name) for name in freelancer_skill_names}
    return sorted((name for name in gig_skill_names if skill_token(name) in mine), key=str.casefold)


def rank_for_freelancer(vectoriser, profile, gigs):
    """
    Score every gig for this freelancer and return them best first as ContentMatch objects.

    A freelancer with no skills and no bio gives an empty document, which cannot be compared with
    anything, so nothing is returned for them rather than a list of meaningless zeros. The profile's
    skills and the gigs' skills and categories should be prefetched by the caller.
    """
    freelancer_skills = [skill.name for skill in profile.skills.all()]
    freelancer_text = freelancer_document(freelancer_skills, profile.bio)
    gigs = list(gigs)
    if not freelancer_text or not gigs:
        return []

    gig_skills = [[skill.name for skill in gig.skills.all()] for gig in gigs]
    gig_texts = [
        gig_document(gig.title, gig.description, skills, gig.category.name)
        for gig, skills in zip(gigs, gig_skills)
    ]
    scores = cosine_scores(vectoriser, freelancer_text, gig_texts)
    matches = [
        ContentMatch(gig=gig, score=float(score), match_reasons=match_reasons(freelancer_skills, skills))
        for gig, skills, score in zip(gigs, gig_skills, scores)
    ]
    # Equal scores are ordered newest first, then by id, so the order never changes between requests.
    matches.sort(key=lambda match: (-match.score, -match.gig.created_at.timestamp(), str(match.gig.id)))
    return matches
