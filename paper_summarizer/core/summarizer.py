"""Core summarizer module for the Paper Summarizer application."""

import os
import re
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
                summary = self._summarize_local(text, num_sentences)
            else:
                summary = self._summarize_together_ai(text, num_sentences)

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
                response = client.get(url, follow_redirects=True)
                response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if isinstance(content_type, str) and "pdf" in content_type:
                return self._summarize_pdf_bytes(response.content, num_sentences)

            text = self._extract_text_from_html(response.text)
            if not text or len(text.strip()) < 100:
                text = response.text

            return self.summarize(text, num_sentences)
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

            if path.suffix.lower() == '.pdf':
                text = self._extract_text_from_pdf(file_path)
            elif path.suffix.lower() in ['.txt', '.md', '.rst']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")

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

    _INJECTION_PATTERNS = re.compile(
        r"(###|---|System:|Assistant:|Human:|IGNORE PREVIOUS INSTRUCTIONS)",
        re.IGNORECASE,
    )
    _MAX_INPUT_LENGTH = 100_000

    def _sanitize_input(self, text: str) -> str:
        """Strip prompt-injection-style delimiters and enforce length limits.

        Args:
            text: Raw user-supplied text.

        Returns:
            Cleaned text safe for interpolation into LLM prompts.
        """
        if len(text) > self._MAX_INPUT_LENGTH:
            self.logger.warning(
                "Input text length (%d) exceeds maximum (%d); truncating.",
                len(text),
                self._MAX_INPUT_LENGTH,
            )
            text = text[: self._MAX_INPUT_LENGTH]

        text = self._INJECTION_PATTERNS.sub("", text)
        return text

    def _summarize_local(self, text: str, num_sentences: int = 5) -> str:
        """Summarize text using local model.

        Args:
            text: Text to summarize
            num_sentences: Number of sentences in the summary

        Returns:
            Summarized text

        Raises:
            ValueError: If summarization fails
        """
        text = self._sanitize_input(text)
        try:
            max_length = min(num_sentences * 40, 512)
            min_length = min(num_sentences * 15, max_length - 10)
            result = self.model(text, max_length=max_length, min_length=min_length, do_sample=False)
            return result[0]['summary_text']
        except (RuntimeError, IndexError, TypeError) as e:
            raise ValueError(f"Local summarization failed: {str(e)}")

    def _summarize_together_ai(self, text: str, num_sentences: int = 5) -> str:
        """Summarize text using Together AI.

        Args:
            text: Text to summarize
            num_sentences: Number of sentences in the summary

        Returns:
            Summarized text

        Raises:
            ValueError: If summarization fails
        """
        text = self._sanitize_input(text)
        try:
            prompt = (
                "You are an expert academic research assistant. "
                "Summarize the following research text in exactly "
                f"{num_sentences} sentences. Focus on:\n"
                "1. The main research question or objective\n"
                "2. The methodology used\n"
                "3. Key findings and results\n"
                "4. Implications and conclusions\n\n"
                "Be precise, use academic language, and preserve "
                "important numerical results or statistical findings.\n\n"
                f"Text:\n{text}\n\n"
                "Summary:"
            )
            response = together.Complete.create(
                prompt=prompt,
                model=self.model_type.value,
                max_tokens=1024,
                temperature=0.2,
                stop=["\n\n"],
            )
            return response['output']['choices'][0]['text'].strip()
        except httpx.HTTPError as e:
            raise ValueError(f"Together AI summarization failed: {str(e)}")
        except (RuntimeError, KeyError, TypeError, IndexError) as e:
            raise ValueError(f"Together AI summarization failed: {str(e)}")

    def _extract_text_from_html(self, html: str) -> str:
        """Extract article text from HTML, stripping navigation and boilerplate."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Remove non-content elements
        for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        # Try to find article/main content first
        article = soup.find("article") or soup.find("main") or soup.find(role="main")
        if article:
            return article.get_text(separator="\n", strip=True)

        # Fallback: get all paragraph text
        paragraphs = soup.find_all("p")
        if paragraphs:
            return "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)

        return soup.get_text(separator="\n", strip=True)

    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text content from a PDF file."""
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)

        if not pages:
            raise ValueError("Could not extract text from PDF")

        return "\n\n".join(pages)

    def _summarize_pdf_bytes(self, pdf_bytes: bytes, num_sentences: int = 5) -> str:
        """Summarize a PDF from raw bytes (e.g. fetched from URL)."""
        from io import BytesIO
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)

        if not pages:
            raise ValueError("Could not extract text from PDF")

        return self.summarize("\n\n".join(pages), num_sentences)

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
