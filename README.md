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
python manage.py create_admin --email admin@example.com
python manage.py runserver
```

The API serves at `http://localhost:8000`.

### Admin accounts

Nobody can sign up as an admin. `create_admin` is the only way to make one:

```bash
python manage.py create_admin --email admin@example.com --full-name "Platform Admin"
```

It asks for the password twice and checks it against the password rules. The new account has the admin role,
a verified email, and `is_staff`. Admins log in on the normal login page and land on `/admin`, the
GigConnect admin area. For a script, pass `--noinput` and put the password in `GIGCONNECT_ADMIN_PASSWORD`.

Django's own `/admin/` site is kept for debugging by a superuser (`createsuperuser`). It is not the product's
admin area.

### ID documents

ID uploads are PDF, JPG or PNG files up to 5 MB. They are kept in `PRIVATE_MEDIA_ROOT` (default `backend/private_media/`),
outside the media folder, so no URL reaches them. Admins read them through `/api/admin/verifications/<id>/document/`.
Back this folder up with the database. If you have older uploads, move them once; `manage.py check` warns until you do:

```bash
python manage.py move_id_documents
```

### ID verification with a live selfie

A freelancer uploads their ID, then takes a live selfie holding it, with the camera only (no gallery upload). Before
the photo they see a random challenge, such as "Hold your ID next to your face and show 3 fingers", which works once
and expires after 10 minutes, and they tick a consent box. The check only reaches the admin queue once both the ID and
the selfie are in. Admins compare the two side by side and must tick three checks before Approve works. A rejection
says which part to redo, and the other part is kept.

What the server checks, and what it can't:
- The selfie must be a JPEG or PNG, at most 5 MB and at least 640 x 480. It is re-encoded as a JPEG with all EXIF data
  (location, camera, time) removed.
