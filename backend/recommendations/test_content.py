import math

from django.test import SimpleTestCase

from . import content
from .features import freelancer_document

# A tiny corpus, already cleaned. Every number below is worked out by hand, not read from the code.
GIG_DJANGO = 'django python api'
GIG_PYTHON = 'python scraping script'
GIG_EXCEL = 'excel sheet report'
CORPUS = [GIG_DJANGO, GIG_PYTHON, GIG_EXCEL]


def fit_tiny(documents=CORPUS):
    # min_df=1 and max_df=1.0 because three documents are too few for the real defaults.
    return content.fit_vectoriser(documents, [], platform_share=0.3, min_df=1, max_df=1.0)


def hand_idf(documents, word):
    """The smoothed inverse document frequency scikit-learn documents: ln((1 + n) / (1 + df)) + 1."""
    n = len(documents)
    df = sum(1 for document in documents if word in document.split())
    return math.log((1 + n) / (1 + df)) + 1


def hand_cosine(documents, freelancer_text, gig_text):
    """TF-IDF with sublinear tf (1 + ln count), then the cosine of the two vectors."""
    def vector(text):
        counts = {}
        for word in text.split():
            counts[word] = counts.get(word, 0) + 1
        return {w: (1 + math.log(c)) * hand_idf(documents, w) for w, c in counts.items() if w in vocabulary}

    vocabulary = {word for document in documents for word in document.split()}
    a, b = vector(freelancer_text), vector(gig_text)
    dot = sum(a[w] * b.get(w, 0) for w in a)
    return dot / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))


class CosineScoreTests(SimpleTestCase):
    def setUp(self):
        self.vectoriser = fit_tiny()
        # A freelancer with the skills Django and Python.
        self.freelancer = freelancer_document(['Django', 'Python'])

    def scores(self, gig_texts):
        return content.cosine_scores(self.vectoriser, self.freelancer, gig_texts)

    def test_the_ranking_is_the_one_worked_out_by_hand(self):
        # Shares Django and Python, then shares only Python, then shares nothing.
        scores = self.scores([GIG_DJANGO, GIG_PYTHON, GIG_EXCEL])
        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[1], scores[2])

    def test_scores_match_the_hand_calculation(self):
        scores = self.scores([GIG_DJANGO, GIG_PYTHON])
        self.assertAlmostEqual(scores[0], hand_cosine(CORPUS, self.freelancer, GIG_DJANGO), places=6)
        self.assertAlmostEqual(scores[1], hand_cosine(CORPUS, self.freelancer, GIG_PYTHON), places=6)
        # For reference, the hand arithmetic gives about 0.78 and 0.29.
        self.assertAlmostEqual(scores[0], 0.7825, places=3)
        self.assertAlmostEqual(scores[1], 0.2868, places=3)

    def test_a_gig_with_nothing_in_common_scores_exactly_zero(self):
        self.assertEqual(self.scores([GIG_EXCEL])[0], 0.0)

    def test_the_same_words_in_the_same_proportions_score_one(self):
        # The freelancer repeats each skill three times, the gig lists each once: same direction.
        self.assertAlmostEqual(self.scores(['django python'])[0], 1.0, places=6)

    def test_a_gigs_score_does_not_depend_on_the_other_gigs_scored_with_it(self):
        alone = self.scores([GIG_PYTHON])[0]
        in_a_batch = self.scores([GIG_EXCEL, GIG_DJANGO, GIG_PYTHON])[2]
        self.assertAlmostEqual(alone, in_a_batch, places=9)

    def test_scores_stay_between_zero_and_one(self):
        for score in self.scores([GIG_DJANGO, GIG_PYTHON, GIG_EXCEL, 'django', 'unknown words only']):
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_words_the_vectoriser_has_never_seen_are_ignored(self):
        self.assertEqual(self.scores(['zzzz qqqq'])[0], 0.0)

    def test_no_gigs_gives_no_scores(self):
        self.assertEqual(len(self.scores([])), 0)

    def test_a_rarer_shared_word_counts_for_more_than_a_common_one(self):
        # "api" is in one document and "python" in two, so sharing "api" is worth more.
        rare = content.cosine_scores(self.vectoriser, 'api', [GIG_DJANGO])[0]
        common = content.cosine_scores(self.vectoriser, 'python', [GIG_DJANGO])[0]
        self.assertGreater(rare, common)


