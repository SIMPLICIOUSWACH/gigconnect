"""Helpers for the review tests."""

from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from adminpanel.testing import AdminTestMixin
from applications.models import Application
from gigs.models import Gig

from .models import Review
from .service import refresh_rating


class ReviewTestMixin(AdminTestMixin):
    def completed_gig(self, client=None, freelancer=None, title='Logo', days_ago=1):
        """A gig the client completed `days_ago` days ago, with `freelancer` hired on it."""
        client = client or self.person('client@example.com', User.Role.CLIENT, 'Wanjiru Bakers')
        freelancer = freelancer or self.person('freelancer@example.com', User.Role.FREELANCER, 'Otieno Designs')
        gig = self.make_gig(client, title=title, status='in_progress')
        self.apply(gig, freelancer, status=Application.Status.HIRED)
        Gig.objects.filter(pk=gig.pk).update(
            status='completed', status_changed_at=timezone.now() - timedelta(days=days_ago),
        )
        return Gig.objects.get(pk=gig.pk)

    def person(self, email, role, name):
        return User.objects.filter(email=email).first() or self.make_user(email, role, full_name=name)

    def review(self, gig, rating=5, text='Great work.'):
        """Write a review straight into the database and bring the freelancer's average up to date."""
        freelancer = Application.objects.get(gig=gig, status='hired').freelancer
        review = Review.objects.create(gig=gig, client=gig.client, freelancer=freelancer, rating=rating, text=text)
        refresh_rating(freelancer)
        return review
