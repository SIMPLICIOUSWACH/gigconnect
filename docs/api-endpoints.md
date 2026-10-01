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
| GET | `/api/settings/export-data/` | Required | JSON export of the user's own data |
| POST | `/api/settings/delete-account/` | Required | Soft-delete (anonymise + deactivate) the account |

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
| GET | `/api/gigs/mine/` | Required (client) | List the logged-in client's own gigs, all statuses |

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
| `skills` | string | Comma-separated skill ids or names (case-insensitive); matches **any** of them |
| `budget_min`, `budget_max` | decimal | Range **overlap**, not containment — a gig matches if its own budget range overlaps the requested one at all |
| `negotiable` | bool | `true`/`false`; omit to not filter on it |
| `include_closed` | bool | `true` lifts the default `status=open` + unexpired-deadline restriction entirely, returning every gig regardless of status or application deadline. Default `false` |
| `deadline_before` | date (`YYYY-MM-DD`) | Project deadline on or before this date |
| `posted_within` | int | One of `1`, `7`, `30` (days) |
| `sort` | string | `newest` (default), `deadline`, `budget_high`, `budget_low`, `relevance` |
| `page`, `page_size` | int | Default page size 12, max 50 |

**`sort=relevance` with no `q`:** relevance ranks by PostgreSQL's `ts_rank` against the search
query, which is meaningless with an empty query. Rather than erroring or returning an arbitrary
order, this combination silently falls back to `sort=newest` — the same behaviour as omitting
`sort` entirely. This is deliberate (see `GigFilterSerializer.validate()` in `gigs/filters.py`),
not a bug: a client that lets the user pick "Best match" before typing anything should still get
a sensible, stable order rather than a 400 or undefined ordering.

Response shape: `{count, page, page_size, total_pages, next, previous, results: [...]}`.

## Not yet built

Applications (Sprint 4) and the recommendation engine (Sprint 5) have no endpoints yet.
`GigDetail` on the frontend shows a disabled "Apply" placeholder rather than a working button.
