from django.test import SimpleTestCase

from .features import (
    clean_text,
    drop_empty_and_duplicates,
    freelancer_document,
    gig_document,
    skill_token,
    skill_tokens,
)


class CleanTextTests(SimpleTestCase):
    def test_lowercases_and_removes_stop_words(self):
        self.assertEqual(clean_text('The Django dashboard and the Excel invoice'), 'django dashboard excel invoice')

    def test_removes_html_web_addresses_and_emails(self):
        text = '<p>Visit https://example.com or www.example.org, email me@example.com for Django</p>'
        self.assertEqual(clean_text(text), 'visit email django')

    def test_removes_numbers_but_keeps_words_that_contain_digits(self):
        self.assertEqual(clean_text('Django 5 and 2024 s3'), 'django s3')

    def test_removes_single_letters(self):
        self.assertEqual(clean_text('R and C'), '')

    def test_punctuation_splits_words(self):
        self.assertEqual(clean_text('django,postgresql;redis'), 'django postgresql redis')

    def test_empty_and_missing_text_give_an_empty_string(self):
        self.assertEqual(clean_text(''), '')
        self.assertEqual(clean_text(None), '')


class SkillTokenTests(SimpleTestCase):
    def test_a_multi_word_skill_stays_together(self):
        self.assertEqual(skill_token('Machine Learning'), 'machine_learning')

    def test_case_and_surrounding_space_do_not_matter(self):
        self.assertEqual(skill_token('  React  '), 'react')
        self.assertEqual(skill_token('REACT'), skill_token('react'))

    def test_punctuation_that_carries_meaning_is_kept_apart(self):
        self.assertEqual(skill_token('C++'), 'cplusplus')
        self.assertEqual(skill_token('C#'), 'csharp')
        self.assertEqual(skill_token('.NET'), 'dotnet')
        self.assertEqual(skill_token('Node.js'), 'node_js')
        self.assertEqual(len({skill_token('C'), skill_token('C++'), skill_token('C#')}), 3)

    def test_an_ampersand_becomes_and(self):
        self.assertEqual(skill_token('Data & Analytics'), 'data_and_analytics')

    def test_nothing_gives_an_empty_token(self):
        self.assertEqual(skill_token(''), '')
        self.assertEqual(skill_token(None), '')

    def test_tokens_have_no_repeats_and_keep_order(self):
        self.assertEqual(skill_tokens(['Django', 'django', '  ', None, 'Machine Learning']), 'django machine_learning')


class DocumentTests(SimpleTestCase):
    def test_gig_document_joins_title_description_category_and_skills(self):
        document = gig_document(
            'Logo for a cafe', '<b>Design</b> a modern logo', ['Graphic Design'], 'Design & Branding',
        )
        self.assertEqual(document, 'logo cafe design modern logo design branding graphic_design')

    def test_gig_document_skips_empty_parts(self):
        self.assertEqual(gig_document('Invoice dashboard', '', [], ''), 'invoice dashboard')

    def test_freelancer_document_repeats_skills_three_times_then_adds_the_bio(self):
        document = freelancer_document(['Django', 'Python'], 'I build APIs')
        self.assertEqual(document, 'django python django python django python build apis')

    def test_freelancer_document_with_no_skills_is_just_the_bio(self):
        self.assertEqual(freelancer_document([], 'Invoice dashboard builder'), 'invoice dashboard builder')

    def test_freelancer_document_with_nothing_is_empty(self):
        self.assertEqual(freelancer_document([], ''), '')


class DropEmptyAndDuplicatesTests(SimpleTestCase):
    def test_keeps_the_first_of_each_and_counts_what_was_dropped(self):
        records = [
            {'id': 1, 'clean_text': 'alpha beta gamma'},
            {'id': 2, 'clean_text': 'alpha beta gamma'},
            {'id': 3, 'clean_text': 'too short'},
            {'id': 4, 'clean_text': 'delta epsilon zeta'},
            {'id': 5, 'clean_text': ''},
        ]
        kept, dropped = drop_empty_and_duplicates(records)
        self.assertEqual([r['id'] for r in kept], [1, 4])
        self.assertEqual(dropped, {'empty': 2, 'duplicate': 1})

    def test_the_minimum_word_count_can_be_changed(self):
        kept, dropped = drop_empty_and_duplicates([{'clean_text': 'two words'}], min_words=2)
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, {'empty': 0, 'duplicate': 0})

    def test_works_on_another_key(self):
        kept, _ = drop_empty_and_duplicates([{'text': 'one two three'}], key='text')
        self.assertEqual(len(kept), 1)
