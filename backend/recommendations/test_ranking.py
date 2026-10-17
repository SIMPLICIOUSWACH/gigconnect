from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from gigs.models import Category, Gig
from profiles.models import Skill

from . import content
from .candidates import candidate_gigs
from .features import gig_document
from .platform import gigs_for_training


class RankForFreelancerTests(TestCase):
    """Ranking real gig objects. The expected order is worked out from which skills each gig shares."""

    def setUp(self):
        self.category = Category.objects.create(name='Ranking Test Category')
        self.django = Skill.objects.create(name='Django Test', category='Test')
        self.python = Skill.objects.create(name='Python Test', category='Test')
        self.excel = Skill.objects.create(name='Excel Test', category='Test')

        self.client_user = self.make_user('rank-client@example.com', 'client')
        self.freelancer = self.make_user('rank-freelancer@example.com', 'freelancer')
        self.profile = self.freelancer.freelancer_profile
        self.profile.skills.set([self.django, self.python])

        # Shares both skills, shares one skill, shares none.
        self.both = self.make_gig('Quokka dashboard', 'Build a quokka dashboard', [self.django, self.python])
        self.one = self.make_gig('Wombat scraper', 'Write a wombat scraper', [self.python])
        self.none = self.make_gig('Numbat ledger', 'Keep a numbat ledger', [self.excel])
        self.vectoriser = self.fit_on_the_gigs()

    def make_user(self, email, role):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password='x-Ranking-pass-1', full_name=email.split('@')[0],
            phone=f'2547000007{number:02d}', role=role,
        )

    def make_gig(self, title, description, skills):
        gig = Gig.objects.create(
            client=self.client_user, category=self.category, title=title, description=description,
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=30),
        )
        gig.skills.set(skills)
        return gig

    def fit_on_the_gigs(self):
        documents = [
            gig_document(g.title, g.description, [s.name for s in g.skills.all()], g.category.name)
            for g in gigs_for_training()
        ]
        return content.fit_vectoriser(documents, [], min_df=1, max_df=1.0)

    def rank(self, gigs=None):
        profile = type(self.profile).objects.prefetch_related('skills').get(pk=self.profile.pk)
        gigs = gigs if gigs is not None else Gig.objects.select_related('category').prefetch_related('skills')
        return content.rank_for_freelancer(self.vectoriser, profile, gigs)

    def test_gigs_come_back_best_first(self):
        self.assertEqual([m.gig.title for m in self.rank()], ['Quokka dashboard', 'Wombat scraper', 'Numbat ledger'])

    def test_each_gig_names_the_skills_it_really_shares(self):
        reasons = {m.gig.title: m.match_reasons for m in self.rank()}
        self.assertEqual(reasons['Quokka dashboard'], ['Django Test', 'Python Test'])
        self.assertEqual(reasons['Wombat scraper'], ['Python Test'])
        self.assertEqual(reasons['Numbat ledger'], [])

    def test_scores_fall_as_less_is_shared_and_none_shared_is_zero(self):
        scores = [m.score for m in self.rank()]
        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[1], 0.0)
        self.assertEqual(scores[2], 0.0)

    def test_a_score_is_the_same_whichever_gigs_it_is_ranked_with(self):
        alone = self.rank([self.one])[0].score
        together = {m.gig.title: m.score for m in self.rank()}['Wombat scraper']
        self.assertAlmostEqual(alone, together, places=9)

    def test_equal_scores_put_the_newest_gig_first_every_time(self):
        older = self.make_gig('Identical gig', 'Same words here', [self.excel])
        newer = self.make_gig('Identical gig', 'Same words here', [self.excel])
        Gig.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=2))
        self.vectoriser = self.fit_on_the_gigs()
        identical = [m.gig.id for m in self.rank() if m.gig.title == 'Identical gig']
        self.assertEqual(identical, [newer.id, older.id])
        self.assertEqual([m.gig.id for m in self.rank()], [m.gig.id for m in self.rank()])

    def test_a_freelancer_with_no_skills_and_no_bio_gets_nothing_back(self):
        self.profile.skills.clear()
        self.assertEqual(self.rank(), [])

    def test_a_bio_alone_can_score_but_never_invents_a_reason(self):
        self.profile.skills.clear()
        self.profile.bio = 'I build a quokka dashboard'
        self.profile.save()
        matches = {m.gig.title: m for m in self.rank()}
        self.assertGreater(matches['Quokka dashboard'].score, 0.0)
        self.assertEqual(matches['Quokka dashboard'].match_reasons, [])

    def test_no_gigs_gives_nothing_back(self):
        self.assertEqual(self.rank([]), [])

    def test_ranking_makes_no_database_queries_of_its_own(self):
        profile = type(self.profile).objects.prefetch_related('skills').get(pk=self.profile.pk)
        gigs = list(Gig.objects.select_related('category').prefetch_related('skills'))
        with self.assertNumQueries(0):
            content.rank_for_freelancer(self.vectoriser, profile, gigs)

    def test_ranks_only_the_gigs_the_freelancer_could_apply_to(self):
        Gig.objects.filter(pk=self.one.pk).update(status=Gig.Status.CLOSED)
        ranked = self.rank(candidate_gigs(self.freelancer))
        self.assertEqual([m.gig.title for m in ranked], ['Quokka dashboard', 'Numbat ledger'])
