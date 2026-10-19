"""
Loading the trained model once and keeping it in memory.

Nothing is loaded at startup, only the first time a model is asked for, so a missing or broken model can
never stop the app from starting. After that the loaded model is reused. The database is asked whether a
newer model has been trained only once the cache time is up (RECOMMENDER_MODEL_CACHE_SECONDS), so a request
does not touch the model files or the database to find that out.

If the files are missing or cannot be read, the problem is logged and the answer is "not available". That
is an ordinary answer, not an error: the API turns it into an empty state and nothing crashes.
"""

import logging
import threading
import time
from dataclasses import dataclass

import joblib
from django.conf import settings

from .models import RecommenderModelVersion
from .training import COLLABORATIVE_FILE, VECTORISER_FILE

logger = logging.getLogger(__name__)

DISABLED = 'disabled'
MODEL_UNAVAILABLE = 'model_unavailable'


@dataclass
class LoadedModel:
    version: RecommenderModelVersion
    vectoriser: object
    collaborative: object  # a collaborative.CollaborativeModel, or None if that model was skipped


@dataclass
class Availability:
    """Either a model, or the reason there isn't one: 'disabled' or 'model_unavailable'."""

    model: LoadedModel = None
    reason: str = ''

    @property
    def available(self):
        return self.model is not None


_lock = threading.Lock()
_state = {'checked_at': None, 'loaded_id': None, 'model': None}


def clear_cache():
    """Forget the loaded model, so the next request looks again. Used by tests and after a manual retrain."""
    with _lock:
        _state.update(checked_at=None, loaded_id=None, model=None)


def load(version):
    """Read one trained model from disk. Returns a LoadedModel, or None if it cannot be read."""
    folder = settings.RECOMMENDER_ARTIFACT_DIR / version.folder
    try:
        vectoriser = joblib.load(folder / VECTORISER_FILE)
        collaborative = joblib.load(folder / COLLABORATIVE_FILE) if version.collaborative_fitted else None
        if not hasattr(vectoriser, 'transform'):
            raise ValueError('the saved content model is not a vectoriser')
    except Exception:  # a missing, corrupt or incompatible file must never reach the user as an error
        logger.warning('Could not load recommender model version %s from %s', version.version, folder, exc_info=True)
        return None
    return LoadedModel(version=version, vectoriser=vectoriser, collaborative=collaborative)


def _refresh(now):
    """Look for a newer model, load it if there is one, and keep serving the old one if it cannot be read."""
    _state['checked_at'] = now
    try:
        latest = RecommenderModelVersion.objects.order_by('-version').first()
    except Exception:  # for example the table does not exist yet
        logger.warning('Could not look up the recommender model version', exc_info=True)
        return
    if latest is None:
        _state.update(loaded_id=None, model=None)
    elif latest.id != _state['loaded_id']:
        loaded = load(latest)
        if loaded is not None:
            _state.update(loaded_id=latest.id, model=loaded)
        # If the newest model cannot be read, the previous one (if any) keeps serving, and this is tried
        # again when the cache time is up.


def current_model():
    """The loaded model, or None. Cheap on almost every call: it only looks again after the cache time."""
    now = time.monotonic()
    with _lock:
        checked = _state['checked_at']
        if checked is None or now - checked >= settings.RECOMMENDER_MODEL_CACHE_SECONDS:
            _refresh(now)
        return _state['model']


def availability():
    """Whether recommendations can be served, and if not, why: switched off, or no usable model."""
    if not settings.RECOMMENDATIONS_ENABLED:
        return Availability(reason=DISABLED)
    model = current_model()
    if model is None:
        return Availability(reason=MODEL_UNAVAILABLE)
    return Availability(model=model)
