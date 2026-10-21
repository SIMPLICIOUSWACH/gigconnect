from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from gigs.models import Category, Gig, GigInteraction

from .models import Application, ApplicationStatusEvent
from .transitions import Status

LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'


class ApplicationApiBase(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Application Api Category')
        self.client_user = self.make_user('api-client@example.com', 'client', '254700000201')
        self.freelancer = self.make_user('api-freelancer@example.com', 'freelancer', '254700000202')
        self.other_freelancer = self.make_user('api-freelancer-2@example.com', 'freelancer', '254700000203')
        self.gig = self.make_gig('Logo for a cafe')

    def make_user(self, email, role, phone, verified=True):
        user = User.objects.create_user(
            email=email, password='StrongPass123!', full_name=email.split('@')[0], phone=phone, role=role,
        )
        user.is_email_verified = verified
        user.save(update_fields=['is_email_verified'])
        return user

    def make_gig(self, title, **overrides):
        fields = {
            'client': self.client_user, 'category': self.category, 'title': title, 'description': 'A gig.',
            'budget_min': 1000, 'budget_max': 2000, 'deadline': date.today() + timedelta(days=30),
        }
        fields.update(overrides)
        return Gig.objects.create(**fields)

    def make_application(self, gig=None, freelancer=None, **overrides):
        fields = {'gig': gig or self.gig, 'freelancer': freelancer or self.freelancer, 'cover_letter': LETTER}
        fields.update(overrides)
        return Application.objects.create(**fields)

    def apply_url(self, gig=None):
        return reverse('gig-applications', args=[(gig or self.gig).id])

    def apply(self, data=None, gig=None):
        return self.client.post(self.apply_url(gig), data or {'cover_letter': LETTER}, format='json')


class ApplyToGigTests(ApplicationApiBase):
    def test_verified_freelancer_can_apply(self):
        self.client.force_authenticate(user=self.freelancer)
        body = {'cover_letter': LETTER, 'portfolio_link': 'https://example.com', 'proposed_rate': '1500'}
        response = self.apply(body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], Status.PENDING)
        self.assertEqual(str(response.data['gig_id']), str(self.gig.id))
        application = Application.objects.get(freelancer=self.freelancer, gig=self.gig)
        self.assertEqual(str(application.proposed_rate), '1500.00')

    def test_applying_writes_the_first_status_event(self):
        self.client.force_authenticate(user=self.freelancer)
        self.apply()
        event = ApplicationStatusEvent.objects.get()
        self.assertEqual(event.from_status, '')
        self.assertEqual(event.to_status, Status.PENDING)
        self.assertEqual(event.changed_by, self.freelancer)

    def test_applying_logs_an_apply_interaction(self):
        self.client.force_authenticate(user=self.freelancer)
        self.apply()
        self.assertEqual(GigInteraction.objects.filter(type=GigInteraction.Type.APPLY, gig=self.gig).count(), 1)

    def test_signed_out_user_is_refused(self):
        self.assertEqual(self.apply().status_code, 401)

    def test_client_role_is_refused(self):
        self.client.force_authenticate(user=self.client_user)
        self.assertEqual(self.apply().status_code, 403)

    def test_unverified_freelancer_is_refused(self):
        unverified = self.make_user('api-unverified@example.com', 'freelancer', '254700000204', verified=False)
        self.client.force_authenticate(user=unverified)
        self.assertEqual(self.apply().status_code, 403)
        self.assertEqual(Application.objects.count(), 0)


class ApplyRuleTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.freelancer)

    def test_unknown_gig_is_404(self):
        url = reverse('gig-applications', args=['00000000-0000-0000-0000-000000000000'])
        response = self.client.post(url, {'cover_letter': LETTER}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['detail'], 'This gig does not exist.')

    def test_cannot_apply_to_own_gig(self):
        own = self.make_gig('My own gig', client=self.freelancer)
        response = self.apply(gig=own)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['detail'], 'You cannot apply to your own gig.')

    def test_closed_gig_is_refused(self):
        self.gig.status = Gig.Status.CLOSED
        self.gig.save(update_fields=['status'])
        response = self.apply()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'This gig is no longer accepting applications.')

    def test_gig_in_progress_is_refused(self):
        self.gig.status = Gig.Status.IN_PROGRESS
        self.gig.save(update_fields=['status'])
        self.assertEqual(self.apply().status_code, 400)

    def test_passed_application_deadline_is_refused(self):
        Gig.objects.filter(pk=self.gig.pk).update(application_deadline=date.today() - timedelta(days=1))
        response = self.apply()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'The application deadline for this gig has passed.')

    def test_passed_delivery_deadline_is_used_when_no_application_deadline(self):
        # save() normally fills application_deadline in, so clear it the way an old row might be.
        Gig.objects.filter(pk=self.gig.pk).update(application_deadline=None, deadline=date.today() - timedelta(days=1))
        self.assertEqual(self.apply().status_code, 400)

    def test_cannot_apply_twice(self):
        self.assertEqual(self.apply().status_code, 201)
        response = self.apply()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'You have already applied to this gig.')
        self.assertEqual(Application.objects.filter(freelancer=self.freelancer).count(), 1)

    def test_cannot_reapply_after_withdrawing(self):
        self.make_application(status=Status.WITHDRAWN)
        response = self.apply()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['detail'], 'You withdrew your application to this gig and cannot apply again.'
        )

    def test_failed_apply_leaves_no_event_or_interaction(self):
        self.make_application()
        self.apply()
        self.assertEqual(ApplicationStatusEvent.objects.count(), 0)
        self.assertEqual(GigInteraction.objects.filter(type=GigInteraction.Type.APPLY).count(), 0)

    def test_another_freelancer_can_still_apply(self):
        self.make_application(freelancer=self.other_freelancer)
        self.assertEqual(self.apply().status_code, 201)


class ApplyValidationTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.freelancer)

    def test_cover_letter_is_required(self):
        response = self.apply({'portfolio_link': 'https://example.com'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['cover_letter'][0], 'Please write a cover letter.')

    def test_short_cover_letter_is_refused(self):
        response = self.apply({'cover_letter': 'Too short'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('at least', response.data['cover_letter'][0])

    def test_long_cover_letter_is_refused(self):
        response = self.apply({'cover_letter': 'x' * 3001})
        self.assertEqual(response.status_code, 400)
        self.assertIn('at most', response.data['cover_letter'][0])

    def test_bad_portfolio_link_is_refused(self):
        response = self.apply({'cover_letter': LETTER, 'portfolio_link': 'not a link'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('portfolio_link', response.data)

    def test_zero_rate_is_refused(self):
        response = self.apply({'cover_letter': LETTER, 'proposed_rate': '0'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['proposed_rate'][0], 'The proposed rate must be more than zero.')

    def test_rate_and_link_are_optional(self):
        self.assertEqual(self.apply({'cover_letter': LETTER}).status_code, 201)

    def test_invalid_body_saves_nothing(self):
        self.apply({'cover_letter': 'Too short'})
        self.assertEqual(Application.objects.count(), 0)
        self.assertEqual(ApplicationStatusEvent.objects.count(), 0)


class MyApplicationsTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('my-applications')
        self.client.force_authenticate(user=self.freelancer)

    def test_lists_only_my_applications(self):
        mine = self.make_application()
        self.make_application(freelancer=self.other_freelancer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.data['results']], [str(mine.id)])

    def test_rows_show_the_gig_and_client(self):
        self.make_application()
        row = self.client.get(self.url).data['results'][0]
        self.assertEqual(row['gig_title'], 'Logo for a cafe')
        self.assertEqual(row['client_name'], self.client_user.full_name)
        self.assertNotIn('cover_letter', row)

    def test_status_counts_cover_every_status(self):
        self.make_application()
        self.make_application(gig=self.make_gig('Second'), status=Status.HIRED)
        counts = self.client.get(self.url).data['status_counts']
        self.assertEqual(counts['pending'], 1)
        self.assertEqual(counts['hired'], 1)
        self.assertEqual(counts['withdrawn'], 0)
        self.assertEqual(counts['total'], 2)

    def test_status_filter_narrows_rows_but_not_counts(self):
        self.make_application()
        self.make_application(gig=self.make_gig('Second'), status=Status.HIRED)
        response = self.client.get(self.url, {'status': 'hired'})
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'hired')
        self.assertEqual(response.data['status_counts']['total'], 2)

    def test_unknown_status_is_400(self):
        self.assertEqual(self.client.get(self.url, {'status': 'nonsense'}).status_code, 400)

    def test_newest_first(self):
        first = self.make_application()
        second = self.make_application(gig=self.make_gig('Second'))
        Application.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(days=1))
        ids =[row['id'] for row in self.client.get(self.url).data['results']]
        self.assertEqual(ids, [str(second.id), str(first.id)])

    def test_empty_list_still_has_counts(self):
        response = self.client.get(self.url)
        self.assertEqual(response.data['results'], [])
        self.assertEqual(response.data['status_counts']['total'], 0)

    def test_client_role_is_refused(self):
        self.client.force_authenticate(user=self.client_user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_signed_out_is_refused(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_query_count_does_not_grow_with_rows(self):
        self.make_application()
        # status counts, page count, page of rows (gig and client joined in)
        with self.assertNumQueries(3):
            self.client.get(self.url)
        for index in range(5):
            self.make_application(gig=self.make_gig(f'Gig {index}'))
        with self.assertNumQueries(3):
            self.client.get(self.url)


class ApplicationDetailTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.application = self.make_application()
        self.url = reverse('application-detail', args=[self.application.id])

    def test_applicant_can_see_it(self):
        self.client.force_authenticate(user=self.freelancer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['cover_letter'], LETTER)
        self.assertEqual(response.data['applicant']['id'], str(self.freelancer.id))

    def test_gig_owner_can_see_it(self):
        self.client.force_authenticate(user=self.client_user)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_other_users_get_404(self):
        self.client.force_authenticate(user=self.other_freelancer)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        other_client = self.make_user('api-client-2@example.com', 'client', '254700000205')
        self.client.force_authenticate(user=other_client)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_signed_out_is_refused(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_allowed_next_statuses_depend_on_the_viewer(self):
        self.client.force_authenticate(user=self.freelancer)
        self.assertEqual(self.client.get(self.url).data['allowed_next_statuses'], ['withdrawn'])
        self.client.force_authenticate(user=self.client_user)
        self.assertEqual(self.client.get(self.url).data['allowed_next_statuses'], ['under_review', 'rejected'])

    def test_events_are_included_with_names(self):
        ApplicationStatusEvent.objects.create(
            application=self.application, from_status='', to_status='pending', changed_by=self.freelancer,
        )
        self.client.force_authenticate(user=self.freelancer)
        events = self.client.get(self.url).data['events']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['changed_by_name'], self.freelancer.full_name)


class WithdrawTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.application = self.make_application()
        self.url = reverse('application-withdraw', args=[self.application.id])
        self.client.force_authenticate(user=self.freelancer)

    def set_status(self, status):
        Application.objects.filter(pk=self.application.pk).update(status=status)

    def test_applicant_can_withdraw(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], Status.WITHDRAWN)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Status.WITHDRAWN)

    def test_withdraw_writes_an_event_with_the_reason(self):
        self.client.post(self.url, {'reason': '  Found other work  '}, format='json')
        event = ApplicationStatusEvent.objects.get(application=self.application)
        self.assertEqual(event.from_status, Status.PENDING)
        self.assertEqual(event.to_status, Status.WITHDRAWN)
        self.assertEqual(event.note, 'Found other work')
        self.assertEqual(event.changed_by, self.freelancer)

    def test_reason_is_ignored_if_not_text(self):
        response = self.client.post(self.url, {'reason': ['a', 'b']}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ApplicationStatusEvent.objects.get().note, '')

    def test_under_review_can_be_withdrawn(self):
        self.set_status(Status.UNDER_REVIEW)
        self.assertEqual(self.client.post(self.url).status_code, 200)

    def test_cannot_withdraw_twice(self):
        self.client.post(self.url)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['detail'],
            'An application can only be withdrawn while it is pending or under review.',
        )

    def test_cannot_withdraw_once_shortlisted_hired_or_rejected(self):
        for status in (Status.SHORTLISTED, Status.HIRED, Status.REJECTED):
            self.set_status(status)
            self.assertEqual(self.client.post(self.url).status_code, 400, status)
        self.assertEqual(ApplicationStatusEvent.objects.count(), 0)

    def test_someone_elses_application_is_404(self):
        self.client.force_authenticate(user=self.other_freelancer)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Status.PENDING)

    def test_client_role_is_refused(self):
        self.client.force_authenticate(user=self.client_user)
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_signed_out_is_refused(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.post(self.url).status_code, 401)
