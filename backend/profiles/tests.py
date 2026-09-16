from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import PortfolioItem, Skill


class ProfileCompleteTests(APITestCase):
    def setUp(self):
        self.skill = Skill.objects.create(name='Test Skill', category='Technology')

    def make_freelancer(self):
        user = User.objects.create_user(
            email='freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000001', role='freelancer',
        )
        user.freelancer_profile.skills.set([self.skill])
        return user

    def make_client(self):
        return User.objects.create_user(
            email='client@example.com', password='StrongPass123!',
            full_name='Client', phone='254700000002', role='client',
        )

    def test_freelancer_profile_complete_requires_bio(self):
        user = self.make_freelancer()
        self.client.force_authenticate(user=user)
        response = self.client.patch('/api/profile/complete/', {'profile_photo': ''}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertFalse(user.is_profile_complete)

    def test_freelancer_profile_complete_with_bio(self):
        user = self.make_freelancer()
        self.client.force_authenticate(user=user)
        response = self.client.patch('/api/profile/complete/', {'bio': 'Experienced developer.'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_profile_complete)

    def test_client_profile_complete_without_required_fields(self):
        user = self.make_client()
        self.client.force_authenticate(user=user)
        response = self.client.patch('/api/profile/complete/', {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.is_profile_complete)


class PortfolioItemTests(APITestCase):
    def setUp(self):
        self.skill = Skill.objects.create(name='Test Skill', category='Technology')
        self.freelancer = User.objects.create_user(
            email='freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000001', role='freelancer',
        )
        self.freelancer.freelancer_profile.skills.set([self.skill])
        self.client_user = User.objects.create_user(
            email='client@example.com', password='StrongPass123!',
            full_name='Client', phone='254700000002', role='client',
        )

    def test_freelancer_can_create_portfolio_item(self):
        self.client.force_authenticate(user=self.freelancer)
        response = self.client.post('/api/profile/portfolio-items/', {'title': 'My Project'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PortfolioItem.objects.count(), 1)

    def test_freelancer_can_delete_own_portfolio_item(self):
        self.client.force_authenticate(user=self.freelancer)
        item = PortfolioItem.objects.create(freelancer=self.freelancer.freelancer_profile, title='My Project')
        response = self.client.delete(f'/api/profile/portfolio-items/{item.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(PortfolioItem.objects.count(), 0)

    def test_client_cannot_access_portfolio_endpoints(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.post('/api/profile/portfolio-items/', {'title': 'Not allowed'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
