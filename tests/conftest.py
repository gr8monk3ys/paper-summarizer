"""Test configuration for pytest."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from paper_summarizer.web.app import create_app
from tests.config import TEST_CONFIG, TEST_DATA

@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    # Set testing mode
    os.environ['TESTING'] = 'true'
    os.environ['TOGETHER_API_KEY'] = 'test_key'
    
    # Create temporary upload directory
    with tempfile.TemporaryDirectory() as temp_dir:
        TEST_CONFIG['UPLOAD_FOLDER'] = temp_dir
        TEST_CONFIG['DATABASE_URL'] = f"sqlite:///{temp_dir}/test.db"
        yield
        
    # Clean up
    os.environ.pop('TESTING', None)
    os.environ.pop('TOGETHER_API_KEY', None)

@pytest.fixture
def app():
    """Create test application."""
    return create_app(TEST_CONFIG)

@pytest.fixture
def client(app):
    """Create test client."""
    with TestClient(app) as client:
        yield client


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

@pytest.fixture
def mock_summarizer():
    """Mock summarizer responses."""
    with patch('paper_summarizer.core.summarizer.PaperSummarizer.summarize') as mock:
        mock.return_value = TEST_DATA['sample_summary']
        yield mock

@pytest.fixture
def mock_together_api():
    """Mock Together AI API responses."""
    with patch('together.Complete.create') as mock:
        mock.return_value = {
            'output': {
                'choices': [{
                    'text': TEST_DATA['sample_summary']
                }]
            }
        }
        yield mock

@pytest.fixture
def test_file():
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(TEST_DATA['sample_text'])
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()

@pytest.fixture
def test_files():
    """Create multiple temporary test files."""
    files = []
    try:
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(TEST_DATA['sample_text'])
                files.append(Path(f.name))
        yield files
    finally:
        for file in files:
            if file.exists():
                file.unlink()
