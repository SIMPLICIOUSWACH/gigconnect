# Sprint 3 search performance

Measured on 2026-10-05 against the gig list and search API (`GET /api/gigs/`), after the Sprint 3.1
search changes. This file is evidence, not a promise: every number below came from the scripts in
this repository, and the plans are copied from their output.

## Summary

- Four of the five query shapes stay under 300 ms at the 95th percentile at both 10,000 and 50,000
  gigs. For the cheap shapes the database is a small part of that: the base feed's page query runs
  in under 10 ms, and the rest is Django, serialisation and the single-threaded development server.
- Two shapes were slow and are fixed in this PR: **skills ALL** (p50 370 ms to 174 ms at 50k) and
  the **typo fallback** (p50 1,651 ms to 680 ms at 50k).
- **The typo fallback is still over the 500 ms target at 50,000 gigs** (p50 680 ms, p95 795 ms). It
  only runs when full-text search finds fewer than 5 gigs. See "What is still slow".

## How this was measured

| | |
|---|---|
| Machine | AMD Ryzen 5 5625U (6 cores, 12 threads), 7.4 GB RAM, Windows 11 Home (build 26200) |
| Database | PostgreSQL 18.3 on the same machine, native install, separate database `gigconnect_perf` |
| Postgres settings | `shared_buffers` 160 MB, `work_mem` 4 MB, `max_parallel_workers_per_gather` 2, `random_page_cost` 4 (defaults) |
| Application | Django development server (`runserver --noreload`, single process, single thread), Python 3.12.6 |
| DEBUG | **Off** (`DEBUG=False`). With it on, Django keeps every SQL query in memory and the numbers are worse |
| Other settings | `SHOW_SYNTHETIC=True`, otherwise the feed would hide every perf gig |
| Client | `backend/scripts/measure_latency.py` on the same machine: 5 warm-up requests, then 100 timed requests per query, one after another, a fresh connection each time |
| Data | `perf_seed`, fixed random seed 42. Seeding took 1 min 14 s for 10,000 gigs and 4 min 40 s for 50,000 (most of it rebuilding search vectors) |

Because client, server and database share one laptop and the server handles one request at a time,
these are good for comparing before with after and one query shape with another. They are not a
forecast for production hardware.

The data is synthetic and its text is built from templates (30 business types, the 24 seeded
skills). Real descriptions would be more varied, which would make the trigram candidate sets
smaller than they are here.

To reproduce, with a database such as `gigconnect_perf` (names are examples):

1. `DB_NAME=gigconnect_perf python manage.py migrate`
2. `DB_NAME=gigconnect_perf python manage.py perf_seed --size 50000`
3. `DB_NAME=gigconnect_perf python scripts/explain_gig_queries.py`
4. Start the server with `DB_NAME=gigconnect_perf DEBUG=False SHOW_SYNTHETIC=True`, then
   `python scripts/measure_latency.py --category-slug design-creative`

The five query shapes:

| Name | Request |
|---|---|
| base feed | `/api/gigs/` |
| q search | `q=bakery` |
| q + filters | `q=bakery&category=<slug>&budget_min=10000&budget_max=30000&county=Nairobi&sort=relevance` |
| skills ALL | `skills=Plumbing,Electrical Work&skills_mode=all` |
| trigram fallback (typo) | `q=bakry&sort=relevance` (a typo of "bakery", so full-text search finds nothing) |

## API latency (milliseconds, 100 requests each)

The "q + filters" row uses `design-creative` for the latency runs. `explain_gig_queries.py` uses
the first category alphabetically, so its match counts for that row differ slightly.

### 10,000 gigs

| Query | Matches | Before p50 | Before p95 | After p50 | After p95 |
|---|---|---|---|---|---|
| base feed | 8,575 | 151 | 256 | 130 | 228 |
| q search | 294 | 141 | 197 | 123 | 158 |
| q + filters | 5 | 146 | 171 | 152 | 252 |
| skills ALL | 85 | 182 | 262 | 129 | 162 |
| trigram fallback (typo) | 294 | 680 | 839 | 268 | 368 |

### 50,000 gigs

| Query | Matches | Before p50 | Before p95 | After p50 | After p95 |
|---|---|---|---|---|---|
| base feed | 42,737 | 179 | 277 | 174 | 277 |
| q search | 1,485 | 144 | 193 | 146 | 252 |
| q + filters | 15 | 139 | 178 | 138 | 205 |
| skills ALL | 398 | 370 | 468 | 174 | 279 |
| trigram fallback (typo) | 1,485 | 1,651 | 1,785 | 680 | 795 |

"Before" is the code on `develop` plus the Sprint 3.1 PR2 changes. "After" adds the two fixes
described next. Rows for queries those fixes did not touch (base feed, q search, q + filters) are
the same code both times, so differences between their before and after columns, up to about 60 ms
at p95, are run-to-run noise on a laptop and give a sense of how much to trust the other rows.

## What was slow, and what changed

### skills ALL

Before, the page query joined `gigs_gigskill`, grouped and counted across the whole gig table. The
plan was a parallel sequential scan of `gigs_gig` (166 ms in `EXPLAIN` at 50k). Now the gigs that
have every requested skill are found through the `gigs_gigskill` index and only those are fetched,
which removes the sequential scan (30 ms in `EXPLAIN` at 50k). No index was added for this; the
existing foreign key index on `gigs_gigskill.skill_id` is the one used.

