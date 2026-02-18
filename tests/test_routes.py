"""Tests for the web routes."""

import pytest
from unittest.mock import Mock, patch

from paper_summarizer.core.summarizer import ModelType, ModelProvider
from tests.config import TEST_DATA

@pytest.fixture
def mock_summarizer():
    """Mock PaperSummarizer instance."""
    mock_instance = Mock()
    mock_instance.summarize.return_value = TEST_DATA['sample_summary']
    mock_instance.summarize_from_url.return_value = TEST_DATA['sample_summary']
    mock_instance.summarize_from_file.return_value = TEST_DATA['sample_summary']
    mock_instance.get_available_models.return_value = [
        {"name": "deepseek-r1", "provider": "together_ai", "description": "High-quality model"},
        {"name": "t5-small", "provider": "local", "description": "Fast local model"},
    ]
    with patch('paper_summarizer.web.routes.summaries.PaperSummarizer') as mock_summaries, \
         patch('paper_summarizer.web.routes.html.PaperSummarizer') as mock_html, \
         patch('paper_summarizer.web.routes.jobs.PaperSummarizer') as mock_jobs:
        for m in (mock_summaries, mock_html, mock_jobs):
            m.return_value = mock_instance
        yield mock_summaries

class TestRoutes:
    """Test cases for web routes."""

    def test_index_route(self, client):
        """Test the index route."""
        response = client.get('/')
        assert response.status_code == 200
        assert 'Paper Summarizer' in response.text

    def test_models_route(self, client, mock_summarizer):
        """Test getting available models."""
        response = client.get('/models')
        assert response.status_code == 200
        data = response.json()
        assert "together_ai" in data
        assert "local" in data

    def test_summarize_url(self, client, mock_summarizer, auth_headers):
        """Test summarization from URL."""
        data = {
            'source_type': 'url',
            'url': TEST_DATA['sample_url'],
            'num_sentences': 5,
            'model_type': ModelType.DEEPSEEK_R1.value,
            'provider': ModelProvider.TOGETHER_AI.value
        }
        with patch('paper_summarizer.web.routes.summaries.validate_url'):
            response = client.post('/summarize', data=data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data['summary'] == TEST_DATA['sample_summary']

    def test_summarize_text(self, client, mock_summarizer, auth_headers):
        """Test summarization from direct text."""
        data = {
            'source_type': 'text',
            'text': TEST_DATA['sample_text'],
            'num_sentences': 5,
            'model_type': ModelType.T5_SMALL.value,
            'provider': ModelProvider.LOCAL.value
        }
        response = client.post('/summarize', data=data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data['summary'] == TEST_DATA['sample_summary']

    def test_summarize_file(self, client, mock_summarizer, test_file, auth_headers):
        """Test summarization from file upload."""
        with open(test_file, 'rb') as f:
            data = {
                'source_type': 'file',
                'num_sentences': 5,
                'model_type': ModelType.DEEPSEEK_R1.value,
                'provider': ModelProvider.TOGETHER_AI.value,
            }
            files = {'file': ('test.txt', f, 'text/plain')}
            response = client.post('/summarize', data=data, files=files, headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data['summary'] == TEST_DATA['sample_summary']

    def test_batch_processing(self, client, mock_summarizer, test_file, auth_headers):
        """Test batch processing of files."""
        with open(test_file, 'rb') as f:
            data = {
                'num_sentences': 5,
                'model_type': ModelType.T5_SMALL.value,
                'provider': ModelProvider.LOCAL.value,
            }
            files = [('files[]', ('test.txt', f, 'text/plain'))]
            response = client.post('/batch', data=data, files=files, headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data['summaries']) > 0
            assert data['summaries'][0]['summary'] == TEST_DATA['sample_summary']

    def test_invalid_source_type(self, client, auth_headers):
        """Test handling of invalid source type."""
        data = {
            'source_type': 'invalid',
            'text': TEST_DATA['sample_text']
        }
        response = client.post('/summarize', data=data, headers=auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data

    def test_missing_required_fields(self, client, auth_headers):
        """Test handling of missing required fields."""
        data = {
            'source_type': 'url'
            # Missing URL field
        }
        response = client.post('/summarize', data=data, headers=auth_headers)
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data

    def test_settings_route(self, client):
        """Test the settings route."""
        response = client.get('/settings')
        assert response.status_code == 200

    def test_save_settings(self, client, auth_headers):
        """Test saving user settings."""
        settings = {
            'defaultModel': ModelType.T5_SMALL.value,
            'summaryLength': 5,
            'citationHandling': 'remove',
            'autoSave': True
        }
        response = client.post('/api/settings', json=settings, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data['defaultModel'] == ModelType.T5_SMALL.value
        assert data['summaryLength'] == 5
        assert data['citationHandling'] == 'remove'
        assert data['autoSave'] is True

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
        assert 'Paper Summarizer' in response.text
