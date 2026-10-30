import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from applications.models import Application, ApplicationStatusEvent
from gigs.models import Gig
from profiles.models import FreelancerProfile

from .models import AdminAction
from .recommender_info import latest_evaluation
from .testing import AdminTestMixin

ZERO = '00000000-0000-0000-0000-000000000000'


class AdminApiTestCase(AdminTestMixin, APITestCase):
    def setUp(self):
        self.admin = self.make_admin()
        self.client_user = self.make_user('client@example.com', User.Role.CLIENT, full_name='Wanjiru Bakers')
        self.freelancer = self.make_user('freelancer@example.com', User.Role.FREELANCER, full_name='Otieno Designs')
        self.gig = self.make_gig(self.client_user)
        self.application = self.apply(self.gig, self.freelancer)
        self.profile = self.freelancer.freelancer_profile
        self.profile.verification_status = FreelancerProfile.VerificationStatus.PENDING
        self.profile.save(update_fields=['verification_status'])

    def as_admin(self):
        self.client.force_authenticate(self.admin)


class PermissionMatrixTests(AdminApiTestCase):
    """Every /api/admin/ endpoint: 401 for anonymous users, 403 for anyone but an active admin."""

    def endpoints(self):
        user, gig, app, profile = self.client_user.pk, self.gig.pk, self.application.pk, self.profile.pk
        return [
            ('get', '/api/admin/stats/'),
            ('get', '/api/admin/recommender/'),
            ('get', '/api/admin/users/'),
            ('get', f'/api/admin/users/{user}/'),
            ('post', f'/api/admin/users/{user}/suspend/'),
            ('post', f'/api/admin/users/{user}/reinstate/'),
            ('get', '/api/admin/verifications/'),
            ('get', f'/api/admin/verifications/{profile}/'),
            ('patch', f'/api/admin/verifications/{profile}/'),
            ('get', f'/api/admin/verifications/{profile}/document/'),
            ('get', '/api/admin/gigs/'),
            ('get', f'/api/admin/gigs/{gig}/'),
            ('post', f'/api/admin/gigs/{gig}/remove/'),
            ('post', f'/api/admin/gigs/{gig}/restore/'),
            ('get', '/api/admin/applications/'),
            ('post', f'/api/admin/applications/{app}/remove/'),
            ('post', f'/api/admin/applications/{app}/restore/'),
            ('get', '/api/admin/audit-log/'),
        ]

    def call(self, method, url):
        return getattr(self.client, method)(url, {'reason': 'Matrix test.'}, format='json')

    def test_every_admin_url_is_in_the_matrix(self):
        from . import urls

        self.assertEqual(len(urls.urlpatterns), len({url for _, url in self.endpoints()}))

    def test_anonymous_users_get_401(self):
        for method, url in self.endpoints():
            with self.subTest(url=url, method=method):
                self.assertEqual(self.call(method, url).status_code, 401)

    def test_freelancers_and_clients_get_403(self):
        for user in (self.freelancer, self.client_user):
            self.client.force_authenticate(user)
            for method, url in self.endpoints():
                with self.subTest(user=user.role, url=url, method=method):
                    self.assertEqual(self.call(method, url).status_code, 403)
        self.assertFalse(AdminAction.objects.exists())

    def test_a_suspended_or_inactive_admin_gets_403(self):
        for field, value in (('account_status', User.AccountStatus.SUSPENDED), ('is_active', False)):
            admin = self.make_admin(f'{field}-admin@example.com')
            setattr(admin, field, value)
            admin.save(update_fields=[field])
            self.client.force_authenticate(admin)
            with self.subTest(field=field):
                self.assertEqual(self.client.get('/api/admin/stats/').status_code, 403)

    def test_admins_get_through(self):
        self.as_admin()
        for method, url in self.endpoints():
            with self.subTest(url=url, method=method):
                self.assertNotIn(self.call(method, url).status_code, (401, 403))

    def test_the_old_staff_flag_alone_is_not_enough(self):
        self.client_user.is_staff = True
        self.client_user.is_superuser = True
        self.client_user.save(update_fields=['is_staff', 'is_superuser'])
        self.client.force_authenticate(self.client_user)
        self.assertEqual(self.client.get('/api/admin/users/').status_code, 403)


