"""Tests for response caching middleware.

Covers:
- ETag generation
- Cache-Control headers
- Conditional GET (If-None-Match)
- Path-based caching rules
- Never-cache paths
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.tier_unit

from kagami_api.response_cache import (
    CACHEABLE_PREFIXES,
    NEVER_CACHE_PATHS,
    response_cache_middleware,
)


class TestCachePathConfiguration:
    """Test cache path configuration."""

    def test_never_cache_paths_includes_health(self) -> None:
        """Health endpoints should never be cached."""
        assert "/health" in NEVER_CACHE_PATHS
        assert "/health/live" in NEVER_CACHE_PATHS
        assert "/health/ready" in NEVER_CACHE_PATHS

    def test_never_cache_paths_includes_metrics(self) -> None:
        """Metrics endpoint should never be cached."""
        assert "/metrics" in NEVER_CACHE_PATHS

    def test_cacheable_prefixes_includes_static(self) -> None:
        """Static asset paths should be cacheable."""
        assert "/api/static/" in CACHEABLE_PREFIXES
        assert "/api/assets/" in CACHEABLE_PREFIXES

    def test_cacheable_prefixes_includes_openapi(self) -> None:
        """OpenAPI spec should be cacheable."""
        assert "/openapi.json" in CACHEABLE_PREFIXES


class TestResponseCacheMiddleware:
    """Test response_cache_middleware function."""

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock response with body."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.body = b'{"data": "test"}'
        return response

    @pytest.mark.asyncio
    async def test_non_get_requests_pass_through(self) -> None:
        """Non-GET requests should pass through without caching."""
        request = MagicMock()
        request.method = "POST"

        response = MagicMock()
        call_next = AsyncMock(return_value=response)

        result = await response_cache_middleware(request, call_next)

        assert result == response
        assert "Cache-Control" not in response.headers

    @pytest.mark.asyncio
    async def test_health_endpoint_no_store(self) -> None:
        """Health endpoints should have no-store cache control."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/health"

        response = MagicMock()
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        result = await response_cache_middleware(request, call_next)

        assert result.headers["Cache-Control"] == "no-store"

    @pytest.mark.asyncio
    async def test_metrics_endpoint_no_store(self) -> None:
        """Metrics endpoint should have no-store cache control."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/metrics"

        response = MagicMock()
        response.headers = {}
        call_next = AsyncMock(return_value=response)

        result = await response_cache_middleware(request, call_next)

        assert result.headers["Cache-Control"] == "no-store"

    @pytest.mark.asyncio
    async def test_static_assets_get_long_cache(
        self, mock_response: MagicMock
    ) -> None:
        """Static assets should get long cache duration."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/static/style.css"
        request.headers = {}

        call_next = AsyncMock(return_value=mock_response)

        result = await response_cache_middleware(request, call_next)

        assert "public" in result.headers["Cache-Control"]
        assert "max-age=86400" in result.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_api_responses_get_private_cache(
        self, mock_response: MagicMock
    ) -> None:
        """API responses should get private, no-cache directive."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/data"
        request.headers = {}

        call_next = AsyncMock(return_value=mock_response)

        result = await response_cache_middleware(request, call_next)

        assert "private" in result.headers["Cache-Control"]
        assert "no-cache" in result.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_etag_generated_for_response_with_body(
        self, mock_response: MagicMock
    ) -> None:
        """ETag should be generated for responses with body."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/data"
        request.headers = {}

        call_next = AsyncMock(return_value=mock_response)

        result = await response_cache_middleware(request, call_next)

        assert "ETag" in result.headers
        assert result.headers["ETag"].startswith('W/"')

    @pytest.mark.asyncio
    async def test_conditional_get_returns_304(
        self, mock_response: MagicMock
    ) -> None:
        """Conditional GET with matching ETag should return 304."""
        # First, get the ETag
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/data"
        request.headers = {}

        call_next = AsyncMock(return_value=mock_response)
        result = await response_cache_middleware(request, call_next)
        etag = result.headers.get("ETag")

        # Now make conditional request with that ETag
        request2 = MagicMock()
        request2.method = "GET"
        request2.url.path = "/api/data"
        request2.headers = {"If-None-Match": etag}

        # Reset mock_response for second call
        mock_response.headers = {}
        call_next2 = AsyncMock(return_value=mock_response)

        result2 = await response_cache_middleware(request2, call_next2)

        assert result2.status_code == 304

    @pytest.mark.asyncio
    async def test_non_2xx_responses_not_cached(self) -> None:
        """Non-2xx responses should not have cache headers added."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/data"

        error_response = MagicMock()
        error_response.status_code = 404
        error_response.headers = {}

        call_next = AsyncMock(return_value=error_response)

        result = await response_cache_middleware(request, call_next)

        assert "Cache-Control" not in result.headers

    @pytest.mark.asyncio
    async def test_existing_cache_control_preserved(self) -> None:
        """Existing Cache-Control headers should be preserved."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/data"

        response = MagicMock()
        response.status_code = 200
        response.headers = {"Cache-Control": "must-revalidate"}

        call_next = AsyncMock(return_value=response)

        result = await response_cache_middleware(request, call_next)

        assert result.headers["Cache-Control"] == "must-revalidate"

    @pytest.mark.asyncio
    async def test_openapi_json_cached(self, mock_response: MagicMock) -> None:
        """OpenAPI spec should be cached."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/openapi.json"
        request.headers = {}

        call_next = AsyncMock(return_value=mock_response)

        result = await response_cache_middleware(request, call_next)

        assert "public" in result.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_response_without_body_skips_etag(self) -> None:
        """Response without body should skip ETag generation."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/data"
        request.headers = {}

        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.body = b""  # Empty body

        call_next = AsyncMock(return_value=response)

        result = await response_cache_middleware(request, call_next)

        # Should not have ETag for empty body
        assert "ETag" not in result.headers or result.headers.get("ETag") is None

    @pytest.mark.asyncio
    async def test_streaming_response_skips_etag(self) -> None:
        """Streaming responses without body attribute should skip ETag."""
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/stream"
        request.headers = {}

        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        # Simulate streaming response without body attribute
        del response.body

        call_next = AsyncMock(return_value=response)

        result = await response_cache_middleware(request, call_next)

        # Should not raise, just skip ETag
        assert "Cache-Control" in result.headers
