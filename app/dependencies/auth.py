from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.constants_auth import (
    AUTH_SCHEME_BEARER,
    JWT_SUBJECT_CLAIM,
    USER_ROLE_ADMIN,
)
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.models_database import User
from app.repositories.repositories_users import user_repository


# HTTPBearer reads the Authorization: Bearer <token> header from each request.
# auto_error=False lets this file return one clear custom 401 error.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return the authenticated user from the Bearer token."""

    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid access token.",
        headers={"WWW-Authenticate": AUTH_SCHEME_BEARER},
    )
    if credentials is None or credentials.scheme.lower() != AUTH_SCHEME_BEARER.lower():
        raise auth_error

    try:
        # The token subject is the user id written by create_access_token().
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(str(payload.get(JWT_SUBJECT_CLAIM)))
    except (TypeError, ValueError):
        raise auth_error

    # Loading the user from the database catches deleted or disabled accounts.
    user = await user_repository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise auth_error
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require the authenticated user to have admin role."""

    # Route functions can depend on this helper instead of repeating role checks.
    if current_user.role != USER_ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role is required.",
        )
    return current_user
