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
| GET | `/api/gigs/` | None | List all **open** gigs (lightweight payload, no full description) |
| POST | `/api/gigs/` | Required (client, email-verified) | Create a gig |
| GET | `/api/gigs/<id>/` | None | Full gig detail; increments `view_count` |
| PUT | `/api/gigs/<id>/` | Required (owning client) | Update a gig — only while `status = open` |
| DELETE | `/api/gigs/<id>/` | Required (owning client) | Delete a gig |
| PATCH | `/api/gigs/<id>/status/` | Required (owning client) | Change status — restricted to valid transitions (see below); disabled on the main detail route, this is the only way to change status |
| GET | `/api/gigs/mine/` | Required (client) | List the logged-in client's own gigs, all statuses |

**Status transitions:** `open → in_progress → completed`, or `open`/`in_progress → closed`
(cancellation). No direct `open → completed`; no changes once `completed` or `closed`.

## Not yet built

Applications (Sprint 4) and the recommendation engine (Sprint 5) have no endpoints yet.
`GigDetail` on the frontend shows a disabled "Apply" placeholder rather than a working button.