### trigram fallback (typo search)

Before, the fallback computed `word_similarity` against both title and description for every open
gig and compared the larger one to the threshold. At 50,000 gigs that was a parallel sequential
scan (717 ms for the page query and 763 ms for the count in `EXPLAIN`).

Now it asks Postgres with the `%>` operator, which the trigram GIN indexes can serve, and only
computes the similarity score for the rows that match. The operator's cut-off is a session setting
(`pg_trgm.word_similarity_threshold`), so it is set from `SEARCH_TRIGRAM_THRESHOLD` on the
connection just before the query is built. Two things were needed:

- A new GIN trigram index on `gigs_gig.title` (`gig_title_trgm_gin`, migration `0011`). The
  `description` column already had one. Added because the plan below uses it.
- `django.contrib.postgres` in `INSTALLED_APPS`, which is what registers the `%>` lookup in Django.

What the plans show:

- **At 50,000 gigs** the plan is a bitmap OR of `gig_search_vector_gin`, `gig_title_trgm_gin` and
  `gig_description_gin`. All three are used.
- **At 10,000 gigs** the planner still picks a parallel sequential scan, because the table is
  small. The improvement there (p50 680 ms to 268 ms) comes from the cheaper per-row `%>` test, not
  from an index. The index only starts to matter as the table grows.

### What is still slow

The typo fallback at 50,000 gigs is p50 680 ms and p95 795 ms, above the 500 ms target. In the plan
below the two trigram indexes hand back thousands of candidate rows (3,875 from the title index and
7,588 from the description index) that Postgres then rechecks against the heap, and the paginator's
count query does the same work again. That recheck is the remaining cost, and it is made worse by
this data's templated descriptions. Options, none applied yet:

1. Match only on title for the fuzzy part. Cheapest, but typos in a description would no longer be
   found.
2. Raise `SEARCH_TRIGRAM_THRESHOLD` back to pg_trgm's 0.3. Fewer candidates, but "pyhton" scores
   only about 0.27 to 0.29 against "python", so the most common typo would stop working.
3. Cap how many fuzzy candidates are considered.

The fallback only runs when full-text search finds fewer than 5 gigs, so most searches never pay
this cost. It needs a decision on which trade-off to accept before it is changed.

## Indexes

Indexes the plans show being used:

- `gig_status_created_idx`: the base feed page query, and the q search page query (which walks the
  newest gigs first and filters them, so the first 12 matches come back quickly).
- `gig_search_vector_gin`: the q search COUNT query, and every other query that has a `q`.
- For q + filters, `gig_search_vector_gin` combined with a category index: `gig_status_category_idx`
  at 10,000 gigs, and the foreign key index on `category_id` at 50,000.
- `gigs_gigskill_skill_id_c5de3338`, the foreign key index on `gigs_gigskill.skill_id`: skills ALL.
- `gig_title_trgm_gin` and `gig_description_gin`: the typo fallback at 50,000 gigs only.

Indexes that none of these five queries used: `gig_budget_min_idx`, `gig_budget_max_idx`,
`gig_deadline_idx` and `gig_app_deadline_idx`. The budget range in "q + filters" is applied as a
filter after the search index narrows the rows, which is cheaper than combining them. They are left
in place; dropping them would be a separate decision with its own measurements.

Added in this PR: `gig_title_trgm_gin`, described above. No other index was added.

## EXPLAIN (ANALYZE, BUFFERS) at 50,000 gigs, after the fixes

Page queries (the first 12 rows, as the API fetches them). Produced by
`python scripts/explain_gig_queries.py`.

### base feed

```
Limit  (cost=0.87..4.64 rows=12 width=3314) (actual time=0.169..0.362 rows=12.00 loops=1)
  Buffers: shared hit=63
  ->  Nested Loop Left Join  (cost=0.87..24218.66 rows=77110 width=3314) (actual time=0.169..0.358 rows=12.00 loops=1)
        Buffers: shared hit=63
        ->  Nested Loop  (cost=0.72..23098.09 rows=42839 width=2470) (actual time=0.138..0.296 rows=12.00 loops=1)
              Buffers: shared hit=45
              ->  Nested Loop  (cost=0.56..22030.17 rows=42839 width=1946) (actual time=0.114..0.248 rows=12.00 loops=1)
                    Buffers: shared hit=35
                    ->  Index Scan using gig_status_created_idx on gigs_gig  (cost=0.41..20968.23 rows=42839 width=477) (actual time=0.068..0.162 rows=12.00 loops=1)
                          Index Cond: ((status)::text = 'open'::text)
                          Filter: (application_deadline >= '2026-10-05'::date)
                          Rows Removed by Filter: 1
                          Index Searches: 1
                          Buffers: shared hit=17
                    ->  Memoize  (cost=0.15..0.17 rows=1 width=1469) (actual time=0.006..0.006 rows=1.00 loops=12)
                          Cache Key: gigs_gig.client_id
                          Cache Mode: logical
                          Hits: 3  Misses: 9  Evictions: 0  Overflows: 0  Memory Usage: 3kB
                          Buffers: shared hit=18
                          ->  Index Scan using accounts_user_pkey on accounts_user  (cost=0.14..0.16 rows=1 width=1469) (actual time=0.005..0.005 rows=1.00 loops=9)
                                Index Cond: (id = gigs_gig.client_id)
                                Index Searches: 9
                                Buffers: shared hit=18
              ->  Memoize  (cost=0.15..0.17 rows=1 width=524) (actual time=0.003..0.003 rows=1.00 loops=12)
                    Cache Key: gigs_gig.category_id
                    Cache Mode: logical
                    Hits: 7  Misses: 5  Evictions: 0  Overflows: 0  Memory Usage: 1kB
                    Buffers: shared hit=10
                    ->  Index Scan using gigs_category_pkey on gigs_category  (cost=0.14..0.16 rows=1 width=524) (actual time=0.005..0.005 rows=1.00 loops=5)
                          Index Cond: (id = gigs_gig.category_id)
                          Index Searches: 5
                          Buffers: shared hit=10
        ->  Memoize  (cost=0.15..1.13 rows=1 width=844) (actual time=0.004..0.004 rows=1.00 loops=12)
              Cache Key: accounts_user.id
              Cache Mode: logical
              Hits: 3  Misses: 9  Evictions: 0  Overflows: 0  Memory Usage: 2kB
              Buffers: shared hit=18
              ->  Index Scan using profiles_clientprofile_user_id_key on profiles_clientprofile  (cost=0.14..1.12 rows=1 width=844) (actual time=0.004..0.004 rows=1.00 loops=9)
                    Index Cond: (user_id = accounts_user.id)
                    Index Searches: 9
                    Buffers: shared hit=18
Planning:
  Buffers: shared hit=331
Planning Time: 7.901 ms
Execution Time: 0.539 ms
```

