"""
What the recommender is allowed to learn from and be scored on, as one dictionary of counts and fingerprints.

enrich_sample_data and seed_showcase add a lot of rows. This is how the project proves they changed nothing the
reported results rest on: take a snapshot before, take another after, and they must be equal. Everything here is
read-only, and nothing is trained or saved.

What it covers: the training sets the platform rules allow (freelancers, gigs, interactions, applications), the
positives and the evaluation split built from them (and the fingerprint of that split), the collaborative model's
training weights and the gigs its vocabulary is fitted on, the saved split on disk and whether it still matches the
data, and the trained model version in use.
"""

import hashlib

from recommendations.evaluation import split as ev
from recommendations.evaluation.training_input import training_input, vectoriser_gig_ids
from recommendations.models import RecommenderModelVersion
from recommendations.platform import (
    applications_for_training,
    freelancers_for_training,
    gigs_for_training,
    interactions_for_training,
)

SEED = 42


def _hash(items):
    return hashlib.sha256('\n'.join(sorted(str(item) for item in items)).encode()).hexdigest()[:16]


def training_snapshot(include_synthetic=True, saved_split_directory=None, check_saved=True):
    """
    The numbers that must not move. `check_saved` also reads the saved evaluation split (the default place, or
    `saved_split_directory`) and says whether its fingerprint still matches the current applications.
    """
    freelancers = list(freelancers_for_training(include_synthetic).values_list('user_id', flat=True))
    gigs = list(gigs_for_training(include_synthetic).values_list('id', flat=True))
    interactions = list(interactions_for_training(include_synthetic).values_list('id', flat=True))
    applications = list(applications_for_training(include_synthetic).values_list('id', flat=True))

    positives = ev.load_positives(include_synthetic)
    split = ev.build_split(positives, seed=SEED, include_synthetic=include_synthetic)
    weights = training_input(split, include_synthetic).weights
    sizes = {part: len(split.in_part(part)) for part in (ev.TRAIN, ev.VALIDATION, ev.TEST)}

    snapshot = {
        'freelancers_for_training': len(freelancers),
        'gigs_for_training': len(gigs),
        'interactions_for_training': len(interactions),
        'applications_for_training': len(applications),
        'positives': len(positives),
        'split_train': sizes[ev.TRAIN],
        'split_validation': sizes[ev.VALIDATION],
        'split_test': sizes[ev.TEST],
        'evaluated_freelancers': len(split.evaluated_freelancers()),
        'split_fingerprint': split.fingerprint(),
        'training_pairs': len(weights),
        'training_weights_hash': _hash(f'{key}={round(float(value), 6)}' for key, value in weights.items()),
        'vectoriser_gigs': len(vectoriser_gig_ids(split, include_synthetic)),
        'freelancer_ids_hash': _hash(freelancers),
        'gig_ids_hash': _hash(gigs),
        'interaction_ids_hash': _hash(interactions),
        'application_ids_hash': _hash(applications),
        'model_versions': RecommenderModelVersion.objects.count(),
        'latest_model_version': getattr(RecommenderModelVersion.objects.order_by('-version').first(), 'version', None),
    }
    if check_saved:
        saved = ev.load_split(saved_split_directory)
        snapshot['saved_split_fingerprint'] = saved.fingerprint() if saved else None
        snapshot['saved_split_matches_data'] = bool(saved) and saved.fingerprint() == snapshot['split_fingerprint']
    return snapshot


def differences(before, after):
    """{key: (before, after)} for every number that changed. Empty means the training world is identical."""
    return {key: (before[key], after.get(key)) for key in before if before[key] != after.get(key)}


def format_snapshot(snapshot):
    width = max(len(key) for key in snapshot)
    return '\n'.join(f'  {key.ljust(width)}  {value}' for key, value in snapshot.items())
