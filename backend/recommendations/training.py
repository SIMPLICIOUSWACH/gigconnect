"""
Training the recommender: fit both models, save them, and record what they were trained on.

The order matters. The files are written to a temporary folder and renamed into place, and the database
row (RecommenderModelVersion) is written last, so anything that finds a row can rely on its files being
there. A run that fails part way leaves no row and so changes nothing for the app.

Trained files are loaded with joblib, which uses pickle. They are only ever read from the folder this
code wrote them to (RECOMMENDER_ARTIFACT_DIR), never from anywhere a user can upload to.
"""

import json
import shutil
from datetime import date
from pathlib import Path

import joblib
from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from . import collaborative as collab
from . import content, corpus, snapshot
from .evaluation import modes
from .features import drop_empty_and_duplicates
from .models import RecommenderModelVersion
from .platform import (
    applications_for_training,
    freelancers_for_training,
    gigs_for_training,
    interactions_for_training,
)

VECTORISER_FILE = 'vectoriser.joblib'
COLLABORATIVE_FILE = 'collaborative.joblib'
METADATA_FILE = 'metadata.json'


class TrainingError(Exception):
    """Training could not run. The message says why in plain language."""


def folder_name(version):
    return f'v{version:04d}'


def read_external_corpus(data_dir):
    """The cleaned external job postings, or an empty list if import_job_corpus has not been run."""
    path = Path(data_dir) / 'processed' / 'combined_corpus.csv'
    return corpus.read_processed_texts(path) if path.is_file() else []


def build_platform_documents(gigs):
    """Each gig's cleaned document with empty and duplicate ones removed, and a count of what was dropped."""
    records, dropped = drop_empty_and_duplicates(snapshot.platform_documents(gigs))
    return records, dropped


