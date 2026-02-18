"""Arq worker for background summarization jobs."""

from __future__ import annotations

import json
import logging

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from paper_summarizer.core.summarizer import ModelProvider, ModelType, PaperSummarizer
from paper_summarizer.web.config import load_settings
from paper_summarizer.web.db import create_db_engine, get_session
from paper_summarizer.web.models import Job, JobStatus, Summary
from paper_summarizer.web.job_helpers import complete_job, resolve_summary_options
from paper_summarizer.web.validation import validate_url

logger = logging.getLogger(__name__)


async def run_summary_job(ctx, job_id: str) -> None:
    engine = ctx["engine"]
    settings = ctx["settings"]

    with get_session(engine) as session:
        job = session.get(Job, job_id)
        if not job or job.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
            return
        job.status = JobStatus.RUNNING
        session.add(job)
        session.commit()
        try:
            payload = json.loads(job.payload_json)
        except json.JSONDecodeError:
            logger.error("Corrupted payload_json for job %s", job_id)
            complete_job(session, job, error="Corrupted job payload data")
            return

    try:
        source_type = payload.get("source_type")
        num_sentences, model_type, provider, keep_citations = resolve_summary_options(payload, settings)

        summarizer = PaperSummarizer(
            model_type=ModelType(model_type),
            provider=ModelProvider(provider),
        )

        if source_type == "url":
            url = payload.get("url")
            if not url:
                raise ValueError("URL is required")
            validate_url(url)
            summary = summarizer.summarize_from_url(url, num_sentences)
            title = url
            source_value = url
        elif source_type == "text":
            text = payload.get("text")
            if not text:
                raise ValueError("Text is required")
            summary = summarizer.summarize(text, num_sentences, keep_citations)
            title = text.strip().splitlines()[0][:80] if text.strip() else None
            source_value = None
        else:
            raise ValueError("Unsupported source type for background jobs")

        if summary is None:
            raise ValueError("Failed to generate summary")

        summary_record = Summary(
            user_id=job.user_id,
            title=title,
            source_type=source_type,
            source_value=source_value,
            summary=summary,
            model_type=model_type,
            provider=provider,
            num_sentences=num_sentences,
        )

        with get_session(engine) as session:
            session.add(summary_record)
            session.commit()
            session.refresh(summary_record)

            job = session.get(Job, job_id)
            if job:
                result_payload = json.dumps(
                    {
                        "summary_id": summary_record.id,
                        "summary": summary_record.summary,
                        "created_at": summary_record.created_at.isoformat(),
                    }
                )
                complete_job(session, job, result_json=result_payload)
    except (ValueError, KeyError, TypeError) as exc:
        logger.error("Job %s failed: %s", job_id, exc)
        with get_session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                complete_job(session, job, error=str(exc))
    except HTTPException as exc:
        logger.error("Job %s failed with HTTP %s: %s", job_id, exc.status_code, exc.detail)
        with get_session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                complete_job(session, job, error=str(exc.detail))
    except (SQLAlchemyError, OSError, RuntimeError) as exc:
        logger.exception("Job %s failed unexpectedly", job_id)
        with get_session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                complete_job(session, job, error=str(exc))


async def startup(ctx) -> None:
    settings = load_settings()
    engine = create_db_engine(settings["DATABASE_URL"])
    ctx["settings"] = settings
    ctx["engine"] = engine


async def shutdown(ctx) -> None:
    ctx.clear()


class WorkerSettings:
    functions = [run_summary_job]
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs = []
