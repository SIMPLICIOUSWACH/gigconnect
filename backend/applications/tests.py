from datetime import date, timedelta
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from gigs.models import Category, Gig

from .models import Application, ApplicationStatusEvent
from .transitions import (
    FINAL_STATUSES,
    Actor,
    InvalidTransition,
    Status,
    allowed_next_statuses,
    can_transition,
)

LETTER = 'I have five years of experience building exactly this kind of thing for small businesses.'

# The rules as the sprint spec states them, written out independently of transitions.py so a
# mistake in the table can't also hide in the test.
CLIENT_ALLOWED = {
    ('pending', 'under_review'),
    ('under_review', 'shortlisted'),
    ('shortlisted', 'hired'),
    ('pending', 'rejected'),
    ('under_review', 'rejected'),
    ('shortlisted', 'rejected'),
}
FREELANCER_ALLOWED = {
    ('pending', 'withdrawn'),
    ('under_review', 'withdrawn'),
}
ALL_STATUSES = ['pending', 'under_review', 'shortlisted', 'hired', 'rejected', 'withdrawn']


class ApplicationTestBase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Application Test Category')
        self.client_user = User.objects.create_user(
            email='app-client@example.com', password='StrongPass123!',
            full_name='Client', phone='254700000101', role='client',
        )
        self.freelancer = User.objects.create_user(
            email='app-freelancer@example.com', password='StrongPass123!',
            full_name='Freelancer', phone='254700000102', role='freelancer',
        )
        self.other_freelancer = User.objects.create_user(
            email='app-freelancer-2@example.com', password='StrongPass123!',
            full_name='Other Freelancer', phone='254700000103', role='freelancer',
        )
        self.gig = self.make_gig('Logo for a cafe')

    def make_gig(self, title):
        return Gig.objects.create(
            client=self.client_user, category=self.category, title=title, description='A gig.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30),
        )

    def make_application(self, gig=None, freelancer=None, **overrides):
        fields = {'gig': gig or self.gig, 'freelancer': freelancer or self.freelancer, 'cover_letter': LETTER}
        fields.update(overrides)
        return Application.objects.create(**fields)


