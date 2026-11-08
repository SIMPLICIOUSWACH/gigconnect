# Sprint 6 Review: Evaluation and User Acceptance Testing

**Status: DRAFT.** Written by the assistant from the code, the pull requests and the measurements taken during the
sprint. The retrospective and anything marked "to confirm" need the team's input.

**Every figure here was measured on synthetic data.** It shows the pipeline works and how its parts compare on seed
data. It does not show how relevant the recommendations are to real freelancers; that is what the user acceptance
testing is for, and it has not been run yet.

## Sprint goal

Measure the Sprint 5 recommender honestly: a 70/15/15 time split, precision, recall and F1 at K = 5 and 10 against a
random baseline, tuning on validation only, one final test run, a performance follow-up, and a kit for user
acceptance testing with a relevance rating. Epics: #24 and #25.

## Stories

| # | Story | Points | Issue | Epic | Pull request | State |
|---|---|---|---|---|---|---|
| 1 | Evaluation split and seed data fit for evaluation | 8 | #66 | #24 | #73 | Merged |
| 2 | Evaluation metrics and baselines | 5 | #67 | #24 | #74 | Merged |
| 3 | `evaluate_recommender` command and report | 5 | #68 | #24 | #75 | Merged |
| 4 | Tuning on the validation set | 8 | #69 | #24 | #76 | Merged |
| 5 | Performance follow-up and gig cache | 3 | #70 | #24 | #77 | Merged |
| 6 | UAT kit and relevance feedback | 8 | #71 | #25 | #78 | Merged |
| 7 | Evaluation docs, review and tests | 5 | #72 | #24 | this story's pull request | Open |

Total planned: 42 points.

Issues #66 to #71 are still open on GitHub even though their pull requests are merged, because they merged into
`develop` and not the default branch. They close when `develop` is released to `main`.

## Done and not done

**Done**

- The seed data made usable for evaluation: applications follow skills, and are dated after their gig was posted and
  inside its application window (three separate problems were found and fixed).
- The split per freelancer by time, saved and reused, with tests that fail if anything held out reaches training, and
  candidates built "as of" the held-out period.
- The metrics with bootstrap intervals, random and popularity baselines, both collaborative readings (applications
  and hiring only, and all interactions), the cold-start group and strict relevance.
- `evaluate_recommender`, with a report and a CSV of every number, a synthetic-data warning, and the test part guarded
  by `--final` and logged.
- `tune_recommender` (240 combinations, validation only, a rule fixed in advance), and a read-only investigation of why
  the collaborative part added nothing.
- `check_collaborative_readiness`, which compares the training matrix with random matrices of the same shape.
- The **synthetic_planted** seed in its own database, with hidden taste groups the collaborative factors were shown to
  recover, labelled everywhere as "synthetic_planted - demonstrates pipeline mechanics, not real-world accuracy".
- The **production and demo recommender profiles**, with the tuned values in configuration, the demo refusing any
  database but the planted one, and its own model and snapshot folders (the production files were hashed before and
  after: unchanged).
- The demo accounts, `refresh_planted_demo` and `show_planted_demo`.
- The one-shot test on both data sets, each with its chosen settings.
- `time_recommendations` and the gig cache: about 7 times faster at 3,000 open gigs, under 500 ms up to 5,000.
- The UAT kit (`docs/uat/`), the "Is this gig relevant to you?" answer and `summarise_relevance`.
- `docs/recommender.md` (an Evaluation section and the full list of differences from the proposal), the ERD, the API
  docs and the README.

**Not done, or still open**

- Story 7's pull request is open and waiting for review.
- **The user acceptance testing has not been run.** The kit is ready and its result sheets are empty.
- **Notifications** (real-time and email, requirement IV) are not built. Planned first in Sprint 7.
- The cold-start note on Recommended for You ("they will improve as you apply") is not true while the production
  collaborative weight is 0. Not changed. To decide.
- The two one-shot test reports were written before a text fix, so their header names the ordinary test-run log. The
  logs themselves are right; the test parts were not scored again.

## Velocity

Planned 42 points. At the time of writing, 37 points are merged (stories 1 to 6) and 5 are in the open pull request.
Story 4 grew well beyond its 8 points at the team's request: the planted seed, the readiness check, the profiles, the
demo accounts and the one-shot tests were added to it. To confirm: the team's own figures.

## Test counts

| | Before Sprint 6 | After Sprint 6 (with Story 7) |
|---|---|---|
| Backend tests | 669 | 1088 |
| Frontend tests | 102 | 109 |

The full backend suite now takes about 8 minutes, most of it in the evaluation tests that fit models on small worlds.
Every pull request ran it three times before it was pushed.

## New migrations, endpoints, commands, settings and pages

**Migrations:** `gigs.0012_relevance_feedback_types` (widens `GigInteraction.type` from 20 to 30 characters for the
two relevance answers; no new column).

