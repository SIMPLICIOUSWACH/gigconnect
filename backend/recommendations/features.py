"""
Turning text into the cleaned documents the recommender learns from (proposal section 3.2.2).

Everything here is a pure function of its input, so it can be tested without a database. The same
functions prepare GigConnect gigs, GigConnect freelancers and the external Kaggle job postings, so
all three end up in the same vocabulary.

Done here: lowercasing, removing web addresses, emails and HTML, removing English stop words,
dropping numbers, and dropping empty and duplicate documents.

Not done: lemmatisation. The proposal asks for it, but it needs an extra language model download
(WordNet or spaCy) that costs install and CI time, and it matters little for skill names, which come
from a controlled list. It is recorded as a gap in docs/recommender.md and can be added here later.
"""

import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

MIN_TOKEN_LENGTH = 2

# A freelancer's skills are repeated this many times in their document so that skills dominate
# their short free-text bio. Gigs list each skill once.
FREELANCER_SKILL_REPEAT = 3

_HTML_TAG = re.compile(r'<[^>]+>')
_URL = re.compile(r'https?://\S+|www\.\S+')
_EMAIL = re.compile(r'\S+@\S+')
_NOT_ALPHANUMERIC = re.compile(r'[^a-z0-9]+')

# Skill names whose punctuation carries the meaning. Without these "C++", "C#" and "C" would all
# become the same token.
_SKILL_SPELLINGS = (('c++', 'cplusplus'), ('c#', 'csharp'), ('f#', 'fsharp'), ('.net', 'dotnet'), ('&', ' and '))


def clean_text(text):
    """Lowercase free text, remove noise and stop words, and return the remaining words joined by spaces."""
    text = (text or '').lower()
    text = _HTML_TAG.sub(' ', text)
    text = _URL.sub(' ', text)
    text = _EMAIL.sub(' ', text)
    words = _NOT_ALPHANUMERIC.sub(' ', text).split()
    return ' '.join(
        word for word in words
        if len(word) >= MIN_TOKEN_LENGTH and not word.isdigit() and word not in ENGLISH_STOP_WORDS
    )


def skill_token(name):
    """One skill name as a single token, so "Machine Learning" stays together as machine_learning."""
    key = (name or '').casefold().strip()
    for old, new in _SKILL_SPELLINGS:
        key = key.replace(old, new)
    return '_'.join(_NOT_ALPHANUMERIC.sub(' ', key).split())


def skill_tokens(names):
    """Skill names as space-separated tokens: no empty tokens, no repeats, original order."""
    seen = []
    for name in names or []:
        token = skill_token(name)
        if token and token not in seen:
            seen.append(token)
    return ' '.join(seen)


def gig_document(title, description, skill_names=(), category_name=''):
    """The text a gig is represented by: title, description, category and skill tokens."""
    parts = [clean_text(title), clean_text(description), clean_text(category_name), skill_tokens(skill_names)]
    return ' '.join(part for part in parts if part)


def freelancer_document(skill_names=(), bio=''):
    """The text a freelancer is represented by: their skill tokens (repeated) and the words of their bio."""
    tokens = skill_tokens(skill_names)
    parts = [' '.join([tokens] * FREELANCER_SKILL_REPEAT) if tokens else '', clean_text(bio)]
    return ' '.join(part for part in parts if part)


def drop_empty_and_duplicates(records, key='clean_text', min_words=3):
    """
    Keep the first record for each distinct document and drop the rest.

    Returns (kept, dropped) where dropped counts the reasons. A document with fewer than min_words
    words is treated as empty, because it carries too little to learn a vocabulary from.
    """
    kept = []
    seen = set()
    dropped = {'empty': 0, 'duplicate': 0}
    for record in records:
        text = record[key]
        if len(text.split()) < min_words:
            dropped['empty'] += 1
        elif text in seen:
            dropped['duplicate'] += 1
        else:
            seen.add(text)
            kept.append(record)
    return kept, dropped
