"""Summary CRUD API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse
from sqlmodel import delete, func, select

from paper_summarizer.core.summarizer import PaperSummarizer, ModelType, ModelProvider
from paper_summarizer.web.auth import get_current_user
from paper_summarizer.web.db import get_session
from paper_summarizer.web.deps import _get_settings, _get_engine, _allowed_file
from paper_summarizer.web.models import (
    Job,
    Summary,
    SummaryEvidence,
    User,
    UserSettings,
)
from paper_summarizer.web.validation import validate_upload, validate_url
from paper_summarizer.web.schemas import (
    ExportSummariesResponse,
    ModelInfo,
    StorageUsageResponse,
    SummaryDetailResponse,
    SummaryListResponse,
    SummaryResponse,
    UserSettingsResponse,
    UserSettingsUpdateRequest,
)

router = APIRouter()


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
    keep_citations_flag = keep_citations.lower() == "true"
    if provider == ModelProvider.LOCAL.value and not settings.get(
        "LOCAL_MODELS_ENABLED", True
    ):
        raise HTTPException(status_code=400, detail="Local models are disabled")

    if (
        num_sentences < settings["MIN_SENTENCES"]
        or num_sentences > settings["MAX_SENTENCES"]
    ):
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
            summary = summarizer.summarize(text, num_sentences, keep_citations_flag)
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
            summary = summarizer.summarize_from_file(
                str(filepath), num_sentences, keep_citations_flag
            )
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


@router.get("/api/settings", response_model=UserSettingsResponse, tags=["meta"])
def get_settings(
    request: Request, current_user: User = Depends(get_current_user)
) -> UserSettingsResponse:
    settings = _get_settings(request)
    engine = _get_engine(request)

    with get_session(engine) as session:
        row = session.get(UserSettings, current_user.id)

    if row:
        return UserSettingsResponse(
            defaultModel=row.default_model,
            summaryLength=row.summary_length,
            citationHandling=row.citation_handling,
            autoSave=row.auto_save,
        )

    return UserSettingsResponse(
        defaultModel=settings["DEFAULT_MODEL"],
        summaryLength=settings["DEFAULT_NUM_SENTENCES"],
        citationHandling="remove",
        autoSave=True,
    )


@router.post("/api/settings", response_model=UserSettingsResponse, tags=["meta"])
def save_settings(
    payload: UserSettingsUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UserSettingsResponse:
    settings = _get_settings(request)
    if (
        payload.summaryLength < settings["MIN_SENTENCES"]
        or payload.summaryLength > settings["MAX_SENTENCES"]
    ):
        raise HTTPException(
            status_code=400,
            detail=f'Summary length must be between {settings["MIN_SENTENCES"]} and {settings["MAX_SENTENCES"]}',
        )

    if payload.citationHandling not in {"keep", "remove"}:
        raise HTTPException(
            status_code=400, detail="citationHandling must be 'keep' or 'remove'"
        )

    engine = _get_engine(request)
    with get_session(engine) as session:
        row = session.get(UserSettings, current_user.id)
        now = datetime.now(timezone.utc)
        if row is None:
            row = UserSettings(
                user_id=current_user.id,
                default_model=payload.defaultModel,
                summary_length=payload.summaryLength,
                citation_handling=payload.citationHandling,
                auto_save=payload.autoSave,
                created_at=now,
                updated_at=now,
            )
        else:
            row.default_model = payload.defaultModel
            row.summary_length = payload.summaryLength
            row.citation_handling = payload.citationHandling
            row.auto_save = payload.autoSave
            row.updated_at = now

        session.add(row)
        session.commit()

    return UserSettingsResponse(
        defaultModel=payload.defaultModel,
        summaryLength=payload.summaryLength,
        citationHandling=payload.citationHandling,
        autoSave=payload.autoSave,
    )


@router.get("/api/storage", response_model=StorageUsageResponse, tags=["meta"])
def get_storage_usage(
    request: Request, current_user: User = Depends(get_current_user)
) -> StorageUsageResponse:
    settings = _get_settings(request)
    max_bytes = int(settings["STORAGE_LIMIT_BYTES"])
    engine = _get_engine(request)
    with get_session(engine) as session:
        rows = session.exec(
            select(Summary.summary).where(Summary.user_id == current_user.id)
        ).all()

    used_bytes = sum(len((value or "").encode("utf-8")) for value in rows)
    summary_count = len(rows)
    used_percent = int((used_bytes / max_bytes) * 100) if max_bytes > 0 else 0
    return StorageUsageResponse(
        usedBytes=used_bytes,
        maxBytes=max_bytes,
        usedPercent=min(100, used_percent),
        summaryCount=summary_count,
    )


@router.post("/api/clear-data", response_class=JSONResponse, tags=["summaries"])
def clear_data(
    request: Request, current_user: User = Depends(get_current_user)
) -> JSONResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        summary_ids = session.exec(
            select(Summary.id).where(Summary.user_id == current_user.id)
        ).all()
        for summary_id in summary_ids:
            session.exec(
                delete(SummaryEvidence).where(SummaryEvidence.summary_id == summary_id)
            )
        session.exec(delete(Summary).where(Summary.user_id == current_user.id))
        session.exec(delete(Job).where(Job.user_id == current_user.id))
        session.commit()

    return JSONResponse({"status": "cleared"})


@router.get("/api/analytics", response_class=JSONResponse, tags=["meta"])
def get_analytics(
    request: Request, current_user: User = Depends(get_current_user)
) -> JSONResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        # Total count
        total = session.exec(
            select(func.count())
            .select_from(Summary)
            .where(Summary.user_id == current_user.id)
        ).one()

        # Model usage: GROUP BY model_type
        model_rows = session.exec(
            select(Summary.model_type, func.count())
            .where(Summary.user_id == current_user.id)
            .group_by(Summary.model_type)
        ).all()
        model_usage = {row[0]: row[1] for row in model_rows}

        # Length distribution: GROUP BY num_sentences
        length_rows = session.exec(
            select(Summary.num_sentences, func.count())
            .where(Summary.user_id == current_user.id)
            .group_by(Summary.num_sentences)
        ).all()
        length_distribution = {str(row[0]): row[1] for row in length_rows}

        # Average length
        avg_length = session.exec(
            select(func.avg(Summary.num_sentences)).where(
                Summary.user_id == current_user.id
            )
        ).one()
        average_length = float(avg_length) if avg_length else 0

        # Daily activity: GROUP BY date(created_at)
        daily_rows = session.exec(
            select(func.date(Summary.created_at), func.count())
            .where(Summary.user_id == current_user.id)
            .group_by(func.date(Summary.created_at))
        ).all()
        daily_activity = {str(row[0]): row[1] for row in daily_rows}

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
def list_summaries(
    request: Request,
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SummaryListResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        total = session.exec(
            select(func.count())
            .select_from(Summary)
            .where(Summary.user_id == current_user.id)
        ).one()
        rows = session.exec(
            select(Summary)
            .where(Summary.user_id == current_user.id)
            .order_by(Summary.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

    return SummaryListResponse(
        items=[
            {
                "id": row.id,
                "title": row.title,
                "summary": row.summary,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/summaries/export", response_model=ExportSummariesResponse, tags=["summaries"]
)
def export_summaries(
    request: Request,
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> ExportSummariesResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        total = session.exec(
            select(func.count())
            .select_from(Summary)
            .where(Summary.user_id == current_user.id)
        ).one()
        rows = session.exec(
            select(Summary)
            .where(Summary.user_id == current_user.id)
            .order_by(Summary.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

    return ExportSummariesResponse(
        items=[
            {
                "id": row.id,
                "title": row.title,
                "summary": row.summary,
                "source_type": row.source_type,
                "source_value": row.source_value,
                "model_type": row.model_type,
                "provider": row.provider,
                "num_sentences": row.num_sentences,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/summaries/{summary_id}",
    response_model=SummaryDetailResponse,
    tags=["summaries"],
)
def get_summary(
    summary_id: str, request: Request, current_user: User = Depends(get_current_user)
) -> SummaryDetailResponse:
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


@router.delete(
    "/api/summaries/{summary_id}", response_class=JSONResponse, tags=["summaries"]
)
def delete_summary(
    summary_id: str, request: Request, current_user: User = Depends(get_current_user)
) -> JSONResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        row = session.get(Summary, summary_id)
        if not row or row.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Summary not found")
        session.delete(row)
        session.commit()
    return JSONResponse({"status": "deleted"})


@router.post("/api/summaries/import", response_class=JSONResponse, tags=["summaries"])
def import_summaries(
    payload: list[dict],
    request: Request,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
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