def save_artifacts(artifact_dir, folder, vectoriser, collaborative_model, metadata):
    """Write the model files to a temporary folder, then move it into place in one step."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    temporary = artifact_dir / f'{folder}.tmp'
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    joblib.dump(vectoriser, temporary / VECTORISER_FILE)
    if collaborative_model is not None:
        joblib.dump(collaborative_model, temporary / COLLABORATIVE_FILE)
    (temporary / METADATA_FILE).write_text(json.dumps(metadata, indent=2, default=str), encoding='utf-8')
    final = artifact_dir / folder
    if final.exists():
        shutil.rmtree(final)
    temporary.rename(final)
    return final


def train(include_synthetic=None, data_dir=None, artifact_dir=None, log=None):
    """
    Train both models on the data the recommender is allowed to use and return the new RecommenderModelVersion.

    include_synthetic defaults to the RECOMMENDER_INCLUDE_SYNTHETIC setting. Raises TrainingError if there
    is nothing to train on. If there is too little interaction data for the collaborative model, that
    model is skipped, the reason is recorded, and the content model still works.
    """
    log = log or (lambda message: None)
    include_synthetic = settings.RECOMMENDER_INCLUDE_SYNTHETIC if include_synthetic is None else include_synthetic
    data_dir = Path(data_dir or settings.RECOMMENDER_DATA_DIR)
    artifact_dir = Path(artifact_dir or settings.RECOMMENDER_ARTIFACT_DIR)

    gigs = list(gigs_for_training(include_synthetic))
    profiles = list(freelancers_for_training(include_synthetic))
    documents, dropped = build_platform_documents(gigs)
    external = read_external_corpus(data_dir)
    log(f'Gigs: {len(gigs)} ({len(documents)} usable). Freelancers: {len(profiles)}.')
    log(f'External job postings: {len(external)}.')
    if not external:
        log('No external corpus found in processed/combined_corpus.csv, so the vocabulary is fitted on gigs only.')

    try:
        vectoriser = content.fit_vectoriser([record['clean_text'] for record in documents], external)
    except ValueError as error:
        raise TrainingError(f'The content model could not be fitted: {error}') from error

    weights = collab.load_weights(include_synthetic)
    real_pairs = set(collab.load_weights(include_synthetic=False)) if include_synthetic else set(weights)
    synthetic_pairs = len(set(weights) - real_pairs)
    collaborative_model, skipped_reason = None, ''
    try:
        collaborative_model = collab.fit(weights)
        log(f'Collaborative model fitted: {collaborative_model.n_components} factors on {len(weights)} pairs.')
    except collab.NotEnoughData as error:
        skipped_reason = str(error)
        log(f'Collaborative model skipped: {skipped_reason}.')

    parameters = {
        'platform_share': settings.RECOMMENDER_PLATFORM_SHARE,
        'tfidf_min_df': settings.RECOMMENDER_TFIDF_MIN_DF,
        'tfidf_max_df': settings.RECOMMENDER_TFIDF_MAX_DF,
        'svd_components_wanted': settings.RECOMMENDER_SVD_COMPONENTS,
        'svd_components_used': collaborative_model.n_components if collaborative_model else None,
        'svd_explained_variance': collaborative_model.explained_variance if collaborative_model else None,
        'interaction_weights': settings.RECOMMENDER_INTERACTION_WEIGHTS,
        'application_weights': settings.RECOMMENDER_APPLICATION_WEIGHTS,
        'cold_start_min_gigs': settings.RECOMMENDER_COLD_START_MIN_GIGS,
        'blend_ramp_gigs': settings.RECOMMENDER_BLEND_RAMP_GIGS,
        'blend_max_weight': settings.RECOMMENDER_BLEND_MAX_WEIGHT,
        'random_seed': settings.RECOMMENDER_RANDOM_SEED,
        'platform_documents_dropped': dropped,
    }

    with transaction.atomic():
        latest = RecommenderModelVersion.objects.aggregate(latest=Max('version'))['latest'] or 0
        version = latest + 1
        folder = folder_name(version)
        metadata = {'version': version, 'trained_at': timezone.now().isoformat(), 'parameters': parameters}
        save_artifacts(artifact_dir, folder, vectoriser, collaborative_model, metadata)
        row = RecommenderModelVersion.objects.create(
            version=version,
            folder=folder,
            include_synthetic=include_synthetic,
            platform_gigs=len(documents),
            synthetic_platform_gigs=sum(1 for record in documents if record['is_synthetic']),
            external_documents=len(external),
            vocabulary_size=len(vectoriser.vocabulary_),
            freelancers=len(profiles),
            collaborative_fitted=collaborative_model is not None,
            collaborative_skipped_reason=skipped_reason[:300],
            interactions=len(weights),
            synthetic_interactions=synthetic_pairs,
            collaborative_scale=collaborative_model.scale if collaborative_model else None,
            parameters=parameters,
        )

    counts = snapshot.write_snapshot(
        data_dir, gigs, profiles,
        interactions_for_training(include_synthetic), applications_for_training(include_synthetic),
    )
    report = write_report(data_dir, row, counts)
    log(f'Saved model version {row.version} to {artifact_dir / folder}.')
    log(f'Report: {report}')
    return row


def write_report(data_dir, row, snapshot_counts):
    """A short Markdown report of the training run, with measured numbers only."""
    folder = Path(data_dir) / 'reports'
    folder.mkdir(parents=True, exist_ok=True)
    stem = f'{modes.report_prefix("training")}-{date.today().isoformat()}'
    path = folder / f'{stem}.md'
    extra = 2
    while path.exists():
        path = folder / f'{stem}-{extra}.md'
        extra += 1

    params = row.parameters
    lines = [
        f'# Training run, model version {row.version}',
        '',
        *modes.label_lines(modes.current_mode()),
        *modes.profile_lines(),
        f'- Models saved in: {settings.RECOMMENDER_ARTIFACT_DIR}',
        f'- Snapshot written to: {Path(data_dir) / settings.RECOMMENDER_SNAPSHOT_FOLDER}',
        f'- Trained at: {row.trained_at:%Y-%m-%d %H:%M}',
        f'- Synthetic data included: {"yes" if row.include_synthetic else "no"}',
        '',
        '## Content model',
        '',
        f'- Platform gigs used: {row.platform_gigs} ({row.synthetic_platform_gigs} synthetic, '
        f'{row.synthetic_gig_share:.0%})',
        f'- Platform gigs dropped as empty or duplicate: {params["platform_documents_dropped"]}',
        f'- External job postings fitted on: {row.external_documents}',
        f'- Vocabulary size: {row.vocabulary_size} words',
        f'- Platform share of the fitted documents (target): {params["platform_share"]}',
        f'- Words kept if in at least {params["tfidf_min_df"]} documents and at most {params["tfidf_max_df"]} of them',
        '',
        '## Collaborative model',
        '',
        f'- Freelancers in the data: {row.freelancers}',
        f'- Freelancer and gig pairs with an interaction: {row.interactions} '
        f'({row.synthetic_interactions} synthetic, {row.synthetic_interaction_share:.0%})',
    ]
    if row.collaborative_fitted:
        lines += [
            '- Status: fitted',
            f'- Factors used: {params["svd_components_used"]} (up to {params["svd_components_wanted"]} wanted)',
            f'- Share of the matrix the factors explain: {params["svd_explained_variance"]:.1%}',
            f'- Raw score scaled to 1.0: {row.collaborative_scale:.4f}',
        ]
    else:
        lines += ['- Status: skipped', f'- Reason: {row.collaborative_skipped_reason}']
    lines += [
        '',
        '## Blending',
        '',
        f'- Content scores only below {params["cold_start_min_gigs"]} different gigs interacted with',
        f'- Then the collaborative weight rises over the next {params["blend_ramp_gigs"]} gigs '
        f'to {params["blend_max_weight"]}',
        '',
        '## Snapshot written to datasets/platform/',
        '',
    ]
    lines += [f'- {name}.csv: {count} rows' for name, count in snapshot_counts.items()]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path
