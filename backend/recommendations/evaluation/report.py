"""
Writing an evaluation run to disk: a Markdown report people read and a CSV with every number in it.

Everything in a report is a measured number from the run it describes, with the split, the synthetic share and the
settings next to it. Nothing is rounded up or left out because it looks bad: every method is in the tables at every
K, the intervals are shown, and a method that could not run says why.

Test runs are special. The test part is the one honest estimate, so looking at it more than once defeats its purpose.
Every test run is appended to `evaluation-test-runs.csv` next to the reports, and every report says how many times the
test part has been looked at.

The files go to datasets/reports/, which is gitignored like the rest of datasets/.
"""

import csv
from datetime import date, datetime
from pathlib import Path

from .compare import COLLABORATIVE_METHODS, METHODS
from .modes import test_runs_name

TEST_RUN_COLUMNS = ['when', 'split_fingerprint', 'include_synthetic', 'seed', 'random_seeds', 'freelancers', 'report']

CSV_COLUMNS = [
    'part', 'relevance', 'group', 'method', 'k', 'metric', 'mean', 'ci_low', 'ci_high', 'freelancers',
    'random_sd', 'random_min', 'random_max', 'candidates_scored', 'right_answers_scored', 'note',
]

# More than this share of the scored part being synthetic triggers the warning at the top of the report.
MOSTLY_SYNTHETIC = 0.5

LABELS = {
    'random': 'Random',
    'popularity': 'Popularity',
    'content': 'Content only',
    'collaborative_applications': 'Collaborative, applications and hiring only',
    'collaborative_all': 'Collaborative, all interactions',
    'hybrid': 'Hybrid (current settings)',
}


def csv_rows(comparison, relevance):
    """Every number of one comparison as flat rows, one per group, method, K and metric."""
    rows = []
    for method in METHODS:
        result = comparison.results[method]
        if not result.available:
            rows.append({
                'part': comparison.part, 'relevance': relevance, 'group': 'all', 'method': method,
                'note': f'not available: {result.note}',
            })
            continue
        for group, summaries in result.groups.items():
            for (k, metric), summary in summaries.items():
                row = {
                    'part': comparison.part, 'relevance': relevance, 'group': group, 'method': method, 'k': k,
                    'metric': metric, 'mean': summary.mean, 'ci_low': summary.low, 'ci_high': summary.high,
                    'freelancers': summary.n,
                }
                spread = result.spread.get((k, metric)) if group == 'all' else None
                if spread:
                    row.update({'random_sd': spread.sd, 'random_min': spread.low, 'random_max': spread.high})
                if method in COLLABORATIVE_METHODS:
                    row.update({'candidates_scored': result.coverage, 'right_answers_scored': result.relevant_coverage})
                rows.append(row)
    return rows


def write_csv(path, comparisons):
    """Write the rows of each (comparison, relevance label) pair to one CSV file."""
    with open(path, 'w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for comparison, relevance in comparisons:
            for row in csv_rows(comparison, relevance):
                writer.writerow(row)


def read_test_runs(folder, mode=None):
    """The test runs recorded so far, oldest first. Empty if the test part has never been scored."""
    path = Path(folder) / test_runs_name(mode)
    if not path.is_file():
        return []
    with open(path, newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def record_test_run(folder, row, mode=None):
    """Append one test run to the log. This is called before the report is written, so the report counts it."""
    path = Path(folder) / test_runs_name(mode)
    new_file = not path.is_file()
    with open(path, 'a', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=TEST_RUN_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow({column: row.get(column, '') for column in TEST_RUN_COLUMNS})


def next_stem(folder, day=None, prefix='evaluation'):
    """evaluation-YYYY-MM-DD, or with -2, -3 and so on if a report from today is already there."""
    folder = Path(folder)
    stem = f'{prefix}-{(day or date.today()).isoformat()}'
    candidate, extra = stem, 2
    while (folder / f'{candidate}.md').exists() or (folder / f'{candidate}.csv').exists():
        candidate = f'{stem}-{extra}'
        extra += 1
    return candidate


def now_text():
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def cell(summary):
    """A mean with its 95% interval, to three places."""
    return f'{summary.mean:.3f} ({summary.low:.3f} to {summary.high:.3f})'


def plain(summary):
    return f'{summary.mean:.3f}'


def share(part, whole):
    return f'{part / whole:.0%}' if whole else 'n/a'


def mostly_synthetic(comparison):
    """True when more than half of the scored part's applications are synthetic."""
    info = comparison.info
    return bool(info['positives']) and info['synthetic_positives'] / info['positives'] > MOSTLY_SYNTHETIC


def results_table(comparison, columns, group='all', interval=True):
    """
    Markdown table lines with one row per method and a column for each (k, metric). A method that could not run
    says so in its row. A group with nobody in it has no table.
    """
    names = {'precision': 'Precision', 'recall': 'Recall', 'f1': 'F1', 'hit': 'Hit rate'}
    lines = [
        '| Method | ' + ' | '.join(f'{names[metric]}@{k}' for k, metric in columns) + ' |',
        '|---|' + '---|' * len(columns),
    ]
    for method in METHODS:
        result = comparison.results[method]
        if not result.available:
            lines.append(f'| {LABELS[method]} | not available: {result.note} |' + ' |' * (len(columns) - 1))
            continue
        summaries = result.groups.get(group, {})
        if not summaries:
            continue
        lines.append(
            f'| {LABELS[method]} | '
            + ' | '.join(cell(summaries[key]) if interval else plain(summaries[key]) for key in columns) + ' |'
        )
    return lines


def metric_columns(ks, metrics_wanted):
    return [(k, metric) for metric in metrics_wanted for k in ks]

