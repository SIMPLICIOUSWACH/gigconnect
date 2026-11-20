import os

from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from accounts.models import User
from applications.models import Application
from applications.transitions import Actor, can_transition
from gigs.models import Gig, GigInvite
from messaging.models import Conversation, Message
from notifications.models import Notification
from profiles.models import FreelancerProfile, PortfolioItem
from recommendations.candidates import candidate_gigs
from recommendations.platform import freelancers_for_training
from reviews.models import Review

from .images import SAMPLE_MARKER
from .ledger import Ledger, undo
from .models import SampleRecord
from .showcase import SHOWCASE_EMAILS
from .snapshot import differences, training_snapshot
from .testing import SampleWorld, TempMedia

PASSWORD = 'a-demo-password-for-tests-1'


@override_settings(SHOWCASE_PASSWORD=PASSWORD)
class ShowcaseTests(TempMedia, SampleWorld, TestCase):
    freelancer_count = 12
    client_count = 8

    def setUp(self):
        super().setUp()
        self.build_sample_world()
        self.joined_before = dict(User.objects.values_list('pk', 'created_at'))
        self.output = self.run_command('seed_showcase')
        self.fa = User.objects.get(email='showcase-freelancer-a@example.test')
        self.fb = User.objects.get(email='showcase-freelancer-b@example.test')
        self.ca = User.objects.get(email='showcase-client-a@example.test')
        self.cb = User.objects.get(email='showcase-client-b@example.test')

    def gigs_of(self, client, status):
        return Gig.objects.filter(client=client, status=status)

    # -- the accounts ---------------------------------------------------------------------------------------------------

    def test_four_flagged_accounts_with_example_test_emails_and_the_configured_password(self):
        accounts = User.objects.filter(email__in=SHOWCASE_EMAILS)
        self.assertEqual(accounts.count(), 4)
        for user in accounts:
            self.assertTrue(user.email.endswith('@example.test'))
            self.assertTrue(user.is_synthetic and user.is_demo_extra and user.is_email_verified)
            self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(sorted(u.role for u in accounts), ['client', 'client', 'freelancer', 'freelancer'])
        self.assertNotIn(PASSWORD, self.output)
        for email in SHOWCASE_EMAILS:
            self.assertIn(email, self.output)

    def test_everything_made_is_flagged_and_the_sample_world_is_not(self):
        made = Gig.objects.filter(is_demo_extra=True)
        self.assertGreater(made.count(), 30)
        self.assertEqual(made.filter(is_synthetic=False).count(), 0)
        self.assertEqual(Application.objects.filter(is_demo_extra=False, gig__is_demo_extra=True).count(), 0)
        self.assertEqual(Application.objects.filter(is_demo_extra=True, gig__is_demo_extra=False).count(), 0)
        self.assertEqual(Gig.objects.filter(is_demo_extra=False).count(), 8)  # only the seeded ones

    def test_nothing_runs_without_a_password_or_with_debug_off(self):
        with override_settings(SHOWCASE_PASSWORD=''), self.assertRaises(CommandError):
            self.run_command('seed_showcase', '--reset')
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            self.run_command('seed_showcase', '--reset')
        self.assertEqual(User.objects.filter(email__in=SHOWCASE_EMAILS).count(), 4)

    # -- freelancer A ---------------------------------------------------------------------------------------------------

    def test_freelancer_a_is_complete(self):
        profile = self.fa.freelancer_profile
        self.assertEqual((profile.county, profile.is_available, profile.open_to_remote), ('Nairobi', True, True))
        self.assertTrue(profile.headline and profile.bio and profile.starting_price)
        self.assertLessEqual(len(profile.bio), 300)
        self.assertGreaterEqual(profile.skills.count(), 4)
        self.assertTrue(profile.profile_photo and os.path.exists(profile.profile_photo.path))
        items = PortfolioItem.objects.filter(freelancer=profile)
        self.assertEqual(items.count(), 4)
        for item in items:
            self.assertTrue(item.title and item.description and os.path.exists(item.image.path))

    def test_freelancer_a_has_eight_completed_gigs_and_seven_reviews(self):
        done = Application.objects.filter(freelancer=self.fa, status='hired', gig__status='completed')
        self.assertEqual(done.count(), 8)
        reviews = Review.objects.filter(freelancer=self.fa)
        self.assertEqual(reviews.count(), 7)
        average = sum(r.rating for r in reviews) / 7
        self.assertAlmostEqual(average, 4.7, delta=0.05)
        self.assertEqual(reviews.exclude(freelancer_reply='').count(), 3)
        profile = FreelancerProfile.objects.get(user=self.fa)
        self.assertEqual((profile.rating_count, float(profile.rating_avg)), (7, round(average, 2)))

    def test_freelancer_a_has_a_gig_in_progress_with_a_realistic_chat(self):
        hired = Application.objects.filter(freelancer=self.fa, status='hired', gig__status='in_progress')
        self.assertEqual(hired.count(), 1)
        chat = Conversation.objects.get(application=hired.get())
        self.assertEqual(chat.client, self.ca)
        messages = list(chat.messages.order_by('created_at', 'id'))
        self.assertTrue(6 <= len(messages) <= 10)
        self.assertEqual(messages[0].sender, self.ca)
        self.assertGreater(len({m.body for m in messages}), len(messages) - 1)
        self.assertEqual(chat.first_message_at, messages[0].created_at)
        self.assertEqual(chat.last_message_at, messages[-1].created_at)
        self.assertEqual([m.read_at is None for m in messages].count(True), 1)
        self.assertLess(messages[-1].created_at, timezone.now())

    def test_each_freelancer_has_an_application_in_every_other_status(self):
        for freelancer in (self.fa, self.fb):
            statuses = set(Application.objects.filter(freelancer=freelancer).values_list('status', flat=True))
            self.assertTrue({'pending', 'under_review', 'shortlisted', 'rejected', 'withdrawn', 'hired'} <= statuses)

    def test_unread_notifications_for_both_freelancers(self):
        for freelancer in (self.fa, self.fb):
            unread = Notification.objects.filter(recipient=freelancer, read_at__isnull=True)
            self.assertGreaterEqual(unread.count(), 3)
            self.assertLess(unread.count(), Notification.objects.filter(recipient=freelancer).count())
        self.assertTrue(Notification.objects.filter(recipient=self.fa, kind='gig_invite').exists())

    # -- freelancer B ---------------------------------------------------------------------------------------------------

    def test_freelancer_b_has_five_completed_gigs_and_an_average_of_four_and_a_half(self):
        self.assertEqual(Application.objects.filter(freelancer=self.fb, status='hired', gig__status='completed').count(), 5)
        reviews = Review.objects.filter(freelancer=self.fb)
        self.assertEqual(reviews.count(), 4)
        self.assertAlmostEqual(sum(r.rating for r in reviews) / 4, 4.5)
        three = reviews.get(rating=3)
        self.assertIn('apolog', three.freelancer_reply.lower())
        self.assertEqual(self.fb.freelancer_profile.county, 'Mombasa')

    def test_freelancer_b_has_a_gig_in_progress_with_a_chat(self):
        hired = Application.objects.get(freelancer=self.fb, status='hired', gig__status='in_progress')
        chat = Conversation.objects.get(application=hired)
        self.assertEqual(chat.client, self.cb)
        self.assertTrue(6 <= chat.messages.count() <= 10)
        self.assertEqual(chat.messages.order_by('created_at', 'id').first().sender, self.cb)

    # -- the clients ----------------------------------------------------------------------------------------------------

    def test_client_a_has_gigs_in_every_status_and_invited_one_freelancer(self):
        counts = {s: self.gigs_of(self.ca, s).count() for s in ('open', 'in_progress', 'completed', 'closed')}
        self.assertEqual(counts, {'open': 2, 'in_progress': 1, 'completed': 3, 'closed': 1})
        for gig in self.gigs_of(self.ca, 'completed'):
            self.assertTrue(Review.objects.filter(gig=gig, client=self.ca).exists())
        invites = GigInvite.objects.filter(client=self.ca)
        self.assertEqual(invites.count(), 1)
        self.assertEqual(invites.get().freelancer, self.fa)
        self.assertEqual(invites.get().gig.client, self.ca)
        self.assertFalse(Application.objects.filter(gig=invites.get().gig, freelancer=self.fa).exists())
        stages = set()
        for gig in self.gigs_of(self.ca, 'open'):
            stages |= set(gig.applications.values_list('status', flat=True))
        self.assertGreaterEqual(len(stages), 3)
        self.assertTrue(self.ca.client_profile.company_logo and self.ca.client_profile.company_name)

    def test_client_b_has_an_open_gig_with_a_shortlisted_applicant_and_hired_freelancer_b(self):
        self.assertEqual(self.gigs_of(self.cb, 'open').count(), 1)
        open_gig = self.gigs_of(self.cb, 'open').get()
        self.assertGreaterEqual(open_gig.applications.count(), 3)
        self.assertTrue(open_gig.applications.filter(status='shortlisted').exists())
        self.assertEqual(self.gigs_of(self.cb, 'completed').count(), 2)
        for gig in self.gigs_of(self.cb, 'completed'):
            self.assertTrue(Review.objects.filter(gig=gig).exists())
        progress = self.gigs_of(self.cb, 'in_progress').get()
        self.assertEqual(progress.applications.get(status='hired').freelancer, self.fb)
        self.assertGreaterEqual(self.gigs_of(self.cb, 'closed').count(), 1)

    # -- recommendations ------------------------------------------------------------------------------------------------

    def test_both_freelancers_have_open_gigs_to_be_recommended(self):
        today = timezone.localdate()
        for freelancer, minimum in ((self.fa, 6), (self.fb, 5)):
            mine = {s.name for s in freelancer.freelancer_profile.skills.all()}
            candidates = list(candidate_gigs(freelancer))
            matching = [g for g in candidates if mine & {s.name for s in g.skills.all()}]
            self.assertGreaterEqual(len(matching), minimum, freelancer.email)
            for gig in candidates:
                self.assertGreaterEqual(gig.application_deadline, today)

    # -- documents ------------------------------------------------------------------------------------------------------

    def test_the_id_check_is_approved_with_clearly_marked_placeholders(self):
        for freelancer in (self.fa, self.fb):
            profile = FreelancerProfile.objects.get(user=freelancer)
            self.assertEqual(profile.verification_status, 'verified')
            self.assertTrue(profile.id_number.startswith('SAMPLE'))
            self.assertIsNone(profile.face_match_score)
            for stored in (profile.id_document, profile.selfie):
                self.assertTrue(os.path.exists(stored.path))
                with Image.open(stored.path) as picture:
                    self.assertEqual(picture.text.get('Comment'), SAMPLE_MARKER)
            with self.assertRaises(ValueError):
                profile.id_document.url  # private storage: no URL can reach it

    # -- dates ----------------------------------------------------------------------------------------------------------

    def test_every_status_history_and_every_date_is_in_order(self):
        now = timezone.now()
        for application in Application.objects.filter(is_demo_extra=True, gig__client__in=[self.ca, self.cb]):
            events = list(application.events.order_by('created_at'))
            for before, after in zip(events, events[1:]):
                actor = Actor.FREELANCER if after.to_status == 'withdrawn' else Actor.CLIENT
                self.assertTrue(can_transition(before.to_status, after.to_status, actor))
                self.assertLess(before.created_at, after.created_at)
            self.assertLess(events[-1].created_at, now)
            self.assertLess(application.gig.created_at, application.created_at)
        for gig in Gig.objects.filter(client__in=[self.ca, self.cb], status='completed'):
            hired = gig.applications.get(status='hired')
            self.assertLess(hired.events.order_by('created_at').last().created_at, gig.status_changed_at)
            review = Review.objects.filter(gig=gig).first()
            if review:
                self.assertGreater(review.created_at, gig.status_changed_at)
                if review.freelancer_reply:
                    self.assertGreater(review.reply_at, review.created_at)
        for message in Message.objects.all():
            self.assertLess(message.created_at, now)
            self.assertGreater(message.created_at, message.conversation.created_at)
        self.assertEqual(Gig.objects.filter(status='open', application_deadline__lt=timezone.localdate()).count(), 0)

    # -- running it again, resetting, undoing --------------------------------------------------------------------------

    def counts(self):
        return (User.objects.count(), Gig.objects.count(), Application.objects.count(), Review.objects.count(),
                Conversation.objects.count(), Message.objects.count(), Notification.objects.count(),
                PortfolioItem.objects.count(), GigInvite.objects.count(), SampleRecord.objects.count())

    def test_running_it_again_creates_nothing(self):
        before = self.counts()
        output = self.run_command('seed_showcase')
        self.assertIn('already exist', output)
        self.assertEqual(self.counts(), before)

    def test_reset_rebuilds_only_the_showcase_accounts(self):
        sample = set(User.objects.filter(is_synthetic=True, is_demo_extra=False).values_list('pk', flat=True))
        seeded = set(Gig.objects.filter(is_demo_extra=False).values_list('pk', flat=True))
        before = self.counts()
        with self.captureOnCommitCallbacks(execute=True):
            self.run_command('seed_showcase', '--reset')
        self.assertEqual(self.counts(), before)
        self.assertEqual(User.objects.filter(email__in=SHOWCASE_EMAILS).count(), 4)
        self.assertEqual(set(User.objects.filter(is_synthetic=True, is_demo_extra=False).values_list('pk', flat=True)), sample)
        self.assertEqual(set(Gig.objects.filter(is_demo_extra=False).values_list('pk', flat=True)), seeded)

    def test_undo_removes_only_what_it_created(self):
        with self.captureOnCommitCallbacks(execute=True):
            undo('showcase')
        self.assertEqual(User.objects.filter(email__in=SHOWCASE_EMAILS).count(), 0)
        self.assertEqual(Gig.objects.count(), 8)
        self.assertEqual(Application.objects.filter(is_demo_extra=True).count(), 0)
        self.assertEqual(Review.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(FreelancerProfile.objects.filter(rating_count__gt=0).count(), 0)
        self.assertEqual(dict(User.objects.values_list('pk', 'created_at')), self.joined_before)
        self.assertFalse(Ledger('showcase').exists())

    def test_an_account_it_did_not_make_is_left_alone(self):
        with self.captureOnCommitCallbacks(execute=True):
            undo('showcase')
        self.make_user('showcase-client-a@example.test', User.Role.CLIENT, full_name='Someone Else')
        with self.assertRaises(CommandError):
            self.run_command('seed_showcase')

    # -- the recommender ------------------------------------------------------------------------------------------------

    def test_the_training_world_is_identical_before_and_after(self):
        with self.captureOnCommitCallbacks(execute=True):
            undo('showcase')
        before = training_snapshot()
        self.run_command('seed_showcase')
        after = training_snapshot()
        self.assertEqual(differences(before, after), {})
        self.assertEqual(before['freelancers_for_training'], after['freelancers_for_training'])
        self.assertNotIn(self.fa.pk, set(freelancers_for_training().values_list('user_id', flat=True)))

    def test_a_dry_run_saves_nothing(self):
        with self.captureOnCommitCallbacks(execute=True):
            undo('showcase')
        before = self.counts()
        output = self.run_command('seed_showcase', '--dry-run')
        self.assertIn('Dry run', output)
        self.assertEqual(self.counts(), before)

    def test_it_refuses_the_planted_demo_database(self):
        with self.captureOnCommitCallbacks(execute=True):
            undo('showcase')
        self.make_user('planted-freelancer-1@example.test', User.Role.FREELANCER, is_synthetic=True)
        with self.assertRaises(CommandError):
            self.run_command('seed_showcase')
