"""
The text of an evaluation report. Each section is a function that returns lines, so a section can be checked on its own.

No section hides a bad number: every method appears in every table, and anything that could not be measured says so.
"""

from django.conf import settings

from . import modes
from . import split as ev
from .compare import COLLABORATIVE_METHODS
from .report import LABELS, metric_columns, mostly_synthetic, results_table, share

HEADLINE_KS = (5, 10)
HEADLINE_METRICS = ('precision', 'recall', 'f1')
MIN_STRICT_FREELANCERS = 20  # below this the strict variant is shown with a warning, not as a finding


def warning_lines(comparison, mode=modes.SKILL_OVERLAP):
    """The warning at the top, and the synthetic share of the scored part either way."""
    info = comparison.info
    count, synthetic = info['positives'], info['synthetic_positives']
    line = (
        f'{synthetic} of the {count} applications in the {comparison.part} part are synthetic '
        f'({share(synthetic, count)}).'
    )
    if mode == modes.SYNTHETIC_PLANTED:
        return [f'Synthetic data: {line}', '', *modes.PLANTED_WARNING]
    if not mostly_synthetic(comparison):
        return [f'Synthetic data: {line}', '']
    return [
        '> **Warning: this is mostly synthetic data.** ' + line,
        '> Results on synthetic data mostly show the models recovering the rules the seed generator used, not real',
        '> relevance. The generator makes a freelancer apply to gigs that share one of their skills about five',
        '> times as often as to others, so **skill-preferring synthetic applications favour the content model by',
        '> construction**.',
        '> Do not quote these numbers as evidence that the recommender works for real freelancers.',
        '',
    ]


def run_lines(comparison, split, run):
    runs = run['test_runs']
    lines = ['## What was run', '', f'- Part scored: **{comparison.part}**.']
    if comparison.part == ev.TEST:
        lines.append(
            f'- **This is a test run.** The test part has now been scored {len(runs)} time(s), and every run is '
            'recorded in evaluation-test-runs.csv. Each look at the test part makes it less of an honest estimate.'
        )
    else:
        lines.append(f'- The test part has been scored {len(runs)} time(s) so far. This run did not look at it.')
    lines += [
        f'- Command: `{run["command"]}`',
        f'- Split: {run["split_how"]}, fingerprint `{split.fingerprint()}`, seed {split.seed}, at least '
        f'{split.min_positives} applications to be split.',
        f'- Synthetic data: {"included" if comparison.info["include_synthetic"] else "left out"}.',
        '- Averages are over freelancers, each with a 95% bootstrap interval (2000 resamples of the freelancers, '
        'fixed seed). An interval that overlaps another method\'s means the difference could be luck with this many '
        'freelancers.',
        f'- The random baseline is the average over {comparison.random_seeds} seeds.',
        f'- Every number is also in `{run["csv_name"]}`.',
    ]
    if run['split_note']:
        lines.append(f'- Note: {run["split_note"]}')
    return lines + ['']


def data_lines(comparison, split, models):
    counts = ev.describe(split)
    lines = [
        '## The data', '',
        'Relevant means the freelancer applied to the gig, whatever became of the application. Views and clicks are '
        'not relevance.', '',
        '| Part | Freelancers | Applications | Synthetic | Synthetic share | Shortlisted or hired |',
        '|---|---|---|---|---|---|',
    ]
    for part in (ev.TRAIN, ev.VALIDATION, ev.TEST):
        c = counts[part]
        lines.append(
            f'| {part} | {c["freelancers"]} | {c["positives"]} | {c["synthetic"]} | '
            f'{share(c["synthetic"], c["positives"])} | {c["strictly_relevant"]} |'
        )
    info = comparison.info
    sizes = info['candidates']
    lines += [
        '',
        f'- Freelancers who can be evaluated (at least {split.min_positives} applications): '
        f'{counts["evaluated_freelancers"]}. Freelancers with fewer stay in train only: '
        f'{counts["too_few_freelancers"]} freelancer(s) with {counts["too_few_positives"]} application(s) in all.',
        f'- Scored in the {comparison.part} part: {info["freelancers_in_part"]} freelancers, '
        f'{info["relevant"]} right answers, {info["unscorable_freelancers"]} with no skills or bio '
        '(they cannot be compared with any gig).',
    ]
    if sizes:
        lines.append(
            f'- Candidate gigs per freelancer: median {sizes["median"]:.0f} (smallest {sizes["smallest"]}, '
            f'largest {sizes["largest"]}), the same for every method. {info["outside_the_rules"]} right answer(s) fell '
            'outside the as-of rules and are included anyway.'
        )
    stats = models.stats
    everything = stats['training_input_all']
    lines += [
        '',
        '### What the models learned from', '',
        f'- Collaborative, all interactions: {stats["pairs_all"]} freelancer and gig pairs. '
        f'Of {everything["interactions_seen"]} '
        f'views, clicks and saves, {everything["interactions_kept"]} were kept, {everything["left_out_after_cutoff"]} '
        f'were left out for coming after the freelancer\'s cut-off and {everything["left_out_held_out_gig"]} for being '
        'about a gig held out for them. '
        f'{everything["statuses_taken_as_of_cutoff"]} application status(es) were taken as they were at the cut-off.',
        f'- Collaborative, applications and hiring only: {stats["pairs_applications"]} pairs.',
        f'- Content model: vocabulary fitted on {stats["vectoriser_gigs"]} platform gigs that existed before the '
        f'earliest cut-off and {stats["external_documents"]} external job postings, {stats["vocabulary_size"]} words.',
        '',
    ]
    return lines


