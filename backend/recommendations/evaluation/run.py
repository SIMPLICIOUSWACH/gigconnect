"""
One evaluation run from start to finish: load or build the split, fit the models on train, score a held-out part,
and write the report and the CSV.

The test part is guarded. Scoring it needs `final=True`, it is only scored after tuning is finished, and every
look at it is recorded (see report.py). The guard is here and not only in the command, so no other caller can
score the test part by accident.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from django.conf import settings

from ..models import RecommenderModelVersion
from . import report, report_markdown
from . import split as ev
from .compare import DEFAULT_RANDOM_SEEDS, Comparison, compare
from .fitting import EvaluationError, FittedModels, fit_models


@dataclass
class EvaluationRun:
    markdown_path: Path
    csv_path: Path
    comparison: Comparison
    strict: Comparison
    split: ev.Split
    models: FittedModels
    split_how: str
    split_note: str


def reports_folder(data_dir=None, output_dir=None):
    return Path(output_dir) if output_dir else Path(data_dir or settings.RECOMMENDER_DATA_DIR) / 'reports'


def prepare_split(include_synthetic, seed, rebuild_split, data_dir):
    """
    The split to score, and a note if there is something to know about it. Returns (split, how, note,
    include_synthetic). Raises EvaluationError if nobody has enough applications to be scored.
    """
    if include_synthetic is None:
        include_synthetic = settings.RECOMMENDER_INCLUDE_SYNTHETIC
    split_directory = Path(data_dir) / 'platform' / 'evaluation' if data_dir else None
    split, how, note = ev.load_or_build(
        include_synthetic=include_synthetic, seed=seed, rebuild=rebuild_split, directory=split_directory,
    )
    if how == 'loaded':
        # A saved split is reused so results stay comparable, but it should not be reused without saying so when
        # the applications have changed since (new ones, reseeded ones, deleted accounts).
        current = ev.fingerprint(ev.load_positives(include_synthetic))
        if current != split.fingerprint():
            changed = (
                'The applications have changed since this split was saved, so it does not include the changes. '
                'Run with --rebuild-split to use the current data.'
            )
            note = f'{note} {changed}'.strip()
    if not split.evaluated_freelancers():
        raise EvaluationError(
            f'No freelancer has at least {split.min_positives} applications, so there is nothing to score. '
            'Seed or collect more applications and build the split again.'
        )
    return split, how, note, include_synthetic


def run_evaluation(
    part=ev.VALIDATION, final=False, include_synthetic=None, seed=42, random_seeds=DEFAULT_RANDOM_SEEDS,
    rebuild_split=False, data_dir=None, output_dir=None, command='evaluate_recommender',
):
    """Score one held-out part and write the report. Raises EvaluationError, with the reason, if it cannot run."""
    if part not in ev.HELD_OUT_PARTS:
        raise EvaluationError(f'Only the validation and test parts can be scored, not "{part}".')
    if part == ev.TEST and not final:
        raise EvaluationError(
            'The test part is only scored with --final, once, after tuning on the validation part is finished. '
            'Scoring it while tuning would make it useless as an honest estimate.'
        )
    split, how, note, include_synthetic = prepare_split(include_synthetic, seed, rebuild_split, data_dir)

    models = fit_models(split, include_synthetic, data_dir)
    comparison = compare(split, part, include_synthetic, random_seeds=random_seeds, models=models, seed=seed)
    strict = compare(split, part, include_synthetic, random_seeds=random_seeds, strict=True, models=models, seed=seed)

    folder = reports_folder(data_dir, output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stem = report.next_stem(folder)
    markdown_path, csv_path = folder / f'{stem}.md', folder / f'{stem}.csv'

    if part == ev.TEST:
        report.record_test_run(folder, {
            'when': report.now_text(), 'split_fingerprint': split.fingerprint(),
            'include_synthetic': include_synthetic, 'seed': seed, 'random_seeds': random_seeds,
            'freelancers': comparison.group_sizes['all'], 'report': markdown_path.name,
        })
    run = {
        'date': date.today().isoformat(), 'command': command, 'split_how': how, 'split_note': note,
        'csv_name': csv_path.name, 'test_runs': report.read_test_runs(folder),
        'live_version': RecommenderModelVersion.objects.order_by('-version').first(),
    }
    markdown_path.write_text(report_markdown.build_markdown(comparison, strict, split, models, run), encoding='utf-8')
    report.write_csv(csv_path, [(comparison, 'applied'), (strict, 'strict')])
    return EvaluationRun(
        markdown_path=markdown_path, csv_path=csv_path, comparison=comparison, strict=strict, split=split,
        models=models, split_how=how, split_note=note,
    )
