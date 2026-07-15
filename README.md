# KB-chatbot

Full-stack developer knowledge-base chatbot workspace.

The product is currently split into a FastAPI backend and a React/Vite
frontend. The backend is the source of truth for real product behavior; the
frontend should only call routes listed in `backend/BACKEND_CAPABILITY_LOG.md`.

## Project Layout

- `backend/` contains the FastAPI API, database migrations, scripts, tests,
  backend `.env.example`, and backend documentation.
- `frontend/` contains the React/Vite UI, frontend `.env.example`, and frontend
  documentation.
- `.github/` contains repo-level GitHub Actions workflows.

## Requirements

Backend:

- Python 3.11 or newer
- PostgreSQL
- `pip`
- A local `backend/.env` based on `backend/.env.example`
- Optional but recommended for RAG speed: PostgreSQL `pgvector`
- Gemini API key when live AI answers or embeddings are enabled
- Gmail app password or another SMTP credential when real email delivery is
  enabled

Frontend:

- Node.js with `npm`
- Frontend dependencies are defined in `frontend/package.json` and locked in
  `frontend/package-lock.json`
- A local `frontend/.env` based on `frontend/.env.example`

Do not commit local `.env` files, `frontend/node_modules/`, or
`backend/uploads/`.

## Backend Quick Start

Run backend commands from the backend folder:

```powershell
cd backend
py -m pip install -r requirements.txt
Copy-Item .env.example .env
py -m alembic upgrade head
py scripts/seed_admin.py
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

The detailed backend guide is in `backend/README.md`.

## Frontend Quick Start

Run frontend commands from the frontend folder:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open the app:

```text
http://127.0.0.1:5173
```

If PowerShell blocks `npm` with an execution policy error, use `npm.cmd`
instead:

```powershell
npm.cmd install
npm.cmd run dev
```

The detailed frontend guide is in `frontend/README.md`.

## Run Both Together

Use two terminals:

```powershell
cd backend
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
cd frontend
npm run dev
```

The frontend expects:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The backend should allow the Vite origins:

```env
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
FRONTEND_VERIFY_EMAIL_URL=http://127.0.0.1:5173/verify-email
FRONTEND_RESET_PASSWORD_URL=http://127.0.0.1:5173/reset-password
```

## Verification

Backend core checks:

```powershell
cd backend
py -m compileall app alembic tests
py tests/test_database_connection.py
py tests/test_model_mappers.py
py tests/test_auth_flow.py
py tests/test_user_hard_delete.py
py tests/test_document_lifecycle.py
py tests/test_document_text_extraction.py
py tests/test_ask_flow.py
py tests/test_chat_flow.py
```

Frontend build check:

```powershell
cd frontend
npm run build
```

Live backend API tests need the backend server running first. If a live login
test returns `429 Too Many Requests`, wait for the sensitive rate-limit window
or restart the local API process before rerunning the test.
