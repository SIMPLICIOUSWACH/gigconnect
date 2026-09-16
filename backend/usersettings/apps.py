from django.apps import AppConfig


class UsersettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usersettings'

    def ready(self):
        from . import signals  # noqa: F401
