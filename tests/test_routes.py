"""Tests for the web routes."""

import os
import io
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from paper_summarizer.web.app import create_app
from paper_summarizer.core.summarizer import ModelType, ModelProvider
from tests.config import TEST_CONFIG, MODEL_CONFIG, TEST_DATA

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app('testing')
    app.config.update(TEST_CONFIG)
    return app

@pytest.fixture
def test_file():
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(TEST_DATA['sample_text'])
        return Path(f.name)

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def mock_summarizer():
    """Mock PaperSummarizer instance."""
    with patch('paper_summarizer.web.routes.PaperSummarizer') as mock:
        mock_instance = Mock()
        mock_instance.summarize.return_value = TEST_DATA['sample_summary']
        mock_instance.summarize_from_url.return_value = TEST_DATA['sample_summary']
        mock_instance.summarize_from_file.return_value = TEST_DATA['sample_summary']
        mock_instance.get_available_models.return_value = {
            "together_ai": [
                {"id": "deepseek-r1", "name": "DeepSeek R1", "description": "High-quality model"}
            ],
            "local": [
                {"id": "t5-small", "name": "T5 Small", "description": "Fast local model"}
            ]
        }
        mock.return_value = mock_instance
        yield mock

class TestRoutes:
    """Test cases for web routes."""

    def test_index_route(self, client):
        """Test the index route."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Paper Summarizer' in response.data

    def test_models_route(self, client, mock_summarizer):
        """Test getting available models."""
        response = client.get('/models')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "together_ai" in data
        assert "local" in data

    def test_summarize_url(self, client, mock_summarizer):
        """Test summarization from URL."""
        data = {
            'source_type': 'url',
            'url': TEST_DATA['sample_url'],
            'num_sentences': 5,
            'model_type': ModelType.DEEPSEEK_R1.value,
            'provider': ModelProvider.TOGETHER_AI.value
        }
        response = client.post('/summarize', data=data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['summary'] == TEST_DATA['sample_summary']

    def test_summarize_text(self, client, mock_summarizer):
        """Test summarization from direct text."""
        data = {
            'source_type': 'text',
            'text': TEST_DATA['sample_text'],
            'num_sentences': 5,
            'model_type': ModelType.T5_SMALL.value,
            'provider': ModelProvider.LOCAL.value
        }
        response = client.post('/summarize', data=data)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['summary'] == TEST_DATA['sample_summary']

    def test_summarize_file(self, client, mock_summarizer, test_file):
        """Test summarization from file upload."""
        with open(test_file, 'rb') as f:
            data = {
                'source_type': 'file',
                'num_sentences': 5,
                'model_type': ModelType.DEEPSEEK_R1.value,
                'provider': ModelProvider.TOGETHER_AI.value,
                'file': (f, 'test.txt')
            }
            response = client.post('/summarize', data=data)
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['summary'] == TEST_DATA['sample_summary']

    def test_batch_processing(self, client, mock_summarizer, test_file):
        """Test batch processing of files."""
        with open(test_file, 'rb') as f:
            data = {
                'num_sentences': 5,
                'model_type': ModelType.T5_SMALL.value,
                'provider': ModelProvider.LOCAL.value,
                'files[]': [(f, 'test.txt')]
            }
            response = client.post('/batch', data=data)
            assert response.status_code == 200
            data = json.loads(response.data)
            assert len(data['summaries']) > 0
            assert data['summaries'][0]['summary'] == TEST_DATA['sample_summary']

    def test_invalid_source_type(self, client):
        """Test handling of invalid source type."""
        data = {
            'source_type': 'invalid',
            'text': TEST_DATA['sample_text']
        }
        response = client.post('/summarize', data=data)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_missing_required_fields(self, client):
        """Test handling of missing required fields."""
        data = {
            'source_type': 'url'
            # Missing URL field
        }
        response = client.post('/summarize', data=data)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_settings_route(self, client):
        """Test the settings route."""
        response = client.get('/settings')
        assert response.status_code == 200

    def test_save_settings(self, client):
        """Test saving user settings."""
        settings = {
            'defaultModel': ModelType.T5_SMALL.value,
            'apiKey': 'test_key',
            'summaryLength': 5,
            'citationHandling': 'remove',
            'autoSave': True
        }
        response = client.post('/api/settings', json=settings)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'

    def test_library_route(self, client):
        """Test the library route."""
        response = client.get('/library')
        assert response.status_code == 200

    def test_batch_route(self, client):
        """Test the batch processing route."""
        response = client.get('/batch')
        assert response.status_code == 200

    def test_analytics_route(self, client):
        """Test the analytics route."""
        response = client.get('/analytics')
        assert response.status_code == 200

    @pytest.mark.parametrize("route", [
        '/library',
        '/batch',
        '/analytics',
        '/settings'
    ])
    def test_template_rendering(self, client, route):
        """Test that all templates render correctly."""
        response = client.get(route)
        assert response.status_code == 200
        assert b'Paper Summarizer' in response.data
