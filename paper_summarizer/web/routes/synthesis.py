"""Synthesis endpoints."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from io import BytesIO

import together
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

logger = logging.getLogger(__name__)

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

    api_key = os.getenv("TOGETHER_API_KEY", "")
    if api_key and not os.getenv("TESTING"):
        try:
            return _synthesize_llm(rows, api_key)
        except Exception as exc:
            logger.warning("LLM synthesis failed, using heuristic: %s", exc)

    return _synthesize_heuristic(rows)


def _synthesize_llm(rows: list[Summary], api_key: str) -> SynthesisResponse:
    """Use Together AI for real multi-document synthesis."""
    together.api_key = api_key

    summaries_text = ""
    for i, row in enumerate(rows, 1):
        title = row.title or f"Paper {i}"
        summaries_text += f"\n[{i}] {title}:\n{row.summary}\n"

    prompt = (
        "You are an expert research synthesist. Analyze the following "
        f"{len(rows)} paper summaries and produce a structured synthesis.\n\n"
        f"Paper summaries:{summaries_text}\n\n"
        "Provide your analysis as a JSON object with these fields:\n"
        '- "consensus": A 2-4 paragraph synthesis of the common findings, '
        "themes, and agreements across these papers. Reference papers by "
        "their number [1], [2], etc.\n"
        '- "disagreements": An array of strings, each describing a specific '
        "point of disagreement or contradiction between papers. Empty array "
        "if none found.\n\n"
        "Respond ONLY with valid JSON:\n"
    )

    response = together.Complete.create(
        prompt=prompt,
        model="deepseek-r1",
        max_tokens=2048,
        temperature=0.2,
        stop=["\n\n\n"],
    )

    raw = response["output"]["choices"][0]["text"].strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    parsed = json.loads(raw)

    consensus = str(parsed.get("consensus", ""))
    disagreements = parsed.get("disagreements", [])
    if not isinstance(disagreements, list):
        disagreements = [str(disagreements)]
    disagreements = [str(d) for d in disagreements]

    sources = [row.id for row in rows]
    citations = [
        {
            "summary_id": row.id,
            "title": row.title,
            "excerpt": row.summary.split(".")[0].strip(),
        }
        for row in rows
    ]

    return SynthesisResponse(
        consensus=consensus,
        disagreements=disagreements,
        sources=sources,
        citations=citations,
    )


def _synthesize_heuristic(rows: list[Summary]) -> SynthesisResponse:
    """Improved heuristic synthesis without LLM."""
    # Group by themes using sentence-level comparison
    all_sentences: list[tuple[str, Summary]] = []
    for row in rows:
        for sent in row.summary.split("."):
            sent = sent.strip()
            if len(sent) > 20:
                all_sentences.append((sent + ".", row))

    # Build consensus by collecting all key sentences organized by paper
    consensus_parts = ["# Cross-Paper Synthesis\n"]
    for i, row in enumerate(rows, 1):
        title = row.title or f"Paper {i}"
        first_sentence = row.summary.split(".")[0].strip()
        if first_sentence:
            consensus_parts.append(f"**[{i}] {title}**: {first_sentence}.")

    consensus_parts.append("")

    # Find overlapping themes via shared vocabulary
    paper_keywords: list[set[str]] = []
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "are",
        "was", "were", "have", "has", "had", "into", "been", "also",
        "their", "they", "these", "those", "which", "about", "would",
        "could", "using", "used", "more", "than", "between", "such",
    }
    for row in rows:
        words = set(
            w.lower() for w in row.summary.split()
            if len(w) > 3 and w.lower() not in stopwords
        )
        paper_keywords.append(words)

    if len(paper_keywords) >= 2:
        # Find common themes (words appearing in majority of papers)
        all_words = Counter()
        for kw_set in paper_keywords:
            for w in kw_set:
                all_words[w] += 1
        threshold = max(2, len(rows) // 2)
        common = [w for w, c in all_words.most_common(10) if c >= threshold]
        if common:
            consensus_parts.append(
                f"**Shared themes**: {', '.join(common)}"
            )

    consensus = "\n".join(consensus_parts)

    # Detect disagreements by looking for contradictory patterns
    disagreements = []
    if len(rows) >= 2:
        # Check if papers discuss different aspects
        unique_per_paper = []
        for i, kw_set in enumerate(paper_keywords):
            others = set()
            for j, other in enumerate(paper_keywords):
                if i != j:
                    others |= other
            unique = kw_set - others
            if unique:
                top_unique = sorted(unique)[:3]
                title = rows[i].title or f"Paper {i+1}"
                unique_per_paper.append((title, top_unique))

        for title, unique_words in unique_per_paper:
            if unique_words:
                disagreements.append(
                    f"{title} uniquely addresses: {', '.join(unique_words)}"
                )

    sources = [row.id for row in rows]
    citations = [
        {
            "summary_id": row.id,
            "title": row.title,
            "excerpt": row.summary.split(".")[0].strip(),
        }
        for row in rows
    ]

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
