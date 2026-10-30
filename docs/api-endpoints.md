# API Endpoint Reference

All endpoints are prefixed with `/api/`. Auth uses JWT bearer tokens
(`Authorization: Bearer <access_token>`) via `djangorestframework-simplejwt`.

## Auth (`/api/auth/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register/` | None | Role-conditional registration (client or freelancer) |
| POST | `/api/auth/login/` | None | Returns access + refresh JWT pair |
| POST | `/api/auth/token/refresh/` | None (refresh token) | Rotates the refresh token, returns a new access token |
| GET | `/api/auth/me/` | Required | Returns the logged-in user + their profile |
| GET | `/api/auth/verify-email/<token>/` | None | Confirms a signed, time-limited email verification token |
| POST | `/api/auth/send-otp/` | Required | Sends a 6-digit phone OTP (5-min expiry) |
| POST | `/api/auth/verify-otp/` | Required | Verifies the OTP, sets `is_phone_verified` |

## Profiles (`/api/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/skills/` | None | List all skills |
| GET | `/api/profiles/<user_id>/` | Required | Public-safe view of any user's profile (no email/phone/id_number) |
| PATCH | `/api/profile/complete/` | Required | Update bio/photo/skills (freelancer) or company info/logo (client) |
| GET/POST | `/api/profile/portfolio-items/` | Required (freelancer) | List / create portfolio items |
| GET/PATCH/DELETE | `/api/profile/portfolio-items/<id>/` | Required (freelancer, owner) | Manage a single portfolio item |
| POST | `/api/profile/submit-verification/` | Required (freelancer) | Submit ID number + document for identity verification |
| GET | `/api/admin/verifications/` | Required (admin) | List verification requests (filterable by `?status=`) |
| PATCH | `/api/admin/verifications/<id>/` | Required (admin) | Approve or reject a verification request |

## Settings (`/api/settings/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| PATCH | `/api/settings/account/` | Required | Update full_name/email/phone (resets the matching verification flag) |
| POST | `/api/settings/change-password/` | Required | Change password (blacklists all existing sessions) |
| GET | `/api/settings/sessions/` | Required | List active sessions |
| DELETE | `/api/settings/sessions/<id>/` | Required | Revoke a single session |
| POST | `/api/settings/sessions/logout-all/` | Required | Revoke every session |
| GET/PATCH | `/api/settings/notifications/` | Required | View/update notification preferences |
| GET | `/api/settings/export-data/` | Required | JSON export of the user's own data: account, notification preferences, gig interactions and `applications` (each with its cover letter, link, rate and status history) |
| POST | `/api/settings/delete-account/` | Required | Soft-delete (anonymise + deactivate) the account. Also deletes the user's gig interactions and closes and empties their applications (see below) |

**Deleting a freelancer's account and their applications:** pending, under review and shortlisted
applications become `withdrawn` with a system status event, and the cover letter, portfolio link and
proposed rate are cleared on all of them. The rows and history stay, so a client still reviewing
sees "Deleted User" with no text rather than the application vanishing. A `hired` application stays
`hired`. All of this happens in one transaction with the rest of the deletion.

## Gigs (`/api/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/categories/` | None | List gig categories |
| GET | `/api/gigs/` | None | List gigs — paginated, filtered, searched (see below) |
| POST | `/api/gigs/` | Required (client, email-verified) | Create a gig. `currency` must be `KES` if given at all (any other value is a 400) |
| GET | `/api/gigs/<id>/` | None | Full gig detail; increments `view_count`. Reachable by id regardless of status or deadline |
| PUT | `/api/gigs/<id>/` | Required (owning client) | Update a gig — only while `status = open` |
| DELETE | `/api/gigs/<id>/` | Required (owning client) | Delete a gig |
| PATCH | `/api/gigs/<id>/status/` | Required (owning client) | Change status — restricted to valid transitions (see below); disabled on the main detail route, this is the only way to change status |
| GET | `/api/gigs/mine/` | Required (client) | List the logged-in client's own gigs, all statuses. Each gig has `application_count` (every application received, withdrawn ones included) and `pending_application_count` |

