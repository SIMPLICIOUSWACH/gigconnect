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
| GET | `/api/meta/counties/` | None | The 47 Kenya counties as `{value, label}`; the single source the frontend reads |
| GET | `/api/skills/` | None | List all skills |
| POST | `/api/skills/` | Required | Get or create a skill (see "Skill creation" below). Rate limited to 30 per hour |
| GET | `/api/profiles/<user_id>/` | Required | Public-safe view of any user's profile (no email/phone/id_number) |
| PATCH | `/api/profile/complete/` | Required | Update bio, optional county, photo and skills (freelancer) or company info and logo (client) |
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
| GET | `/api/settings/export-data/` | Required | JSON export of the user's own data, including `gig_interactions` (the gigs they viewed or opened from search) |
| POST | `/api/settings/delete-account/` | Required | Soft-delete (anonymise and deactivate) the account, and delete that user's gig interactions outright |

## Gigs (`/api/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/categories/` | None | List gig categories |
| GET | `/api/gigs/` | None | List gigs: paginated, filtered, searched (see below) |
| POST | `/api/gigs/` | Required (client, email-verified) | Create a gig. `currency` must be `KES` if given at all (any other value is a 400) |
| GET | `/api/gigs/<id>/` | None | Full gig detail. Counts a view (see "View counts" below). Reachable by id regardless of status, deadline or `is_synthetic` |
| PUT | `/api/gigs/<id>/` | Required (owning client) | Update a gig, only while `status = open` |
| DELETE | `/api/gigs/<id>/` | Required (owning client) | Delete a gig |
| PATCH | `/api/gigs/<id>/status/` | Required (owning client) | Change status, restricted to valid transitions (see below). Disabled on the main detail route, so this is the only way to change status |
| GET | `/api/gigs/mine/` | Required (client) | List the logged-in client's own gigs, all statuses |
| POST | `/api/gigs/<id>/interactions/` | None | Log that the visitor opened this gig from search results (see below) |

**Status transitions:** `open → in_progress → completed`, or `open`/`in_progress → closed`
(cancellation). No direct `open → completed`; no changes once `completed` or `closed`.

### `GET /api/gigs/` query parameters

By default the feed only returns gigs where `status = open` and `application_deadline` has not
passed. All parameters below are optional and combine with AND. Invalid values (an unknown
category slug, `budget_min > budget_max`, an out-of-range `posted_within`, an unrecognised
`sort`) return `400` with a field-level error rather than a silent no-op or a 500.

| Param | Type | Notes |
|---|---|---|
| `q` | string | Full-text search (title weight A, skills weight B, description weight C) via PostgreSQL `websearch_to_tsquery`, so stray punctuation can't cause a syntax error. Typo tolerant: see below |
| `category` | string | Category slug, exact match |
| `skills` | string | Comma-separated skill ids or names (case-insensitive) |
| `skills_mode` | string | `any` (default): the gig has at least one of the skills. `all`: it has every one; a skill that doesn't exist means no results |
| `budget_min`, `budget_max` | decimal | Range **overlap**, not containment: a gig matches if its own budget range overlaps the requested one at all |
| `negotiable` | bool | `true`/`false`; omit to not filter on it |
| `county` | string | One of the 47 counties (exact name, for example `Nairobi`). An unknown county is a 400 |
| `remote` | bool | `true` returns only remote gigs, `false` excludes them; omit to not filter. Combines with `county` using AND |
| `include_closed` | bool | `true` lifts the default `status=open` + unexpired-deadline restriction entirely, returning every gig regardless of status or application deadline. Default `false` |
| `deadline_before` | date (`YYYY-MM-DD`) | Project deadline on or before this date |
| `posted_within` | int | One of `1`, `7`, `30` (days) |
| `sort` | string | `newest` (default), `deadline`, `budget_high`, `budget_low`, `relevance` |
| `page`, `page_size` | int | Default page size 12, max 50 |

**`sort=relevance`:** ranks by the number of matched `skills` first (when given), then by the text
search rank (when `q` is given), then newest. With neither `q` nor `skills` there is nothing to
rank by, so rather than erroring or returning an arbitrary order the request silently falls back
to `sort=newest`, the same behaviour as omitting
`sort` entirely. This is deliberate (see `GigFilterSerializer.validate()` in `gigs/filters.py`),
not a bug: a client that lets the user pick "Best match" before typing anything should still get
a sensible, stable order rather than a 400 or undefined ordering.

Response shape: `{count, page, page_size, total_pages, next, previous, results: [...]}`. Each gig
includes `county` and `is_remote` alongside the fields above.

**Typo tolerance.** If full-text search on `q` finds fewer than `SEARCH_FALLBACK_MIN_RESULTS` gigs
(default 5, counted after the other filters), results are topped up with gigs whose title or
description has a trigram word similarity of at least `SEARCH_TRIGRAM_THRESHOLD` (default 0.25)
with `q`, so "pyhton" finds a Python gig. Under `sort=relevance`, exact matches rank above fuzzy
ones. The threshold is 0.25 rather than pg_trgm's usual 0.3 because a one-letter transposition
scores only about 0.27.

**Synthetic data.** Gigs created by the seed and data-pipeline commands have `is_synthetic = true`.
The feed hides them unless the `SHOW_SYNTHETIC` setting is on (it defaults to `DEBUG`). They stay
reachable by id and in the owner's `/api/gigs/mine/`.

### `POST /api/gigs/<id>/interactions/`

Body: `{"type": "search_click", "query": "<optional text, max 200 chars>", "position": <optional
rank in the results, 1 to 10000>}`. Returns `201` with no body. Works for anonymous visitors
(identified by session) and signed-in users. `type` must be `search_click`: views are logged by the
server, and `save` and `apply` have their own flows, so those values are a 400. Rate limited to 300
requests per hour. These rows are training data for the Sprint 5 recommender.

### View counts

`GET /api/gigs/<id>/` counts a view at most once per viewer (the user, or the session for anonymous
visitors) per gig per 24 hours, and never when the gig's own client is the viewer. The increment is
atomic. Each counted view is also stored as a `view` interaction. A client that sends no cookies
gets a new session on every request, so it is counted every time.

### Skill creation

`POST /api/skills/` with `{"name": "...", "category": "<optional>"}` needs authentication and
returns the skill, creating it only if it is new. Names are trimmed and have whitespace collapsed;
matching ignores case and spacing, and known aliases resolve to their canonical skill, so posting
`ReactJS` returns `React`. Names are rejected (400, with a message under `name`) if shorter than 2
or longer than 50 characters, if they contain no letters or numbers, or if they contain a web
address. The `skills` filter on `GET /api/gigs/` resolves names and aliases the same way.

## Not yet built

Applications (Sprint 4) and the recommendation engine (Sprint 5) have no endpoints yet.
`GigDetail` on the frontend shows a disabled "Apply" placeholder rather than a working button.
