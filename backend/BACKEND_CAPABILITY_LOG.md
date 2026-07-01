# Backend Capability Log

Last checked: 2026-07-01

This log is the backend source of truth for frontend work. Build the frontend
against what is listed here, not against mock UI ideas.

## Current Server Design

The backend is a modular monolith FastAPI API. It is one deployable server with
separate modules for routes, services, repositories, models, schemas, auth, AI,
documents, users, chat, and audit logging.

Main backend folders:

- `app/routes/`: HTTP endpoints.
- `app/services/`: business logic.
- `app/repositories/`: SQLAlchemy database queries.
- `app/models/`: ORM models.
- `app/schemas/`: request and response schemas.
- `app/core/`: settings, middleware, errors, prompts.
- `alembic/versions/`: database migrations.
- `scripts/`: local database/admin/vector helper scripts.
- `tests/`: executable script tests.

## Runtime Configuration Checked

Current safe config state:

- `AI_PROVIDER=gemini`
- `EMBEDDINGS_ENABLED=true`
- `EMAIL_ENABLED=true`
- `EMAIL_RETURN_DEV_TOKENS=true`
- SMTP host, username, password, and from-email are set.
- SMTP TLS is enabled.
- Frontend CORS origins allow `http://127.0.0.1:5173` and `http://localhost:5173`.
- Uploads allow only `.md`.
- Max upload size is `10MB`.
- Email verification link base is currently `http://127.0.0.1:5173/verify-email`.
- Password reset link base is currently `http://127.0.0.1:5173/reset-password`.

Important email finding:

- The backend really does try to send SMTP email through `smtplib`.
- During live API tests, Gmail rejected the configured SMTP credentials with
  authentication error `535 BadCredentials`.
- Because the auth service catches email-send failures, registration and password
  reset still return successfully with `email_sent=false`.
- Because `EMAIL_RETURN_DEV_TOKENS=true`, verification/reset tokens are returned
  in API responses for local Swagger/testing.
- For real email delivery, fix the SMTP credentials, usually by using a Gmail app
  password instead of a normal account password.
- Frontend verification/reset URLs now point to the React frontend routes.

## Database

The active database connection works and the `kb` schema exists.

Expected tables found:

- `users`
- `document_categories`
- `documents`
- `document_chunks`
- `document_versions`
- `document_permissions`
- `chat_sessions`
- `chat_messages`
- `message_sources`
- `ai_runs`
- `refresh_tokens`
- `email_verification_tokens`
- `password_reset_tokens`
- `audit_logs`

Document categories found:

- `coding-convention`
- `git-flow`
- `pull-request`
- `database`
- `api-standard`
- `logging`

pgvector status:

- `vector` extension is available and installed.
- `halfvec` is available.
- `document_chunks.embedding_vector` exists.
- HNSW vector index exists:
  `idx_document_chunks_embedding_vector_hnsw`.

## API Routes

Auth:

- `POST /api/auth/register`
- `POST /api/auth/verify-email`
- `POST /api/auth/resend-verification`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `GET /api/auth/me`

Ask and chat:

- `POST /api/ask`
- `POST /ask` legacy alias
- `POST /api/chat`
- `GET /api/chat/sessions`
- `GET /api/chat/sessions/{session_id}`
- `DELETE /api/chat/sessions/{session_id}`

Documents:

- `GET /api/documents`
- `GET /api/documents/search`
- `GET /api/documents/{document_id}`
- `GET /api/documents/{document_id}/versions`
- `POST /api/documents/upload`
- `PUT /api/documents/{document_id}`
- `PATCH /api/documents/{document_id}/restore`
- `DELETE /api/documents/{document_id}`

Document permissions:

- `GET /api/documents/{document_id}/permissions`
- `PUT /api/documents/{document_id}/permissions`
- `DELETE /api/documents/{document_id}/permissions/{user_id}`

Users:

- `GET /api/users`
- `GET /api/users/{user_id}`
- `PATCH /api/users/{user_id}`
- `PATCH /api/users/{user_id}/soft-delete`
- `PATCH /api/users/{user_id}/restore`
- `DELETE /api/users/{user_id}`

Health:

- `GET /api/health`

## Auth Contract

Registration:

