"""Focused tests for synthesis helper behavior and exports."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from paper_summarizer.web.models import Summary
from paper_summarizer.web.routes.synthesis import _synthesize_heuristic, _synthesize_llm


def _make_summary(summary_id: str, title: str, text: str) -> Summary:
    return Summary(
        id=summary_id,
        user_id="user-1",
        title=title,
        source_type="text",
        source_value=None,
        summary=text,
        model_type="t5-small",
        provider="together_ai",
        num_sentences=5,
        created_at=datetime.now(timezone.utc),
    )


def test_synthesize_heuristic_builds_consensus_and_citations() -> None:
    rows = [
        _make_summary(
            "s1", "Paper A", "Machine learning improves outcomes. It reduces cost."
        ),
        _make_summary(
            "s2",
            "Paper B",
            "Machine learning improves outcomes. It increases accuracy.",
        ),
    ]

    result = _synthesize_heuristic(rows)

    assert "Cross-Paper Synthesis" in result.consensus
    assert "Shared themes" in result.consensus
    assert result.sources == ["s1", "s2"]
    assert len(result.citations) == 2


@patch("paper_summarizer.web.routes.synthesis.together.Complete.create")
def test_synthesize_llm_parses_markdown_json(mock_create) -> None:
    rows = [_make_summary("s1", "Paper A", "A short summary.")]
    mock_create.return_value = {
        "output": {
            "choices": [
                {
                    "text": '```json\n{"consensus": "Unified finding", "disagreements": []}\n```'
                }
            ]
        }
    }

    result = _synthesize_llm(rows, api_key="dummy")

    assert result.consensus == "Unified finding"
    assert result.disagreements == []
    assert result.sources == ["s1"]


def test_export_synthesis_pdf_response(client, auth_headers) -> None:
    response = client.get(
        "/api/summaries/synthesize/export",
        params={"consensus": "Line one\nLine two", "format": "pdf"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
