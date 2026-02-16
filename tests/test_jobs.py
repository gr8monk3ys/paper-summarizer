"""Tests for the jobs route module."""

import json
import uuid

import pytest
from unittest.mock import Mock, patch, MagicMock

from paper_summarizer.core.summarizer import ModelType, ModelProvider
from paper_summarizer.web.routes.jobs import _run_summary_job
from paper_summarizer.web.models import Job
from paper_summarizer.web.schemas import JobSummaryRequest
from paper_summarizer.web.db import get_session
from tests.config import TEST_DATA


@pytest.fixture
def mock_summarizer():
    """Mock PaperSummarizer for job route tests."""
    mock_instance = Mock()
    mock_instance.summarize.return_value = TEST_DATA["sample_summary"]
    mock_instance.summarize_from_url.return_value = TEST_DATA["sample_summary"]
    mock_instance.summarize_from_file.return_value = TEST_DATA["sample_summary"]
    with patch("paper_summarizer.web.routes.jobs.PaperSummarizer") as mock_cls:
        mock_cls.return_value = mock_instance
        yield mock_cls


def _get_engine_from_app(app):
    """Extract the SQLAlchemy engine from the app state."""
    return app.state.engine


def _get_settings_from_app(app):
    """Extract settings dict from the app state."""
    return app.state.settings


# ---------------------------------------------------------------------------
# POST /api/jobs/summarize
# ---------------------------------------------------------------------------