### q search

```
Limit  (cost=0.85..154.04 rows=12 width=3318) (actual time=0.204..1.439 rows=12.00 loops=1)
  Buffers: shared hit=389
  ->  Nested Loop Left Join  (cost=0.85..33664.30 rows=2637 width=3318) (actual time=0.202..1.435 rows=12.00 loops=1)
        Buffers: shared hit=389
        ->  Nested Loop  (cost=0.70..32905.51 rows=1465 width=2470) (actual time=0.168..1.328 rows=12.00 loops=1)
              Buffers: shared hit=371
              ->  Nested Loop  (cost=0.55..32619.95 rows=1465 width=1946) (actual time=0.157..1.289 rows=12.00 loops=1)
                    Buffers: shared hit=347
                    ->  Index Scan using gig_status_created_idx on gigs_gig  (cost=0.41..32342.60 rows=1465 width=477) (actual time=0.143..1.235 rows=12.00 loops=1)
                          Index Cond: ((status)::text = 'open'::text)
                          Filter: ((application_deadline >= '2026-10-05'::date) AND (search_vector @@ websearch_to_tsquery('bakery'::text)))
                          Rows Removed by Filter: 307
                          Index Searches: 1
                          Buffers: shared hit=323
                    ->  Index Scan using accounts_user_pkey on accounts_user  (cost=0.14..0.19 rows=1 width=1469) (actual time=0.003..0.003 rows=1.00 loops=12)
                          Index Cond: (id = gigs_gig.client_id)
                          Index Searches: 12
                          Buffers: shared hit=24
              ->  Index Scan using gigs_category_pkey on gigs_category  (cost=0.14..0.20 rows=1 width=524) (actual time=0.002..0.002 rows=1.00 loops=12)
                    Index Cond: (id = gigs_gig.category_id)
                    Index Searches: 12
                    Buffers: shared hit=24
        ->  Memoize  (cost=0.15..1.13 rows=1 width=844) (actual time=0.004..0.004 rows=1.00 loops=12)
              Cache Key: accounts_user.id
              Cache Mode: logical
              Hits: 3  Misses: 9  Evictions: 0  Overflows: 0  Memory Usage: 2kB
              Buffers: shared hit=18
              ->  Index Scan using profiles_clientprofile_user_id_key on profiles_clientprofile  (cost=0.14..1.12 rows=1 width=844) (actual time=0.003..0.003 rows=1.00 loops=9)
                    Index Cond: (user_id = accounts_user.id)
                    Index Searches: 9
                    Buffers: shared hit=18
Planning:
  Buffers: shared hit=4
Planning Time: 1.240 ms
Execution Time: 1.526 ms
```

### q + filters

