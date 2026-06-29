# Frontend

Dependency-free frontend for the MedKB Dev knowledge workspace.

## Run Locally

Start the backend first:

```powershell
cd backend
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then serve the frontend:

```powershell
cd frontend
py -m http.server 5173
```

Open:

```text
http://127.0.0.1:5173/login.html
```

## Pages

```text
login.html
register.html -> verify.html -> login.html -> chat.html
documents.html
users.html
permissions.html
```

The UI direction is clinical, multi-page, and lightly glass-styled. It follows
the MedKB Dev healthcare developer dashboard reference, with sidebar navigation,
top search/workspace controls, chat sources/context panels, document upload,
admin users, and document permissions.
