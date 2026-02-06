"""Custom middleware helpers."""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class MaxContentSizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int, exempt_paths: tuple[str, ...] = ("/static",)) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes
        self.exempt_paths = exempt_paths

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self.exempt_paths):
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
            except ValueError:
                return JSONResponse({"error": "Invalid content length"}, status_code=400)
            if length > self.max_bytes:
                return JSONResponse({"error": "Request body too large"}, status_code=413)

        return await call_next(request)
