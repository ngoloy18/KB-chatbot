from fastapi import APIRouter, FastAPI

from app.routes.routes_documents import router as documents_router

# Group every public API endpoint under /api so route modules can keep their
# own focused prefixes, such as /documents.
api_router = APIRouter(prefix="/api")
api_router.include_router(documents_router)


@api_router.get("/health", tags=["health"], summary="API health check")
async def health_check() -> dict[str, str]:
    """Small endpoint used to confirm the API process is running."""

    return {"status": "ok", "service": "developer-kb-chatbot"}


# FastAPI application metadata appears in the generated Swagger/OpenAPI docs.
app = FastAPI(
    title="Developer KB Chatbot API",
    version="0.1.0",
    description="Week 1 FastAPI foundation for managing developer knowledge documents.",
)

# Attach the /api router after the app is created so all API routes are active.
app.include_router(api_router)