`GET /api/gigs/<id>/` also returns `my_application` (`{id, status}`) for a signed-in freelancer who
has applied to that gig, and `null` for everyone else.

**Status transitions:** `open → in_progress → completed`, or `open`/`in_progress → closed`
(cancellation). No direct `open → completed`; no changes once `completed` or `closed`.

### `GET /api/gigs/` query parameters

By default the feed only returns gigs where `status = open` and `application_deadline` has not
passed. All parameters below are optional and combine with AND. Invalid values (an unknown
category slug, `budget_min > budget_max`, an out-of-range `posted_within`, an unrecognised
`sort`) return `400` with a field-level error rather than a silent no-op or a 500.

| Param | Type | Notes |
|---|---|---|
| `q` | string | Full-text search (title weight A, skills weight B, description weight C) via PostgreSQL `websearch_to_tsquery`, so stray punctuation can't cause a syntax error |
| `category` | string | Category slug, exact match |
| `skills` | string | Comma-separated skill ids or names (case-insensitive) |
| `skills_mode` | string | `any` (default): the gig has at least one of the skills. `all`: it has every one; a skill that doesn't exist means no results |
| `budget_min`, `budget_max` | decimal | Range **overlap**, not containment — a gig matches if its own budget range overlaps the requested one at all |
| `negotiable` | bool | `true`/`false`; omit to not filter on it |
| `include_closed` | bool | `true` lifts the default `status=open` + unexpired-deadline restriction entirely, returning every gig regardless of status or application deadline. Default `false` |
| `deadline_before` | date (`YYYY-MM-DD`) | Project deadline on or before this date |
| `posted_within` | int | One of `1`, `7`, `30` (days) |
| `sort` | string | `newest` (default), `deadline`, `budget_high`, `budget_low`, `relevance` |
| `page`, `page_size` | int | Default page size 12, max 50 |

**`sort=relevance`:** ranks by the number of matched `skills` first (when given), then by the text
search rank (when `q` is given), then newest. With neither `q` nor `skills` there is nothing to
rank by, so rather than erroring or returning an arbitrary order the request silently falls back
to `sort=newest` — the same behaviour as omitting
`sort` entirely. This is deliberate (see `GigFilterSerializer.validate()` in `gigs/filters.py`),
not a bug: a client that lets the user pick "Best match" before typing anything should still get
a sensible, stable order rather than a 400 or undefined ordering.

Response shape: `{count, page, page_size, total_pages, next, previous, results: [...]}`.

