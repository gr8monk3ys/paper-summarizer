"""Shared dependencies for web route modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request

from .config import load_settings
from .db import create_db_engine, init_db

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


def _get_settings(request: Request) -> dict[str, Any]:
    if not hasattr(request.app.state, "settings"):
        settings = load_settings()
        engine = create_db_engine(settings["DATABASE_URL"])
        init_db(
            engine,
            reset=bool(settings.get("TESTING")),
            auto_create=bool(settings.get("AUTO_CREATE_DB", True)),
        )
        request.app.state.settings = settings
        request.app.state.engine = engine
    return request.app.state.settings


def _get_engine(request: Request):
    _get_settings(request)
    return request.app.state.engine


def _allowed_file(filename: str, settings: dict[str, Any]) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in settings["ALLOWED_EXTENSIONS"]
    )
