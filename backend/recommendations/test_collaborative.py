from django.test import SimpleTestCase, override_settings

from . import collaborative as collab

# Small limits, so a hand-built matrix of a few people and gigs can be fitted.
SMALL = {
    'RECOMMENDER_SVD_MIN_FREELANCERS': 1,
    'RECOMMENDER_SVD_MIN_GIGS': 1,
    'RECOMMENDER_SVD_MIN_INTERACTIONS': 1,
}


def weights_from(groups, weight=3):
    """{(user, gig): weight} from {'A': ['g1', 'g2'], ...}."""
    return {(user, gig): weight for user, gigs in groups.items() for gig in gigs}


# Two groups of three freelancers. Group one likes gigs g1 to g3 and group two likes g4 to g6.
# A has not seen g3 and F has not seen g6, although the rest of their group has.
TWO_GROUPS = weights_from({
    'A': ['g1', 'g2'], 'B': ['g1', 'g2', 'g3'], 'C': ['g1', 'g2', 'g3'],
    'D': ['g4', 'g5', 'g6'], 'E': ['g4', 'g5', 'g6'], 'F': ['g4', 'g5'],
})


class BuildWeightsTests(SimpleTestCase):
    def test_the_strongest_interaction_for_a_pair_wins_and_they_are_not_added(self):
        weights = collab.build_weights(
            [('u1', 'g1', 'view'), ('u1', 'g1', 'view'), ('u1', 'g1', 'apply'), ('u1', 'g2', 'view')], [],
        )
        self.assertEqual(weights, {('u1', 'g1'): 3, ('u1', 'g2'): 1})

    def test_each_kind_of_interaction_has_its_weight(self):
        weights = collab.build_weights(
            [('u', 'a', 'view'), ('u', 'b', 'search_click'), ('u', 'c', 'save'), ('u', 'd', 'apply')], [],
        )
        self.assertEqual(weights, {('u', 'a'): 1, ('u', 'b'): 1, ('u', 'c'): 2, ('u', 'd'): 3})

    def test_application_outcomes_raise_the_weight(self):
        applications = [('u', 'a', 'pending'), ('u', 'b', 'shortlisted'), ('u', 'c', 'hired')]
        self.assertEqual(
            collab.build_weights([], applications), {('u', 'a'): 3, ('u', 'b'): 4, ('u', 'c'): 5},
        )

    def test_a_rejected_or_withdrawn_application_still_counts_as_applying_and_no_more(self):
        applications = [('u', 'a', 'rejected'), ('u', 'b', 'withdrawn')]
        self.assertEqual(collab.build_weights([], applications), {('u', 'a'): 3, ('u', 'b'): 3})

    def test_an_application_outranks_a_view_of_the_same_gig(self):
        weights = collab.build_weights([('u', 'g', 'view')], [('u', 'g', 'shortlisted')])
        self.assertEqual(weights, {('u', 'g'): 4})

    def test_a_weaker_signal_never_lowers_a_stronger_one(self):
        weights = collab.build_weights([('u', 'g', 'view')], [('u', 'g', 'rejected')])
        self.assertEqual(weights, {('u', 'g'): 3})
        weights = collab.build_weights([('u', 'g', 'apply')], [('u', 'g', 'withdrawn')])
        self.assertEqual(weights, {('u', 'g'): 3})

    def test_a_type_or_status_with_no_weight_is_ignored(self):
        weights = collab.build_weights([('u', 'g', 'something_new')], [('u', 'g', 'unknown_status')])
        self.assertEqual(weights, {})

    def test_the_weights_come_from_the_settings(self):
        with override_settings(RECOMMENDER_INTERACTION_WEIGHTS={'view': 7}):
            self.assertEqual(collab.build_weights([('u', 'g', 'view')], []), {('u', 'g'): 7})

    def test_no_data_gives_no_weights(self):
        self.assertEqual(collab.build_weights([], []), {})


class BuildMatrixTests(SimpleTestCase):
    def test_rows_are_freelancers_and_columns_are_gigs(self):
        matrix, users, gigs = collab.build_matrix({('u1', 'g1'): 3, ('u1', 'g2'): 1, ('u2', 'g2'): 5})
        self.assertEqual(matrix.shape, (2, 2))
        dense = matrix.toarray()
        self.assertEqual(dense[users['u1'], gigs['g1']], 3)
        self.assertEqual(dense[users['u1'], gigs['g2']], 1)
        self.assertEqual(dense[users['u2'], gigs['g2']], 5)
        self.assertEqual(dense[users['u2'], gigs['g1']], 0)

    def test_only_people_and_gigs_with_an_interaction_appear(self):
        matrix, users, gigs = collab.build_matrix({('u1', 'g1'): 3})
        self.assertEqual((set(users), set(gigs)), ({'u1'}, {'g1'}))
        self.assertEqual(matrix.nnz, 1)


