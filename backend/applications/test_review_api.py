from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from gigs.models import Gig

from .models import Application, ApplicationStatusEvent
from .test_api import LETTER, ApplicationApiBase
from .transitions import Status


class ListApplicantsTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('gig-applications', args=[self.gig.id])
        self.client.force_authenticate(user=self.client_user)

    def test_owner_sees_applicants_with_the_details_a_client_needs(self):
        self.make_application(portfolio_link='https://example.com/me')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        row = response.data['results'][0]
        self.assertEqual(row['cover_letter'], LETTER)
        self.assertEqual(row['portfolio_link'], 'https://example.com/me')
        self.assertEqual(row['applicant']['full_name'], self.freelancer.full_name)
        self.assertIn('skills', row['applicant'])
        self.assertIn('verification_status', row['applicant'])
        self.assertEqual(row['allowed_next_statuses'], ['under_review', 'rejected'])

    def test_only_this_gigs_applications_are_listed(self):
        self.make_application()
        self.make_application(gig=self.make_gig('Another gig'), freelancer=self.other_freelancer)
        self.assertEqual(len(self.client.get(self.url).data['results']), 1)

    def test_another_client_is_refused(self):
        other_client = self.make_user('api-client-2@example.com', 'client', '254700000205')
        self.client.force_authenticate(user=other_client)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_freelancers_are_refused_even_the_applicant(self):
        self.make_application()
        self.client.force_authenticate(user=self.freelancer)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_signed_out_is_refused(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_unknown_gig_is_404(self):
        url = reverse('gig-applications', args=['00000000-0000-0000-0000-000000000000'])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_status_filter_and_counts(self):
        self.make_application()
        self.make_application(freelancer=self.other_freelancer, status=Status.SHORTLISTED)
        response = self.client.get(self.url, {'status': 'shortlisted'})
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'shortlisted')
        self.assertEqual(response.data['status_counts']['pending'], 1)
        self.assertEqual(response.data['status_counts']['total'], 2)

    def test_unknown_status_is_400(self):
        self.assertEqual(self.client.get(self.url, {'status': 'nonsense'}).status_code, 400)

    def test_newest_first(self):
        first = self.make_application()
        second = self.make_application(freelancer=self.other_freelancer)
        Application.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(days=1))
        ids = [row['id'] for row in self.client.get(self.url).data['results']]
        self.assertEqual(ids, [str(second.id), str(first.id)])

    def test_closed_gig_applications_can_still_be_listed(self):
        self.make_application()
        Gig.objects.filter(pk=self.gig.pk).update(status=Gig.Status.CLOSED)
        self.assertEqual(len(self.client.get(self.url).data['results']), 1)

    def add_applicant_with_history(self, freelancer):
        application = self.make_application(freelancer=freelancer)
        ApplicationStatusEvent.objects.create(
            application=application, from_status='', to_status='pending', changed_by=freelancer,
        )

    def test_query_count_does_not_grow_with_applicants(self):
        self.add_applicant_with_history(self.freelancer)
        # gig, status counts, page count, applications, events, event authors, skills
        with self.assertNumQueries(7):
            self.client.get(self.url)
        for index in range(4):
            freelancer = self.make_user(f'api-extra-{index}@example.com', 'freelancer', f'25470000030{index}')
            self.add_applicant_with_history(freelancer)
        with self.assertNumQueries(7):
            self.client.get(self.url)


class ChangeStatusTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.application = self.make_application()
        self.url = reverse('application-status', args=[self.application.id])
        self.client.force_authenticate(user=self.client_user)

    def move(self, status, note=None, url=None):
        body = {'status': status}
        if note is not None:
            body['note'] = note
        return self.client.patch(url or self.url, body, format='json')

    def set_status(self, status):
        Application.objects.filter(pk=self.application.pk).update(status=status)

    def test_owner_can_move_an_application_forward(self):
        response = self.move('under_review')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'under_review')
        self.assertEqual(response.data['allowed_next_statuses'], ['shortlisted', 'rejected'])
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Status.UNDER_REVIEW)

    def test_a_status_event_records_who_and_why(self):
        self.move('rejected', note='  Budget too high  ')
        event = ApplicationStatusEvent.objects.get(application=self.application)
        self.assertEqual(event.from_status, Status.PENDING)
        self.assertEqual(event.to_status, Status.REJECTED)
        self.assertEqual(event.note, 'Budget too high')
        self.assertEqual(event.changed_by, self.client_user)

    def test_note_is_optional(self):
        self.assertEqual(self.move('under_review').status_code, 200)
        self.assertEqual(ApplicationStatusEvent.objects.get().note, '')

    def test_note_has_a_length_limit(self):
        response = self.move('under_review', note='x' * 501)
        self.assertEqual(response.status_code, 400)
        self.assertIn('note', response.data)

    def test_skipping_a_step_is_refused(self):
        response = self.move('shortlisted')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'An application that is pending cannot be moved to shortlisted.')
        self.assertEqual(ApplicationStatusEvent.objects.count(), 0)

    def test_client_cannot_withdraw_for_the_freelancer(self):
        self.assertEqual(self.move('withdrawn').status_code, 400)

    def test_final_statuses_cannot_be_changed(self):
        for status in (Status.REJECTED, Status.WITHDRAWN, Status.HIRED):
            self.set_status(status)
            self.assertEqual(self.move('under_review').status_code, 400, status)

    def test_unknown_or_missing_status_is_400(self):
        self.assertEqual(self.move('nonsense').status_code, 400)
        self.assertEqual(self.client.patch(self.url, {}, format='json').status_code, 400)

    def test_another_client_gets_404(self):
        other_client = self.make_user('api-client-2@example.com', 'client', '254700000205')
        self.client.force_authenticate(user=other_client)
        self.assertEqual(self.move('under_review').status_code, 404)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Status.PENDING)

    def test_freelancer_is_refused(self):
        self.client.force_authenticate(user=self.freelancer)
        self.assertEqual(self.move('under_review').status_code, 403)

    def test_signed_out_is_refused(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.move('under_review').status_code, 401)

    def test_unknown_application_is_404(self):
        url = reverse('application-status', args=['00000000-0000-0000-0000-000000000000'])
        self.assertEqual(self.move('under_review', url=url).status_code, 404)

    def test_get_and_put_are_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.put(self.url, {'status': 'under_review'}, format='json').status_code, 405)

    def test_review_still_works_after_the_gig_is_closed(self):
        Gig.objects.filter(pk=self.gig.pk).update(status=Gig.Status.CLOSED)
        self.assertEqual(self.move('under_review').status_code, 200)
        self.assertEqual(self.move('rejected').status_code, 200)


class HiringTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.application = self.make_application(status=Status.SHORTLISTED)
        self.other = self.make_application(freelancer=self.other_freelancer)
        self.url = reverse('application-status', args=[self.application.id])
        self.client.force_authenticate(user=self.client_user)

    def hire(self, application=None):
        url = reverse('application-status', args=[(application or self.application).id])
        return self.client.patch(url, {'status': 'hired'}, format='json')

    def test_hiring_marks_the_application_hired_and_the_gig_in_progress(self):
        response = self.hire()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'hired')
        self.assertEqual(response.data['gig_status'], 'in_progress')
        self.gig.refresh_from_db()
        self.assertEqual(self.gig.status, Gig.Status.IN_PROGRESS)

    def test_other_applications_are_left_alone(self):
        self.hire()
        self.other.refresh_from_db()
        self.assertEqual(self.other.status, Status.PENDING)
        self.assertEqual(ApplicationStatusEvent.objects.filter(application=self.other).count(), 0)

    def test_only_one_person_can_be_hired(self):
        Application.objects.filter(pk=self.other.pk).update(status=Status.SHORTLISTED)
        self.assertEqual(self.hire().status_code, 200)
        response = self.hire(self.other)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'You have already hired someone for this gig.')
        self.other.refresh_from_db()
        self.assertEqual(self.other.status, Status.SHORTLISTED)

    def test_a_hire_must_be_shortlisted_first(self):
        response = self.hire(self.other)
        self.assertEqual(response.status_code, 400)
        self.gig.refresh_from_db()
        self.assertEqual(self.gig.status, Gig.Status.OPEN)

    def test_cannot_hire_on_a_closed_or_completed_gig(self):
        for gig_status in (Gig.Status.CLOSED, Gig.Status.COMPLETED):
            Gig.objects.filter(pk=self.gig.pk).update(status=gig_status)
            response = self.hire()
            self.assertEqual(response.status_code, 400, gig_status)
            self.assertEqual(response.data['detail'], 'You can only hire for a gig that is open or in progress.')
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Status.SHORTLISTED)

    def test_hiring_on_a_gig_already_in_progress_keeps_it_there(self):
        Gig.objects.filter(pk=self.gig.pk).update(status=Gig.Status.IN_PROGRESS)
        self.assertEqual(self.hire().status_code, 200)
        self.gig.refresh_from_db()
        self.assertEqual(self.gig.status, Gig.Status.IN_PROGRESS)

    def test_a_rejected_hire_changes_nothing(self):
        Gig.objects.filter(pk=self.gig.pk).update(status=Gig.Status.CLOSED)
        self.hire()
        self.assertEqual(ApplicationStatusEvent.objects.count(), 0)


class MyGigsCountTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('gig-mine')
        self.client.force_authenticate(user=self.client_user)

    def row(self, gig):
        return next(item for item in self.client.get(self.url).data if item['id'] == str(gig.id))

    def test_gig_with_no_applications_has_zero_counts(self):
        row = self.row(self.gig)
        self.assertEqual(row['application_count'], 0)
        self.assertEqual(row['pending_application_count'], 0)

    def test_counts_are_per_gig(self):
        second = self.make_gig('Second gig')
        self.make_application()
        self.make_application(freelancer=self.other_freelancer, status=Status.UNDER_REVIEW)
        self.make_application(gig=second, status=Status.REJECTED)
        first_row = self.row(self.gig)
        self.assertEqual(first_row['application_count'], 2)
        self.assertEqual(first_row['pending_application_count'], 1)
        second_row = self.row(second)
        self.assertEqual(second_row['application_count'], 1)
        self.assertEqual(second_row['pending_application_count'], 0)

    def test_withdrawn_applications_still_count_but_are_not_pending(self):
        self.make_application(status=Status.WITHDRAWN)
        row = self.row(self.gig)
        self.assertEqual(row['application_count'], 1)
        self.assertEqual(row['pending_application_count'], 0)

    def test_counts_do_not_leak_into_the_public_feed(self):
        self.make_application()
        self.client.force_authenticate(user=None)
        feed = self.client.get(reverse('gig-list-create')).data['results']
        self.assertNotIn('application_count', feed[0])

    def test_query_count_does_not_grow_with_gigs(self):
        self.make_application()
        with self.assertNumQueries(2):
            self.client.get(self.url)
        for index in range(4):
            self.make_application(gig=self.make_gig(f'Extra {index}'))
        with self.assertNumQueries(2):
            self.client.get(self.url)
