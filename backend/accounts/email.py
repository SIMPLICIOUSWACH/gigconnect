import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .tokens import make_email_verification_token

logger = logging.getLogger(__name__)


def send_verification_email(user):
    """
    Email the verification link. Returns True if the mail server accepted it and False if sending failed. A failure is
    logged, never raised, so it can't break the request that asked for the email.
    """
    token = make_email_verification_token(user)
    link = f'{settings.FRONTEND_URL}/verify-email/{token}'
    try:
        send_mail(
            subject='Verify your GigConnect email',
            message=f'Hi {user.full_name},\n\nVerify your email by visiting:\n{link}\n\nThis link expires in 24 hours.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
    except Exception:
        # The user id, not the address, so the log holds no personal data.
        logger.exception('Could not send the verification email to user %s.', user.pk)
        return False
    return True


def send_verification_email_on_commit(user):
    """
    Send once the caller's transaction commits, so an account that is rolled back never gets an email. Outside a
    transaction it sends at once. Returns a dict that holds `sent` (True or False) once the email has been tried.
    """
    outcome = {}
    transaction.on_commit(lambda: outcome.update(sent=send_verification_email(user)))
    return outcome
