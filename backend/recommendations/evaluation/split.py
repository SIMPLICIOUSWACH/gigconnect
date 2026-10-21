"""
The 70/15/15 evaluation split (proposal section 3.2.4).

What counts as relevant. A gig is relevant to a freelancer if they applied to it, whatever became of the
application, and a stricter reading counts only gigs they were shortlisted or hired for. Views, clicks and saves
are not relevance.

How the split is made. Each freelancer's positive gigs are put in time order. The oldest 70% go to train, the
next 15% to validation and the newest 15% to test, because the system is used to predict what someone applies
to next, and training on the future would flatter it. A freelancer needs at least MIN_POSITIVES positives to be
split. They get at least one in each held-out part, so 5 positives split 3, 1 and 1. Freelancers with fewer stay
in train only and are counted separately.

A limit worth knowing. Each freelancer has their own cut-off, so one freelancer's training period can include
events that happened after another freelancer's test event. The collaborative model then learns from other
people's later behaviour. This is the price of splitting per freelancer, and the report says so.

Everything here is deterministic: positives with the same timestamp are ordered by a hash of the seed and the
gig, and the split is saved to a CSV with a fingerprint of the data it was made from, so a rerun loads the same
split unless it is rebuilt on purpose.
"""

import csv
import hashlib
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from applications.transitions import Status

from ..platform import applications_for_training, freelancers_for_training, interactions_for_training

TRAIN, VALIDATION, TEST = 'train', 'validation', 'test'
HELD_OUT_PARTS = (VALIDATION, TEST)
MIN_POSITIVES = 5
HELD_OUT_SHARE = 0.15  # each of validation and test; train gets the rest, about 70%
STRICT_STATUSES = {Status.SHORTLISTED, Status.HIRED}
APPLIED = 'applied'  # a positive known only from an apply interaction, with no application row

SPLIT_FILE = 'split.csv'
META_FILE = 'split.meta.json'
COLUMNS = ['freelancer_id', 'gig_id', 'timestamp', 'part', 'status', 'is_synthetic']


@dataclass(frozen=True)
class Positive:
    freelancer_id: object
    gig_id: object
    timestamp: datetime
    status: str  # the application's status, or APPLIED
    is_synthetic: bool

    @property
    def strictly_relevant(self):
        return self.status in STRICT_STATUSES


@dataclass(frozen=True)
class SplitRow:
    positive: Positive
    part: str


@dataclass
class Split:
    rows: list
    seed: int
    include_synthetic: bool
    min_positives: int = MIN_POSITIVES
    too_few: set = field(default_factory=set)  # freelancers kept in train only, with their count in .rows

    def in_part(self, part):
        return [row.positive for row in self.rows if row.part == part]

    def evaluated_freelancers(self):
        """Freelancers who have positives in validation and test, and so can be scored."""
        return {row.positive.freelancer_id for row in self.rows if row.part in HELD_OUT_PARTS}

    def by_freelancer(self):
        grouped = defaultdict(lambda: {TRAIN: [], VALIDATION: [], TEST: []})
        for row in self.rows:
            grouped[row.positive.freelancer_id][row.part].append(row.positive)
        return grouped

    def cutoff(self, freelancer_id):
        """When the freelancer's training period ends: the time of their last train positive. None if not evaluated."""
        parts = self.by_freelancer().get(freelancer_id)
        if not parts or not parts[VALIDATION]:
            return None
        return max(p.timestamp for p in parts[TRAIN])

    def held_out_gigs(self, freelancer_id):
        parts = self.by_freelancer().get(freelancer_id)
        if not parts:
            return set()
        return {p.gig_id for part in HELD_OUT_PARTS for p in parts[part]}

    def fingerprint(self):
        return fingerprint([row.positive for row in self.rows])


def tie_key(seed, gig_id):
    """A fixed order for positives with the same timestamp, that depends on the seed."""
    return hashlib.sha256(f'{seed}|{gig_id}'.encode()).hexdigest()