- Endpoint: `POST /api/auth/register`
- Body: `email`, `password`, `full_name`
- Password requires uppercase, lowercase, number, and special character.
- New users are created as `role=user`.
- New users must verify email before login.
- Response includes `user`, `message`, `email_sent`, and maybe
  `verification_token` when dev tokens are enabled.

Email verification:

- Endpoint: `POST /api/auth/verify-email`
- Body: `token`
- Marks user email verified.

Resend verification:

- Endpoint: `POST /api/auth/resend-verification`
- Body: `email`
- Response includes `message`, `email_sent`, and maybe `verification_token`.

Login:

- Endpoint: `POST /api/auth/login`
- Body: `email`, `password`
- Response includes `access_token`, `refresh_token`, `token_type`.
- Login blocks inactive users.
- Login blocks users whose email is not verified.

Refresh/logout:

- `POST /api/auth/refresh` rotates refresh tokens.
- `POST /api/auth/logout` revokes the submitted refresh token.

Password reset:

- `POST /api/auth/forgot-password` with `email`.
- `POST /api/auth/reset-password` with `token`, `new_password`.
- Reset password revokes existing refresh sessions.
- Dev mode may return `reset_token` in the forgot-password response.

Current roles:

- `admin`
- `user`

Not supported right now:

- GitHub login.
- Username login.
- Department field.
- Invite flow.
- Viewer/developer/custom roles.
- Revoke all sessions endpoint from frontend.
- Self-service password change endpoint separate from reset-password.

## User Admin Contract

All `/api/users` routes require an admin access token.

List users:

- `GET /api/users?page=1&page_size=10`
- Response: `items`, `total`, `page`, `page_size`.

User response fields:

- `id`
- `email`
- `full_name`
- `role`
- `is_active`
- `is_email_verified`
- `created_at`
- `updated_at`

Update user:

- `PATCH /api/users/{user_id}`
- Body can include `email`, `full_name`, `role`, `is_active`,
  `is_email_verified`, `password`.
- Changing email marks the user unverified.
- Role can only be `admin` or `user`.

Delete behavior:

- Soft delete deactivates a user.
- Restore reactivates a user.
- Hard delete exists.
- Admin cannot delete themself.
- Backend prevents removing the final active admin.

## Document Contract

All document routes require an authenticated user.

Upload:

- Endpoint: `POST /api/documents/upload`
- Admin only.
- Multipart form fields: `name`, `category`, `file`.
- File must be UTF-8 text.
- File extension must currently be `.md`.
- Max upload size is `10MB`.
- Upload creates document chunks and embeddings when embeddings are enabled.
- Upload returns public document metadata and does not expose `file_path`.

List/search:

- `GET /api/documents`
- Query filters: `name`, `category`, `page`, `page_size`.
- Normal users only see documents they can access.
- Admin users can see all documents.
- `GET /api/documents/search?q=...` searches document chunks.

Document response fields:

- `id`
- `name`
- `category`
- `file_name`
- `file_type`
- `content_checksum`
- `content`
- `is_deleted`
- `deleted_at`
- `created_at`

Lifecycle:

- `PUT /api/documents/{document_id}` replaces metadata and uploaded file.
- Updates append immutable document versions.
- `GET /api/documents/{document_id}/versions` returns version history.
- `DELETE /api/documents/{document_id}` soft-deletes.
- `PATCH /api/documents/{document_id}/restore` restores.

Document permissions:

- Admin-only endpoints are nested under the document route.
- Permission values are `read`, `write`, and `owner`.
- There is no top-level `/api/permissions` endpoint.

Not supported right now:

- PDF upload.
- DOCX upload.
- Drag/drop upload progress endpoint.
- Object storage/S3.
- Background upload processing queue.

## Ask And Chat Contract

Single-turn ask:

- Endpoint: `POST /api/ask`
- Body: `question`
- Response: `answer`, `sources`, `model_used`.
- Requires authentication.
- Uses document retrieval over documents the user can access.

Multi-turn chat:

- Endpoint: `POST /api/chat`
- Body: `question`, optional `session_id`, optional `title`.
- Response: `session_id`, `user_message_id`, `assistant_message_id`, `answer`,
  `sources`, `model_used`.
