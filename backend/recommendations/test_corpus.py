import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from . import corpus

UPWORK_COLUMNS = ['Job Title', 'Description', 'Search_Keyword'] + [f'Category_{n}' for n in range(1, 10)]


def write_csv(path, columns, rows, encoding='utf-8'):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding=encoding) as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def upwork_row(title, description, keyword, *skills):
    return [title, description, keyword, *skills, *[''] * (9 - len(skills))]


def make_data_dir(root):
    """A folder laid out like datasets/, holding tiny files with the same columns as the real ones."""
    raw = Path(root) / 'raw'
    # The real Upwork file starts with a hidden byte-order mark, so write the fake one the same way.
    write_csv(raw / 'upwork-freelance-jobs-60k/Final_Upwork_Dataset.csv', UPWORK_COLUMNS, [
        upwork_row('Django API builder', 'Build REST endpoints for invoices', 'Web', 'Django', 'Python'),
        upwork_row('Django API builder', 'Build REST endpoints for invoices', 'Web', 'Django', 'Python'),
        upwork_row('', 'ok', 'Web'),
        upwork_row('Excel dashboard', 'Create a monthly sales dashboard', 'Data', 'Microsoft Excel'),
    ], encoding='utf-8-sig')
    write_csv(raw / 'linkedin-job-postings/postings.csv', ['job_id', 'title', 'description', 'work_type'], [
        ['1', 'Senior accountant', 'Prepare monthly financial statements for the board', 'FULL_TIME'],
        ['2', 'Logo designer', 'Design a modern logo for a small bakery', 'CONTRACT'],
        ['3', 'Weekend barista', 'Prepare espresso drinks for weekend customers', 'PART_TIME'],
        ['4', 'Payroll manager', 'Run payroll for two hundred employees', 'FULL_TIME'],
    ])
    write_csv(raw / 'freelancer-data-analysis-jobs/freelancer_job_postings.csv',
              ['projectId', 'job_title', 'job_description', 'tags'], [
        ['10', 'Data entry', 'Enter survey results into a spreadsheet', "['excel', 'data entry']"],
        ['11', 'SQL report', 'Write a weekly sales report query', 'sql, reporting'],
    ])
    return Path(root)


def run(*args, data_dir):
    out = StringIO()
    call_command('import_job_corpus', *args, '--data-dir', str(data_dir), stdout=out)
    return out.getvalue()


def read_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


class ReaderTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = make_data_dir(self.tmp.name)

    def build(self, name, **kwargs):
        path = self.data_dir / corpus.SOURCE_FILES[name]
        return corpus.build_source(name, path, kwargs.get('max_rows'), kwargs.get('seed', 42))

    def test_upwork_reads_the_title_despite_the_hidden_mark_and_takes_skills_from_the_category_columns(self):
        records, _ = self.build('upwork')
        first = records[0]
        self.assertEqual(first['title'], 'Django API builder')
        self.assertEqual(first['skills_text'], 'django python')
        self.assertIn('django', first['clean_text'].split())
        self.assertEqual(records[1]['skills_text'], 'microsoft_excel')

    def test_empty_and_duplicate_rows_are_dropped_and_counted(self):
        records, stats = self.build('upwork')
        self.assertEqual((stats['rows_read'], stats['empty'], stats['duplicate'], stats['kept']), (4, 1, 1, 2))
        self.assertEqual(len(records), 2)

    def test_linkedin_full_time_postings_are_left_out(self):
        records, stats = self.build('linkedin')
        self.assertEqual({r['title'] for r in records}, {'Logo designer', 'Weekend barista'})
        self.assertEqual(stats['excluded_full_time'], 2)
        self.assertEqual(stats['rows_read'], 4)
        self.assertEqual(stats['breakdown']['work_type']['FULL_TIME'], 2)

    def test_linkedin_has_no_skill_tokens_but_keeps_the_job_text(self):
        records, _ = self.build('linkedin')
        self.assertEqual({r['skills_text'] for r in records}, {''})
        self.assertIn('bakery', records[0]['clean_text'].split())

    def test_freelancer_tags_are_read_as_a_list_or_as_plain_text(self):
        records, _ = self.build('freelancer')
        self.assertEqual(records[0]['skills_text'], 'excel data_entry')
        self.assertEqual(records[1]['skills_text'], 'sql reporting')

    def test_rows_over_the_cap_are_sampled_the_same_way_every_time(self):
        first, stats = self.build('linkedin', max_rows=1, seed=7)
        second, _ = self.build('linkedin', max_rows=1, seed=7)
        self.assertEqual(len(first), 1)
        self.assertEqual(first, second)
        self.assertEqual((stats['unique_before_cap'], stats['kept']), (2, 1))

    def test_a_cap_larger_than_the_data_keeps_everything(self):
        records, _ = self.build('linkedin', max_rows=100)
        self.assertEqual(len(records), 2)

    def test_real_column_names_can_be_read(self):
        path = self.data_dir / corpus.SOURCE_FILES['linkedin']
        self.assertEqual(corpus.read_columns(path), ['job_id', 'title', 'description', 'work_type'])