class MatchReasonTests(SimpleTestCase):
    def test_only_skills_on_both_lists_are_returned(self):
        reasons = content.match_reasons(['Django', 'PostgreSQL'], ['PostgreSQL', 'Django', 'Redis'])
        self.assertEqual(reasons, ['Django', 'PostgreSQL'])

    def test_case_and_spacing_do_not_matter_and_the_gigs_spelling_is_used(self):
        self.assertEqual(content.match_reasons(['machine  learning'], ['Machine Learning']), ['Machine Learning'])

    def test_no_shared_skill_gives_no_reason(self):
        self.assertEqual(content.match_reasons(['Django'], ['Excel']), [])

    def test_a_freelancer_with_no_skills_gives_no_reason(self):
        self.assertEqual(content.match_reasons([], ['Excel']), [])

    def test_punctuation_does_not_make_different_skills_the_same(self):
        self.assertEqual(content.match_reasons(['C'], ['C++', 'C#']), [])


class RepeatToShareTests(SimpleTestCase):
    def test_repeats_platform_documents_until_they_are_the_wanted_share(self):
        repeated = content.repeat_to_share(['p'] * 10, external_count=70, share=0.3)
        # Wanted: 0.3 / 0.7 * 70 = 30 documents, which is 10 documents three times over.
        self.assertEqual(len(repeated), 30)
        self.assertAlmostEqual(len(repeated) / (len(repeated) + 70), 0.3)

    def test_with_no_external_documents_nothing_is_repeated(self):
        self.assertEqual(content.repeat_to_share(['a', 'b'], external_count=0, share=0.3), ['a', 'b'])

    def test_a_share_of_zero_means_no_repeating(self):
        self.assertEqual(content.repeat_to_share(['a', 'b'], external_count=100, share=0), ['a', 'b'])

    def test_a_share_of_one_is_refused(self):
        with self.assertRaises(ValueError):
            content.repeat_to_share(['a'], external_count=10, share=1)

    def test_no_platform_documents_gives_nothing(self):
        self.assertEqual(content.repeat_to_share([], external_count=10, share=0.3), [])

    def test_at_least_one_copy_is_always_kept(self):
        self.assertEqual(len(content.repeat_to_share(['a'] * 100, external_count=1, share=0.3)), 100)


class FitVectoriserTests(SimpleTestCase):
    def test_platform_words_survive_a_much_bigger_external_corpus(self):
        external = ['alpha beta gamma'] * 100
        platform = ['django python', 'excel report']
        weighted = content.fit_vectoriser(platform, external, platform_share=0.3, min_df=3, max_df=1.0)
        self.assertIn('django', weighted.vocabulary_)
        # Without the repeating, "django" is in one document and falls below min_df.
        unweighted = content.fit_vectoriser(platform, external, platform_share=0, min_df=3, max_df=1.0)
        self.assertNotIn('django', unweighted.vocabulary_)

    def test_a_skill_token_stays_one_word(self):
        vectoriser = fit_tiny(['machine_learning python', 'machine_learning excel'])
        self.assertIn('machine_learning', vectoriser.vocabulary_)
        self.assertNotIn('machine', vectoriser.vocabulary_)

    def test_nothing_to_fit_on_is_an_error(self):
        with self.assertRaises(ValueError):
            content.fit_vectoriser([], [])

    def test_the_settings_give_the_defaults(self):
        with self.settings(RECOMMENDER_TFIDF_MIN_DF=2, RECOMMENDER_TFIDF_MAX_DF=1.0, RECOMMENDER_PLATFORM_SHARE=0.5):
            vectoriser = content.fit_vectoriser(['one two', 'one three'])
        self.assertEqual(set(vectoriser.vocabulary_), {'one'})