class TooLittleDataTests(SimpleTestCase):
    def reason(self, weights):
        return collab.too_little_data(collab.build_matrix(weights)[0])

    def test_names_the_first_minimum_that_is_not_met(self):
        self.assertIn('freelancers', self.reason({('u', 'g'): 3}))

    def test_enough_data_gives_no_reason(self):
        with override_settings(**SMALL):
            self.assertEqual(self.reason(TWO_GROUPS), '')

    def test_each_of_the_three_minimums_is_checked(self):
        limits = {**SMALL, 'RECOMMENDER_SVD_MIN_FREELANCERS': 7}
        with override_settings(**limits):
            self.assertIn('7 are needed', self.reason(TWO_GROUPS))
        with override_settings(**{**SMALL, 'RECOMMENDER_SVD_MIN_GIGS': 9}):
            self.assertIn('9 are needed', self.reason(TWO_GROUPS))
        with override_settings(**{**SMALL, 'RECOMMENDER_SVD_MIN_INTERACTIONS': 99}):
            self.assertIn('99 are needed', self.reason(TWO_GROUPS))


@override_settings(**SMALL)
class FitAndScoreTests(SimpleTestCase):
    """
    The hand-built matrix has two groups of freelancers. With two hidden factors, one for each group,
    a freelancer should be pointed at the gigs their group liked, and not at the other group's gigs.
    """

    def setUp(self):
        self.model = collab.fit(TWO_GROUPS, n_components=2)
        self.all_gigs = ['g1', 'g2', 'g3', 'g4', 'g5', 'g6']

    def test_a_gig_that_similar_freelancers_liked_ranks_above_the_other_groups_gigs(self):
        scores = collab.score(self.model, 'A', self.all_gigs)
        # g3 is unseen by A but liked by B and C, who share A's history.
        for other_group in ('g4', 'g5', 'g6'):
            self.assertGreater(scores['g3'], scores[other_group])
        # Weights are 3, so a gig the group liked scores near that and the other group's near zero.
        self.assertGreater(scores['g3'], 1.0)
        for other_group in ('g4', 'g5', 'g6'):
            self.assertLess(abs(scores[other_group]), 0.5)

    def test_the_same_holds_for_the_other_group(self):
        scores = collab.score(self.model, 'F', self.all_gigs)
        for other_group in ('g1', 'g2', 'g3'):
            self.assertGreater(scores['g6'], scores[other_group])
        self.assertGreater(scores['g6'], 1.0)

    def test_gigs_a_freelancer_already_liked_score_higher_than_gigs_only_their_group_liked(self):
        scores = collab.score(self.model, 'A', self.all_gigs)
        self.assertGreater(scores['g1'], scores['g3'])

    def test_a_freelancer_with_no_history_has_no_collaborative_score(self):
        scores = collab.score(self.model, 'nobody', self.all_gigs)
        self.assertEqual(scores, {gig: None for gig in self.all_gigs})

    def test_a_gig_nobody_has_interacted_with_is_absent_not_zero(self):
        scores = collab.score(self.model, 'A', ['g1', 'brand-new-gig'])
        self.assertIsNotNone(scores['g1'])
        self.assertIsNone(scores['brand-new-gig'])

    def test_fitting_twice_gives_the_same_scores(self):
        again = collab.fit(TWO_GROUPS, n_components=2)
        first = collab.score(self.model, 'A', self.all_gigs)
        second = collab.score(again, 'A', self.all_gigs)
        for gig in self.all_gigs:
            self.assertAlmostEqual(first[gig], second[gig], places=9)

    def test_the_model_reports_how_much_the_factors_explain(self):
        self.assertEqual(self.model.n_components, 2)
        self.assertGreater(self.model.explained_variance, 0.5)
        self.assertLessEqual(self.model.explained_variance, 1.0)
        self.assertEqual(self.model.n_interactions, len(TWO_GROUPS))

    def test_more_factors_than_the_data_has_are_cut_back_to_half_the_smaller_side(self):
        model = collab.fit(TWO_GROUPS, n_components=50)
        self.assertEqual(model.n_components, 3)  # a 6 by 6 matrix: half of 6

    def test_the_number_of_factors_defaults_to_the_setting(self):
        with override_settings(RECOMMENDER_SVD_COMPONENTS=3):
            self.assertEqual(collab.fit(TWO_GROUPS).n_components, 3)