class TestCreateSummaryJob:
    """Tests for the POST /api/jobs/summarize endpoint."""

    def test_create_job_with_text_source(self, client, auth_headers, mock_summarizer):
        """POST /api/jobs/summarize with text source returns job_id and queued status."""
        payload = {
            "source_type": "text",
            "text": TEST_DATA["sample_text"],
            "num_sentences": 5,
            "model_type": ModelType.T5_SMALL.value,
            "provider": ModelProvider.LOCAL.value,
        }
        response = client.post("/api/jobs/summarize", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_create_job_with_url_source(self, client, auth_headers, mock_summarizer):
        """POST /api/jobs/summarize with URL source returns job_id and queued status."""
        payload = {
            "source_type": "url",
            "url": TEST_DATA["sample_url"],
            "num_sentences": 5,
            "model_type": ModelType.T5_SMALL.value,
            "provider": ModelProvider.LOCAL.value,
        }
        with patch("paper_summarizer.web.routes.jobs.validate_url"):
            response = client.post("/api/jobs/summarize", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_create_job_invalid_source_type_returns_400(self, client, auth_headers):
        """POST /api/jobs/summarize with unsupported source_type returns 400."""
        payload = {
            "source_type": "file",
            "text": TEST_DATA["sample_text"],
        }
        response = client.post("/api/jobs/summarize", json=payload, headers=auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_create_job_without_auth_returns_401(self, client):
        """POST /api/jobs/summarize without authentication returns 401."""
        payload = {
            "source_type": "text",
            "text": TEST_DATA["sample_text"],
        }
        response = client.post("/api/jobs/summarize", json=payload)
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------


class TestGetJobStatus:
    """Tests for the GET /api/jobs/{job_id} endpoint."""

    def test_get_job_status(self, client, auth_headers, mock_summarizer):
        """GET /api/jobs/{job_id} returns the correct job status."""
        # First create a job so we have a valid job_id.
        payload = {
            "source_type": "text",
            "text": TEST_DATA["sample_text"],
        }
        create_resp = client.post("/api/jobs/summarize", json=payload, headers=auth_headers)
        assert create_resp.status_code == 200
        job_id = create_resp.json()["job_id"]

        response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] in {"queued", "running", "complete", "failed"}
        assert "created_at" in data

    def test_get_nonexistent_job_returns_404(self, client, auth_headers):
        """GET /api/jobs/{nonexistent_id} returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/jobs/{fake_id}", headers=auth_headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# _run_summary_job  (direct unit tests)
# ---------------------------------------------------------------------------


class TestRunSummaryJob:
    """Direct unit tests for the _run_summary_job helper."""

    def test_success_path_text(self, app, client, auth_headers, mock_summarizer):
        """_run_summary_job with valid text payload marks job as complete."""
        engine = _get_engine_from_app(app)
        settings = _get_settings_from_app(app)

        # Resolve the user id from the auth token.
        me_resp = client.get("/auth/me", headers=auth_headers)
        user_id = me_resp.json()["id"]

        payload = JobSummaryRequest(
            source_type="text",
            text=TEST_DATA["sample_text"],
            num_sentences=5,
            model_type=ModelType.T5_SMALL.value,
            provider=ModelProvider.LOCAL.value,
        )

        # Create a Job row manually.
        job = Job(
            user_id=user_id,
            status="queued",
            payload_json=json.dumps(payload.model_dump()),
        )
        with get_session(engine) as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            job_id = job.id

        # Run the background function directly.
        _run_summary_job(job_id, dict(settings), engine, payload, user_id)

        # Verify the job transitioned to "complete".
        with get_session(engine) as session:
            updated = session.get(Job, job_id)
            assert updated is not None
            assert updated.status == "complete"
            assert updated.result_json is not None
            result = json.loads(updated.result_json)
            assert "summary" in result
            assert "summary_id" in result

    def test_failure_path(self, app, client, auth_headers, mock_summarizer):
        """_run_summary_job records failure when summarizer raises ValueError."""
        engine = _get_engine_from_app(app)
        settings = _get_settings_from_app(app)

        me_resp = client.get("/auth/me", headers=auth_headers)
        user_id = me_resp.json()["id"]

        # Make the mock summarizer raise a ValueError.
        mock_summarizer.return_value.summarize.side_effect = ValueError("boom")

        payload = JobSummaryRequest(
            source_type="text",
            text=TEST_DATA["sample_text"],
            num_sentences=5,
            model_type=ModelType.T5_SMALL.value,
            provider=ModelProvider.LOCAL.value,
        )

        job = Job(
            user_id=user_id,
            status="queued",
            payload_json=json.dumps(payload.model_dump()),
        )
        with get_session(engine) as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            job_id = job.id

        _run_summary_job(job_id, dict(settings), engine, payload, user_id)

        with get_session(engine) as session:
            updated = session.get(Job, job_id)
            assert updated is not None
            assert updated.status == "failed"
            assert updated.error == "boom"
            assert updated.completed_at is not None

    def test_nonexistent_job_early_return(self, app, client, auth_headers, mock_summarizer):
        """_run_summary_job returns early when the job id does not exist."""
        engine = _get_engine_from_app(app)
        settings = _get_settings_from_app(app)

        me_resp = client.get("/auth/me", headers=auth_headers)
        user_id = me_resp.json()["id"]

        payload = JobSummaryRequest(
            source_type="text",
            text=TEST_DATA["sample_text"],
        )

        fake_id = str(uuid.uuid4())

        # Should not raise; just return silently.
        _run_summary_job(fake_id, dict(settings), engine, payload, user_id)

        # Confirm no job was created or modified.
        with get_session(engine) as session:
            assert session.get(Job, fake_id) is None


# ---------------------------------------------------------------------------
# POST /batch
# ---------------------------------------------------------------------------


class TestBatchEndpoint:
    """Tests for the POST /batch endpoint."""

    def test_batch_no_files_returns_400(self, client, auth_headers):
        """POST /batch with no files returns 400."""
        response = client.post(
            "/batch",
            data={
                "num_sentences": "5",
                "model_type": ModelType.T5_SMALL.value,
                "provider": ModelProvider.LOCAL.value,
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_batch_without_auth_returns_401(self, client):
        """POST /batch without authentication returns 401/403."""
        response = client.post("/batch")
        assert response.status_code in (401, 403)
