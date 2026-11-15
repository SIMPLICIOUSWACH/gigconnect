"""
The rules for reviews, in one place.

- Only the gig's client can rate, only the freelancer hired on that gig, and only once the gig is completed.
- Rating and editing are both open for 14 days after completion (Gig.status_changed_at), then closed for good.
- The freelancer can reply once.
- A freelancer's average and count live on their profile and are recalculated, in the same transaction, whenever a
  review is written, edited, removed or restored. Removed reviews don't count.
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from applications.models import Application
from gigs.models import Gig
from notifications.models import Notification
from notifications.service import notify
from profiles.models import FreelancerProfile

from .models import Review

Kind = Notification.Kind


class ReviewError(ValueError):
    """The change isn't allowed. The message is shown to the person."""


def review_window():
    return timedelta(days=settings.REVIEW_WINDOW_DAYS)


def hired_freelancer(gig):
    """The freelancer hired on this gig (a gig has at most one hire), or None."""
    hired = getattr(gig, 'hired_applications', None)
    if hired is None:
        hired = list(
            Application.objects.filter(gig=gig, status=Application.Status.HIRED).select_related('freelancer')
        )
    return hired[0].freelancer if hired else None


def window_closes_at(gig):
    """When rating and editing stop for this gig, or None if it isn't completed."""
    if gig.status != Gig.Status.COMPLETED or gig.status_changed_at is None:
        return None
    return gig.status_changed_at + review_window()


def window_open(gig, now=None):
    closes = window_closes_at(gig)
    return closes is not None and (now or timezone.now()) < closes


def client_name(review):
    return 'Deleted client' if review.client.deleted_at is not None else review.client.full_name


def refresh_rating(freelancer):
    """Recalculate the freelancer's average and count from their visible reviews."""
    totals = Review.objects.filter(freelancer=freelancer, moderation_status=Review.Moderation.VISIBLE).aggregate(
        average=Avg('rating'), count=Count('id'),
    )
    average = round(totals['average'], 2) if totals['average'] is not None else None
    FreelancerProfile.objects.filter(user=freelancer).update(rating_avg=average, rating_count=totals['count'])


def bayesian_rating(prefix=''):
    """
    A queryset expression: the rating to sort by. (C * m + sum of ratings) / (C + count), so one 5-star review can't
    outrank twenty 4.8s, and someone with no reviews sits at the prior mean rather than at 0. `prefix` is the path to
    the freelancer profile, such as 'freelancer_profile__'.
    """
    weight, mean = settings.RATING_PRIOR_WEIGHT, settings.RATING_PRIOR_MEAN
    count = F(f'{prefix}rating_count')
    total = Coalesce(F(f'{prefix}rating_avg'), Value(0.0), output_field=FloatField()) * count
    return ExpressionWrapper((Value(weight * mean) + total) / (Value(float(weight)) + count), output_field=FloatField())


def rating_state(gig, freelancer, review):
    """For the client's My gigs: who they can rate, whether they still can, and their review if they wrote one."""
    if gig.status != Gig.Status.COMPLETED or freelancer is None:
        return None
    is_open = window_open(gig)
    deleted = freelancer.deleted_at is not None
    return {
        'freelancer_id': str(freelancer.pk),
        'freelancer_name': 'Deleted user' if deleted else freelancer.full_name,
        'closes_at': window_closes_at(gig),
        'can_rate': review is None and is_open and not deleted,
        'can_edit': review is not None and is_open and not review.is_removed,
        'review': None if review is None else {
            'id': str(review.pk), 'rating': review.rating, 'text': review.text, 'removed': review.is_removed,
        },
    }


def _check_can_write(client, gig):
    if gig.client_id != client.pk:
        raise ReviewError('Only the client who posted this gig can rate it.')
    if gig.status != Gig.Status.COMPLETED:
        raise ReviewError('You can rate the freelancer once the gig is completed.')
    freelancer = hired_freelancer(gig)
    if freelancer is None:
        raise ReviewError('Nobody was hired on this gig, so there is nobody to rate.')
    if not window_open(gig):
        raise ReviewError(f'Ratings close {settings.REVIEW_WINDOW_DAYS} days after a gig is completed.')
    return freelancer


def create_review(client, gig, rating, text=''):
    freelancer = _check_can_write(client, gig)
    if freelancer.deleted_at is not None:
        raise ReviewError("This freelancer's account was deleted, so it can't be rated.")
    if Review.objects.filter(gig=gig).exists():
        raise ReviewError('You have already rated this gig. You can edit your review instead.')
    with transaction.atomic():
        review = Review.objects.create(gig=gig, client=client, freelancer=freelancer, rating=rating, text=text)
        refresh_rating(freelancer)
        stars = f'{rating} star' if rating == 1 else f'{rating} stars'
        notify(
            freelancer, Kind.REVIEW_RECEIVED, f'{client.full_name} rated your work on "{gig.title}"',
            f'{client.full_name} gave you {stars} for "{gig.title}". You can post one public reply.',
            link=f'/profile/{freelancer.pk}', email_preference='status_change_email',
            inapp_preference='status_change_inapp',
        )
    return review


def update_review(client, review, rating=None, text=None):
    _check_can_write(client, review.gig)
    if review.is_removed:
        raise ReviewError("An administrator removed this review, so it can't be edited.")
    with transaction.atomic():
        if rating is not None:
            review.rating = rating
        if text is not None:
            review.text = text
        review.save(update_fields=['rating', 'text', 'updated_at'])
        refresh_rating(review.freelancer)
    return review


def reply_to_review(freelancer, review, reply):
    if review.freelancer_id != freelancer.pk:
        raise ReviewError('Only the freelancer who was rated can reply.')
    if review.is_removed:
        raise ReviewError("An administrator removed this review, so it can't be replied to.")
    if review.reply_at is not None:
        raise ReviewError('You have already replied to this review.')
    with transaction.atomic():
        review.freelancer_reply = reply
        review.reply_at = timezone.now()
        review.save(update_fields=['freelancer_reply', 'reply_at'])
        if review.client.deleted_at is None:
            notify(
                review.client, Kind.REVIEW_REPLY, f'{freelancer.full_name} replied to your review',
                f'{freelancer.full_name} replied to your review of "{review.gig.title}".',
                link=f'/profile/{freelancer.pk}', email_preference='status_change_email',
                inapp_preference='status_change_inapp',
            )
    return review
