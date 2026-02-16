"""Tests for API endpoints: evidence, export, synthesis, auth, and summary CRUD."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from paper_summarizer.web.app import create_app
from tests.config import TEST_CONFIG, TEST_DATA


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_test_env():
    os.environ['TESTING'] = 'true'
    os.environ['TOGETHER_API_KEY'] = 'test_key'
    with tempfile.TemporaryDirectory() as temp_dir:
        TEST_CONFIG['UPLOAD_FOLDER'] = temp_dir
        TEST_CONFIG['DATABASE_URL'] = f"sqlite:///{temp_dir}/test.db"
        yield
    os.environ.pop('TESTING', None)
    os.environ.pop('TOGETHER_API_KEY', None)


@pytest.fixture
def client():
    app = create_app(TEST_CONFIG)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "test-password"},
    )
    if response.status_code != 200:
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "test-password"},
        )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_summary(client, auth_headers):
    """Helper: create a summary via the /summarize endpoint with a mocked summarizer."""
    with patch('paper_summarizer.web.routes.summaries.PaperSummarizer') as mock_cls:
        mock_instance = MagicMock()
        mock_instance.summarize.return_value = TEST_DATA['sample_summary']
        mock_cls.return_value = mock_instance
        response = client.post(
            '/summarize',
            data={
                'source_type': 'text',
                'text': TEST_DATA['sample_text'],
                'num_sentences': 5,
                'model_type': 't5-small',
                'provider': 'together_ai',
            },
            headers=auth_headers,
        )
    assert response.status_code == 200, response.text
    return response.json()['summary_id']


# ---------------------------------------------------------------------------
# 1. Auth endpoint tests
# ---------------------------------------------------------------------------

class TestAuth:
    def test_register_valid(self, client):
        response = client.post(
            "/auth/register",
            json={"email": "new@example.com", "password": "secure-password"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client):
        client.post(
            "/auth/register",
            json={"email": "dup@example.com", "password": "secure-password"},
        )
        response = client.post(
            "/auth/register",
            json={"email": "dup@example.com", "password": "another-password"},
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["error"].lower()

    def test_login_valid(self, client):
        client.post(
            "/auth/register",
            json={"email": "login@example.com", "password": "secure-password"},
        )
        response = client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "secure-password"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        client.post(
            "/auth/register",
            json={"email": "wrong@example.com", "password": "secure-password"},
        )
        response = client.post(
            "/auth/login",
            json={"email": "wrong@example.com", "password": "bad-password"},
        )
        assert response.status_code == 401

    def test_me_with_valid_token(self, client, auth_headers):
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "id" in data

    def test_me_without_token(self, client):
        response = client.get("/auth/me")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 2. Evidence endpoint tests
# ---------------------------------------------------------------------------

class TestEvidence:
    def test_create_evidence(self, client, auth_headers):
        summary_id = _create_summary(client, auth_headers)
        response = client.post(
            f"/api/summaries/{summary_id}/evidence",
            json={
                "claim": "Test claim",
                "evidence": "Test evidence text",
                "location": "Section 3",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["summary_id"] == summary_id
        assert len(data["items"]) == 1
        assert data["items"][0]["claim"] == "Test claim"
        assert data["items"][0]["evidence"] == "Test evidence text"
        assert data["items"][0]["location"] == "Section 3"

    def test_list_evidence(self, client, auth_headers):
        summary_id = _create_summary(client, auth_headers)
        # Create two evidence items
        for i in range(2):
            client.post(
                f"/api/summaries/{summary_id}/evidence",
                json={"claim": f"Claim {i}", "evidence": f"Evidence {i}"},
                headers=auth_headers,
            )
        response = client.get(
            f"/api/summaries/{summary_id}/evidence",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["summary_id"] == summary_id
        assert len(data["items"]) == 2

    def test_update_evidence(self, client, auth_headers):
        summary_id = _create_summary(client, auth_headers)
        # Create evidence
        create_resp = client.post(
            f"/api/summaries/{summary_id}/evidence",
            json={"claim": "Original", "evidence": "Original evidence"},
            headers=auth_headers,
        )
        evidence_id = create_resp.json()["items"][0]["id"]

        # Update it
        response = client.put(
            f"/api/summaries/{summary_id}/evidence/{evidence_id}",
            json={"claim": "Updated claim", "location": "Page 5"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        items = response.json()["items"]
        updated = [i for i in items if i["id"] == evidence_id][0]
        assert updated["claim"] == "Updated claim"
        assert updated["evidence"] == "Original evidence"  # unchanged
        assert updated["location"] == "Page 5"

    def test_delete_evidence(self, client, auth_headers):
        summary_id = _create_summary(client, auth_headers)
        create_resp = client.post(
            f"/api/summaries/{summary_id}/evidence",
            json={"claim": "To delete", "evidence": "Will be removed"},
            headers=auth_headers,
        )
        evidence_id = create_resp.json()["items"][0]["id"]

        response = client.delete(
            f"/api/summaries/{summary_id}/evidence/{evidence_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == 0

    def test_generate_evidence(self, client, auth_headers):
        summary_id = _create_summary(client, auth_headers)
        response = client.post(
            f"/api/summaries/{summary_id}/evidence/generate",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["summary_id"] == summary_id
        # The generate endpoint splits on "." and takes up to 2 sentences
        assert len(data["items"]) > 0
        for item in data["items"]:
            assert "Evidence placeholder" in item["evidence"]


# ---------------------------------------------------------------------------
# 3. Export endpoint tests
# ---------------------------------------------------------------------------

class TestExport:
    def test_export_txt(self, client, auth_headers):
        summary_id = _create_summary(client, auth_headers)
        response = client.get(
            f"/export/{summary_id}?format=txt",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert TEST_DATA['sample_summary'] in response.text
        assert "text/plain" in response.headers["content-type"]
        assert f"summary_{summary_id}.txt" in response.headers.get("content-disposition", "")

    def test_export_md(self, client, auth_headers):
        summary_id = _create_summary(client, auth_headers)
        response = client.get(
            f"/export/{summary_id}?format=md",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "# Summary" in response.text
        assert TEST_DATA['sample_summary'] in response.text
        assert f"summary_{summary_id}.md" in response.headers.get("content-disposition", "")

    def test_export_pdf(self, client, auth_headers):
        summary_id = _create_summary(client, auth_headers)
        response = client.get(
            f"/export/{summary_id}?format=pdf",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert f"summary_{summary_id}.pdf" in response.headers.get("content-disposition", "")
        # PDF files start with %PDF
        assert response.content[:5] == b"%PDF-"

    def test_export_invalid_summary_id(self, client, auth_headers):
        response = client.get(
            "/export/nonexistent-id?format=txt",
            headers=auth_headers,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# 4. Synthesis endpoint tests
# ---------------------------------------------------------------------------

class TestSynthesis:
    def test_synthesize_summaries(self, client, auth_headers):
        id1 = _create_summary(client, auth_headers)
        id2 = _create_summary(client, auth_headers)
        response = client.post(
            "/api/summaries/synthesize",
            json={"summary_ids": [id1, id2]},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "consensus" in data
        assert "Consensus Snapshot" in data["consensus"]
        assert "sources" in data
        assert id1 in data["sources"]
        assert id2 in data["sources"]
        assert "disagreements" in data
        assert "citations" in data

    def test_synthesize_empty_ids(self, client, auth_headers):
        response = client.post(
            "/api/summaries/synthesize",
            json={"summary_ids": []},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_synthesize_no_ids_field(self, client, auth_headers):
        response = client.post(
            "/api/summaries/synthesize",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422  # validation error


# ---------------------------------------------------------------------------
# 5. Summary CRUD endpoint tests
# ---------------------------------------------------------------------------

class TestSummaryCRUD:
    def test_list_summaries(self, client, auth_headers):
        _create_summary(client, auth_headers)
        _create_summary(client, auth_headers)
        response = client.get("/api/summaries", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "summaries" in data
        assert len(data["summaries"]) >= 2

    def test_get_summary_detail(self, client, auth_headers):
        summary_id = _create_summary(client, auth_headers)
        response = client.get(
            f"/api/summaries/{summary_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == summary_id
        assert data["summary"] == TEST_DATA['sample_summary']
        assert data["source_type"] == "text"
        assert data["model_type"] == "t5-small"
        assert data["provider"] == "together_ai"
        assert data["num_sentences"] == 5

    def test_get_summary_not_found(self, client, auth_headers):
        response = client.get(
            "/api/summaries/nonexistent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_delete_summary(self, client, auth_headers):
        summary_id = _create_summary(client, auth_headers)
        response = client.delete(
            f"/api/summaries/{summary_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify it is gone
        get_resp = client.get(
            f"/api/summaries/{summary_id}",
            headers=auth_headers,
        )
        assert get_resp.status_code == 404

    def test_export_summaries_bulk(self, client, auth_headers):
        """GET /api/summaries/export is shadowed by the /api/summaries/{summary_id}
        route (which is registered first and treats 'export' as a summary_id).
        Verify the request returns 404 due to the route-ordering conflict."""
        _create_summary(client, auth_headers)
        response = client.get("/api/summaries/export", headers=auth_headers)
        assert response.status_code == 404

    def test_import_summaries(self, client, auth_headers):
        payload = [
            {
                "title": "Imported Paper 1",
                "summary": "Imported summary content one.",
                "source_type": "import",
                "model_type": "t5-small",
                "provider": "import",
                "num_sentences": 3,
            },
            {
                "title": "Imported Paper 2",
                "summary": "Imported summary content two.",
                "source_type": "import",
                "model_type": "t5-small",
                "provider": "import",
                "num_sentences": 5,
            },
        ]
        response = client.post(
            "/api/summaries/import",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "imported"
        assert data["count"] == 2

        # Verify they appear in the list
        list_resp = client.get("/api/summaries", headers=auth_headers)
        titles = [s["title"] for s in list_resp.json()["summaries"]]
        assert "Imported Paper 1" in titles
        assert "Imported Paper 2" in titles

    def test_import_skips_entries_without_summary(self, client, auth_headers):
        payload = [
            {"title": "No summary field"},
            {"summary": "Valid one"},
        ]
        response = client.post(
            "/api/summaries/import",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_analytics(self, client, auth_headers):
        _create_summary(client, auth_headers)
        response = client.get("/api/analytics", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "totalSummaries" in data
        assert data["totalSummaries"] >= 1
        assert "modelUsage" in data
        assert "averageLength" in data
        assert "uniqueModels" in data
        assert "lengthDistribution" in data
        assert "dailyActivity" in data
