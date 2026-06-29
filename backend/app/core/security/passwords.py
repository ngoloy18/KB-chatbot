from passlib.context import CryptContext


# Passlib hides bcrypt details behind one context so the rest of the app only
# needs to call hash_password() and verify_password().
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password before storing it."""

    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return whether a plaintext password matches a stored hash."""

    return password_context.verify(plain_password, hashed_password)
