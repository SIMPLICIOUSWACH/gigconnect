from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ... import corpus

DEFAULT_SOURCES = ['upwork', 'linkedin']
REPORT_TERMS = 30


def _join(pairs):
    return ', '.join(f'{key} {count}' for key, count in pairs)


class Command(BaseCommand):
    help = (
        'Read the Kaggle job-posting datasets in datasets/raw/, clean them into the same document shape '
        'as GigConnect gigs, and write the corpus used to fit the content model. Writes CSV files to '
        'datasets/processed/, previews to datasets/samples/ and a report to datasets/reports/. '
        'LinkedIn full-time postings are left out.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--sources', default=','.join(DEFAULT_SOURCES),
            help='Comma-separated: upwork, linkedin, freelancer (default: upwork,linkedin). Freelancer.com '
                 'is data-analysis only and can skew the vocabulary, so it is off unless asked for.',
        )
        parser.add_argument(
            '--max-rows', type=int,
            help='Cap rows per source, instead of the RECOMMENDER_CORPUS_MAX_ROWS setting.',
        )
        parser.add_argument(
            '--seed', type=int, default=42,
            help='Seed for the random sample when a source is capped (default 42).',
        )
        parser.add_argument('--data-dir', help='Use this folder instead of the RECOMMENDER_DATA_DIR setting.')

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'] or settings.RECOMMENDER_DATA_DIR)
        sources = self._sources(options['sources'])
        self._check_files(data_dir, sources)

        results = {}
        for name in sources:
            path = data_dir / corpus.SOURCE_FILES[name]
            cap = options['max_rows'] or settings.RECOMMENDER_CORPUS_MAX_ROWS.get(name)
            self.stdout.write(f'Reading {name} ({path.name}) ...')
            columns = corpus.read_columns(path)
            records, stats = corpus.build_source(name, path, cap, options['seed'])
            results[name] = {'path': path, 'columns': columns, 'records': records, 'stats': stats, 'cap': cap}
            corpus.write_csv(data_dir / 'processed' / f'{name}_corpus.csv', records, corpus.CORPUS_COLUMNS)
            corpus.write_sample(path, data_dir / 'samples' / f'{path.stem}.sample.csv')
            self.stdout.write(f'  kept {stats["kept"]} of {stats["rows_read"]} rows')

        combined = [record for result in results.values() for record in result['records']]
        processed = data_dir / 'processed'
        corpus.write_csv(processed / 'combined_corpus.csv', combined, corpus.CORPUS_COLUMNS)
        for name in [*results, 'combined']:
            corpus.write_sample(processed / f'{name}_corpus.csv', data_dir / 'samples' / f'{name}_corpus.sample.csv')

        report_path = data_dir / 'reports' / f'import-{date.today().isoformat()}.md'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(self._report(results, combined, options['seed']), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Wrote {len(combined)} documents to {processed}.'))
        self.stdout.write(f'Report: {report_path}')

    def _sources(self, text):
        sources = [name.strip() for name in text.split(',') if name.strip()]
        unknown = [name for name in sources if name not in corpus.SOURCE_FILES]
        if unknown or not sources:
            raise CommandError(
                f'Unknown source(s): {", ".join(unknown) or "none given"}. '
                f'Choose from: {", ".join(corpus.SOURCE_FILES)}.'
            )
        return sources

    def _check_files(self, data_dir, sources):
        missing = [
            str(data_dir / corpus.SOURCE_FILES[name]) for name in sources
            if not (data_dir / corpus.SOURCE_FILES[name]).is_file()
        ]
        if missing:
            listing = '\n  '.join(missing)
            raise CommandError(f'These files are missing. Download them (see datasets/README.md):\n  {listing}')

    def _report(self, results, combined, seed):
        lines = [
            f'# Corpus import, {date.today().isoformat()}',
            '',
            'Only measured numbers. The corpus is used to fit the content model vocabulary and is never '
            'shown to users as gigs.',
            '',
            f'- Sources: {", ".join(results)}',
            f'- Random seed: {seed}',
            f'- Documents written: {len(combined)}',
            f'- Distinct words across the combined corpus: {len(corpus.vocabulary(combined))}',
            '',
            '## Rows per source',
            '',
            '| Source | Rows read | Left out (LinkedIn full-time) | Dropped empty | Dropped duplicate '
            '| Unique | Row cap | Kept |',
            '|---|---|---|---|---|---|---|---|',
        ]
        for name, result in results.items():
            s = result['stats']
            cap = 'none' if result['cap'] is None else result['cap']
            lines.append(
                f'| {name} | {s["rows_read"]} | {s["excluded_full_time"]} | {s["empty"]} '
                f'| {s["duplicate"]} | {s["unique_before_cap"]} | {cap} | {s["kept"]} |'
            )

        vocabularies = {name: corpus.vocabulary(result['records']) for name, result in results.items()}
        for name, result in results.items():
            lines += self._source_section(name, result, len(vocabularies[name]))
        lines += self._overlap_section(vocabularies)
        return '\n'.join(lines) + '\n'

    def _source_section(self, name, result, vocabulary_size):
        breakdown = result['stats']['breakdown']
        columns = ', '.join(f'`{column}`' for column in result['columns'])
        lines = [
            '',
            f'## {name}',
            '',
            f'- File: `{result["path"].name}`',
            f'- Columns found ({len(result["columns"])}): {columns}',
            f'- Distinct words in the kept documents: {vocabulary_size}',
        ]
        if breakdown['work_type']:
            lines.append('- Rows read by `work_type`: ' + _join(breakdown['work_type'].most_common()))
        if breakdown['search_keyword']:
            lines.append('- Top search keywords among rows read: ' + _join(breakdown['search_keyword'].most_common(10)))
        top = corpus.top_terms(result['records'], REPORT_TERMS)
        lines += ['', f'Top {REPORT_TERMS} words in the kept documents:', '', ', '.join(f'{t} ({c})' for t, c in top)]
        return lines

    def _overlap_section(self, vocabularies):
        if len(vocabularies) < 2:
            return []
        lines = [
            '',
            '## How alike the sources are',
            '',
            "Overlap of each pair of sources' 1000 most common words (0 means nothing in common, 1 means identical):",
            '',
        ]
        names = list(vocabularies)
        for index, first in enumerate(names):
            for second in names[index + 1:]:
                overlap = corpus.term_overlap(vocabularies[first], vocabularies[second])
                lines.append(f'- {first} and {second}: {overlap:.2f}')
        return lines
