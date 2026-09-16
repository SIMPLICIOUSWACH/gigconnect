# GigConnect

A gig marketplace platform for the Kenyan digital labour market. Centralises gig
posting, applications, and (in a later sprint) a hybrid ML recommendation engine
matching freelancers to gigs.

- **Backend:** Django 5 + Django REST Framework + PostgreSQL, JWT auth (SimpleJWT)
- **Frontend:** React 19 + Vite + Tailwind CSS

## Prerequisites

- Python 3.12+
- Node.js 20+
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

The app serves at `http://localhost:5173` and proxies `/api` requests to the
backend on port 8000 (see `frontend/vite.config.js`).

## Database

`docker-compose up -d` starts a local Postgres 16 on port 5432 with the
`gigconnect`/`gigconnect` user/database, matching `backend/.env.example`. If you
run Postgres natively instead, update `backend/.env` to match your host/port/
credentials.

## Tests

```bash
cd backend
python manage.py test
```

## Project structure

```
backend/    Django project (config/) + apps (accounts, profiles, ...)
frontend/   React + Vite + Tailwind app
docker-compose.yml   Local Postgres for development
```
