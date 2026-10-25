# GigConnect

A gig marketplace platform for the Kenyan digital labour market. A final-year capstone
project (BSc Informatics & Computer Science, Strathmore University). GigConnect centralises
gig posting and applications, priced and structured for the Kenyan market (KES, local
categories), and will integrate a hybrid ML recommendation engine (TF-IDF/cosine similarity +
Truncated SVD) in a later sprint.

## Stack

- **Backend:** Django 5 + Django REST Framework + PostgreSQL, JWT auth via
  `djangorestframework-simplejwt` (30-min access tokens, 7-day refresh tokens, rotation +
  blacklist on rotation)
- **Frontend:** React 19 + Vite 6 + Tailwind CSS v3

## Prerequisites

- Python 3.12+
- Node.js 20+ (Vite is pinned to `^6.3.5` on purpose, since Node 20.18 doesn't support the
  native Rolldown binding Vite 7/8 require; do not upgrade Vite without also upgrading Node to
  ≥20.19)
- PostgreSQL 15+ (native install, or via `docker-compose up -d`)

## Backend setup

```bash
cd backend
python -m venv venv
venv/Scripts/activate       # venv\Scripts\activate on Windows cmd
pip install -r requirements.txt
cp .env.example .env        # then edit DB_* values to match your Postgres setup
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API serves at `http://localhost:8000`.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The app serves at `http://localhost:5173` and proxies `/api/*` requests to the backend on
port 8000 (see `frontend/vite.config.js`). The frontend currently has no required environment
variables; see `frontend/.env.example`.

## Database

`docker-compose up -d` starts a local Postgres 16 on port **5432** with the
`gigconnect`/`gigconnect` user/database, matching `backend/.env.example`.

If you run Postgres natively instead (as this project's own dev machine does), your instance
may listen on a different port. For example, a native Windows Postgres install commonly ends
up on **3204**, not the default 5432. Whatever your actual port is, set `DB_PORT` in
`backend/.env` to match; don't assume 5432 just because that's the Docker default.

## Recommender profiles and the planted demo

The recommender runs under one of two profiles, chosen by the `RECOMMENDER_PROFILE` environment variable. The values
live in `backend/config/recommender_profiles.json`, not in code.

| | production (the default) | demo |
|---|---|---|
| Database | the ordinary one (`DB_NAME`, normally `gigconnect`) | `gigconnect_planted`, always |
| Largest collaborative weight | 0, so recommendations are content only | 0.5 |
| Ramp, factors, cold start | 20 gigs, 20 factors, below 5 gigs | 50 gigs, 2 factors, below 10 gigs |
| Match band cut-offs (good, strong) | 0.13, 0.27 | 0.35, 0.6 |
| Trained models and snapshot | `recommendations/artifacts/`, `datasets/platform/` | `recommendations/artifacts/demo/`, `datasets/platform/demo/` |
| Where the values come from | tuning on the skill-overlap seed data | tuning on the planted data |

- If the variable is missing, production is used. Any other name is refused.
- The demo profile refuses to start unless it is connected to the planted database, and only planted accounts are in
  it. It is labelled **synthetic_planted - demonstrates pipeline mechanics, not real-world accuracy** in the admin
  header and in every report. Every report also names the profile it was made under.
- Recommendations are worked out on each request and never stored, so switching the profile and restarting the server
  is all it takes. There is nothing to regenerate.

How the demo blends: a freelancer below 10 different gigs gets content scores only. From 10 gigs the collaborative
share rises by 0.5 / 50 = 1 point per gig, so 0 at 0 or 5 gigs, 1% at 10, 11% at 20 and 31% at 40, until it reaches
50%. The planted freelancers have 15 to 25 applications, so their share is between 3% and 16%.

### Running the demo

Once, create an empty PostgreSQL database called `gigconnect_planted`, then from `backend/` (PowerShell):

```powershell
$env:RECOMMENDER_PROFILE = "demo"
python manage.py migrate
python manage.py refresh_planted_demo
python manage.py runserver
```

`refresh_planted_demo` rebuilds the planted world dated up to today (the same seed, so the same world), retrains the
demo model, makes the demo accounts and prints how many gigs are open today and each demo account's top 5. Run it the
day before a presentation, because the planted gigs close as the days pass. `show_planted_demo` prints the same
without rebuilding anything. To go back to production, close that terminal or run `Remove-Item Env:RECOMMENDER_PROFILE`
and restart the server.

### Demo accounts

All of them sign in with the demo password `DemoPass123!`. They exist only in the planted database: a local demo on
synthetic accounts, never real ones.

| Account | Email | What it shows |
|---|---|---|
| Amina Wanjiru | `planted-amina@example.test` | A premium freelancer: higher budget, negotiable gigs from verified clients |
| Brian Otieno | `planted-brian@example.test` | A quick_cash freelancer: short, urgent, lower budget gigs |
| Cynthia Achieng | `planted-cynthia@example.test` | A remote_only freelancer: remote gigs |
| David Kamau | `planted-david@example.test` | A brand-new freelancer with no applications: skill matches only (cold start) |

Each of the first three is the member of their hidden group whose top 5 recommendations show the group's habit most
clearly. The habit only shows in the gigs the collaborative part pulls in, which are often gigs that share no skill with
them (a content score of 0). The groups themselves are only in `datasets/synthetic_planted/ground_truth.csv`.

## Tests

```bash
cd backend
python manage.py test
```

78 tests across `accounts`, `profiles`, `usersettings`, and `gigs` as of Sprint 2.

## Project structure

```
backend/    Django project (config/) + apps: accounts, profiles, usersettings, gigs
frontend/   React + Vite + Tailwind app
data/       Seed data and loading instructions
docs/       API endpoint reference and ERD
docker-compose.yml   Local Postgres for development
```

## Branching strategy

- `main`: protected, always deployable, updated only via reviewed pull requests
- `develop`: integration branch for work in progress
- Feature branches off `develop`, named `type/<issue-number>-short-description`
  (e.g. `feat/12-seed-command`, `chore/9-ci-workflow`, `fix/15-gig-status-bug`)
- Open a pull request into `develop` referencing the issue it closes (`Closes #<n>`); merge to
  `main` happens from `develop` once a milestone is stable

## Commit convention

[Conventional Commits](https://www.conventionalcommits.org/): `type: short summary`, for
example `feat: add gig status transition endpoint`, `fix: resolve profile photo URL bug`,
`docs: add API endpoint reference`, `chore: add root .gitignore`, `refactor: extract skill
picker component`, `test: add gig ownership permission tests`.
