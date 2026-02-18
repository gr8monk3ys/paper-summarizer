"""Job and batch management endpoints."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlmodel import select

from paper_summarizer.core.summarizer import PaperSummarizer, ModelType, ModelProvider
from paper_summarizer.web.auth import get_current_user
from paper_summarizer.web.db import get_session
from paper_summarizer.web.deps import _get_settings, _get_engine, _allowed_file
from paper_summarizer.web.models import Job, JobStatus, Summary, User
from paper_summarizer.web.job_helpers import complete_job, resolve_summary_options
from paper_summarizer.web.validation import validate_upload, validate_url
from paper_summarizer.web.schemas import (
    BatchSummaryItem,
    BatchSummaryResponse,
    JobCreateResponse,
    JobStatusResponse,
    JobSummaryRequest,
    ModelInfo,
)

logger = logging.getLogger(__name__)

_MAX_BATCH_FILES = 20

router = APIRouter()

def _run_summary_job(
    job_id: str,
    settings: dict[str, Any],
    engine,
    payload: JobSummaryRequest,
    user_id: str,
) -> None:
    with get_session(engine) as session:
        job = session.get(Job, job_id)
        if not job:
            return
        job.status = JobStatus.RUNNING
        session.add(job)
        session.commit()

    try:
        num_sentences, model_type, provider, keep_citations = resolve_summary_options(payload, settings)

        summarizer = PaperSummarizer(
            model_type=ModelType(model_type),
            provider=ModelProvider(provider),
        )

        if payload.source_type == "url":
            if not payload.url:
                raise ValueError("URL is required")
            validate_url(payload.url)
            summary = summarizer.summarize_from_url(payload.url, num_sentences)
            title: str | None = payload.url
        elif payload.source_type == "text":
            if not payload.text:
                raise ValueError("Text is required")
            summary = summarizer.summarize(payload.text, num_sentences, keep_citations)
            title = payload.text.strip().splitlines()[0][:80] if payload.text.strip() else None
        else:
            raise ValueError("Unsupported source type for background jobs")

        if summary is None:
            raise ValueError("Failed to generate summary")

        summary_record = Summary(
            user_id=user_id,
            title=title,
            source_type=payload.source_type,
            source_value=payload.url if payload.source_type == "url" else None,
            summary=summary,
            model_type=model_type,
            provider=provider,
            num_sentences=num_sentences,
        )
        with get_session(engine) as session:
            session.add(summary_record)
            session.commit()
            session.refresh(summary_record)

        result_payload = {
            "summary_id": summary_record.id,
            "summary": summary_record.summary,
            "created_at": summary_record.created_at.isoformat(),
        }
        with get_session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                complete_job(session, job, result_json=json.dumps(result_payload))
    except (ValueError, OSError, RuntimeError, TypeError) as exc:
        with get_session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                complete_job(session, job, error=str(exc))


@router.post("/api/jobs/summarize", response_model=JobCreateResponse, tags=["jobs"])
async def create_summary_job(
    payload: JobSummaryRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> JobCreateResponse:
    if payload.source_type not in {"url", "text"}:
        raise HTTPException(status_code=400, detail="Unsupported source type for background jobs")

    settings = _get_settings(request)
    engine = _get_engine(request)

    job = Job(
        user_id=current_user.id,
        status=JobStatus.QUEUED,
        payload_json=json.dumps(payload.model_dump()),
    )
    with get_session(engine) as session:
        session.add(job)
        session.commit()
        session.refresh(job)

    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        try:
            await redis.enqueue_job("run_summary_job", job.id)
        except Exception:
            logger.exception("Failed to enqueue job %s to Redis, falling back to background task", job.id)
            background_tasks.add_task(
                _run_summary_job,
                job.id,
                settings,
                engine,
                payload,
                current_user.id,
            )
    else:
        background_tasks.add_task(
            _run_summary_job,
            job.id,
            settings,
            engine,
            payload,
            current_user.id,
        )
    return JobCreateResponse(job_id=job.id, status=job.status)


@router.get("/api/jobs/{job_id}", response_model=JobStatusResponse, tags=["jobs"])
def get_job_status(
    job_id: str, request: Request, current_user: User = Depends(get_current_user)
) -> JobStatusResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        job = session.get(Job, job_id)
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Job not found")
        result = None
        if job.result_json:
            try:
                result = json.loads(job.result_json)
            except json.JSONDecodeError:
                logger.error("Corrupted result_json for job %s", job_id)
                raise HTTPException(status_code=500, detail="Corrupted job result data")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        result=result,
        error=job.error,
    )


@router.post("/batch", response_model=BatchSummaryResponse, tags=["summaries"])
async def process_batch(
    request: Request,
    files: list[UploadFile] | None = File(None, alias="files[]"),
    num_sentences: int | None = Form(None),
    model_type: str | None = Form(None),
    provider: str | None = Form(None),
    keep_citations: str = Form("false"),
    current_user: User = Depends(get_current_user),
) -> BatchSummaryResponse:
    """Handle batch processing requests."""
    settings = _get_settings(request)
    num_sentences = num_sentences or settings["DEFAULT_NUM_SENTENCES"]
    model_type = model_type or settings["DEFAULT_MODEL"]
    provider = provider or settings["DEFAULT_PROVIDER"]
    keep_citations_flag = keep_citations.lower() == "true"
    if provider == ModelProvider.LOCAL.value and not settings.get("LOCAL_MODELS_ENABLED", True):
        raise HTTPException(status_code=400, detail="Local models are disabled")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > _MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files: maximum is {_MAX_BATCH_FILES}, got {len(files)}",
        )

    try:
        summarizer = PaperSummarizer(
            model_type=ModelType(model_type),
            provider=ModelProvider(provider),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    summaries: list[BatchSummaryItem] = []
    engine = _get_engine(request)
    for upload in files:
        if not upload.filename:
            continue
        if not _allowed_file(upload.filename, settings):
            continue

        filename = Path(upload.filename).name
        filepath = settings["UPLOAD_FOLDER"] / filename
        contents = await upload.read()
        validate_upload(contents, filename, settings)
        filepath.write_bytes(contents)
        try:
            summary = summarizer.summarize_from_file(str(filepath), num_sentences, keep_citations_flag)
            if summary:
                summary_record = Summary(
                    user_id=current_user.id,
                    title=Path(filename).stem,
                    source_type="file",
                    source_value=filename,
                    summary=summary,
                    model_type=model_type,
                    provider=provider,
                    num_sentences=num_sentences,
                )
                with get_session(engine) as session:
                    session.add(summary_record)
                    session.commit()
                    session.refresh(summary_record)
                summaries.append(
                    BatchSummaryItem(
                        filename=filename,
                        summary=summary_record.summary,
                        summary_id=summary_record.id,
                        created_at=summary_record.created_at,
                    )
                )
        except ValueError:
            continue
        finally:
            if filepath.exists():
                filepath.unlink()

    if not summaries:
        raise HTTPException(status_code=400, detail="No valid files processed")

    return BatchSummaryResponse(
        summaries=summaries,
        model_info=ModelInfo(type=model_type, provider=provider),
    )
