"""FastAPI middleware for request logging and rate limiting.

RequestLoggingMiddleware — structured logging for every HTTP request with
timing, status codes, and client info.

RateLimitMiddleware — token-bucket rate limiter keyed by client IP. Rejects
requests that exceed the configured rate with HTTP 429.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger()


# ── Request Logging ─────────────────────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status code, and duration.

    Skips noisy health-check requests by default to keep logs clean in
    environments with frequent liveness probes.
    """

    SKIP_PATHS = {"/health", "/openapi.json", "/docs", "/redoc"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        client_ip = self._get_client_ip(request)
        request_id = request.headers.get("x-request-id", "")

        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            request_id=request_id,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                client_ip=client_ip,
                duration_ms=round(duration_ms, 2),
                error=str(exc),
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000

        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
            client_ip=client_ip,
            request_id=request_id,
        )

        response.headers["X-Request-Duration-Ms"] = str(round(duration_ms, 2))
        if request_id:
            response.headers["X-Request-Id"] = request_id

        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For behind a reverse proxy."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = request.client
        return client.host if client else "unknown"


# ── Rate Limiting ───────────────────────────────────────────────────────

@dataclass
class _TokenBucket:
    """Simple token-bucket for a single client."""

    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def consume(self, now: Optional[float] = None) -> bool:
        """Try to consume one token.  Returns True if allowed."""
        now = now or time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP token-bucket rate limiter.

    Parameters
    ----------
    app : ASGI application
    requests_per_minute : int
        Maximum sustained request rate per client IP (default 60).
    burst : int
        Maximum burst size — how many requests can arrive at once before
        throttling kicks in (default 20).
    """

    # Paths exempt from rate limiting (health probes, docs)
    EXEMPT_PATHS = {"/health", "/openapi.json", "/docs", "/redoc"}

    def __init__(
        self,
        app: Callable,
        requests_per_minute: int = 60,
        burst: int = 20,
    ) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self._refill_rate = requests_per_minute / 60.0  # tokens per second
        self._buckets: Dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(
                capacity=float(burst),
                refill_rate=self._refill_rate,
                tokens=float(burst),
            )
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        client_ip = RequestLoggingMiddleware._get_client_ip(request)
        bucket = self._buckets[client_ip]

        if not bucket.consume():
            logger.warning(
                "rate_limited",
                client_ip=client_ip,
                path=request.url.path,
                rpm_limit=self.requests_per_minute,
            )
            retry_after = int(1.0 / self._refill_rate) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)

        # Inform clients of their remaining budget
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))

        return response
