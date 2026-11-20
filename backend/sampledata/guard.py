from django.conf import settings
from django.core.management.base import CommandError


def require_debug():
    """The sample-data commands make accounts with a shared password, so they only run in development."""
    if not settings.DEBUG:
        raise CommandError('This command only runs with DEBUG=True. It makes sample accounts and data for development.')
