"""
The demo profile refuses to start unless it is connected to the planted database.

This is a Django system check, so `runserver` and every management command that runs checks stop with an error
instead of serving the planted tuning settings over real data. It checks the database name the profile asks for and,
once the tables exist, that every account in it is a planted one. An empty, freshly made planted database passes, so
`migrate` and `seed_planted` can run on it.
"""

from django.conf import settings
from django.core.checks import Error, register
from django.db import DatabaseError, connection

DEMO = 'demo'
PLANTED_EMAIL_PREFIX = 'planted-'


def demo_problems(profile, database_name, planted_database, foreign_accounts):
    """
    What is wrong with running this profile on this database, as plain messages. Empty when nothing is.
    foreign_accounts is how many accounts are not planted, or None if that could not be counted.
    """
    if profile != DEMO:
        return []
    problems = []
    if database_name != planted_database:
        problems.append(
            f'The demo profile must run on the planted database "{planted_database}", but it is connected to '
            f'"{database_name}".'
        )
    if foreign_accounts:
        problems.append(
            f'The demo profile is connected to a database with {foreign_accounts} account(s) that are not planted. '
            'It only runs on the planted database, so real or ordinary seed data is never shown with demo settings.'
        )
    return problems


def count_foreign_accounts():
    """Accounts that are not planted, or None before the tables exist (a new database that is still empty)."""
    from accounts.models import User

    if User._meta.db_table not in connection.introspection.table_names():
        return None
    return User.objects.exclude(email__startswith=PLANTED_EMAIL_PREFIX).count()


@register()
def demo_profile_database(app_configs, **kwargs):
    if settings.RECOMMENDER_PROFILE != DEMO:
        return []
    try:
        foreign = count_foreign_accounts()
    except DatabaseError as error:
        return [Error(f'The demo profile could not check its database: {error}', id='recommendations.E002')]
    problems = demo_problems(
        settings.RECOMMENDER_PROFILE, settings.DATABASES['default']['NAME'], settings.RECOMMENDER_PLANTED_DATABASE,
        foreign,
    )
    return [Error(message, id='recommendations.E001') for message in problems]
