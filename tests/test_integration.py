"""Integration tests for the Paper Summarizer application."""

import pytest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from paper_summarizer.web.app import create_app
from paper_summarizer.core.summarizer import ModelType, ModelProvider
from tests.config import TEST_DATA, TEST_CONFIG

class TestIntegration:
    """Integration test cases."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        return create_app(TEST_CONFIG)

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        with TestClient(app) as client:
            yield client

    @pytest.fixture
    def test_files(self):
        """Create test files for batch processing."""
        files = []
        for i in range(3):
            path = Path(f'test_file_{i}.txt')
            path.write_text(TEST_DATA['sample_text'])
            files.append(path)
        yield files
        for file in files:
            if file.exists():
                file.unlink()

    def test_index_route(self, client):
        """Test index route."""
        response = client.get('/')
        assert response.status_code == 200
        assert 'Paper Summarizer' in response.text

    def test_summarize_from_url(self, client, auth_headers):
        """Test summarization from URL."""
        with patch('paper_summarizer.core.summarizer.PaperSummarizer.summarize_from_url') as mock_summarize, \
             patch('paper_summarizer.web.routes.summaries.validate_url'):
            mock_summarize.return_value = TEST_DATA['sample_summary']

            data = {
                'source_type': 'url',
                'url': TEST_DATA['sample_url'],
                'model_type': ModelType.T5_SMALL.value,
                'provider': ModelProvider.TOGETHER_AI.value,
                'num_sentences': 3
            }
            response = client.post('/summarize', data=data, headers=auth_headers)
            assert response.status_code == 200
            result = response.json()
            assert result['summary'] == TEST_DATA['sample_summary']

    def test_summarize_from_text(self, client, auth_headers):
        """Test summarization from direct text input."""
        with patch('paper_summarizer.core.summarizer.PaperSummarizer.summarize') as mock_summarize:
            mock_summarize.return_value = TEST_DATA['sample_summary']

            data = {
                'source_type': 'text',
                'text': TEST_DATA['sample_text'],
                'model_type': ModelType.T5_SMALL.value,
                'provider': ModelProvider.TOGETHER_AI.value,
                'num_sentences': 3
            }
            response = client.post('/summarize', data=data, headers=auth_headers)
            assert response.status_code == 200
            result = response.json()
            assert result['summary'] == TEST_DATA['sample_summary']

    def test_batch_processing_flow(self, client, test_files, auth_headers):
        """Test batch processing of multiple files."""
        with patch('paper_summarizer.core.summarizer.PaperSummarizer.summarize_from_file') as mock_summarize:
            mock_summarize.return_value = TEST_DATA['sample_summary']

            data = {
                'model_type': ModelType.T5_SMALL.value,
                'provider': ModelProvider.TOGETHER_AI.value,
                'num_sentences': '3',
            }

            files = []
            for file_path in test_files:
                files.append(('files[]', (file_path.name, file_path.read_bytes(), 'text/plain')))

            response = client.post('/batch', data=data, files=files, headers=auth_headers)
            
            assert response.status_code == 200
            result = response.json()
            assert len(result['summaries']) == len(test_files)
            assert all(s['summary'] == TEST_DATA['sample_summary'] for s in result['summaries'])

    def test_error_handling(self, client, auth_headers):
        """Test error handling across the application."""
        # 1. Invalid model type
        data = {
            'source_type': 'text',
            'text': TEST_DATA['sample_text'],
            'model_type': 'invalid_model'
        }
        response = client.post('/summarize', data=data, headers=auth_headers)
        assert response.status_code == 400
        result = response.json()
        assert 'error' in result

        # 2. Missing required fields
        data = {
            'source_type': 'url'
        }
        response = client.post('/summarize', data=data, headers=auth_headers)
        assert response.status_code == 400
        result = response.json()
        assert 'error' in result

        # 3. Invalid file type
        data = {
            'source_type': 'file',
            'num_sentences': 3,
            'model_type': ModelType.T5_SMALL.value,
            'provider': ModelProvider.LOCAL.value,
        }
        files = {'file': ('test.xyz', b'test content', 'text/plain')}
        response = client.post('/summarize', data=data, files=files, headers=auth_headers)
        
        assert response.status_code == 400
        result = response.json()
        assert 'error' in result
