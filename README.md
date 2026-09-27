# GigConnect

A gig marketplace platform for the Kenyan digital labour market  a final-year capstone
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
- Node.js 20+ (Vite is pinned to `^6.3.5` on purpose Node 20.18 doesn't support the native
  Rolldown binding Vite 7/8 require; do not upgrade Vite without also upgrading Node to ≥20.19)
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
variables see `frontend/.env.example`.

## Database

`docker-compose up -d` starts a local Postgres 16 on port **5432** with the
`gigconnect`/`gigconnect` user/database, matching `backend/.env.example`.

If you run Postgres natively instead (as this project's own dev machine does), your instance
may listen on a different port  for example, a native Windows Postgres install commonly ends
up on **3204**, not the default 5432. Whatever your actual port is, set `DB_PORT` in
`backend/.env` to match; don't assume 5432 just because that's the Docker default.

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

- `main` — protected, always deployable, updated only via reviewed pull requests
- `develop` — integration branch for work in progress
- Feature branches off `develop`, named `type/<issue-number>-short-description`
  (e.g. `feat/12-seed-command`, `chore/9-ci-workflow`, `fix/15-gig-status-bug`)
- Open a pull request into `develop` referencing the issue it closes (`Closes #<n>`); merge to
  `main` happens from `develop` once a milestone is stable

## Commit convention

[Conventional Commits](https://www.conventionalcommits.org/): `type: short summary`, for
example `feat: add gig status transition endpoint`, `fix: resolve profile photo URL bug`,
`docs: add API endpoint reference`, `chore: add root .gitignore`, `refactor: extract skill
picker component`, `test: add gig ownership permission tests`.
