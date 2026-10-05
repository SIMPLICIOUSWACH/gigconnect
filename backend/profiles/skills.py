"""Skill name normalisation, validation and alias-aware lookup.

Every path that turns text into a Skill (creating one, filtering gigs by skill name) goes
through here so "React", "react " and "ReactJS" all land on the same canonical skill.
"""

import re

MIN_LENGTH = 2
MAX_LENGTH = 50

_URL_PATTERN = re.compile(
    r'(https?://|www\.|\b[a-z0-9-]+\.(com|net|org|io|ke|co|info|biz|xyz|app|dev|me)\b)', re.IGNORECASE
)


def display_name(name):
    """Trim and collapse internal whitespace, keeping the original casing for display."""
    return ' '.join((name or '').split())


def match_key(name):
    """The case-folded form used for matching and uniqueness."""
    return display_name(name).casefold()


def validation_error(name):
    """A plain-language reason this isn't an acceptable new skill name, or None if it is."""
    cleaned = display_name(name)
    if len(cleaned) < MIN_LENGTH:
        return f'Skill name must be at least {MIN_LENGTH} characters.'
    if len(cleaned) > MAX_LENGTH:
        return f'Skill name must be {MAX_LENGTH} characters or fewer.'
    if not any(ch.isalnum() for ch in cleaned):
        return 'Skill name must contain letters or numbers.'
    if _URL_PATTERN.search(cleaned):
        return 'Skill name cannot contain a web address.'
    return None


def find_skill(name):
    """The canonical Skill for a name or alias (case and spacing insensitive), or None."""
    from .models import Skill, SkillAlias

    key = match_key(name)
    if not key:
        return None
    skill = Skill.objects.filter(normalized_name=key).first()
    if skill:
        return skill
    alias = SkillAlias.objects.select_related('skill').filter(normalized_alias=key).first()
    return alias.skill if alias else None