def fingerprint(positives):
    """A short fingerprint of the data a split was made from, so a changed dataset is noticed."""
    lines = sorted(f'{p.freelancer_id}|{p.gig_id}|{p.timestamp.isoformat()}' for p in positives)
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()[:16]


def split_sizes(count, min_positives=MIN_POSITIVES):
    """(train, validation, test) sizes for a freelancer with this many positives, or None if they have too few."""
    if count < min_positives:
        return None
    # Rounded half up (Python's round() goes to the nearest even number, which would hold out 4 of 30, not 5).
    held_out = max(1, int(HELD_OUT_SHARE * count + 0.5))
    return count - 2 * held_out, held_out, held_out


def load_positives(include_synthetic=True):
    """
    Every (freelancer, gig) the freelancer applied to, with when they applied. This reuses the training data
    rules, so a deleted freelancer and their erased applications are never in it.

    An application's time is when it was made. An apply interaction with no matching application row also counts.
    If both exist the earlier time wins.
    """
    found = {}

    def keep(freelancer_id, gig_id, when, status, synthetic):
        key = (freelancer_id, gig_id)
        old = found.get(key)
        if old is None:
            found[key] = Positive(freelancer_id, gig_id, when, status, synthetic)
            return
        # The same pair seen twice (an application and its apply interaction): the earlier time wins, and a real
        # application status beats the bare "applied".
        real_status = status if old.status == APPLIED else old.status
        found[key] = Positive(
            freelancer_id, gig_id, min(when, old.timestamp), real_status, old.is_synthetic or synthetic,
        )

    applications = applications_for_training(include_synthetic).values_list(
        'freelancer_id', 'gig_id', 'created_at', 'status', 'is_synthetic', 'freelancer__is_synthetic',
    )
    for freelancer_id, gig_id, when, status, synthetic, person_synthetic in applications:
        keep(freelancer_id, gig_id, when, status, synthetic or person_synthetic)
    interactions = interactions_for_training(include_synthetic).filter(type='apply').values_list(
        'user_id', 'gig_id', 'created_at', 'is_synthetic', 'user__is_synthetic',
    )
    for freelancer_id, gig_id, when, synthetic, person_synthetic in interactions:
        keep(freelancer_id, gig_id, when, APPLIED, synthetic or person_synthetic)
    return sorted(found.values(), key=lambda p: (str(p.freelancer_id), p.timestamp, str(p.gig_id)))


def build_split(positives, seed=42, include_synthetic=True, min_positives=MIN_POSITIVES):
    """Split positives per freelancer by time. See the module description for the rules."""
    grouped = defaultdict(list)
    for positive in positives:
        grouped[positive.freelancer_id].append(positive)

    rows, too_few = [], set()
    for freelancer_id, items in grouped.items():
        items.sort(key=lambda p: (p.timestamp, tie_key(seed, p.gig_id)))
        sizes = split_sizes(len(items), min_positives)
        if sizes is None:
            too_few.add(freelancer_id)
            rows += [SplitRow(item, TRAIN) for item in items]
            continue
        train, validation, _ = sizes
        for index, item in enumerate(items):
            part = TRAIN if index < train else VALIDATION if index < train + validation else TEST
            rows.append(SplitRow(item, part))
    rows.sort(key=lambda r: (str(r.positive.freelancer_id), r.positive.timestamp, str(r.positive.gig_id)))
    return Split(
        rows=rows, seed=seed, include_synthetic=include_synthetic, min_positives=min_positives, too_few=too_few,
    )


