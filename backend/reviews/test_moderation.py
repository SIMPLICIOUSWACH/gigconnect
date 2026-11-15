from decimal import Decimal

from rest_framework.test import APITestCase

from accounts.models import User
from adminpanel.models import AdminAction
from notifications.models import Notification

from .models import Review
from .testing import ReviewTestMixin


class ReviewModerationTests(ReviewTestMixin, APITestCase):
    def setUp(self):
        self.admin = self.make_admin()
        self.gig = self.completed_gig()
        self.freelancer = User.objects.get(email='freelancer@example.com')
        self.low = self.review(self.gig, rating=1, text='Rude words here.')
        self.high = self.review(self.completed_gig(self.gig.client, self.freelancer, title='Menu'), rating=5)
        self.url = f'/api/admin/reviews/{self.low.pk}/'
        self.client.force_authenticate(self.admin)

    def profile(self):
        self.freelancer.freelancer_profile.refresh_from_db()
        return self.freelancer.freelancer_profile

    def test_only_admins(self):
        self.client.force_authenticate(self.gig.client)
        self.assertEqual(self.client.get('/api/admin/reviews/').status_code, 403)
        self.assertEqual(self.client.post(self.url + 'remove/', {'reason': 'x'}).status_code, 403)
        self.assertFalse(Review.objects.get(pk=self.low.pk).is_removed)

    def test_the_list_shows_every_review_and_filters(self):
        rows = self.client.get('/api/admin/reviews/').data['results']
        self.assertEqual({row['rating'] for row in rows}, {1, 5})
        self.assertEqual(rows[0]['client']['full_name'], 'Wanjiru Bakers')
        one = self.client.get('/api/admin/reviews/', {'rating': 1}).data['results']
        self.assertEqual([row['id'] for row in one], [str(self.low.pk)])
        self.assertEqual(self.client.get('/api/admin/reviews/', {'moderation': 'removed'}).data['results'], [])

    def test_removing_needs_a_reason(self):
        response = self.client.post(self.url + 'remove/', {'reason': ' '})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Review.objects.get(pk=self.low.pk).is_removed)

    def test_removing_hides_it_takes_it_out_of_the_average_logs_it_and_tells_both(self):
        self.assertEqual((self.profile().rating_avg, self.profile().rating_count), (Decimal('3.00'), 2))
        response = self.client.post(self.url + 'remove/', {'reason': 'Abusive language.'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['moderation_status'], response.data['removed_reason']),
                         ('removed', 'Abusive language.'))
        self.assertEqual((self.profile().rating_avg, self.profile().rating_count), (Decimal('5.00'), 1))

        action = AdminAction.objects.get(action='remove_review')
        self.assertEqual((action.admin, action.target_id), (self.admin, self.low.pk))
        self.assertEqual(action.reason, 'Abusive language.')
        notices = Notification.objects.filter(kind='review_removed')
        self.assertEqual({n.recipient for n in notices}, {self.freelancer, self.gig.client})
        self.assertIn('Reason: Abusive language.', notices[0].body)

        self.client.force_authenticate(self.gig.client)
        listed = self.client.get(f'/api/freelancers/{self.freelancer.pk}/reviews/').data['results']
        self.assertEqual([row['rating'] for row in listed], [5])

    def test_restoring_puts_it_back(self):
        self.client.post(self.url + 'remove/', {'reason': 'Abusive language.'})
        response = self.client.post(self.url + 'restore/', {})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['moderation_status'], 'visible')
        self.assertEqual((self.profile().rating_avg, self.profile().rating_count), (Decimal('3.00'), 2))
        self.assertTrue(AdminAction.objects.filter(action='restore_review', target_id=self.low.pk).exists())
        self.assertEqual(Notification.objects.filter(kind='review_restored').count(), 2)

    def test_removing_twice_or_restoring_a_visible_one_is_refused(self):
        self.client.post(self.url + 'remove/', {'reason': 'x'})
        self.assertEqual(self.client.post(self.url + 'remove/', {'reason': 'x'}).status_code, 400)
        self.assertEqual(self.client.post(f'/api/admin/reviews/{self.high.pk}/restore/', {}).status_code, 400)

    def test_the_audit_log_names_the_review(self):
        self.client.post(self.url + 'remove/', {'reason': 'x'})
        row = self.client.get('/api/admin/audit-log/').data['results'][0]
        self.assertEqual(row['action_label'], 'Removed review')
        self.assertEqual(row['target_label'], 'Review of Otieno Designs by Wanjiru Bakers on "Logo"')
