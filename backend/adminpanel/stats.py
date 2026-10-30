"""
The numbers on the admin Overview. Every count is of what is in the database, synthetic rows included, with the
synthetic share given next to it, so a demo database is never mistaken for real use.
"""

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.models import User
from applications.models import Application, ApplicationStatusEvent
from applications.transitions import Status
from gigs.feed import apply_feed_rules
from gigs.models import Gig
from profiles.models import FreelancerProfile

WINDOW_DAYS = 30


def window_start():
    """Midnight, local time, at the start of the 30-day window (today and the 29 days before it)."""
    first_day = timezone.localdate() - timedelta(days=WINDOW_DAYS - 1)
    return timezone.make_aware(timezone.datetime.combine(first_day, timezone.datetime.min.time()))


def daily_counts(queryset, start):
    """[{'date': 'YYYY-MM-DD', 'count': n}, ...] for each of the 30 days, zero where there were none."""
    per_day = {
        row['day']: row['n']
        for row in queryset.filter(created_at__gte=start)
        .annotate(day=TruncDate('created_at', tzinfo=timezone.get_current_timezone()))
        .order_by()
        .values('day')
        .annotate(n=Count('id'))
    }
    first_day = timezone.localdate(start)
    days = [first_day + timedelta(days=offset) for offset in range(WINDOW_DAYS)]
    return [{'date': day.isoformat(), 'count': per_day.get(day, 0)} for day in days]


def platform_stats():
    start = window_start()
    users = User.objects.filter(deleted_at__isnull=True)
    by_role = {role: 0 for role in User.Role.values}
    for row in users.order_by().values('role').annotate(n=Count('id')):
        by_role[row['role']] = row['n']

    open_gigs = apply_feed_rules(Gig.objects.all(), include_closed=False)
    applications = Application.objects.all()
    recent_applications = applications.filter(created_at__gte=start)
    hires = ApplicationStatusEvent.objects.filter(to_status=Status.HIRED)

    return {
        'window_days': WINDOW_DAYS,
        'users': {
            'total': users.count(),
            'by_role': by_role,
            'synthetic': users.filter(is_synthetic=True).count(),
            'suspended': users.filter(account_status=User.AccountStatus.SUSPENDED).count(),
            'new_last_30_days': users.filter(created_at__gte=start).count(),
        },
        'verifications': {
            'pending': FreelancerProfile.objects.filter(
                verification_status=FreelancerProfile.VerificationStatus.PENDING,
            ).count(),
        },
        'gigs': {
            # The same rule as the public feed, so this is the number of gigs a freelancer can see and apply to.
            'open': open_gigs.count(),
            'open_synthetic': open_gigs.filter(is_synthetic=True).count(),
            'posted_last_30_days': Gig.objects.filter(created_at__gte=start).count(),
            'removed': Gig.objects.filter(moderation_status=Gig.Moderation.REMOVED).count(),
        },
        'applications': {
            'total': applications.count(),
            'last_30_days': recent_applications.count(),
            'synthetic_last_30_days': recent_applications.filter(is_synthetic=True).count(),
            'removed': applications.filter(moderation_status=Application.Moderation.REMOVED).count(),
        },
        'hires': {
            'total': applications.filter(status=Status.HIRED).count(),
            'last_30_days': hires.filter(created_at__gte=start).count(),
        },
        'daily_applications': daily_counts(applications, start),
    }