- It must show exactly one face (OpenCV's Haar cascade). Faces less than a third the size of the largest are ignored,
  so the photo on the ID card held up next to the face doesn't count as a second person.
- The challenge must be the person's own, unused and less than 10 minutes old.
- **The server can't prove a photo is live.** It only knows a fresh challenge was used. The admin checklist covers the
  rest: the reviewer checks the gesture was really done.
- Browsers only allow the camera on `https://` or `localhost`. On a phone, the site has to be on HTTPS.

**Advisory face score.** When the ID is an image (not a PDF), OpenCV's YuNet finds a face in each picture and SFace
gives a similarity score, shown to admins as "System similarity: 0.78, advisory". It never approves or rejects
anything. Without the model files, or for a PDF ID, it says "not available". Download the models once:

```bash
python manage.py fetch_face_models
```

They come from the official [OpenCV Zoo](https://github.com/opencv/opencv_zoo) repository, go into
`backend/face_models/` (not in git), and each download is checked against the SHA-256 published there:

| File | SHA-256 | Size | Licence |
|---|---|---|---|
| `face_detection_yunet_2023mar.onnx` | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` | 232,589 bytes | MIT (Shiqi Yu) |
| `face_recognition_sface_2021dec.onnx` | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` | 38,696,353 bytes | Apache-2.0 |

**Privacy settings in `backend/.env`:**
- `ID_HASH_KEY`: a long random secret. ID numbers are also stored as a keyed hash (HMAC-SHA256) plus the last 3
  digits, so a second account with the same ID can be spotted after the number itself is deleted. Set it once and
  never change it, or old and new hashes won't match. `manage.py check` warns while it is unset. After setting it,
  run `python manage.py rehash_id_numbers` once so ID numbers stored before then get a hash with the new key.
- `PRIVACY_CONTACT_EMAIL`: shown on the privacy page and in the selfie consent text.

**Deleting ID images after 90 days.** `purge_id_images` deletes the ID image, the selfie and the plain ID number 90
days after an admin's final decision, keeping the decision, its dates, the face score and the hash. Deleting an account
does the same at once. Run the purge daily; `--dry-run` only counts. On Windows, schedule it with Task Scheduler, for
example from a command prompt (change the paths to yours):

```bash
schtasks /Create /SC DAILY /ST 02:00 /TN "GigConnect purge ID images" /TR "C:\gigconnect\backend\venv\Scripts\python.exe C:\gigconnect\backend\manage.py purge_id_images"
```

**Chat emails and old chats.** Two more commands keep the chat running. Both take `--dry-run`, which only counts:
- `send_message_emails` emails people about chat messages still unread after 15 minutes (at most one email per chat an
  hour, and only if their "New messages" email setting is on). Run it every 5 minutes. Running it twice never sends
  the same email twice.
- `purge_old_conversations` deletes a whole conversation 12 months after it became read-only (30 days after its gig
  was completed or closed, or as soon as a gig or application is removed or an account is suspended or deleted). Run
  it daily.

```bash
schtasks /Create /SC MINUTE /MO 5 /TN "GigConnect message emails" /TR "C:\gigconnect\backend\venv\Scripts\python.exe C:\gigconnect\backend\manage.py send_message_emails"
```

```bash
schtasks /Create /SC DAILY /ST 02:15 /TN "GigConnect purge old chats" /TR "C:\gigconnect\backend\venv\Scripts\python.exe C:\gigconnect\backend\manage.py purge_old_conversations"
```

### Sending email

By default every email (verification links, notifications) is printed in the terminal running the backend, not sent.
Tests always use Django's in-memory mailbox, whatever is set here. To send real email through a Gmail account:

1. Use a Gmail account just for GigConnect and turn on 2-Step Verification for it.
2. Create an app password: Google Account, Security, App passwords. Gmail rejects the normal account password here.
3. In `backend/.env`, set the email lines from `.env.example`: `EMAIL_BACKEND` to the SMTP backend,
   `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True`, `EMAIL_HOST_USER` to the address,
   `EMAIL_HOST_PASSWORD` to the app password, and `DEFAULT_FROM_EMAIL=GigConnect <the same address>`.
4. Set `FRONTEND_URL` to the address people open the site at, because the links in emails use it.
5. Restart the backend. `python manage.py check` warns if the SMTP backend is on without a login.

Emails go out once the database change behind them is saved. If sending fails, the action still succeeds and the error
is logged: after sign-up the page says the email couldn't be sent and offers Resend, and a signed-in user can resend
from the Dashboard banner. Resending is limited to 5 an hour. Keep `.env` out of git; only `.env.example` is committed.

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
| Largest collaborative weight | 0.5, chosen by hand (tuning picked 0, see `docs/recommender.md`) | 0.5 |
| Ramp, factors, cold start | 20 gigs, 20 factors, below 5 gigs | 50 gigs, 2 factors, below 10 gigs |
| Match band cut-offs (good, strong) | 0.13, 0.27 | 0.35, 0.6 |
| Trained models and snapshot | `recommendations/artifacts/`, `datasets/platform/` | `recommendations/artifacts/demo/`, `datasets/platform/demo/` |
| Where the values come from | tuning on the skill-overlap seed data, except the weight | tuning on the planted data |

- If the variable is missing, production is used. Any other name is refused.
- The demo profile refuses to start unless it is connected to the planted database, and only planted accounts are in
  it. It is labelled **synthetic_planted - demonstrates pipeline mechanics, not real-world accuracy** in the admin
  header and in every report. Every report also names the profile it was made under.
- Recommendations are worked out on each request and never stored, so switching the profile and restarting the server
  is all it takes. There is nothing to regenerate.

How the demo blends: a freelancer below 10 different gigs gets content scores only. From 10 gigs the collaborative
share rises by 0.5 / 50 = 1 point per gig, so 0 at 0 or 5 gigs, 1% at 10, 11% at 20 and 31% at 40, until it reaches
50%. The planted freelancers have 15 to 25 applications, so their share is between 6% and 16%.

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
| Amina Wanjiru | `planted-amina@example.test` | A premium freelancer: higher budget, negotiable gigs from premium clients (a synthetic trait) |
| Brian Otieno | `planted-brian@example.test` | A quick_cash freelancer: short, urgent, lower budget gigs |
| Cynthia Achieng | `planted-cynthia@example.test` | A remote_only freelancer: remote gigs |
| David Kamau | `planted-david@example.test` | A brand-new freelancer with no applications: skill matches only (cold start) |
| Demo Admin | `planted-admin@example.test` | The admin area at `/admin`, on the planted data |
| Baraka Home Services | `planted-demo-client@example.test` | A client who hired Amina, Brian and Cynthia, with sample chats under Messages |

**Sample chats.** `python manage.py seed_demo_conversations` (with `RECOMMENDER_PROFILE=demo`) adds the demo client,
three in-progress gigs with Amina, Brian and Cynthia hired, and a short chat with each, the client writing first.
Running it again replaces them. These gigs and applications are flagged `is_demo_extra` and are never used to train or
evaluate the recommender, so `train_recommender` on the demo sees the same world with or without them. Run it again
after `refresh_planted_demo` or reseeding, which remove them.

The demo admin is made with `create_admin` like any other admin. Its email starts with `planted-` because the demo
profile refuses to start on a database that holds any other kind of account. `seed_planted --delete` removes it with
the rest of the planted world, so run `create_admin` again after reseeding.

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
