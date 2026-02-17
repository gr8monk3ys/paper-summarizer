"""Synthesis endpoints."""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

from sqlmodel import col, select

from paper_summarizer.web.auth import get_current_user
from paper_summarizer.web.db import get_session
from paper_summarizer.web.deps import _get_engine
from paper_summarizer.web.models import Summary, User
from paper_summarizer.web.schemas import (
    SynthesisRequest,
    SynthesisResponse,
)

router = APIRouter()


@router.post("/api/summaries/synthesize", response_model=SynthesisResponse, tags=["summaries"])
def synthesize_summaries(payload: SynthesisRequest, request: Request, current_user: User = Depends(get_current_user)) -> SynthesisResponse:
    engine = _get_engine(request)
    with get_session(engine) as session:
        rows = session.exec(
            select(Summary).where(
                col(Summary.id).in_(payload.summary_ids),
                Summary.user_id == current_user.id,
            )
        ).all()

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
        counts: dict[str, int] = {}
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
