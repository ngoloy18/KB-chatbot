from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.constants.constants_auth import (
    JWT_EXPIRES_AT_CLAIM,
    JWT_ROLE_CLAIM,
    JWT_SUBJECT_CLAIM,
)
from app.core.config import settings


# Passlib hides bcrypt details behind one context so the rest of the app only
# needs to call hash_password() and verify_password().
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password before storing it."""

    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return whether a plaintext password matches a stored hash."""

    return password_context.verify(plain_password, hashed_password)


def create_access_token(user_id: UUID, role: str) -> str:
    """Create a signed JWT access token for one user."""

    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is missing. Add it to your .env file.")

    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    # "sub" is the standard JWT subject field. Here it stores our user's UUID.
    # Role is included so admin checks can read the user's permission level.
    payload = {
        JWT_SUBJECT_CLAIM: str(user_id),
        JWT_ROLE_CLAIM: role,
        JWT_EXPIRES_AT_CLAIM: expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token."""

    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is missing. Add it to your .env file.")

    try:
        # jwt.decode checks the signature and the exp timestamp before returning data.
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired access token.") from exc
