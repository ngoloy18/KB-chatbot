# KB Chat Bot Dev Frontend

React/Vite frontend for the KB Chat Bot Dev AI developer assistant.

This UI should stay aligned with the real FastAPI backend. Do not add visible
features that do not exist in `../backend/BACKEND_CAPABILITY_LOG.md`.

## Tech

- Vite + React
- React Router
- Tailwind CSS
- lucide-react icons
- react-markdown, remark-gfm, and rehype-sanitize for safe AI Markdown answers
- localStorage token auth
- FastAPI backend at `http://127.0.0.1:8000`

## Requirements

- Node.js with `npm`
- Dependencies are defined in `package.json` and locked in `package-lock.json`
- Backend running on `http://127.0.0.1:8000`
- Local `frontend/.env` copied from `frontend/.env.example`

## Environment

Create `frontend/.env`:

```powershell
Copy-Item .env.example .env
```

Expected value:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The backend must also allow the frontend origin through CORS:

```env
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
```

## Run Locally

Start the backend in one terminal:

```powershell
cd backend
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

If PowerShell blocks `npm`, use `npm.cmd`:

```powershell
npm.cmd install
npm.cmd run dev
```

## Build Check

```powershell
npm run build
```

## Supported Routes

```text
/login
/register
/verify-email
/forgot-password
/reset-password
/chat
/documents
/documents/:id
/admin/users
```

## Backend Features Used

- Register, verify email, resend verification, login, refresh, logout
- Forgot password and reset password
- Authenticated chat with conversation history and sources
- Documents list/search/detail/upload/update/delete/restore/version history
- Admin user list/update/soft-delete/restore/hard-delete
- Admin document permissions through document detail screens

Not supported by the backend right now:

- GitHub login
- Username login
- Workspace switching
- Notifications
- Department filters
- Invite flow
- Viewer/developer/custom roles
- PDF/DOCX upload
- Top-level `/api/permissions` page

The API client lives in `src/api/client.js` and uses the `/api` backend prefix.
