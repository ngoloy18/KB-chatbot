from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.constants.constants_auth import (
    JWT_ACCESS_TOKEN_TYPE,
    JWT_EXPIRES_AT_CLAIM,
    JWT_ID_CLAIM,
    JWT_REFRESH_TOKEN_TYPE,
    JWT_ROLE_CLAIM,
    JWT_SUBJECT_CLAIM,
    JWT_TOKEN_TYPE_CLAIM,
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

    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    # "sub" is the standard JWT subject field. Here it stores our user's UUID.
    # Role is included so admin checks can read the user's permission level.
    # token_type lets the API reject refresh tokens on normal protected routes.
    return _create_token(
        {
            JWT_SUBJECT_CLAIM: str(user_id),
            JWT_ROLE_CLAIM: role,
            JWT_TOKEN_TYPE_CLAIM: JWT_ACCESS_TOKEN_TYPE,
        },
        expires_at=expires_at,
    )


def create_refresh_token(user_id: UUID) -> str:
    """Create a longer-lived JWT used only to request a new access token."""

    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.refresh_token_expire_minutes
    )
    # Refresh tokens only need the user id. The latest role is loaded from DB
    # before a new access token is created.
    return _create_token(
        {
            JWT_SUBJECT_CLAIM: str(user_id),
            JWT_ID_CLAIM: uuid4().hex,
            JWT_TOKEN_TYPE_CLAIM: JWT_REFRESH_TOKEN_TYPE,
        },
        expires_at=expires_at,
    )


def _create_token(payload: dict, expires_at: datetime) -> str:
    """Sign a JWT payload with a shared expiration timestamp."""

    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is missing. Add it to your .env file.")

    payload = {
        **payload,
        JWT_EXPIRES_AT_CLAIM: expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token."""

    payload = _decode_token(token)
    if payload.get(JWT_TOKEN_TYPE_CLAIM) != JWT_ACCESS_TOKEN_TYPE:
        raise ValueError("Invalid access token.")
    return payload


def decode_refresh_token(token: str) -> dict:
    """Decode and verify a JWT refresh token."""

    payload = _decode_token(token)
    if payload.get(JWT_TOKEN_TYPE_CLAIM) != JWT_REFRESH_TOKEN_TYPE:
        raise ValueError("Invalid refresh token.")
    return payload


def hash_token(token: str) -> str:
    """Hash a token before storing it so the raw token is not saved."""

    return sha256(token.encode("utf-8")).hexdigest()


def _decode_token(token: str) -> dict:
    """Decode a JWT and verify its signature and expiration."""

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
        raise ValueError("Invalid or expired token.") from exc
