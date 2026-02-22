"""HTML page rendering routes and simple meta GET endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from paper_summarizer.core.summarizer import PaperSummarizer, ModelProvider
from paper_summarizer.web.config import load_settings
from paper_summarizer.web.deps import TEMPLATES_DIR

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter()


def _render(request: Request, template: str, active_page: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        template,
        {"active_page": active_page},
    )


@router.get("/", response_class=HTMLResponse, name="index")
def index(request: Request) -> HTMLResponse:
    """Render the main page."""
    return _render(request, "index.html", "index")


@router.get("/library", response_class=HTMLResponse, name="library")
def library(request: Request) -> HTMLResponse:
    """Render the library page."""
    return _render(request, "library.html", "library")


@router.get("/batch", response_class=HTMLResponse, name="batch")
def batch(request: Request) -> HTMLResponse:
    """Render the batch processing page."""
    return _render(request, "batch.html", "batch")


@router.get("/analytics", response_class=HTMLResponse, name="analytics")
def analytics(request: Request) -> HTMLResponse:
    """Render the analytics page."""
    return _render(request, "analytics.html", "analytics")


@router.get("/settings", response_class=HTMLResponse, name="settings")
def settings(request: Request) -> HTMLResponse:
    """Render the settings page."""
    return _render(request, "settings.html", "settings")


@router.get("/login", response_class=HTMLResponse, name="login")
def login(request: Request) -> HTMLResponse:
    return _render(request, "login.html", "login")


@router.get("/archive", response_class=HTMLResponse, name="archive")
def archive(request: Request) -> HTMLResponse:
    return _render(request, "archive.html", "archive")


@router.get("/synthesis", response_class=HTMLResponse, name="synthesis")
def synthesis(request: Request) -> HTMLResponse:
    return _render(request, "synthesis.html", "synthesis")


@router.get("/health", response_class=JSONResponse)
async def health(request: Request) -> JSONResponse:
    """Check database and Redis connectivity."""
    result: dict[str, str] = {"status": "healthy"}

    # Database check
    try:
        engine = request.app.state.engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["database"] = "ok"
    except Exception:
        result["database"] = "error"
        result["status"] = "unhealthy"

    # Redis check
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        try:
            await redis.ping()
            result["redis"] = "ok"
        except Exception:
            result["redis"] = "error"
    else:
        result["redis"] = "not_configured"

    status_code = 200 if result["database"] == "ok" else 503
    return JSONResponse(result, status_code=status_code)


@router.get("/models", response_class=JSONResponse, tags=["meta"])
def get_models() -> JSONResponse:
    """Get available models."""
    settings = load_settings()
    summarizer = PaperSummarizer(
        provider=(
            ModelProvider.TOGETHER_AI
            if not settings.get("LOCAL_MODELS_ENABLED", True)
            else ModelProvider.LOCAL
        )
    )
    models = summarizer.get_available_models()

    grouped = {}
    for model in models:
        if model["provider"] == ModelProvider.LOCAL.value and not settings.get(
            "LOCAL_MODELS_ENABLED", True
        ):
            continue
        grouped.setdefault(model["provider"], []).append(
            {
                "id": model["name"],
                "name": model["name"].replace("-", " ").title(),
                "description": model["description"],
            }
        )
    return JSONResponse(grouped)
