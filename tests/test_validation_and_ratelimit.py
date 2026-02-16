"""Tests for validation helpers and rate limiter modules."""

from __future__ import annotations

import socket
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from paper_summarizer.web.ratelimit import (
    InMemoryBackend,
    RateLimiter,
    RateLimitConfig,
    RedisBackend,
)
from paper_summarizer.web.validation import validate_upload, validate_url


# ---------------------------------------------------------------------------
# validate_upload tests
# ---------------------------------------------------------------------------

class TestValidateUpload:
    """Tests for the validate_upload function."""

    def _settings(self, max_size: int = 10_000) -> dict:
        return {"MAX_CONTENT_LENGTH": max_size}

    def test_valid_text_file(self):
        contents = b"Hello, this is a plain text file."
        validate_upload(contents, "notes.txt", self._settings())

    def test_valid_pdf(self):
        contents = b"%PDF-1.4 fake pdf body"
        validate_upload(contents, "paper.pdf", self._settings())

    def test_file_too_large(self):
        contents = b"x" * 10_001
        with pytest.raises(HTTPException) as exc_info:
            validate_upload(contents, "big.txt", self._settings(max_size=10_000))
        assert exc_info.value.status_code == 413
        assert "File too large" in exc_info.value.detail

    def test_invalid_pdf_magic_bytes(self):
        contents = b"Not a real PDF file"
        with pytest.raises(HTTPException) as exc_info:
            validate_upload(contents, "fake.pdf", self._settings())
        assert exc_info.value.status_code == 400
        assert "Invalid PDF upload" in exc_info.value.detail

    def test_non_utf8_text_file(self):
        # Invalid UTF-8 byte sequence
        contents = b"\x80\x81\x82\x83"
        with pytest.raises(HTTPException) as exc_info:
            validate_upload(contents, "data.txt", self._settings())
        assert exc_info.value.status_code == 400
        assert "UTF-8" in exc_info.value.detail


# ---------------------------------------------------------------------------
# validate_url tests
# ---------------------------------------------------------------------------

