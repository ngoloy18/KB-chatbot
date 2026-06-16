from fastapi import APIRouter, FastAPI
from sqlalchemy import text

from app.db.session import engine
from app.routes.routes_documents import router as documents_router

# Group every public API endpoint under /api so route modules can keep their
# own focused prefixes, such as /documents.
api_router = APIRouter(prefix="/api")
api_router.include_router(documents_router)


@api_router.get("/health", tags=["health"], summary="API health check")
async def health_check() -> dict[str, str]:
    """Small endpoint used to confirm the API process is running."""

    # This endpoint does not check the database; startup handles DB connectivity.
    return {"status": "ok", "service": "developer-kb-chatbot"}


# FastAPI application metadata appears in the generated Swagger/OpenAPI docs.
app = FastAPI(
    title="Developer KB Chatbot API",
    version="0.1.2",
    description="Week 2 Fastapi with SQLAlchemy.",
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
