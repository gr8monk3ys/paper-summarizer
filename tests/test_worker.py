"""Tests for paper_summarizer.web.worker module."""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from paper_summarizer.web.config import load_settings
from paper_summarizer.web.db import create_db_engine, get_session, init_db
from paper_summarizer.web.models import Job, Summary
from paper_summarizer.web.worker import (
    WorkerSettings,
    run_summary_job,
    shutdown,
    startup,
)
from tests.config import TEST_CONFIG, TEST_DATA


@pytest.fixture
def db_setup():
    """Create a temporary database engine and settings for worker tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = dict(TEST_CONFIG)
        config["UPLOAD_FOLDER"] = temp_dir
        config["DATABASE_URL"] = f"sqlite:///{temp_dir}/test.db"
        settings = load_settings(config)
        engine = create_db_engine(settings["DATABASE_URL"])
        init_db(engine, reset=True, auto_create=True)
        yield engine, settings


def _make_ctx(engine, settings):
    """Build a worker context dict from engine and settings."""
    return {"engine": engine, "settings": settings}


def _create_job(engine, payload, status="queued", user_id="test-user"):
    """Insert a Job row and return its id."""
    job_id = str(uuid4())
    job = Job(
        id=job_id,
        user_id=user_id,
        status=status,
        payload_json=json.dumps(payload),
    )
    with get_session(engine) as session:
        session.add(job)
        session.commit()
    return job_id


def _get_job(engine, job_id):
    """Reload a Job from the database."""
    with get_session(engine) as session:
        return session.get(Job, job_id)


# ---------- 1. text source – success path ----------


@patch("paper_summarizer.web.worker.PaperSummarizer")
def test_run_summary_job_text_success(mock_cls, db_setup):
    engine, settings = db_setup
    ctx = _make_ctx(engine, settings)

    mock_instance = MagicMock()
    mock_instance.summarize.return_value = TEST_DATA["sample_summary"]
    mock_cls.return_value = mock_instance

    payload = {
        "source_type": "text",
        "text": "First line of paper.\nSecond line.",
        "num_sentences": 3,
        "model_type": "t5-small",
        "provider": "local",
        "keep_citations": False,
    }
    job_id = _create_job(engine, payload)

    asyncio.run(run_summary_job(ctx, job_id))

    job = _get_job(engine, job_id)
    assert job.status == "complete"
    assert job.error is None
    result = json.loads(job.result_json)
    assert "summary_id" in result
    assert result["summary"] == TEST_DATA["sample_summary"]
    assert job.completed_at is not None

    # Verify the Summary row was created
    with get_session(engine) as session:
        summary_record = session.get(Summary, result["summary_id"])
        assert summary_record is not None
        assert summary_record.user_id == "test-user"
        assert summary_record.source_type == "text"
        assert summary_record.source_value is None
        assert summary_record.summary == TEST_DATA["sample_summary"]
        assert summary_record.num_sentences == 3

    mock_instance.summarize.assert_called_once_with(
        "First line of paper.\nSecond line.", 3, False
    )


# ---------- 2. URL source – success path ----------


@patch("paper_summarizer.web.worker.validate_url")
@patch("paper_summarizer.web.worker.PaperSummarizer")
def test_run_summary_job_url_success(mock_cls, mock_validate, db_setup):
    engine, settings = db_setup
    ctx = _make_ctx(engine, settings)

    mock_instance = MagicMock()
    mock_instance.summarize_from_url.return_value = TEST_DATA["sample_summary"]
    mock_cls.return_value = mock_instance

    payload = {
        "source_type": "url",
        "url": "https://example.com/paper.pdf",
        "num_sentences": 5,
        "model_type": "t5-small",
        "provider": "local",
    }
    job_id = _create_job(engine, payload)

    asyncio.run(run_summary_job(ctx, job_id))

    job = _get_job(engine, job_id)
    assert job.status == "complete"
    assert job.error is None
    result = json.loads(job.result_json)
    assert result["summary"] == TEST_DATA["sample_summary"]

    mock_validate.assert_called_once_with("https://example.com/paper.pdf")
    mock_instance.summarize_from_url.assert_called_once_with(
        "https://example.com/paper.pdf", 5
    )

    # Verify Summary row
    with get_session(engine) as session:
        summary_record = session.get(Summary, result["summary_id"])
        assert summary_record is not None
        assert summary_record.source_type == "url"
        assert summary_record.source_value == "https://example.com/paper.pdf"
        assert summary_record.title == "https://example.com/paper.pdf"


# ---------- 3. non-existent job_id – early return ----------


def test_run_summary_job_nonexistent_job(db_setup):
    engine, settings = db_setup
    ctx = _make_ctx(engine, settings)

    missing_id = str(uuid4())
    # Should return without error
    asyncio.run(run_summary_job(ctx, missing_id))


# ---------- 4. already-completed job – early return ----------


def test_run_summary_job_already_completed(db_setup):
    engine, settings = db_setup
    ctx = _make_ctx(engine, settings)

    payload = {"source_type": "text", "text": "some text"}
    job_id = _create_job(engine, payload, status="complete")

    asyncio.run(run_summary_job(ctx, job_id))

    # Status should remain "complete" (no change)
    job = _get_job(engine, job_id)
    assert job.status == "complete"


# ---------- 5. summarizer raises ValueError – job fails ----------


@patch("paper_summarizer.web.worker.PaperSummarizer")
def test_run_summary_job_value_error(mock_cls, db_setup):
    engine, settings = db_setup
    ctx = _make_ctx(engine, settings)

    mock_instance = MagicMock()
    mock_instance.summarize.side_effect = ValueError("Model failed")
    mock_cls.return_value = mock_instance

    payload = {
        "source_type": "text",
        "text": "Some paper text.",
        "num_sentences": 3,
        "model_type": "t5-small",
        "provider": "local",
    }
    job_id = _create_job(engine, payload)

    asyncio.run(run_summary_job(ctx, job_id))

    job = _get_job(engine, job_id)
    assert job.status == "failed"
    assert "Model failed" in job.error
    assert job.completed_at is not None


# ---------- 6. validate_url raises HTTPException – job fails ----------


@patch("paper_summarizer.web.worker.validate_url")
@patch("paper_summarizer.web.worker.PaperSummarizer")
def test_run_summary_job_http_exception(mock_cls, mock_validate, db_setup):
    engine, settings = db_setup
    ctx = _make_ctx(engine, settings)

    mock_validate.side_effect = HTTPException(
        status_code=400, detail="URL host is not allowed"
    )

    payload = {
        "source_type": "url",
        "url": "https://localhost/evil",
        "num_sentences": 5,
        "model_type": "t5-small",
        "provider": "local",
    }
    job_id = _create_job(engine, payload)

    asyncio.run(run_summary_job(ctx, job_id))

    job = _get_job(engine, job_id)
    assert job.status == "failed"
    assert job.error == "URL host is not allowed"
    assert job.completed_at is not None


# ---------- 7. unsupported source_type – job fails ----------


@patch("paper_summarizer.web.worker.PaperSummarizer")
def test_run_summary_job_unsupported_source_type(mock_cls, db_setup):
    engine, settings = db_setup
    ctx = _make_ctx(engine, settings)

    payload = {
        "source_type": "file",
        "num_sentences": 3,
        "model_type": "t5-small",
        "provider": "local",
    }
    job_id = _create_job(engine, payload)

    asyncio.run(run_summary_job(ctx, job_id))

    job = _get_job(engine, job_id)
    assert job.status == "failed"
    assert "Unsupported source type" in job.error


# ---------- 8. missing text field – job fails ----------


@patch("paper_summarizer.web.worker.PaperSummarizer")
def test_run_summary_job_missing_text(mock_cls, db_setup):
    engine, settings = db_setup
    ctx = _make_ctx(engine, settings)

    payload = {
        "source_type": "text",
        "text": "",
        "num_sentences": 3,
        "model_type": "t5-small",
        "provider": "local",
    }
    job_id = _create_job(engine, payload)

    asyncio.run(run_summary_job(ctx, job_id))

    job = _get_job(engine, job_id)
    assert job.status == "failed"
    assert "Text is required" in job.error


# ---------- 9. num_sentences out of range – job fails ----------


@patch("paper_summarizer.web.worker.PaperSummarizer")
def test_run_summary_job_num_sentences_out_of_range(mock_cls, db_setup):
    engine, settings = db_setup
    ctx = _make_ctx(engine, settings)

    payload = {
        "source_type": "text",
        "text": "Some paper text.",
        "num_sentences": 999,
        "model_type": "t5-small",
        "provider": "local",
    }
    job_id = _create_job(engine, payload)

    asyncio.run(run_summary_job(ctx, job_id))

    job = _get_job(engine, job_id)
    assert job.status == "failed"
    assert "Number of sentences must be between" in job.error


# ---------- 10. startup populates ctx ----------


@patch("paper_summarizer.web.worker.create_db_engine")
@patch("paper_summarizer.web.worker.load_settings")
def test_startup_populates_ctx(mock_load_settings, mock_create_engine):
    mock_settings = {"DATABASE_URL": "sqlite:///test.db", "OTHER": "value"}
    mock_load_settings.return_value = mock_settings
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    ctx = {}
    asyncio.run(startup(ctx))

    assert ctx["settings"] is mock_settings
    assert ctx["engine"] is mock_engine
    mock_load_settings.assert_called_once()
    mock_create_engine.assert_called_once_with("sqlite:///test.db")


# ---------- 11. shutdown clears ctx ----------


def test_shutdown_clears_ctx():
    ctx = {"engine": "something", "settings": {"a": 1}}
    asyncio.run(shutdown(ctx))
    assert ctx == {}


# ---------- 12. WorkerSettings class attributes ----------


def test_worker_settings_attributes():
    assert run_summary_job in WorkerSettings.functions
    assert WorkerSettings.on_startup is startup
    assert WorkerSettings.on_shutdown is shutdown
    assert WorkerSettings.cron_jobs == []
