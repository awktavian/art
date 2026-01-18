"""Tests for kagami/tools/web/fetcher.py - Safe HTTP fetcher."""

from __future__ import annotations

import hashlib
from unittest.mock import Mock, patch

import pytest
import requests


class TestFetchResult:
    """Tests for FetchResult dataclass."""

    def test_fetch_result_creation(self) -> None:
        """Test FetchResult dataclass instantiation."""
        from kagami.tools.web.fetcher import FetchResult

        result = FetchResult(
            url="https://example.com",
            status=200,
            content_type="text/html",
            text="Hello World",
            sha256="abc123",
            fetch_time_ms=100.0,
        )

        assert result.url == "https://example.com"
        assert result.status == 200
        assert result.content_type == "text/html"
        assert result.text == "Hello World"
        assert result.sha256 == "abc123"
        assert result.fetch_time_ms == 100.0


class TestExtractText:
    """Tests for _extract_text helper."""

    def test_extract_text_returns_content_when_no_trafilatura(self) -> None:
        """Test fallback when trafilatura not available."""
        from kagami.tools.web.fetcher import _extract_text

        html = "<html><body>Test content</body></html>"
        result = _extract_text(html)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_extract_text_handles_empty_string(self) -> None:
        """Test handling of empty string."""
        from kagami.tools.web.fetcher import _extract_text

        result = _extract_text("")
        assert result == ""


class TestFetch:
    """Tests for fetch() function."""

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_success(self, mock_get: Mock) -> None:
        """Test successful fetch with mocked response."""
        from kagami.tools.web.fetcher import fetch

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_response.raw = Mock()
        mock_response.raw.read = Mock(return_value=b"<html>Hello</html>")
        mock_response.close = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetch("https://example.com")

        assert result.url == "https://example.com"
        assert result.status == 200
        assert result.content_type == "text/html; charset=utf-8"
        assert result.fetch_time_ms >= 0
        assert len(result.sha256) == 64  # SHA256 hex length

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_respects_timeout(self, mock_get: Mock) -> None:
        """Test that timeout parameter is passed to requests."""
        from kagami.tools.web.fetcher import fetch

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_response.raw = Mock()
        mock_response.raw.read = Mock(return_value=b"content")
        mock_response.close = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetch("https://example.com", timeout=5.0)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == 5.0

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_custom_user_agent(self, mock_get: Mock) -> None:
        """Test that custom UA is passed to requests."""
        from kagami.tools.web.fetcher import fetch

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_response.raw = Mock()
        mock_response.raw.read = Mock(return_value=b"content")
        mock_response.close = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetch("https://example.com", ua="CustomBot/1.0")

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["headers"]["User-Agent"] == "CustomBot/1.0"

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_computes_sha256(self, mock_get: Mock) -> None:
        """Test that SHA256 hash is computed correctly."""
        from kagami.tools.web.fetcher import fetch

        content = b"test content for hashing"
        expected_hash = hashlib.sha256(content).hexdigest()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_response.raw = Mock()
        mock_response.raw.read = Mock(return_value=content)
        mock_response.close = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetch("https://example.com")

        assert result.sha256 == expected_hash

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_follows_redirects(self, mock_get: Mock) -> None:
        """Test that final URL after redirects is captured."""
        from kagami.tools.web.fetcher import fetch

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/final"  # Redirected URL
        mock_response.headers = {}
        mock_response.raw = Mock()
        mock_response.raw.read = Mock(return_value=b"content")
        mock_response.close = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetch("https://example.com/redirect")

        assert result.url == "https://example.com/final"

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_max_bytes_limit_enforced(self, mock_get: Mock) -> None:
        """Test that MAX_BYTES limit is enforced during fetch."""
        from kagami.tools.web.fetcher import fetch, MAX_BYTES

        # Create content larger than MAX_BYTES
        large_content = b"x" * (MAX_BYTES + 1000)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.raw = Mock()
        mock_response.raw.read = Mock(return_value=large_content[:MAX_BYTES])
        mock_response.close = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetch("https://example.com")

        # Verify MAX_BYTES was passed to read()
        mock_response.raw.read.assert_called_once_with(MAX_BYTES, decode_content=True)
        assert len(result.text) <= MAX_BYTES

    @pytest.mark.parametrize(
        "status_code,exception_type",
        [
            (404, requests.HTTPError),
            (403, requests.HTTPError),
            (500, requests.HTTPError),
            (502, requests.HTTPError),
            (503, requests.HTTPError),
        ],
    )
    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_http_error_codes(
        self, mock_get: Mock, status_code: int, exception_type: type[Exception]
    ) -> None:
        """Test that various HTTP error codes are handled correctly."""
        from kagami.tools.web.fetcher import fetch

        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.raise_for_status = Mock(side_effect=exception_type(f"{status_code} Error"))
        mock_get.return_value = mock_response

        with pytest.raises(exception_type):
            fetch("https://example.com/error")

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_timeout_error(self, mock_get: Mock) -> None:
        """Test that timeout errors are propagated."""
        from kagami.tools.web.fetcher import fetch

        mock_get.side_effect = requests.Timeout("Request timeout")

        with pytest.raises(requests.Timeout):
            fetch("https://example.com/slow")

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_connection_error(self, mock_get: Mock) -> None:
        """Test that connection errors are propagated."""
        from kagami.tools.web.fetcher import fetch

        mock_get.side_effect = requests.ConnectionError("Connection failed")

        with pytest.raises(requests.ConnectionError):
            fetch("https://unreachable.example.com")

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_handles_missing_content_type(self, mock_get: Mock) -> None:
        """Test handling of responses without Content-Type header."""
        from kagami.tools.web.fetcher import fetch

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {}  # No Content-Type
        mock_response.raw = Mock()
        mock_response.raw.read = Mock(return_value=b"content")
        mock_response.close = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetch("https://example.com")

        assert result.content_type == ""
        assert result.status == 200

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_stream_mode_enabled(self, mock_get: Mock) -> None:
        """Test that streaming mode is enabled in requests."""
        from kagami.tools.web.fetcher import fetch

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_response.raw = Mock()
        mock_response.raw.read = Mock(return_value=b"content")
        mock_response.close = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetch("https://example.com")

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["stream"] is True
        assert call_kwargs["allow_redirects"] is True

    @patch("kagami.tools.web.fetcher.requests.get")
    def test_fetch_response_closed_after_read(self, mock_get: Mock) -> None:
        """Test that response is properly closed after reading."""
        from kagami.tools.web.fetcher import fetch

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com"
        mock_response.headers = {}
        mock_response.raw = Mock()
        mock_response.raw.read = Mock(return_value=b"content")
        mock_response.close = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetch("https://example.com")

        mock_response.close.assert_called_once()


class TestConstants:
    """Tests for module constants."""

    def test_max_bytes_limit(self) -> None:
        """Test MAX_BYTES is set to 2MB."""
        from kagami.tools.web.fetcher import MAX_BYTES

        assert MAX_BYTES == 2_000_000

    def test_default_timeout(self) -> None:
        """Test DEFAULT_TIMEOUT is reasonable."""
        from kagami.tools.web.fetcher import DEFAULT_TIMEOUT

        assert DEFAULT_TIMEOUT == 15.0

    def test_default_user_agent(self) -> None:
        """Test DEFAULT_UA contains ResearchBot."""
        from kagami.tools.web.fetcher import DEFAULT_UA

        assert "ResearchBot" in DEFAULT_UA
        assert "K os-ResearchBot" in DEFAULT_UA
