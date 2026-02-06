"""Security middleware and helpers."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, app_env: str) -> None:
        super().__init__(app)
        self.app_env = app_env

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'",
        )
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if self.app_env == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """Basic CSRF protection by validating Origin/Referer for unsafe methods."""

    def __init__(self, app, exempt_paths: tuple[str, ...] = ("/static",)) -> None:
        super().__init__(app)
        self.exempt_paths = exempt_paths

    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            path = request.url.path
            if not any(path.startswith(prefix) for prefix in self.exempt_paths):
                origin = request.headers.get("origin") or request.headers.get("referer")
                if origin:
                    origin_host = urlparse(origin).netloc
                    if origin_host and origin_host != request.headers.get("host", ""):
                        return JSONResponse({"error": "Invalid origin"}, status_code=403)
        return await call_next(request)
