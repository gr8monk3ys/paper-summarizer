"""Application configuration."""

import os
from pathlib import Path

class Config:
    """Base configuration."""
    
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'md', 'rst'}
    
    # API configuration
    TOGETHER_API_KEY = os.environ.get('TOGETHER_API_KEY')
    
    # Model configuration
    DEFAULT_MODEL = 't5-small'
    DEFAULT_PROVIDER = 'local'
    DEFAULT_NUM_SENTENCES = 5
    MIN_SENTENCES = 1
    MAX_SENTENCES = 20
    
    # Create upload folder if it doesn't exist
    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

class TestConfig(Config):
    """Test configuration."""
    TESTING = True
    DEBUG = False
    # Use temporary directory for uploads in tests
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'test_uploads')
    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    DEVELOPMENT = True

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestConfig,
    'default': DevelopmentConfig
}
