# Data

## Currently seeded (automatic)

Two lookup tables are seeded via Django data migrations, so they load automatically the first
time anyone runs `python manage.py migrate` — no manual step required:

- **Skills** (`backend/profiles/migrations/0002_seed_skills.py`) — 20 starter skills across
  Technology, Design, Writing, Marketing, Media, Business, and Trades categories.
- **Gig categories** (`backend/gigs/migrations/0002_seed_categories.py`) — 8 categories
  reflecting the Kenyan gig market (Web & Software Development, Design & Creative, Marketing &
  Sales, Writing & Content, Admin & Virtual Assistance, Data & Analytics, Video & Photography,
  Local Services).

## Synthetic user data

```bash
cd backend
python manage.py seed_data              # 20 clients + 20 freelancers (default)
python manage.py seed_data --count 50   # 50 of each
```

Creates client accounts (`seed-client-1@example.test`, ...) with a company name and industry,
and freelancer accounts (`seed-freelancer-1@example.test`, ...) with a bio and 1-4 random
skills. All seeded accounts use the password `SeedPass123!` and are created with
`is_email_verified=True` / `is_profile_complete=True` so they're immediately usable for testing
gig posting, browsing, etc. without going through the verification flow.

The command is idempotent — emails are deterministic (`seed-client-<n>@example.test`), so
re-running with the same or a smaller `--count` skips accounts that already exist rather than
erroring or duplicating them. Requires skills to already be seeded (via `migrate`); it warns
and exits without creating anything if `profiles.Skill` is empty.

**Known gap:** no current model (`ClientProfile`, `FreelancerProfile`, or `Gig`) has a `county`
field, and there's no county list in the frontend to reuse. This command deliberately doesn't
fabricate county values — adding a real `county` field is a product decision for a later
sprint, not something to smuggle in via a seeding script. Gig seeding is also out of scope here
(see issue #19) since it depends on realistic category/skill combinations best added once
Sprint 3's browse/search work defines what's worth searching over.

## `seed/`

Reserved for static fixtures (e.g. a JSON export) if a need for one comes up later. Currently
empty — the synthetic data above is generated programmatically, not loaded from a file here.
