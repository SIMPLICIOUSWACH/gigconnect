"""
The text and CSV of a tuning run. Every combination that was tried is in the CSV with its validation result, and the
report says what was tried, what was left alone, how the choice was made and what it decided, whichever way it went.
"""

import csv
from statistics import median

from django.conf import settings

from . import modes
from . import split as ev
from . import tuning as tn
from .report import share

METRIC_NAMES = ('precision', 'recall', 'f1', 'hit')
CSV_COLUMNS = [
    'rank', 'max_weight', 'ramp', 'factors', 'factors_used', 'cold_start', 'selection', 'is_current', 'is_best',
] + [f'{metric}_at_{k}' for k in tn.KS for metric in METRIC_NAMES]


def rank_of(trials):
    """{index: rank} with 1 for the highest selection value. Equal values share a rank."""
    order = sorted(set(round(t.selection, 12) for t in trials), reverse=True)
    position = {value: place for place, value in enumerate(order, start=1)}
    return {index: position[round(t.selection, 12)] for index, t in enumerate(trials)}


def csv_rows(trials, decision):
    ranks = rank_of(trials)
    rows = []
    for index, trial in enumerate(trials):
        row = {
            'rank': ranks[index], 'max_weight': trial.setting.max_weight, 'ramp': trial.setting.ramp,
            'factors': trial.setting.factors, 'factors_used': trial.components,
            'cold_start': trial.setting.cold_start, 'selection': trial.selection,
            'is_current': trial.key() == decision.current.key(),
            'is_best': trial.key() == decision.best.key(),
        }
        for k in tn.KS:
            for metric in METRIC_NAMES:
                row[f'{metric}_at_{k}'] = trial.means[(k, metric)]
        rows.append(row)
    return rows