```
Limit  (cost=966.43..966.44 rows=2 width=3318) (actual time=2.643..2.648 rows=12.00 loops=1)
  Buffers: shared hit=299
  ->  Sort  (cost=966.43..966.44 rows=2 width=3318) (actual time=2.642..2.645 rows=12.00 loops=1)
        Sort Key: (ts_rank(gigs_gig.search_vector, websearch_to_tsquery('bakery'::text))) DESC, gigs_gig.created_at DESC
        Sort Method: quicksort  Memory: 39kB
        Buffers: shared hit=299
        ->  Nested Loop Left Join  (cost=165.97..966.42 rows=2 width=3318) (actual time=2.054..2.512 rows=14.00 loops=1)
              Buffers: shared hit=293
              ->  Nested Loop  (cost=165.83..964.77 rows=1 width=2470) (actual time=2.029..2.403 rows=14.00 loops=1)
                    Buffers: shared hit=265
                    ->  Nested Loop  (cost=165.69..964.26 rows=1 width=1001) (actual time=2.014..2.343 rows=14.00 loops=1)
                          Buffers: shared hit=237
                          ->  Index Scan using gigs_category_slug_a4eb13cd_like on gigs_category  (cost=0.14..8.16 rows=1 width=524) (actual time=0.005..0.006 rows=1.00 loops=1)
                                Index Cond: ((slug)::text = 'admin-virtual-assistance'::text)
                                Index Searches: 1
                                Buffers: shared hit=2
                          ->  Bitmap Heap Scan on gigs_gig  (cost=165.54..955.93 rows=17 width=477) (actual time=2.005..2.328 rows=14.00 loops=1)
                                Recheck Cond: ((search_vector @@ websearch_to_tsquery('bakery'::text)) AND (category_id = gigs_category.id))
                                Filter: ((application_deadline >= '2026-10-05'::date) AND (budget_max >= 10000.00) AND (budget_min <= 30000.00) AND ((status)::text = 'open'::text) AND ((currency)::text = 'KES'::text) AND ((county)::text = 'Nairobi'::text))
                                Rows Removed by Filter: 203
                                Heap Blocks: exact=211
                                Buffers: shared hit=235
                                ->  BitmapAnd  (cost=165.54..165.54 rows=214 width=0) (actual time=1.914..1.915 rows=0.00 loops=1)
                                      Buffers: shared hit=24
                                      ->  Bitmap Index Scan on gig_search_vector_gin  (cost=0.00..38.09 rows=1710 width=0) (actual time=0.509..0.509 rows=1716.00 loops=1)
                                            Index Cond: (search_vector @@ websearch_to_tsquery('bakery'::text))
                                            Index Searches: 1
                                            Buffers: shared hit=4
                                      ->  Bitmap Index Scan on gigs_gig_category_id_e9d38d2a  (cost=0.00..127.17 rows=6250 width=0) (actual time=1.290..1.290 rows=6279.00 loops=1)
                                            Index Cond: (category_id = gigs_category.id)
                                            Index Searches: 1
                                            Buffers: shared hit=20
                    ->  Index Scan using accounts_user_pkey on accounts_user  (cost=0.14..0.50 rows=1 width=1469) (actual time=0.003..0.003 rows=1.00 loops=14)
                          Index Cond: (id = gigs_gig.client_id)
                          Index Searches: 14
                          Buffers: shared hit=28
              ->  Index Scan using profiles_clientprofile_user_id_key on profiles_clientprofile  (cost=0.14..1.12 rows=1 width=844) (actual time=0.002..0.002 rows=1.00 loops=14)
                    Index Cond: (user_id = accounts_user.id)
                    Index Searches: 14
                    Buffers: shared hit=28
Planning:
  Buffers: shared hit=17
Planning Time: 1.134 ms
Execution Time: 2.886 ms
```

### skills ALL

```
Limit  (cost=2780.57..2780.60 rows=12 width=3314) (actual time=29.174..29.181 rows=12.00 loops=1)
  Buffers: shared hit=4689
  ->  Sort  (cost=2780.57..2780.76 rows=76 width=3314) (actual time=29.174..29.178 rows=12.00 loops=1)
        Sort Key: gigs_gig.created_at DESC
        Sort Method: top-N heapsort  Memory: 46kB
        Buffers: shared hit=4689
        ->  Hash Left Join  (cost=2157.86..2778.83 rows=76 width=3314) (actual time=17.404..28.641 rows=398.00 loops=1)
              Hash Cond: (accounts_user.id = profiles_clientprofile.user_id)
              Buffers: shared hit=4689
              ->  Nested Loop  (cost=2145.84..2766.69 rows=42 width=2470) (actual time=17.336..28.246 rows=398.00 loops=1)
                    Buffers: shared hit=4688
                    ->  Nested Loop  (cost=2145.69..2759.82 rows=42 width=1946) (actual time=17.329..27.470 rows=398.00 loops=1)
                          Buffers: shared hit=3892
                          ->  Nested Loop  (cost=2145.55..2753.17 rows=42 width=477) (actual time=17.315..26.528 rows=398.00 loops=1)
                                Buffers: shared hit=3096
                                ->  GroupAggregate  (cost=2145.14..2347.74 rows=49 width=16) (actual time=17.274..22.855 rows=478.00 loops=1)
                                      Group Key: u0.gig_id
                                      Filter: (count(DISTINCT u0.skill_id) = 2)
                                      Rows Removed by Filter: 9500
                                      Buffers: shared hit=1184
                                      ->  Sort  (cost=2145.14..2171.77 rows=10655 width=32) (actual time=17.243..18.305 rows=10456.00 loops=1)
                                            Sort Key: u0.gig_id, u0.skill_id
                                            Sort Method: quicksort  Memory: 875kB
                                            Buffers: shared hit=1184
                                            ->  Bitmap Heap Scan on gigs_gigskill u0  (cost=131.17..1432.36 rows=10655 width=32) (actual time=0.873..10.220 rows=10456.00 loops=1)
                                                  Recheck Cond: (skill_id = ANY ('{37d59bc0-7453-4f78-99ca-495cb5a9bb11,614424c9-07f3-47b5-8ecd-b7c2ffee93b9}'::uuid[]))
                                                  Heap Blocks: exact=1168
                                                  Buffers: shared hit=1181
                                                  ->  Bitmap Index Scan on gigs_gigskill_skill_id_c5de3338  (cost=0.00..128.50 rows=10655 width=0) (actual time=0.627..0.628 rows=10456.00 loops=1)
                                                        Index Cond: (skill_id = ANY ('{37d59bc0-7453-4f78-99ca-495cb5a9bb11,614424c9-07f3-47b5-8ecd-b7c2ffee93b9}'::uuid[]))
                                                        Index Searches: 2
                                                        Buffers: shared hit=13
                                ->  Index Scan using gigs_gig_pkey on gigs_gig  (cost=0.41..8.27 rows=1 width=477) (actual time=0.007..0.007 rows=0.83 loops=478)
                                      Index Cond: (id = u0.gig_id)
                                      Filter: ((application_deadline >= '2026-10-05'::date) AND ((status)::text = 'open'::text))
                                      Rows Removed by Filter: 0
                                      Index Searches: 478
                                      Buffers: shared hit=1912
                          ->  Index Scan using accounts_user_pkey on accounts_user  (cost=0.14..0.16 rows=1 width=1469) (actual time=0.002..0.002 rows=1.00 loops=398)
                                Index Cond: (id = gigs_gig.client_id)
                                Index Searches: 398
                                Buffers: shared hit=796
                    ->  Index Scan using gigs_category_pkey on gigs_category  (cost=0.14..0.16 rows=1 width=524) (actual time=0.001..0.001 rows=1.00 loops=398)
                          Index Cond: (id = gigs_gig.category_id)
                          Index Searches: 398
                          Buffers: shared hit=796
              ->  Hash  (cost=10.90..10.90 rows=90 width=844) (actual time=0.037..0.037 rows=20.00 loops=1)
                    Buckets: 1024  Batches: 1  Memory Usage: 10kB
                    Buffers: shared hit=1
                    ->  Seq Scan on profiles_clientprofile  (cost=0.00..10.90 rows=90 width=844) (actual time=0.025..0.030 rows=20.00 loops=1)
                          Buffers: shared hit=1
Planning:
  Buffers: shared hit=74
Planning Time: 6.758 ms
Execution Time: 29.542 ms
```

