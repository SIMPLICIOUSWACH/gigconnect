"""Measure GET /api/gigs/ latency for the main query shapes and print a Markdown table.

    python scripts/measure_latency.py --base-url http://127.0.0.1:8000 --category-slug design-creative

Standard library only. Requests are sent one after another over a fresh connection each time, so
the numbers include connection setup and JSON serialisation, not just the database. Run it against
a server started with DEBUG off, otherwise Django records every SQL query in memory and the numbers
are pessimistic. Warm-up requests are sent first and not counted.
"""

import argparse
import json
import platform
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request


def queries(category_slug):
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


def fetch(url):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            body = json.load(response)
            ok = response.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None, None
    return (time.perf_counter() - started) * 1000, body.get('count') if ok else None


def percentile(sorted_values, fraction):
    index = min(len(sorted_values) - 1, max(0, round(fraction * len(sorted_values)) - 1))
    return sorted_values[index]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--category-slug', required=True)
    parser.add_argument('--requests', type=int, default=100)
    parser.add_argument('--warmup', type=int, default=5)
    args = parser.parse_args()

    print(f'Machine: {platform.platform()}, Python {platform.python_version()}')
    print(f'Requests per query: {args.requests} (after {args.warmup} warm-up), sequential\n')
    print('| Query | Matches | p50 ms | p95 ms | max ms | Failed |')
    print('|---|---|---|---|---|---|')

    for name, params in queries(args.category_slug).items():
        url = f'{args.base_url}/api/gigs/?{urllib.parse.urlencode(params)}'
        for _ in range(args.warmup):
            fetch(url)
        timings, failures, matches = [], 0, None
        for _ in range(args.requests):
            elapsed, count = fetch(url)
            if elapsed is None:
                failures += 1
            else:
                timings.append(elapsed)
                matches = count
        timings.sort()
        if timings:
            print(
                f'| {name} | {matches} | {statistics.median(timings):.0f} | '
                f'{percentile(timings, 0.95):.0f} | {timings[-1]:.0f} | {failures} |'
            )
        else:
            print(f'| {name} | n/a | n/a | n/a | n/a | {failures} |')


if __name__ == '__main__':
    main()