class UserEndpointTests(AdminApiTestCase):
    def ids(self, **params):
        self.as_admin()
        return {row['email'] for row in self.client.get('/api/admin/users/', params).data['results']}

    def test_lists_users_with_search_and_filters(self):
        self.assertEqual(self.ids(), {'admin@example.com', 'client@example.com', 'freelancer@example.com'})
        self.assertEqual(self.ids(search='wanjiru'), {'client@example.com'})
        self.assertEqual(self.ids(role='freelancer'), {'freelancer@example.com'})
        self.assertEqual(self.ids(verified='false', role='freelancer'), {'freelancer@example.com'})
        self.assertEqual(self.ids(verified='true'), set())
        self.client.post(f'/api/admin/users/{self.client_user.pk}/suspend/', {'reason': 'Spam.'})
        self.assertEqual(self.ids(status='suspended'), {'client@example.com'})
        self.assertNotIn('client@example.com', self.ids(status='active'))

    def test_a_bad_filter_is_a_400(self):
        self.as_admin()
        self.assertEqual(self.client.get('/api/admin/users/', {'role': 'wizard'}).status_code, 400)

    def test_detail_has_profile_gigs_applications_and_history(self):
        self.as_admin()
        self.client.post(f'/api/admin/gigs/{self.gig.pk}/remove/', {'reason': 'Spam gig.'})
        data = self.client.get(f'/api/admin/users/{self.client_user.pk}/').data
        self.assertEqual(data['full_name'], 'Wanjiru Bakers')
        self.assertEqual([gig['title'] for gig in data['gigs']], [self.gig.title])
        self.assertEqual(data['gigs'][0]['moderation_status'], 'removed')
        self.assertEqual(
            [(row['action'], row['target_label'], row['reason']) for row in data['history']],
            [('remove_gig', self.gig.title, 'Spam gig.')],
        )
        freelancer = self.client.get(f'/api/admin/users/{self.freelancer.pk}/').data
        self.assertEqual([row['id'] for row in freelancer['applications']], [str(self.application.pk)])
        self.assertEqual(freelancer['verification_status'], 'pending')

    def test_suspend_and_reinstate(self):
        self.as_admin()
        response = self.client.post(f'/api/admin/users/{self.client_user.pk}/suspend/', {'reason': 'Scam gigs.'})
        self.assertEqual((response.status_code, response.data['status']), (200, 'suspended'))
        response = self.client.post(f'/api/admin/users/{self.client_user.pk}/reinstate/', {})
        self.assertEqual((response.status_code, response.data['status']), (200, 'active'))

    def test_suspend_needs_a_reason(self):
        self.as_admin()
        response = self.client.post(f'/api/admin/users/{self.client_user.pk}/suspend/', {'reason': '  '})
        self.assertEqual(response.status_code, 400)
        self.assertIn('reason', response.data['detail'])
        self.assertFalse(AdminAction.objects.exists())

    def test_admins_cannot_suspend_themselves_or_another_admin(self):
        self.as_admin()
        other = self.make_admin('second-admin@example.com')
        for target in (self.admin, other):
            with self.subTest(target=target.email):
                response = self.client.post(f'/api/admin/users/{target.pk}/suspend/', {'reason': 'Test.'})
                self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(account_status=User.AccountStatus.SUSPENDED).exists())
        self.assertFalse(AdminAction.objects.exists())

    def test_unknown_user_is_404(self):
        self.as_admin()
        self.assertEqual(self.client.post(f'/api/admin/users/{ZERO}/suspend/', {'reason': 'x'}).status_code, 404)


