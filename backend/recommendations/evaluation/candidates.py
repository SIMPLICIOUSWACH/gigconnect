"""
The gigs a freelancer could have been recommended at the time of their held-out applications.

The live feed rules (open, deadline not passed) cannot be used for this: today most of the gigs people applied to
in the past are closed or past their deadline, and the rules would hide nearly every held-out gig. Instead, for
one freelancer and one held-out part (validation or test), a gig is a candidate if:

- it was posted by the end of the part (created at or before the freelancer's last positive in the part), and
- it was still taking applications at some point in the part (its application deadline is on or after the day of
  the freelancer's first positive in the part, or it has none), and
- it is not the freelancer's own gig, and
- it is not a gig they applied to in train, and
- it is not a gig they applied to in the other held-out part. That one is a real positive, only for the other
  evaluation, and leaving it in would count it as a wrong answer.

The gig's status then is not recorded anywhere, so the application deadline stands in for "was open". A gig that
closed early would still count as a candidate. This approximation is stated in the report.

The part's own positives are always candidates. If one would not pass the rules above (which means the data is
inconsistent, for example an application dated before its gig existed) it is still included and reported, so the
inconsistency is visible and not silently hidden.

The live feed rules are not changed by any of this.
"""

from dataclasses import dataclass

from ..platform import gigs_for_training
from .split import TEST, TRAIN, VALIDATION


@dataclass(frozen=True)
class GigRecord:
    id: object
    client_id: object
    created_at: object
    application_deadline: object  # a date, or None


def load_gig_records(include_synthetic=True):
    """Every gig, whatever its status, as plain records."""
    rows = gigs_for_training(include_synthetic).values_list('id', 'client_id', 'created_at', 'application_deadline')
    return [GigRecord(*row) for row in rows]


def candidates_for(split, freelancer_id, part, gigs):
    """
    The candidate gig ids for this freelancer and this held-out part, and the part's positives that did not
    pass the rules (see the module description). Returns (ids, outside_the_rules), both sorted.
    """
    if part not in (VALIDATION, TEST):
        raise ValueError('Candidates are only built for the validation or test part.')
    parts = split.by_freelancer().get(freelancer_id)
    if not parts or not parts[part]:
        return [], []

    positives = parts[part]
    first, last = min(p.timestamp for p in positives), max(p.timestamp for p in positives)
    other = TEST if part == VALIDATION else VALIDATION
    excluded = {p.gig_id for p in parts[TRAIN]} | {p.gig_id for p in parts[other]}

    allowed = {
        gig.id for gig in gigs
        if gig.client_id != freelancer_id
        and gig.id not in excluded
        and gig.created_at <= last
        and (gig.application_deadline is None or gig.application_deadline >= first.date())
    }
    relevant = {p.gig_id for p in positives}
    return sorted(allowed | relevant, key=str), sorted(relevant - allowed, key=str)