### trigram fallback (typo)

```
Limit  (cost=7483.99..7491.35 rows=12 width=3326) (actual time=219.649..229.492 rows=12.00 loops=1)
  Buffers: shared hit=3363
  ->  Nested Loop Left Join  (cost=7483.99..10526.28 rows=4959 width=3326) (actual time=219.648..229.488 rows=12.00 loops=1)
        Buffers: shared hit=3363
        ->  Gather Merge  (cost=7483.84..7797.83 rows=2755 width=2470) (actual time=219.508..228.340 rows=12.00 loops=1)
              Workers Planned: 1
              Workers Launched: 1
              Buffers: shared hit=3345
              ->  Sort  (cost=6483.83..6487.88 rows=1621 width=2470) (actual time=189.496..189.506 rows=48.50 loops=2)
                    Sort Key: (CASE WHEN (gigs_gig.search_vector @@ websearch_to_tsquery('bakry'::text)) THEN (ts_rank(gigs_gig.search_vector, websearch_to_tsquery('bakry'::text)) + '2'::double precision) ELSE (GREATEST(word_similarity('bakry'::text, (gigs_gig.title)::text), word_similarity('bakry'::text, gigs_gig.description)))::double precision END) DESC, gigs_gig.created_at DESC
                    Sort Method: quicksort  Memory: 670kB
                    Buffers: shared hit=3345
                    Worker 0:  Sort Method: quicksort  Memory: 465kB
                    ->  Hash Join  (cost=352.93..6397.41 rows=1621 width=2470) (actual time=9.094..184.846 rows=742.50 loops=2)
                          Hash Cond: (gigs_gig.category_id = gigs_category.id)
                          Buffers: shared hit=3330
                          ->  Hash Join  (cost=339.78..6379.87 rows=1621 width=1946) (actual time=8.523..154.706 rows=742.50 loops=2)
                                Hash Cond: (gigs_gig.client_id = accounts_user.id)
                                Buffers: shared hit=3308
                                ->  Parallel Bitmap Heap Scan on gigs_gig  (cost=328.65..6364.13 rows=1621 width=477) (actual time=8.058..153.483 rows=742.50 loops=2)
                                      Recheck Cond: ((search_vector @@ websearch_to_tsquery('bakry'::text)) OR ((title)::text %> 'bakry'::text) OR (description %> 'bakry'::text))
                                      Rows Removed by Index Recheck: 2936
                                      Filter: ((application_deadline >= '2026-10-05'::date) AND ((status)::text = 'open'::text))
                                      Rows Removed by Filter: 116
                                      Heap Blocks: exact=1872
                                      Buffers: shared hit=3306
                                      Worker 0:  Heap Blocks: exact=1272
                                      ->  BitmapOr  (cost=328.65..328.65 rows=3271 width=0) (actual time=12.069..12.071 rows=0.00 loops=1)
                                            Buffers: shared hit=63
                                            ->  Bitmap Index Scan on gig_search_vector_gin  (cost=0.00..30.79 rows=250 width=0) (actual time=0.022..0.022 rows=0.00 loops=1)
                                                  Index Cond: (search_vector @@ websearch_to_tsquery('bakry'::text))
                                                  Index Searches: 1
                                                  Buffers: shared hit=3
                                            ->  Bitmap Index Scan on gig_title_trgm_gin  (cost=0.00..76.95 rows=1008 width=0) (actual time=2.460..2.460 rows=3875.00 loops=1)
                                                  Index Cond: ((title)::text %> 'bakry'::text)
                                                  Index Searches: 1
                                                  Buffers: shared hit=21
                                            ->  Bitmap Index Scan on gig_description_gin  (cost=0.00..218.85 rows=2013 width=0) (actual time=9.586..9.586 rows=7588.00 loops=1)
                                                  Index Cond: (description %> 'bakry'::text)
                                                  Index Searches: 1
                                                  Buffers: shared hit=39
                                ->  Hash  (cost=10.50..10.50 rows=50 width=1469) (actual time=0.439..0.440 rows=20.00 loops=2)
                                      Buckets: 1024  Batches: 1  Memory Usage: 13kB
                                      Buffers: shared hit=2
                                      ->  Seq Scan on accounts_user  (cost=0.00..10.50 rows=50 width=1469) (actual time=0.409..0.418 rows=20.00 loops=2)
                                            Buffers: shared hit=2
                          ->  Hash  (cost=11.40..11.40 rows=140 width=524) (actual time=0.507..0.508 rows=8.00 loops=2)
                                Buckets: 1024  Batches: 1  Memory Usage: 9kB
                                Buffers: shared hit=22
                                ->  Seq Scan on gigs_category  (cost=0.00..11.40 rows=140 width=524) (actual time=0.498..0.500 rows=8.00 loops=2)
                                      Buffers: shared hit=22
        ->  Memoize  (cost=0.15..1.13 rows=1 width=844) (actual time=0.005..0.005 rows=1.00 loops=12)
              Cache Key: accounts_user.id
              Cache Mode: logical
              Hits: 3  Misses: 9  Evictions: 0  Overflows: 0  Memory Usage: 2kB
              Buffers: shared hit=18
              ->  Index Scan using profiles_clientprofile_user_id_key on profiles_clientprofile  (cost=0.14..1.12 rows=1 width=844) (actual time=0.005..0.005 rows=1.00 loops=9)
                    Index Cond: (user_id = accounts_user.id)
                    Index Searches: 9
                    Buffers: shared hit=18
Planning:
  Buffers: shared hit=25 dirtied=1
Planning Time: 7.945 ms
Execution Time: 230.754 ms
```