**Endpoints:** new `PUT /api/recommendations/<gig_id>/relevance/`. Changed: `GET /api/recommendations/` results carry
`relevance`, the freelancer's own answer.

**Commands:** `build_evaluation_split`, `evaluate_recommender`, `tune_recommender`, `check_collaborative_readiness`,
`seed_planted`, `refresh_planted_demo`, `show_planted_demo`, `time_recommendations` and `summarise_relevance`. Changed:
`seed_applications` (about 20 applications per freelancer, skill preference, realistic dates).

**Settings:** `RECOMMENDER_PROFILE` (production by default, or demo), with the profiles in
`backend/config/recommender_profiles.json`; `RECOMMENDER_PROFILE_LABEL`, `RECOMMENDER_PLANTED_DATABASE` and
`RECOMMENDER_SNAPSHOT_FOLDER`. The blend, factors, cold-start and band settings now come from the profile.

**Pages:** no new pages. Changed: Recommended for You asks "Is this gig relevant to you?" under each gig, and Browse
Gigs shows 10 recommendations instead of 6. The admin header names the active profile.

## Results

Test part, mean over freelancers. Full tables with intervals are in `docs/recommender.md`.

| | Skill-overlap seed, production (30 freelancers) | Planted seed, demo (250 freelancers), synthetic_planted |
|---|---|---|
| Random, F1@5 / F1@10 | 0.037 / 0.043 | 0.029 / 0.036 |
| Content only | 0.131 / 0.183 | 0.156 / 0.151 |
| Collaborative only | 0.025 / 0.041 | 0.048 / 0.042 |
| Chosen setting | 0.131 / 0.183 (weight 0, content only) | 0.160 / 0.161 (hybrid) |

**Tuned against Sprint 5:** production went from a collaborative weight of 0.5 to **0**, because on validation
content only beat the Sprint 5 hybrid by 0.058 (random spread 0.012, paired interval 0.013 to 0.110); the band
cut-offs went from 0.15 and 0.30 to 0.13 and 0.27. The demo profile uses the planted pick: weight 0.5, ramp 50, 2
factors, cold start below 10.

**Caveats**

- All data is synthetic. The skill-overlap seed favours the content model by construction; the planted seed was built
  with the pattern the collaborative model then found.
- On the skill-overlap seed the collaborative part had nothing to learn: its matrix explains no more than a random one
  of the same shape, and its scores rank the right answers at chance.
- On the planted test set the hybrid is ahead of content only, but the intervals overlap. Validation showed a gain of
  0.012 (paired interval 0.005 to 0.019).
- 30 freelancers is a small sample, and the strict (shortlisted or hired) reading had too few cases to say anything.

**Performance:** at 3,000 open gigs, a median of 136 ms and a 95th percentile of 209 ms with the gig cache, against
1,019 ms and 1,155 ms before it. The first request after a model loads builds the cache (about 2 seconds at 5,000).

## Where the build differs from the proposal

The full list is in `docs/recommender.md`. The ones to note in the final report:

- Live recommendations are content only in production (collaborative weight 0), chosen by tuning; the hybrid is built
  and runs in the demo profile.
- No lemmatisation; category in the TF-IDF text rather than one-hot; more interaction types than applications and
  hiring in the collaborative model; no stored recommendations or notifications tables; the model loaded on first use;
  text choices instead of database ENUMs; and the dataset choices.
- Notifications (requirement IV) are not built yet.
- Added beyond the proposal: popularity baseline, K = 20 and hit rate, bootstrap intervals, the planted seed and the
  demo profile, and the System Usability Scale as an optional extra in the UAT kit.

## Retrospective (DRAFT, to be completed by the team)

**What went well**

- The honest-numbers rule held: one split, validation only for tuning, one look at each test part, every number from
  a command that was run, and the synthetic share next to every result.
- Leakage was guarded by tests that fail when it happens, and the important tests were checked by breaking the code
  on purpose.
- When the collaborative part added nothing, the investigation found why, and the planted seed showed the pipeline can
  find a pattern when one is there.
- Measuring before building the cache showed the real cost was loading and cleaning gigs, not the vectors.

**What was harder**

- The seed data needed three fixes before it could be evaluated at all.
- Story 4 grew a lot through new requests during the sprint, which the points do not show.
- Tests that depend on random ids were flaky twice; the thresholds were set from simulations rather than retried.
- One commit picked up `docs/prompts/` by mistake; it was removed before the push.

**Ideas to try (for discussion)**

- Run the UAT sessions and compare perceived relevance at 5 and 10 with the offline precision.
- Re-run the readiness check and tuning when there is real data.
- Warm the gig cache when a model loads, and decide what the cold-start note should say at a weight of 0.
- Try a blend on matched scales (the z-scored diagnostic did better than the raw blend).