class GigAndApplicationEndpointTests(AdminApiTestCase):
    def test_gig_list_filters(self):
        self.as_admin()
        other = self.make_gig(self.client_user, title='Website for a school', status=Gig.Status.CLOSED)
        self.client.post(f'/api/admin/gigs/{self.gig.pk}/remove/', {'reason': 'Spam.'})

        def titles(**params):
            return {row['title'] for row in self.client.get('/api/admin/gigs/', params).data['results']}

        self.assertEqual(titles(), {self.gig.title, other.title})
        self.assertEqual(titles(search='school'), {other.title})
        self.assertEqual(titles(search='wanjiru'), {self.gig.title, other.title})
        self.assertEqual(titles(status='closed'), {other.title})
        self.assertEqual(titles(moderation='removed'), {self.gig.title})
        self.assertEqual(titles(category=self.gig.category.slug), {self.gig.title, other.title})
        self.assertEqual(titles(category='no-such-category'), set())

    def test_remove_and_restore_a_gig(self):
        self.as_admin()
        url = f'/api/admin/gigs/{self.gig.pk}/'
        self.assertEqual(self.client.post(url + 'remove/', {}).status_code, 400)
        response = self.client.post(url + 'remove/', {'reason': 'Asks for payment up front.'})
        self.assertEqual((response.data['moderation_status'], response.data['removed_reason']),
                         ('removed', 'Asks for payment up front.'))
        self.assertEqual(self.client.post(url + 'remove/', {'reason': 'Again.'}).status_code, 400)
        detail = self.client.get(url).data
        self.assertEqual((detail['description'], detail['application_count']), (self.gig.description, 1))
        self.assertEqual(self.client.post(url + 'restore/', {}).data['moderation_status'], 'visible')

    def test_application_list_filters_and_remove_restore(self):
        self.as_admin()
        other_gig = self.make_gig(self.client_user, title='Second gig')
        other = self.apply(other_gig, self.make_user('second@example.com', User.Role.FREELANCER))

        def ids(**params):
            return {row['id'] for row in self.client.get('/api/admin/applications/', params).data['results']}

        self.assertEqual(ids(), {str(self.application.pk), str(other.pk)})
        self.assertEqual(ids(gig=self.gig.pk), {str(self.application.pk)})
        self.assertEqual(ids(freelancer=other.freelancer_id), {str(other.pk)})
        self.assertEqual(ids(id=other.pk), {str(other.pk)})
        self.assertEqual(self.client.get('/api/admin/applications/', {'gig': 'nope'}).status_code, 400)

        url = f'/api/admin/applications/{self.application.pk}/'
        self.assertEqual(self.client.post(url + 'remove/', {'reason': ''}).status_code, 400)
        self.assertEqual(self.client.post(url + 'remove/', {'reason': 'Abuse.'}).data['moderation_status'], 'removed')
        self.assertEqual(ids(moderation='removed'), {str(self.application.pk)})
        self.assertEqual(self.client.post(url + 'restore/', {}).data['moderation_status'], 'visible')


