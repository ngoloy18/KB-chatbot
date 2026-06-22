-- SCHEMA: kb

-- DROP SCHEMA IF EXISTS kb ;

CREATE SCHEMA IF NOT EXISTS kb
    AUTHORIZATION postgres;

-- Table: kb.users

-- DROP TABLE IF EXISTS kb.users;

CREATE TABLE IF NOT EXISTS kb.users
(
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    email character varying(255) COLLATE pg_catalog."default" NOT NULL,
    hashed_password text COLLATE pg_catalog."default" NOT NULL,
    full_name character varying(255) COLLATE pg_catalog."default",
    role character varying(20) COLLATE pg_catalog."default" NOT NULL DEFAULT 'user'::character varying,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT users_pkey PRIMARY KEY (id),
    CONSTRAINT users_email_key UNIQUE (email),
    CONSTRAINT users_role_check CHECK (role::text = ANY (ARRAY['admin'::character varying, 'user'::character varying]::text[]))
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS kb.users
    OWNER to postgres;

-- Table: kb.message_sources

-- DROP TABLE IF EXISTS kb.message_sources;

CREATE TABLE IF NOT EXISTS kb.message_sources
(
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    message_id uuid NOT NULL,
    document_id uuid NOT NULL,
    chunk_id uuid,
    similarity_score double precision,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT message_sources_pkey PRIMARY KEY (id),
    CONSTRAINT message_sources_chunk_id_fkey FOREIGN KEY (chunk_id)
        REFERENCES kb.document_chunks (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE SET NULL,
    CONSTRAINT message_sources_document_id_fkey FOREIGN KEY (document_id)
        REFERENCES kb.documents (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT message_sources_message_id_fkey FOREIGN KEY (message_id)
        REFERENCES kb.chat_messages (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS kb.message_sources
    OWNER to postgres;
-- Index: idx_message_sources_message_id

-- DROP INDEX IF EXISTS kb.idx_message_sources_message_id;

CREATE INDEX IF NOT EXISTS idx_message_sources_message_id
    ON kb.message_sources USING btree
    (message_id ASC NULLS LAST)
    TABLESPACE pg_default;

-- Table: kb.documents

-- DROP TABLE IF EXISTS kb.documents;

CREATE TABLE IF NOT EXISTS kb.documents
(
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    title character varying(120) COLLATE pg_catalog."default" NOT NULL,
    category_id uuid NOT NULL,
    file_name character varying(255) COLLATE pg_catalog."default",
    file_path text COLLATE pg_catalog."default",
    file_type character varying(50) COLLATE pg_catalog."default",
    content text COLLATE pg_catalog."default" NOT NULL,
    status character varying(30) COLLATE pg_catalog."default" NOT NULL DEFAULT 'uploaded'::character varying,
    created_by uuid,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT documents_pkey PRIMARY KEY (id),
    CONSTRAINT documents_category_id_fkey FOREIGN KEY (category_id)
        REFERENCES kb.document_categories (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION,
    CONSTRAINT documents_created_by_fkey FOREIGN KEY (created_by)
        REFERENCES kb.users (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION,
    CONSTRAINT documents_status_check CHECK (status::text = ANY (ARRAY['uploaded'::character varying, 'processing'::character varying, 'ready'::character varying, 'failed'::character varying]::text[]))
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS kb.documents
    OWNER to postgres;
-- Index: idx_documents_category_id

-- DROP INDEX IF EXISTS kb.idx_documents_category_id;

CREATE INDEX IF NOT EXISTS idx_documents_category_id
    ON kb.documents USING btree
    (category_id ASC NULLS LAST)
    TABLESPACE pg_default;
-- Index: idx_documents_created_by

-- DROP INDEX IF EXISTS kb.idx_documents_created_by;

CREATE INDEX IF NOT EXISTS idx_documents_created_by
    ON kb.documents USING btree
    (created_by ASC NULLS LAST)
    TABLESPACE pg_default;


-- Table: kb.document_permissions

-- DROP TABLE IF EXISTS kb.document_permissions;

CREATE TABLE IF NOT EXISTS kb.document_permissions
(
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL,
    user_id uuid NOT NULL,
    permission character varying(20) COLLATE pg_catalog."default" NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT document_permissions_pkey PRIMARY KEY (id),
    CONSTRAINT document_permissions_unique_user_document UNIQUE (document_id, user_id),
    CONSTRAINT document_permissions_document_id_fkey FOREIGN KEY (document_id)
        REFERENCES kb.documents (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT document_permissions_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES kb.users (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT document_permissions_permission_check CHECK (permission::text = ANY (ARRAY['read'::character varying, 'write'::character varying, 'owner'::character varying]::text[]))
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS kb.document_permissions
    OWNER to postgres;
-- Index: idx_document_permissions_user_id

-- DROP INDEX IF EXISTS kb.idx_document_permissions_user_id;

CREATE INDEX IF NOT EXISTS idx_document_permissions_user_id
    ON kb.document_permissions USING btree
    (user_id ASC NULLS LAST)
    TABLESPACE pg_default;

-- Table: kb.document_chunks

-- DROP TABLE IF EXISTS kb.document_chunks;

CREATE TABLE IF NOT EXISTS kb.document_chunks
(
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    content text COLLATE pg_catalog."default" NOT NULL,
    token_count integer,
    embedding_id text COLLATE pg_catalog."default",
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT document_chunks_pkey PRIMARY KEY (id),
    CONSTRAINT document_chunks_unique_index UNIQUE (document_id, chunk_index),
    CONSTRAINT document_chunks_document_id_fkey FOREIGN KEY (document_id)
        REFERENCES kb.documents (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS kb.document_chunks
    OWNER to postgres;
-- Index: idx_document_chunks_document_id

-- DROP INDEX IF EXISTS kb.idx_document_chunks_document_id;

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id
    ON kb.document_chunks USING btree
    (document_id ASC NULLS LAST)
    TABLESPACE pg_default;

-- Table: kb.document_categories

-- DROP TABLE IF EXISTS kb.document_categories;

CREATE TABLE IF NOT EXISTS kb.document_categories
(
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    name character varying(50) COLLATE pg_catalog."default" NOT NULL,
    description text COLLATE pg_catalog."default",
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT document_categories_pkey PRIMARY KEY (id),
    CONSTRAINT document_categories_name_key UNIQUE (name)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS kb.document_categories
    OWNER to postgres;


-- Table: kb.chat_sessions

-- DROP TABLE IF EXISTS kb.chat_sessions;

CREATE TABLE IF NOT EXISTS kb.chat_sessions
(
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    title character varying(255) COLLATE pg_catalog."default",
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT chat_sessions_pkey PRIMARY KEY (id),
    CONSTRAINT chat_sessions_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES kb.users (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS kb.chat_sessions
    OWNER to postgres;
-- Index: idx_chat_sessions_user_id

-- DROP INDEX IF EXISTS kb.idx_chat_sessions_user_id;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id
    ON kb.chat_sessions USING btree
    (user_id ASC NULLS LAST)
    TABLESPACE pg_default;

-- Table: kb.chat_messages

-- DROP TABLE IF EXISTS kb.chat_messages;

CREATE TABLE IF NOT EXISTS kb.chat_messages
(
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL,
    role character varying(20) COLLATE pg_catalog."default" NOT NULL,
    content text COLLATE pg_catalog."default" NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT chat_messages_pkey PRIMARY KEY (id),
    CONSTRAINT chat_messages_session_id_fkey FOREIGN KEY (session_id)
        REFERENCES kb.chat_sessions (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT chat_messages_role_check CHECK (role::text = ANY (ARRAY['user'::character varying, 'assistant'::character varying, 'system'::character varying]::text[]))
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS kb.chat_messages
    OWNER to postgres;
-- Index: idx_chat_messages_session_id

-- DROP INDEX IF EXISTS kb.idx_chat_messages_session_id;

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
    ON kb.chat_messages USING btree
    (session_id ASC NULLS LAST)
    TABLESPACE pg_default;


-- Table: kb.ai_runs

-- DROP TABLE IF EXISTS kb.ai_runs;

CREATE TABLE IF NOT EXISTS kb.ai_runs
(
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL,
    user_message_id uuid,
    assistant_message_id uuid,
    model_name character varying(100) COLLATE pg_catalog."default" NOT NULL,
    prompt_tokens integer DEFAULT 0,
    completion_tokens integer DEFAULT 0,
    total_tokens integer DEFAULT 0,
    status character varying(20) COLLATE pg_catalog."default" NOT NULL DEFAULT 'success'::character varying,
    error_message text COLLATE pg_catalog."default",
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT ai_runs_pkey PRIMARY KEY (id),
    CONSTRAINT ai_runs_assistant_message_id_fkey FOREIGN KEY (assistant_message_id)
        REFERENCES kb.chat_messages (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE SET NULL,
    CONSTRAINT ai_runs_session_id_fkey FOREIGN KEY (session_id)
        REFERENCES kb.chat_sessions (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT ai_runs_user_message_id_fkey FOREIGN KEY (user_message_id)
        REFERENCES kb.chat_messages (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE SET NULL,
    CONSTRAINT ai_runs_status_check CHECK (status::text = ANY (ARRAY['success'::character varying, 'failed'::character varying]::text[]))
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS kb.ai_runs
    OWNER to postgres;
-- Index: idx_ai_runs_session_id

-- DROP INDEX IF EXISTS kb.idx_ai_runs_session_id;

CREATE INDEX IF NOT EXISTS idx_ai_runs_session_id
    ON kb.ai_runs USING btree
    (session_id ASC NULLS LAST)
    TABLESPACE pg_default;

-- Extension: pgcrypto

-- DROP EXTENSION pgcrypto;

CREATE EXTENSION IF NOT EXISTS pgcrypto
    SCHEMA public
    VERSION "1.4";

    