def model_lines(models, live_version):
    lines = [
        '## Models and parameters', '',
        'These models were fitted for this evaluation on the train part only and were not saved. They are not a '
        'saved model version.',
        '',
    ]
    if live_version is None:
        lines.append('- There is no saved live model.')
    else:
        lines.append(
            f'- The live model, version {live_version.version}, was trained '
            f'{live_version.trained_at:%Y-%m-%d %H:%M} on all data and is not used here.'
        )
    lines += ['']
    for label, attribute, name in (
        ('Collaborative, applications and hiring only', 'collaborative_applications', 'applications'),
        ('Collaborative, all interactions', 'collaborative_all', 'all'),
    ):
        model = getattr(models, attribute)
        if model is None:
            lines.append(f'- {label}: **not fitted**. {models.skipped.get(name, "")}')
        else:
            lines.append(
                f'- {label}: fitted with {model.n_components} factors (up to {settings.RECOMMENDER_SVD_COMPONENTS} '
                f'wanted), explaining {model.explained_variance:.1%} of the matrix, {model.n_interactions} pairs.'
            )
    lines += [
        '',
        f'- Content model: platform share {settings.RECOMMENDER_PLATFORM_SHARE}, words kept if in at least '
        f'{settings.RECOMMENDER_TFIDF_MIN_DF} documents and at most {settings.RECOMMENDER_TFIDF_MAX_DF} of them.',
        f'- Interaction weights: {settings.RECOMMENDER_INTERACTION_WEIGHTS}. Application weights: '
        f'{settings.RECOMMENDER_APPLICATION_WEIGHTS}.',
        f'- Hybrid: content scores only below {settings.RECOMMENDER_COLD_START_MIN_GIGS} different gigs in training, '
        f'then the collaborative weight rises over {settings.RECOMMENDER_BLEND_RAMP_GIGS} gigs to '
        f'{settings.RECOMMENDER_BLEND_MAX_WEIGHT}. These are the live settings, not tuned.',
        f'- Random seed for fitting: {settings.RECOMMENDER_RANDOM_SEED}.',
        '',
    ]
    return lines


def headline_lines(comparison):
    columns = metric_columns(HEADLINE_KS, HEADLINE_METRICS)
    size = comparison.group_sizes['all']
    return [
        '## Headline results (K = 5 and 10)', '',
        f'Mean over {size} freelancers with a 95% bootstrap interval in brackets. Precision is the right answers in '
        'the first K divided by K, recall is the share of their right answers found in the first K, and F1 is worked '
        'out for each freelancer and then averaged.', '',
        *results_table(comparison, columns), '',
    ]


def supplementary_lines(comparison):
    columns = metric_columns((20,), HEADLINE_METRICS) + metric_columns((5, 10, 20), ('hit',))
    return [
        '## Supplementary: K = 20 and hit rate', '',
        'Hit rate is the share of freelancers with at least one right answer in the first K.', '',
        *results_table(comparison, columns), '',
    ]


def spread_lines(comparison):
    spread = comparison.results['random'].spread
    lines = [
        '## Random baseline: how far luck alone moves a result', '',
        f'Over {comparison.random_seeds} seeds, the all-freelancer average of the random baseline moved by this much. '
        'A difference between two methods that is smaller than this is not worth reading.', '',
        '| Metric | Standard deviation | Lowest seed | Highest seed |', '|---|---|---|---|',
    ]
    names = {'precision': 'Precision', 'recall': 'Recall', 'f1': 'F1', 'hit': 'Hit rate'}
    for k, metric in metric_columns(comparison.ks, ('precision', 'recall', 'f1', 'hit')):
        if (k, metric) in spread:
            found = spread[(k, metric)]
            lines.append(f'| {names[metric]}@{k} | {found.sd:.3f} | {found.low:.3f} | {found.high:.3f} |')
    return lines + ['']


