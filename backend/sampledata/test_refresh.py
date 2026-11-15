from datetime import timedelta

from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from applications.models import Application, ApplicationStatusEvent
from gigs.models import Gig
from messaging.models import Conversation, Message
from notifications.models import Notification
from profiles.models import FreelancerProfile
from recommendations.candidates import candidate_gigs
from reviews.models import Review

from .dates import shift_batch
from .ledger import Ledger
from .snapshot import differences, training_snapshot
from .testing import SampleWorld, TempMedia


def dates_of_everything():
    """Every date the refresh may move, keyed so two readings can be compared."""
    found = {}
    for gig in Gig.objects.all():
        found[('gig', gig.pk)] = (gig.created_at, gig.status_changed_at, gig.deadline, gig.application_deadline)
    for app in Application.objects.all():
        found[('app', app.pk)] = (app.created_at, app.updated_at)
    for event in ApplicationStatusEvent.objects.all():
        found[('event', event.pk)] = (event.created_at,)
    for message in Message.objects.all():
        found[('message', message.pk)] = (message.created_at, message.read_at)
    for review in Review.objects.all():
        found[('review', review.pk)] = (review.created_at, review.reply_at)
    for note in Notification.objects.all():
        found[('note', note.pk)] = (note.created_at, note.read_at)
    for chat in Conversation.objects.all():
        found[('chat', chat.pk)] = (chat.created_at, chat.first_message_at, chat.last_message_at)
    for user in User.objects.all():
        found[('user', user.pk)] = (user.created_at,)
    for profile in FreelancerProfile.objects.exclude(verification_decided_at=None):
        found[('check', profile.pk)] = (profile.verification_submitted_at, profile.verification_decided_at)
    return found


def shifted(values, delta):
    return tuple(None if v is None else v + delta for v in values)


@override_settings(SHOWCASE_PASSWORD='a-demo-password-for-tests-1')
class RefreshTests(TempMedia, SampleWorld, TestCase):
    freelancer_count = 12
    client_count = 8

    def setUp(self):
        super().setUp()
        self.build_sample_world()
        self.run_command('enrich_sample_data')
        self.run_command('seed_showcase')
        self.fa = User.objects.get(email='showcase-freelancer-a@example.test')
        self.fb = User.objects.get(email='showcase-freelancer-b@example.test')

    def age_everything(self, days):
        """Pretend the sample data was made `days` ago: move it back and back-date the anchors."""
        for batch in ('showcase', 'enrich'):
            shift_batch(batch, -days)
            Ledger(batch).set_anchor(timezone.localdate() - timedelta(days=days))

    def test_old_open_gigs_are_open_again_and_recommendations_come_back(self):
        self.age_everything(60)
        self.assertGreater(Gig.objects.filter(is_demo_extra=True, status='open',
                                              application_deadline__lt=timezone.localdate()).count(), 0)
        self.assertEqual([g for g in candidate_gigs(self.fa) if g.is_demo_extra], [])
        output = self.run_command('refresh_showcase_dates')
        self.assertIn('Moved everything forward by 60 day(s)', output)
        today = timezone.localdate()
        self.assertEqual(Gig.objects.filter(status='open', application_deadline__lt=today).count(), 0)
        for freelancer, minimum in ((self.fa, 6), (self.fb, 5)):
            mine = {s.name for s in freelancer.freelancer_profile.skills.all()}
            matching = [g for g in candidate_gigs(freelancer) if mine & {s.name for s in g.skills.all()}]
            self.assertGreaterEqual(len(matching), minimum)

    def test_everything_moves_by_the_same_amount_so_the_order_never_changes(self):
        before = dates_of_everything()
        self.run_command('refresh_showcase_dates', '--days', '9')
        after = dates_of_everything()
        self.assertEqual(set(before), set(after))
        moved = 0
        for key, values in before.items():
            if key[0] == 'user' and not User.objects.filter(pk=key[1], is_synthetic=True).exists():
                self.assertEqual(after[key], values)
                continue
            if shifted(values, timedelta(days=9)) == after[key]:
                moved += 1
            else:
                # The only rows that may stay put are ones neither batch made (the seeded gigs and their applications).
                self.assertIn(key[0], ('gig', 'app', 'user'), key)
        self.assertGreater(moved, 200)
        for gig in Gig.objects.filter(is_demo_extra=True, status='completed'):
            hired = gig.applications.get(status='hired')
            self.assertLess(gig.created_at, hired.created_at)
            self.assertLess(hired.created_at, gig.status_changed_at)

    def test_rows_it_did_not_make_are_untouched(self):
        seeded = {g.pk: (g.created_at, g.deadline, g.application_deadline)
                  for g in Gig.objects.filter(is_demo_extra=False)}
        real_joined = User.objects.get(email='real.person@gmail.com').created_at
        self.run_command('refresh_showcase_dates', '--days', '30')
        for gig in Gig.objects.filter(is_demo_extra=False):
            self.assertEqual((gig.created_at, gig.deadline, gig.application_deadline), seeded[gig.pk])
        self.assertEqual(User.objects.get(email='real.person@gmail.com').created_at, real_joined)

    def test_it_does_nothing_when_the_data_is_already_current(self):
        before = dates_of_everything()
        output = self.run_command('refresh_showcase_dates')
        self.assertIn('already up to date', output)
        self.assertEqual(dates_of_everything(), before)

    def test_the_chats_stay_in_order_and_in_the_past(self):
        self.run_command('refresh_showcase_dates', '--days', '12')
        for chat in Conversation.objects.filter(gig__is_demo_extra=True):
            times = list(chat.messages.order_by('created_at', 'id').values_list('created_at', flat=True))
            if times:
                self.assertEqual(times, sorted(times))
                self.assertGreater(times[0], chat.created_at)
                self.assertEqual(chat.last_message_at, times[-1])

    def test_the_id_check_times_move_with_everything_else(self):
        decided = FreelancerProfile.objects.get(user=self.fa).verification_decided_at
        self.run_command('refresh_showcase_dates', '--days', '20')
        self.assertEqual(FreelancerProfile.objects.get(user=self.fa).verification_decided_at, decided + timedelta(days=20))

    def test_a_dry_run_moves_nothing(self):
        before = dates_of_everything()
        output = self.run_command('refresh_showcase_dates', '--days', '5', '--dry-run')
        self.assertIn('Would move', output)
        self.assertEqual(dates_of_everything(), before)

    def test_the_training_world_is_identical_before_and_after(self):
        before = training_snapshot()
        self.run_command('refresh_showcase_dates', '--days', '17')
        self.assertEqual(differences(before, training_snapshot()), {})

    def test_it_refuses_without_sample_data_or_with_debug_off(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            self.run_command('refresh_showcase_dates')
        from .ledger import undo
        with self.captureOnCommitCallbacks(execute=True):
            undo('showcase')
            undo('enrich')
        with self.assertRaises(CommandError):
            self.run_command('refresh_showcase_dates')