### trigram fallback (typo): the paginator's COUNT query

```
Aggregate  (cost=6738.04..6738.05 rows=1 width=8) (actual time=287.703..287.705 rows=1.00 loops=1)
  Buffers: shared hit=3207
  ->  Bitmap Heap Scan on gigs_gig  (cost=328.65..6731.16 rows=2755 width=0) (actual time=8.020..287.428 rows=1485.00 loops=1)
        Recheck Cond: ((search_vector @@ websearch_to_tsquery('bakry'::text)) OR ((title)::text %> 'bakry'::text) OR (description %> 'bakry'::text))
        Rows Removed by Index Recheck: 5872
        Filter: ((application_deadline >= '2026-10-05'::date) AND ((status)::text = 'open'::text))
        Rows Removed by Filter: 231
        Heap Blocks: exact=3144
        Buffers: shared hit=3207
        ->  BitmapOr  (cost=328.65..328.65 rows=3271 width=0) (actual time=7.101..7.102 rows=0.00 loops=1)
              Buffers: shared hit=63
              ->  Bitmap Index Scan on gig_search_vector_gin  (cost=0.00..30.79 rows=250 width=0) (actual time=0.022..0.023 rows=0.00 loops=1)
                    Index Cond: (search_vector @@ websearch_to_tsquery('bakry'::text))
                    Index Searches: 1
                    Buffers: shared hit=3
              ->  Bitmap Index Scan on gig_title_trgm_gin  (cost=0.00..76.95 rows=1008 width=0) (actual time=2.235..2.235 rows=3875.00 loops=1)
                    Index Cond: ((title)::text %> 'bakry'::text)
                    Index Searches: 1
                    Buffers: shared hit=21
              ->  Bitmap Index Scan on gig_description_gin  (cost=0.00..218.85 rows=2013 width=0) (actual time=4.842..4.842 rows=7588.00 loops=1)
                    Index Cond: (description %> 'bakry'::text)
                    Index Searches: 1
                    Buffers: shared hit=39
Planning:
  Buffers: shared hit=6
Planning Time: 6.033 ms
Execution Time: 287.896 ms
```

## EXPLAIN (ANALYZE, BUFFERS) at 50,000 gigs, before the fixes

Only the two queries that changed.

### skills ALL (before)

