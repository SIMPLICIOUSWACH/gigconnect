# Sprint 5 Review: Recommendation Engine

**Status: DRAFT.** Written by the assistant from the code, the pull requests, the CI results and the measurements
taken during the sprint. The retrospective and anything marked "to confirm" need the team's input.

**This review contains no accuracy figures, on purpose.** Evaluating the recommender (the split, precision,
recall and F1 at K, the random baseline and tuning) is Sprint 6. Nothing in this sprint was measured against
ground truth.

## Sprint goal

Build the hybrid gig recommendation engine from the proposal: content-based filtering (TF-IDF and cosine
similarity), collaborative filtering (Truncated SVD over interactions and applications), a cold-start fallback,
a "Recommended for You" section for freelancers, and skill match scores for clients, with nothing shown that the
trained model did not compute for that exact freelancer and gig. Epics: #22 and #23.

## Stories

| # | Story | Points | Issue | Epic | Pull request | State |
|---|---|---|---|---|---|---|
| 1 | Recommendation app, dependencies, datasets and data pipeline | 8 | #51 | #22 | #58 | Merged |
| 2 | Content-based model | 5 | #52 | #22 | #59 | Merged |
| 3 | Collaborative model | 5 | #53 | #23 | #60 | Merged |
| 4 | Hybrid scoring, cold start, training and loading | 8 | #54 | #23 | #61 | Merged |
| 5 | Recommendations and match score API | 5 | #55 | #23 | #62 | Merged |
| 6 | Recommended for You and match scores (frontend) | 5 | #56 | #22 | #63 | Merged |
| 7 | Seed data, privacy, docs and tests | 5 | #57 | #22 | #64 | Open |

Total planned: 41 points.

Issues #51 to #56 are still open on GitHub even though their pull requests are merged. GitHub only closes an
issue when a pull request merges into the default branch, and these merged into `develop`. They close when
`develop` is released to `main`.

## Done and not done

**Done**

- The `recommendations` app, the pinned ML dependencies, the cleaned document pipeline, and `import_job_corpus`
  for the Kaggle files (LinkedIn full-time postings left out).
- The content model, the candidate rules (shared with the feed and checked against the real apply endpoint), and
  the shared skills named as the reason for each match.
- The collaborative model, with weights in settings, scores that are absent and not zero, and a refusal with a
  recorded reason when there is too little data.
- The hybrid score with cold start, `train_recommender`, the `RecommenderModelVersion` table, and a loader that
  loads once, caches, and answers "not available" instead of failing.
- `GET /api/recommendations/`, the client's match score and band on the applicants list, and recommendation
  click logging.
- Recommended for You on Browse Gigs and the Dashboard, and the match band on the applicant card, with an
  honest empty state for every case.
- `seed_interactions`, the privacy checks, `docs/recommender.md`, and the API and ERD documentation.

**Not done, or still open**

- Story 7's pull request is open and waiting for review.
- **No evaluation.** The recommender has not been checked for relevance in any way. That is Sprint 6.
- Lemmatisation is not done. It is a documented gap.
- The data is almost all synthetic (see below), so nothing here shows the recommendations are good for real
  freelancers.
- The dataset download dates and versions in the `datasets/raw/` READMEs and in `docs/recommender.md` are left
  for the project owner to fill in. To confirm.
- The applicants page showing a match band has not been seen in a browser against real applicants; it is covered
  by tests. The other new pages were checked in a browser.

## Velocity

Planned 41 points. At the time of writing, 36 points are merged (stories 1 to 6) and 5 points are in the open
pull request (story 7). Earlier sprints' velocity is not in the repository, so no comparison is made. To
confirm: the team's own figures.

## Test counts

