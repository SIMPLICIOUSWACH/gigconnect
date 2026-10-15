"""
Which GigConnect rows the recommender is allowed to learn from.

This is where the privacy rules from Sprint 4 are applied to training. A freelancer who deleted their
account never appears here, and neither do their interactions or applications, so they drop out at the
next training run. The text of an erased application was already cleared at deletion time.

Synthetic rows (flagged is_synthetic by the seed commands) are included or left out by one flag, so a
trained model can always say how much of what it learned from was synthetic.
"""

from accounts.models import User
from applications.models import Application
from gigs.models import Gig, GigInteraction
from profiles.models import FreelancerProfile


def freelancers_for_training(include_synthetic=True):
    """Freelancer profiles of active, non-deleted accounts."""
    profiles = FreelancerProfile.objects.filter(
        user__role=User.Role.FREELANCER, user__is_active=True, user__deleted_at__isnull=True,
    )
    if not include_synthetic:
        profiles = profiles.filter(user__is_synthetic=False)
    return profiles.select_related('user').prefetch_related('skills')


def gigs_for_training(include_synthetic=True):
    """Gigs with their text, skills and category, whatever their status."""
    gigs = Gig.objects.select_related('category').prefetch_related('skills')
    if not include_synthetic:
        gigs = gigs.filter(is_synthetic=False)
    return gigs


def interactions_for_training(include_synthetic=True):
    """
    Signed-in freelancers' interactions. Anonymous visitors cannot be matched to a freelancer, and a
    synthetic interaction or a synthetic freelancer both count as synthetic.
    """
    interactions = GigInteraction.objects.filter(
        user__isnull=False, user__role=User.Role.FREELANCER, user__is_active=True, user__deleted_at__isnull=True,
    )
    if not include_synthetic:
        interactions = interactions.filter(is_synthetic=False, user__is_synthetic=False)
    return interactions


def applications_for_training(include_synthetic=True):
    """Applications of active, non-deleted freelancers."""
    applications = Application.objects.filter(
        freelancer__is_active=True, freelancer__deleted_at__isnull=True,
    )
    if not include_synthetic:
        applications = applications.filter(is_synthetic=False, freelancer__is_synthetic=False)
    return applications