```
Limit  (cost=12353.96..12353.99 rows=12 width=3322) (actual time=141.262..145.730 rows=12.00 loops=1)
  Buffers: shared hit=7750 read=5, temp read=511 written=512
  ->  Sort  (cost=12353.96..12354.16 rows=82 width=3322) (actual time=141.260..145.726 rows=12.00 loops=1)
        Sort Key: gigs_gig.created_at DESC
        Sort Method: top-N heapsort  Memory: 46kB
        Buffers: shared hit=7750 read=5, temp read=511 written=512
        ->  GroupAggregate  (cost=9815.45..12352.08 rows=82 width=3322) (actual time=94.835..145.241 rows=398.00 loops=1)
              Group Key: accounts_user.id, gigs_gig.id, profiles_clientprofile.id, gigs_category.id
              Filter: (count(DISTINCT gigs_gigskill.skill_id) = 2)
              Rows Removed by Filter: 8168
              Buffers: shared hit=7750 read=5, temp read=511 written=512
              ->  Incremental Sort  (cost=9815.45..11941.28 rows=16432 width=3330) (actual time=94.760..130.460 rows=8964.00 loops=1)
                    Sort Key: accounts_user.id, gigs_gig.id, profiles_clientprofile.id, gigs_category.id, gigs_gigskill.skill_id
                    Presorted Key: accounts_user.id
                    Full-sort Groups: 20  Sort Method: quicksort  Average Memory: 76kB  Peak Memory: 76kB
                    Pre-sorted Groups: 20  Sort Method: quicksort  Average Memory: 392kB  Peak Memory: 392kB
                    Buffers: shared hit=7750 read=5, temp read=511 written=512
                    ->  Merge Left Join  (cost=9714.40..10939.98 rows=16432 width=3330) (actual time=93.150..113.707 rows=8964.00 loops=1)
                          Merge Cond: (accounts_user.id = profiles_clientprofile.user_id)
                          Buffers: shared hit=7750 read=5, temp read=511 written=512
                          ->  Gather Merge  (cost=9700.58..10811.60 rows=9129 width=2486) (actual time=93.115..108.224 rows=8964.00 loops=1)
                                Workers Planned: 2
                                Workers Launched: 2
                                Buffers: shared hit=7749 read=5, temp read=511 written=512
                                ->  Merge Join  (cost=8700.55..8757.86 rows=3804 width=2486) (actual time=36.865..40.458 rows=2988.00 loops=3)
                                      Merge Cond: (gigs_gig.client_id = accounts_user.id)
                                      Buffers: shared hit=7749 read=5, temp read=511 written=512
                                      ->  Sort  (cost=8688.64..8698.15 rows=3804 width=1017) (actual time=35.922..37.215 rows=2988.00 loops=3)
                                            Sort Key: gigs_gig.client_id
                                            Sort Method: external merge  Disk: 4088kB
                                            Buffers: shared hit=7746 read=5, temp read=511 written=512
                                            Worker 0:  Sort Method: quicksort  Memory: 484kB
                                            Worker 1:  Sort Method: quicksort  Memory: 511kB
                                            ->  Hash Join  (cost=1469.01..8462.43 rows=3804 width=1017) (actual time=6.591..27.816 rows=2988.00 loops=3)
                                                  Hash Cond: (gigs_gig.category_id = gigs_category.id)
                                                  Buffers: shared hit=7738 read=5
                                                  ->  Parallel Hash Join  (cost=1455.86..8438.99 rows=3804 width=493) (actual time=5.830..25.367 rows=2988.00 loops=3)
                                                        Hash Cond: (gigs_gig.id = gigs_gigskill.gig_id)
                                                        Buffers: shared hit=7735 read=5
                                                        ->  Parallel Seq Scan on gigs_gig  (cost=0.00..6871.50 rows=17850 width=477) (actual time=0.017..14.162 rows=14245.67 loops=3)
                                                              Filter: ((application_deadline >= '2026-10-05'::date) AND ((status)::text = 'open'::text))
                                                              Rows Removed by Filter: 2421
                                                              Buffers: shared hit=6559
                                                        ->  Parallel Hash  (cost=1377.51..1377.51 rows=6268 width=32) (actual time=5.686..5.688 rows=3485.33 loops=3)
                                                              Buckets: 16384  Batches: 1  Memory Usage: 800kB
                                                              Buffers: shared hit=1176 read=5
                                                              ->  Parallel Bitmap Heap Scan on gigs_gigskill  (cost=131.17..1377.51 rows=6268 width=32) (actual time=1.123..12.648 rows=10456.00 loops=1)
                                                                    Recheck Cond: (skill_id = ANY ('{37d59bc0-7453-4f78-99ca-495cb5a9bb11,614424c9-07f3-47b5-8ecd-b7c2ffee93b9}'::uuid[]))
                                                                    Heap Blocks: exact=1168
                                                                    Buffers: shared hit=1176 read=5
                                                                    ->  Bitmap Index Scan on gigs_gigskill_skill_id_c5de3338  (cost=0.00..128.50 rows=10655 width=0) (actual time=0.884..0.884 rows=10456.00 loops=1)
                                                                          Index Cond: (skill_id = ANY ('{37d59bc0-7453-4f78-99ca-495cb5a9bb11,614424c9-07f3-47b5-8ecd-b7c2ffee93b9}'::uuid[]))
                                                                          Index Searches: 2
                                                                          Buffers: shared hit=8 read=5
                                                  ->  Hash  (cost=11.40..11.40 rows=140 width=524) (actual time=0.736..0.737 rows=8.00 loops=3)
                                                        Buckets: 1024  Batches: 1  Memory Usage: 9kB
                                                        Buffers: shared hit=3
                                                        ->  Seq Scan on gigs_category  (cost=0.00..11.40 rows=140 width=524) (actual time=0.715..0.716 rows=8.00 loops=3)
                                                              Buffers: shared hit=3
                                      ->  Sort  (cost=11.91..12.04 rows=50 width=1469) (actual time=0.935..0.940 rows=20.00 loops=3)
                                            Sort Key: accounts_user.id
                                            Sort Method: quicksort  Memory: 29kB
                                            Buffers: shared hit=3
                                            Worker 0:  Sort Method: quicksort  Memory: 29kB
                                            Worker 1:  Sort Method: quicksort  Memory: 29kB
                                            ->  Seq Scan on accounts_user  (cost=0.00..10.50 rows=50 width=1469) (actual time=0.892..0.901 rows=20.00 loops=3)
                                                  Buffers: shared hit=3
                          ->  Sort  (cost=13.82..14.05 rows=90 width=844) (actual time=0.031..0.036 rows=20.00 loops=1)
                                Sort Key: profiles_clientprofile.user_id
                                Sort Method: quicksort  Memory: 26kB
                                Buffers: shared hit=1
                                ->  Seq Scan on profiles_clientprofile  (cost=0.00..10.90 rows=90 width=844) (actual time=0.015..0.019 rows=20.00 loops=1)
                                      Buffers: shared hit=1
Planning:
  Buffers: shared hit=103 read=6
Planning Time: 24.559 ms
Execution Time: 165.648 ms
```

