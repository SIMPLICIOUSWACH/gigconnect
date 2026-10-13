# Sprint 4 Review: Application Tracking

**Status: DRAFT.** Written by the assistant from the code, the pull requests and the CI results. The
retrospective and any figure marked "to confirm" need the team's input before this is final.

## Sprint goal

Let a freelancer apply to a gig and follow what happens next, and let a client review applicants and
hire one, with every change recorded and the privacy rules for applications decided and tested.
Epic: #21.

## Stories

| # | Story | Points | Issue | Pull request | State |
|---|---|---|---|---|---|
| 1 | Application model, status events and transition rules | 5 | #37 | #44 | Merged |
| 2 | Apply, withdraw and my-applications endpoints, `apply` interaction logging | 5 | #38 | #45 | Merged |
| 3 | Client review, hiring, and application counts on My Gigs | 5 | #39 | #46 | Merged |
| 4 | Apply flow on Gig Detail and the application page | 5 | #40 | #47 | Merged |
| 5 | Freelancer applications dashboard | 3 | #41 | #48 | Merged |
| 6 | Client applicants page | 5 | #42 | #49 | Open, CI green |
| 7 | Privacy, docs, seed data and tests | 8 | #43 | #50 | Open, CI running at time of writing |

Total planned: 36 points.

Issues #37 to #41 are still open on GitHub even though their pull requests are merged. The
pull requests say `Closes #N`, but GitHub only closes issues when a pull request merges into the
default branch, and these merged into `develop`. They will close when `develop` is released to `main`.

## Done and not done

**Done**

- The `applications` app: `Application` and `ApplicationStatusEvent`, the one-application-per-gig and
  one-hire-per-gig database constraints, and the status rules in a single module.
- Four endpoints for freelancers (apply, my applications, one application, withdraw) and two for
  clients (list applicants, change status), plus `my_application` on the gig detail and
  `application_count` and `pending_application_count` on My Gigs.
- Hiring moves an open gig to `in_progress` and leaves other applicants alone. Nothing is auto-rejected.
- The apply form with inline validation and plain-language server errors, the "Applied" state, the
  application page with a confirmed withdraw, the `/applications` dashboard, and the
  `/gigs/<id>/applicants` page.
- Data export includes applications. Account deletion withdraws open applications, clears personal
  text, and keeps rows and history.
- `seed_applications` (development only), and the API reference and ERD updated.

**Not done, or still open**

- Stories 6 and 7 are built and have passing checks, but their pull requests are not merged yet.
- No recommendation or match score. The applicants page shows a marked spot that says "Match scores
  arrive with the recommendation engine". This is Sprint 5 work.
- The frontend pages for Stories 4 to 6 have been tested with unit tests, but nobody has yet walked
  through them in a browser against a seeded database. This is the main remaining check.
- Notifications to a freelancer when their status changes are not part of this sprint.

## Velocity

Planned 36 points. At the time of writing, 23 points are merged (stories 1 to 5) and 13 points are
in open pull requests (stories 6 and 7). Earlier sprints' velocity is not recorded in the repository,
so no comparison is made here. To confirm: the team's own velocity figures for Sprints 1 to 3.

## Test counts

| | Before Sprint 4 | After Sprint 4 (with #49 and #50) |
|---|---|---|
| Backend tests | 216 | 371 |
| Frontend tests | 28 | 74 |

How these were counted: the backend figures count test functions in `backend/` at the last commit
before Sprint 4 and at the tip of the Story 7 branch. The frontend figures are Vitest's own totals.
The full backend suite was not run to completion on a developer machine, because it is slow
(about 3.5 minutes for the 90 application tests alone). CI ran the whole suite and passed on #45,
#46, #47, #48 and #49. #50 was still running when this was written.

New tests by story: model and rules 35 (#44), apply and list endpoints 48 (#45), client review 37
(#46), privacy 17 and seed 11 (#50). Frontend: apply flow 21 (#47), dashboard 12 (#48), applicants
page 13 (#49).

## New migrations, endpoints and pages

**Migrations:** `applications/0001_initial` (the two tables, constraints and indexes). Nothing else
this sprint.

**Endpoints:**

- `POST /api/gigs/<id>/applications/`
- `GET /api/gigs/<id>/applications/`
- `GET /api/applications/mine/`
- `GET /api/applications/<id>/`
- `POST /api/applications/<id>/withdraw/`
- `PATCH /api/applications/<id>/status/`

Changed responses: `GET /api/gigs/<id>/` (`my_application`), `GET /api/gigs/mine/` (two counts),
`GET /api/settings/export-data/` (`applications`).

**Management command:** `seed_applications`.

**Pages:** `/applications` (freelancer), `/applications/:id`, and `/gigs/:id/applicants` (client).
Changed: Gig Detail (real Apply flow), My Gigs (applicant counts), the navigation and the freelancer
Dashboard.

## Where the build differs from what was planned

I could not compare against the written proposal itself, so this lists behaviour that may not match it.

- **Apply form:** the plan said a separate `/gigs/<id>/apply` page. It was built as a form that opens
  in place on Gig Detail, which the sprint prompt allowed ("modal or page"). It is simpler and the
  application itself is still linkable.
- **Status boxes:** five boxes (total, pending, shortlisted, hired, not selected), as the sprint
  prompt listed. "Pending" counts only `pending`; `under_review` and `withdrawn` appear in the tabs
  only.
- **Wording:** a rejected application is shown to the freelancer as "Not selected".
- **Withdrawing:** a withdrawn application cannot be re-submitted. The unique rule allows one
  application per freelancer per gig, and the error says so.
- **Hiring:** it does not reject other applicants. If the proposal expected that, it differs.
- **Match score:** a labelled placeholder only. No number is calculated or shown.
- **Deleted freelancer:** open applications are withdrawn, including shortlisted ones. That one move
  is a system action and skips the normal freelancer rule on purpose.

## Retrospective (DRAFT, to be completed by the team)

*These are observations from the work, not agreed conclusions.*

**What went well**

- One module for the status rules meant the API, the tests and the buttons on screen all followed the
  same source. The frontend never copies the rules; it shows what the server says is allowed.
- The query-count tests found a real extra database query on the applicants list before it shipped.
- One branch and one pull request per story kept each review small.

**What was harder**

- Test runs are slow on Windows and cannot run in parallel here, which made checking each change take
  minutes.
- Two timestamps created back to back can tie on Windows, which made a test flaky and showed that
  list ordering needed a tiebreaker.
- A development database that is behind on migrations fails at login with an unhelpful error.
- Closing issues from pull requests does not work when merging into `develop`.

**Ideas to try (for discussion)**

- Walk the three new pages in a browser against `seed_applications` data before the release to `main`.
- Use a faster password hasher in test settings to shorten test runs.
- Decide whether hiring should offer to reject the remaining applicants.
