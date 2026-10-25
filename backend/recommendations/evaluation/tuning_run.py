"""
One tuning run from start to finish: load the split, fit on train, try all 240 combinations on the validation part,
decide, and write the report and the CSV. It never changes a setting: the report says what the settings should be,
and a person changes them.

There is no part to choose. Tuning looks at the validation part only.
"""

from dataclasses import dataclass
from datetime import date

from . import groups, modes, report, tuning, tuning_report
from .compare import DEFAULT_RANDOM_SEEDS
from .run import prepare_split, reports_folder


@dataclass
class TuningRun:
    markdown_path: object
    csv_path: object
    trials: list
    decision: tuning.Decision
    spread: dict
    evidence: dict
    suggested_bands: dict
    references: list
    recovery: dict  # planted data only, else None
    mode: str
    split: object
    split_how: str
    split_note: str


def run_tuning(
    include_synthetic=None, seed=42, random_seeds=DEFAULT_RANDOM_SEEDS, rebuild_split=False, data_dir=None,
    output_dir=None, command='tune_recommender',
):
    split, how, note, include_synthetic = prepare_split(include_synthetic, seed, rebuild_split, data_dir)
    context = tuning.build_context(split, include_synthetic, data_dir, seed)
    trials = tuning.run_grid(context)
    current = tuning.run_trial(context, tuning.current_setting())
    spread = tuning.random_spread(context, random_seeds)
    decision = tuning.decide(trials, current, spread['sd'], seed)
    evidence = tuning.band_evidence(context)
    suggested = tuning.suggested_bands(evidence)

    references = tuning.references(context, trials, decision)
    mode = modes.current_mode()
    recovery = None
    if mode == modes.SYNTHETIC_PLANTED:
        # The hidden groups are read only now, after every model has been fitted, and only to score them.
        from ..planted import read_ground_truth

        recovery = groups.recovery(context, read_ground_truth(), tuning.FACTORS)
    folder = reports_folder(data_dir, output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stem = report.next_stem(folder, prefix=modes.report_prefix('tuning', mode))
    markdown_path, csv_path = folder / f'{stem}.md', folder / f'{stem}.csv'
    text = tuning_report.build_markdown(
        split, context, trials, spread, decision, evidence, suggested, command, csv_path.name,
        date.today().isoformat(), mode, references, recovery,
    )
    markdown_path.write_text(text, encoding='utf-8')
    tuning_report.write_csv(csv_path, trials, decision)
    return TuningRun(
        markdown_path=markdown_path, csv_path=csv_path, trials=trials, decision=decision, spread=spread,
        evidence=evidence, suggested_bands=suggested, references=references, recovery=recovery, mode=mode,
        split=split, split_how=how, split_note=note,
    )
