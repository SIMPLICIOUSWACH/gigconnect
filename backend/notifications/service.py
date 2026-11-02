from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from usersettings.models import NotificationPreference

from .models import Notification


def notify(recipient, kind, title, body, link='', email_preference=None):
    """
    Write an in-app notification, and email it too if the recipient has `email_preference` (a field of
    NotificationPreference, such as 'status_change_email') switched on.

    The row is written in the caller's transaction. The email is sent only once that transaction commits, so a
    rolled-back action never emails anyone.
    """
    notification = Notification.objects.create(recipient=recipient, kind=kind, title=title, body=body, link=link)
    if email_preference and _wants_email(recipient, email_preference):
        transaction.on_commit(lambda: _send_email(recipient, title, body, link))
    return notification


def _wants_email(user, preference):
    prefs = NotificationPreference.objects.filter(user=user).first()
    # Every account gets a preference row when it is created; one without a row keeps the defaults, which are on.
    return getattr(prefs, preference) if prefs else True


def _send_email(user, title, body, link):
    message = f'Hi {user.full_name},\n\n{body}\n'
    if link:
        message += f'\n{settings.FRONTEND_URL}{link}\n'
    send_mail(
        subject=f'GigConnect: {title}',
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
