from gigs.models import Gig, GigInteraction

from .models import Application, ApplicationStatusEvent
from .privacy import ACCOUNT_DELETED_NOTE
from .test_api import LETTER, ApplicationApiBase
from .transitions import Status

PASSWORD = 'StrongPass123!'
EXPORT_URL = '/api/settings/export-data/'
DELETE_URL = '/api/settings/delete-account/'


class ExportApplicationsTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.freelancer)

    def test_export_includes_the_users_applications_and_their_history(self):
        application = self.make_application(portfolio_link='https://example.com/me', proposed_rate='1500')
        ApplicationStatusEvent.objects.create(
            application=application, from_status='', to_status='pending', changed_by=self.freelancer,
        )
        ApplicationStatusEvent.objects.create(
            application=application, from_status='pending', to_status='rejected',
            changed_by=self.client_user, note='Budget too high',
        )
        exported = self.client.get(EXPORT_URL).data['applications']
        self.assertEqual(len(exported), 1)
        row = exported[0]
        self.assertEqual(row['gig_title'], 'Logo for a cafe')
        self.assertEqual(row['cover_letter'], LETTER)
        self.assertEqual(row['portfolio_link'], 'https://example.com/me')
        self.assertEqual(str(row['proposed_rate']), '1500.00')
        self.assertEqual(
            [(h['from_status'], h['to_status'], h['changed_by']) for h in row['status_history']],
            [('', 'pending', 'you'), ('pending', 'rejected', 'client or system')],
        )
        self.assertEqual(row['status_history'][1]['note'], 'Budget too high')

    def test_export_does_not_name_the_client_in_the_history(self):
        application = self.make_application()
        ApplicationStatusEvent.objects.create(
            application=application, from_status='pending', to_status='under_review', changed_by=self.client_user,
        )
        history = self.client.get(EXPORT_URL).data['applications'][0]['status_history']
        self.assertNotIn(self.client_user.full_name, str(history))
        self.assertNotIn(self.client_user.email, str(history))

    def test_export_only_has_the_users_own_applications(self):
        self.make_application()
        self.make_application(freelancer=self.other_freelancer)
        self.assertEqual(len(self.client.get(EXPORT_URL).data['applications']), 1)

    def test_export_is_an_empty_list_for_someone_who_never_applied(self):
        self.client.force_authenticate(user=self.other_freelancer)
        self.assertEqual(self.client.get(EXPORT_URL).data['applications'], [])

    def test_a_client_gets_an_empty_list_not_the_applications_they_received(self):
        self.make_application()
        self.client.force_authenticate(user=self.client_user)
        self.assertEqual(self.client.get(EXPORT_URL).data['applications'], [])


