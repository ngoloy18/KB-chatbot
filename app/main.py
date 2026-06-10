# This is the main application file for the Developer KB Chatbot API, which sets up the FastAPI app and includes the document-related routes.
from fastapi import APIRouter, FastAPI
from app.routes.routes_documents import router as documents_router

api_router = APIRouter(prefix="/api")
api_router.include_router(documents_router)


@api_router.get("/health", tags=["health"], summary="API health check")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "developer-kb-chatbot"}


app = FastAPI(
    title="Developer KB Chatbot API",
    version="0.1.0",
    description="Week 1 FastAPI foundation for managing developer knowledge documents.",
)
app.include_router(api_router)
