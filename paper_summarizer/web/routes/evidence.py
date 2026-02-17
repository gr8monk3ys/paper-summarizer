"""Evidence management endpoints."""

from __future__ import annotations

import json
import logging
import os

import httpx
import together
from fastapi import APIRouter, Depends, HTTPException, Request

from paper_summarizer.web.auth import get_current_user
from paper_summarizer.web.db import get_session
from paper_summarizer.web.deps import _get_engine, _get_settings
from paper_summarizer.web.models import Summary, SummaryEvidence, User
from paper_summarizer.web.schemas import (
    EvidenceCreate,
    EvidenceUpdate,
    EvidenceItem,
    EvidenceListResponse,
)
from sqlmodel import select

logger = logging.getLogger(__name__)

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
    settings = _get_settings(request)

    with get_session(engine) as session:
        summary_row = session.get(Summary, summary_id)
        if not summary_row or summary_row.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Summary not found")

        summary_text = summary_row.summary
        source_text = _fetch_source_text(summary_row)

    evidence_items = _extract_evidence(summary_text, source_text, settings)

    with get_session(engine) as session:
        for item in evidence_items:
            session.add(
                SummaryEvidence(
                    summary_id=summary_id,
                    claim=item["claim"],
                    evidence=item["evidence"],
                    location=item.get("location"),
                )
            )
        session.commit()

    return list_evidence(summary_id, request, current_user)


def _fetch_source_text(summary_row: Summary) -> str | None:
    """Try to fetch the original source text for evidence linking."""
    if summary_row.source_type == "url" and summary_row.source_value:
        try:
            with httpx.Client(timeout=15) as client:
                response = client.get(summary_row.source_value, follow_redirects=True)
                response.raise_for_status()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            article = soup.find("article") or soup.find("main")
            if article:
                return article.get_text(separator="\n", strip=True)
            paragraphs = soup.find_all("p")
            if paragraphs:
                return "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            return None
    return None


def _extract_evidence(
    summary_text: str,
    source_text: str | None,
    settings: dict,
) -> list[dict]:
    """Extract evidence claims from a summary, with supporting quotes if source available."""
    api_key = os.getenv("TOGETHER_API_KEY", "")
    if api_key and not os.getenv("TESTING"):
        try:
            return _extract_evidence_llm(summary_text, source_text, api_key)
        except Exception:
            pass  # Fall through to heuristic

    return _extract_evidence_heuristic(summary_text, source_text)


def _extract_evidence_llm(
    summary_text: str,
    source_text: str | None,
    api_key: str,
) -> list[dict]:
    """Use Together AI to extract evidence mappings."""
    together.api_key = api_key

    source_section = ""
    if source_text:
        # Truncate source to avoid token limits
        truncated = source_text[:8000]
        source_section = (
            f"\n\nOriginal source text:\n{truncated}\n\n"
            "For each claim, find a direct supporting quote from the source text above."
        )
    else:
        source_section = (
            "\n\nNo source text available. For each claim, describe what "
            "evidence would be needed to verify it."
        )

    prompt = (
        "You are a research evidence analyst. Extract the key claims from "
        "the following summary and map each to supporting evidence.\n\n"
        f"Summary:\n{summary_text}\n"
        f"{source_section}\n\n"
        "Respond with a JSON array of objects, each with:\n"
        '- "claim": the specific claim from the summary\n'
        '- "evidence": a direct quote or description of supporting evidence\n'
        '- "location": where in the source this evidence appears (paragraph number, section, etc.) or null\n\n'
        "JSON array:"
    )

    response = together.Complete.create(
        prompt=prompt,
        model="deepseek-r1",
        max_tokens=2048,
        temperature=0.1,
        stop=["\n\n\n"],
    )

    raw = response["output"]["choices"][0]["text"].strip()
    # Try to parse JSON from the response
    # Handle cases where the model wraps in markdown code blocks
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    items = json.loads(raw)
    if not isinstance(items, list):
        raise ValueError("Expected JSON array")

    result = []
    for item in items[:10]:  # Cap at 10 evidence items
        if isinstance(item, dict) and "claim" in item and "evidence" in item:
            result.append({
                "claim": str(item["claim"])[:500],
                "evidence": str(item["evidence"])[:1000],
                "location": str(item["location"])[:200] if item.get("location") else None,
            })

    if not result:
        raise ValueError("No valid evidence items parsed")

    return result


def _extract_evidence_heuristic(
    summary_text: str,
    source_text: str | None,
) -> list[dict]:
    """Heuristic fallback: split summary into sentences and find matching source passages."""
    sentences = [s.strip() + "." for s in summary_text.split(".") if len(s.strip()) > 20]

    result = []
    for sentence in sentences[:5]:  # Cap at 5
        evidence = _find_supporting_passage(sentence, source_text) if source_text else None
        result.append({
            "claim": sentence,
            "evidence": evidence or "No source text available for verification.",
            "location": None,
        })

    return result


def _find_supporting_passage(claim: str, source_text: str) -> str | None:
    """Find the most relevant passage in source text for a given claim."""
    # Simple keyword overlap scoring
    claim_words = set(
        w.lower() for w in claim.split()
        if len(w) > 3 and w.lower() not in {
            "that", "this", "with", "from", "have", "been",
            "were", "also", "than", "more", "into", "their",
        }
    )

    if not claim_words:
        return None

    # Split source into sentences
    source_sentences = [s.strip() for s in source_text.replace("\n", " ").split(".") if len(s.strip()) > 20]

    best_score = 0
    best_passage = None

    for sent in source_sentences:
        sent_words = set(w.lower() for w in sent.split())
        overlap = len(claim_words & sent_words)
        score = overlap / len(claim_words) if claim_words else 0
        if score > best_score:
            best_score = score
            best_passage = sent.strip() + "."

    if best_score >= 0.3 and best_passage:
        return f'"{best_passage}"'

    return None
