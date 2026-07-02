# KB-chatbot

Developer knowledge-base chatbot API built with FastAPI, PostgreSQL, async
SQLAlchemy, and Alembic.

Run the commands in this file from the `backend/` folder.

## Current Status

This project is a backend-first developer knowledge-base chatbot. The server is
now requirement-ready for the current backend milestone: auth, admin user
management, document lifecycle, permissions, chat history, RAG answers, Gemini
AI integration, embeddings, pgvector search, audit logs, and script tests are in
place.

The app is currently a modular monolith: one FastAPI service owns the API,
business logic, database access, AI orchestration, and local document storage.
The code is split by routes, services, repositories, schemas, models, and
feature folders so it can stay understandable while still being simple to run
for a class project or mentor demo.

The backend is not production-perfect yet. The biggest remaining product work is
frontend/backend integration polish and end-to-end demo testing. The biggest
remaining production work is Docker/deploy setup, Redis-backed rate limiting,
structured request logging, backup/restore practice, object storage/background
document processing, and a few account-security polish items such as password
change and revoke-all-sessions.

Public document responses intentionally do not expose internal storage
`file_path` values. Uploaded file paths stay server-side only so the API does
not leak local filesystem details.

## Requirements

- Python 3.11 or newer
- PostgreSQL running locally
- `pip`
- Project dependencies from `requirements.txt`
- A `.env` copied from `.env.example`
- Node.js/npm only if you also run the frontend in `../frontend`

## Database

The app expects a PostgreSQL database named:

```text
chatbot_db
```

The project tables live in the PostgreSQL schema:

```text
kb
```

The database currently uses these 14 tables:

```text
kb.users
kb.email_verification_tokens
kb.password_reset_tokens
kb.audit_logs
kb.document_categories
kb.documents
kb.document_chunks
kb.document_permissions
kb.document_versions
kb.chat_sessions
kb.chat_messages
kb.message_sources
kb.ai_runs
kb.refresh_tokens
```

The six document categories are:

- `coding-convention`
- `git-flow`
- `pull-request`
- `database`
- `api-standard`
- `logging`

## Environment

Create a local `.env` file from `.env.example`:

```env
APP_NAME=developer-kb-chatbot
APP_TITLE=Developer KB Chatbot API
APP_VERSION=0.2.0
APP_DESCRIPTION=FastAPI with SQLAlchemy, JWT auth, and protected uploads.
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=your_flash_model_from_ai_studio
AI_TIMEOUT_SECONDS=30
AI_MAX_RETRIES=2
AI_RETRY_DELAY_SECONDS=1
CHAT_HISTORY_LIMIT=12
EMBEDDINGS_ENABLED=false
EMBEDDING_PROVIDER=gemini
GEMINI_EMBEDDING_MODEL=your_embedding_model_from_ai_studio
EMBEDDING_DIMENSIONS=0
RAG_TOP_K=10
RAG_MAX_CONTEXT_TOKENS=3200
RAG_MIN_SIMILARITY=0
RAG_NEIGHBOR_WINDOW=1
RAG_DEBUG=false
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5123/chatbot_db
DATABASE_ECHO=false
DATABASE_SCHEMA=kb
JWT_SECRET=change_me_to_a_long_random_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_MINUTES=10080
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
PASSWORD_RESET_TOKEN_RETENTION_DAYS=7
EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES=1440
EMAIL_VERIFICATION_TOKEN_RETENTION_DAYS=7
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=ChangeMe123!
EMAIL_ENABLED=true
EMAIL_RETURN_DEV_TOKENS=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_sender_email@gmail.com
SMTP_PASSWORD=your_google_app_password
SMTP_FROM_EMAIL=your_sender_email@gmail.com
SMTP_USE_TLS=true
FRONTEND_VERIFY_EMAIL_URL=http://127.0.0.1:5173/verify-email
FRONTEND_RESET_PASSWORD_URL=http://127.0.0.1:5173/reset-password
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=10
ALLOWED_UPLOAD_EXTENSIONS=.md
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_EXCLUDED_PATHS=/docs,/openapi.json,/redoc
SENSITIVE_RATE_LIMIT_REQUESTS=5
SENSITIVE_RATE_LIMIT_WINDOW_SECONDS=60
SENSITIVE_RATE_LIMIT_PATHS=/api/auth/login,/api/auth/register,/api/auth/forgot-password,/api/auth/reset-password,/api/auth/resend-verification,/api/documents/upload
```

Use your real PostgreSQL password in `.env`. Do not commit `.env`.

Passwords must be 8-128 characters and include uppercase, lowercase, number,
and special character.

For local email testing with Gmail SMTP, use a Google App Password and set:

```env
EMAIL_ENABLED=true
EMAIL_RETURN_DEV_TOKENS=true
```