class ApplicationModelTests(ApplicationTestBase):
    def test_new_application_defaults(self):
        application = self.make_application()
        self.assertEqual(application.status, Status.PENDING)
        self.assertFalse(application.is_synthetic)
        self.assertEqual(application.portfolio_link, '')
        self.assertIsNone(application.proposed_rate)
        self.assertIsNotNone(application.created_at)
        self.assertEqual(len(str(application.id)), 36)  # a UUID

    def test_the_six_statuses(self):
        self.assertEqual([value for value, _ in Application.Status.choices], ALL_STATUSES)

    def build_application(self, **overrides):
        fields = {'gig': self.gig, 'freelancer': self.freelancer, 'cover_letter': LETTER}
        fields.update(overrides)
        return Application(**fields)  # not saved, for checking validation

    def test_cover_letter_must_be_at_least_50_characters(self):
        with self.assertRaises(ValidationError) as caught:
            self.build_application(cover_letter='x' * 49).full_clean()
        self.assertIn('cover_letter', caught.exception.message_dict)
        self.build_application(cover_letter='x' * 50).full_clean()

    def test_cover_letter_must_be_at_most_3000_characters(self):
        self.build_application(cover_letter='x' * 3000).full_clean()
        with self.assertRaises(ValidationError) as caught:
            self.build_application(cover_letter='x' * 3001).full_clean()
        self.assertIn('cover_letter', caught.exception.message_dict)

    def test_cover_letter_is_required(self):
        application = Application(gig=self.gig, freelancer=self.freelancer, cover_letter='')
        with self.assertRaises(ValidationError) as caught:
            application.full_clean()
        self.assertIn('cover_letter', caught.exception.message_dict)

    def test_proposed_rate_must_be_positive(self):
        for bad in (Decimal('0'), Decimal('-5')):
            application = Application(gig=self.gig, freelancer=self.freelancer, cover_letter=LETTER, proposed_rate=bad)
            with self.assertRaises(ValidationError, msg=str(bad)) as caught:
                application.full_clean()
            self.assertIn('proposed_rate', caught.exception.message_dict)
        Application(
            gig=self.gig, freelancer=self.freelancer, cover_letter=LETTER, proposed_rate=Decimal('0.01')
        ).full_clean()

    def test_proposed_rate_and_portfolio_link_are_optional(self):
        Application(gig=self.gig, freelancer=self.freelancer, cover_letter=LETTER).full_clean()

    def test_portfolio_link_must_be_a_url(self):
        application = Application(
            gig=self.gig, freelancer=self.freelancer, cover_letter=LETTER, portfolio_link='not a url'
        )
        with self.assertRaises(ValidationError) as caught:
            application.full_clean()
        self.assertIn('portfolio_link', caught.exception.message_dict)
        application.portfolio_link = 'https://example.com/me'
        application.full_clean()

    def test_one_application_per_freelancer_per_gig(self):
        self.make_application()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_application()

    def test_the_same_freelancer_can_apply_to_different_gigs(self):
        self.make_application()
        self.make_application(gig=self.make_gig('Another gig'))
        self.assertEqual(Application.objects.filter(freelancer=self.freelancer).count(), 2)

    def test_different_freelancers_can_apply_to_the_same_gig(self):
        self.make_application()
        self.make_application(freelancer=self.other_freelancer)
        self.assertEqual(self.gig.applications.count(), 2)

    def test_a_gig_can_have_only_one_hired_application(self):
        self.make_application(status=Status.HIRED)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_application(freelancer=self.other_freelancer, status=Status.HIRED)

    def test_hired_on_one_gig_does_not_block_a_hire_on_another(self):
        self.make_application(status=Status.HIRED)
        self.make_application(gig=self.make_gig('Another gig'), status=Status.HIRED)

    def test_other_applicants_can_coexist_with_the_hire(self):
        self.make_application(status=Status.HIRED)
        self.make_application(freelancer=self.other_freelancer, status=Status.PENDING)
        self.assertEqual(self.gig.applications.count(), 2)

    def test_deleting_a_gig_deletes_its_applications(self):
        self.make_application()
        self.gig.delete()
        self.assertEqual(Application.objects.count(), 0)

    def test_both_models_are_registered_in_the_admin(self):
        self.assertTrue(admin.site.is_registered(Application))
        self.assertTrue(admin.site.is_registered(ApplicationStatusEvent))


class TransitionRuleTests(TestCase):
    def test_every_client_transition_matches_the_spec(self):
        for current in ALL_STATUSES:
            for new in ALL_STATUSES:
                with self.subTest(actor='client', current=current, new=new):
                    self.assertEqual(can_transition(current, new, Actor.CLIENT), (current, new) in CLIENT_ALLOWED)

    def test_every_freelancer_transition_matches_the_spec(self):
        for current in ALL_STATUSES:
            for new in ALL_STATUSES:
                with self.subTest(actor='freelancer', current=current, new=new):
                    self.assertEqual(
                        can_transition(current, new, Actor.FREELANCER), (current, new) in FREELANCER_ALLOWED
                    )

    def test_hired_rejected_and_withdrawn_are_final_for_everyone(self):
        self.assertEqual(FINAL_STATUSES, {'hired', 'rejected', 'withdrawn'})
        for status in FINAL_STATUSES:
            for actor in (Actor.CLIENT, Actor.FREELANCER):
                self.assertEqual(allowed_next_statuses(status, actor), set(), f'{actor} from {status}')

    def test_the_client_cannot_skip_a_stage(self):
        self.assertFalse(can_transition('pending', 'shortlisted', Actor.CLIENT))
        self.assertFalse(can_transition('pending', 'hired', Actor.CLIENT))
        self.assertFalse(can_transition('under_review', 'hired', Actor.CLIENT))

    def test_the_client_can_reject_from_every_live_stage(self):
        for status in ('pending', 'under_review', 'shortlisted'):
            self.assertIn('rejected', allowed_next_statuses(status, Actor.CLIENT))

    def test_the_freelancer_cannot_withdraw_once_shortlisted(self):
        self.assertFalse(can_transition('shortlisted', 'withdrawn', Actor.FREELANCER))

    def test_the_client_cannot_withdraw_and_the_freelancer_cannot_review(self):
        self.assertFalse(can_transition('pending', 'withdrawn', Actor.CLIENT))
        self.assertFalse(can_transition('pending', 'under_review', Actor.FREELANCER))
        self.assertFalse(can_transition('shortlisted', 'hired', Actor.FREELANCER))

    def test_allowed_next_statuses_returns_a_copy(self):
        allowed_next_statuses('pending', Actor.CLIENT).add('hired')
        self.assertNotIn('hired', allowed_next_statuses('pending', Actor.CLIENT))


