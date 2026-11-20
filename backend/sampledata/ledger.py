"""
The ledger behind --undo and "run it again and nothing doubles". See SampleRecord for what each kind of entry means.

Undo takes back only what a batch recorded: it deletes the rows the batch created (their applications, reviews and
chats go with them), puts back the fields it filled in, and deletes the generated image files. Rows and values that
were there before are never touched.
"""

from collections import Counter

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.utils.dateparse import parse_datetime

from .models import SampleRecord

Kind = SampleRecord.Kind

# Deleted in this order: a gig takes its applications, reviews, chats and invites with it; users go last.
DELETE_ORDER = ['gigs.Gig', 'profiles.PortfolioItem', 'notifications.Notification', 'accounts.User']


def label_of(obj):
    return obj._meta.label


def _json(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if hasattr(value, 'name') and not isinstance(value, (str, int, float, bool)):  # a FieldFile
        return value.name or ''
    return value


class Ledger:
    def __init__(self, batch):
        self.batch = batch

    def _records(self, kind, label=None):
        found = SampleRecord.objects.filter(batch=self.batch, kind=kind)
        return found.filter(model_label=label) if label else found

    def created(self, obj):
        SampleRecord.objects.get_or_create(
            batch=self.batch, kind=Kind.CREATED, model_label=label_of(obj), object_id=str(obj.pk), field='',
        )

    def created_ids(self, label):
        return set(self._records(Kind.CREATED, label).values_list('object_id', flat=True))

    def is_done(self, obj, step):
        return self._records(Kind.DONE, label_of(obj)).filter(object_id=str(obj.pk), field=step).exists()

    def mark_done(self, obj, step):
        SampleRecord.objects.get_or_create(
            batch=self.batch, kind=Kind.DONE, model_label=label_of(obj), object_id=str(obj.pk), field=step,
        )

    def remember(self, obj, field):
        """Save what the field holds now, once, before the batch changes it. A second call keeps the first value."""
        SampleRecord.objects.get_or_create(
            batch=self.batch, kind=Kind.CHANGED, model_label=label_of(obj), object_id=str(obj.pk), field=field,
            defaults={'old_value': _json(getattr(obj, field))},
        )

    def anchor(self):
        """The day the dates were last set, as an ISO date string, or None."""
        record = self._records(Kind.ANCHOR).first()
        return record.old_value if record else None

    def set_anchor(self, day):
        SampleRecord.objects.update_or_create(
            batch=self.batch, kind=Kind.ANCHOR, model_label='', object_id='', field='date',
            defaults={'old_value': day.isoformat()},
        )

    def exists(self):
        return SampleRecord.objects.filter(batch=self.batch).exists()


def _file_fields(model):
    return [f for f in model._meta.get_fields() if isinstance(f, models.FileField)]


def _collect_files(label, ids):
    """[(storage, name)] for every file these rows hold, and the profiles and portfolio items hanging off users."""
    model = apps.get_model(label)
    files = []
    if label == 'accounts.User':
        for profile_label in ('profiles.FreelancerProfile', 'profiles.ClientProfile'):
            profile_model = apps.get_model(profile_label)
            files += _collect_files_of(profile_model, profile_model.objects.filter(user_id__in=ids))
        PortfolioItem = apps.get_model('profiles.PortfolioItem')
        files += _collect_files_of(PortfolioItem, PortfolioItem.objects.filter(freelancer__user_id__in=ids))
        return files
    return _collect_files_of(model, model.objects.filter(pk__in=ids))


def _collect_files_of(model, queryset):
    files = []
    for field in _file_fields(model):
        for name in queryset.values_list(field.name, flat=True):
            if name:
                files.append((field.storage, name))
    return files


def _refresh_ratings(freelancer_ids):
    """A freelancer's average and count are stored on their profile, so they are worked out again once reviews go."""
    from reviews.service import refresh_rating

    for freelancer in apps.get_model('accounts.User').objects.filter(pk__in=freelancer_ids):
        refresh_rating(freelancer)


def _restore_value(model, field_name, value):
    field = model._meta.get_field(field_name)
    if isinstance(field, models.DateTimeField) and isinstance(value, str):
        return parse_datetime(value)
    return value


@transaction.atomic
def undo(batch):
    """Take back one batch. Returns a Counter of what was removed and restored."""
    ledger = Ledger(batch)
    summary = Counter()
    doomed_files = []

    created = {}
    for label in {r.model_label for r in ledger._records(Kind.CREATED)}:
        created[label] = list(ledger._records(Kind.CREATED, label).values_list('object_id', flat=True))
    for label in DELETE_ORDER:
        ids = created.get(label)
        if not ids:
            continue
        model = apps.get_model(label)
        doomed_files += _collect_files(label, ids)
        if label == 'gigs.Gig':
            reviews = apps.get_model('reviews.Review').objects.filter(gig_id__in=ids)
            rated = set(reviews.values_list('freelancer_id', flat=True))
        deleted, _ = model.objects.filter(pk__in=ids).delete()
        summary[f'{label} deleted'] = len(ids)
        summary['rows removed with them'] += deleted - len(ids)
        if label == 'gigs.Gig':
            _refresh_ratings(rated)

    for record in ledger._records(Kind.CHANGED):
        model = apps.get_model(record.model_label)
        try:
            row = model.objects.get(pk=record.object_id)
        except ObjectDoesNotExist:
            continue
        current = getattr(row, record.field)
        if isinstance(model._meta.get_field(record.field), models.FileField) and current:
            doomed_files.append((model._meta.get_field(record.field).storage, current.name))
        model.objects.filter(pk=record.object_id).update(
            **{record.field: _restore_value(model, record.field, record.old_value)},
        )
        summary['fields put back'] += 1

    SampleRecord.objects.filter(batch=batch).delete()

    def delete_files():
        for storage, name in doomed_files:
            try:
                storage.delete(name)
            except OSError:
                pass

    transaction.on_commit(delete_files)
    summary['files deleted'] = len(doomed_files)
    return summary
