"""Configuration settings for the Paper Summarizer application."""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Set
from pathlib import Path

@dataclass
class Config:
    """Application configuration."""
    
    # Flask settings
    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'dev-key-please-change-in-production')
    DEBUG: bool = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # File upload settings
    UPLOAD_FOLDER: Path = field(default_factory=lambda: Path("uploads"))
    MAX_CONTENT_LENGTH: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: Set[str] = field(default_factory=lambda: {'txt', 'pdf', 'docx'})
    
    # Summarizer settings
    DEFAULT_SUMMARY_LENGTH: int = 5
    MAX_SUMMARY_LENGTH: int = 20
    MIN_SUMMARY_LENGTH: int = 1
    KEEP_CITATIONS: bool = False
    
    # History settings
    HISTORY_FILE: Path = field(default_factory=lambda: Path("summary_history.json"))
    MAX_HISTORY_ENTRIES: int = 100
    
    # Cache settings
    CACHE_TYPE: str = "SimpleCache"
    CACHE_DEFAULT_TIMEOUT: int = 300
    
    def __post_init__(self):
        """Create necessary directories after initialization."""
        self.UPLOAD_FOLDER.mkdir(exist_ok=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

# Create default config instance
config = Config()
