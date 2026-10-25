import tempfile
import uuid
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone

from django.test import TestCase, override_settings

from accounts.models import User
from applications.models import Application
from gigs.models import Category, Gig, GigInteraction, Skill
from profiles.models import FreelancerProfile

from . import content
from .evaluation import compare as cmp
from .evaluation import fitting
from .evaluation import split as ev

START = datetime(2026, 10, 1, 12, 0, tzinfo=dt_timezone.utc)

SMALL_COLLABORATIVE = {
    'RECOMMENDER_SVD_MIN_FREELANCERS': 4, 'RECOMMENDER_SVD_MIN_GIGS': 10, 'RECOMMENDER_SVD_MIN_INTERACTIONS': 40,
}


# The text cleaner drops numbers, so each gig needs a word of its own or the gigs become duplicates and are dropped.
WORDS = [
    'apple', 'bridge', 'candle', 'dragon', 'engine', 'forest', 'garden', 'harbor', 'island', 'jungle',
    'kettle', 'ladder', 'meadow', 'needle', 'orchard', 'pillow', 'quarry', 'rocket', 'saddle', 'tunnel',
]


def day(n):
    return START + timedelta(days=n)


class BlockWorld(TestCase):
    """
    Two groups of 6 freelancers and two blocks of 20 gigs. Group A only ever applies to block A, group B to block B.
    Freelancer i of a group applies to 8 gigs of their block, starting at gig 3 * i and wrapping round, one a day on
    days 1 to 8. So each has 6 train applications (days 1 to 6), one in validation (day 7) and one in test (day 8),
    and every gig held out for someone is also applied to in train by the next freelancer in their group. A model that
    learns "this group likes this block" can find the held-out gigs.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        override = override_settings(RECOMMENDER_DATA_DIR=self.tmp.name)
        override.enable()
        self.addCleanup(override.disable)

        self.category = Category.objects.create(name='Block World Category')
        self.client_user = self.make_user('block-client@example.com', 'client')
        self.skills = {
            'A': Skill.objects.create(name='Blockalpha', category='Test'),
            'B': Skill.objects.create(name='Blockbeta', category='Test'),
        }
        self.gigs = {'A': [], 'B': []}
        names = {'A': 'alpha', 'B': 'beta'}
        for group in 'AB':
            for n, word in enumerate(WORDS):
                gig = Gig.objects.create(
                    client=self.client_user, category=self.category,
                    title=f'{word.title()} project for {names[group]}',
                    description=(
                        f'Work for the {names[group]} group on {self.skills[group].name} things near the {word}.'
                    ),
                    budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=60),
                )
                gig.skills.set([self.skills[group]])
                self.gigs[group].append(gig)
        Gig.objects.update(created_at=day(-30))

        self.people = {'A': [], 'B': []}
        for group in 'AB':
            for i in range(6):
                person = self.make_user(f'block-{group}-{i}@example.com', 'freelancer')
                person.freelancer_profile.skills.set([self.skills[group]])
                self.people[group].append(person)
                for j in range(8):
                    self.apply(person, self.gigs[group][(3 * i + j) % 20], j + 1)

    def make_user(self, email, role):
        number = User.objects.count() + 1
        return User.objects.create_user(
            email=email, password='x-Block-pass-1', full_name=email.split('@')[0],
            phone=f'2547000093{number:02d}', role=role,
        )

    def apply(self, person, gig, days, status='pending'):
        application = Application.objects.create(gig=gig, freelancer=person, cover_letter='x' * 60, status=status)
        Application.objects.filter(pk=application.pk).update(created_at=day(days))
        return application

    def make_split(self, include_synthetic=True):
        return ev.build_split(ev.load_positives(include_synthetic), include_synthetic=include_synthetic)

    def at(self, comparison, method, k, metric, group='all'):
        return comparison.results[method].groups[group][(k, metric)].mean


class WorldIsAsDescribedTests(BlockWorld):
    def test_every_freelancer_has_six_train_and_one_in_each_held_out_part(self):
        split = self.make_split()
        self.assertEqual(len(split.evaluated_freelancers()), 12)
        for parts in split.by_freelancer().values():
            self.assertEqual((len(parts['train']), len(parts['validation']), len(parts['test'])), (6, 1, 1))

    def test_every_held_out_gig_is_applied_to_in_train_by_someone_else(self):
        split = self.make_split()
        train_gigs_by_other = {}
        for freelancer_id, parts in split.by_freelancer().items():
            for p in parts['train']:
                train_gigs_by_other.setdefault(p.gig_id, set()).add(freelancer_id)
        for freelancer_id, parts in split.by_freelancer().items():
            for part in ('validation', 'test'):
                gig_id = parts[part][0].gig_id
                self.assertTrue(train_gigs_by_other.get(gig_id, set()) - {freelancer_id}, part)


def means(comparison, method, group='all'):
    """Every average for a method as {(k, metric): mean}, to compare whole methods at once."""
    return {key: summary.mean for key, summary in comparison.results[method].groups[group].items()}


@override_settings(**SMALL_COLLABORATIVE)
class BlockWorldComparisonTests(BlockWorld):
    """
    In this world every freelancer has exactly one right answer in each held-out part and 33 candidates (40 gigs,
    minus 6 applied to in train, minus the one held out in the other part). That fixes several things by hand.
    """

    def run_compare(self, **kwargs):
        include_synthetic = kwargs.get('include_synthetic', True)
        return cmp.compare(self.make_split(include_synthetic), **kwargs)

    def test_every_method_is_compared_over_the_same_33_candidates_for_all_12_freelancers(self):
        result = self.run_compare()
        self.assertEqual(set(result.results), set(cmp.METHODS))
        self.assertEqual(result.info['freelancers_in_part'], 12)
        self.assertEqual(result.info['candidates'], {'smallest': 33, 'median': 33, 'largest': 33})
        self.assertEqual(result.group_sizes, {'all': 12, 'cold_start': 0, 'not_cold_start': 12})
        self.assertEqual(result.info['outside_the_rules'], 0)
        for method in cmp.METHODS:
            self.assertEqual(result.results[method].groups['all'][(5, 'precision')].n, 12, method)

    def test_with_one_right_answer_each_every_metric_follows_from_the_hit_rate(self):
        # With one relevant gig, precision is hit / K, recall is hit, and F1 is 2 * hit / (K + 1). This holds for
        # every method whatever it ranks, so it checks the plumbing and not the models.
        result = self.run_compare()
        for method in cmp.METHODS:
            found = means(result, method)
            for k in (5, 10, 20):
                hit = found[(k, 'hit')]
                self.assertAlmostEqual(found[(k, 'precision')], hit / k, msg=f'{method} P@{k}')
                self.assertAlmostEqual(found[(k, 'recall')], hit, msg=f'{method} R@{k}')
                self.assertAlmostEqual(found[(k, 'f1')], 2 * hit / (k + 1), msg=f'{method} F1@{k}')

    def test_the_random_baseline_hits_at_the_rate_chance_says(self):
        # One right answer among 33: a random top 5 holds it 5 / 33 of the time, and a top 20 holds it 20 / 33.
        found = means(self.run_compare(), 'random')
        self.assertAlmostEqual(found[(5, 'hit')], 5 / 33, delta=0.08)
        self.assertAlmostEqual(found[(20, 'hit')], 20 / 33, delta=0.1)

    def test_the_random_baseline_reports_how_much_luck_alone_moves_it(self):
        result = self.run_compare()
        self.assertEqual(result.random_seeds, 20)
        spread = result.results['random'].spread
        self.assertEqual(set(spread), {(k, m) for k in (5, 10, 20) for m in ('precision', 'recall', 'f1', 'hit')})
        self.assertGreater(spread[(5, 'hit')].sd, 0.0)
        self.assertLessEqual(spread[(5, 'hit')].low, spread[(5, 'hit')].high)

    def test_the_content_model_finds_every_right_answer_in_its_top_20(self):
        # Only the 13 candidates in the freelancer's own block share any word with them, and the other 20 score
        # exactly 0, so the right answer is always among the first 13. (Which of the 13 comes first is a tie.)
        self.assertEqual(means(self.run_compare(), 'content')[(20, 'hit')], 1.0)

    def test_the_collaborative_model_finds_the_pattern_this_world_was_built_with(self):
        # Group A only ever applies to block A, and the held-out gig of each is also in train for the next
        # freelancer. A model that learns that should put it near the top; random manages about 10 / 33.
        result = self.run_compare()
        for method in ('collaborative_applications', 'collaborative_all'):
            found = means(result, method)
            self.assertGreaterEqual(found[(10, 'hit')], 0.8, method)
            self.assertGreater(found[(10, 'hit')], means(result, 'random')[(10, 'hit')] + 0.3, method)

    def test_with_no_interactions_the_two_collaborative_variants_are_the_same_model(self):
        result = self.run_compare()
        self.assertEqual(means(result, 'collaborative_applications'), means(result, 'collaborative_all'))

    def test_the_models_can_score_every_candidate_and_every_right_answer_here(self):
        result = self.run_compare()
        for method in ('collaborative_applications', 'collaborative_all'):
            self.assertEqual(result.results[method].coverage, 1.0)
            self.assertEqual(result.results[method].relevant_coverage, 1.0)

    def test_a_right_answer_nobody_touched_in_train_cannot_be_scored_and_is_reported(self):
        # Freelancer A0's validation application moves to a new gig that no one else applied to. Every freelancer
        # now has 34 candidates (41 gigs - 6 train - 1 other part) and the new gig is the one with no score, so
        # 33 / 34 of the candidates are scored. 11 of the 12 right answers are scored.
        zebra = Gig.objects.create(
            client=self.client_user, category=self.category, title='Zebra project for alpha',
            description='Work for the alpha group on Blockalpha things near the zebra.',
            budget_min=1000, budget_max=2000, deadline=date.today() + timedelta(days=60),
        )
        zebra.skills.set([self.skills['A']])
        Gig.objects.filter(pk=zebra.pk).update(created_at=day(-30))
        moved = Application.objects.get(freelancer=self.people['A'][0], gig=self.gigs['A'][6])
        Application.objects.filter(pk=moved.pk).update(gig=zebra)

        result = self.run_compare()
        self.assertEqual(result.info['candidates'], {'smallest': 34, 'median': 34.0, 'largest': 34})
        for method in ('collaborative_applications', 'collaborative_all'):
            self.assertAlmostEqual(result.results[method].coverage, 33 / 34)
            self.assertAlmostEqual(result.results[method].relevant_coverage, 11 / 12)
            # A0's right answer goes to the back of the list, so no top 20 can hold it.
            self.assertLessEqual(means(result, method)[(20, 'hit')], 11 / 12 + 1e-9, method)

    def test_the_same_data_and_seed_give_the_same_numbers_twice(self):
        first, second = self.run_compare(), self.run_compare()
        for method in cmp.METHODS:
            self.assertEqual(means(first, method), means(second, method), method)
        self.assertEqual(first.results['random'].spread, second.results['random'].spread)

    def test_the_intervals_hold_the_means(self):
        result = self.run_compare()
        for method in cmp.METHODS:
            for key, summary in result.results[method].groups['all'].items():
                self.assertLessEqual(summary.low, summary.mean + 1e-9, (method, key))
                self.assertGreaterEqual(summary.high, summary.mean - 1e-9, (method, key))

    def test_the_test_part_is_scored_on_the_test_applications_only(self):
        result = self.run_compare(part='test')
        self.assertEqual(result.part, 'test')
        self.assertEqual(result.info['candidates'], {'smallest': 33, 'median': 33, 'largest': 33})
        self.assertEqual(result.info['positives'], 12)

    def test_the_train_part_cannot_be_scored(self):
        with self.assertRaises(ValueError):
            self.run_compare(part='train')

    def test_zero_random_seeds_is_refused(self):
        with self.assertRaises(ValueError):
            self.run_compare(random_seeds=0)


@override_settings(**SMALL_COLLABORATIVE)
class ColdStartGroupTests(BlockWorld):
    """Each freelancer has 6 different gigs in training, so the cold-start threshold decides who is in the group."""

    def compare(self):
        return cmp.compare(self.make_split())

    def test_at_the_default_threshold_of_five_nobody_is_in_cold_start(self):
        result = self.compare()
        self.assertEqual(result.group_sizes, {'all': 12, 'cold_start': 0, 'not_cold_start': 12})
        self.assertEqual(result.results['hybrid'].groups['cold_start'], {})

    def test_the_hybrid_uses_the_collaborative_score_once_there_are_enough_gigs(self):
        # 6 gigs: the weight is 0.5 * (6 - 5 + 1) / 20 = 0.05, which is above 0, so the hybrid is not the content
        # score. The collaborative part breaks the ties inside the freelancer's own block.
        result = self.compare()
        self.assertNotEqual(means(result, 'hybrid'), means(result, 'content'))

    @override_settings(RECOMMENDER_COLD_START_MIN_GIGS=7)
    def test_raising_the_threshold_puts_everyone_in_cold_start_where_the_hybrid_is_the_content_model(self):
        result = self.compare()
        self.assertEqual(result.group_sizes, {'all': 12, 'cold_start': 12, 'not_cold_start': 0})
        self.assertEqual(result.results['hybrid'].groups['not_cold_start'], {})
        self.assertEqual(means(result, 'hybrid', 'cold_start'), means(result, 'content', 'cold_start'))

    def test_a_freelancer_with_few_gigs_is_reported_apart_and_is_scored_on_content_alone(self):
        # A newcomer with 5 applications splits 3, 1, 1, so has 3 gigs in training: cold start.
        newcomer = self.make_user('block-newcomer@example.com', 'freelancer')
        newcomer.freelancer_profile.skills.set([self.skills['A']])
        for j in range(5):
            self.apply(newcomer, self.gigs['A'][j], j + 1)
        result = self.compare()
        self.assertEqual(result.group_sizes, {'all': 13, 'cold_start': 1, 'not_cold_start': 12})
        self.assertEqual(means(result, 'hybrid', 'cold_start'), means(result, 'content', 'cold_start'))
        for method in cmp.METHODS:
            self.assertEqual(result.results[method].groups['cold_start'][(5, 'hit')].n, 1, method)
            self.assertEqual(result.results[method].groups['not_cold_start'][(5, 'hit')].n, 12, method)

    def test_a_freelancer_with_no_skills_and_no_bio_cannot_be_compared_and_is_counted(self):
        blank = self.make_user('block-blank@example.com', 'freelancer')
        for j in range(5):
            self.apply(blank, self.gigs['A'][j], j + 1)
        result = self.compare()
        self.assertEqual(result.info['unscorable_freelancers'], 1)
        self.assertEqual(result.group_sizes['all'], 13)


class ModelNotAvailableTests(BlockWorld):
    """Under the default minimums (10 freelancers, 20 gigs, 100 pairs) this world has too few pairs."""

    def test_a_collaborative_model_that_could_not_be_fitted_is_marked_unavailable_with_the_reason(self):
        result = cmp.compare(self.make_split())
        for method in ('collaborative_applications', 'collaborative_all'):
            self.assertFalse(result.results[method].available, method)
            self.assertEqual(result.results[method].groups, {}, method)
            self.assertIn('72 freelancer and gig pairs', result.results[method].note, method)
        self.assertEqual(set(result.info['skipped']), {'all', 'applications'})

    def test_the_other_methods_still_run_and_the_hybrid_is_then_the_content_model(self):
        result = cmp.compare(self.make_split())
        for method in ('random', 'popularity', 'content', 'hybrid'):
            self.assertTrue(result.results[method].available, method)
        self.assertEqual(means(result, 'hybrid'), means(result, 'content'))


@override_settings(**SMALL_COLLABORATIVE)
class StrictRelevanceAndDataChoiceTests(BlockWorld):
    def test_strict_relevance_counts_only_shortlisted_and_hired_and_keeps_the_candidates(self):
        # A0's validation gig is gig 6 and A1's is gig 9. Shortlist those two, and hire A2 in the test part only.
        for person, number, status in (
            (self.people['A'][0], 6, 'shortlisted'), (self.people['A'][1], 9, 'shortlisted'),
            (self.people['A'][2], 13, 'hired'),
        ):
            Application.objects.filter(freelancer=person, gig=self.gigs['A'][number]).update(status=status)
        split = self.make_split()

        validation = cmp.compare(split, part='validation', strict=True)
        self.assertTrue(validation.strict)
        self.assertEqual(validation.info['relevant'], 2)
        self.assertEqual(validation.group_sizes['all'], 2)
        self.assertEqual(validation.results['content'].groups['all'][(5, 'hit')].n, 2)
        self.assertEqual(validation.info['candidates'], {'smallest': 33, 'median': 33, 'largest': 33})

        everyone = cmp.compare(split, part='validation', strict=False)
        self.assertEqual(everyone.info['relevant'], 12)

        test = cmp.compare(split, part='test', strict=True)
        self.assertEqual(test.info['relevant'], 1)  # only A2's hire is in the test part

    def test_leaving_synthetic_data_out_drops_the_synthetic_freelancers_and_counts_the_share(self):
        User.objects.filter(email__startswith='block-B-').update(is_synthetic=True)
        with_synthetic = cmp.compare(self.make_split(True), include_synthetic=True)
        self.assertEqual(with_synthetic.info['freelancers_in_part'], 12)
        self.assertEqual(with_synthetic.info['positives'], 12)
        self.assertEqual(with_synthetic.info['synthetic_positives'], 6)
        self.assertTrue(with_synthetic.info['include_synthetic'])

        without = cmp.compare(self.make_split(False), include_synthetic=False)
        self.assertEqual(without.info['freelancers_in_part'], 6)
        self.assertEqual(without.info['synthetic_positives'], 0)
        self.assertFalse(without.info['include_synthetic'])

    def test_a_split_with_nobody_to_evaluate_gives_empty_results_and_no_error(self):
        result = cmp.compare(ev.build_split([]))
        self.assertEqual(result.group_sizes, {'all': 0, 'cold_start': 0, 'not_cold_start': 0})
        self.assertEqual(result.info['candidates'], {})
        for method in cmp.METHODS:
            self.assertEqual(result.results[method].groups.get('all', {}), {}, method)


@override_settings(**SMALL_COLLABORATIVE)
class LeakageThroughTheComparisonTests(BlockWorld):
    """The guard is tested on its own in test_evaluation_leakage. This checks it holds all the way through."""

    def pairs_in_the_collaborative_model(self):
        return cmp.compare(self.make_split(), random_seeds=1).info['models']['pairs_all']

    def view(self, person, gig, days):
        row = GigInteraction.objects.create(gig=gig, user=person, type='view')
        GigInteraction.objects.filter(pk=row.pk).update(created_at=day(days))

    def test_a_view_of_a_gig_the_freelancer_went_on_to_apply_to_never_reaches_the_model(self):
        before = self.pairs_in_the_collaborative_model()
        self.assertEqual(before, 72)  # 12 freelancers x 6 train applications
        self.view(self.people['A'][0], self.gigs['A'][6], 2)  # A0's validation gig, viewed well before the cut-off
        self.assertEqual(self.pairs_in_the_collaborative_model(), 72)

    def test_a_view_after_the_cutoff_never_reaches_the_model(self):
        self.view(self.people['A'][0], self.gigs['B'][0], 7)  # the cut-off is day 6
        self.assertEqual(self.pairs_in_the_collaborative_model(), 72)

    def test_a_view_before_the_cutoff_of_an_unrelated_gig_does_reach_it(self):
        self.view(self.people['A'][0], self.gigs['B'][0], 3)
        self.assertEqual(self.pairs_in_the_collaborative_model(), 73)

    def test_the_applications_only_model_ignores_views_altogether(self):
        self.view(self.people['A'][0], self.gigs['B'][0], 3)
        stats = cmp.compare(self.make_split(), random_seeds=1).info['models']
        self.assertEqual((stats['pairs_all'], stats['pairs_applications']), (73, 72))


@override_settings(**SMALL_COLLABORATIVE)
class ScorerTests(BlockWorld):
    def setUp(self):
        super().setUp()
        self.split = self.make_split()
        self.models = fitting.fit_models(self.split)
        self.scorer = fitting.Scorer(self.models)
        self.person = self.people['A'][0]
        self.candidates = [gig.id for gig in self.gigs['A'][:6] + self.gigs['B'][:6]]

    def test_content_scores_are_the_ones_the_live_content_model_gives(self):
        profile = FreelancerProfile.objects.prefetch_related('skills').get(user=self.person)
        gigs = Gig.objects.filter(id__in=self.candidates).select_related('category').prefetch_related('skills')
        matches = content.rank_for_freelancer(self.models.vectoriser, profile, gigs)
        live = {match.gig.id: match.score for match in matches}
        mine = self.scorer.content_scores(self.person.id, self.candidates)
        self.assertEqual(set(live), set(mine))
        for gig_id, score in live.items():
            self.assertAlmostEqual(mine[gig_id], score, msg=str(gig_id))

    def test_content_scores_are_zero_for_the_other_block_and_positive_for_their_own(self):
        scores = self.scorer.content_scores(self.person.id, self.candidates)
        for gig in self.gigs['A'][:6]:
            self.assertGreater(scores[gig.id], 0.0)
        for gig in self.gigs['B'][:6]:
            self.assertEqual(scores[gig.id], 0.0)

    def test_the_hybrid_is_the_blend_with_the_weight_worked_out_from_six_training_gigs(self):
        # Six different gigs in training: w = 0.5 * (6 - 5 + 1) / 20 = 0.05.
        self.assertEqual(self.models.history[self.person.id], 6)
        content_scores = self.scorer.content_scores(self.person.id, self.candidates)
        raw = self.scorer.collaborative_scores(self.models.collaborative_all, self.person.id, self.candidates)
        scale = self.models.collaborative_all.scale
        blended = self.scorer.hybrid_scores(self.person.id, self.candidates)
        for gig_id in self.candidates:
            collaborative = min(1.0, max(0.0, raw[gig_id] / scale))
            self.assertAlmostEqual(blended[gig_id], 0.05 * collaborative + 0.95 * content_scores[gig_id])

    def test_a_freelancer_without_skills_or_bio_gets_no_scores(self):
        blank = self.make_user('block-blank-scorer@example.com', 'freelancer')
        scorer = fitting.Scorer(self.models)
        self.assertFalse(scorer.scorable(blank.id))
        self.assertEqual(set(scorer.content_scores(blank.id, self.candidates).values()), {None})

    def test_a_freelancer_the_model_has_never_seen_has_no_collaborative_scores(self):
        scores = self.scorer.collaborative_scores(self.models.collaborative_all, uuid.uuid4(), self.candidates)
        self.assertEqual(set(scores.values()), {None})

    def test_no_model_means_no_scores_not_zeros(self):
        scores = self.scorer.collaborative_scores(None, self.person.id, self.candidates)
        self.assertEqual(set(scores.values()), {None})


