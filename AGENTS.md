# Repository Guidelines

## Project Structure & Module Organization

This repo is split into `backend/` and `frontend/`. The current backend is a
FastAPI knowledge-base chatbot API. Backend application code lives in
`backend/app/`. Routes are in `backend/app/routes/`, business logic in
`backend/app/services/`, SQLAlchemy queries in `backend/app/repositories/`, ORM
models in `backend/app/models/`, and shared settings/security helpers in
`backend/app/core/`. Database migrations are in `backend/alembic/versions/`.
Local utility scripts are in `backend/scripts/`. Tests are script-style files in
`backend/tests/`, named `test_*.py`. Uploaded files are stored under
`backend/uploads/`, which is ignored by git. Frontend work should live in
`frontend/`.

## Build, Test, and Development Commands

Install dependencies:

```powershell
cd backend
py -m pip install -r requirements.txt
```

Run database migrations:

```powershell
cd backend
py -m alembic upgrade head
```

Start the API locally:

```powershell
cd backend
py -m uvicorn app.main:app --reload
```

Run core checks:

```powershell
cd backend
py -m compileall app alembic
py tests/test_database_connection.py
py scripts/check_pgvector.py
```

Run the full local script test set from the README before committing substantial
backend changes.

## Coding Style & Naming Conventions

Use Python 3.11+ style with 4-space indentation and type hints for service,
repository, and schema code. Keep route handlers thin: routes translate HTTP
errors, services hold business rules, repositories own database queries. Prefer
explicit names such as `document_service`, `chat_repository`, and `UserAdminResponse`.
Keep comments short and useful; avoid explaining obvious assignments.

## Testing Guidelines

Backend tests are currently executable scripts, not pure pytest tests. Name new
tests `backend/tests/test_<feature>.py` and make them print a clear success
message. Stub AI providers in tests so Gemini/Ollama calls do not run during
local or CI checks. For live API tests, start the server first on
`127.0.0.1:8000`.

## Commit & Pull Request Guidelines

Recent commits use short conventional prefixes, for example `feat: add pgvector`
and `test: add test for chunk doc, lifecycle, search`. Use a concise prefix such
as `feat:`, `fix:`, `test:`, `docs:`, or `chore:`. PRs should describe behavior
changes, list migrations, mention test commands run, and call out any `.env`
settings needed.

## Security & Configuration Tips

Never commit `backend/.env`, API keys, uploaded files, or local progress logs.
Keep model names and provider settings configurable through environment
variables. If a change touches auth, permissions, documents, or AI retrieval,
verify user isolation and source citation behavior before merging.
