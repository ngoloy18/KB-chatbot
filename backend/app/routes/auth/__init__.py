from fastapi import APIRouter

from app.routes.auth.account import router as account_router
from app.routes.auth.passwords import router as password_router
from app.routes.auth.profile import router as profile_router
from app.routes.auth.sessions import router as session_router


# Keep main.py simple while the actual auth endpoints live in focused files.
router = APIRouter()
router.include_router(account_router)
router.include_router(session_router)
router.include_router(password_router)
router.include_router(profile_router)
