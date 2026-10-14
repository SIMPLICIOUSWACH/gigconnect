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
| GET | `/api/gigs/<gig_id>/applications/` | Required (the gig's client) | The gig's applicants, newest first, each with the applicant's name, skills, verification, cover letter, link, rate and status history. Query: `status`, `page`, `page_size`. Anyone else gets `403` |
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

## Seeding sample data (development only)

`python manage.py seed_applications [--count N] [--delete]` creates clearly-fake applications on the
seeded open gigs, in a spread of statuses with matching history, each marked `is_synthetic`, with a
synthetic `apply` interaction. It refuses to run when `DEBUG` is `False`, and needs `seed_data` and
`seed_gigs` to have run first. `--delete` removes only the seeded applications and puts gigs that a
seeded hire moved on back to `open`.

## Not yet built

The recommendation engine (Sprint 5) and its evaluation (Sprint 6) have no endpoints yet. The
applicants page leaves a marked spot for the skill match score, which says "Match scores arrive with
the recommendation engine" until then.
