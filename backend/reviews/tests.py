from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from accounts.services import delete_account
from applications.models import Application
from gigs.models import Gig
from notifications.models import Notification

from .models import Review
from .service import refresh_rating
from .testing import ReviewTestMixin


class ReviewApiTestCase(ReviewTestMixin, APITestCase):
    def setUp(self):
        self.gig = self.completed_gig()
        self.client_user = self.gig.client
        self.freelancer = User.objects.get(email='freelancer@example.com')
        self.url = f'/api/gigs/{self.gig.pk}/review/'

    def rate(self, user=None, url=None, **body):
        self.client.force_authenticate(user or self.client_user)
        return self.client.post(url or self.url, {'rating': 5, 'text': 'Great work.', **body}, format='json')

    def profile(self):
        self.freelancer.freelancer_profile.refresh_from_db()
        return self.freelancer.freelancer_profile


class WhoCanRateTests(ReviewApiTestCase):
    def test_the_client_rates_the_freelancer_they_hired(self):
        response = self.rate(rating=4, text='  Solid work, on time.  ')
        self.assertEqual(response.status_code, 201, response.data)
        review = Review.objects.get()
        self.assertEqual((review.client, review.freelancer, review.rating), (self.client_user, self.freelancer, 4))
        self.assertEqual(review.text, 'Solid work, on time.')
        self.assertEqual((response.data['freelancer_name'], response.data['can_edit']), ('Otieno Designs', True))

    def test_the_review_text_is_optional(self):
        self.assertEqual(self.rate(text='').status_code, 201)
        self.assertEqual(Review.objects.get().text, '')

    def test_nobody_else_can_rate_the_gig(self):
        other_client = self.person('other@example.com', User.Role.CLIENT, 'Other Client')
        for user in (other_client, self.freelancer):
            self.assertEqual(self.rate(user=user).status_code, 404)
        self.assertFalse(Review.objects.exists())

    def test_only_a_completed_gig(self):
        for status in ('open', 'in_progress', 'closed'):
            Gig.objects.filter(pk=self.gig.pk).update(status=status)
            response = self.rate()
            self.assertEqual(response.status_code, 400, status)
            self.assertEqual(response.data['detail'], 'You can rate the freelancer once the gig is completed.')
        self.assertFalse(Review.objects.exists())

    def test_a_gig_with_nobody_hired_cannot_be_rated(self):
        Application.objects.filter(gig=self.gig).update(status='rejected')
        self.assertEqual(self.rate().data['detail'], 'Nobody was hired on this gig, so there is nobody to rate.')

    def test_one_review_per_gig(self):
        self.rate()
        response = self.rate(rating=1)
        self.assertEqual(response.status_code, 400)
        self.assertIn('already rated', response.data['detail'])
        self.assertEqual(Review.objects.get().rating, 5)

    def test_the_database_allows_one_review_per_gig(self):
        self.review(self.gig)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(gig=self.gig, client=self.client_user, freelancer=self.freelancer, rating=3)

    def test_stars_are_1_to_5(self):
        for rating in (0, 6, -1, 'five', None, 4.5):
            response = self.rate(rating=rating)
            self.assertEqual(response.status_code, 400, rating)
        self.assertEqual(self.rate(rating=0).data['rating'], ['Choose 1 to 5 stars.'])
        self.assertFalse(Review.objects.exists())

    def test_the_database_refuses_other_ratings(self):
        for rating in (0, 6):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Review.objects.create(gig=self.gig, client=self.client_user, freelancer=self.freelancer, rating=rating)

    def test_a_long_review_is_refused(self):
        self.assertEqual(self.rate(text='x' * 1001).status_code, 400)
        self.assertEqual(self.rate(text='x' * 1000).status_code, 201)

    def test_the_freelancer_is_told(self):
        self.rate(rating=4)
        notice = Notification.objects.get(recipient=self.freelancer, kind='review_received')
        self.assertEqual(notice.title, 'Wanjiru Bakers rated your work on "Logo"')
        self.assertEqual(notice.link, f'/profile/{self.freelancer.pk}')


