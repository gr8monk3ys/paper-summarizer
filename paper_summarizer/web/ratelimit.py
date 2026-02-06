"""Simple in-memory rate limiter middleware."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, DefaultDict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


@dataclass
class RateLimitConfig:
    requests: int
    window_seconds: int
    enabled: bool = True


class RateLimiter:
    def __init__(self, config: RateLimitConfig) -> None:
        self.config = config
        self._buckets: DefaultDict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        if not self.config.enabled:
            return True
        now = time.monotonic()
        window_start = now - self.config.window_seconds
        bucket = self._buckets[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= self.config.requests:
            return False
        bucket.append(now)
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter, exempt_paths: tuple[str, ...] = ("/static",)) -> None:
        super().__init__(app)
        self.limiter = limiter
        self.exempt_paths = exempt_paths

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self.exempt_paths):
            return await call_next(request)

        client_ip = request.headers.get("x-forwarded-for")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        if not self.limiter.allow(client_ip):
            return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)

        return await call_next(request)
