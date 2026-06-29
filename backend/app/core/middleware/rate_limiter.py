from dataclasses import dataclass
from threading import Lock
import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


@dataclass
class RateLimitBucket:
    """Track one client's request count inside the current time window."""

    window_start: float
    request_count: int = 0


class InMemoryRateLimiter:
    """Simple fixed-window limiter for local development and single-server apps."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, RateLimitBucket] = {}
        self._lock = Lock()

    def check_limit(self, key: str) -> tuple[bool, int, int]:
        """Return whether a request is allowed, remaining quota, and reset seconds."""

        now = time.time()

        with self._lock:
            bucket = self._buckets.get(key)

            if bucket is None or now - bucket.window_start >= self.window_seconds:
                bucket = RateLimitBucket(window_start=now)
                self._buckets[key] = bucket

            reset_seconds = max(1, int(bucket.window_start + self.window_seconds - now))

            if bucket.request_count >= self.max_requests:
                return False, 0, reset_seconds

            bucket.request_count += 1
            remaining_requests = max(0, self.max_requests - bucket.request_count)
            return True, remaining_requests, reset_seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply request limits before route handlers run."""

    def __init__(
        self,
        app: ASGIApp,
        enabled: bool,
        max_requests: int,
        window_seconds: int,
        excluded_paths: set[str],
        route_limits: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.excluded_paths = excluded_paths
        self.default_limiter = InMemoryRateLimiter(
            max_requests=max_requests,
            window_seconds=window_seconds,
        )
        # Certain routes like login and upload should have tighter limits than
        # the general API because attackers tend to target them first.
        self.route_limiters = {
            path: InMemoryRateLimiter(
                max_requests=limit[0],
                window_seconds=limit[1],
            )
            for path, limit in (route_limits or {}).items()
        }

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], object],
    ) -> Response:
        if not self.enabled or request.url.path in self.excluded_paths:
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        limiter = self.route_limiters.get(request.url.path, self.default_limiter)
        if limiter is self.default_limiter:
            limit_key = client_host
        else:
            limit_key = f"{client_host}:{request.url.path}"
        allowed, remaining_requests, reset_seconds = limiter.check_limit(limit_key)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": {"message": "Too many requests. Try again later."}},
                headers={
                    "Retry-After": str(reset_seconds),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining_requests)
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)
        return response
