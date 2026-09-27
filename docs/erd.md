# Entity Relationship Diagram

Core domain entities as of Sprint 2. `NotificationPreference`, `UserSession`, and `OTP`
(supporting tables in `accounts`/`usersettings`) are omitted from the diagram to keep it
readable — see `backend/*/models.py` for their full definitions.

```mermaid
erDiagram
    USER ||--o| CLIENT_PROFILE : "has (if role=client)"
    USER ||--o| FREELANCER_PROFILE : "has (if role=freelancer)"
    USER ||--o{ GIG : posts
    FREELANCER_PROFILE }o--o{ SKILL : "lists (implicit M2M)"
    FREELANCER_PROFILE ||--o{ PORTFOLIO_ITEM : has
    GIG }o--|| CATEGORY : "belongs to"
    GIG }o--o{ SKILL : "requires (via GigSkill)"

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
```

Note: `User` does not have a single `Profile` — the profile is split into `ClientProfile` and
`FreelancerProfile` depending on `role`, each auto-created via a `post_save` signal. There is
no `county` field on any model yet.