class WindowTests(ReviewApiTestCase):
    def age_gig(self, days):
        Gig.objects.filter(pk=self.gig.pk).update(status_changed_at=timezone.now() - timezone.timedelta(days=days))

    def test_rating_closes_14_days_after_completion(self):
        self.age_gig(15)
        response = self.rate()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Ratings close 14 days after a gig is completed.')
        self.age_gig(13)
        self.assertEqual(self.rate().status_code, 201)

    def test_editing_is_allowed_for_14_days_and_then_locked(self):
        self.rate(rating=5)
        self.client.force_authenticate(self.client_user)
        response = self.client.patch(self.url, {'rating': 3, 'text': 'On reflection, some delays.'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['rating'], response.data['text']), (3, 'On reflection, some delays.'))
        self.assertEqual(self.profile().rating_avg, Decimal('3.00'))

        self.age_gig(15)
        locked = self.client.patch(self.url, {'rating': 1}, format='json')
        self.assertEqual(locked.status_code, 400)
        self.assertEqual(Review.objects.get().rating, 3)
        self.assertFalse(self.client.get(self.url).data['can_edit'])

    def test_editing_only_the_text_keeps_the_rating(self):
        self.rate(rating=4)
        self.client.force_authenticate(self.client_user)
        self.client.patch(self.url, {'text': 'Added a note.'}, format='json')
        review = Review.objects.get()
        self.assertEqual((review.rating, review.text), (4, 'Added a note.'))

    def test_there_is_nothing_to_edit_before_rating(self):
        self.client.force_authenticate(self.client_user)
        self.assertEqual(self.client.patch(self.url, {'rating': 3}, format='json').status_code, 404)

    def test_my_gigs_says_whether_the_gig_can_still_be_rated(self):
        self.client.force_authenticate(self.client_user)

        def rating():
            return self.client.get('/api/gigs/mine/').data[0]['rating']

        state = rating()
        self.assertEqual((state['can_rate'], state['freelancer_name'], state['review']), (True, 'Otieno Designs', None))
        self.age_gig(15)
        self.assertFalse(rating()['can_rate'])
        self.age_gig(1)
        self.rate(rating=4)
        state = rating()
        self.assertEqual((state['can_rate'], state['can_edit'], state['review']['rating']), (False, True, 4))


class ReplyTests(ReviewApiTestCase):
    def setUp(self):
        super().setUp()
        self.review_row = self.review(self.gig, rating=4)
        self.reply_url = f'/api/reviews/{self.review_row.pk}/reply/'

    def reply(self, user=None, text='Thank you, it was a pleasure.'):
        self.client.force_authenticate(user or self.freelancer)
        return self.client.post(self.reply_url, {'reply': text}, format='json')

    def test_the_freelancer_replies_once(self):
        response = self.reply()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['reply'], 'Thank you, it was a pleasure.')
        again = self.reply(text='One more thing.')
        self.assertEqual((again.status_code, again.data['detail']), (400, 'You have already replied to this review.'))
        self.assertEqual(Review.objects.get().freelancer_reply, 'Thank you, it was a pleasure.')

    def test_only_the_rated_freelancer(self):
        other = self.person('other@example.com', User.Role.FREELANCER, 'Achieng Studio')
        for user in (other, self.client_user):
            self.assertEqual(self.reply(user=user).status_code, 404)

    def test_a_reply_is_1_to_500_characters(self):
        self.assertEqual(self.reply(text='  ').status_code, 400)
        self.assertEqual(self.reply(text='x' * 501).status_code, 400)
        self.assertEqual(self.reply(text='x' * 500).status_code, 200)

    def test_the_client_is_told(self):
        self.reply()
        notice = Notification.objects.get(recipient=self.client_user, kind='review_reply')
        self.assertEqual(notice.title, 'Otieno Designs replied to your review')

    def test_a_removed_review_cannot_be_replied_to(self):
        Review.objects.filter(pk=self.review_row.pk).update(moderation_status='removed')
        self.assertEqual(self.reply().status_code, 400)