class EveryActionIsLoggedTests(AdminApiTestCase):
    def test_each_change_writes_one_audit_row_with_its_reason(self):
        self.as_admin()
        steps = [
            (f'/api/admin/users/{self.client_user.pk}/suspend/', 'suspend_user', 'Spam.'),
            (f'/api/admin/users/{self.client_user.pk}/reinstate/', 'reinstate_user', 'Appeal upheld.'),
            (f'/api/admin/gigs/{self.gig.pk}/remove/', 'remove_gig', 'Scam.'),
            (f'/api/admin/gigs/{self.gig.pk}/restore/', 'restore_gig', ''),
            (f'/api/admin/applications/{self.application.pk}/remove/', 'remove_application', 'Abuse.'),
            (f'/api/admin/applications/{self.application.pk}/restore/', 'restore_application', ''),
        ]
        for url, action, reason in steps:
            with self.subTest(action=action):
                before = AdminAction.objects.count()
                self.assertEqual(self.client.post(url, {'reason': reason}).status_code, 200)
                self.assertEqual(AdminAction.objects.count(), before + 1)
                row = AdminAction.objects.order_by('-created_at').first()
                self.assertEqual((row.admin, row.action, row.reason), (self.admin, action, reason))

        log = self.client.get('/api/admin/audit-log/').data
        self.assertEqual(log['count'], len(steps))
        self.assertEqual(log['results'][0]['admin']['full_name'], self.admin.full_name)
        self.assertEqual(
            {row['target_label'] for row in log['results']},
            {'Wanjiru Bakers', self.gig.title, f'Otieno Designs on "{self.gig.title}"'},
        )
        filtered = self.client.get('/api/admin/audit-log/', {'action': 'remove_gig'}).data
        self.assertEqual([row['action'] for row in filtered['results']], ['remove_gig'])
        by_type = self.client.get('/api/admin/audit-log/', {'target_type': 'application'}).data
        self.assertEqual(by_type['count'], 2)
        self.assertEqual(self.client.get('/api/admin/audit-log/', {'admin': ZERO}).data['count'], 0)


class VerificationEndpointTests(AdminApiTestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)

    def submit(self, user):
        self.client.force_authenticate(user)
        document = SimpleUploadedFile('id.pdf', b'%PDF-1.4 fake id', content_type='application/pdf')
        response = self.client.post(
            '/api/profile/submit-verification/', {'id_number': '12345678', 'id_document': document},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200)
        return user.freelancer_profile

    def test_queue_is_oldest_first_and_shows_the_id_number_to_admins(self):
        first = self.submit(self.freelancer)
        second = self.submit(self.make_user('later@example.com', User.Role.FREELANCER))
        two_days_ago = timezone.now() - timedelta(days=2)
        FreelancerProfile.objects.filter(pk=first.pk).update(verification_submitted_at=two_days_ago)
        self.as_admin()
        rows = self.client.get('/api/admin/verifications/').data['results']
        self.assertEqual([row['id'] for row in rows], [str(first.pk), str(second.pk)])
        self.assertEqual((rows[0]['id_number'], rows[0]['has_document']), ('12345678', True))

    def test_document_is_served_to_admins_and_not_cached(self):
        profile = self.submit(self.freelancer)
        self.as_admin()
        response = self.client.get(f'/api/admin/verifications/{profile.pk}/document/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 fake id')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_document_404_when_there_is_none(self):
        self.as_admin()
        other = self.make_user('nodoc@example.com', User.Role.FREELANCER).freelancer_profile
        self.assertEqual(self.client.get(f'/api/admin/verifications/{other.pk}/document/').status_code, 404)

    def test_approve_and_reject_write_the_audit_log(self):
        profile = self.submit(self.freelancer)
        self.as_admin()
        url = f'/api/admin/verifications/{profile.pk}/'
        response = self.client.patch(url, {'verification_status': 'rejected'})
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(url, {'verification_status': 'rejected', 'reason': 'The photo is blurred.'})
        self.assertEqual((response.status_code, response.data['verification_status']), (200, 'rejected'))

        self.submit(self.freelancer)
        self.as_admin()
        self.assertEqual(self.client.patch(url, {'verification_status': 'verified'}).status_code, 200)
        self.assertEqual(
            list(AdminAction.objects.order_by('created_at').values_list('action', 'reason')),
            [('verify_reject', 'The photo is blurred.'), ('verify_approve', '')],
        )
        self.assertEqual(self.client.patch(url, {'verification_status': 'pending'}).status_code, 400)