def write_csv(path, trials, decision):
    with open(path, 'w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(csv_rows(trials, decision))


def describe_setting(trial):
    s = trial.setting
    used = trial.components if trial.components else 'no'
    return (
        f'largest weight {s.max_weight:g}, ramp {s.ramp}, {used} factors (asked for {s.factors}), '
        f'cold start below {s.cold_start}'
    )


def marginal_lines(trials):
    """The average selection value for each value of each parameter, so the trend is visible."""
    positive = [t for t in trials if t.setting.max_weight > 0]
    lines = [
        '## What each setting does on average', '',
        'The average selection value (mean of F1@5 and F1@10) over every combination with that value. The ramp, '
        'the factors and the cold-start threshold only matter once the collaborative weight is above 0, so they '
        f'are averaged over the {len(positive)} combinations where it is.', '',
        '| Setting | Value | Average selection value |', '|---|---|---|',
    ]
    for value in tn.MAX_WEIGHTS:
        found = [t.selection for t in trials if t.setting.max_weight == value]
        if found:
            lines.append(f'| Largest collaborative weight | {value:g} | {sum(found) / len(found):.3f} |')
    parameters = (
        ('Ramp (gigs)', 'ramp', tn.RAMPS), ('Factors', 'factors', tn.FACTORS),
        ('Cold-start threshold', 'cold_start', tn.COLD_STARTS),
    )
    for label, attribute, values in parameters:
        for value in values:
            found = [t.selection for t in positive if getattr(t.setting, attribute) == value]
            if found:
                lines.append(f'| {label} | {value} | {sum(found) / len(found):.3f} |')
    return lines + ['']


def results_lines(decision):
    lines = [
        '| | Precision@5 | Precision@10 | Recall@5 | Recall@10 | F1@5 | F1@10 | Hit rate@10 |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for label, trial in (('Current settings', decision.current), ('Best combination', decision.best)):
        m = trial.means
        cells = [m[(5, 'precision')], m[(10, 'precision')], m[(5, 'recall')], m[(10, 'recall')],
                 m[(5, 'f1')], m[(10, 'f1')], m[(10, 'hit')]]
        lines.append(f'| {label} | ' + ' | '.join(f'{value:.3f}' for value in cells) + ' |')
    return lines


def band_lines(evidence, suggested):
    lines = [
        '## Match band cut-offs', '',
        'A band is shown to a client only when the applicant really shares a skill with the gig. The cut-offs are '
        'read from the content scores of pairs that share a skill, as they were in Sprint 5: the median for "good" '
        'and the 90th percentile for "strong". The scores here come from a vectoriser fitted on the train part '
        'only.', '',
        '| Pairs sharing a skill | Count | Median | 75th | 90th | 95th |', '|---|---|---|---|---|---|',
    ]
    rows = (
        ('Every candidate gig of a validation freelancer', 'candidates'), ('Only gigs they applied to', 'applicants'),
    )
    for label, key in rows:
        q = evidence[key]
        if q['n']:
            found = ' | '.join(f'{q[name]:.3f}' for name in ('p50', 'p75', 'p90', 'p95'))
            lines.append(f'| {label} | {q["n"]} | {found} |')
        else:
            lines.append(f'| {label} | 0 | n/a | n/a | n/a | n/a |')
    lines += [
        '',
        f'- Current cut-offs: good {settings.RECOMMENDER_BAND_GOOD}, strong {settings.RECOMMENDER_BAND_STRONG}.',
    ]
    if suggested:
        lines.append(f'- Re-derived from the first row: good {suggested["good"]}, strong {suggested["strong"]}.')
    else:
        lines.append('- There are no pairs sharing a skill, so nothing can be re-derived.')
    lines += [
        '- **These stay provisional.** The data is mostly synthetic, and the applications in it were generated to '
        'follow skills. The second row is shown because people who apply lean towards gigs that suit them, so '
        'their scores run higher.', '',
    ]
    return lines


def warning_lines(split_counts, mode=modes.SKILL_OVERLAP):
    synthetic, total = split_counts['synthetic'], split_counts['positives']
    if mode == modes.SYNTHETIC_PLANTED:
        return list(modes.PLANTED_WARNING)
    if not total or synthetic / total <= 0.5:
        return []
    return [
        f'> **Warning: this is mostly synthetic data.** {synthetic} of the {total} applications in the validation '
        f'part are synthetic ({share(synthetic, total)}). Tuning on it tunes to the rules the seed generator used.',
        '> Skill-preferring synthetic applications favour the content model by construction, so a setting that '
        'favours content is expected to win.',
        '> Do not read the winner as what is best for real freelancers. Run this again when there is real data.',
        '',
    ]


def method_lines(split, context, trials, counts, command, csv_name):
    capped = context.collaborative.get(tn.CAP)
    return [
        '## What was run', '',
        f'- Command: `{command}`',
        f'- Split: fingerprint `{split.fingerprint()}`, seed {split.seed}. Only the **validation** part was scored. '
        'The test part was not used and cannot be reached from this command.',
        f'- Freelancers scored: {len(context.cases)}, with {counts["positives"]} right answers.',
        f'- Every one of the {len(trials)} combinations is in `{csv_name}` with its validation result.', '',
        '## What was tuned, and what was not', '',
        f'- Largest collaborative weight: {", ".join(f"{v:g}" for v in tn.MAX_WEIGHTS)}.',
        f'- Ramp, the gigs it takes to reach that weight: {", ".join(str(v) for v in tn.RAMPS)}.',
        '- Hidden factors in the collaborative model: 2, 5, 10 and the cap, which is half the smaller side of the '
        f'matrix ({capped.n_components if capped else "n/a"} here).',
        '- Cold-start threshold, the different gigs below which only the content score is used: '
        f'{", ".join(str(v) for v in tn.COLD_STARTS)}.',
        '- That is 5 x 3 x 4 x 4 = 240 combinations, all scored on the same validation candidates as the '
        'evaluation report.',
        '- **Not tuned: the interaction weights** (view, click, save, apply and the application statuses). With '
        f'{counts["positives"]} right answers over {len(context.cases)} freelancers, changing four or more numbers '
        'to fit them would be overfitting.', '',
        '## How the choice is made', '',
        'Fixed before any result was looked at. A combination is scored by the average, over freelancers, of F1@5 '
        'and F1@10 on the validation part. The live defaults change only if the best combination beats the current '
        'settings by more than the random baseline moves from seed to seed, AND the 95% bootstrap interval of the '
        'paired difference over freelancers lies wholly above zero. Ties go to the combination closest to the '
        'current settings. The best of 240 is optimistic by construction, which is why the rule asks for more than '
        'a gain.', '',
    ]


def result_lines(trials, spread, decision):
    lines = [
        '## Result', '', *results_lines(decision), '',
        f'- Current settings: {describe_setting(decision.current)}.',
        f'- Best combination: {describe_setting(decision.best)}.',
        f'- Random baseline, selection value: {spread["mean"]:.3f} on average, standard deviation '
        f'{spread["sd"]:.3f} over {spread["seeds"]} seeds (lowest {spread["low"]:.3f}, highest {spread["high"]:.3f}).',
        *[f'- {reason}' for reason in decision.reasons], '',
        f'- Combinations that beat the current settings by more than the random spread: '
        f'{decision.beat_by_more_than_luck} of {len(trials)}.',
        f'- Combinations within the random spread of the best: {decision.within_luck_of_best} of {len(trials)}, so '
        'many of them cannot be told apart from it.',
        f'- Across all {len(trials)}: lowest {min(t.selection for t in trials):.3f}, median '
        f'{median(t.selection for t in trials):.3f}, highest {max(t.selection for t in trials):.3f}.', '',
        '### Best combination for each largest collaborative weight', '',
        'With a largest weight of 0 the collaborative score is never used, so the other settings make no '
        'difference and many combinations tie. The first one is shown.', '',
        '| Largest weight | Ramp | Factors used | Cold start below | Selection value |', '|---|---|---|---|---|',
    ]
    for value in tn.MAX_WEIGHTS:
        found = [t for t in trials if t.setting.max_weight == value]
        t = max(found, key=lambda trial: round(trial.selection, 12))
        lines.append(
            f'| {value:g} | {t.setting.ramp} | {t.components} | {t.setting.cold_start} | {t.selection:.3f} |'
        )
    return lines + ['']


def reference_lines(references):
    lines = [
        '## Content only, collaborative only and the hybrids', '',
        'Points to read the combinations against, on the same validation candidates. Collaborative only ranks by the '
        'collaborative score alone; a gig it cannot score goes to the back.', '',
        '| | Precision@5 | Precision@10 | Recall@10 | F1@5 | F1@10 | Hit rate@10 | Selection value |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for reference in references:
        if not reference.means:
            lines.append(f'| {reference.label} | | | | | | | |')
            continue
        m = reference.means
        cells = [m[(5, 'precision')], m[(10, 'precision')], m[(10, 'recall')], m[(5, 'f1')], m[(10, 'f1')],
                 m[(10, 'hit')], reference.selection]
        lines.append(f'| {reference.label} | ' + ' | '.join(f'{value:.3f}' for value in cells) + ' |')
    return lines + ['']


def recovery_lines(recovery):
    if not recovery:
        return []
    groups = sorted(recovery['rows'][0]['per_group']) if recovery['rows'] else []
    mean, sd = recovery['chance']
    lines = [
        '## Hidden group recovery (planted data only)', '',
        'For every pair of freelancers, the cosine similarity of their vectors. The pair AUC is the chance that two '
        'freelancers from the same hidden group are more alike than two from different groups: 0.5 is chance. The '
        'per-group columns compare pairs inside that group with pairs that have one member in it. The groups were read '
        'from the ground truth file only after every model was fitted. '
        f'Over {recovery["freelancers"]} freelancers.', '',
        '| Vectors | Pair AUC | ' + ' | '.join(groups) + ' |', '|---|---|' + '---|' * len(groups),
    ]
    for row in recovery['rows']:
        cells = [row['per_group'][g] for g in groups]
        lines.append(
            f'| {row["label"]} | {row["auc"]:.3f} | '
            + ' | '.join('n/a' if value is None else f'{value:.3f}' for value in cells) + ' |'
        )
    lines += ['', f'- Shuffled labels (chance): {mean:.3f}, standard deviation {sd:.3f}.', '']
    return lines


PLANTED_DEFAULTS_NOTE = (
    '- **Planted data never sets the live defaults.** Whatever the rule says here, the live settings are decided '
    'from the skill-overlap data.'
)


LIMIT_LINES = [
    '## Limits', '',
    '- Only one split was used. A different split could rank the combinations differently.',
    '- The models are fitted on the train part only and the choice is made on validation, so validation is no '
    'longer a clean estimate. The test part is the only clean one, and it is used once, after this.',
    '- Skills and bios are read as they are today, and each freelancer has their own cut-off (see the evaluation '
    'report).',
    '',
]


def build_markdown(
    split, context, trials, spread, decision, evidence, suggested, command, csv_name, day, mode=modes.SKILL_OVERLAP,
    references=(), recovery=None,
):
    counts = ev.describe(split)[ev.VALIDATION]
    lines = [
        f'# Tuning on the validation part, {day}', '', *modes.label_lines(mode), *modes.profile_lines(),
        *warning_lines(counts, mode),
    ]
    lines += method_lines(split, context, trials, counts, command, csv_name)
    lines += result_lines(trials, spread, decision)
    if mode == modes.SYNTHETIC_PLANTED:
        lines += [PLANTED_DEFAULTS_NOTE, '']
    if references:
        lines += reference_lines(references)
    lines += recovery_lines(recovery)
    lines += marginal_lines(trials)
    lines += band_lines(evidence, suggested)
    lines += LIMIT_LINES
    return '\n'.join(lines) + '\n'
