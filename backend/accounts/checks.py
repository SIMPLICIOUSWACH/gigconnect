from django.conf import settings
from django.core.checks import Warning, register

SMTP_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'


@register()
def email_settings(app_configs, **kwargs):
    """Real email needs a login for the mail server. Without one, every email fails and is only logged."""
    if settings.EMAIL_BACKEND != SMTP_BACKEND:
        return []
    missing = [name for name in ('EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD') if not getattr(settings, name)]
    if not missing:
        return []
    return [Warning(
        f'EMAIL_BACKEND is SMTP but {" and ".join(missing)} is not set, so no email can be sent.',
        hint='Fill these in backend/.env. See "Sending email" in the README.',
        id='accounts.W001',
    )]
