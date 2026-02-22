"""Prometheus metrics helpers."""

from __future__ import annotations

import time
from typing import Iterable

from fastapi import Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "paper_summarizer_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "paper_summarizer_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app, skip_paths: Iterable[str] = ("/metrics", "/static")
    ) -> None:
        super().__init__(app)
        self.skip_paths = tuple(skip_paths)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self.skip_paths):
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.method, path).observe(duration)
        return response


def metrics_response() -> Response:
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
