"""Print EXPLAIN (ANALYZE, BUFFERS) for the gig list queries, as the API runs them.

Run from the backend folder, against the database named by the DB_* environment variables:

    python scripts/explain_gig_queries.py

Each query is built through the same code the API uses (GigFilterSerializer, apply_gig_filters and
the list view's base queryset), then sliced to the first page (LIMIT 12). The COUNT(*) the
paginator also runs is explained separately where it is a meaningful cost.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from gigs.filters import GigFilterSerializer, apply_gig_filters  # noqa: E402
from gigs.models import Category, Gig  # noqa: E402
from gigs.views import GigListCreateView  # noqa: E402


def build_queries():
    category_slug = Category.objects.order_by('name').first().slug
    return {
        'base feed': {},
        'q search': {'q': 'bakery'},
        'q + filters': {
            'q': 'bakery', 'category': category_slug, 'budget_min': '10000', 'budget_max': '30000',
            'county': 'Nairobi', 'sort': 'relevance',
        },
        'skills ALL': {'skills': 'Plumbing,Electrical Work', 'skills_mode': 'all'},
        'trigram fallback (typo)': {'q': 'bakry', 'sort': 'relevance'},
    }


def explain(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute('EXPLAIN (ANALYZE, BUFFERS) ' + sql, params)
        return '\n'.join(row[0] for row in cursor.fetchall())


def main():
    print(f'Gigs in table: {Gig.objects.count()}')
    with connection.cursor() as cursor:
        cursor.execute('SHOW server_version')
        print(f'PostgreSQL {cursor.fetchone()[0]}')

    for name, params in build_queries().items():
        serializer = GigFilterSerializer(data=params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        queryset = apply_gig_filters(
            GigListCreateView().get_queryset(include_closed=bool(data.get('include_closed'))), data
        )

        page_sql, page_params = queryset[:12].query.sql_with_params()
        print(f'\n===== {name}: page query (LIMIT 12) =====')
        print(f'params: {params}')
        print(explain(page_sql, page_params))

        with CaptureQueriesContext(connection) as captured:
            count = queryset.count()
        print(f'\n===== {name}: COUNT query ({count} matching) =====')
        print(explain(captured.captured_queries[-1]['sql']))


if __name__ == '__main__':
    main()
