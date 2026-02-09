"""Route package combining all API routers."""

from __future__ import annotations

from fastapi import APIRouter

from paper_summarizer.web.deps import STATIC_DIR
from .html import router as html_router
from .summaries import router as summaries_router
from .jobs import router as jobs_router
from .evidence import router as evidence_router
from .export import router as export_router
from .synthesis import router as synthesis_router

router = APIRouter()
router.include_router(html_router)
router.include_router(summaries_router)
router.include_router(jobs_router)
router.include_router(evidence_router)
router.include_router(export_router)
router.include_router(synthesis_router)

__all__ = ["router", "STATIC_DIR"]
