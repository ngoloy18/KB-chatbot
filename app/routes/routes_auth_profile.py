from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.models.models_database import User
from app.schemas.schemas_auth import UserResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the user represented by the Bearer token."""

    # get_current_user already verified the token and loaded the database user.
    return UserResponse.model_validate(current_user)
