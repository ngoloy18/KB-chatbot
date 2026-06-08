from fastapi import FastAPI

from app.routes.documents import router as documents_router


app = FastAPI(
    title="Developer KB Chatbot API",
    version="0.1.0",
    description="Week 1 FastAPI foundation for managing developer knowledge documents.",
)

app.include_router(documents_router)


@app.get("/", tags=["health"], summary="API health check")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "developer-kb-chatbot"}
