"""
The recommender profiles: which database and which tuned settings the app runs with.

The values live in recommender_profiles.json next to this file, not in code, so a profile can be read and changed
without touching Python. RECOMMENDER_PROFILE picks one:

- production (the default when the variable is missing): the ordinary database and the skill-overlap tuning pick.
- demo: the planted database and the planted tuning pick. Its reports and the admin are labelled as planted data.

The demo profile always uses the planted database, whatever DB_NAME says, and it refuses to start if the database it
reaches holds anything but planted accounts (see recommendations/checks.py). It has its own folders for trained
models and training snapshots, so training it can never touch the production ones.
"""

import json
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

PROFILES_FILE = Path(__file__).with_name('recommender_profiles.json')
DEFAULT = 'production'
REQUIRED = {
    'description', 'label', 'database', 'recommendations_enabled', 'blend_max_weight', 'blend_ramp_gigs',
    'svd_components', 'cold_start_min_gigs', 'band_good', 'band_strong', 'artifact_folder', 'snapshot_folder',
}


def load(path=PROFILES_FILE):
    profiles = json.loads(Path(path).read_text(encoding='utf-8'))
    for name, values in profiles.items():
        missing = REQUIRED - set(values)
        if missing:
            raise ImproperlyConfigured(f'Recommender profile "{name}" is missing {", ".join(sorted(missing))}.')
    return profiles


def resolve(environ, profiles=None):
    """(name, values) for the profile RECOMMENDER_PROFILE names, production when it is not set."""
    profiles = profiles or load()
    name = (environ.get('RECOMMENDER_PROFILE') or DEFAULT).strip().lower()
    if name not in profiles:
        raise ImproperlyConfigured(
            f'RECOMMENDER_PROFILE is "{name}", but the profiles are {", ".join(sorted(profiles))}.'
        )
    return name, profiles[name]


def database_name(values, environ):
    """The database a profile runs on. A profile that names one always uses it, so DB_NAME cannot override it."""
    return values['database'] or environ.get('DB_NAME', 'gigconnect')


def recommendations_enabled(values, environ):
    """A profile can switch recommendations on. Otherwise RECOMMENDATIONS_ENABLED decides, off by default."""
    if values['recommendations_enabled'] is not None:
        return bool(values['recommendations_enabled'])
    return environ.get('RECOMMENDATIONS_ENABLED', 'False') == 'True'
