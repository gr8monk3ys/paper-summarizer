"""Test configuration and sample data."""

import os
import tempfile
from pathlib import Path

# Test environment configuration
TEST_CONFIG = {
    'TESTING': True,
    'DEBUG': True,
    'UPLOAD_FOLDER': 'tests/uploads',
    'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,  # 16MB max file size
    'ALLOWED_EXTENSIONS': {'txt', 'pdf', 'md', 'rst'},
    'DEFAULT_MODEL': 't5-small',
    'DEFAULT_PROVIDER': 'local',
    'DEFAULT_NUM_SENTENCES': 5,
    'MIN_SENTENCES': 1,
    'MAX_SENTENCES': 10,
    'RATE_LIMIT_ENABLED': False,
    'LOCAL_MODELS_ENABLED': True
}

# Sample test data
TEST_DATA = {
    'sample_url': 'https://example.com/paper.pdf',
    'sample_text': 'This is a sample academic paper about machine learning.',
    'sample_summary': 'This is a test summary of the academic paper.\nIt contains the key points and maintains academic integrity.\nThe summary preserves important information while being concise.',
    'text_with_citations': 'Recent studies [1] have shown significant progress in this field. Smith et al. (2020) demonstrated the effectiveness of this approach. Further research (Johnson, 2019) supported these results.',
    'text_without_citations': 'Recent studies have shown significant progress in this field. demonstrated the effectiveness of this approach. Further research supported these results.'
}

# Mock API responses
MOCK_RESPONSES = {
    'together_ai': {
        'success': {
            'output': {
                'choices': [{
                    'text': TEST_DATA['sample_summary']
                }]
            }
        },
        'error': {
            'error': {
                'message': 'Invalid API key'
            }
        }
    }
}

# Model configuration for tests
MODEL_CONFIG = {
    'together_ai': {
        'api_key': 'test_key',
        'models': [
            {
                'id': 'deepseek-r1',
                'name': 'DeepSeek R1',
                'description': 'High-quality model for testing'
            }
        ]
    },
    'local': {
        'models': [
            {
                'id': 't5-small',
                'name': 'T5 Small',
                'description': 'Fast local model for testing'
            }
        ]
    }
}

# Clean up temporary directory on exit
def cleanup():
    """Clean up temporary test files."""
    # Clean up test files
    test_files_dir = Path('tests/uploads')
    if test_files_dir.exists():
        for file in test_files_dir.glob('*'):
            try:
                file.unlink()
            except Exception:
                pass
        try:
            test_files_dir.rmdir()
        except Exception:
            pass

import atexit
atexit.register(cleanup)
