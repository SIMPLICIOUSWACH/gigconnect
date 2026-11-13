"""
Sample reviews for the planted demo: the demo client (Baraka Home Services) completed a few gigs with Amina, Brian,
Cynthia and some other planted freelancers, and rated them. This gives Find freelancers ratings to sort and filter by,
and the demo profiles something to show.

The gigs and applications are flagged is_demo_extra, which recommendations/platform.py leaves out of training and
evaluation, and reviews themselves are never read by the recommender. So the demo's model sees exactly the same world
with or without them. Running this again replaces the sample reviews. Planted database only.
"""

from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from applications.models import Application, ApplicationStatusEvent
from gigs.models import Gig
from messaging.demo import COVER_LETTER, DEMO_CLIENT, _usual_category, demo_client
from recommendations.evaluation import modes
from recommendations.planted_demo import DEMO_ACCOUNTS, DemoError, require_planted_database

from .models import Review
from .service import refresh_rating

# (rating, review, the freelancer's reply or '') for each completed gig. The three demo freelancers come first.
DEMO_REVIEWS = {
    'premium': [
        (5, 'Careful, thoughtful work and clear updates all the way through. Worth every shilling.',
         'Thank you! It was a pleasure working with your team.'),
        (5, 'Delivered ahead of schedule and handled our changes without any fuss.', ''),
        (4, 'Very good result. One round of revisions took a little longer than planned.', ''),
    ],
    'quick_cash': [
        (5, 'Came the same day and sorted it out in an afternoon.', 'Glad I could help at short notice.'),
        (4, 'Fast and friendly. Exactly what we needed for a small job.', ''),
    ],
    'remote_only': [
        (5, 'Everything was done remotely and communication was excellent.', ''),
        (4, 'Good work and easy to reach online. Would hire again.', 'Thanks, happy to help again.'),
    ],
}
# A few other planted freelancers, so the list has a spread of ratings, including a low one and a single 5.
OTHER_REVIEWS = [
    [(5, 'Great first job together.', '')],
    [(4, 'Solid work.', ''), (4, 'Reliable again the second time.', ''), (5, 'Our go-to for this now.', '')],
    [(3, 'The work was fine but it arrived late.', 'Sorry about the delay. I have since changed how I plan.')],
    [(2, 'Not what we agreed, and hard to reach.', '')],
    [(5, 'Excellent.', ''), (5, 'Excellent again.', '')],
]


def _freelancers():
    """[(freelancer, their reviews)]: the three demo freelancers, then other planted freelancers in a fixed order."""
    chosen = []
    for group, (email, _) in DEMO_ACCOUNTS.items():
        user = User.objects.filter(email=email).first()
        if user is None:
            raise DemoError(f'{email} is missing. Run refresh_planted_demo first.')
        chosen.append((user, DEMO_REVIEWS[group]))
    demo_emails = [email for email, _ in DEMO_ACCOUNTS.values()]
    others = (
        User.objects.filter(
            role=User.Role.FREELANCER, email__startswith=f'{modes.PLANTED_EMAIL_PREFIX}freelancer-',
            is_active=True, deleted_at__isnull=True,
        ).exclude(email__in=demo_emails).order_by('email')[:len(OTHER_REVIEWS)]
    )
    chosen.extend(zip(others, OTHER_REVIEWS))
    return chosen


def seed(now=None):
    """Replace the sample reviews. Returns [(freelancer, number of reviews)]."""
    require_planted_database()
    now = now or timezone.now()
    chosen = _freelancers()

    with transaction.atomic():
        client = demo_client()
        # Only the completed sample gigs: the in-progress ones belong to the sample chats (messaging/demo.py).
        old = Gig.objects.filter(client=client, is_demo_extra=True, status=Gig.Status.COMPLETED)
        rated_before = list(User.objects.filter(reviews_received__gig__in=old).distinct())
        old.delete()
        for freelancer in rated_before:
            refresh_rating(freelancer)

        summary = []
        days_ago = 4
        for freelancer, reviews in chosen:
            category = _usual_category(freelancer)
            for number, (rating, text, reply) in enumerate(reviews, start=1):
                completed_at = now - timedelta(days=days_ago)
                days_ago += 3
                gig = Gig.objects.create(
                    client=client, category=category, title=f'{category.name} job {number} for {freelancer.full_name}',
                    description=f'A completed sample gig for {DEMO_CLIENT[1]}, used to show ratings in the demo.',
                    budget_min=6000, budget_max=12000, deadline=date.today() + timedelta(days=7),
                    application_deadline=(completed_at - timedelta(days=10)).date(),
                    is_synthetic=True, is_demo_extra=True, status=Gig.Status.COMPLETED,
                )
                Gig.objects.filter(pk=gig.pk).update(status_changed_at=completed_at)
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
                review = Review.objects.create(
                    gig=gig, client=client, freelancer=freelancer, rating=rating, text=text,
                    freelancer_reply=reply, reply_at=completed_at + timedelta(days=1) if reply else None,
                )
                written = completed_at + timedelta(hours=3)
                Review.objects.filter(pk=review.pk).update(created_at=written, updated_at=written)
            refresh_rating(freelancer)
            summary.append((freelancer, len(reviews)))
    return summary
