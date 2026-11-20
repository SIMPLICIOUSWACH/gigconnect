"""
A shared check for account deletion. build_world() makes an account with something of every kind deletion touches,
and assert_erased() checks every effect. The self-deletion and the admin-deletion tests both use it, so the two
paths are held to exactly the same result.
"""

import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path

from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from applications.models import Application
from gigs.models import Category, Gig, GigInteraction
from messaging.models import Conversation, Message
from messaging.rules import read_only_reason
from notifications.models import Notification
from profiles.id_privacy import hash_id_number
from usersettings.models import UserSession

from .models import User

PASSWORD = 'x-Delete-test-pass-1'
LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'
ID_KEY = 'a-test-id-hash-key-that-is-long-enough'


class DeletionWorld:
    """Mix into an APITestCase. Private files go to a temporary folder that is removed afterwards."""

    def setUp(self):
        super().setUp()
        self.private = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.private, ignore_errors=True)
        for override in (override_settings(PRIVATE_MEDIA_ROOT=self.private), override_settings(ID_HASH_KEY=ID_KEY)):
            override.enable()
            self.addCleanup(override.disable)

    def person(self, email, role, name, **extra):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password=PASSWORD, full_name=name, phone=f'2547110{number:05d}', role=role,
            is_email_verified=True, **extra,
        )

    def gig(self, client, title, status='open'):
        category = Category.objects.get_or_create(name='Deletion Test Category')[0]
        gig = Gig.objects.create(
            client=client, category=category, title=title, description='A clean logo for a small bakery in Nakuru.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30), status=status,
        )
        return gig

    def build_world(self, role='freelancer'):
        """The account to delete, with history, files, an application or gig, a chat, and live tokens."""
        client = self.person('wanjiru@example.com', 'client', 'Wanjiru Bakers')
        freelancer = self.person('otieno@example.com', 'freelancer', 'Otieno Designs')
        applicant = self.person('achieng@example.com', 'freelancer', 'Achieng Studio')

        # A hire on a gig finished today: its chat is still open, and it is not active work.
        finished = self.gig(client, 'Finished logo', status='in_progress')
        hire = Application.objects.create(gig=finished, freelancer=freelancer, cover_letter=LETTER, status='hired')
        Gig.objects.filter(pk=finished.pk).update(status='completed', status_changed_at=timezone.now())
        conversation = Conversation.objects.create(
            application=hire, gig=finished, client=client, freelancer=freelancer,
        )
        Message.objects.create(conversation=conversation, sender=client, body='Thanks for the logo.')
        Message.objects.create(conversation=conversation, sender=freelancer, body='Glad you like it.')

        # The client's open gig with someone waiting on it, and the freelancer's own pending application.
        open_gig = self.gig(client, 'Menu design')
        waiting = Application.objects.create(gig=open_gig, freelancer=applicant, cover_letter=LETTER)
        pending = Application.objects.create(gig=open_gig, freelancer=freelancer, cover_letter=LETTER,
                                             portfolio_link='https://example.com/otieno', proposed_rate=1500)

        profile = freelancer.freelancer_profile
        profile.id_document.save('id.pdf', ContentFile(b'%PDF-1.4 synthetic id'), save=False)
        profile.selfie.save('selfie.jpg', ContentFile(b'synthetic selfie'), save=False)
        profile.id_number = '12345678'
        profile.id_number_hash = hash_id_number('12345678')
        profile.save()
        for name in (profile.id_document.name, profile.selfie.name):
            assert (self.private / name).is_file(), name  # really in private storage, so "deleted" means something

        user = freelancer if role == 'freelancer' else client
        GigInteraction.objects.create(gig=open_gig if role == 'freelancer' else finished, user=user, type='view')
        Notification.objects.create(recipient=user, kind='password_changed', title='Password changed', body='Hi.')
        refresh = RefreshToken.for_user(user)
        UserSession.objects.create(user=user, jti=refresh['jti'], user_agent='test')

        self.world = {
            'user': user, 'other': client if role == 'freelancer' else freelancer, 'applicant': applicant,
            'conversation': conversation, 'open_gig': open_gig, 'waiting': waiting, 'pending': pending,
            'files': [profile.id_document.name, profile.selfie.name], 'hash': profile.id_number_hash,
            'access': str(refresh.access_token),
        }
        return self.world

    def assert_erased(self):
        """Every effect of deleting world['user'], whichever path deleted it."""
        world = self.world
        user = User.objects.get(pk=world['user'].pk)
        self.assertEqual((user.full_name, user.phone, user.is_active), ('Deleted User', '', False))
        self.assertEqual(user.email, f'deleted-{user.pk}@gigconnect.invalid')
        self.assertIsNotNone(user.deleted_at)
        self.assertFalse(user.has_usable_password())

        self.assertFalse(GigInteraction.objects.filter(user=user).exists())
        self.assertFalse(Notification.objects.filter(recipient=user).exists())

        # Every session ends: the refresh token is blacklisted and the old access token no longer works.
        self.assertFalse(UserSession.objects.filter(user=user).exists())
        outstanding = OutstandingToken.objects.filter(user=user)
        self.assertEqual(BlacklistedToken.objects.filter(token__in=outstanding).count(), outstanding.count())
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {world["access"]}')
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.client.credentials()

        # The chat stays for the other person, read-only, with the deleted side shown as "Deleted user".
        conversation = Conversation.objects.get(pk=world['conversation'].pk)
        self.assertEqual(conversation.messages.count(), 2)
        self.assertEqual(read_only_reason(conversation), 'This account was deleted, so this chat is read-only.')
        self.client.force_authenticate(world['other'])
        detail = self.client.get(f'/api/conversations/{conversation.pk}/').data
        self.assertEqual(detail['other']['full_name'], 'Deleted user')
        self.client.force_authenticate(None)

        if user.role == 'freelancer':
            for application in Application.objects.filter(freelancer=user):
                self.assertEqual((application.cover_letter, application.portfolio_link), ('', ''))
                self.assertIsNone(application.proposed_rate)
            self.assertEqual(Application.objects.get(pk=world['pending'].pk).status, 'withdrawn')
            self.assertEqual(Application.objects.get(pk=world['conversation'].application_id).status, 'hired')
            profile = user.freelancer_profile
            profile.refresh_from_db()
            self.assertFalse(profile.id_document)
            self.assertFalse(profile.selfie)
            self.assertEqual(profile.id_number, '')
            self.assertEqual(profile.id_number_hash, world['hash'])  # kept, so the same ID can't be reused
            for name in world['files']:
                self.assertFalse((self.private / name).exists(), name)
        else:
            # The client's open gig is closed and the freelancer waiting on it is told.
            gig = Gig.objects.get(pk=world['open_gig'].pk)
            self.assertEqual(gig.status, 'closed')
            self.assertIsNotNone(gig.status_changed_at)
            notice = Notification.objects.get(recipient=world['applicant'], kind='gig_closed')
            self.assertEqual(notice.body, "This gig was closed because the client's account was removed.")