## Applications (`/api/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/gigs/<gig_id>/applications/` | Required (freelancer, email-verified) | Apply to a gig. Body: `cover_letter` (50 to 3000 characters), optional `portfolio_link`, optional `proposed_rate` (KES, more than 0). Returns `201` with the application |
| GET | `/api/gigs/<gig_id>/applications/` | Required (the gig's client) | The gig's applicants, newest first, each with the applicant's name, skills, verification, cover letter, link, rate, status history and a skill match (`match_score`, `match_reasons`, `match_band`, see Recommendations below). Query: `status`, `page`, `page_size`. Anyone else gets `403` |
| GET | `/api/applications/mine/` | Required (freelancer) | The freelancer's own applications, newest first. Query: `status`, `page`, `page_size` |
| GET | `/api/applications/<id>/` | Required (applicant or the gig's client) | One application with its status history. Anyone else gets `404`, so the endpoint does not reveal that it exists |
| POST | `/api/applications/<id>/withdraw/` | Required (the applicant) | Withdraw while `pending` or `under_review`. Optional `reason` (text, kept to 500 characters) |
| PATCH | `/api/applications/<id>/status/` | Required (the gig's client) | Move an application along the allowed transitions. Body: `status`, optional `note` (up to 500 characters). Anyone else gets `404` |

**List responses** (`/applications/mine/` and the client's applicants list) use the gig list's page
shape, `{count, page, page_size, total_pages, next, previous, results}`, plus
`status_counts`: `{pending, under_review, shortlisted, hired, rejected, withdrawn, total}`. The
counts ignore the `status` filter, so a set of tabs can always show every total. An unknown `status`
returns `400`.

**Each application** has `id`, `gig_id`, `gig_title`, `gig_status`, `client_name`, `status`,
`proposed_rate`, `created_at`, `updated_at`. The detail form (single application and the client's
list) also has `cover_letter`, `portfolio_link`, `applicant`, `events` and `allowed_next_statuses`.
`allowed_next_statuses` is worked out on the server for whoever is asking (the applicant, or the gig's
client), so a client of this API never has to copy the rules.

**Apply rules**, checked in this order (the first failure wins). Errors are `{"detail": "..."}`:

| # | Rule | Status | Message |
|---|---|---|---|
| 1 | The gig exists | 404 | This gig does not exist. |
| 2 | Not your own gig | 403 | You cannot apply to your own gig. |
| 3 | The gig is `open` | 400 | This gig is no longer accepting applications. |
| 4 | The application deadline has not passed | 400 | The application deadline for this gig has passed. |
| 5 | Not withdrawn before | 400 | You withdrew your application to this gig and cannot apply again. |
| 6 | Not already applied | 400 | You have already applied to this gig. |
| 7 | The body is valid | 400 | Field errors, for example `cover_letter` |

Role and email checks come before all of these: a client gets `403`, and an unverified email gets
`403` with "You must verify your email before performing this action." A successful application also
writes its first status event and an `apply` gig interaction, in one transaction. Two requests at
once cannot both succeed: the database's unique constraint is the backstop.

**Status transitions** (one module, `applications/transitions.py`). `hired`, `rejected` and
`withdrawn` are final.

| Who | From | To |
|---|---|---|
| Client | `pending` | `under_review`, `rejected` |
| Client | `under_review` | `shortlisted`, `rejected` |
| Client | `shortlisted` | `hired`, `rejected` |
| Freelancer | `pending`, `under_review` | `withdrawn` |

An invalid move returns `400` with, for example, "An application that is pending cannot be moved to
shortlisted." A client can review applications on a gig of any status.

**Hiring:** moving an application to `hired` also moves an `open` gig to `in_progress`, in the same
transaction. Other applications are left as they are, and the client rejects them when ready. Nothing
is rejected automatically. Hiring is refused with `400` on a `closed` or `completed` gig ("You can
only hire for a gig that is open or in progress."), and a second hire on the same gig is refused
("You have already hired someone for this gig.").

## Recommendations (`/api/`)

How the scores are made is in `docs/recommender.md`. This section is what the API returns.

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/recommendations/` | Required (freelancer, email-verified) | Gigs recommended for the signed-in freelancer, best first. Query: `page`, `page_size` (default 12, max 50) |
| POST | `/api/gigs/<gig_id>/interactions/` | None (throttled) | Log that a gig was opened from a list. Body: `type` of `search_click` or `recommendation_click`, optional `position` (its place in the list, 1 to 10000). Other types (`view`, `save`, `apply` and the two relevance answers) are written by the server or their own endpoint and are refused here with `400` |
| PUT | `/api/recommendations/<gig_id>/relevance/` | Required (freelancer, email-verified, throttled) | Answer "Is this gig relevant to you?" for a recommended gig. Body: `relevant` (`true` or `false`), optional `position` (its place in the list). Returns `{gig, relevance}` with `relevance` of `relevant` or `not_relevant`. A new answer replaces the old one. `403` while recommendations are switched off |

**`GET /api/recommendations/`** returns the gig list's page shape,
`{count, page, page_size, total_pages, next, previous, results}`, and also:

- `available`: whether recommendations could be served at all.
- `reason`: why not, or why the list is empty (see the table below), otherwise `null`.
- `cold_start`: `true` while the freelancer has interacted with fewer than 5 different gigs, so their scores
  come from skills only. `null` when `available` is false.
- `model`: `{version, trained_at, collaborative}`, where `collaborative` says whether that model has a
  collaborative part. `null` when `available` is false.

Each result is the gig card fields of the gig list plus `score`, `match_reasons`, `source` and `relevance`:

- `score` is from 0 to 1 and is computed by the trained model for this freelancer and this gig. It is for
  ordering, and it is not shown to users as a percentage.
- `match_reasons` is the skills the freelancer and the gig really share, named as the gig names them. It is
  never worked out from the score, and it can be empty.
- `source` is `content` (from skills and text only) or `hybrid` (blended with what freelancers with
  similar history showed interest in).
- `relevance` is the freelancer's own answer to "Is this gig relevant to you?": `relevant`, `not_relevant` or
  `null` if they have not answered.

**Relevance answers** (Sprint 6, for user acceptance testing) are stored as `recommendation_relevant` and
`recommendation_not_relevant` gig interactions, one per freelancer and gig, with the gig's place in the list. They
never feed the recommender: they are left out of training and do not count as history for the blend. They are in the
freelancer's data export and are deleted with their account. `python manage.py summarise_relevance
[--include-synthetic]` counts them overall, per gig and as "rated relevant out of rated" within the top 5 and top 10;
answers from synthetic accounts are left out unless asked for. See `docs/uat/relevance-rating.md`.

Only gigs the freelancer could apply to are scored: open, application deadline not passed, not their own,
and no application of theirs in any status. A gig that scores exactly 0 shares nothing with the freelancer
and is not recommended. Nothing about what was recommended is stored.

**Every empty state is a plain `200`, with the same response shape as a full one.** Permission problems are
the usual `401` and `403`.

| `available` | `reason` | When |
|---|---|---|
| false | `disabled` | `RECOMMENDATIONS_ENABLED` is off (the default) |
| false | `model_unavailable` | no trained model could be loaded: none trained, files missing or corrupt |
| true | `no_skills` | the freelancer has no skills and no bio, so there is nothing to compare gigs with |
| true | `null`, empty `results` | no gig the freelancer could apply to scores above zero |

**Skill match for clients.** Each applicant in `GET /api/gigs/<gig_id>/applications/` also has:

- `match_score`: the content model's score for that freelancer and that gig, from 0 to 1, or `null`.
- `match_reasons`: the skills they share with the gig.
- `match_band`: `strong`, `good` or `some` skill overlap, and only when at least one skill is really shared.
  `null` otherwise. The cut-offs are the settings `RECOMMENDER_BAND_STRONG` and `RECOMMENDER_BAND_GOOD`, which come
  from the recommender profile (0.27 and 0.13 in production), re-derived on the validation split and provisional.

The response also has `match_scores: {available, reason}`. `match_score` is `null`, never 0, when it cannot be
worked out: no model, or an applicant with no skills and no bio, or an applicant who deleted their account.
A score of 0 means the model compared them and found nothing in common. Only the gig's owner can open this
list, and an applicant's own views of their application never contain these fields.

## Seeding sample data (development only)

Every seed command refuses to run when `DEBUG` is `False`, marks what it creates `is_synthetic`, and needs
the accounts and gigs from the commands before it.

- `python manage.py seed_applications [--per-freelancer N] [--count N] [--seed N] [--delete]` creates
  clearly-fake applications on the seeded open gigs, about 20 per seed freelancer by default (5 more or fewer),
  in a spread of statuses with matching history and a synthetic `apply` interaction. Like the interactions
  below, seeded freelancers favour gigs that share a skill with them, so the applications follow a pattern that
  **favours the content model by construction**. Each application is dated within the last month, after the
  gig was posted and no later than the end of its application deadline day, and each later status comes hours
  or days after the one before (a client can review and hire after the deadline). `--count` stops after that many in
  total. The same seed gives the same rows after a `--delete`. Running again without `--delete` never repeats a
  pair, and may add more if a seeded hire closed a gig. `--delete` removes only the seeded applications and
  puts gigs that a seeded hire moved on back to `open`.
- `python manage.py seed_interactions [--per-freelancer N] [--seed N] [--delete]` creates clearly-fake views,
  search clicks, saves and recommendation clicks from the seed freelancers on the seeded gigs (25 different
  gigs each by default). Gigs that share a skill with the freelancer are about five times more likely to be
  picked, so similar freelancers get similar histories, which is the pattern the collaborative model looks
  for. It is made-up behaviour and says nothing about real freelancers. The same seed gives the same rows,
  and running it again only adds pairs that are not there yet. `--delete` removes the seeded interactions
  and leaves the seeded `apply` rows to `seed_applications`.

To get a development database where both recommender models run:

```
python manage.py seed_data --count 30
python manage.py seed_gigs
python manage.py seed_applications
python manage.py seed_interactions
python manage.py import_job_corpus
python manage.py train_recommender
```

`seed_gigs` is only needed once. With the defaults this gives 30 seed freelancers and about 890 pairs, well
above the collaborative model's minimums (10 freelancers, 20 gigs and 100 pairs).

## Evaluation split

`python manage.py build_evaluation_split [--include-synthetic | --no-include-synthetic] [--seed N]
[--rebuild-split]` builds the 70/15/15 split used to evaluate the recommender and saves it to
`datasets/platform/evaluation/` (gitignored, real user data). Each freelancer's applications are put in time
order: the oldest 70% go to train, the next 15% to validation and the newest 15% to test. A freelancer needs at
least 5 applications to be split (3, 1 and 1 at 5); those with fewer stay in train only and are counted
separately. A saved split is loaded again on later runs so results stay comparable, until `--rebuild-split` is
given or the synthetic setting changes. The command prints the counts for each part, how many are synthetic,
how many freelancers can be evaluated, and how many candidate gigs each gets "as of" the held-out period. It
trains and scores nothing. Each freelancer has their own cut-off, so one freelancer's training period can
include events that happened after another freelancer's test event.

## Measuring the recommender

`python manage.py evaluate_recommender [--split validation|test] [--final] [--include-synthetic |
--no-include-synthetic] [--seed N] [--random-seeds N] [--rebuild-split] [--data-dir PATH] [--output-dir PATH]`
loads or builds the split above, fits the models on the train part only, scores a held-out part and writes a
report and a CSV of every number to `datasets/reports/` (gitignored): `evaluation-YYYY-MM-DD.md` and
`evaluation-YYYY-MM-DD.csv`, with `-2`, `-3` and so on if there is already one from today. Nothing is saved to the
live model, and nothing is tuned.

- **Methods compared**, on the same candidates: random (averaged over 20 seeds, with the spread), popularity (the
  gigs most freelancers applied to in train), content only, collaborative on applications and hiring only (as
  the proposal describes it), collaborative on all interactions (as built), and the hybrid at the current settings.
- **Metrics**: precision, recall and F1 at K = 5 and 10 are the headline. K = 20 and hit rate are supplementary.
  Every average has a 95% bootstrap interval over freelancers and the number of freelancers behind it. Freelancers
  in cold start are reported apart from the rest, and the shortlisted-or-hired reading of relevance is reported
  separately with a warning when too few freelancers qualify.
- **Validation by default.** `--split test` is refused unless `--final` is also given, and every test run is
  appended to `evaluation-test-runs.csv` next to the reports. Every report says how many times the test part has
  been scored. Use the test part once, after tuning on validation is finished.
- **Warning for synthetic data.** When more than half of the scored applications are synthetic, the report starts
  with a warning: results on synthetic data mostly show the models recovering the rules the seed generator
  used, and skill-preferring synthetic applications favour the content model by construction.
- A saved split is reused so results stay comparable. If the applications have changed since it was saved, the
  report says so and `--rebuild-split` uses the current data.

## Timing the recommendations endpoint

`python manage.py time_recommendations [--extra-open-gigs N] [--requests N] [--freelancers N]` times
`/api/recommendations/` through the full request stack for the verified freelancers with skills and prints the
median, 95th percentile and worst response time, the first request after loading, and the database queries per
request. `--extra-open-gigs` adds that many open gigs for the measurement inside a transaction that is rolled back,
so nothing is left in the database. The results are in `docs/recommender.md`, "Performance".

## Tuning the hybrid

`python manage.py tune_recommender [--include-synthetic | --no-include-synthetic] [--seed N] [--random-seeds N]
[--rebuild-split] [--output-dir PATH]` tries 240 combinations of the hybrid settings on the **validation** part
only: the largest collaborative weight (0, 0.25, 0.5, 0.75, 1), the ramp (5, 20, 50 gigs), the hidden factors (2,
5, 10 and the cap) and the cold-start threshold (0, 3, 5, 10). Every combination goes into
`tuning-YYYY-MM-DD.csv`, and `tuning-YYYY-MM-DD.md` says how the choice was made and what it decided, next to
content only, collaborative only and the best hybrid. The interaction weights are not tuned. A combination is
picked by the mean of F1@5 and F1@10, and the defaults should change only if it beats the current settings by
more than the random baseline's spread and the paired 95% interval is above zero. The command never changes a
setting and cannot reach the test part. It also re-derives the match band cut-offs, still provisional.

## Is there anything for the collaborative model to learn?

`python manage.py check_collaborative_readiness [--draws N] [--rebuild-split] [--output-dir PATH]` reads the train
part of the split and reports the explained-variance curve of the collaborative matrix (the share k hidden factors
explain) against two kinds of random matrix: the same shape and values in random cells, and the same number of
cells per freelancer and per gig (which keeps popularity). Beating the second means freelancers share tastes, not
just popular gigs. The data shows structure when, at some k, it beats the random mean by more than three standard
deviations and by at least one percentage point. Writes `readiness-YYYY-MM-DD.md`.

## The planted seed mode (synthetic_planted)

A second seed mode beside the skill-overlap seed above, for checking that the pipeline finds a collaborative
pattern when one exists. **It demonstrates pipeline mechanics, not real-world accuracy**, and every report made from
it starts with that label. It never sets the live defaults.

- About 250 freelancers, 300 gigs and 60 clients, with 15 to 25 applications per freelancer. A hidden popularity per
  gig means the median gig has well over 5 applicants.
- Each freelancer belongs to one of five hidden taste groups: quick_cash (short window or short job, lower budget),
  premium (higher budget, negotiable, a client with a verified phone), remote_only, client_loyal (two favourite
  clients among the ten that post the most) and cross_field (one neighbouring category whose skills they do not
  have). About 40% of each freelancer's applications follow their group, 40% skill overlap and 20% chance.
- Habits only use budget, urgency, client, location and posting date, which the content model does not read. Gig
  text is made from the category and skills alone.
- The groups are written to `datasets/synthetic_planted/ground_truth.csv`, never to the database. They are read only
  after the models are fitted, to score how well the collaborative factors recover them.

It lives in a database of its own, so it can never mix with other data or touch the ordinary split and its test
part. `seed_planted` refuses to write into a database that holds any other account. In a planted database the split
is saved in `datasets/platform/evaluation/synthetic_planted/`, reports are named `evaluation-synthetic_planted-...`,
`tuning-synthetic_planted-...` and `readiness-synthetic_planted-...`, and test runs have their own log.

The world is dated up to the day it is written: gigs were posted in the last 1 to 36 days, so about a third of them
are still open on that day and already have applicants. To set it up (PowerShell, from `backend/`), create an empty
database called `gigconnect_planted` in PostgreSQL, then run it under the demo profile, which always uses that
database (see the README, "Recommender profiles and the planted demo"):

```
$env:RECOMMENDER_PROFILE = "demo"
python manage.py migrate
python manage.py refresh_planted_demo
python manage.py check_collaborative_readiness --rebuild-split
python manage.py tune_recommender
Remove-Item Env:RECOMMENDER_PROFILE
```

- `refresh_planted_demo` rebuilds the world for today (same seed), retrains the demo model into its own folder, makes
  the demo accounts and prints the open-gig count and each demo account's top 5. It only runs under the demo profile.
- `show_planted_demo` prints the demo again without rebuilding.
- `seed_planted [--seed N] [--delete]` writes or removes the world on its own, without the demo accounts or training.

A rebuild changes the dates, so the next evaluation notes that the saved planted split is out of date and
`--rebuild-split` builds it again.

## The one-shot test

Each mode's test part has been scored once (`evaluate_recommender --split test --final`), with its own chosen settings:
the skill-overlap data under the production profile (content only) and the planted data under the demo profile. The
reports are `evaluation-2026-10-25-2.md` and `evaluation-synthetic_planted-2026-10-25.md` in `datasets/reports/`, and
each run is in its own test-run log. Neither test part should be scored again.
