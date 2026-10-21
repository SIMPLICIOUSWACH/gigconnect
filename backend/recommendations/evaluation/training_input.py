"""
What the models are allowed to learn from during an evaluation. This is the one place that decides it.

The rule is that nothing from a freelancer's held-out period, or about the gigs held out for them, may reach
training. For each freelancer with held-out positives (an "evaluated" freelancer):

- Every interaction they had after their cut-off is left out. The cut-off is the time of their last train
  positive.
- Every interaction they had with a gig held out for them (in validation or test) is left out, whenever it
  happened. A view of a gig they went on to apply to would otherwise tell the model the answer.
- Their train applications count with the status they had at the cut-off, not the status they ended up with.
  An application shortlisted after the cut-off counts as it was then, an ordinary application.

Apply interactions are not read as interactions here, for anyone. A freelancer's applications come only from the
positives in the split, so a held-out application cannot get in through its matching apply interaction. For
freelancers who are not evaluated (too few positives) everything they did is training data.

The vectoriser follows the same rule: it is fitted only on gigs that existed before the earliest cut-off of
anyone being evaluated, so it has not seen text from a gig posted during anyone's held-out period.

What remains is the limit the split module describes: each freelancer has their own cut-off, so one freelancer's
training data can include things other people did after that freelancer's cut-off.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from applications.models import ApplicationStatusEvent
from applications.transitions import Status

from .. import collaborative
from ..platform import gigs_for_training, interactions_for_training
from .split import APPLIED, TRAIN


@dataclass
class TrainingInput:
    weights: dict  # {(freelancer id, gig id): weight}, ready for the collaborative model
    stats: dict = field(default_factory=dict)


def status_as_of(events, cutoff, final_status):
    """
    The status an application had at a moment, from its status events, as [(time, to_status), ...].

    With no events recorded it falls back to the final status, because there is nothing to say it was
    different. Before the first event it is pending.
    """
    if not events:
        return final_status
    status = Status.PENDING
    for when, to_status in sorted(events):
        if when > cutoff:
            break
        status = to_status
    return status


def load_status_events(freelancer_ids):
    """{(freelancer id, gig id): [(time, to_status), ...]} for these freelancers' applications."""
    events = defaultdict(list)
    rows = ApplicationStatusEvent.objects.filter(application__freelancer_id__in=freelancer_ids).values_list(
        'application__freelancer_id', 'application__gig_id', 'created_at', 'to_status',
    )
    for freelancer_id, gig_id, when, to_status in rows:
        events[(freelancer_id, gig_id)].append((when, to_status))
    return events


def training_input(split, include_synthetic=True):
    """The weights the collaborative model may learn from, given this split, plus counts of what was left out."""
    evaluated = split.evaluated_freelancers()
    cutoffs = {f: split.cutoff(f) for f in evaluated}
    held_out = {f: split.held_out_gigs(f) for f in evaluated}
    stats = {
        'interactions_seen': 0, 'interactions_kept': 0, 'left_out_after_cutoff': 0, 'left_out_held_out_gig': 0,
        'train_positives': 0, 'statuses_taken_as_of_cutoff': 0,
    }

    interactions = []
    rows = interactions_for_training(include_synthetic).exclude(type='apply').values_list(
        'user_id', 'gig_id', 'type', 'created_at',
    )
    for user_id, gig_id, kind, when in rows:
        stats['interactions_seen'] += 1
        if user_id in evaluated:
            if when > cutoffs[user_id]:
                stats['left_out_after_cutoff'] += 1
                continue
            if gig_id in held_out[user_id]:
                stats['left_out_held_out_gig'] += 1
                continue
        interactions.append((user_id, gig_id, kind))
    stats['interactions_kept'] = len(interactions)

    events = load_status_events(evaluated)
    applications = []
    for positive in split.in_part(TRAIN):
        stats['train_positives'] += 1
        status = positive.status
        if positive.freelancer_id in evaluated and status != APPLIED:
            as_of = status_as_of(
                events.get((positive.freelancer_id, positive.gig_id), []), cutoffs[positive.freelancer_id], status,
            )
            if as_of != status:
                stats['statuses_taken_as_of_cutoff'] += 1
            status = as_of
        # A bare "applied" (an apply interaction with no application row) is worth the same as a pending one.
        applications.append((positive.freelancer_id, positive.gig_id, Status.PENDING if status == APPLIED else status))

    return TrainingInput(weights=collaborative.build_weights(interactions, applications), stats=stats)


def vectoriser_gig_ids(split, include_synthetic=True):
    """
    The ids of the gigs the content model's vocabulary may be fitted on: those that existed before the earliest
    cut-off of anyone being evaluated. With nobody evaluated there is no held-out period, so every gig counts.
    """
    gigs = gigs_for_training(include_synthetic)
    cutoffs = [c for c in (split.cutoff(f) for f in split.evaluated_freelancers()) if c is not None]
    if cutoffs:
        gigs = gigs.filter(created_at__lte=min(cutoffs))
    return list(gigs.values_list('id', flat=True))

