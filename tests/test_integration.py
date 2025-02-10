"""Integration tests for the Paper Summarizer application."""

import os
import json
import pytest
import io
from pathlib import Path
from unittest.mock import patch
from werkzeug.datastructures import FileStorage, MultiDict
from paper_summarizer.web.app import create_app
from paper_summarizer.core.summarizer import ModelType, ModelProvider
from tests.config import TEST_DATA

class TestIntegration:
    """Integration test cases."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        app = create_app()
        app.config['TESTING'] = True
        app.config['TOGETHER_API_KEY'] = 'test_key'
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

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
        assert b'Paper Summarizer' in response.data

    def test_summarize_from_url(self, client):
        """Test summarization from URL."""
        with patch('paper_summarizer.core.summarizer.PaperSummarizer.summarize_from_url') as mock_summarize:
            mock_summarize.return_value = TEST_DATA['sample_summary']

            data = {
                'source_type': 'url',
                'url': TEST_DATA['sample_url'],
                'model_type': ModelType.T5_SMALL.value,
                'provider': ModelProvider.LOCAL.value,
                'num_sentences': 3
            }
            response = client.post('/summarize', data=data)
            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['summary'] == TEST_DATA['sample_summary']

    def test_summarize_from_text(self, client):
        """Test summarization from direct text input."""
        with patch('paper_summarizer.core.summarizer.PaperSummarizer.summarize') as mock_summarize:
            mock_summarize.return_value = TEST_DATA['sample_summary']

            data = {
                'source_type': 'text',
                'text': TEST_DATA['sample_text'],
                'model_type': ModelType.T5_SMALL.value,
                'provider': ModelProvider.LOCAL.value,
                'num_sentences': 3
            }
            response = client.post('/summarize', data=data)
            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['summary'] == TEST_DATA['sample_summary']

    def test_batch_processing_flow(self, client, test_files):
        """Test batch processing of multiple files."""
        with patch('paper_summarizer.core.summarizer.PaperSummarizer.summarize_from_file') as mock_summarize:
            mock_summarize.return_value = TEST_DATA['sample_summary']

            # Create file uploads
            data = MultiDict([
                ('model_type', ModelType.T5_SMALL.value),
                ('provider', ModelProvider.LOCAL.value),
                ('num_sentences', '3')
            ])

            for file_path in test_files:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    file_storage = FileStorage(
                        stream=io.BytesIO(file_content),
                        filename=file_path.name,
                        content_type='text/plain'
                    )
                    data.add('files[]', file_storage)

            response = client.post('/batch', data=data)
            
            assert response.status_code == 200
            result = json.loads(response.data)
            assert len(result['summaries']) == len(test_files)
            assert all(s['summary'] == TEST_DATA['sample_summary'] for s in result['summaries'])

    def test_error_handling(self, client):
        """Test error handling across the application."""
        # 1. Invalid model type
        data = {
            'source_type': 'text',
            'text': TEST_DATA['sample_text'],
            'model_type': 'invalid_model'
        }
        response = client.post('/summarize', data=data)
        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'error' in result

        # 2. Missing required fields
        data = {
            'source_type': 'url'
        }
        response = client.post('/summarize', data=data)
        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'error' in result

        # 3. Invalid file type
        data = MultiDict()
        file_storage = FileStorage(
            stream=io.BytesIO(b'test content'),
            filename='test.xyz',
            content_type='text/plain'
        )
        data.add('file', file_storage)
        
        response = client.post('/summarize', data=data)
        
        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'error' in result
