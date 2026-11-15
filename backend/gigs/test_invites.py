from datetime import date, timedelta

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from applications.models import Application
from messaging.models import Conversation
from notifications.models import Notification
from usersettings.models import NotificationPreference

from .models import Category, Gig, GigInvite


class InviteTestCase(APITestCase):
    def setUp(self):
        self.count = 0
        self.client_user = self.user('client@example.com', 'client', 'Wanjiru Bakers')
        self.freelancer = self.user('otieno@example.com', 'freelancer', 'Otieno Designs')
        self.category = Category.objects.create(name='Invite Test Category')
        self.gig = self.make_gig('Logo for a bakery')
        self.url = f'/api/gigs/{self.gig.pk}/invites/'
        self.client.force_authenticate(self.client_user)

    def user(self, email, role, name, **extra):
        self.count += 1
        return User.objects.create_user(
            email=email, password='x-Invite-test-1', full_name=name, phone=f'2547130{self.count:05d}', role=role,
            is_email_verified=True, **extra,
        )

    def make_gig(self, title, client=None, **extra):
        return Gig.objects.create(
            client=client or self.client_user, category=self.category, title=title,
            description='A clean logo for a small bakery in Nakuru.', budget_min=1000, budget_max=2000,
            deadline=date.today() + timedelta(days=30), **extra,
        )

    def invite(self, freelancer=None, url=None):
        body = {'freelancer_id': (freelancer or self.freelancer).pk}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url or self.url, body, format='json')


class InviteTests(InviteTestCase):
    def test_inviting_notifies_and_emails_the_freelancer_with_the_gig_link(self):
        response = self.invite()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['detail'], 'Otieno Designs was invited to apply.')
        notice = Notification.objects.get(recipient=self.freelancer, kind='gig_invite')
        self.assertEqual(notice.title, 'Wanjiru Bakers invited you to apply for "Logo for a bakery"')
        self.assertEqual(notice.link, f'/gigs/{self.gig.pk}')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['otieno@example.com'])
        self.assertIn(f'/gigs/{self.gig.pk}', mail.outbox[0].body)

    def test_it_does_not_open_a_chat(self):
        self.invite()
        self.assertFalse(Conversation.objects.exists())

    def test_the_freelancers_settings_are_respected(self):
        NotificationPreference.objects.filter(user=self.freelancer).update(invite_email=False, invite_inapp=False)
        self.assertEqual(self.invite().status_code, 201)
        self.assertFalse(Notification.objects.filter(kind='gig_invite').exists())
        self.assertEqual(mail.outbox, [])
        self.assertEqual(GigInvite.objects.count(), 1)

    def test_one_invite_per_freelancer_per_gig(self):
        self.invite()
        again = self.invite()
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data['detail'], 'You have already invited Otieno Designs to this gig.')
        other_gig = self.make_gig('Menu design')
        self.assertEqual(self.invite(url=f'/api/gigs/{other_gig.pk}/invites/').status_code, 201)
        self.assertEqual(GigInvite.objects.count(), 2)

    def test_someone_who_already_applied_is_not_invited(self):
        Application.objects.create(gig=self.gig, freelancer=self.freelancer, cover_letter='x' * 60)
        response = self.invite()
        self.assertEqual((response.status_code, response.data['detail']),
                         (400, 'Otieno Designs has already applied to this gig.'))

    @override_settings(INVITES_PER_DAY=3)
    def test_the_daily_limit(self):
        people = [self.user(f'f{i}@example.com', 'freelancer', f'Freelancer {i}') for i in range(4)]
        for person in people[:3]:
            self.assertEqual(self.invite(person).status_code, 201)
        blocked = self.invite(people[3])
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.data['detail'], 'You can send 3 invitations a day. Try again tomorrow.')
        # A day later the oldest invites no longer count.
        GigInvite.objects.update(created_at=timezone.now() - timedelta(hours=25))
        self.assertEqual(self.invite(people[3]).status_code, 201)

    def test_only_the_gigs_client_and_only_open_gigs(self):
        other_client = self.user('other@example.com', 'client', 'Other Client')
        self.client.force_authenticate(other_client)
        self.assertEqual(self.invite().status_code, 404)
        self.client.force_authenticate(self.freelancer)
        self.assertEqual(self.invite().status_code, 403)
        self.client.force_authenticate(self.client_user)
        for change in ({'status': 'in_progress'}, {'status': 'closed'}, {'moderation_status': 'removed'},
                       {'application_deadline': date.today() - timedelta(days=1)}):
            Gig.objects.filter(pk=self.gig.pk).update(**change)
            response = self.invite()
            self.assertEqual((response.status_code, response.data['detail']),
                             (400, 'Only open gigs can take invitations.'), change)
            Gig.objects.filter(pk=self.gig.pk).update(
                status='open', moderation_status='visible', application_deadline=date.today() + timedelta(days=5),
            )
        self.assertFalse(GigInvite.objects.exists())

    def test_only_findable_freelancers(self):
        hidden = self.user('hidden@example.com', 'freelancer', 'Hidden Person')
        hidden.freelancer_profile.search_visible = False
        hidden.freelancer_profile.save()
        suspended = self.user('s@example.com', 'freelancer', 'Suspended Person', account_status='suspended')
        for person in (hidden, suspended, self.client_user):
            self.assertEqual(self.invite(person).status_code, 404)

    def test_my_open_gigs_for_a_freelancer_show_what_was_already_done(self):
        applied_to = self.make_gig('Menu design')
        Application.objects.create(gig=applied_to, freelancer=self.freelancer, cover_letter='x' * 60)
        self.make_gig('Closed one', status='closed')
        self.invite()
        data = self.client.get(f'/api/freelancers/{self.freelancer.pk}/invitable-gigs/').data
        rows = {row['title']: (row['invited'], row['applied']) for row in data['gigs']}
        self.assertEqual(rows, {'Logo for a bakery': (True, False), 'Menu design': (False, True)})
        self.assertEqual(data['invites_left'], 19)
