import sys
from pathlib import Path

# Add the project root to Python's import path when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.rate_limiter import InMemoryRateLimiter


def check_rate_limiter() -> None:
    """Verify the in-memory limiter blocks requests after the configured limit."""

    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)

    first_allowed, first_remaining, first_reset = limiter.check_limit("client-a")
    assert first_allowed is True
    assert first_remaining == 1
    assert first_reset > 0

    second_allowed, second_remaining, _ = limiter.check_limit("client-a")
    assert second_allowed is True
    assert second_remaining == 0

    third_allowed, third_remaining, third_reset = limiter.check_limit("client-a")
    assert third_allowed is False
    assert third_remaining == 0
    assert third_reset > 0

    other_client_allowed, other_client_remaining, _ = limiter.check_limit("client-b")
    assert other_client_allowed is True
    assert other_client_remaining == 1

    print("Rate limiter OK.")


if __name__ == "__main__":
    try:
        check_rate_limiter()
    except Exception as exc:
        print("Rate limiter test FAILED.")
        print(f"Reason: {exc}")
        raise SystemExit(1) from exc
