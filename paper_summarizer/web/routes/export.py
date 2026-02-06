"""PDF and file export endpoints."""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from sqlmodel import select

from paper_summarizer.web.auth import get_current_user
from paper_summarizer.web.db import get_session
from paper_summarizer.web.deps import _get_engine
from paper_summarizer.web.models import Summary, SummaryEvidence, User

router = APIRouter()


@router.get(
    "/export/{summary_id}", response_class=PlainTextResponse, tags=["summaries"]
)
def export_summary(
    summary_id: str,
    request: Request,
    format: str = "txt",
    current_user: User = Depends(get_current_user),
) -> Response:
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
        headers = {
            "Content-Disposition": f'attachment; filename="summary_{summary_id}.pdf"'
        }
        return Response(buffer.read(), media_type="application/pdf", headers=headers)

    filename = f"summary_{summary_id}.txt"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return PlainTextResponse(row.summary, headers=headers)