class ChangeStatusTests(ApplicationTestBase):
    def test_a_valid_change_updates_the_status_and_records_an_event(self):
        application = self.make_application()
        event = application.change_status('under_review', Actor.CLIENT, self.client_user, note='Looks good.')

        application.refresh_from_db()
        self.assertEqual(application.status, 'under_review')
        self.assertEqual(
            (event.from_status, event.to_status, event.changed_by, event.note),
            ('pending', 'under_review', self.client_user, 'Looks good.'),
        )
        self.assertEqual(application.events.count(), 1)

    def test_every_change_is_recorded_in_order(self):
        application = self.make_application()
        application.change_status('under_review', Actor.CLIENT, self.client_user)
        application.change_status('shortlisted', Actor.CLIENT, self.client_user)
        application.change_status('hired', Actor.CLIENT, self.client_user)

        trail = [(e.from_status, e.to_status) for e in application.events.all()]
        self.assertEqual(
            trail, [('pending', 'under_review'), ('under_review', 'shortlisted'), ('shortlisted', 'hired')]
        )

    def test_an_invalid_change_raises_and_changes_nothing(self):
        application = self.make_application()
        with self.assertRaises(InvalidTransition):
            application.change_status('hired', Actor.CLIENT, self.client_user)

        application.refresh_from_db()
        self.assertEqual(application.status, 'pending')
        self.assertEqual(application.events.count(), 0)

    def test_the_wrong_actor_cannot_make_the_change(self):
        application = self.make_application()
        with self.assertRaises(InvalidTransition):
            application.change_status('under_review', Actor.FREELANCER, self.freelancer)

    def test_the_freelancer_can_withdraw_from_pending(self):
        application = self.make_application()
        application.change_status('withdrawn', Actor.FREELANCER, self.freelancer)
        application.refresh_from_db()
        self.assertEqual(application.status, 'withdrawn')

    def test_a_final_application_cannot_change_again(self):
        application = self.make_application()
        application.change_status('rejected', Actor.CLIENT, self.client_user)
        with self.assertRaises(InvalidTransition):
            application.change_status('under_review', Actor.CLIENT, self.client_user)

    def test_a_stale_copy_cannot_act_on_an_old_status(self):
        application = self.make_application()
        stale = Application.objects.get(pk=application.pk)  # still thinks it is pending

        application.change_status('withdrawn', Actor.FREELANCER, self.freelancer)
        with self.assertRaises(InvalidTransition):
            stale.change_status('rejected', Actor.CLIENT, self.client_user)

        self.assertEqual(application.events.count(), 1)

    def test_the_system_can_record_a_change_with_no_user(self):
        application = self.make_application()
        event = application.change_status('withdrawn', Actor.FREELANCER, None, note='Account deleted.')
        self.assertIsNone(event.changed_by)

    def test_an_event_can_have_a_blank_from_status_for_the_first_entry(self):
        application = self.make_application()
        event = ApplicationStatusEvent.objects.create(
            application=application, from_status='', to_status='pending', changed_by=self.freelancer
        )
        event.full_clean()

    def test_events_survive_their_author_being_deleted_as_null(self):
        application = self.make_application()
        application.change_status('under_review', Actor.CLIENT, self.other_freelancer)
        self.other_freelancer.delete()
        self.assertIsNone(application.events.get().changed_by)

    def test_deleting_an_application_deletes_its_history(self):
        application = self.make_application()
        application.change_status('under_review', Actor.CLIENT, self.client_user)
        application.delete()
        self.assertEqual(ApplicationStatusEvent.objects.count(), 0)