class VocabularyTests(SimpleTestCase):
    def test_top_terms_count_every_use(self):
        records = [{'clean_text': 'alpha beta alpha'}, {'clean_text': 'alpha gamma'}]
        self.assertEqual(corpus.top_terms(records, 2), [('alpha', 3), ('beta', 1)])

    def test_vocabulary_counts_documents_not_uses(self):
        records = [{'clean_text': 'alpha beta alpha'}, {'clean_text': 'alpha gamma'}]
        self.assertEqual(dict(corpus.vocabulary(records)), {'alpha': 2, 'beta': 1, 'gamma': 1})

    def test_overlap_is_zero_for_nothing_in_common_and_one_for_the_same(self):
        same = corpus.vocabulary([{'clean_text': 'alpha beta'}])
        other = corpus.vocabulary([{'clean_text': 'gamma delta'}])
        self.assertEqual(corpus.term_overlap(same, same), 1.0)
        self.assertEqual(corpus.term_overlap(same, other), 0.0)
        self.assertEqual(corpus.term_overlap(corpus.vocabulary([]), corpus.vocabulary([])), 0.0)


class ImportCommandTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = make_data_dir(self.tmp.name)

    def test_writes_one_processed_file_per_source_and_a_combined_one(self):
        run(data_dir=self.data_dir)
        processed = self.data_dir / 'processed'
        self.assertEqual(len(read_rows(processed / 'upwork_corpus.csv')), 2)
        self.assertEqual(len(read_rows(processed / 'linkedin_corpus.csv')), 2)
        combined = read_rows(processed / 'combined_corpus.csv')
        self.assertEqual(len(combined), 4)
        self.assertEqual({row['source'] for row in combined}, {'upwork', 'linkedin'})
        self.assertEqual(list(combined[0]), corpus.CORPUS_COLUMNS)

    def test_freelancer_com_is_left_out_unless_asked_for(self):
        run(data_dir=self.data_dir)
        self.assertFalse((self.data_dir / 'processed' / 'freelancer_corpus.csv').exists())
        run('--sources', 'freelancer', data_dir=self.data_dir)
        self.assertEqual(len(read_rows(self.data_dir / 'processed' / 'freelancer_corpus.csv')), 2)

    def test_writes_samples_of_raw_and_processed_files(self):
        run(data_dir=self.data_dir)
        samples = self.data_dir / 'samples'
        for name in ('Final_Upwork_Dataset.sample.csv', 'postings.sample.csv', 'upwork_corpus.sample.csv',
                     'linkedin_corpus.sample.csv', 'combined_corpus.sample.csv'):
            self.assertTrue((samples / name).exists(), name)

    def test_a_sample_is_the_header_and_at_most_200_rows(self):
        big = self.data_dir / 'raw/linkedin-job-postings/postings.csv'
        rows = [
            [str(n), f'Contract role {n}', f'Describe task number {n} for a client', 'CONTRACT']
            for n in range(500)
        ]
        write_csv(big, ['job_id', 'title', 'description', 'work_type'], rows)
        run('--sources', 'linkedin', data_dir=self.data_dir)
        sample = (self.data_dir / 'samples' / 'postings.sample.csv').read_text(encoding='utf-8-sig').splitlines()
        self.assertEqual(len(sample), 201)

    def test_writes_a_report_with_the_measured_numbers(self):
        run(data_dir=self.data_dir)
        reports = list((self.data_dir / 'reports').glob('import-*.md'))
        self.assertEqual(len(reports), 1)
        text = reports[0].read_text(encoding='utf-8')
        # rows read, left out, empty, duplicate, unique, row cap (the setting's default), kept
        self.assertIn('| linkedin | 4 | 2 | 0 | 0 | 2 | 15000 | 2 |', text)
        self.assertIn('| upwork | 4 | 0 | 1 | 1 | 2 | 15000 | 2 |', text)
        self.assertIn('FULL_TIME 2', text)
        self.assertIn('How alike the sources are', text)
        self.assertNotIn('—', text)

    def test_the_max_rows_option_caps_every_source(self):
        run('--max-rows', '1', data_dir=self.data_dir)
        self.assertEqual(len(read_rows(self.data_dir / 'processed' / 'combined_corpus.csv')), 2)

    def test_a_missing_file_is_named_in_the_error(self):
        (self.data_dir / corpus.SOURCE_FILES['linkedin']).unlink()
        with self.assertRaises(CommandError) as raised:
            run(data_dir=self.data_dir)
        self.assertIn('postings.csv', str(raised.exception))

    def test_an_unknown_source_is_refused(self):
        with self.assertRaises(CommandError):
            run('--sources', 'nonsense', data_dir=self.data_dir)

    def test_processed_texts_can_be_read_back(self):
        run(data_dir=self.data_dir)
        texts = corpus.read_processed_texts(self.data_dir / 'processed' / 'combined_corpus.csv')
        self.assertEqual(len(texts), 4)
        self.assertTrue(all(text for text in texts))