def describe(split):
    """
    Counts for each part of a split: how many freelancers and positives, how many positives are synthetic, and how
    many are strictly relevant (shortlisted or hired). The report quotes these next to every result.
    """
    counts = {}
    for part in (TRAIN, VALIDATION, TEST):
        positives = split.in_part(part)
        counts[part] = {
            'freelancers': len({p.freelancer_id for p in positives}),
            'positives': len(positives),
            'synthetic': sum(1 for p in positives if p.is_synthetic),
            'strictly_relevant': sum(1 for p in positives if p.strictly_relevant),
        }
    counts['evaluated_freelancers'] = len(split.evaluated_freelancers())
    counts['too_few_freelancers'] = len(split.too_few)
    counts['too_few_positives'] = sum(1 for row in split.rows if row.positive.freelancer_id in split.too_few)
    return counts


def default_directory():
    return Path(settings.RECOMMENDER_DATA_DIR) / 'platform' / 'evaluation'


def save_split(split, directory=None):
    """Write the split and its description to datasets/platform/evaluation/ (gitignored, real user data)."""
    directory = Path(directory or default_directory())
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / SPLIT_FILE, 'w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in split.rows:
            p = row.positive
            writer.writerow({
                'freelancer_id': p.freelancer_id, 'gig_id': p.gig_id, 'timestamp': p.timestamp.isoformat(),
                'part': row.part, 'status': p.status, 'is_synthetic': p.is_synthetic,
            })
    meta = {
        'seed': split.seed, 'include_synthetic': split.include_synthetic, 'min_positives': split.min_positives,
        'fingerprint': split.fingerprint(), 'saved_at': timezone.now().isoformat(),
        'too_few': sorted(str(f) for f in split.too_few),
    }
    (directory / META_FILE).write_text(json.dumps(meta, indent=2), encoding='utf-8')
    return directory


def load_split(directory=None):
    """Read a saved split. Returns None if there is none."""
    directory = Path(directory or default_directory())
    if not (directory / SPLIT_FILE).is_file() or not (directory / META_FILE).is_file():
        return None
    meta = json.loads((directory / META_FILE).read_text(encoding='utf-8'))
    rows = []
    with open(directory / SPLIT_FILE, newline='', encoding='utf-8-sig') as handle:
        for record in csv.DictReader(handle):
            positive = Positive(
                freelancer_id=uuid.UUID(record['freelancer_id']), gig_id=uuid.UUID(record['gig_id']),
                timestamp=datetime.fromisoformat(record['timestamp']), status=record['status'],
                is_synthetic=record['is_synthetic'] == 'True',
            )
            rows.append(SplitRow(positive, record['part']))
    return Split(
        rows=rows, seed=meta['seed'], include_synthetic=meta['include_synthetic'],
        min_positives=meta['min_positives'], too_few={uuid.UUID(f) for f in meta['too_few']},
    )


def load_or_build(include_synthetic=True, seed=42, rebuild=False, directory=None):
    """
    The saved split, or a new one. Returns (split, how, note) where how is 'loaded' or 'built'.

    A saved split is reused so results stay comparable between runs, unless it is rebuilt on purpose
    (rebuild=True) or it was made with a different include_synthetic setting. Anyone who has deleted their
    account since it was saved is removed from it, so a saved split never keeps a deleted person's data.
    """
    saved = None if rebuild else load_split(directory)
    if saved is not None and saved.include_synthetic != include_synthetic:
        saved, note = None, 'The saved split was made with a different synthetic setting, so it was rebuilt.'
    else:
        note = ''

    if saved is None:
        split = build_split(load_positives(include_synthetic), seed=seed, include_synthetic=include_synthetic)
        save_split(split, directory)
        return split, 'built', note

    eligible = set(freelancers_for_training(include_synthetic).values_list('user_id', flat=True))
    kept = [row for row in saved.rows if row.positive.freelancer_id in eligible]
    dropped = len({row.positive.freelancer_id for row in saved.rows} - eligible)
    if dropped:
        note = f'{dropped} freelancer(s) who deleted their account since the split was saved were removed from it.'
    saved.rows = kept
    saved.too_few &= eligible
    return saved, 'loaded', note
