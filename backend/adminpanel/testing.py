"""Helpers shared by the admin panel's tests."""

from datetime import date, timedelta

from accounts.models import User
from applications.models import Application
from gigs.models import Category, Gig

PASSWORD = 'x-Admin-test-pass-1'
LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'


class AdminTestMixin:
    def make_user(self, email, role, **extra):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password=PASSWORD, full_name=extra.pop('full_name', email.split('@')[0].title()),
            phone=f'2547100{number:05d}', role=role, is_email_verified=True, **extra,
        )

    def make_admin(self, email='admin@example.com'):
        return self.make_user(email, User.Role.ADMIN, is_staff=True)

    def make_gig(self, client, title='Logo for a bakery', category=None, **extra):
        category = category or Category.objects.get_or_create(name='Admin Test Category')[0]
        return Gig.objects.create(
            client=client, category=category, title=title, description='A clean logo for a small bakery in Nakuru.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30), **extra,
        )

    def apply(self, gig, freelancer, **extra):
        return Application.objects.create(gig=gig, freelancer=freelancer, cover_letter=LETTER, **extra)
