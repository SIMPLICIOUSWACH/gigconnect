from datetime import timedelta

from django.db.models import Avg
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from applications.models import Application, ApplicationStatusEvent
from applications.transitions import Actor, can_transition
from gigs.models import Gig
from messaging.models import Conversation
from profiles.models import FreelancerProfile
from recommendations.platform import freelancers_for_training
from reviews.models import Review

from . import builders, text
from .models import SampleRecord
from .snapshot import differences, training_snapshot
from .testing import SampleWorld, TempMedia


class HistoryTests(TempMedia, SampleWorld, TestCase):
    freelancer_count = 20
    client_count = 8

    def setUp(self):
        super().setUp()
        self.build_sample_world()
        self.old_gigs = set(Gig.objects.values_list('pk', flat=True))
        self.old_apps = set(Application.objects.values_list('pk', flat=True))
        self.old_joined = dict(User.objects.values_list('pk', 'created_at'))
        self.run_command('enrich_sample_data')
        self.new_gigs = Gig.objects.exclude(pk__in=self.old_gigs)

    def completed(self):
        return self.new_gigs.filter(status='completed')

    def test_everything_new_is_flagged_and_nothing_old_is(self):
        self.assertTrue(self.new_gigs.exists())
        self.assertEqual(self.new_gigs.filter(is_demo_extra=False).count(), 0)
        self.assertEqual(self.new_gigs.filter(is_synthetic=False).count(), 0)
        new_apps = Application.objects.exclude(pk__in=self.old_apps)
        self.assertEqual(new_apps.filter(is_demo_extra=False).count(), 0)
        self.assertEqual(Gig.objects.filter(pk__in=self.old_gigs, is_demo_extra=True).count(), 0)
        self.assertEqual(Application.objects.filter(pk__in=self.old_apps, is_demo_extra=True).count(), 0)

    def test_about_seventy_percent_of_freelancers_have_completed_gigs(self):
        counts = {f.pk: self.completed().filter(applications__freelancer=f, applications__status='hired').count()
                  for f in self.freelancers}
        with_gigs = [n for n in counts.values() if n]
        self.assertEqual(len(with_gigs), 14)  # 70% of 20
        self.assertTrue(all(n >= 1 for n in with_gigs))
        self.assertGreaterEqual(len([n for n in with_gigs if n >= 10]), 3)

    def test_every_completed_gig_has_one_hire_a_chat_and_dates_in_order(self):
        now = timezone.now()
        for gig in self.completed():
            hired = list(gig.applications.filter(status='hired'))
            self.assertEqual(len(hired), 1, gig.title)
            application = hired[0]
            events = list(application.events.order_by('created_at'))
            self.assertEqual([e.to_status for e in events], ['pending', 'under_review', 'shortlisted', 'hired'])
            hire_time = events[-1].created_at
            self.assertLess(gig.created_at, application.created_at)
            self.assertLess(application.created_at, hire_time)
            self.assertLess(hire_time, gig.status_changed_at)
            self.assertLess(gig.status_changed_at, now)
            self.assertGreater(gig.created_at, now - timedelta(days=366))
            self.assertTrue(Conversation.objects.filter(application=application).exists())

    def test_every_status_history_follows_the_rules_and_the_clock(self):
        for application in Application.objects.exclude(pk__in=self.old_apps):
            events = list(application.events.order_by('created_at'))
            self.assertEqual(events[0].to_status, 'pending')
            self.assertEqual(events[-1].to_status, application.status)
            for before, after in zip(events, events[1:]):
                actor = Actor.FREELANCER if after.to_status == 'withdrawn' else Actor.CLIENT
                self.assertTrue(can_transition(before.to_status, after.to_status, actor), (before, after))
                self.assertLess(before.created_at, after.created_at)
            self.assertLessEqual(application.created_at, application.updated_at)

    def test_builders_refuse_a_history_that_breaks_the_rules(self):
        from .context import Context
        ctx = Context(batch='enrich', seed=1)
        gig = self.new_gigs.first()
        other = [f for f in self.freelancers if not gig.applications.filter(freelancer=f).exists()][0]
        with self.assertRaises(builders.HistoryError):
            builders.add_application(
                ctx, gig, other, ctx.now, [('hired', ctx.now + timedelta(days=1))], cover_letter='x' * 60,
            )
        with self.assertRaises(builders.HistoryError):
            builders.add_application(
                ctx, gig, other, ctx.now, [('under_review', ctx.now - timedelta(days=1))], cover_letter='x' * 60,
            )

    def test_budgets_are_in_kes_and_fit_the_category(self):
        for gig in self.new_gigs:
            self.assertEqual(gig.currency, 'KES')
            self.assertLess(gig.budget_min, gig.budget_max)
            self.assertGreaterEqual(gig.budget_min, 500)
            self.assertLessEqual(gig.budget_max, max(high for _, high in text.BUDGET_RANGE.values()) + 500)

    def test_reviews_are_most_completed_gigs_and_mostly_good(self):
        completed = self.completed().count()
        reviews = Review.objects.all()
        self.assertGreater(reviews.count(), 0.55 * completed)
        self.assertLess(reviews.count(), completed + 1)
        good = reviews.filter(rating__gte=4).count()
        self.assertGreater(good, 0.6 * reviews.count())
        for review in reviews:
            self.assertTrue(1 <= review.rating <= 5)
            self.assertEqual(review.client_id, review.gig.client_id)
            self.assertEqual(review.gig.status, 'completed')
            self.assertGreater(review.created_at, review.gig.status_changed_at)
            if review.freelancer_reply:
                self.assertGreater(review.reply_at, review.created_at)
            else:
                self.assertIsNone(review.reply_at)

    def test_no_two_reviews_read_the_same(self):
        texts = list(Review.objects.values_list('text', flat=True))
        self.assertEqual(len(texts), len(set(texts)))
        replies = [r for r in Review.objects.exclude(freelancer_reply='').values_list('freelancer_reply', flat=True)]
        self.assertGreater(len(replies), 0)

    def test_rating_averages_and_counts_are_right(self):
        rated = 0
        for profile in FreelancerProfile.objects.filter(user__in=self.freelancers):
            mine = Review.objects.filter(freelancer=profile.user)
            self.assertEqual(profile.rating_count, mine.count())
            if mine.exists():
                rated += 1
                self.assertEqual(float(profile.rating_avg), round(mine.aggregate(a=Avg('rating'))['a'], 2))
            else:
                self.assertIsNone(profile.rating_avg)
        self.assertGreater(rated, 5)

    def test_every_sample_client_has_a_gig_in_each_status(self):
        for client in self.clients:
            statuses = set(Gig.objects.filter(client=client).values_list('status', flat=True))
            self.assertEqual(statuses, {'open', 'in_progress', 'completed', 'closed'}, client.email)

    def test_open_gigs_are_open_for_applications(self):
        today = timezone.localdate()
        for gig in self.new_gigs.filter(status='open'):
            self.assertGreaterEqual(gig.application_deadline, today + timedelta(days=9))

    def test_accounts_join_before_their_history(self):
        joined_earlier = 0
        for user in User.objects.filter(is_synthetic=True):
            first = min(
                [g.created_at for g in Gig.objects.filter(client=user)]
                + [a.created_at for a in Application.objects.filter(freelancer=user)],
                default=None,
            )
            if first:
                self.assertLessEqual(user.created_at, first, user.email)
            if user.created_at < self.old_joined[user.pk]:
                joined_earlier += 1
        self.assertGreater(joined_earlier, 0)

    def test_running_it_again_creates_nothing(self):
        before = (Gig.objects.count(), Application.objects.count(), Review.objects.count(),
                  Conversation.objects.count(), ApplicationStatusEvent.objects.count(), SampleRecord.objects.count())
        output = self.run_command('enrich_sample_data')
        self.assertEqual(before, (Gig.objects.count(), Application.objects.count(), Review.objects.count(),
                                  Conversation.objects.count(), ApplicationStatusEvent.objects.count(),
                                  SampleRecord.objects.count()))
        self.assertIn('nothing new', output)

    def test_undo_brings_back_exactly_what_was_there(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.run_command('enrich_sample_data', '--undo')
        self.assertEqual(set(Gig.objects.values_list('pk', flat=True)), self.old_gigs)
        self.assertEqual(set(Application.objects.values_list('pk', flat=True)), self.old_apps)
        self.assertEqual(Review.objects.count(), 0)
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(dict(User.objects.values_list('pk', 'created_at')), self.old_joined)
        self.assertEqual(FreelancerProfile.objects.filter(rating_count__gt=0).count(), 0)
        self.assertEqual(SampleRecord.objects.count(), 0)

    def test_the_training_world_is_identical_after_the_whole_enrichment(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.run_command('enrich_sample_data', '--undo')
        before = training_snapshot()
        self.run_command('enrich_sample_data')
        after = training_snapshot()
        self.assertEqual(differences(before, after), {})
        self.assertEqual(before['freelancers_for_training'], after['freelancers_for_training'])
        self.assertEqual(freelancers_for_training().count(), before['freelancers_for_training'])

    def test_a_dry_run_saves_nothing(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.run_command('enrich_sample_data', '--undo')
        counts = (Gig.objects.count(), Application.objects.count(), Review.objects.count())
        output = self.run_command('enrich_sample_data', '--dry-run')
        self.assertIn('Dry run', output)
        self.assertIn('completed gigs', output)
        self.assertEqual(counts, (Gig.objects.count(), Application.objects.count(), Review.objects.count()))
        self.assertEqual(SampleRecord.objects.count(), 0)