def coverage_lines(comparison):
    lines = [
        '## What the collaborative models could score', '',
        'A collaborative model only knows the gigs and freelancers it was trained on. A gig it cannot score goes '
        'to the back of its list, so a low share here limits how well it can do.', '',
        '| Model | Candidates scored | Right answers scored |', '|---|---|---|',
    ]
    for method in COLLABORATIVE_METHODS:
        result = comparison.results[method]
        if result.available:
            lines.append(f'| {LABELS[method]} | {result.coverage:.0%} | {result.relevant_coverage:.0%} |')
        else:
            lines.append(f'| {LABELS[method]} | not fitted | not fitted |')
    return lines + ['']


def cold_start_lines(comparison):
    sizes = comparison.group_sizes
    lines = [
        '## Cold start', '',
        f'Cold start means fewer than {settings.RECOMMENDER_COLD_START_MIN_GIGS} different gigs in the freelancer\'s '
        f'training data. {sizes["cold_start"]} freelancer(s) are in cold start and {sizes["not_cold_start"]} are not.',
        '',
    ]
    columns = metric_columns(HEADLINE_KS, HEADLINE_METRICS)
    for group, title in (('cold_start', 'In cold start'), ('not_cold_start', 'Not in cold start')):
        if sizes[group]:
            lines += [f'### {title} ({sizes[group]} freelancers)', '', *results_table(comparison, columns, group), '']
        else:
            lines += [f'{title}: nobody, so there is nothing to report for this group.', '']
    return lines


def strict_lines(strict):
    sizes = strict.group_sizes
    count = sizes['all']
    lines = [
        '## Strict relevance (shortlisted or hired only)', '',
        f'{strict.info["relevant"]} right answers over {count} freelancers. The candidates are the same as above, and '
        'a gig the freelancer only applied to is now just another wrong answer.',
    ]
    if count < MIN_STRICT_FREELANCERS:
        lines += [
            '',
            f'**Fewer than {MIN_STRICT_FREELANCERS} freelancers have a shortlisted or hired right answer, so these '
            'numbers are shown for completeness and are too few to draw a conclusion from.**',
        ]
    if count:
        lines += ['', *results_table(strict, metric_columns(HEADLINE_KS, HEADLINE_METRICS))]
    return lines + ['']


LIMIT_LINES = [
    '## How to read these numbers', '',
    '- Candidates for each freelancer are the gigs that existed by the end of the part and were still taking '
    'applications at some point in it (by application deadline), not their own, not applied to in train and not the '
    'other held-out part\'s right answers. Whether a gig was open is not recorded, so the deadline stands in for it.',
    '- Each freelancer has their own cut-off, so the collaborative models learn from some behaviour that happened '
    'after another freelancer\'s cut-off.',
    '- Skills and bios are read as they are today. Profiles are not versioned.',
    '- Equal scores are ordered by a hash of the seed and the gig for every method, not newest first as in the live '
    'feed.',
    '- A model with no score for a gig puts it after every gig it can score.',
    '- Nothing was tuned for this run. The settings are the live ones.',
    '',
]


def test_run_lines(run):
    lines = ['## Test runs recorded', '', '| When | Split fingerprint | Synthetic data | Report |', '|---|---|---|---|']
    for row in run['test_runs']:
        lines.append(
            f'| {row["when"]} | {row["split_fingerprint"]} | '
            f'{"included" if row["include_synthetic"] == "True" else "left out"} | {row["report"]} |'
        )
    return lines + ['']


def build_markdown(comparison, strict, split, models, run):
    """The whole report. run holds the command, how the split was made, the test runs and the file names."""
    mode = run.get('mode', modes.SKILL_OVERLAP)
    lines = [
        f'# Recommender evaluation: {comparison.part} part, {run["date"]}', '', *modes.label_lines(mode),
        *modes.profile_lines(),
    ]
    lines += warning_lines(comparison, mode)
    lines += run_lines(comparison, split, run)
    lines += data_lines(comparison, split, models)
    lines += model_lines(models, run['live_version'])
    lines += headline_lines(comparison)
    lines += supplementary_lines(comparison)
    lines += spread_lines(comparison)
    lines += coverage_lines(comparison)
    lines += cold_start_lines(comparison)
    lines += strict_lines(strict)
    lines += LIMIT_LINES
    if comparison.part == ev.TEST:
        lines += test_run_lines(run)
    return '\n'.join(lines) + '\n'

