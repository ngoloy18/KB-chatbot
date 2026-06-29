import sys
from pathlib import Path

from pydantic import ValidationError

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.auth.schemas import RegisterRequest, ResetPasswordRequest
from app.schemas.users.schemas import UserUpdateRequest


def expect_validation_error(callback) -> None:
    """Fail the test if a weak password unexpectedly passes schema validation."""

    try:
        callback()
    except ValidationError:
        return
    raise AssertionError("Weak password should not pass validation.")


def check_password_validation() -> None:
    """Verify registration and password reset require strong passwords."""

    RegisterRequest(
        email="strong@example.com",
        password="Password123!",
        full_name="Strong User",
    )
    ResetPasswordRequest(
        token="reset-token-value-that-is-long-enough",
        new_password="NewPassword123!",
    )
    UserUpdateRequest(password="AdminPassword123!")

    expect_validation_error(
        lambda: RegisterRequest(
            email="weak@example.com",
            password="password123",
            full_name="Weak User",
        )
    )
    expect_validation_error(
        lambda: ResetPasswordRequest(
            token="reset-token-value-that-is-long-enough",
            new_password="NoSpecial123",
        )
    )
    expect_validation_error(lambda: UserUpdateRequest(password="NoNumber!"))

    print("Password validation OK.")


if __name__ == "__main__":
    try:
        check_password_validation()
    except Exception as exc:
        print("Password validation test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
