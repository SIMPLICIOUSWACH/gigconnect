"""
Which kind of seed data a database holds, so every report can say what its numbers are about.

- skill_overlap: the ordinary development seed. Freelancers favour gigs that share a skill with them, which the
  content model sees directly, and there is no other pattern.
- synthetic_planted: a separate world made by `seed_planted` in its own database, with hidden taste groups that only
  a collaborative model could find. It shows whether the pipeline can find a pattern when one exists. It says
  nothing about real freelancers, and every report on it says so.

A database is in planted mode when it holds the planted accounts. `seed_planted` refuses to write into a database
that holds anything else, so the two never mix. A planted split is saved in a folder of its own, so building one
can never touch the split, and the held-out test part, of the ordinary data.
"""

from pathlib import Path

from django.conf import settings

SKILL_OVERLAP = 'skill_overlap'
SYNTHETIC_PLANTED = 'synthetic_planted'
PLANTED_EMAIL_PREFIX = 'planted-'
PLANTED_LABEL = 'synthetic_planted - demonstrates pipeline mechanics, not real-world accuracy'


def current_mode():
    from accounts.models import User

    if User.objects.filter(email__startswith=PLANTED_EMAIL_PREFIX).exists():
        return SYNTHETIC_PLANTED
    return SKILL_OVERLAP


def split_directory(mode=None):
    """Where a mode's split is saved. The ordinary one keeps its old place."""
    base = Path(settings.RECOMMENDER_DATA_DIR) / 'platform' / 'evaluation'
    return base / SYNTHETIC_PLANTED if (mode or current_mode()) == SYNTHETIC_PLANTED else base


def planted_directory():
    """Where the planted world's ground truth is kept. Not in the database, so no model can read it."""
    return Path(settings.RECOMMENDER_DATA_DIR) / SYNTHETIC_PLANTED


def report_prefix(kind, mode=None):
    """evaluation, tuning or readiness, with the mode added for planted data so the reports cannot be confused."""
    return f'{kind}-{SYNTHETIC_PLANTED}' if (mode or current_mode()) == SYNTHETIC_PLANTED else kind


def label_lines(mode):
    """The line every planted report starts with. Other reports are left as they were."""
    return [f'**Data: {PLANTED_LABEL}.**', ''] if mode == SYNTHETIC_PLANTED else []


PLANTED_WARNING = [
    '> **Planted synthetic data.** Each freelancer was generated to pick about 40% of their gigs by a hidden taste',
    '> group (from budget, urgency, client, location and posting date, none of which the content model reads), about',
    '> 40% by skill overlap and about 20% at random. The group share favours the collaborative model and the skill',
    '> share favours the content model, both by construction. These numbers show whether the pipeline finds a',
    '> planted pattern, not how it would do for real freelancers.',
    '',
]


def test_runs_name(mode=None):
    """The log of test runs. Planted data keeps its own, so its runs never count against the ordinary test part."""
    if mode == SYNTHETIC_PLANTED:
        return f'evaluation-{SYNTHETIC_PLANTED}-test-runs.csv'
    return 'evaluation-test-runs.csv'