class EdgeCaseTests(SimpleTestCase):
    def test_no_data_is_refused_with_the_reason(self):
        with self.assertRaises(collab.NotEnoughData) as raised:
            collab.fit({})
        self.assertIn('0 freelancers', str(raised.exception))

    def test_a_single_freelancer_is_refused_at_the_default_limits(self):
        with self.assertRaises(collab.NotEnoughData):
            collab.fit({('only', 'g1'): 3, ('only', 'g2'): 1})

    def test_a_single_gig_is_refused_at_the_default_limits(self):
        with self.assertRaises(collab.NotEnoughData):
            collab.fit({(f'u{n}', 'only-gig'): 3 for n in range(30)})

    @override_settings(**SMALL)
    def test_a_single_freelancer_is_refused_even_if_the_limits_are_lowered(self):
        # One freelancer has nobody to learn from.
        with self.assertRaises(collab.NotEnoughData):
            collab.fit({('only', 'g1'): 3, ('only', 'g2'): 1})

    @override_settings(**SMALL)
    def test_a_single_gig_is_refused_even_if_the_limits_are_lowered(self):
        # The SVD cannot run on a single column, so this must be a clean refusal and not a crash.
        with self.assertRaises(collab.NotEnoughData):
            collab.fit({('u1', 'only'): 3, ('u2', 'only'): 5})

    @override_settings(**SMALL)
    def test_two_freelancers_and_two_gigs_is_the_smallest_matrix_that_is_fitted(self):
        # u2 has not touched g2, so there is something to score for them.
        model = collab.fit({('u1', 'g1'): 3, ('u1', 'g2'): 1, ('u2', 'g1'): 5})
        scores = collab.score(model, 'u2', ['g1', 'g2'])
        self.assertTrue(all(value is not None and abs(value) < 100 for value in scores.values()))
        self.assertGreater(model.scale, 0)

    @override_settings(**SMALL)
    def test_when_everyone_has_touched_every_gig_there_is_nothing_to_recommend_and_it_says_so(self):
        everything = {('u1', 'g1'): 3, ('u1', 'g2'): 1, ('u2', 'g1'): 5, ('u2', 'g2'): 3}
        with self.assertRaises(collab.NotEnoughData) as raised:
            collab.fit(everything)
        self.assertIn('every gig', str(raised.exception))

    def test_the_fitted_model_keeps_the_scale_it_was_trained_with(self):
        with override_settings(**SMALL):
            model = collab.fit(TWO_GROUPS, n_components=2)
        self.assertGreater(model.scale, 0)
        # The scale is a high percentile of the untouched cells' scores, so it is near what A scored g3 (about 1.7).
        self.assertGreater(model.scale, 1.0)
        self.assertLess(model.scale, 3.0)

    def test_a_matrix_below_the_default_limits_is_refused(self):
        with self.assertRaises(collab.NotEnoughData):
            collab.fit(TWO_GROUPS)


class TooManyFactorsRegressionTests(SimpleTestCase):
    """
    A matrix just big enough for the real default limits (12 freelancers, 20 gigs, 108 pairs), in two groups
    that each viewed 9 of their own 10 gigs. This failed in CI once, because the model was allowed almost as
    many factors as the matrix has rows: it reproduced the data it was given, a gig a freelancer had not seen
    scored about zero, and the scores were numerical noise that happened to pass on one machine.
    """

    def setUp(self):
        # Group X's signal is stronger (2 against 1), so the two groups' strongest patterns differ and cannot
        # tie. Built identically, the SVD may return an arbitrary mix of them.
        self.weights = {}
        for group in 'PX':
            for position in range(6):
                for step in range(9):
                    self.weights[(f'{group}{position}', f'{group}gig{(position + step) % 10}')] = (
                        1 if group == 'P' else 2
                    )
        self.unseen_by_p0 = next(f'Pgig{n}' for n in range(10) if ('P0', f'Pgig{n}') not in self.weights)
        self.other_group = [f'Xgig{n}' for n in range(10)]

    def test_the_factors_are_capped_at_half_the_smaller_side_with_the_real_defaults(self):
        model = collab.fit(self.weights)
        self.assertEqual(model.n_components, 6)  # half of 12, although 20 are wanted

    # The two groups are built identically, so several of their small factors tie exactly, and which of them
    # the model keeps can differ between machines. The exact score for the gig the group viewed therefore
    # varies (about 0.5 to 0.8 here), so these check what the structure guarantees: clearly above zero for
    # that gig, and about zero for the other group's gigs, which share nothing with this freelancer.
    def test_a_gig_the_group_viewed_but_this_freelancer_did_not_scores_clearly_above_zero(self):
        model = collab.fit(self.weights)
        scores = collab.score(model, 'P0', [self.unseen_by_p0] + self.other_group)
        self.assertGreater(scores[self.unseen_by_p0], 0.2)
        for gig in self.other_group:
            self.assertLess(abs(scores[gig]), 0.1)

    def test_after_scaling_the_gap_is_wide_and_does_not_depend_on_noise(self):
        from . import hybrid

        model = collab.fit(self.weights)
        scores = collab.score(model, 'P0', [self.unseen_by_p0] + self.other_group)
        own = hybrid.normalise_collaborative(scores[self.unseen_by_p0], model.scale)
        others = [hybrid.normalise_collaborative(scores[gig], model.scale) for gig in self.other_group]
        self.assertGreater(own, 0.3)
        self.assertLess(max(others), 0.1)

    def test_with_nearly_as_many_factors_as_rows_the_scores_are_noise_which_is_why_the_cap_exists(self):
        # Not the default: this shows the problem the cap prevents, using the largest the old rule allowed.
        from sklearn.decomposition import TruncatedSVD

        matrix, users, gigs = collab.build_matrix(self.weights)
        svd = TruncatedSVD(n_components=11, random_state=42)
        factors = svd.fit_transform(matrix)
        unseen = float(factors[users['P0']] @ svd.components_[:, gigs[self.unseen_by_p0]])
        self.assertLess(abs(unseen), 0.1)  # the model has simply copied the data, gap included
