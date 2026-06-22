from fastapi import APIRouter

from app.core.config import settings


router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="API health check")
async def health_check() -> dict[str, str]:
    """Confirm the API process is running."""

    return {"status": "ok", "service": settings.app_name}
