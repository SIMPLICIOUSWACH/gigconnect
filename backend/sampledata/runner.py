"""
How the commands run: all in one transaction, checked against the training snapshot, and thrown away on a dry run.

The check is what protects the reported results. A snapshot of what the recommender trains and is evaluated on is
taken before and after the work, inside the same transaction. If any number differs the whole run is rolled back and
the command stops with the difference, so a mistake can never leave the training world changed.
"""

from django.core.management.base import CommandError
from django.db import transaction

from recommendations.evaluation import modes

from .snapshot import differences, format_snapshot, training_snapshot


class DryRun(Exception):
    """Raised at the end of a dry run so the transaction rolls back."""


def require_main_database():
    if modes.current_mode() == modes.SYNTHETIC_PLANTED:
        raise CommandError(
            'This is the planted demo database. These commands are for the main database (see the README).'
        )


def guarded(work, dry_run=False, stdout=None, saved_files=None):
    """
    Run `work()` in a transaction, with the training snapshot taken before and after. Returns (before, after, result).
    A dry run rolls everything back; a changed snapshot rolls back and raises.
    """
    before = training_snapshot()
    result = None
    try:
        with transaction.atomic():
            result = work()
            after = training_snapshot()
            changed = differences(before, after)
            if changed:
                raise CommandError(
                    'Stopped and rolled back: the recommender\'s training data would have changed.\n'
                    + '\n'.join(f'  {key}: {old} -> {new}' for key, (old, new) in changed.items())
                )
            if dry_run:
                raise DryRun
    except DryRun:
        pass
    except Exception:
        for storage, name in saved_files or []:
            try:
                storage.delete(name)
            except OSError:
                pass
        raise
    if dry_run:
        for storage, name in saved_files or []:  # nothing is saved on a dry run, but be sure
            storage.delete(name)
    if stdout is not None:
        stdout.write('Training snapshot before and after (identical):\n' + format_snapshot(before))
    return before, after, result