`EMAIL_RETURN_DEV_TOKENS=true` keeps verification and reset tokens visible in
Swagger while also sending emails. In production, set it to `false`.

The frontend consumes the links generated from `FRONTEND_VERIFY_EMAIL_URL` and
`FRONTEND_RESET_PASSWORD_URL`. Keep these pointed at the React app while running
the full product locally.

`SENSITIVE_RATE_LIMIT_*` settings apply stricter limits to endpoints that are
easy to abuse, such as login, register, password reset, resend verification, and
document upload.

`AI_PROVIDER=gemini` selects the Gemini provider. Set `GEMINI_MODEL` to a Flash
model available in your AI Studio project instead of hard-coding a model name in
the app.

`AI_TIMEOUT_SECONDS`, `AI_MAX_RETRIES`, and `AI_RETRY_DELAY_SECONDS` bound
external AI calls so slow provider responses do not hang the API indefinitely.

`CHAT_HISTORY_LIMIT` controls how many previous messages are sent with each
multi-turn chat request.

`EMBEDDINGS_ENABLED=true` makes document upload/update generate chunk
embeddings and makes `/api/chat` retrieve top matching chunks before calling the
chat model. `GEMINI_EMBEDDING_MODEL` should be set from AI Studio; the app does
not hard-code an embedding model. `EMBEDDING_DIMENSIONS=0` means infer the
dimension from stored embeddings; set it only when you intentionally request a
specific embedding output size. `RAG_TOP_K`, `RAG_MAX_CONTEXT_TOKENS`,
`RAG_MIN_SIMILARITY`, and `RAG_NEIGHBOR_WINDOW` control retrieval size,
filtering, and how many adjacent chunks are included around each match. Set
`RAG_DEBUG=true` locally when you want the API logs to show retrieved chunk ids,
similarity scores, token counts, and previews.

The `0008` migration stores embeddings and tries to enable PostgreSQL `vector`
support when the server has pgvector installed. If your local PostgreSQL does
not include pgvector, semantic retrieval still works with exact cosine scoring
over stored embeddings, but pgvector indexing/acceleration is not available
until the server extension is installed.

The `0009` migration adds an HNSW pgvector index. For high-dimensional Gemini
embeddings such as 3072 dimensions, the app uses pgvector `halfvec` indexing
because normal `vector` HNSW indexes support only lower-dimensional vectors.

Existing chunks do not receive embeddings just because the migration runs. After
configuring `GEMINI_EMBEDDING_MODEL`, backfill current chunks manually:

```powershell
py scripts/backfill_embeddings.py --limit 20
```

If chunking rules, chunk size, overlap, or Markdown heading logic change,
rebuild stored chunks instead:

```powershell
py scripts/rechunk_documents.py --limit 20
```

When `EMBEDDINGS_ENABLED=true`, rechunking also regenerates embeddings for the
new chunks. Use `--document-id <uuid>` to reprocess one document.

`EMAIL_VERIFICATION_TOKEN_RETENTION_DAYS=7` and
`PASSWORD_RESET_TOKEN_RETENTION_DAYS=7` mean used auth token rows can be kept
briefly for debugging/history. Expired token rows are removed whenever the
cleanup script runs.

## Install

```powershell
py -m pip install -r requirements.txt
```

If you need to force Python 3.11 on Windows:

```powershell
py -3.11 -m pip install -r requirements.txt
```

## Alembic

Alembic tracks database schema changes.

If your `kb` tables already exist because you created them manually, mark the
current database as matching the first migration:

```powershell
alembic stamp head
```

For a new empty database, run:

```powershell
alembic upgrade head
```

Do not run `alembic upgrade head` against a database where the same tables
already exist, or PostgreSQL will complain that the tables already exist.

## Full Backend Verification

Run this before committing backend changes:

```powershell
py -m compileall app alembic tests
py tests/test_database_connection.py
py tests/test_model_mappers.py
py tests/test_auth_security.py
py tests/test_auth_flow.py
py tests/test_auth_password_validation.py
py tests/test_rate_limiter.py
py tests/test_email_service.py
py tests/test_document_chunking.py
py tests/test_document_lifecycle.py
py tests/test_document_search.py
py tests/test_ask_flow.py
py tests/test_chat_flow.py
py tests/test_token_cleanup.py
py tests/test_user_soft_delete.py
py tests/test_user_hard_delete.py
```

Expected success output includes:

```text
Database connection OK: connected to 'chatbot_db'.
Schema OK: found kb schema and all 14 expected tables.
Categories OK: found all 6 document categories.
SQLAlchemy model mappers OK.
Auth security helpers OK.
Normal user register/login flow OK.
Password validation OK.
Rate limiter OK.
Email service config OK.
Document chunking OK.
Document lifecycle OK.
Document chunk search OK.
Ask flow OK.
Chat flow OK.
Token cleanup OK.
User soft delete OK.
User hard delete OK.
```

