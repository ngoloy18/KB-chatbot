# Repository Guidelines

## Project Structure & Module Organization

This is a FastAPI knowledge-base chatbot backend. Application code lives in `app/`.
Routes are in `app/routes/`, business logic in `app/services/`, SQLAlchemy queries in
`app/repositories/`, ORM models in `app/models/`, and shared settings/security helpers
in `app/core/`. Database migrations are in `alembic/versions/`. Local utility scripts
are in `scripts/`. Tests are script-style files in `tests/`, named `test_*.py`.
Uploaded files are stored under `uploads/`, which is ignored by git.

## Build, Test, and Development Commands

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

Run database migrations:

```powershell
py -m alembic upgrade head
```

Start the API locally:

```powershell
py -m uvicorn app.main:app --reload
```

Run core checks:

```powershell
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

Tests are currently executable scripts, not pure pytest tests. Name new tests
`tests/test_<feature>.py` and make them print a clear success message. Stub AI
providers in tests so Gemini/Ollama calls do not run during local or CI checks.
For live API tests, start the server first on `127.0.0.1:8000`.

## Commit & Pull Request Guidelines

Recent commits use short conventional prefixes, for example `feat: add pgvector`
and `test: add test for chunk doc, lifecycle, search`. Use a concise prefix such
as `feat:`, `fix:`, `test:`, `docs:`, or `chore:`. PRs should describe behavior
changes, list migrations, mention test commands run, and call out any `.env`
settings needed.

## Security & Configuration Tips

Never commit `.env`, API keys, uploaded files, or local progress logs. Keep model
names and provider settings configurable through environment variables. If a
change touches auth, permissions, documents, or AI retrieval, verify user
isolation and source citation behavior before merging.