def _public_addrinfo(host: str = "93.184.216.34", port: int = 443):
    """Return a fake getaddrinfo result pointing to a public IP."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port))]


class TestValidateUrl:
    """Tests for the validate_url function."""

    @patch("paper_summarizer.web.validation.socket.getaddrinfo", return_value=_public_addrinfo())
    def test_valid_https_url(self, mock_gai):
        validate_url("https://example.com/paper.pdf")
        mock_gai.assert_called_once()

    def test_ftp_scheme_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("ftp://example.com/file")
        assert exc_info.value.status_code == 400
        assert "scheme" in exc_info.value.detail

    def test_no_hostname_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("https://")
        assert exc_info.value.status_code == 400
        assert "host" in exc_info.value.detail.lower()

    def test_credentials_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("https://user:pass@example.com/")
        assert exc_info.value.status_code == 400
        assert "credentials" in exc_info.value.detail.lower()

    def test_localhost_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("https://localhost/secret")
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail.lower()

    def test_dotlocal_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("https://myhost.local/path")
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail.lower()

    @patch(
        "paper_summarizer.web.validation.socket.getaddrinfo",
        side_effect=socket.gaierror("Name or service not known"),
    )
    def test_unresolvable_host(self, mock_gai):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("https://nonexistent.example.invalid/")
        assert exc_info.value.status_code == 400
        assert "could not be resolved" in exc_info.value.detail

    @patch(
        "paper_summarizer.web.validation.socket.getaddrinfo",
        return_value=_public_addrinfo(host="192.168.1.1"),
    )
    def test_private_ip_rejected(self, mock_gai):
        with pytest.raises(HTTPException) as exc_info:
            validate_url("https://example.com/")
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# InMemoryBackend tests
# ---------------------------------------------------------------------------

class TestInMemoryBackend:
    """Tests for the InMemoryBackend rate limiter."""

    def test_allows_requests_within_limit(self):
        backend = InMemoryBackend()
        for _ in range(5):
            assert backend.allow("client1", max_requests=5, window_seconds=60) is True

    def test_blocks_when_limit_exceeded(self):
        backend = InMemoryBackend()
        for _ in range(3):
            backend.allow("client1", max_requests=3, window_seconds=60)
        assert backend.allow("client1", max_requests=3, window_seconds=60) is False

    def test_window_expiry(self):
        backend = InMemoryBackend()
        # Fill up the bucket
        for _ in range(2):
            assert backend.allow("client1", max_requests=2, window_seconds=1) is True
        assert backend.allow("client1", max_requests=2, window_seconds=1) is False

        # Patch time.monotonic to simulate passage of time beyond the window
        original_monotonic = time.monotonic
        offset = 0.0

        def patched_monotonic():
            return original_monotonic() + offset

        with patch("paper_summarizer.web.ratelimit.time.monotonic", side_effect=patched_monotonic):
            offset = 2.0  # Jump forward 2 seconds (past the 1-second window)
            assert backend.allow("client1", max_requests=2, window_seconds=1) is True

    def test_separate_keys_are_independent(self):
        backend = InMemoryBackend()
        assert backend.allow("a", max_requests=1, window_seconds=60) is True
        assert backend.allow("a", max_requests=1, window_seconds=60) is False
        # Different key should still be allowed
        assert backend.allow("b", max_requests=1, window_seconds=60) is True


# ---------------------------------------------------------------------------
# RedisBackend tests (mocked)
# ---------------------------------------------------------------------------

class TestRedisBackend:
    """Tests for the RedisBackend with mocked Redis."""

    def test_fails_open_when_import_fails(self):
        backend = RedisBackend("redis://localhost:6379")
        with patch.dict("sys.modules", {"redis": None}):
            with patch.object(backend, "_get_client", return_value=None):
                assert backend.allow("key", 5, 60) is True

    def test_fails_open_when_connection_fails(self):
        backend = RedisBackend("redis://localhost:6379")
        # _get_client returns None when connection fails
        with patch.object(backend, "_get_client", return_value=None):
            assert backend.allow("key", 5, 60) is True

    def test_allows_when_under_limit(self):
        backend = RedisBackend("redis://localhost:6379")
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        # results[1] is zcard result: current_count = 2, max_requests = 5 -> allowed
        mock_pipe.execute.return_value = [None, 2, None, None]

        with patch.object(backend, "_get_client", return_value=mock_client):
            assert backend.allow("key", 5, 60) is True

    def test_blocks_when_over_limit(self):
        backend = RedisBackend("redis://localhost:6379")
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        # results[1] is zcard result: current_count = 5, max_requests = 5 -> blocked
        mock_pipe.execute.return_value = [None, 5, None, None]

        with patch.object(backend, "_get_client", return_value=mock_client):
            assert backend.allow("key", 5, 60) is False

    def test_fails_open_on_pipeline_exception(self):
        backend = RedisBackend("redis://localhost:6379")
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        mock_pipe.execute.side_effect = Exception("Redis pipeline error")

        with patch.object(backend, "_get_client", return_value=mock_client):
            assert backend.allow("key", 5, 60) is True


# ---------------------------------------------------------------------------
# RateLimiter tests
# ---------------------------------------------------------------------------

class TestRateLimiter:
    """Tests for the RateLimiter wrapper."""

    def test_allow_within_limit_no_redis(self):
        config = RateLimitConfig(requests=3, window_seconds=60)
        limiter = RateLimiter(config)
        assert limiter.allow("client1") is True
        assert limiter.allow("client1") is True
        assert limiter.allow("client1") is True

    def test_block_when_exceeded_no_redis(self):
        config = RateLimitConfig(requests=2, window_seconds=60)
        limiter = RateLimiter(config)
        assert limiter.allow("client1") is True
        assert limiter.allow("client1") is True
        assert limiter.allow("client1") is False

    def test_disabled_always_allows(self):
        config = RateLimitConfig(requests=1, window_seconds=60, enabled=False)
        limiter = RateLimiter(config)
        # Should always return True regardless of how many requests
        for _ in range(10):
            assert limiter.allow("client1") is True

    def test_uses_redis_backend_when_url_provided(self):
        config = RateLimitConfig(requests=5, window_seconds=60)
        limiter = RateLimiter(config, redis_url="redis://localhost:6379")
        assert isinstance(limiter._backend, RedisBackend)
        assert isinstance(limiter._fallback, InMemoryBackend)

    def test_uses_inmemory_backend_when_no_url(self):
        config = RateLimitConfig(requests=5, window_seconds=60)
        limiter = RateLimiter(config)
        assert isinstance(limiter._backend, InMemoryBackend)
        assert limiter._fallback is None
