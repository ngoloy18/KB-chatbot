from fastapi import APIRouter, FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.rate_limiter import RateLimitMiddleware
from app.db.session import engine
from app.routes.routes_auth import router as auth_router
from app.routes.routes_document_permissions import router as document_permissions_router
from app.routes.routes_documents import router as documents_router
from app.routes.routes_health import router as health_router
from app.routes.routes_users import router as users_router

# Group every public API endpoint under /api so route modules can keep their
# own focused prefixes, such as /documents.
api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(document_permissions_router)
api_router.include_router(documents_router)
api_router.include_router(health_router)
api_router.include_router(users_router)


# FastAPI application metadata appears in the generated Swagger/OpenAPI docs.
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=settings.app_description,
)
register_exception_handlers(app)
app.add_middleware(
    RateLimitMiddleware,
    enabled=settings.rate_limit_enabled,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
    excluded_paths=settings.rate_limit_excluded_paths,
)


@app.on_event("startup")
async def check_database_connection() -> None:
    """Confirm the database is reachable when the API starts."""

    try:
        # SELECT 1 is a tiny query that proves the database accepts connections.
        async with engine.connect() as connection:
            await connection.scalar(text("SELECT 1"))
    except Exception as exc:
        # Raising the exception stops startup so a broken DB is visible immediately.
        print(f"database connect failed: {exc}")
        raise

    # This is the message the user asked to see in the terminal on successful start.
    print("database connect is working")


# Attach the /api router after the app is created so all API routes are active.
app.include_router(api_router)