### trigram fallback (typo) (before)

```
Limit  (cost=13717.88..13725.48 rows=12 width=3326) (actual time=705.771..715.262 rows=12.00 loops=1)
  Buffers: shared hit=6895 read=2
  ->  Nested Loop Left Join  (cost=13717.88..30161.17 rows=25960 width=3326) (actual time=705.770..715.258 rows=12.00 loops=1)
        Buffers: shared hit=6895 read=2
        ->  Nested Loop  (cost=13717.73..16117.38 rows=14422 width=2470) (actual time=705.678..714.335 rows=12.00 loops=1)
              Buffers: shared hit=6877 read=2
              ->  Nested Loop  (cost=13717.58..15756.87 rows=14422 width=1946) (actual time=705.661..714.282 rows=12.00 loops=1)
                    Buffers: shared hit=6863 read=2
                    ->  Gather Merge  (cost=13717.43..15397.11 rows=14422 width=477) (actual time=705.626..714.203 rows=12.00 loops=1)
                          Workers Planned: 2
                          Workers Launched: 2
                          Buffers: shared hit=6845 read=2
                          ->  Sort  (cost=12717.40..12732.42 rows=6009 width=477) (actual time=664.143..664.151 rows=87.33 loops=3)
                                Sort Key: (CASE WHEN (gigs_gig.search_vector @@ websearch_to_tsquery('bakry'::text)) THEN (ts_rank(gigs_gig.search_vector, websearch_to_tsquery('bakry'::text)) + '2'::double precision) ELSE (GREATEST(word_similarity('bakry'::text, (gigs_gig.title)::text), word_similarity('bakry'::text, gigs_gig.description)))::double precision END) DESC, gigs_gig.created_at DESC
                                Sort Method: quicksort  Memory: 306kB
                                Buffers: shared hit=6845 read=2
                                Worker 0:  Sort Method: quicksort  Memory: 233kB
                                Worker 1:  Sort Method: quicksort  Memory: 259kB
                                ->  Parallel Seq Scan on gigs_gig  (cost=0.00..12340.25 rows=6009 width=477) (actual time=1.952..661.644 rows=495.00 loops=3)
                                      Filter: ((application_deadline >= '2026-10-05'::date) AND ((status)::text = 'open'::text) AND ((search_vector @@ websearch_to_tsquery('bakry'::text)) OR (GREATEST(word_similarity('bakry'::text, (title)::text), word_similarity('bakry'::text, description)) >= '0.25'::double precision)))
                                      Rows Removed by Filter: 16172
                                      Buffers: shared hit=6755 read=2
                    ->  Memoize  (cost=0.15..0.17 rows=1 width=1469) (actual time=0.005..0.005 rows=1.00 loops=12)
                          Cache Key: gigs_gig.client_id
                          Cache Mode: logical
                          Hits: 3  Misses: 9  Evictions: 0  Overflows: 0  Memory Usage: 3kB
                          Buffers: shared hit=18
                          ->  Index Scan using accounts_user_pkey on accounts_user  (cost=0.14..0.16 rows=1 width=1469) (actual time=0.004..0.004 rows=1.00 loops=9)
                                Index Cond: (id = gigs_gig.client_id)
                                Index Searches: 9
                                Buffers: shared hit=18
              ->  Memoize  (cost=0.15..0.18 rows=1 width=524) (actual time=0.003..0.003 rows=1.00 loops=12)
                    Cache Key: gigs_gig.category_id
                    Cache Mode: logical
                    Hits: 5  Misses: 7  Evictions: 0  Overflows: 0  Memory Usage: 2kB
                    Buffers: shared hit=14
                    ->  Index Scan using gigs_category_pkey on gigs_category  (cost=0.14..0.17 rows=1 width=524) (actual time=0.003..0.003 rows=1.00 loops=7)
                          Index Cond: (id = gigs_gig.category_id)
                          Index Searches: 7
                          Buffers: shared hit=14
        ->  Memoize  (cost=0.15..1.13 rows=1 width=844) (actual time=0.003..0.003 rows=1.00 loops=12)
              Cache Key: accounts_user.id
              Cache Mode: logical
              Hits: 3  Misses: 9  Evictions: 0  Overflows: 0  Memory Usage: 2kB
              Buffers: shared hit=18
              ->  Index Scan using profiles_clientprofile_user_id_key on profiles_clientprofile  (cost=0.14..1.12 rows=1 width=844) (actual time=0.002..0.002 rows=1.00 loops=9)
                    Index Cond: (user_id = accounts_user.id)
                    Index Searches: 9
                    Buffers: shared hit=18
Planning:
  Buffers: shared hit=20
Planning Time: 1.272 ms
Execution Time: 716.529 ms
```

