from django.apps import AppConfig


class GigsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gigs'

    def ready(self):
        from . import signals  # noqa: F401
