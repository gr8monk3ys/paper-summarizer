"""Evidence management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from paper_summarizer.web.auth import get_current_user
from paper_summarizer.web.db import get_session
from paper_summarizer.web.deps import _get_engine
from paper_summarizer.web.models import Summary, SummaryEvidence, User
from paper_summarizer.web.schemas import (
    EvidenceCreate,
    EvidenceUpdate,
    EvidenceItem,
    EvidenceListResponse,
)
from sqlmodel import select

router = APIRouter()


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
    return list_evidence(summary_id, request, current_user)


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
    return list_evidence(summary_id, request, current_user)


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
    return list_evidence(summary_id, request, current_user)


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

    return list_evidence(summary_id, request, current_user)
