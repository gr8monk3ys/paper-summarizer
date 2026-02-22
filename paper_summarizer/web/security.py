"""Security middleware and helpers."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect HTTP to HTTPS in production based on X-Forwarded-Proto."""

    async def dispatch(self, request: Request, call_next):
        proto = request.headers.get("x-forwarded-proto", "").lower()
        if proto == "http":
            url = request.url.replace(scheme="https")
            return RedirectResponse(str(url), status_code=301)
        return await call_next(request)


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
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if self.app_env == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection by validating Origin/Referer for unsafe methods.

    Security model
    --------------
    This middleware guards against cross-site request forgery by comparing
    the Origin (or Referer) header of every state-changing request against
    the Host header.  The comparison is port-aware (full netloc) so that
    ``localhost:3000`` is not confused with ``localhost:8000``.

    Endpoints that accept unauthenticated form submissions (e.g. login and
    registration) are exempt because they have no existing session to
    protect.  All other state-changing endpoints are protected.

    Note: the auth system uses bearer tokens, not cookies, so the
    SameSite cookie attribute does not apply here.
    """

    # Auth endpoints are exempt because they are public form submissions
    # with no existing session to protect via CSRF.
    _DEFAULT_EXEMPT_PATHS: tuple[str, ...] = (
        "/static",
        "/auth/register",
        "/auth/login",
    )

    def __init__(self, app, exempt_paths: tuple[str, ...] | None = None) -> None:
        super().__init__(app)
        self.exempt_paths = (
            exempt_paths if exempt_paths is not None else self._DEFAULT_EXEMPT_PATHS
        )

    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            path = request.url.path
            if not any(path.startswith(prefix) for prefix in self.exempt_paths):
                origin = request.headers.get("origin") or request.headers.get("referer")
                if origin:
                    # Port-aware comparison: use full netloc (host:port) so
                    # that e.g. localhost:3000 != localhost:8000.
                    origin_netloc = urlparse(origin).netloc
                    request_netloc = request.headers.get("host", "")
                    if origin_netloc and origin_netloc != request_netloc:
                        logger.warning(
                            "CSRF origin mismatch: origin=%s, host=%s, path=%s",
                            origin_netloc,
                            request_netloc,
                            path,
                        )
                        return JSONResponse(
                            {"error": "Invalid origin"}, status_code=403
                        )
        return await call_next(request)