For live API tests, start the server first:

```powershell
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --access-log --log-level info
```

Then run:

```powershell
py tests/test_api_smoke.py
py tests/test_upload_rules.py
py tests/test_document_lifecycle_api.py
```

Expected success output includes:

```text
Live Swagger/API smoke test OK.
Upload rules OK.
Live document lifecycle API test OK.
```

The sensitive auth/upload endpoints have a stricter local rate limiter. If a
live test returns `429 Too Many Requests` from `/api/auth/login`, wait for
`SENSITIVE_RATE_LIMIT_WINDOW_SECONDS` to pass and rerun that test.

## Run Locally

```powershell
py -m uvicorn app.main:app --reload
```

If the database connection works, the terminal prints:

```text
database connect is working
```

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Seed The First Admin

Public registration always creates normal users. Create the first admin with:

```powershell
py scripts/seed_admin.py
```

The script reads `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` from `.env`.
Running it twice does not create duplicate admins. It checks for an existing
user by email first, promotes that user if needed, and the `users.email` column
is unique at the database level.

## Cleanup Old Tokens

Email verification and password reset tokens are stored for short-term
debugging/security history. Delete expired token rows and used token rows past
the configured retention windows with:

```powershell
py scripts/cleanup_tokens.py
```

By default, `EMAIL_VERIFICATION_TOKEN_RETENTION_DAYS=7`.

## Project Structure

```text
app/
  constants/
    ai/           AI run status constants
    auth/         auth, JWT, role, and password constants
    chat/         chat role constants
    database/     database schema constants
    documents/    document status/upload constants
    permissions/  document permission constants
  core/
    config/       environment settings and document category enum
    errors/       shared exception handlers
    middleware/   shared middleware such as rate limiting
    security/     password hashing and JWT helpers
  dependencies/   FastAPI dependencies such as current-user/admin checks
  db/             SQLAlchemy engine, session, and Base
  models/
    audit/        append-only audit log ORM model
    auth/         user, verification-token, and refresh-token ORM models
    chat/         chat/session/message/source/AI run ORM models
    common/       shared ORM mixins
    documents/    document/category/chunk/permission ORM models
    database.py   central model exports for Alembic and compatibility
  repositories/
    auth/         verification-token and refresh-token persistence
    chat/         chat session/message/source persistence
    documents/    document persistence
    users/        user persistence
  routes/
    ask/          stateless document Q&A compatibility route
    auth/         register/login/logout/password/profile routes
    chat/         authenticated multi-turn chat routes
    documents/    document and permission routes
    health/       health route
    users/        admin user routes
  schemas/
    ask/          stateless Q&A request/response schemas
    auth/         auth request/response schemas
    chat/         chat request/session/message response schemas
    documents/    document request/response schemas
    users/        user admin schemas
  services/
    ai/           configurable AI provider implementations
    ask/          long-context document Q&A context and service
    audit/        append-only audit event persistence
    auth/         auth business logic and email sender
    chat/         multi-turn chat business logic
    documents/    document business logic
    users/        user admin business logic
  main.py         FastAPI app entrypoint
alembic/          database migrations
tests/            local test scripts
```

The request flow is:

```text
routes -> services -> repositories -> database
```

Routes handle HTTP, file uploads, and error-to-status-code translation.
Services contain business logic and response conversion.
Repositories contain SQLAlchemy queries and database commits.

## Server Design And Tradeoffs

| Design choice | What it gives you | Tradeoff |
| --- | --- | --- |
| Modular monolith with FastAPI | Simple local setup, one deployable server, easy mentor demo | The whole backend scales and deploys as one unit |
| Route/service/repository layers | Clear ownership for HTTP, business rules, and database queries | More files than a tiny prototype |
| PostgreSQL schema `kb` with Alembic | Durable data, migrations, organized tables | Requires migration discipline and rollback practice |
| JWT access tokens plus refresh-token table | Fast authenticated API calls and revocable sessions | Token rotation and cleanup add complexity |
| Admin/user roles plus document permissions | User isolation and per-document access control | More policy tests are needed for every protected route |
| Local markdown upload storage | Easy to build and test on one machine | Production should move files to object storage |
| Chunking plus keyword/vector retrieval | Real RAG answers with source citations | Needs embedding backfill/rechunk scripts when documents or chunk rules change |
| Gemini provider behind AI service code | Better answer quality without running a local model | Depends on external API availability, latency, and cost |
| In-memory rate limiter | Good local abuse protection with simple config | Multi-instance production should use Redis |
| Script-style tests | Easy to run one by one while building | Pytest fixtures, CI coverage, and isolated test DB would be stronger |

## Endpoints

