"""The things that happen on GigConnect that someone is told about. Admin actions are in adminpanel/moderation.py."""

from django.conf import settings
from django.core.mail import send_mass_mail
from django.db import transaction

from accounts.models import User
from applications.transitions import Status
from usersettings.models import NotificationPreference

from .models import Notification
from .service import clean_title, email_text, notify, wants

Kind = Notification.Kind

STATUS_MESSAGES = {
    Status.UNDER_REVIEW: 'The client has started reviewing your application for "{title}".',
    Status.SHORTLISTED: 'Good news: the client shortlisted you for "{title}".',
    Status.HIRED: 'Congratulations: the client hired you for "{title}".',
    Status.REJECTED: 'The client did not go ahead with your application for "{title}".',
}


def new_application(application):
    gig = application.gig
    notify(
        gig.client, Kind.NEW_APPLICATION, f'New application for "{gig.title}"',
        f'{application.freelancer.full_name} applied to your gig "{gig.title}".',
        link=f'/gigs/{gig.pk}/applicants',
        email_preference='new_application_email', inapp_preference='new_application_inapp',
    )


def application_withdrawn(application):
    gig = application.gig
    notify(
        gig.client, Kind.APPLICATION_WITHDRAWN, f'Application withdrawn for "{gig.title}"',
        f'{application.freelancer.full_name} withdrew their application to your gig "{gig.title}".',
        link=f'/gigs/{gig.pk}/applicants',
        email_preference='new_application_email', inapp_preference='new_application_inapp',
    )


def application_status_changed(application):
    title = application.gig.title
    label = Status(application.status).label
    notify(
        application.freelancer, Kind.APPLICATION_STATUS, f'Your application for "{title}": {label}',
        STATUS_MESSAGES[application.status].format(title=title),
        link=f'/applications/{application.pk}',
        email_preference='status_change_email', inapp_preference='status_change_inapp',
    )


def password_changed(user):
    notify(
        user, Kind.PASSWORD_CHANGED, 'Your password was changed',
        'The password on your GigConnect account was changed and every session was logged out. If this was not you, '
        'contact GigConnect straight away.',
        email_preference='security_alert_email', inapp_preference='security_alert_inapp',
    )


def matching_freelancers(gig):
    """Active freelancers who share a skill with the gig, oldest accounts first, up to the setting's limit."""
    return (
        User.objects.filter(
            role=User.Role.FREELANCER, is_active=True, deleted_at__isnull=True,
            account_status=User.AccountStatus.ACTIVE, is_email_verified=True,
            freelancer_profile__skills__in=gig.skills.all(),
        )
        .exclude(pk=gig.client_id).distinct().order_by('created_at', 'id')[:settings.NOTIFICATION_MATCH_LIMIT]
    )


def new_gig_match(gig):
    """
    Tell freelancers about a new gig that shares a skill with them. One query for the people, one for their settings,
    one insert for the rows and one batch of emails, so posting a gig stays quick however many people match.
    """
    people = list(matching_freelancers(gig))
    prefs = {row.user_id: row for row in NotificationPreference.objects.filter(user__in=people)}
    title = clean_title(f'New gig that matches your skills: {gig.title}')
    body = f'"{gig.title}" was just posted and shares a skill on your profile.'
    link = f'/gigs/{gig.pk}'
    Notification.objects.bulk_create([
        Notification(recipient=person, kind=Kind.NEW_GIG_MATCH, title=title, body=body, link=link)
        for person in people if wants(prefs.get(person.pk), 'new_match_inapp')
    ])
    emails = [
        (f'GigConnect: {title}', email_text(person, body, link), settings.DEFAULT_FROM_EMAIL, [person.email])
        for person in people if wants(prefs.get(person.pk), 'new_match_email')
    ]
    if emails:
        transaction.on_commit(lambda: send_mass_mail(emails), robust=True)
