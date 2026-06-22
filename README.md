# KB-chatbot

Developer knowledge-base chatbot API built with FastAPI, PostgreSQL, async
SQLAlchemy, and Alembic.

## Current Status

This project is on Week 3: Authentication + File Upload.

The document API now stores uploaded documents in PostgreSQL instead of an
in-memory dictionary. Data should stay available after the API server restarts.
Auth endpoints use JWT access tokens, and document upload is protected by admin
role. Admin users can also list, update, and delete user accounts.

## Requirements

- Python 3.11 or newer
- PostgreSQL running locally
- `pip`
- Project dependencies from `requirements.txt`

## Database

The app expects a PostgreSQL database named:

```text
chatbot_db
```

The project tables live in the PostgreSQL schema:

```text
kb
```

The database currently uses these 9 tables:

```text
kb.users
kb.document_categories
kb.documents
kb.document_chunks
kb.document_permissions
kb.chat_sessions
kb.chat_messages
kb.message_sources
kb.ai_runs
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
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5123/chatbot_db
DATABASE_ECHO=false
DATABASE_SCHEMA=kb
JWT_SECRET=change_me_to_a_long_random_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=change_me
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=10
ALLOWED_UPLOAD_EXTENSIONS=.md
```

Use your real PostgreSQL password in `.env`. Do not commit `.env`.

## Install

```powershell
python -m pip install -r requirements.txt
```

If your machine uses the `py` launcher on Windows:

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

## Test Database Connection

Run:

```powershell
python tests/test_database_connection.py
python tests/test_model_mappers.py
python tests/test_auth_security.py
```

Expected success output:

```text
Database connection OK: connected to 'chatbot_db'.
Schema OK: found kb schema and all 9 expected tables.
Categories OK: found all 6 document categories.
```

## Run Locally

```powershell
python -m uvicorn app.main:app --reload
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
python scripts/seed_admin.py
```

The script reads `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` from `.env`.
Running it twice does not create duplicate admins.

## Project Structure

```text
app/
  core/       shared config and enums
  dependencies/ auth dependencies such as current-user/admin checks
  db/         SQLAlchemy engine, session, and Base
  models/     split SQLAlchemy ORM model files
  repositories/ database query layer
  routes/     FastAPI routers
  schemas/    Pydantic request and response models
  services/   business logic
  main.py     FastAPI app entrypoint
alembic/      database migrations
tests/        local test scripts
```

The request flow is:

```text
routes -> services -> repositories -> database
```

Routes handle HTTP, file uploads, and error-to-status-code translation.
Services contain business logic and response conversion.
Repositories contain SQLAlchemy queries and database commits.

## Endpoints

- `GET /api/health` checks whether the API process is running.
- `POST /api/auth/register` creates a normal user.
- `POST /api/auth/verify-email` verifies a registered user's email token.
- `POST /api/auth/login` returns a JWT access token.
- `GET /api/auth/me` returns the current Bearer-token user.
- `GET /api/users` lists users as admin.
- `GET /api/users/{user_id}` returns one user as admin.
- `PATCH /api/users/{user_id}` updates user information as admin.
- `DELETE /api/users/{user_id}` deletes one user as admin.
- `GET /api/documents` lists paginated documents and supports optional `name` and `category` filtering.
- `GET /api/documents/{document_id}` returns one document by UUID or `404`.
- `GET /api/documents/{document_id}/permissions` lists access rules for a document as admin.
- `PUT /api/documents/{document_id}/permissions` grants or updates one user's access as admin.
- `DELETE /api/documents/{document_id}/permissions/{user_id}` revokes one user's access as admin.
- `POST /api/documents/upload` creates a document from an admin markdown upload.
- `PUT /api/documents/{document_id}` replaces a document as admin or a user with `write`/`owner` permission.
- `DELETE /api/documents/{document_id}` deletes a document as admin or a user with `owner` permission.

## Swagger Test Checklist

- Start PostgreSQL.
- Start the API and confirm the terminal prints `database connect is working`.
- Run `python scripts/seed_admin.py`.
- Register a normal user and copy the returned `verification_token`.
- Verify the normal user with `POST /api/auth/verify-email`.
- Log in with `POST /api/auth/login` and copy the access token.
- Call `GET /api/auth/me` with `Authorization: Bearer <token>`.
- Log in as admin and confirm `GET /api/users` returns the user list.
- Confirm admin can update a user with `PATCH /api/users/{user_id}`.
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
