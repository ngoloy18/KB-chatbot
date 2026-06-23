import os
import sys
from pathlib import Path
from uuid import uuid4

# Set JWT_SECRET before importing app settings/security.
os.environ.setdefault("JWT_SECRET", "test-secret-for-auth-security")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.constants.constants_auth import JWT_ROLE_CLAIM, JWT_SUBJECT_CLAIM, USER_ROLE_ADMIN
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def check_auth_security() -> None:
    """Verify password hashing and JWT helpers work."""

    hashed_password = hash_password("password123")
    assert hashed_password != "password123"
    assert verify_password("password123", hashed_password)
    assert not verify_password("wrong-password", hashed_password)

    user_id = uuid4()
    token = create_access_token(user_id=user_id, role=USER_ROLE_ADMIN)
    payload = decode_access_token(token)
    assert payload[JWT_SUBJECT_CLAIM] == str(user_id)
    assert payload[JWT_ROLE_CLAIM] == USER_ROLE_ADMIN

    print("Auth security helpers OK.")


if __name__ == "__main__":
    try:
        check_auth_security()
    except Exception as exc:
        print("Auth security test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
