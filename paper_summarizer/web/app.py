"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles

from .config import load_settings
from .db import create_db_engine, init_db
from .auth import router as auth_router
from .middleware import MaxContentSizeMiddleware
from .metrics import MetricsMiddleware, metrics_response
from .observability import RequestLoggingMiddleware
from .ratelimit import RateLimitConfig, RateLimiter, RateLimitMiddleware
from .security import CSRFMiddleware, HTTPSRedirectMiddleware, SecurityHeadersMiddleware
from .routes import router, STATIC_DIR
import sentry_sdk
from arq import create_pool
from arq.connections import RedisSettings


def create_app(settings_overrides: dict | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = load_settings(settings_overrides)
    logger = logging.getLogger("paper_summarizer")
    if not logger.handlers:
        log_level = getattr(
            logging, str(settings.get("LOG_LEVEL", "INFO")).upper(), logging.INFO
        )
        logging.basicConfig(level=log_level)

    sentry_dsn = str(settings.get("SENTRY_DSN", "")).strip()
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn, environment=str(settings.get("APP_ENV", "development"))
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_db_engine(settings["DATABASE_URL"])
        init_db(
            engine,
            reset=bool(settings.get("TESTING")),
            auto_create=bool(settings.get("AUTO_CREATE_DB", True)),
        )
        app.state.settings = settings
        app.state.engine = engine
        redis_url = str(settings.get("REDIS_URL", "")).strip()
        app.state.redis = None
        if redis_url:
            app.state.redis = await create_pool(RedisSettings.from_dsn(redis_url))
        try:
            yield
        finally:
            if app.state.redis is not None:
                await app.state.redis.close()

    app = FastAPI(title="Paper Summarizer", lifespan=lifespan)

    allowed_origins = []
    for o in str(settings.get("CORS_ALLOWED_ORIGINS", "")).split(","):
        origin = o.strip()
        if origin and origin.startswith(("https://", "http://")):
            allowed_origins.append(origin)
        elif origin:
            logger.warning(
                "Ignoring invalid CORS origin (must start with http:// or https://): %s",
                origin,
            )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app_env = str(settings.get("APP_ENV", "development"))
    if app_env == "production":
        app.add_middleware(HTTPSRedirectMiddleware)

    redis_url = str(settings.get("REDIS_URL", "")).strip()
    limiter = RateLimiter(
        RateLimitConfig(
            requests=int(settings.get("RATE_LIMIT_PER_MINUTE", 60)),
            window_seconds=int(settings.get("RATE_LIMIT_WINDOW_SECONDS", 60)),
            enabled=bool(settings.get("RATE_LIMIT_ENABLED", True)),
        ),
        redis_url=redis_url,
    )
    auth_limiter = RateLimiter(
        RateLimitConfig(
            requests=int(settings.get("AUTH_RATE_LIMIT_PER_MINUTE", 20)),
            window_seconds=60,
            enabled=bool(settings.get("RATE_LIMIT_ENABLED", True)),
        ),
        redis_url=redis_url,
    )
    app.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        exempt_paths=("/static", "/health", "/metrics"),
        auth_limiter=auth_limiter,
    )
    app.add_middleware(RequestLoggingMiddleware, logger=logger)
    app.add_middleware(CSRFMiddleware, exempt_paths=("/static", "/health"))
    app.add_middleware(
        SecurityHeadersMiddleware, app_env=str(settings.get("APP_ENV", "development"))
    )
    app.add_middleware(
        MaxContentSizeMiddleware,
        max_bytes=int(settings.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)),
        exempt_paths=("/static", "/health"),
    )
    if settings.get("METRICS_ENABLED", True):
        app.add_middleware(MetricsMiddleware)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)
    app.include_router(auth_router)

    if settings.get("METRICS_ENABLED", True):
        app.add_api_route("/metrics", metrics_response, methods=["GET"])

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        payload = {"error": exc.detail}
        if request_id:
            payload["request_id"] = request_id
        return JSONResponse(payload, status_code=exc.status_code)

    return app


app = create_app()
