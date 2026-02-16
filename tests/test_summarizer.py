"""Unit tests for the PaperSummarizer class."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import httpx
from paper_summarizer.core.summarizer import PaperSummarizer, ModelType, ModelProvider
from tests.config import TEST_DATA

class TestPaperSummarizer:
    """Test cases for PaperSummarizer class."""

    @pytest.fixture
    def summarizer(self):
        """Create a test summarizer instance."""
        try:
            __import__("torch")
        except Exception:
            pytest.skip("torch is not available on this platform")
        return PaperSummarizer(model_type=ModelType.T5_SMALL, provider=ModelProvider.LOCAL)

    def test_initialization(self, summarizer):
        """Test summarizer initialization."""
        assert summarizer.model_type == ModelType.T5_SMALL
        assert summarizer.provider == ModelProvider.LOCAL

    def test_summarize_with_local_model(self, summarizer):
        """Test summarization with local model."""
        with patch.object(summarizer, '_summarize_local', return_value=TEST_DATA['sample_summary'].strip()):
            text = TEST_DATA['sample_text']
            summary = summarizer.summarize(text, num_sentences=3)
            assert summary == TEST_DATA['sample_summary'].strip()

    def test_summarize_with_together_ai(self):
        """Test summarization with Together AI."""
        os.environ['TESTING'] = 'true'
        os.environ['TOGETHER_API_KEY'] = 'test_key'

        with patch('together.Complete.create') as mock_create:
            mock_create.return_value = {
                'output': {
                    'choices': [{
                        'text': TEST_DATA['sample_summary'].strip()
                    }]
                }
            }

            summarizer = PaperSummarizer(
                model_type=ModelType.DEEPSEEK_R1,
                provider=ModelProvider.TOGETHER_AI
            )

            text = TEST_DATA['sample_text']
            with patch.object(summarizer, '_summarize_together_ai', return_value=TEST_DATA['sample_summary'].strip()):
                summary = summarizer.summarize(text, num_sentences=3)
                assert summary == TEST_DATA['sample_summary'].strip()

    def test_summarize_from_url(self, summarizer):
        """Test summarization from URL."""
        with patch('httpx.Client') as mock_client_cls:
            mock_response = MagicMock()
            mock_response.text = TEST_DATA['sample_text']
            mock_response.raise_for_status = MagicMock()
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_ctx.get.return_value = mock_response
            mock_client_cls.return_value = mock_ctx

            with patch.object(summarizer, '_summarize_local', return_value=TEST_DATA['sample_summary'].strip()):
                summary = summarizer.summarize_from_url(TEST_DATA['sample_url'])
                assert summary == TEST_DATA['sample_summary'].strip()

    def test_summarize_from_file(self, summarizer):
        """Test summarization from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(TEST_DATA['sample_text'])
            file_path = Path(f.name)

        try:
            with patch.object(summarizer, '_summarize_local', return_value=TEST_DATA['sample_summary'].strip()):
                summary = summarizer.summarize_from_file(str(file_path))
                assert summary == TEST_DATA['sample_summary'].strip()
        finally:
            if file_path.exists():
                file_path.unlink()

    def test_citation_handling(self, summarizer):
        """Test citation handling."""
        text_with_citations = TEST_DATA['text_with_citations']
        text_without_citations = TEST_DATA['text_without_citations']

        # Test citation removal
        processed_text = summarizer._remove_citations(text_with_citations)
        print("\nExpected:", repr(text_without_citations))
        print("Got:", repr(processed_text))
        assert ' '.join(processed_text.split()) == ' '.join(text_without_citations.split())

        # Test summarization with citations
        with patch.object(summarizer, '_summarize_local', return_value=TEST_DATA['sample_summary']):
            # Keep citations
            summary = summarizer.summarize(text_with_citations, keep_citations=True)
            assert summary == TEST_DATA['sample_summary']

            # Remove citations
            summary = summarizer.summarize(text_with_citations, keep_citations=False)
            assert summary == TEST_DATA['sample_summary']

    def test_file_format_handling(self, summarizer):
        """Test handling of different file formats."""
        # Test with unsupported format
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as temp_file:
            temp_file.write(b'test content')
            temp_file.flush()
            file_path = temp_file.name

        try:
            with pytest.raises(ValueError):
                summarizer.summarize_from_file(file_path)
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)

    def test_batch_processing(self, summarizer):
        """Test batch processing capability."""
        files = []
        try:
            # Create multiple test files
            for i in range(3):
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(TEST_DATA['sample_text'])
                    files.append(Path(f.name))

            with patch.object(summarizer, '_summarize_local', return_value=TEST_DATA['sample_summary'].strip()):
                summaries = []
                for file in files:
                    summary = summarizer.summarize_from_file(str(file))
                    summaries.append(summary)

                assert len(summaries) == len(files)
                assert all(s == TEST_DATA['sample_summary'].strip() for s in summaries)
        finally:
            for file in files:
                if file.exists():
                    file.unlink()

    def test_error_handling(self, summarizer):
        """Test error handling."""
        # Test with invalid URL
        with patch('httpx.Client') as mock_client_cls:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_ctx.get.side_effect = httpx.ConnectError('Failed to fetch URL')
            mock_client_cls.return_value = mock_ctx
            with pytest.raises(ValueError, match='Connection failed for URL'):
                summarizer.summarize_from_url('https://invalid-url.com')

        # Test with invalid file path
        with pytest.raises(FileNotFoundError, match='File not found'):
            summarizer.summarize_from_file('nonexistent_file.txt')

        # Test with invalid file format
        with tempfile.NamedTemporaryFile(suffix='.xyz') as temp_file:
            with pytest.raises(ValueError, match='Unsupported file format'):
                summarizer.summarize_from_file(temp_file.name)

        # Test with empty text
        with pytest.raises(ValueError, match='Input text is empty'):
            summarizer.summarize('')

    def test_model_configuration(self):
        """Test model configuration."""
        # Test with missing API key
        os.environ.pop('TOGETHER_API_KEY', None)
        os.environ.pop('TESTING', None)

        with pytest.raises(ValueError):
            PaperSummarizer(
                model_type=ModelType.DEEPSEEK_R1,
                provider=ModelProvider.TOGETHER_AI
            )