class StatsTests(AdminApiTestCase):
    """The Overview numbers, against a database whose contents the test knows exactly."""

    def test_numbers_match_the_data(self):
        now = timezone.now()
        old_client = self.make_user('old@example.com', User.Role.CLIENT)
        User.objects.filter(pk=old_client.pk).update(created_at=now - timedelta(days=60))
        closed = self.make_gig(self.client_user, title='Closed gig', status=Gig.Status.CLOSED)
        removed = self.make_gig(self.client_user, title='Removed gig')
        self.as_admin()
        self.client.post(f'/api/admin/gigs/{removed.pk}/remove/', {'reason': 'Spam.'})
        old_gig = self.make_gig(old_client, title='Old gig')
        Gig.objects.filter(pk=old_gig.pk).update(created_at=now - timedelta(days=45))

        second = self.make_user('second@example.com', User.Role.FREELANCER)
        hired = self.apply(closed, second, status=Application.Status.HIRED)
        ApplicationStatusEvent.objects.create(application=hired, to_status='hired', changed_by=self.client_user)
        old_application = self.apply(old_gig, second)
        Application.objects.filter(pk=old_application.pk).update(created_at=now - timedelta(days=40))
        three_days_ago = self.apply(removed, second)
        Application.objects.filter(pk=three_days_ago.pk).update(created_at=now - timedelta(days=3))

        data = self.client.get('/api/admin/stats/').data
        self.assertEqual(data['users']['by_role'], {'client': 2, 'freelancer': 2, 'admin': 1})
        self.assertEqual(data['users']['total'], 5)
        self.assertEqual(data['users']['new_last_30_days'], 4)
        self.assertEqual(data['verifications']['pending'], 1)
        # self.gig and old_gig are open; closed and removed are not.
        self.assertEqual(data['gigs']['open'], 2)
        self.assertEqual(data['gigs']['posted_last_30_days'], 3)
        self.assertEqual(data['gigs']['removed'], 1)
        self.assertEqual(data['applications']['total'], 4)
        self.assertEqual(data['applications']['last_30_days'], 3)
        self.assertEqual((data['hires']['total'], data['hires']['last_30_days']), (1, 1))

        series = data['daily_applications']
        self.assertEqual(len(series), 30)
        self.assertEqual(series[-1]['date'], timezone.localdate().isoformat())
        self.assertEqual(sum(day['count'] for day in series), 3)
        self.assertEqual(series[-1]['count'], 2)
        self.assertEqual(series[-4]['count'], 1)


class RecommenderEndpointTests(AdminApiTestCase):
    def test_shows_the_active_profile_and_settings(self):
        self.as_admin()
        data = self.client.get('/api/admin/recommender/').data
        self.assertIn(data['profile']['name'], ('production', 'demo'))
        self.assertEqual(data['profile']['is_demo'], data['profile']['name'] == 'demo')
        for key in ('blend_max_weight', 'blend_ramp_gigs', 'cold_start_min_gigs', 'svd_components'):
            self.assertIn(key, data['settings'])
        self.assertIsNone(data['model'])

    def test_reads_the_newest_evaluation_report_of_the_current_mode(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.assertIsNone(latest_evaluation(folder))
        header = 'part,relevance,group,method,k,metric,mean,ci_low,ci_high,freelancers\n'
        (folder / 'evaluation-2026-10-25.csv').write_text(
            header + 'validation,applied,all,hybrid,10,recall,0.25,0.2,0.3,40\n'
            'validation,applied,all,hybrid,5,recall,0.9,0.8,1.0,40\n'
            'validation,applied,cold,hybrid,10,recall,0.9,0.8,1.0,40\n',
            encoding='utf-8',
        )
        (folder / 'evaluation-synthetic_planted-2026-10-26.csv').write_text(
            header + 'validation,applied,all,hybrid,10,recall,0.99,0.9,1.0,250\n', encoding='utf-8',
        )
        (folder / 'evaluation-test-runs.csv').write_text('when\n', encoding='utf-8')
        summary = latest_evaluation(folder)
        self.assertEqual((summary['report'], summary['part'], summary['freelancers']),
                         ('evaluation-2026-10-25.csv', 'validation', 40))
        self.assertEqual(
            summary['scores'], [{'method': 'hybrid', 'metric': 'recall', 'mean': 0.25, 'ci_low': 0.2, 'ci_high': 0.3}],
        )