class DeleteAccountApplicationsTests(ApplicationApiBase):
    def setUp(self):
        super().setUp()
        self.gigs = {
            status: self.make_gig(f'Gig for {status}')
            for status in ('pending', 'under_review', 'shortlisted', 'hired', 'rejected', 'withdrawn')
        }
        self.applications = {
            status: self.make_application(
                gig=gig, status=status, portfolio_link='https://example.com/me', proposed_rate='1500',
            )
            for status, gig in self.gigs.items()
        }
        self.client.force_authenticate(user=self.freelancer)

    def delete_account(self, password=PASSWORD):
        return self.client.post(DELETE_URL, {'password': password}, format='json')

    def refresh(self, status):
        application = self.applications[status]
        application.refresh_from_db()
        return application

    def test_open_applications_are_withdrawn_with_a_system_event(self):
        self.assertEqual(self.delete_account().status_code, 200)
        for status in ('pending', 'under_review', 'shortlisted'):
            application = self.refresh(status)
            self.assertEqual(application.status, Status.WITHDRAWN, status)
            event = application.events.get()
            self.assertEqual((event.from_status, event.to_status), (status, Status.WITHDRAWN))
            self.assertIsNone(event.changed_by)
            self.assertEqual(event.note, ACCOUNT_DELETED_NOTE)

    def test_final_applications_keep_their_status_and_get_no_new_event(self):
        self.delete_account()
        for status in ('hired', 'rejected', 'withdrawn'):
            self.assertEqual(self.refresh(status).status, status)
            self.assertEqual(self.applications[status].events.count(), 0)

    def test_personal_text_is_cleared_on_every_application(self):
        self.delete_account()
        for status in self.applications:
            application = self.refresh(status)
            self.assertEqual(application.cover_letter, '', status)
            self.assertEqual(application.portfolio_link, '', status)
            self.assertIsNone(application.proposed_rate, status)

    def test_rows_stay_so_the_clients_records_still_make_sense(self):
        self.delete_account()
        self.assertEqual(Application.objects.filter(freelancer=self.freelancer).count(), 6)

    def test_the_reason_typed_on_withdrawing_is_cleared_but_the_clients_note_is_kept(self):
        application = self.applications['rejected']
        ApplicationStatusEvent.objects.create(
            application=application, from_status='pending', to_status='withdrawn',
            changed_by=self.freelancer, note='Found other work',
        )
        ApplicationStatusEvent.objects.create(
            application=application, from_status='pending', to_status='rejected',
            changed_by=self.client_user, note='Budget too high',
        )
        self.delete_account()
        notes = set(application.events.values_list('note', flat=True))
        self.assertNotIn('Found other work', notes)
        self.assertIn('Budget too high', notes)

    def test_the_client_still_sees_the_applications_as_a_deleted_user_with_no_text(self):
        self.delete_account()
        self.client.force_authenticate(user=self.client_user)
        url = f'/api/gigs/{self.gigs["shortlisted"].id}/applications/'
        row = self.client.get(url).data['results'][0]
        self.assertEqual(row['applicant']['full_name'], 'Deleted User')
        self.assertEqual(row['status'], 'withdrawn')
        self.assertEqual(row['cover_letter'], '')
        self.assertEqual(row['allowed_next_statuses'], [])
        self.assertEqual(row['events'][-1]['changed_by_name'], 'System')

    def test_my_gigs_counts_stay_true_after_the_applicant_leaves(self):
        self.client.force_authenticate(user=self.client_user)
        before = next(g for g in self.client.get('/api/gigs/mine/').data if g['id'] == str(self.gigs['pending'].id))
        self.assertEqual((before['application_count'], before['pending_application_count']), (1, 1))
        self.client.force_authenticate(user=self.freelancer)
        self.delete_account()
        self.client.force_authenticate(user=self.client_user)
        after = next(g for g in self.client.get('/api/gigs/mine/').data if g['id'] == str(self.gigs['pending'].id))
        self.assertEqual((after['application_count'], after['pending_application_count']), (1, 0))

    def test_the_gig_of_a_hired_applicant_is_not_changed(self):
        before = Gig.objects.get(pk=self.gigs['hired'].pk).status
        self.delete_account()
        self.assertEqual(Gig.objects.get(pk=self.gigs['hired'].pk).status, before)

    def test_apply_interactions_are_deleted_with_the_account(self):
        GigInteraction.objects.create(gig=self.gigs['pending'], user=self.freelancer, type='apply')
        self.delete_account()
        self.assertEqual(GigInteraction.objects.filter(user=self.freelancer).count(), 0)

    def test_other_freelancers_applications_are_untouched(self):
        other = self.make_application(freelancer=self.other_freelancer)
        self.delete_account()
        other.refresh_from_db()
        self.assertEqual(other.status, Status.PENDING)
        self.assertEqual(other.cover_letter, LETTER)

    def test_a_wrong_password_changes_nothing(self):
        self.assertEqual(self.delete_account('wrong-password').status_code, 400)
        application = self.refresh('pending')
        self.assertEqual(application.status, Status.PENDING)
        self.assertEqual(application.cover_letter, LETTER)
        self.assertEqual(ApplicationStatusEvent.objects.count(), 0)

    def test_a_deleted_user_is_gone_from_the_account_too(self):
        self.delete_account()
        self.freelancer.refresh_from_db()
        self.assertEqual(self.freelancer.full_name, 'Deleted User')
        self.assertFalse(self.freelancer.is_active)
