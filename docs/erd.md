# Entity Relationship Diagram

Core domain entities as of Sprint 3.1. `NotificationPreference`, `UserSession` and `OTP`
(supporting tables in `accounts` and `usersettings`) are left out of the diagram to keep it
readable. See `backend/*/models.py` for their full definitions. `Application` and
`ApplicationStatusEvent` arrive in Sprint 4.

```mermaid
erDiagram
    USER ||--o| CLIENT_PROFILE : "has (if role=client)"
    USER ||--o| FREELANCER_PROFILE : "has (if role=freelancer)"
    USER ||--o{ GIG : posts
    USER |o--o{ GIG_INTERACTION : "performs (null for anonymous visitors)"
    FREELANCER_PROFILE }o--o{ SKILL : "lists (implicit M2M)"
    FREELANCER_PROFILE ||--o{ PORTFOLIO_ITEM : has
    GIG }o--|| CATEGORY : "belongs to"
    GIG ||--o{ GIG_SKILL : has
    SKILL ||--o{ GIG_SKILL : "required by"
    GIG ||--o{ GIG_INTERACTION : receives
    SKILL ||--o{ SKILL_ALIAS : "known as"

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
        bool is_synthetic "seed and pipeline accounts"
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
        string county "nullable, one of the 47 counties"
        image profile_photo
        string id_number "write-only, never serialized"
        file id_document
        string verification_status "unverified/pending/verified/rejected"
    }

    SKILL {
        uuid id PK
        string name UK "display name"
        string normalized_name "case-folded, used for matching"
        string category
    }

    SKILL_ALIAS {
        uuid id PK
        string alias "for example ReactJS, JS, MS Excel"
        string normalized_alias UK
        uuid skill_id FK "the canonical skill"
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
        string title "GIN trigram index"
        text description "GIN trigram index"
        decimal budget_min
        decimal budget_max
        string currency "KES only for new gigs"
        date deadline "project delivery date"
        date application_deadline "last day to apply, defaults to deadline"
        bool is_negotiable
        string county "nullable, one of the 47 counties"
        bool is_remote
        string status "open/in_progress/completed/closed"
        int view_count "once per viewer per 24h, never the owner"
        tsvector search_vector "title A, skills B, description C, GIN index"
        bool is_synthetic
        datetime created_at
        datetime updated_at
    }

    GIG_SKILL {
        uuid id PK
        uuid gig_id FK
        uuid skill_id FK "unique with gig_id"
    }

    GIG_INTERACTION {
        uuid id PK
        uuid user_id FK "nullable"
        string session_key "set for anonymous visitors"
        uuid gig_id FK
        string type "view / search_click / save / apply"
        text query "nullable, the search text"
        int position "nullable, rank in the results"
        datetime created_at
        bool is_synthetic
    }
```

## Notes

- `User` does not have a single `Profile`. The profile is split into `ClientProfile` and
  `FreelancerProfile` depending on `role`, each created by a `post_save` signal. The
  `is_synthetic` flag lives on `User` and covers the profile rows that hang off it.
- Counties come from one list in `backend/profiles/counties.py`. Both `county` columns take their
  choices from it, and the frontend reads it from `GET /api/meta/counties/`.
- `Gig.search_vector` is kept current by `post_save` and `m2m_changed` signals. Anything that
  bypasses them (`bulk_create`, `QuerySet.update()`, a skill rename, a skill merge) needs
  `python manage.py rebuild_search_vectors` afterwards.
- `GigInteraction` rows of type `view` are written by the gig detail endpoint and double as the
  record used to count a view only once per viewer per 24 hours. `search_click` comes from the
  Browse page. `apply` is written by the applications flow in Sprint 4, and `save` has no
  producer yet.
- Indexes on `gigs_gig`: GIN on `search_vector`, GIN trigram on `title` and on `description`, and B-tree on
  `(status, created_at)`, `(status, category)`, `deadline`, `application_deadline`, `budget_min`
  and `budget_max`. On `gigs_giginteraction`: `(user, gig)` and `(type, created_at)`.
