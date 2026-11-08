"""
What the admin Recommender page shows: the active profile, the model in use and its settings, and the latest
evaluation scores if a report has been written. Read only: training and tuning stay management commands.
"""

import csv
from pathlib import Path

from django.conf import settings

from recommendations.evaluation import modes
from recommendations.models import RecommenderModelVersion

# The evaluation report has a row per method, cutoff and metric. The page shows these.
REPORT_K = '10'
REPORT_METRICS = ('precision', 'recall', 'hit')
REPORT_METHODS = ('hybrid', 'content', 'popularity', 'random')


def recommender_overview():
    version = RecommenderModelVersion.objects.order_by('-version').first()
    return {
        'profile': {
            'name': settings.RECOMMENDER_PROFILE,
            'label': settings.RECOMMENDER_PROFILE_LABEL,
            'is_demo': settings.RECOMMENDER_PROFILE == 'demo',
            'database': settings.DATABASES['default']['NAME'],
            'recommendations_enabled': settings.RECOMMENDATIONS_ENABLED,
        },
        'model': _model(version),
        'settings': {
            'blend_max_weight': settings.RECOMMENDER_BLEND_MAX_WEIGHT,
            'blend_ramp_gigs': settings.RECOMMENDER_BLEND_RAMP_GIGS,
            'cold_start_min_gigs': settings.RECOMMENDER_COLD_START_MIN_GIGS,
            'svd_components': settings.RECOMMENDER_SVD_COMPONENTS,
            'band_good': settings.RECOMMENDER_BAND_GOOD,
            'band_strong': settings.RECOMMENDER_BAND_STRONG,
            'include_synthetic': settings.RECOMMENDER_INCLUDE_SYNTHETIC,
        },
        'evaluation': latest_evaluation(),
    }


def _model(version):
    if version is None:
        return None
    return {
        'version': version.version,
        'trained_at': version.trained_at,
        'include_synthetic': version.include_synthetic,
        'platform_gigs': version.platform_gigs,
        'synthetic_platform_gigs': version.synthetic_platform_gigs,
        'external_documents': version.external_documents,
        'freelancers': version.freelancers,
        'interactions': version.interactions,
        'collaborative_fitted': version.collaborative_fitted,
        'collaborative_skipped_reason': version.collaborative_skipped_reason,
    }


def latest_evaluation(folder=None):
    """The newest evaluation report for the current data mode, summarised, or None if there isn't one."""
    folder = Path(folder or Path(settings.RECOMMENDER_DATA_DIR) / 'reports')
    prefix = modes.report_prefix('evaluation')
    if not folder.is_dir():
        return None
    reports = [
        path for path in folder.glob(f'{prefix}-*.csv')
        if not path.stem.endswith('test-runs') and _is_report_of_mode(path.stem, prefix)
    ]
    if not reports:
        return None
    newest = max(reports, key=lambda path: path.stat().st_mtime)
    with open(newest, newline='', encoding='utf-8-sig') as handle:
        rows = [
            row for row in csv.DictReader(handle)
            if row['group'] == 'all' and row['relevance'] == 'applied' and row['k'] == REPORT_K
            and row['metric'] in REPORT_METRICS and row['method'] in REPORT_METHODS
        ]
    if not rows:
        return None
    return {
        'report': newest.name,
        'part': rows[0]['part'],
        'k': int(REPORT_K),
        'freelancers': _int(rows[0]['freelancers']),
        'scores': [
            {
                'method': row['method'], 'metric': row['metric'], 'mean': _float(row['mean']),
                'ci_low': _float(row['ci_low']), 'ci_high': _float(row['ci_high']),
            }
            for row in rows
        ],
    }


def _is_report_of_mode(stem, prefix):
    """evaluation-2026-10-25 belongs to the ordinary mode, not evaluation-synthetic_planted-2026-10-25."""
    rest = stem[len(prefix) + 1:]
    return rest[:1].isdigit()


def _float(text):
    return float(text) if text not in ('', None) else None


def _int(text):
    return int(text) if text not in ('', None) else None
