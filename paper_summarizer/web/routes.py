"""FastAPI routes for the Paper Summarizer application."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from paper_summarizer.core.summarizer import PaperSummarizer, ModelType, ModelProvider
from paper_summarizer.web.config import load_settings
from paper_summarizer.web.db import create_db_engine, get_session, init_db
from paper_summarizer.web.auth import get_current_user
from paper_summarizer.web.models import Job, Summary, SummaryEvidence, User
from paper_summarizer.web.validation import validate_upload, validate_url
from paper_summarizer.web.schemas import (
    BatchSummaryItem,
    BatchSummaryResponse,
    EvidenceCreate,
    EvidenceUpdate,
    EvidenceItem,
    EvidenceListResponse,
    ModelInfo,
    SummaryDetailResponse,
    SummaryListResponse,
    SummaryResponse,
    SynthesisRequest,
    SynthesisResponse,
    JobCreateResponse,
    JobStatusResponse,
    JobSummaryRequest,
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter()


def _allowed_file(filename: str, settings: dict[str, Any]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in settings["ALLOWED_EXTENSIONS"]


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




def _render(request: Request, template: str, active_page: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        template,
        {"active_page": active_page},
    )


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
        job.status = "running"
        session.add(job)
        session.commit()

    try:
        num_sentences = payload.num_sentences or settings["DEFAULT_NUM_SENTENCES"]
        model_type = payload.model_type or settings["DEFAULT_MODEL"]
        provider = payload.provider or settings["DEFAULT_PROVIDER"]
        keep_citations = bool(payload.keep_citations)
        if provider == ModelProvider.LOCAL.value and not settings.get("LOCAL_MODELS_ENABLED", True):
            raise ValueError("Local models are disabled")

        if num_sentences < settings["MIN_SENTENCES"] or num_sentences > settings["MAX_SENTENCES"]:
            raise ValueError(
                f'Number of sentences must be between {settings["MIN_SENTENCES"]} and {settings["MAX_SENTENCES"]}'
            )

        summarizer = PaperSummarizer(
            model_type=ModelType(model_type),
            provider=ModelProvider(provider),
        )

        if payload.source_type == "url":
            if not payload.url:
                raise ValueError("URL is required")
            validate_url(payload.url)
            summary = summarizer.summarize_from_url(payload.url, num_sentences)
            title = payload.url
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
                job.status = "complete"
                job.result_json = json.dumps(result_payload)
                job.completed_at = summary_record.created_at
                session.add(job)
                session.commit()
    except Exception as exc:  # pragma: no cover - defensive guard for background tasks
        with get_session(engine) as session:
            job = session.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                session.add(job)
                session.commit()


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
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@router.get("/models", response_class=JSONResponse, tags=["meta"])
def get_models() -> JSONResponse:
    """Get available models."""
    settings = load_settings()
    summarizer = PaperSummarizer(
        provider=ModelProvider.TOGETHER_AI if not settings.get("LOCAL_MODELS_ENABLED", True) else ModelProvider.LOCAL
    )
    models = summarizer.get_available_models()
    if isinstance(models, dict):
        if not settings.get("LOCAL_MODELS_ENABLED", True):
            models.pop("local", None)
        return JSONResponse(models)

    grouped = {}
    for model in models:
        if model["provider"] == ModelProvider.LOCAL.value and not settings.get("LOCAL_MODELS_ENABLED", True):
            continue
        grouped.setdefault(model["provider"], []).append(
            {
                "id": model["name"],
                "name": model["name"].replace("-", " ").title(),
                "description": model["description"],
            }
        )
    return JSONResponse(grouped)


@router.post("/summarize", response_model=SummaryResponse, tags=["summaries"])
async def summarize(
    request: Request,
    source_type: str = Form("url"),
    num_sentences: int | None = Form(None),
    model_type: str | None = Form(None),
    provider: str | None = Form(None),
    keep_citations: str = Form("false"),
    url: str | None = Form(None),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
) -> SummaryResponse:
    """Handle summarization requests."""
    settings = _get_settings(request)
    num_sentences = num_sentences or settings["DEFAULT_NUM_SENTENCES"]
    model_type = model_type or settings["DEFAULT_MODEL"]
    provider = provider or settings["DEFAULT_PROVIDER"]
    keep_citations = keep_citations.lower() == "true"
    if provider == ModelProvider.LOCAL.value and not settings.get("LOCAL_MODELS_ENABLED", True):
        raise HTTPException(status_code=400, detail="Local models are disabled")

    if num_sentences < settings["MIN_SENTENCES"] or num_sentences > settings["MAX_SENTENCES"]:
        raise HTTPException(
            status_code=400,
            detail=f'Number of sentences must be between {settings["MIN_SENTENCES"]} and {settings["MAX_SENTENCES"]}',
        )

    try:
        summarizer = PaperSummarizer(
            model_type=ModelType(model_type),
            provider=ModelProvider(provider),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if source_type == "url":
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        validate_url(url)
        try:
            summary = summarizer.summarize_from_url(url, num_sentences)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif source_type == "text":
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        try:
            summary = summarizer.summarize(text, num_sentences, keep_citations)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif source_type == "file":
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        if not _allowed_file(file.filename, settings):
            raise HTTPException(status_code=400, detail="File type not allowed")

        filename = Path(file.filename).name
        filepath = settings["UPLOAD_FOLDER"] / filename
        contents = await file.read()
        validate_upload(contents, filename, settings)
        filepath.write_bytes(contents)
        try:
            summary = summarizer.summarize_from_file(str(filepath), num_sentences, keep_citations)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            if filepath.exists():
                filepath.unlink()
    else:
        raise HTTPException(status_code=400, detail="Invalid source type")

    if summary is None:
        raise HTTPException(status_code=500, detail="Failed to generate summary")

    title = None
    if source_type == "url" and url:
        title = url
    elif source_type == "file" and file and file.filename:
        title = Path(file.filename).stem
    elif source_type == "text" and text:
        title = text.strip().splitlines()[0][:80] if text.strip() else None

    summary_record = Summary(
        user_id=current_user.id,
        title=title,
        source_type=source_type,
        source_value=url if source_type == "url" else (file.filename if file else None),
        summary=summary,
        model_type=model_type,
        provider=provider,
        num_sentences=num_sentences,
    )

    engine = _get_engine(request)
    with get_session(engine) as session:
        session.add(summary_record)
        session.commit()
        session.refresh(summary_record)

    return SummaryResponse(
        summary=summary_record.summary,
        model_info=ModelInfo(type=model_type, provider=provider),
        summary_id=summary_record.id,
        created_at=summary_record.created_at,
    )


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
        status="queued",
        payload_json=json.dumps(payload.model_dump()),
    )
    with get_session(engine) as session:
        session.add(job)
        session.commit()
        session.refresh(job)

    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        await redis.enqueue_job("run_summary_job", job.id)
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
        result = json.loads(job.result_json) if job.result_json else None

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
    keep_citations = keep_citations.lower() == "true"
    if provider == ModelProvider.LOCAL.value and not settings.get("LOCAL_MODELS_ENABLED", True):
        raise HTTPException(status_code=400, detail="Local models are disabled")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

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
            summary = summarizer.summarize_from_file(str(filepath), num_sentences, keep_citations)
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


@router.get("/api/settings", response_class=JSONResponse, tags=["meta"])
def get_settings(request: Request, current_user: User = Depends(get_current_user)) -> JSONResponse:
    settings = _get_settings(request)
    return JSONResponse(
        {
            "defaultModel": settings["DEFAULT_MODEL"],
            "summaryLength": settings["DEFAULT_NUM_SENTENCES"],
            "citationHandling": "remove",
            "autoSave": True,
        }
    )


@router.post("/api/settings", response_class=JSONResponse, tags=["meta"])
async def save_settings(current_user: User = Depends(get_current_user)) -> JSONResponse:
    return JSONResponse({"status": "success"})


@router.get("/api/analytics", response_class=JSONResponse, tags=["meta"])
def get_analytics(request: Request, current_user: User = Depends(get_current_user)) -> JSONResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        rows = session.exec(select(Summary).where(Summary.user_id == current_user.id)).all()

    total = len(rows)
    model_usage = {}
    length_distribution = {}
    daily_activity = {}
    total_length = 0

    for row in rows:
        model_usage[row.model_type] = model_usage.get(row.model_type, 0) + 1
        length_distribution[str(row.num_sentences)] = length_distribution.get(str(row.num_sentences), 0) + 1
        day_key = row.created_at.date().isoformat()
        daily_activity[day_key] = daily_activity.get(day_key, 0) + 1
        total_length += row.num_sentences

    average_length = (total_length / total) if total else 0

    analytics = {
        "totalSummaries": total,
        "modelUsage": model_usage,
        "averageLength": average_length,
        "uniqueModels": len(model_usage),
        "lengthDistribution": length_distribution,
        "dailyActivity": daily_activity,
    }
    return JSONResponse(analytics)


@router.get("/api/summaries", response_model=SummaryListResponse, tags=["summaries"])
def list_summaries(request: Request, current_user: User = Depends(get_current_user)) -> SummaryListResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        rows = session.exec(
            select(Summary)
            .where(Summary.user_id == current_user.id)
            .order_by(Summary.created_at.desc())
        ).all()

    return SummaryListResponse(
        summaries=[
            {
                "id": row.id,
                "title": row.title,
                "summary": row.summary,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    )


@router.get("/api/summaries/{summary_id}", response_model=SummaryDetailResponse, tags=["summaries"])
def get_summary(summary_id: str, request: Request, current_user: User = Depends(get_current_user)) -> SummaryDetailResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        row = session.get(Summary, summary_id)
        if not row or row.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Summary not found")
        return SummaryDetailResponse(
            id=row.id,
            title=row.title,
            summary=row.summary,
            source_type=row.source_type,
            source_value=row.source_value,
            model_type=row.model_type,
            provider=row.provider,
            num_sentences=row.num_sentences,
            created_at=row.created_at,
        )


@router.get(
    "/api/summaries/{summary_id}/evidence",
    response_model=EvidenceListResponse,
    tags=["evidence"],
)
def list_evidence(summary_id: str, request: Request, current_user: User = Depends(get_current_user)) -> EvidenceListResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        summary = session.get(Summary, summary_id)
        if not summary or summary.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Summary not found")
        items = session.exec(
            select(SummaryEvidence).where(SummaryEvidence.summary_id == summary_id)
        ).all()

    return EvidenceListResponse(
        summary_id=summary_id,
        items=[
            EvidenceItem(
                id=item.id,
                claim=item.claim,
                evidence=item.evidence,
                location=item.location,
                created_at=item.created_at,
            )
            for item in items
        ],
    )


@router.post(
    "/api/summaries/{summary_id}/evidence",
    response_model=EvidenceListResponse,
    tags=["evidence"],
)
def create_evidence(
    summary_id: str, payload: EvidenceCreate, request: Request, current_user: User = Depends(get_current_user)
) -> EvidenceListResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        summary = session.get(Summary, summary_id)
        if not summary or summary.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Summary not found")
        record = SummaryEvidence(
            summary_id=summary_id,
            claim=payload.claim,
            evidence=payload.evidence,
            location=payload.location,
        )
        session.add(record)
        session.commit()
    return list_evidence(summary_id, request)


@router.put(
    "/api/summaries/{summary_id}/evidence/{evidence_id}",
    response_model=EvidenceListResponse,
    tags=["evidence"],
)
def update_evidence(
    summary_id: str, evidence_id: str, payload: EvidenceUpdate, request: Request, current_user: User = Depends(get_current_user)
) -> EvidenceListResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        summary = session.get(Summary, summary_id)
        if not summary or summary.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Summary not found")
        record = session.get(SummaryEvidence, evidence_id)
        if not record or record.summary_id != summary_id:
            raise HTTPException(status_code=404, detail="Evidence not found")
        if payload.claim is not None:
            record.claim = payload.claim
        if payload.evidence is not None:
            record.evidence = payload.evidence
        if payload.location is not None:
            record.location = payload.location
        session.add(record)
        session.commit()
    return list_evidence(summary_id, request)


@router.delete(
    "/api/summaries/{summary_id}/evidence/{evidence_id}",
    response_model=EvidenceListResponse,
    tags=["evidence"],
)
def delete_evidence(summary_id: str, evidence_id: str, request: Request, current_user: User = Depends(get_current_user)) -> EvidenceListResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        summary = session.get(Summary, summary_id)
        if not summary or summary.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Summary not found")
        record = session.get(SummaryEvidence, evidence_id)
        if not record or record.summary_id != summary_id:
            raise HTTPException(status_code=404, detail="Evidence not found")
        session.delete(record)
        session.commit()
    return list_evidence(summary_id, request)


@router.post(
    "/api/summaries/{summary_id}/evidence/generate",
    response_model=EvidenceListResponse,
    tags=["evidence"],
)
def generate_evidence(summary_id: str, request: Request, current_user: User = Depends(get_current_user)) -> EvidenceListResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        summary_row = session.get(Summary, summary_id)
        if not summary_row or summary_row.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Summary not found")

        sentences = [s.strip() for s in summary_row.summary.split(".") if s.strip()]
        samples = sentences[:2] if sentences else []

        for sentence in samples:
            session.add(
                SummaryEvidence(
                    summary_id=summary_id,
                    claim=sentence,
                    evidence="Evidence placeholder: link this claim to a quote.",
                    location=None,
                )
            )
        session.commit()

    return list_evidence(summary_id, request)


@router.delete("/api/summaries/{summary_id}", response_class=JSONResponse, tags=["summaries"])
def delete_summary(summary_id: str, request: Request, current_user: User = Depends(get_current_user)) -> JSONResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        row = session.get(Summary, summary_id)
        if not row or row.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Summary not found")
        session.delete(row)
        session.commit()
    return JSONResponse({"status": "deleted"})


@router.get("/export/{summary_id}", response_class=PlainTextResponse, tags=["summaries"])
def export_summary(summary_id: str, request: Request, format: str = "txt", current_user: User = Depends(get_current_user)) -> Response:
    engine = _get_engine(request)
    with get_session(engine) as session:
        row = session.get(Summary, summary_id)
        if not row or row.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Summary not found")
        evidence = session.exec(
            select(SummaryEvidence).where(SummaryEvidence.summary_id == summary_id)
        ).all()

    if format == "md":
        content = f"# Summary\n\n{row.summary}\n\n## Evidence\n"
        if evidence:
            content += "\n".join(
                [f"- **{item.claim}**: {item.evidence}" for item in evidence]
            )
        else:
            content += "No evidence items."
        filename = f"summary_{summary_id}.md"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return PlainTextResponse(content, headers=headers)

    if format == "pdf":
        from io import BytesIO
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        margin = 72
        y = height - margin

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(margin, y, "Summary")
        y -= 28
        pdf.setFont("Helvetica", 11)

        for line in row.summary.splitlines():
            if y < margin:
                pdf.showPage()
                y = height - margin
                pdf.setFont("Helvetica", 11)
            pdf.drawString(margin, y, line[:110])
            y -= 16

        y -= 10
        pdf.setStrokeColor(colors.HexColor("#f4b4a6"))
        pdf.setLineWidth(1)
        pdf.line(margin, y, width - margin, y)
        y -= 16
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(margin, y, "Evidence")
        y -= 20
        pdf.setFont("Helvetica", 10)
        if evidence:
            for item in evidence:
                wrapped = f"{item.claim}: {item.evidence}"
                for line in wrapped.splitlines():
                    if y < margin:
                        pdf.showPage()
                        y = height - margin
                        pdf.setFont("Helvetica", 10)
                    pdf.drawString(margin, y, line[:110])
                    y -= 14
        else:
            pdf.drawString(margin, y, "No evidence items.")

        pdf.save()
        buffer.seek(0)
        headers = {"Content-Disposition": f'attachment; filename="summary_{summary_id}.pdf"'}
        return Response(buffer.read(), media_type="application/pdf", headers=headers)

    filename = f"summary_{summary_id}.txt"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return PlainTextResponse(row.summary, headers=headers)


@router.get("/api/summaries/export", response_class=JSONResponse, tags=["summaries"])
def export_summaries(request: Request, current_user: User = Depends(get_current_user)) -> JSONResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        rows = session.exec(
            select(Summary)
            .where(Summary.user_id == current_user.id)
            .order_by(Summary.created_at.desc())
        ).all()
    return JSONResponse(
        [
            {
                "id": row.id,
                "title": row.title,
                "summary": row.summary,
                "source_type": row.source_type,
                "source_value": row.source_value,
                "model_type": row.model_type,
                "provider": row.provider,
                "num_sentences": row.num_sentences,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    )


@router.post("/api/summaries/import", response_class=JSONResponse, tags=["summaries"])
def import_summaries(payload: list[dict], request: Request, current_user: User = Depends(get_current_user)) -> JSONResponse:
    engine = _get_engine(request)
    imported = 0
    with get_session(engine) as session:
        for item in payload:
            summary = item.get("summary")
            if not summary:
                continue
            record = Summary(
                user_id=current_user.id,
                title=item.get("title"),
                source_type=item.get("source_type", "import"),
                source_value=item.get("source_value"),
                summary=summary,
                model_type=item.get("model_type", "unknown"),
                provider=item.get("provider", "import"),
                num_sentences=int(item.get("num_sentences", 5)),
            )
            session.add(record)
            imported += 1
        session.commit()
    return JSONResponse({"status": "imported", "count": imported})


@router.post("/api/summaries/synthesize", response_model=SynthesisResponse, tags=["summaries"])
def synthesize_summaries(payload: SynthesisRequest, request: Request, current_user: User = Depends(get_current_user)) -> SynthesisResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        rows = [session.get(Summary, summary_id) for summary_id in payload.summary_ids]
        rows = [row for row in rows if row and row.user_id == current_user.id]

    if not rows:
        raise HTTPException(status_code=400, detail="No valid summaries provided")

    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "have",
        "has", "had", "into", "over", "under", "between", "using", "use", "used", "study",
        "paper", "results", "method", "methods", "model", "models", "data", "dataset",
        "we", "our", "their", "they", "these", "those", "shows", "show", "based", "analysis",
    }

    def extract_keywords(text: str) -> list[str]:
        tokens = [
            "".join(ch for ch in word.lower() if ch.isalnum())
            for word in text.split()
        ]
        tokens = [token for token in tokens if token and token not in stopwords and len(token) > 3]
        counts = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        return [token for token, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:5]]

    clusters: dict[str, list[Summary]] = {}
    for row in rows:
        keywords = extract_keywords(row.summary)
        key = keywords[0] if keywords else "misc"
        clusters.setdefault(key, []).append(row)

    consensus_sections = []
    citations = []
    for key, items in clusters.items():
        header = f"Theme: {key} ({len(items)} summaries)"
        lines = []
        for item in items:
            first_sentence = item.summary.split(".")[0].strip()
            if first_sentence:
                lines.append(f"- {first_sentence} [{item.id[:8]}]")
                citations.append(
                    {
                        "summary_id": item.id,
                        "title": item.title,
                        "excerpt": first_sentence,
                    }
                )
        consensus_sections.append(header + "\n" + "\n".join(lines))

    consensus = "Consensus Snapshot:\n\n" + "\n\n".join(consensus_sections)

    disagreements = []
    if len(clusters) > 1:
        disagreements.append(
            "Themes diverge across clusters: " + ", ".join(sorted(clusters.keys()))
        )

    sources = [row.id for row in rows]

    return SynthesisResponse(
        consensus=consensus,
        disagreements=disagreements,
        sources=sources,
        citations=citations,
    )


@router.get("/api/summaries/synthesize/export", response_class=PlainTextResponse, tags=["summaries"])
def export_synthesis(consensus: str, format: str = "txt", current_user: User = Depends(get_current_user)) -> PlainTextResponse:
    if format == "md":
        content = f"# Synthesis Output\n\n{consensus}"
        filename = "synthesis.md"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return PlainTextResponse(content, headers=headers)
    if format == "pdf":
        from io import BytesIO
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        margin = 72
        y = height - margin

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(margin, y, "Synthesis Output")
        y -= 28

        pdf.setFont("Helvetica", 11)
        for line in consensus.splitlines():
            if y < margin:
                pdf.showPage()
                y = height - margin
                pdf.setFont("Helvetica", 11)
            pdf.drawString(margin, y, line[:110])
            y -= 16

        pdf.save()
        buffer.seek(0)
        headers = {"Content-Disposition": 'attachment; filename="synthesis.pdf"'}
        return Response(buffer.read(), media_type="application/pdf", headers=headers)

    content = consensus
    filename = "synthesis.txt"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return PlainTextResponse(content, headers=headers)
