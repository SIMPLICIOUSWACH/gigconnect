"""
Moving the dates of sample data forward, so a timeline made some days ago looks as if it was made today.

Everything a batch made (its gigs and what hangs off them, its notifications, portfolio items, accounts and ID check
times) moves by the same number of days. Nothing changes order, so a gig posted before it was applied to is still posted
before. Open gigs keep their distance from today, so they stay open, and the showcase freelancers keep getting
recommendations. Rows the batch did not make are never touched.
"""

from collections import Counter
from datetime import timedelta

from django.apps import apps
from django.db.models import F

from .ledger import Ledger
from .models import SampleRecord

# model label -> (how to find the batch's rows, the date fields to move)
GIG = 'gigs.Gig'
TARGETS = [
    ('applications.Application', 'gig_id__in', ['created_at', 'updated_at']),
    ('applications.ApplicationStatusEvent', 'application__gig_id__in', ['created_at']),
    ('messaging.Conversation', 'gig_id__in', ['created_at', 'first_message_at', 'last_message_at',
                                              'client_emailed_at', 'freelancer_emailed_at']),
    ('messaging.Message', 'conversation__gig_id__in', ['created_at', 'read_at']),
    ('reviews.Review', 'gig_id__in', ['created_at', 'updated_at', 'reply_at']),
    ('gigs.GigInvite', 'gig_id__in', ['created_at']),
]
GIG_FIELDS = ['created_at', 'updated_at', 'status_changed_at', 'deadline', 'application_deadline']
PROFILE_FIELDS = ['verification_submitted_at', 'verification_decided_at', 'selfie_challenge_issued_at',
                  'selfie_consent_at', 'selfie_submitted_at']


def _move(queryset, fields, delta):
    """Move datetime fields with one UPDATE. A null stays null."""
    return queryset.update(**{field: F(field) + delta for field in fields})


def shift_batch(batch, days):
    """Move everything the batch made by `days` days (a whole number, forward when positive). Returns a Counter."""
    ledger = Ledger(batch)
    delta = timedelta(days=days)
    moved = Counter()

    gig_ids = ledger.created_ids(GIG)
    Gig = apps.get_model(GIG)
    gigs = list(Gig.objects.filter(pk__in=gig_ids))
    for gig in gigs:
        for name in GIG_FIELDS:
            value = getattr(gig, name)
            if value is not None:
                setattr(gig, name, value + delta)
    Gig.objects.bulk_update(gigs, GIG_FIELDS)
    moved['gigs'] = len(gigs)

    for label, lookup, fields in TARGETS:
        model = apps.get_model(label)
        moved[label.split('.')[1]] = _move(model.objects.filter(**{lookup: gig_ids}), fields, delta)

    Notification = apps.get_model('notifications.Notification')
    moved['Notification'] = _move(
        Notification.objects.filter(pk__in=ledger.created_ids('notifications.Notification')),
        ['created_at', 'read_at'], delta,
    )
    PortfolioItem = apps.get_model('profiles.PortfolioItem')
    moved['PortfolioItem'] = _move(
        PortfolioItem.objects.filter(pk__in=ledger.created_ids('profiles.PortfolioItem')), ['created_at'], delta,
    )

    made = ledger.created_ids('accounts.User')
    backdated = set(
        SampleRecord.objects.filter(batch=batch, kind=SampleRecord.Kind.CHANGED, model_label='accounts.User',
                                    field='created_at').values_list('object_id', flat=True)
    )
    User = apps.get_model('accounts.User')
    moved['User'] = _move(User.objects.filter(pk__in=made | backdated), ['created_at'], delta)
    FreelancerProfile = apps.get_model('profiles.FreelancerProfile')
    moved['FreelancerProfile'] = _move(FreelancerProfile.objects.filter(user_id__in=made), PROFILE_FIELDS, delta)
    return moved

