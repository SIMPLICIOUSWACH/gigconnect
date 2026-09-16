from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from accounts.models import User
from profiles.models import Skill

from .models import NotificationPreference, UserSession


class AccountSettingsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com', password='StrongPass123!',
            full_name='Original Name', phone='254700000000', role='client',
        )
        self.user.is_email_verified = True
        self.user.is_phone_verified = True
        self.user.save()
        self.client.force_authenticate(user=self.user)

    def test_changing_email_resets_verification_and_resends(self):
        from django.core import mail
        response = self.client.patch('/api/settings/account/', {'email': 'new@example.com'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new@example.com')
        self.assertFalse(self.user.is_email_verified)
        self.assertEqual(len(mail.outbox), 1)

    def test_changing_phone_resets_verification_and_sends_otp(self):
        response = self.client.patch('/api/settings/account/', {'phone': '254711111111'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '254711111111')
        self.assertFalse(self.user.is_phone_verified)

    def test_changing_full_name_does_not_affect_verification(self):
        response = self.client.patch('/api/settings/account/', {'full_name': 'New Name'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)
        self.assertTrue(self.user.is_phone_verified)


class ChangePasswordTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com', password='OldPass123!',
            full_name='User', phone='254700000000', role='client',
        )

    def test_change_password_requires_current_password(self):
        login = self.client.post('/api/auth/login/', {'email': 'user@example.com', 'password': 'OldPass123!'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')

        response = self.client.post('/api/settings/change-password/', {
            'current_password': 'WrongPass', 'new_password': 'NewPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_logs_out_all_sessions(self):
        login = self.client.post('/api/auth/login/', {'email': 'user@example.com', 'password': 'OldPass123!'})
        access, refresh = login.data['access'], login.data['refresh']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        response = self.client.post('/api/settings/change-password/', {
            'current_password': 'OldPass123!', 'new_password': 'NewPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        refresh_response = self.client.post('/api/auth/token/refresh/', {'refresh': refresh})
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)


class SessionManagementTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com', password='StrongPass123!',
            full_name='User', phone='254700000000', role='client',
        )

    def _login(self):
        return self.client.post('/api/auth/login/', {'email': 'user@example.com', 'password': 'StrongPass123!'})

    def test_login_creates_a_session(self):
        self._login()
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 1)

    def test_refresh_keeps_one_session_row_with_updated_jti(self):
        login = self._login()
        old_session_id = UserSession.objects.get(user=self.user).id
        refresh_response = self.client.post('/api/auth/token/refresh/', {'refresh': login.data['refresh']})
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 1)
        self.assertEqual(UserSession.objects.get(user=self.user).id, old_session_id)

    def test_list_sessions(self):
        login = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')
        response = self.client.get('/api/settings/sessions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_revoke_session_blacklists_its_refresh_token(self):
        login = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')
        session_id = UserSession.objects.get(user=self.user).id

        response = self.client.delete(f'/api/settings/sessions/{session_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        refresh_response = self.client.post('/api/auth/token/refresh/', {'refresh': login.data['refresh']})
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_all_blacklists_every_session(self):
        login1 = self._login()
        login2 = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {login1.data["access"]}')

        response = self.client.post('/api/settings/sessions/logout-all/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 0)

        for token in (login1.data['refresh'], login2.data['refresh']):
            r = self.client.post('/api/auth/token/refresh/', {'refresh': token})
            self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationPreferenceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com', password='StrongPass123!',
            full_name='User', phone='254700000000', role='client',
        )
        self.client.force_authenticate(user=self.user)

    def test_notification_preference_auto_created(self):
        self.assertTrue(NotificationPreference.objects.filter(user=self.user).exists())

    def test_update_notification_preferences(self):
        response = self.client.patch('/api/settings/notifications/', {'new_application_email': False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['new_application_email'])


class PrivacyAndDataTests(APITestCase):
    def setUp(self):
        self.skill = Skill.objects.create(name='Test Skill', category='Technology')
        self.user = User.objects.create_user(
            email='user@example.com', password='StrongPass123!',
            full_name='User', phone='254700000000', role='freelancer',
        )
        self.user.freelancer_profile.skills.set([self.skill])
        self.client.force_authenticate(user=self.user)

    def test_export_data_excludes_id_number_and_omits_unbuilt_features(self):
        response = self.client.get('/api/settings/export-data/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('id_number', response.data['user']['profile'])
        self.assertNotIn('applications', response.data)
        self.assertNotIn('gigs', response.data)

    def test_delete_account_requires_correct_password(self):
        response = self.client.post('/api/settings/delete-account/', {'password': 'wrong'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_account_soft_deletes_and_blocks_login(self):
        response = self.client.post('/api/settings/delete-account/', {'password': 'StrongPass123!'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        deleted_user = User.objects.get(id=self.user.id)
        self.assertFalse(deleted_user.is_active)
        self.assertIsNotNone(deleted_user.deleted_at)

        login_response = self.client.post('/api/auth/login/', {
            'email': deleted_user.email, 'password': 'StrongPass123!',
        })
        self.assertEqual(login_response.status_code, status.HTTP_401_UNAUTHORIZED)


class RoleScopedSettingsTests(APITestCase):
    def setUp(self):
        self.skill = Skill.objects.create(name='Test Skill', category='Technology')
        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!',
            full_name='Client', phone='254700000001', role='client',
        )
        self.freelancer = User.objects.create_user(
            email='freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000002', role='freelancer',
        )
        self.freelancer.freelancer_profile.skills.set([self.skill])

    def test_client_editing_profile_complete_does_not_touch_freelancer_only_fields(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.patch('/api/profile/complete/', {'company_name': 'Acme'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('bio', response.data)
        self.assertNotIn('skills', response.data)

    def test_client_cannot_submit_verification(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post('/api/profile/submit-verification/', {'id_number': '123'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
