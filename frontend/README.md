# MedKB Dev Frontend

React frontend for the MedKB Dev healthcare AI developer assistant.

## Tech

- Vite + React
- React Router
- Tailwind CSS
- lucide-react icons
- localStorage token auth
- FastAPI backend at `http://127.0.0.1:8000`

## Run Locally

Install Node.js first. Then:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Start the backend in another terminal:

```powershell
cd backend
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Routes

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

The API client lives in `src/api/client.js` and uses the `/api` backend prefix.
It calls the real backend routes listed in `backend/BACKEND_CAPABILITY_LOG.md`.
