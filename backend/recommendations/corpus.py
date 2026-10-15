"""
Reading the external job-posting datasets (Kaggle) into the same document shape as GigConnect gigs.

These postings are used only to fit the TF-IDF vocabulary and word weights for the content-based model,
so it knows how skill and job words relate before GigConnect has many gigs of its own. They are never
shown to users as gigs and never go into the collaborative model.

Each reader streams its file row by row, so the 517 MB LinkedIn file is never held in memory. Column
names were checked against the real files, not assumed from the dataset pages.
"""

import ast
import csv
import random
from collections import Counter
from pathlib import Path

from .features import drop_empty_and_duplicates, gig_document, skill_tokens

csv.field_size_limit(10**9)

# How much of the original description is kept in the processed CSV, so the file stays easy to open.
DESCRIPTION_PREVIEW_CHARS = 1000

CORPUS_COLUMNS = ['source', 'source_id', 'title', 'description', 'skills_text', 'clean_text']

# Where each source's main file lives under datasets/raw/. The Upwork download also contains LinkedIn
# company tables (companies.csv and others). They hold no job text and are ignored.
SOURCE_FILES = {
    'upwork': Path('raw/upwork-freelance-jobs-60k/Final_Upwork_Dataset.csv'),
    'linkedin': Path('raw/linkedin-job-postings/postings.csv'),
    'freelancer': Path('raw/freelancer-data-analysis-jobs/freelancer_job_postings.csv'),
}

# LinkedIn full-time postings are left out: they are ordinary employment, not gig-style work. Everything
# else (contract, part-time, temporary, internship, volunteer, other) is kept.
EXCLUDED_LINKEDIN_WORK_TYPES = {'FULL_TIME'}

UPWORK_SKILL_COLUMNS = [f'Category_{n}' for n in range(1, 10)]


def _open_csv(path):
    # utf-8-sig drops the hidden byte-order mark that the Upwork file starts with.
    return open(path, newline='', encoding='utf-8-sig', errors='replace')


def read_columns(path):
    """The real column names in a CSV file, as they are in the file."""
    with _open_csv(path) as handle:
        return next(csv.reader(handle))


def _preview(text):
    return ' '.join((text or '').split())[:DESCRIPTION_PREVIEW_CHARS]


def read_upwork(path, stats):
    """Upwork jobs. The skill tags are the Category_1 to Category_9 columns."""
    with _open_csv(path) as handle:
        for number, row in enumerate(csv.DictReader(handle), start=1):
            stats['rows_read'] += 1
            stats['breakdown']['search_keyword'][row.get('Search_Keyword') or '(blank)'] += 1
            skills = [row.get(column, '').strip() for column in UPWORK_SKILL_COLUMNS]
            yield {
                'source_id': f'upwork-{number}',
                'title': row.get('Job Title', ''),
                'description': row.get('Description', ''),
                'skill_names': [skill for skill in skills if skill],
            }


def read_linkedin(path, stats):
    """LinkedIn postings, leaving out full-time ones. There is no clean skills column, so no skill tokens."""
    with _open_csv(path) as handle:
        for row in csv.DictReader(handle):
            stats['rows_read'] += 1
            work_type = row.get('work_type') or '(blank)'
            stats['breakdown']['work_type'][work_type] += 1
            if work_type in EXCLUDED_LINKEDIN_WORK_TYPES:
                stats['excluded_full_time'] += 1
                continue
            yield {
                'source_id': row.get('job_id', ''),
                'title': row.get('title', ''),
                'description': row.get('description', ''),
                'skill_names': [],
            }


def _parse_tags(value):
    """The Freelancer.com tags column is a list written as text, such as "['sql', 'excel']"."""
    try:
        parsed = ast.literal_eval(value or '[]')
        if isinstance(parsed, (list, tuple)):
            return [str(tag).strip() for tag in parsed if str(tag).strip()]
    except (ValueError, SyntaxError):
        pass
    return [part.strip(" '\"[]") for part in (value or '').split(',') if part.strip(" '\"[]")]


def read_freelancer(path, stats):
    """Freelancer.com data-analysis jobs, with the tags column as skills."""
    with _open_csv(path) as handle:
        for row in csv.DictReader(handle):
            stats['rows_read'] += 1
            yield {
                'source_id': row.get('projectId', ''),
                'title': row.get('job_title', ''),
                'description': row.get('job_description', ''),
                'skill_names': _parse_tags(row.get('tags')),
            }


READERS = {'upwork': read_upwork, 'linkedin': read_linkedin, 'freelancer': read_freelancer}


def new_stats():
    return {
        'rows_read': 0,
        'excluded_full_time': 0,
        'empty': 0,
        'duplicate': 0,
        'unique_before_cap': 0,
        'kept': 0,
        'breakdown': {'search_keyword': Counter(), 'work_type': Counter()},
    }


def build_source(name, path, max_rows, seed):
    """
    Read one source and return (records, stats).

    Rows are cleaned, empty and duplicate documents are dropped, and if more than max_rows remain a
    random sample of max_rows is kept. The sample is seeded, so a rerun gives the same rows.
    """
    stats = new_stats()
    candidates = []
    for raw in READERS[name](path, stats):
        document = gig_document(raw['title'], raw['description'], raw['skill_names'])
        candidates.append({
            'source': name,
            'source_id': raw['source_id'],
            'title': ' '.join(raw['title'].split()),
            'description': _preview(raw['description']),
            'skills_text': skill_tokens(raw['skill_names']),
            'clean_text': document,
        })
    records, dropped = drop_empty_and_duplicates(candidates)
    stats['empty'] = dropped['empty']
    stats['duplicate'] = dropped['duplicate']
    stats['unique_before_cap'] = len(records)

    if max_rows is not None and len(records) > max_rows:
        chosen = sorted(random.Random(seed).sample(range(len(records)), max_rows))
        records = [records[index] for index in chosen]
    stats['kept'] = len(records)
    return records, stats


def top_terms(records, count=30):
    """The most common words across a source's cleaned documents."""
    counter = Counter()
    for record in records:
        counter.update(record['clean_text'].split())
    return counter.most_common(count)


def vocabulary(records):
    """Every distinct word in a set of cleaned documents, with how many documents use it."""
    counter = Counter()
    for record in records:
        counter.update(set(record['clean_text'].split()))
    return counter


def term_overlap(first, second, size=1000):
    """How alike two sources' vocabularies are: the overlap of their most common words, from 0 to 1."""
    top_first = {term for term, _ in first.most_common(size)}
    top_second = {term for term, _ in second.most_common(size)}
    if not top_first and not top_second:
        return 0.0
    return len(top_first & top_second) / len(top_first | top_second)


def read_processed_texts(path):
    """The clean_text of every row in a processed corpus CSV, for fitting the vectoriser."""
    with _open_csv(path) as handle:
        return [row['clean_text'] for row in csv.DictReader(handle)]


def write_csv(path, rows, columns):
    """Write rows as UTF-8 with a header. The byte-order mark lets Excel open it correctly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def write_sample(source_path, sample_path, rows=200):
    """Copy the first rows of a CSV, for looking at a file too big to open."""
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    with _open_csv(source_path) as source, open(sample_path, 'w', newline='', encoding='utf-8-sig') as target:
        reader = csv.reader(source)
        writer = csv.writer(target)
        for index, row in enumerate(reader):
            if index > rows:  # the header plus the first `rows` data rows
                break
            writer.writerow(row)
