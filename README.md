# KB-chatbot

Developer knowledge-base chatbot product workspace.

## Project Layout

- `backend/` contains the FastAPI API, database migrations, backend scripts,
  backend tests, backend environment example, and backend documentation.
- `frontend/` is reserved for the new frontend app.
- `.github/` contains repo-level GitHub Actions workflows.

## Backend Quick Start

Run backend commands from the backend folder:

```powershell
cd backend
py -m pip install -r requirements.txt
py -m alembic upgrade head
py -m uvicorn app.main:app --reload
```

The detailed backend README is in `backend/README.md`.

## Frontend

The frontend folder exists now and is ready for the UI implementation.