- Chat sessions belong to the authenticated user.
- `GET /api/chat/sessions` lists the current user's sessions.
- `GET /api/chat/sessions/{session_id}` returns messages.
- `DELETE /api/chat/sessions/{session_id}` deletes one owned session.

AI/RAG behavior:

- Current provider is Gemini.
- The system prompt lives in `app/core/prompts.py`.
- Retrieval uses document chunks, pgvector embeddings, permissions, and citations.
- Gemini/network access is required when embeddings or live AI answers are used.

Not supported right now:

- Workspace switching.
- Notifications.
- Saved code snippets.
- API reference module.
- Projects module.
- Collections module.

## Middleware And API Behavior

Errors:

- HTTP errors return `{"error": {"message": ...}}`.
- Validation errors return `{"error": {"message": "Validation failed.", "details": [...]}}`.
- Unknown exceptions return `{"error": {"message": "Internal server error."}}`.

CORS:

- Local Vite frontend origins are allowed.

Rate limit:

- Current limiter is in-memory fixed-window.
- General limit defaults to 100 requests per 60 seconds.
- Sensitive routes default to 5 requests per 60 seconds:
  - `/api/auth/login`
  - `/api/auth/register`
  - `/api/auth/forgot-password`
  - `/api/auth/reset-password`
  - `/api/auth/resend-verification`
  - `/api/documents/upload`
- Running multiple live scripts back-to-back can hit 429 on login.
- For local full live test runs, either wait for the 60 second window, restart the
  server, or temporarily disable/tune rate limiting in `.env`.
- Production Redis rate limiting is not implemented yet.

## Tests Run In This Audit

Passed:

- `python -m compileall app alembic`
- `tests/test_email_service.py`
- `tests/test_auth_password_validation.py`
- `tests/test_auth_security.py`
- `tests/test_database_connection.py`
- `tests/test_model_mappers.py`
- `tests/test_rate_limiter.py`
- `tests/test_auth_flow.py`
- `tests/test_user_soft_delete.py`
- `tests/test_document_chunking.py`
- `tests/test_document_lifecycle.py`
- `tests/test_document_search.py`
- `tests/test_token_cleanup.py`
- `tests/test_ask_flow.py`
- `tests/test_chat_flow.py`
- `scripts/check_pgvector.py`
- `tests/test_api_smoke.py` with local server running.
- `tests/test_upload_rules.py` with local server running.
- `tests/test_document_lifecycle_api.py` with local server running and outbound
  network access allowed.

Notes from failed/blocked attempts:

- `tests/test_upload_rules.py` fails if the server is not running.
- `tests/test_document_lifecycle_api.py` can fail with 429 if login rate limit was
  already used by other live scripts.
- `tests/test_document_lifecycle_api.py` can fail with Gemini socket/network
  errors if the server process cannot make outbound network calls.
- SMTP delivery failed during live auth flows because Gmail rejected current SMTP
  credentials.

## Frontend Rules From Backend Truth

Build these screens first:

- Register
- Verify email
- Login
- Forgot password
- Reset password
- Chat
- Chat history
- Documents list/search/detail
- Admin users table
- Admin user update/role/activate/delete actions
- Admin document upload/update/delete/restore/version history
- Admin document permissions

Do not build these as real features unless the backend adds them:

- GitHub login.
- Workspace switcher.
- Notifications.
- Department filters.
- Pending invites.
- Viewer/developer role badges.
- Code snippets.
- API reference pages.
- Projects.
- Collections.
- PDF/DOCX upload.
- Top-level permissions page backed by `/api/permissions`.

## Backend Gaps To Fix Before Demo/Production

Highest priority:

- Fix SMTP credentials so verification and reset emails really deliver.
- Change frontend email URLs away from `/docs` once frontend routes exist.
- Decide whether dev tokens should stay on for class demo or be disabled.
- Add a frontend-friendly reset password page and verify email page that consume
  the token from the link.

Server polish:

- Add request IDs to logs and responses.
- Add structured JSON logging with redaction.
- Replace in-memory rate limiting with Redis for production.
- Add a local test mode that stubs email and AI for live script tests.
- Add route tests that can run without rate-limit collisions.

Scaling:

- Move uploads from local filesystem to object storage.
- Move chunking/embedding generation to a background job.
- Add a re-chunk/re-embed admin script for existing documents.
- Add backup/restore documentation and migration rollback practice.
