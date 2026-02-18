"""FastAPI configuration helpers."""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

logger = logging.getLogger(__name__)

APP_ENV = os.getenv("APP_ENV", "development")


def _resolve_secret_key() -> str:
    """Return the SECRET_KEY, raising in non-development environments if unset."""
    secret = os.getenv("SECRET_KEY")
    if secret:
        return secret
    if APP_ENV == "development":
        random_key = secrets.token_hex(32)
        logger.warning(
            "SECRET_KEY not set — generated a random key. "
            "Sessions will NOT persist across restarts."
        )
        return random_key
    raise RuntimeError(
        "SECRET_KEY environment variable is required when APP_ENV "
        f"is '{APP_ENV}' (i.e. not 'development'). Set it before starting the server."
    )


DEFAULT_SETTINGS = {
    "APP_ENV": APP_ENV,
    "UPLOAD_FOLDER": Path(os.getenv("UPLOAD_FOLDER", "uploads")),
    "DATABASE_URL": os.getenv("DATABASE_URL", "sqlite:///data/paper_summarizer.db"),
    "SECRET_KEY": _resolve_secret_key(),
    "ACCESS_TOKEN_EXPIRE_MINUTES": int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
    "AUTO_CREATE_DB": os.getenv("AUTO_CREATE_DB", "true" if APP_ENV != "production" else "false").lower() == "true",
    "MAX_CONTENT_LENGTH": 16 * 1024 * 1024,
    "STORAGE_LIMIT_BYTES": int(os.getenv("STORAGE_LIMIT_BYTES", str(1024 * 1024 * 1024))),
    "ALLOWED_EXTENSIONS": {"txt", "pdf", "md", "rst"},
    "DEFAULT_MODEL": os.getenv("DEFAULT_MODEL", "t5-small"),
    "DEFAULT_PROVIDER": os.getenv("DEFAULT_PROVIDER", "local"),
    "DEFAULT_NUM_SENTENCES": int(os.getenv("DEFAULT_NUM_SENTENCES", "5")),
    "MIN_SENTENCES": int(os.getenv("MIN_SENTENCES", "1")),
    "MAX_SENTENCES": int(os.getenv("MAX_SENTENCES", "20")),
    "RATE_LIMIT_ENABLED": os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
    "RATE_LIMIT_PER_MINUTE": int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    "RATE_LIMIT_WINDOW_SECONDS": int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
    "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
    "REDIS_URL": os.getenv("REDIS_URL", ""),
    "SENTRY_DSN": os.getenv("SENTRY_DSN", ""),
    "METRICS_ENABLED": os.getenv("METRICS_ENABLED", "true").lower() == "true",
    "LOCAL_MODELS_ENABLED": os.getenv("LOCAL_MODELS_ENABLED", "true" if APP_ENV != "production" else "false").lower() == "true",
    "CORS_ALLOWED_ORIGINS": os.getenv("CORS_ALLOWED_ORIGINS", ""),
}


def validate_settings(settings: dict) -> None:
    """Validate settings, raising ValueError on invalid configuration.

    In production (APP_ENV=production):
      - SECRET_KEY must be explicitly set (non-empty).
      - DATABASE_URL must be set.
      - TOGETHER_API_KEY env var must be set if DEFAULT_PROVIDER is 'together_ai'.
    """
    app_env = settings.get("APP_ENV", "development")
    if app_env != "production":
        return

    if not settings.get("SECRET_KEY"):
        raise ValueError(
            "SECRET_KEY must be explicitly set in production (APP_ENV=production)."
        )

    if not settings.get("DATABASE_URL"):
        raise ValueError(
            "DATABASE_URL must be set in production (APP_ENV=production)."
        )

    if settings.get("DEFAULT_PROVIDER") == "together_ai":
        if not os.getenv("TOGETHER_API_KEY"):
            raise ValueError(
                "TOGETHER_API_KEY environment variable must be set when "
                "DEFAULT_PROVIDER is 'together_ai' in production."
            )


def load_settings(overrides: dict | None = None) -> dict:
    """Load settings with optional overrides."""
    settings = dict(DEFAULT_SETTINGS)
    if overrides:
        settings.update(overrides)

    upload_folder = Path(str(settings["UPLOAD_FOLDER"]))
    upload_folder.mkdir(parents=True, exist_ok=True)
    settings["UPLOAD_FOLDER"] = upload_folder

    db_url = str(settings["DATABASE_URL"])
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)

    validate_settings(settings)

    return settings