- `GET /api/health` checks whether the API process is running.
- `POST /api/ask` answers a question from documents the authenticated user can read.
- `POST /ask` is a root alias for the same authenticated document Q&A flow.
- `POST /api/chat` creates or continues an authenticated multi-turn chat session.
- `GET /api/chat/sessions` lists only the authenticated user's chat sessions.
- `GET /api/chat/sessions/{session_id}` returns only a session owned by the authenticated user.
- `DELETE /api/chat/sessions/{session_id}` deletes only a session owned by the authenticated user.
- `POST /api/auth/register` creates a normal user.
- `POST /api/auth/verify-email` verifies a registered user's email token.
- `POST /api/auth/resend-verification` sends a fresh verification token.
- `POST /api/auth/login` returns JWT access and refresh tokens.
- `POST /api/auth/refresh` rotates a refresh token and returns new tokens.
- `POST /api/auth/logout` revokes one refresh token.
- `POST /api/auth/forgot-password` creates a password reset token.
- `POST /api/auth/reset-password` replaces the password with a valid reset token.
- `GET /api/auth/me` returns the current Bearer-token user.
- `GET /api/users` lists users as admin.
- `GET /api/users/{user_id}` returns one user as admin.
- `PATCH /api/users/{user_id}` updates user information as admin.
- `PATCH /api/users/{user_id}/soft-delete` deactivates one user as admin while keeping the row.
- `DELETE /api/users/{user_id}` deletes one user as admin.
- `GET /api/documents` lists paginated documents and supports optional `name` and `category` filtering.
- `GET /api/documents/{document_id}` returns one document by UUID or `404`.
- `GET /api/documents/{document_id}/versions` returns document version history.
- `GET /api/documents/{document_id}/permissions` lists access rules for a document as admin.
- `PUT /api/documents/{document_id}/permissions` grants or updates one user's access as admin.
- `DELETE /api/documents/{document_id}/permissions/{user_id}` revokes one user's access as admin.
- `POST /api/documents/upload` creates a document from an admin markdown upload.
- `PUT /api/documents/{document_id}` replaces a document as admin or a user with `write`/`owner` permission.
- `PATCH /api/documents/{document_id}/restore` restores a soft-deleted document as admin or owner.
- `DELETE /api/documents/{document_id}` soft-deletes a document as admin or owner.

## Swagger Test Checklist

- Start PostgreSQL.
- Start the API and confirm the terminal prints `database connect is working`.
- Run `py scripts/seed_admin.py`.
- Register a normal user and copy the returned `verification_token`.
- If `EMAIL_ENABLED=true`, confirm the verification email appears in the recipient inbox.
- If the email is missing, call `POST /api/auth/resend-verification`.
- Verify the normal user with `POST /api/auth/verify-email`.
- Log in with `POST /api/auth/login` and copy the access token and refresh token.
- Call `GET /api/auth/me` with `Authorization: Bearer <token>`.
- Use `POST /api/auth/refresh` with the refresh token and confirm it returns new tokens.
- Use `POST /api/auth/logout` with the latest refresh token and confirm it cannot refresh again.
- Use `POST /api/auth/forgot-password` and copy the returned reset token.
- If `EMAIL_ENABLED=true`, confirm the password reset email appears in the recipient inbox.
- Use `POST /api/auth/reset-password` and confirm login works with the new password.
- Log in as admin and confirm `GET /api/users` returns the user list.
- Confirm admin can update a user with `PATCH /api/users/{user_id}`.
- Confirm admin can soft-delete a user with `PATCH /api/users/{user_id}/soft-delete`.
- Confirm admin can delete a different user with `DELETE /api/users/{user_id}`.
- As admin, grant a normal user document access with `PUT /api/documents/{document_id}/permissions`.
- Log in as that normal user and confirm `GET /api/documents` only shows allowed documents.
- Confirm `read` can view, `write` can view/update, and `owner` can view/update/delete.
- Revoke access with `DELETE /api/documents/{document_id}/permissions/{user_id}`.
- Create a document with a valid category.
- Confirm `id` is a UUID and `created_at` is generated by the server.
- List documents with `GET /api/documents?page=1&page_size=10`.
- Filter documents with `GET /api/documents?name=Coding&category=coding-convention&page=1&page_size=10`.
- Fetch a valid document by id.
- Fetch a missing UUID and confirm it returns `404`.
- Replace a document with `PUT /api/documents/{document_id}`.
- Try an invalid category and confirm validation rejects it.
- Delete a document and confirm the same id returns `404` afterward.
- Restart the API and confirm created documents still appear.
- Confirm normal users receive `403` when uploading documents.
- Confirm uploads reject non-`.md` files and files larger than 10MB.

More detail is in `WEEK2_DATABASE_NOTES.txt`.
