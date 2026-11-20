"""
The pieces both commands build history from: a gig, an application with its status history, a chat opened on a hire,
a review, a notification. Each one is flagged is_synthetic and is_demo_extra (so the recommender never trains or is
scored on it), has its dates set explicitly, and is recorded in the ledger so --undo can remove it.

An application's history follows applications/transitions.py exactly: the client moves it forward one step at a time
and can reject from any live stage, the freelancer can only withdraw before being shortlisted. A history that breaks
those rules (or goes backwards in time) is refused here, so no command can write one.
"""

from datetime import timedelta

from applications.models import Application, ApplicationStatusEvent
from applications.transitions import Actor, Status, can_transition
from gigs.models import Gig
from messaging.models import Conversation, Message
from notifications.models import Notification
from reviews.models import Review

HIRE_STEPS = (Status.UNDER_REVIEW, Status.SHORTLISTED, Status.HIRED)


class HistoryError(ValueError):
    pass


def round_to(amount, step=500):
    return int(round(amount / step) * step)


def create_gig(
    ctx, *, client, category, title, description, skills, status, posted_at, window_days, delivery_days, budget,
    county=None, is_remote=False, changed_at=None,
):
    """A flagged gig. `changed_at` is when it reached its status (completed or closed); open gigs have none."""
    gig = Gig.objects.create(
        client=client, category=category, title=title, description=description, budget_min=budget[0],
        budget_max=budget[1], deadline=(posted_at + timedelta(days=delivery_days)).date(),
        application_deadline=(posted_at + timedelta(days=window_days)).date(), county=county, is_remote=is_remote,
        is_synthetic=True, is_demo_extra=True, status=status,
    )
    gig.skills.set(skills)
    Gig.objects.filter(pk=gig.pk).update(
        created_at=posted_at, updated_at=changed_at or posted_at, status_changed_at=changed_at or posted_at,
    )
    ctx.ledger.created(gig)
    ctx.count(f'{status} gigs')
    ctx.touch(client, posted_at)
    gig.refresh_from_db()
    return gig


def add_application(ctx, gig, freelancer, applied_at, steps=(), *, cover_letter, proposed_rate=None):
    """
    An application and its status events. `steps` is [(status, when), ...] after the first pending one, in order.
    Raises HistoryError if a step is not allowed or the times do not increase.
    """
    current, last = Status.PENDING, applied_at
    events = [('', Status.PENDING, freelancer, applied_at)]
    for status, when in steps:
        actor = Actor.FREELANCER if status == Status.WITHDRAWN else Actor.CLIENT
        if not can_transition(current, status, actor):
            raise HistoryError(f'An application cannot go from {current} to {status} as the {actor}.')
        if when <= last:
            raise HistoryError(f'{status} at {when} is not after {last}.')
        events.append((current, status, freelancer if actor == Actor.FREELANCER else gig.client, when))
        current, last = status, when
    application = Application.objects.create(
        gig=gig, freelancer=freelancer, cover_letter=cover_letter, proposed_rate=proposed_rate, status=current,
        is_synthetic=True, is_demo_extra=True,
    )
    Application.objects.filter(pk=application.pk).update(created_at=applied_at, updated_at=last)
    for from_status, to_status, by, when in events:
        event = ApplicationStatusEvent.objects.create(
            application=application, from_status=from_status, to_status=to_status, changed_by=by,
        )
        ApplicationStatusEvent.objects.filter(pk=event.pk).update(created_at=when)
    ctx.count('applications')
    ctx.touch(freelancer, applied_at)
    application.refresh_from_db()
    return application


def open_conversation(ctx, application, opened_at):
    """The chat the app opens when a client hires. Quiet until someone writes."""
    conversation = Conversation.objects.create(
        application=application, gig=application.gig, client=application.gig.client,
        freelancer=application.freelancer,
    )
    Conversation.objects.filter(pk=conversation.pk).update(created_at=opened_at)
    ctx.count('conversations')
    conversation.refresh_from_db()
    return conversation


def write_messages(ctx, conversation, lines, started_at, unread_from=None, gap=None):
    """
    Messages from [(who, text), ...] where who is 'client' or 'freelancer', the client first, spaced out from
    `started_at`. From index `unread_from` on they are unread. Times are kept in step on the conversation.
    """
    people = {'client': conversation.client, 'freelancer': conversation.freelancer}
    if lines and lines[0][0] != 'client':
        raise HistoryError('The client writes first.')
    sent = started_at
    times = []
    for position, (who, body) in enumerate(lines):
        sent = sent + (gap[position] if gap else timedelta(hours=3 + position))
        message = Message.objects.create(conversation=conversation, sender=people[who], body=body)
        read_at = None if unread_from is not None and position >= unread_from else sent + timedelta(minutes=25)
        Message.objects.filter(pk=message.pk).update(created_at=sent, read_at=read_at)
        times.append(sent)
        ctx.count('messages')
    Conversation.objects.filter(pk=conversation.pk).update(first_message_at=times[0], last_message_at=times[-1])
    return times


def add_review(ctx, gig, freelancer, rating, text, written_at, reply='', reply_at=None):
    review = Review.objects.create(
        gig=gig, client=gig.client, freelancer=freelancer, rating=rating, text=text, freelancer_reply=reply,
        reply_at=reply_at if reply else None,
    )
    Review.objects.filter(pk=review.pk).update(created_at=written_at, updated_at=reply_at or written_at)
    ctx.count('reviews')
    if reply:
        ctx.count('replies')
    return review


def add_notification(ctx, recipient, kind, title, body, link, at, read=False):
    note = Notification.objects.create(recipient=recipient, kind=kind, title=title, body=body, link=link)
    Notification.objects.filter(pk=note.pk).update(created_at=at, read_at=at + timedelta(hours=2) if read else None)
    ctx.ledger.created(note)
    ctx.count('notifications')
    return note
