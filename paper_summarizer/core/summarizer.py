"""Core summarizer module for the Paper Summarizer application."""

import os
import logging
import httpx
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

import together

class ModelType(Enum):
    """Available model types."""
    T5_SMALL = 't5-small'
    DEEPSEEK_R1 = 'deepseek-r1'

class ModelProvider(Enum):
    """Available model providers."""
    LOCAL = 'local'
    TOGETHER_AI = 'together_ai'

class PaperSummarizer:
    """Paper summarizer class."""

    def __init__(self, model_type: ModelType = ModelType.T5_SMALL, provider: ModelProvider = ModelProvider.LOCAL):
        """Initialize the summarizer.
        
        Args:
            model_type: Type of model to use for summarization
            provider: Provider of the model (local or Together AI)
        """
        self.model_type = model_type
        self.provider = provider
        self.logger = logging.getLogger(__name__)
        
        # Set up API key for Together AI if needed
        if provider == ModelProvider.TOGETHER_AI:
            api_key = os.getenv('TOGETHER_API_KEY')
            if not api_key and not os.getenv('TESTING'):
                raise ValueError("Together AI API key not found. Please set TOGETHER_API_KEY environment variable.")
            together.api_key = api_key

        # Initialize local model if using local provider
        if provider == ModelProvider.LOCAL:
            try:
                from transformers import pipeline
                self.model = pipeline('summarization', model=model_type.value)
            except ImportError as e:
                self.logger.error(f"Failed to initialize local model: {str(e)}")
                raise ValueError(f"Failed to initialize local model: {str(e)}")
            except (OSError, RuntimeError) as e:
                self.logger.error(f"Failed to initialize local model: {str(e)}")
                raise ValueError(f"Failed to initialize local model: {str(e)}")

    def summarize(self, text: str, num_sentences: int = 5, keep_citations: bool = True) -> str:
        """Summarize the given text.
        
        Args:
            text: Text to summarize
            num_sentences: Number of sentences in the summary
            keep_citations: Whether to keep citations in the summary
            
        Returns:
            Summarized text
            
        Raises:
            ValueError: If text is empty or summarization fails
        """
        if not text or not text.strip():
            raise ValueError("Input text is empty")

        try:
            # Remove citations if requested
            if not keep_citations:
                text = self._remove_citations(text)

            # Use appropriate provider
            if self.provider == ModelProvider.LOCAL:
                summary = self._summarize_local(text)
            else:
                summary = self._summarize_together_ai(text)

            if not summary:
                raise ValueError("Failed to generate summary")

            return summary.strip()

        except ValueError:
            raise
        except RuntimeError as e:
            self.logger.error(f"Failed to summarize text: {str(e)}")
            raise ValueError(f"Failed to summarize text: {str(e)}")

    def summarize_from_url(self, url: str, num_sentences: int = 5) -> str:
        """Summarize text from a URL.
        
        Args:
            url: URL to fetch text from
            num_sentences: Number of sentences in the summary
            
        Returns:
            Summarized text
            
        Raises:
            ValueError: If URL is invalid or content cannot be fetched
        """
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url)
                response.raise_for_status()
            return self.summarize(response.text, num_sentences)
        except httpx.TimeoutException as e:
            self.logger.error(f"Request timed out for URL {url}: {str(e)}")
            raise ValueError(f"Request timed out for URL {url}: {str(e)}")
        except httpx.ConnectError as e:
            self.logger.error(f"Connection failed for URL {url}: {str(e)}")
            raise ValueError(f"Connection failed for URL {url}: {str(e)}")
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Failed to fetch content from URL {url}: {str(e)}")
            raise ValueError(f"Failed to fetch content from URL {url}: {str(e)}")
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to fetch content from URL {url}: {str(e)}")
            raise ValueError(f"Failed to fetch content from URL {url}: {str(e)}")
        except ValueError:
            raise

    def summarize_from_file(self, file_path: str, num_sentences: int = 5, keep_citations: bool = True) -> str:
        """Summarize text from a file.
        
        Args:
            file_path: Path to the file
            num_sentences: Number of sentences in the summary
            keep_citations: Whether to keep citations in the summary
            
        Returns:
            Summarized text
            
        Raises:
            ValueError: If file format is unsupported or file cannot be read
            FileNotFoundError: If file does not exist
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
                
            if path.suffix.lower() not in ['.txt', '.md', '.rst']:
                raise ValueError(f"Unsupported file format: {path.suffix}")
                
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
                
            return self.summarize(text, num_sentences, keep_citations)
            
        except FileNotFoundError:
            self.logger.error(f"File not found: {file_path}")
            raise
        except ValueError as e:
            self.logger.error(f"Failed to read or summarize file {file_path}: {str(e)}")
            raise
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to read or summarize file {file_path}: {str(e)}")
            raise ValueError(f"Failed to read or summarize file {file_path}: {str(e)}")

    def _summarize_local(self, text: str) -> str:
        """Summarize text using local model.
        
        Args:
            text: Text to summarize
            
        Returns:
            Summarized text
            
        Raises:
            ValueError: If summarization fails
        """
        try:
            result = self.model(text, max_length=150, min_length=50, do_sample=False)
            return result[0]['summary_text']
        except (RuntimeError, IndexError, TypeError) as e:
            raise ValueError(f"Local summarization failed: {str(e)}")

    def _summarize_together_ai(self, text: str) -> str:
        """Summarize text using Together AI.
        
        Args:
            text: Text to summarize
            
        Returns:
            Summarized text
            
        Raises:
            ValueError: If summarization fails
        """
        try:
            prompt = f"Please summarize the following text:\n\n{text}\n\nSummary:"
            response = together.Complete.create(
                prompt=prompt,
                model=self.model_type.value,
                max_tokens=150,
                temperature=0.3
            )
            return response['output']['choices'][0]['text'].strip()
        except httpx.HTTPError as e:
            raise ValueError(f"Together AI summarization failed: {str(e)}")
        except (RuntimeError, KeyError, TypeError, IndexError) as e:
            raise ValueError(f"Together AI summarization failed: {str(e)}")

    def _remove_citations(self, text: str) -> str:
        """Remove citations from text.
        
        Args:
            text: Text to remove citations from
            
        Returns:
            Text with citations removed
        """
        import re
        # Remove citations in brackets [1] or [1,2,3]
        text = re.sub(r'\[[0-9,\s]+\]', '', text)
        # Remove citations in parentheses (Author, Year)
        text = re.sub(r'\([A-Za-z\s]+,\s*\d{4}\)', '', text)
        # Remove citations in parentheses (Author et al., Year)
        text = re.sub(r'\([A-Za-z\s]+et al\.,\s*\d{4}\)', '', text)
        # Remove author names at start of sentence
        text = re.sub(r'[A-Za-z\s]+et al\.\s+', '', text)
        text = re.sub(r'[A-Za-z\s]+\(\d{4}\)\s+', '', text)
        # Clean up extra whitespace
        text = ' '.join(text.split())
        return text

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models.
        
        Returns:
            List of available models with their details
        """
        models = []
        for model_type in ModelType:
            for provider in ModelProvider:
                models.append({
                    'name': model_type.value,
                    'provider': provider.value,
                    'description': f"{model_type.value} model from {provider.value}"
                })
        return models
