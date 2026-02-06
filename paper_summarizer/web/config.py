"""FastAPI configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path


APP_ENV = os.getenv("APP_ENV", "development")
DEFAULT_SETTINGS = {
    "APP_ENV": APP_ENV,
    "UPLOAD_FOLDER": Path(os.getenv("UPLOAD_FOLDER", "uploads")),
    "DATABASE_URL": os.getenv("DATABASE_URL", "sqlite:///data/paper_summarizer.db"),
    "SECRET_KEY": os.getenv("SECRET_KEY", "dev-secret-change-me"),
    "ACCESS_TOKEN_EXPIRE_MINUTES": int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")),
    "AUTO_CREATE_DB": os.getenv("AUTO_CREATE_DB", "true" if APP_ENV != "production" else "false").lower() == "true",
    "MAX_CONTENT_LENGTH": 16 * 1024 * 1024,
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
}


def load_settings(overrides: dict | None = None) -> dict:
    """Load settings with optional overrides."""
    settings = dict(DEFAULT_SETTINGS)
    if overrides:
        settings.update(overrides)

    upload_folder = Path(settings["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    settings["UPLOAD_FOLDER"] = upload_folder

    db_url = settings["DATABASE_URL"]
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)

    return settings
