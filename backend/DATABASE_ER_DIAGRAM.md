# Database ER Diagram

PostgreSQL schema `kb` (configurable), derived from Alembic head `0011_admin_documents_global_read`.

```mermaid
erDiagram
    USERS {
        uuid id PK
        varchar_255 email UK
        text hashed_password
        varchar_255 full_name "NULL"
        varchar_20 role "admin | user"
        boolean is_active
        boolean is_email_verified
        timestamptz created_at
        timestamptz updated_at
    }

    REFRESH_TOKENS {
        uuid id PK
        uuid user_id FK
        varchar_64 token_hash UK
        varchar_64 token_id UK
        timestamptz expires_at
        timestamptz revoked_at "NULL"
        boolean is_revoked
        timestamptz created_at
        timestamptz updated_at
    }

    EMAIL_VERIFICATION_TOKENS {
        uuid id PK
        uuid user_id FK
        varchar_64 token_hash UK
        timestamptz expires_at
        boolean is_used
        timestamptz used_at "NULL"
        timestamptz created_at
        timestamptz updated_at
    }

    PASSWORD_RESET_TOKENS {
        uuid id PK
        uuid user_id FK
        varchar_64 token_hash UK
        timestamptz expires_at
        boolean is_used
        timestamptz used_at "NULL"
        timestamptz created_at
        timestamptz updated_at
    }

    DOCUMENT_CATEGORIES {
        uuid id PK
        varchar_50 name UK
        text description "NULL"
        timestamptz created_at
        timestamptz updated_at
    }

    DOCUMENTS {
        uuid id PK
        varchar_120 title
        uuid category_id FK
        varchar_255 file_name "NULL"
        text file_path "NULL"
        varchar_50 file_type "NULL"
        varchar_64 content_checksum "NULL"
        text content
        varchar_30 status "uploaded | processing | ready | failed"
        uuid created_by FK "NULL"
        boolean is_global_read
        boolean is_deleted
        timestamptz deleted_at "NULL"
        timestamptz created_at
        timestamptz updated_at
    }

    DOCUMENT_CHUNKS {
        uuid id PK
        uuid document_id FK
        integer chunk_index
        text content
        integer token_count "NULL"
        text embedding_id "NULL"
        text embedding "NULL"
        varchar_50 embedding_provider "NULL"
        varchar_100 embedding_model "NULL"
        integer embedding_dimensions "NULL"
        timestamptz embedded_at "NULL"
        vector embedding_vector "NULL; conditional pgvector column"
        timestamptz created_at
        timestamptz updated_at
    }

    DOCUMENT_PERMISSIONS {
        uuid id PK
        uuid document_id FK
        uuid user_id FK
        varchar_20 permission "read | write | owner"
        timestamptz created_at
        timestamptz updated_at
    }

    DOCUMENT_VERSIONS {
        uuid id PK
        uuid document_id FK
        integer version_number
        varchar_120 title
        uuid category_id FK
        varchar_255 file_name "NULL"
        text file_path "NULL"
        varchar_50 file_type "NULL"
        varchar_64 content_checksum "NULL"
        text content
        timestamptz created_at
        timestamptz updated_at
    }

    CHAT_SESSIONS {
        uuid id PK
        uuid user_id FK
        varchar_255 title "NULL"
        timestamptz created_at
        timestamptz updated_at
    }

    CHAT_MESSAGES {
        uuid id PK
        uuid session_id FK
        varchar_20 role "user | assistant | system"
        text content
        timestamptz created_at
        timestamptz updated_at
    }

    MESSAGE_SOURCES {
        uuid id PK
        uuid message_id FK
        uuid document_id FK
        uuid chunk_id FK "NULL"
        float similarity_score "NULL"
        timestamptz created_at
        timestamptz updated_at
    }

    AI_RUNS {
        uuid id PK
        uuid session_id FK
        uuid user_message_id FK "NULL"
        uuid assistant_message_id FK "NULL"
        varchar_100 model_name
        integer prompt_tokens "NULL; default 0"
        integer completion_tokens "NULL; default 0"
        integer total_tokens "NULL; default 0"
        varchar_20 status "success | failed"
        text error_message "NULL"
        timestamptz created_at
        timestamptz updated_at
    }

    AUDIT_LOGS {
        uuid id PK
        uuid actor_user_id FK "NULL"
        varchar_100 action
        varchar_80 resource_type "NULL"
        uuid resource_id "NULL; not a foreign key"
        jsonb details "NULL"
        timestamptz created_at
        timestamptz updated_at
    }

    USERS ||--o{ REFRESH_TOKENS : owns
    USERS ||--o{ EMAIL_VERIFICATION_TOKENS : verifies_with
    USERS ||--o{ PASSWORD_RESET_TOKENS : resets_with
    USERS o|--o{ DOCUMENTS : creates
    USERS ||--o{ DOCUMENT_PERMISSIONS : receives
    USERS ||--o{ CHAT_SESSIONS : owns
    USERS o|--o{ AUDIT_LOGS : acts_in

    DOCUMENT_CATEGORIES ||--o{ DOCUMENTS : categorizes
    DOCUMENT_CATEGORIES ||--o{ DOCUMENT_VERSIONS : categorizes

    DOCUMENTS ||--o{ DOCUMENT_CHUNKS : contains
    DOCUMENTS ||--o{ DOCUMENT_PERMISSIONS : grants
    DOCUMENTS ||--o{ DOCUMENT_VERSIONS : snapshots
    DOCUMENTS ||--o{ MESSAGE_SOURCES : cited_by

    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : contains
    CHAT_SESSIONS ||--o{ AI_RUNS : records

    CHAT_MESSAGES ||--o{ MESSAGE_SOURCES : cites
    CHAT_MESSAGES o|--o{ AI_RUNS : user_message
    CHAT_MESSAGES o|--o{ AI_RUNS : assistant_message

    DOCUMENT_CHUNKS o|--o{ MESSAGE_SOURCES : pinpoints
```

Composite unique constraints:

- `document_chunks (document_id, chunk_index)`
- `document_permissions (document_id, user_id)`
- `document_versions (document_id, version_number)`

`document_chunks.embedding_vector` and its HNSW index are created only when pgvector is available and embedding dimensions are usable.