| | Before Sprint 5 | After Sprint 5 (with #64) |
|---|---|---|
| Backend tests | 371 | 669 |
| Frontend tests | 74 | 102 |

The backend figures are the test runner's totals. Running the backend suite takes about 100 seconds now, where
it took about 20 minutes at the start of the sprint (see below).

## New dependencies, migrations, endpoints, commands, settings and pages

**Dependencies:** scikit-learn 1.9.1, scipy 1.18.1, numpy 2.5.4, joblib 1.6.0 and threadpoolctl 3.7.0. Installing
dependencies in CI went from about 5 to about 12 seconds.

**Migrations:** `recommendations.0001_initial` (the model version table) and `gigs.0011_alter_giginteraction_type`
(adds `recommendation_click`; choices only, no table change).

**Endpoints:** new `GET /api/recommendations/`. Changed: `GET /api/gigs/<id>/applications/` (adds `match_score`,
`match_reasons`, `match_band` and `match_scores`) and `POST /api/gigs/<id>/interactions/` (accepts
`recommendation_click`).

**Commands:** `import_job_corpus`, `train_recommender` and `seed_interactions`.

**Settings:** `RECOMMENDATIONS_ENABLED` (off by default) and the `RECOMMENDER_*` settings listed in
`docs/recommender.md`.

**Pages:** no new pages. Changed: Browse Gigs and the Dashboard (Recommended for You) and the applicant card on
the applicants page (the match band). The hard-coded frontend `RECOMMENDATIONS_ENABLED` constant was removed.

## The data actually used

From the dated reports in `datasets/reports/` (gitignored).

**External job postings** (content vocabulary only): Upwork read 63,950 rows, dropped 4 empty and 3,550
duplicates, kept 15,000 of 60,396 unique. LinkedIn read 123,849 rows, left out 98,814 full-time, dropped 1 empty
and 3,673 duplicates, kept 15,000 of 21,361 unique. 30,000 documents in all; vocabulary 30,516 words after the
vectoriser's own limits.

**GigConnect data** (latest development training run, version 2): 305 gigs, of which 300 are synthetic (98%); 35
freelancers; 893 freelancer and gig pairs, of which 890 are synthetic (100%). The collaborative model fitted with
15 factors, which explain 64.8% of the matrix. The first training run, before the seed data, had 3 pairs and
skipped the collaborative model.

**Measured endpoint timings** (development database, real model, 660 requests from 33 freelancers): the first
request after a restart, which loads the model, took 494 ms. After that the median was 53 ms, the 95th
percentile 59 ms and the worst 154 ms, with 6 database queries. These are speeds, not quality. Scoring grows
linearly with the number of gigs a freelancer could apply to, and would pass the 500 ms target at somewhere above
3,000 open gigs for one freelancer.

## Where the build differs from the proposal

I could not compare against the written proposal itself, so this lists what may differ:

- Lemmatisation is not done.
- LinkedIn full-time postings are excluded, and Freelancer.com is built in but off by default.
- A client's match is shown as a band in words, not as a number or percentage.
- A `recommendation_click` interaction type was added.
- Training is a manual command, not scheduled.
- The cold-start numbers, the blend weights, the SVD limits and the band cut-offs are starting values.

## Retrospective (DRAFT, to be completed by the team)

*These are observations from the work, not agreed conclusions.*

**What went well**

- A fast password hasher for the test run cut the backend suite from about 20 minutes to about 35 seconds at the
  start of the sprint, which made every later check quick. The suite has grown since and now takes about 100 s.
- Sharing the feed's rules with the recommender, and testing the recommender's candidates against the real apply
  endpoint, means a gig that is not in the feed cannot be recommended.
- Every empty state has its own plain message, and tests check that no score, percentage or match label appears
  where the model did not produce one.
- Seeing the finished pages in a real browser, with the real model, caught nothing wrong and gave real
  confidence. It should have been done earlier in Sprint 4.

**What was harder**

- **A CI failure found a real bug.** The collaborative model was allowed almost as many hidden factors as the
  matrix had rows, so it memorised its input and its scores were noise. A test passed on one machine by luck and
  failed in CI. The cap is now half the smaller side. I should have run that test several times before pushing.
- Several tests were flaky for reasons that only showed up on repeat runs: two records created back to back with
  the same timestamp, rows in no fixed order, test data that tied exactly, and random ids that changed which gigs
  were seeded. Each was fixed, and running model-dependent tests several times is now the habit.
- The seed command was not repeatable at first, because skipped rows shifted the random numbers for the next
  freelancer. Each freelancer now has their own random stream.
- Closing issues from pull requests does not work when merging into `develop`.

**Ideas to try (for discussion)**

- Start Sprint 6 by writing the evaluation split and a random baseline, so any later change can be compared.
- Decide whether to cache gig vectors now or wait until the number of open gigs makes it necessary.
- Collect some real freelancer and client feedback on the "shared skills" wording before tuning the bands.
