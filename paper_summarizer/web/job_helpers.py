"""Shared helpers for background summary jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from paper_summarizer.core.summarizer import ModelProvider
from paper_summarizer.web.models import Job, JobStatus

_MAX_ERROR_LENGTH = 500


def complete_job(
    session: Session,
    job: Job,
    result_json: str | None = None,
    error: str | None = None,
) -> None:
    """Set a job to its terminal state (COMPLETE or FAILED)."""
    if error is not None:
        job.status = JobStatus.FAILED
        job.error = error[:_MAX_ERROR_LENGTH]
    else:
        job.status = JobStatus.COMPLETE
        job.result_json = result_json
    job.completed_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()


def resolve_summary_options(
    payload: Any, settings: dict[str, Any]
) -> tuple[int, str, str, bool]:
    """Resolve and validate summarization options from payload and settings."""
    if isinstance(payload, Mapping):
        num_sentences = (
            payload.get("num_sentences") or settings["DEFAULT_NUM_SENTENCES"]
        )
        model_type = payload.get("model_type") or settings["DEFAULT_MODEL"]
        provider = payload.get("provider") or settings["DEFAULT_PROVIDER"]
        keep_citations = bool(payload.get("keep_citations"))
    else:
        num_sentences = payload.num_sentences or settings["DEFAULT_NUM_SENTENCES"]
        model_type = payload.model_type or settings["DEFAULT_MODEL"]
        provider = payload.provider or settings["DEFAULT_PROVIDER"]
        keep_citations = bool(payload.keep_citations)

    if provider == ModelProvider.LOCAL.value and not settings.get(
        "LOCAL_MODELS_ENABLED", True
    ):
        raise ValueError("Local models are disabled")

    if (
        num_sentences < settings["MIN_SENTENCES"]
        or num_sentences > settings["MAX_SENTENCES"]
    ):
        raise ValueError(
            f'Number of sentences must be between {settings["MIN_SENTENCES"]} and {settings["MAX_SENTENCES"]}'
        )

    return num_sentences, model_type, provider, keep_citations