class AverageTests(ReviewApiTestCase):
    def test_average_and_count_follow_the_reviews(self):
        self.assertEqual((self.profile().rating_avg, self.profile().rating_count), (None, 0))
        self.rate(rating=5)
        self.assertEqual((self.profile().rating_avg, self.profile().rating_count), (Decimal('5.00'), 1))
        second = self.completed_gig(self.client_user, self.freelancer, title='Menu')
        self.rate(url=f'/api/gigs/{second.pk}/review/', rating=4)
        self.assertEqual((self.profile().rating_avg, self.profile().rating_count), (Decimal('4.50'), 2))

    def test_removed_reviews_do_not_count(self):
        first = self.review(self.gig, rating=1)
        second = self.completed_gig(self.client_user, self.freelancer, title='Menu')
        self.review(second, rating=5)
        self.assertEqual(self.profile().rating_avg, Decimal('3.00'))
        Review.objects.filter(pk=first.pk).update(moderation_status='removed')
        refresh_rating(self.freelancer)
        self.assertEqual((self.profile().rating_avg, self.profile().rating_count), (Decimal('5.00'), 1))

    def test_the_profile_and_the_applicant_card_show_the_average(self):
        self.review(self.gig, rating=4)
        self.client.force_authenticate(self.client_user)
        profile = self.client.get(f'/api/profiles/{self.freelancer.pk}/').data['profile']
        self.assertEqual((profile['rating_avg'], profile['rating_count']), ('4.00', 1))
        applicant = self.client.get(f'/api/gigs/{self.gig.pk}/applications/').data['results'][0]['applicant']
        self.assertEqual((applicant['rating_avg'], applicant['rating_count']), (Decimal('4.00'), 1))


class PublicListTests(ReviewApiTestCase):
    def setUp(self):
        super().setUp()
        self.review_row = self.review(self.gig, rating=4, text='Solid work.')
        self.list_url = f'/api/freelancers/{self.freelancer.pk}/reviews/'

    def test_anyone_signed_in_sees_public_fields_only(self):
        reader = self.person('reader@example.com', User.Role.CLIENT, 'A Reader')
        self.client.force_authenticate(reader)
        row = self.client.get(self.list_url).data['results'][0]
        self.assertEqual(set(row), {
            'id', 'rating', 'text', 'gig_title', 'client_name', 'created_at', 'edited', 'reply', 'reply_at',
            'can_reply',
        })
        self.assertEqual((row['client_name'], row['gig_title'], row['can_reply']), ('Wanjiru Bakers', 'Logo', False))
        self.assertNotIn(self.client_user.email, str(row))
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.list_url).status_code, 401)

    def test_the_rated_freelancer_can_reply_from_the_list(self):
        self.client.force_authenticate(self.freelancer)
        self.assertTrue(self.client.get(self.list_url).data['results'][0]['can_reply'])

    def test_removed_reviews_are_not_listed(self):
        Review.objects.filter(pk=self.review_row.pk).update(moderation_status='removed')
        self.client.force_authenticate(self.client_user)
        self.assertEqual(self.client.get(self.list_url).data['results'], [])


class DeletedAccountTests(ReviewApiTestCase):
    def setUp(self):
        super().setUp()
        self.review_row = self.review(self.gig, rating=4)
        self.list_url = f'/api/freelancers/{self.freelancer.pk}/reviews/'

    def test_a_deleted_freelancers_reviews_are_hidden(self):
        delete_account(self.freelancer)
        self.client.force_authenticate(self.client_user)
        self.assertEqual(self.client.get(self.list_url).status_code, 404)
        self.assertEqual(self.client.get(f'/api/profiles/{self.freelancer.pk}/').status_code, 404)

    def test_a_deleted_clients_review_stays_as_deleted_client(self):
        delete_account(self.client_user)
        reader = self.person('reader@example.com', User.Role.CLIENT, 'A Reader')
        self.client.force_authenticate(reader)
        row = self.client.get(self.list_url).data['results'][0]
        self.assertEqual((row['client_name'], row['rating']), ('Deleted client', 4))
        self.assertEqual(self.profile().rating_count, 1)

    def test_a_deleted_freelancer_cannot_be_rated(self):
        second = self.completed_gig(self.client_user, self.freelancer, title='Menu')
        delete_account(self.freelancer)
        response = self.rate(url=f'/api/gigs/{second.pk}/review/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('deleted', response.data['detail'])
