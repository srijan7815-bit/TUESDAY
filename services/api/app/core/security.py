"""Authentication, request limits, rate limits, and browser security headers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings, get_settings

SESSION_COOKIE = "tuesday_session"
PUBLIC_PATHS = {
    "/",
    "/health",
    "/health/live",
    "/health/ready",
    "/manifest.webmanifest",
    "/service-worker.js",
    "/offline.html",
    "/v1/auth/session",
    "/v1/auth/status",
}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_session_cookie(settings: Settings, *, now: int | None = None) -> str:
    issued = int(now if now is not None else time.time())
    payload = {"iat": issued, "exp": issued + settings.tuesday_session_ttl_sec, "v": 1}
    encoded = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        settings.tuesday_secret_key.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded}.{_b64(signature)}"


def verify_session_cookie(
    value: str | None, settings: Settings, *, now: int | None = None
) -> bool:
    if not value:
        return False
    try:
        encoded, supplied = value.split(".", 1)
        expected = hmac.new(
            settings.tuesday_secret_key.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_unb64(supplied), expected):
            return False
        payload = json.loads(_unb64(encoded))
        current = int(now if now is not None else time.time())
        return payload.get("v") == 1 and int(payload.get("exp", 0)) >= current
    except (ValueError, TypeError, json.JSONDecodeError):
        return False


def request_is_authenticated(
    request: Request, settings: Settings | None = None
) -> bool:
    settings = settings or get_settings()
    if not settings.auth_required:
        return True
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and hmac.compare_digest(
        auth[7:].strip(), settings.tuesday_access_token
    ):
        return True
    return verify_session_cookie(request.cookies.get(SESSION_COOKIE), settings)


class RequestGuardsMiddleware(BaseHTTPMiddleware):
    """Single-instance limiter plus auth and safe response headers."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_gc = 0.0

    @staticmethod
    def _client_key(request: Request) -> str:
        # Uvicorn's trusted proxy middleware normalizes request.client in production.
        # Reading X-Forwarded-For here would let direct clients rotate a spoofed header.
        return request.client.host if request.client else "unknown"

    def _rate_limited(self, request: Request, settings: Settings) -> bool:
        if not request.url.path.startswith("/v1/"):
            return False
        now = time.monotonic()
        is_login = request.url.path == "/v1/auth/session" and request.method == "POST"
        key = f"{self._client_key(request)}:{'login' if is_login else 'api'}"
        limit = (
            min(10, settings.tuesday_rate_limit_per_minute)
            if is_login
            else settings.tuesday_rate_limit_per_minute
        )
        bucket = self._hits[key]
        cutoff = now - 60
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
        if now - self._last_gc > 300:
            self._last_gc = now
            for stale_key in [
                k for k, v in self._hits.items() if not v or v[-1] < cutoff
            ]:
                self._hits.pop(stale_key, None)
        return False

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        length = request.headers.get("content-length")
        if (
            length
            and length.isdigit()
            and int(length) > settings.tuesday_max_request_bytes
        ):
            response: Response = JSONResponse(
                {"detail": "Request body is too large"}, status_code=413
            )
        elif self._rate_limited(request, settings):
            response = JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        elif (
            request.url.path.startswith("/v1/")
            and request.url.path not in PUBLIC_PATHS
            and not request_is_authenticated(request, settings)
        ):
            response = JSONResponse(
                {"detail": "Authentication required"}, status_code=401
            )
        else:
            response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), payment=(), usb=(), microphone=(self)",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
            "form-action 'self'; object-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'",
        )
        if settings.tuesday_env == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        if request.url.path.startswith("/v1/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response
