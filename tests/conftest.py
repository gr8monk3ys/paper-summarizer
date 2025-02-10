"""Test configuration for pytest."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch
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
        yield
        
    # Clean up
    os.environ.pop('TESTING', None)
    os.environ.pop('TOGETHER_API_KEY', None)

@pytest.fixture
def app():
    """Create test application."""
    app = create_app()
    app.config.update(TEST_CONFIG)
    return app

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

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
