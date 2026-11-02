from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils.text import Truncator

from usersettings.models import NotificationPreference

from .models import Notification

TITLE_MAX_LENGTH = Notification._meta.get_field('title').max_length


def clean_title(title):
    """
    One line, short enough for the column. Titles quote gig titles, which can be just as long, and a line break would
    make the email subject invalid.
    """
    return Truncator(' '.join(title.split())).chars(TITLE_MAX_LENGTH)


def notify(recipient, kind, title, body, link='', email_preference=None, inapp_preference=None):
    """
    Write an in-app notification, and email it too if the recipient has `email_preference` (a field of
    NotificationPreference, such as 'status_change_email') switched on.

    `inapp_preference` works the same way for the in-app row. Admin notices leave it out, so someone always has a
    record of what an admin did to their account. Returns the notification, or None if the setting is off.

    The row is written in the caller's transaction. The email is sent only once that transaction commits, so a
    rolled-back action never emails anyone, and a mail failure is logged rather than failing the request.
    """
    title = clean_title(title)
    prefs = NotificationPreference.objects.filter(user=recipient).first()
    notification = None
    if inapp_preference is None or wants(prefs, inapp_preference):
        notification = Notification.objects.create(recipient=recipient, kind=kind, title=title, body=body, link=link)
    if email_preference and wants(prefs, email_preference):
        transaction.on_commit(lambda: send_email(recipient, title, body, link), robust=True)
    return notification


def wants(prefs, preference):
    # Every account gets a preference row when it is created; one without a row keeps the defaults, which are on.
    return getattr(prefs, preference) if prefs else True


def email_text(user, body, link):
    message = f'Hi {user.full_name},\n\n{body}\n'
    if link:
        message += f'\n{settings.FRONTEND_URL}{link}\n'
    return message


def send_email(user, title, body, link):
    send_mail(
        subject=f'GigConnect: {title}',
        message=email_text(user, body, link),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
