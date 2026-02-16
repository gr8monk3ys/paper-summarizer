"""Rate limiter middleware with Redis backend and in-memory fallback."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, DefaultDict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    requests: int
    window_seconds: int
    enabled: bool = True


class InMemoryBackend:
    """In-memory sliding window rate limiter (single-process only)."""

    def __init__(self) -> None:
        self._buckets: DefaultDict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        window_start = now - window_seconds
        bucket = self._buckets[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= max_requests:
            return False
        bucket.append(now)
        return True


class RedisBackend:
    """Redis-backed sliding window rate limiter (works across processes)."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis = None

    def _get_client(self):
        if self._redis is None:
            try:
                import redis as redis_lib

                self._redis = redis_lib.Redis.from_url(
                    self._redis_url, decode_responses=True
                )
                self._redis.ping()
            except Exception:
                logger.warning("Redis rate-limit backend unavailable, connection failed")
                self._redis = None
        return self._redis

    def allow(self, key: str, max_requests: int, window_seconds: int) -> bool:
        client = self._get_client()
        if client is None:
            return True  # fail open if Redis is down

        redis_key = f"ratelimit:{key}"
        now = time.time()
        window_start = now - window_seconds

        pipe = client.pipeline(transaction=True)
        try:
            pipe.zremrangebyscore(redis_key, "-inf", window_start)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window_seconds)
            results = pipe.execute()
            current_count = results[1]
            return current_count < max_requests
        except Exception:
            logger.warning("Redis rate-limit check failed, allowing request")
            return True


class RateLimiter:
    def __init__(self, config: RateLimitConfig, redis_url: str = "") -> None:
        self.config = config
        if redis_url:
            self._backend = RedisBackend(redis_url)
            self._fallback = InMemoryBackend()
        else:
            self._backend = InMemoryBackend()
            self._fallback = None

    def allow(self, key: str) -> bool:
        if not self.config.enabled:
            return True
        allowed = self._backend.allow(
            key, self.config.requests, self.config.window_seconds
        )
        if allowed is None and self._fallback is not None:
            return self._fallback.allow(
                key, self.config.requests, self.config.window_seconds
            )
        return allowed


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
