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

A `seed_data` management command (`python manage.py seed_data`) is planned to generate
synthetic clients and freelancers for local development and demos. Tracked as a Sprint 0 issue;
this section will be updated with usage instructions once it lands.

**Known gap:** no current model (`ClientProfile`, `FreelancerProfile`, or `Gig`) has a `county`
field, and there's no county list in the frontend to reuse. The seed command will generate data
using the fields that actually exist today (skills, bio, company info, etc.) rather than
fabricating county values — adding a real `county` field is a product decision for a later
sprint, not something to smuggle in via a seeding script.

## `seed/`

Reserved for static fixtures (e.g. a JSON export) if a need for one comes up later. Currently
empty — the synthetic data above is generated programmatically, not loaded from a file here.
