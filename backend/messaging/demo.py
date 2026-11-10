"""
Sample chats for the planted demo: a demo client who hired Amina, Brian and Cynthia (the planted demo freelancers) on
three gigs that are now in progress, with a few messages in each chat, the client writing first.

These gigs and applications are flagged is_demo_extra, and recommendations/platform.py leaves such rows out of
training and evaluation, so the demo's recommender sees exactly the same world with or without them. Running this
again replaces the sample chats rather than adding more. Planted database only.
"""

from collections import Counter
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from applications.models import Application, ApplicationStatusEvent
from gigs.models import Gig
from recommendations.planted_demo import DEMO_ACCOUNTS, DEMO_PASSWORD, DemoError, require_planted_database

from .models import Conversation, Message

DEMO_CLIENT = ('planted-demo-client@example.test', 'Baraka Home Services')
DEMO_CLIENT_PHONE = '+254792000001'
COVER_LETTER = 'A sample application for the chat demo. I have done this kind of work before and can start this week.'

# For each demo freelancer: the gig's title (after the category) and the chat, as (who, text) in order.
CHATS = {
    'premium': (
        'help for our new branch',
        [
            ('client', 'Hi Amina, thanks for applying. Here are the next steps: I will send the brief today, and I '
                       'would like a first draft by Friday.'),
            ('freelancer', 'Thanks! The brief looks clear. I will share a first draft on Thursday evening.'),
            ('client', 'Great. Payment goes through GigConnect once you deliver.'),
        ],
    ),
    'quick_cash': (
        'help this week',
        [
            ('client', 'Hi Brian, thanks for applying. Can you start tomorrow morning?'),
            ('freelancer', 'Yes, I can start at 9. Is there anything I should bring?'),
            ('client', 'Just your laptop. See you then.'),
        ],
    ),
    'remote_only': (
        'help, fully remote',
        [
            ('client', 'Hi Cynthia, thanks for applying. Everything for this one can be done remotely.'),
            ('freelancer', 'Perfect, remote suits me. When do you need it finished?'),
        ],
    ),
}


def demo_client():
    email, name = DEMO_CLIENT
    client = User.objects.filter(email=email).first()
    if client is None:
        client = User(
            email=email, full_name=name, phone=DEMO_CLIENT_PHONE, role=User.Role.CLIENT, is_email_verified=True,
            is_profile_complete=True, is_synthetic=True,
        )
        client.set_password(DEMO_PASSWORD)
        client.save()
        client.client_profile.company_name = name
        client.client_profile.save(update_fields=['company_name'])
    return client


def _usual_category(freelancer):
    """The category the freelancer applies in most, so the demo gig looks like work they would take."""
    counts = Counter(
        Application.objects.filter(freelancer=freelancer, is_demo_extra=False).values_list('gig__category', flat=True)
    )
    if counts:
        category_id = counts.most_common(1)[0][0]
        return Gig.objects.filter(category_id=category_id).first().category
    return Gig.objects.filter(is_demo_extra=False).select_related('category').first().category


def seed(now=None):
    """Replace the sample chats. Returns the conversations, one per demo freelancer."""
    require_planted_database()
    now = now or timezone.now()
    freelancers = {}
    for group, (email, _) in DEMO_ACCOUNTS.items():
        freelancers[group] = User.objects.filter(email=email).first()
        if freelancers[group] is None:
            raise DemoError(f'{email} is missing. Run refresh_planted_demo first.')

    with transaction.atomic():
        client = demo_client()
        # Deleting the gigs takes their applications, conversations and messages with them.
        Gig.objects.filter(client=client, is_demo_extra=True).delete()
        conversations = []
        for days_ago, (group, (title_end, lines)) in zip((6, 4, 2), CHATS.items()):
            freelancer = freelancers[group]
            hired_at = now - timedelta(days=days_ago)
            category = _usual_category(freelancer)
            gig = Gig.objects.create(
                client=client, category=category, title=f'{category.name} {title_end}',
                description=f'{DEMO_CLIENT[1]} needs {category.name.lower()} {title_end}. A sample gig for the chat '
                            'demo.',
                budget_min=8000, budget_max=15000, deadline=date.today() + timedelta(days=14),
                application_deadline=(hired_at - timedelta(days=1)).date(), is_remote=group == 'remote_only',
                is_synthetic=True, is_demo_extra=True, status=Gig.Status.IN_PROGRESS,
            )
            application = Application.objects.create(
                gig=gig, freelancer=freelancer, cover_letter=COVER_LETTER, status=Application.Status.HIRED,
                is_synthetic=True, is_demo_extra=True,
            )
            ApplicationStatusEvent.objects.bulk_create([
                ApplicationStatusEvent(application=application, from_status='', to_status='pending',
                                       changed_by=freelancer),
                ApplicationStatusEvent(application=application, from_status='pending', to_status='hired',
                                       changed_by=client),
            ])
            conversation = Conversation.objects.create(
                application=application, gig=gig, client=client, freelancer=freelancer,
            )
            Conversation.objects.filter(pk=conversation.pk).update(created_at=hired_at)
            conversations.append(_write_chat(conversation, lines, hired_at, now))
    return conversations


def _write_chat(conversation, lines, hired_at, now):
    """The messages, an hour apart from the hire on. The last one stays unread, so the demo shows an unread badge."""
    people = {'client': conversation.client, 'freelancer': conversation.freelancer}
    messages = []
    for position, (who, text) in enumerate(lines):
        sent = hired_at + timedelta(hours=position + 1)
        last = position == len(lines) - 1
        message = Message.objects.create(conversation=conversation, sender=people[who], body=text)
        Message.objects.filter(pk=message.pk).update(
            created_at=sent, read_at=None if last else min(sent + timedelta(minutes=20), now),
        )
        messages.append(sent)
    Conversation.objects.filter(pk=conversation.pk).update(first_message_at=messages[0], last_message_at=messages[-1])
    conversation.refresh_from_db()
    return conversation
