# Entity Relationship Diagram

Core domain entities as of Sprint 4. `NotificationPreference`, `UserSession`, `OTP`, `SkillAlias`
and `GigInteraction` (supporting tables) are omitted from the diagram to keep it readable, and some
columns added since Sprint 2 (such as `county`, `is_remote` and `is_synthetic`) are only listed
where they matter here. See `backend/*/models.py` for the full definitions.

```mermaid
erDiagram
    USER ||--o| CLIENT_PROFILE : "has (if role=client)"
    USER ||--o| FREELANCER_PROFILE : "has (if role=freelancer)"
    USER ||--o{ GIG : posts
    FREELANCER_PROFILE }o--o{ SKILL : "lists (implicit M2M)"
    FREELANCER_PROFILE ||--o{ PORTFOLIO_ITEM : has
    GIG }o--|| CATEGORY : "belongs to"
    GIG }o--o{ SKILL : "requires (via GigSkill)"
    GIG ||--o{ APPLICATION : receives
    USER ||--o{ APPLICATION : "submits (freelancer)"
    APPLICATION ||--|{ APPLICATION_STATUS_EVENT : "history"
    USER |o--o{ APPLICATION_STATUS_EVENT : "changed_by (null = system)"

    USER {
        uuid id PK
        string email UK
        string full_name
        string phone
        string role "client / freelancer / admin"
        bool is_email_verified
        bool is_phone_verified
        bool is_profile_complete
        datetime deleted_at "soft-delete"
    }

    CLIENT_PROFILE {
        uuid id PK
        uuid user_id FK
        string company_name
        string industry
        image company_logo
    }

    FREELANCER_PROFILE {
        uuid id PK
        uuid user_id FK
        string bio "max 300 chars"
        image profile_photo
        string id_number "write-only, never serialized"
        file id_document
        string verification_status "unverified/pending/verified/rejected"
    }

    SKILL {
        uuid id PK
        string name UK
        string category
    }

    PORTFOLIO_ITEM {
        uuid id PK
        uuid freelancer_id FK
        string title
        text description
        string link
        image image
    }

    CATEGORY {
        uuid id PK
        string name UK
        string slug UK
    }

    GIG {
        uuid id PK
        uuid client_id FK
        uuid category_id FK
        string title
        text description "GIN trigram index"
        decimal budget_min
        decimal budget_max
        string currency "default KES"
        date deadline
        string status "open/in_progress/completed/closed"
        int view_count
    }

    APPLICATION {
        uuid id PK
        uuid gig_id FK
        uuid freelancer_id FK
        text cover_letter "50 to 3000 characters"
        string portfolio_link "optional"
        decimal proposed_rate "optional, KES, more than 0"
        string status "pending/under_review/shortlisted/hired/rejected/withdrawn"
        datetime created_at
        datetime updated_at
        bool is_synthetic
    }

    APPLICATION_STATUS_EVENT {
        uuid id PK
        uuid application_id FK
        string from_status "blank for the first event"
        string to_status
        uuid changed_by_id FK "null when the system made the change"
        text note "optional"
        datetime created_at
    }
```

Note: `User` does not have a single `Profile` — the profile is split into `ClientProfile` and
`FreelancerProfile` depending on `role`, each auto-created via a `post_save` signal. `Gig` and
`FreelancerProfile` each have a nullable `county` (one list of counties, served by
`GET /api/meta/counties/`), and `Gig` also has `is_remote`.

## Applications

**Constraints** (enforced by the database, so they hold even if two requests arrive together):

- `unique_application_per_gig`: one application per freelancer per gig. This is also why a
  freelancer who withdraws cannot apply to the same gig again.
- `one_hired_application_per_gig`: at most one `hired` application on a gig.

**Indexes:** `app_freelancer_status_idx` (a freelancer's list, filtered by status) and
`app_gig_status_idx` (a client's applicants list and the My Gigs counts).

**Status rules** live in one module, `backend/applications/transitions.py`, which the API uses and
the frontend reads through `allowed_next_statuses`:

| Who | From | To |
|---|---|---|
| Client | pending | under_review, rejected |
| Client | under_review | shortlisted, rejected |
| Client | shortlisted | hired, rejected |
| Freelancer | pending, under_review | withdrawn |

`hired`, `rejected` and `withdrawn` are final. Every change writes an `ApplicationStatusEvent`.

**When a freelancer deletes their account** (`backend/applications/privacy.py`): their pending,
under review and shortlisted applications are withdrawn with a system event (`changed_by` null),
the cover letter, portfolio link and proposed rate are cleared on all of their applications, and
any reason they typed when withdrawing is cleared from the history. The rows and history stay, so
the client's records and counts still make sense, and a `hired` application stays `hired`. This
is the one place a shortlisted application is withdrawn without going through the normal rules,
because it is a system action and not a choice by the freelancer.
