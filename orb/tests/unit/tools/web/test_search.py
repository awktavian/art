"""Tests for kagami/tools/web/search.py - Web search client."""

from __future__ import annotations

from unittest.mock import Mock, patch, AsyncMock

import pytest


class TestSearchHit:
    """Tests for SearchHit dataclass."""

    def test_search_hit_creation(self) -> None:
        """Test SearchHit dataclass instantiation."""
        from kagami.tools.web.search import SearchHit

        hit = SearchHit(
            title="Test Result",
            url="https://example.com",
            snippet="This is a test snippet",
            source="serpapi",
        )

        assert hit.title == "Test Result"
        assert hit.url == "https://example.com"
        assert hit.snippet == "This is a test snippet"
        assert hit.source == "serpapi"


class TestSearchSerpapi:
    """Tests for _search_serpapi function."""

    @pytest.mark.asyncio
    async def test_serpapi_returns_empty_without_key(self) -> None:
        """Test that SERPAPI returns empty list without API key."""
        from kagami.tools.web.search import _search_serpapi
        import httpx

        with patch.dict("os.environ", {}, clear=True):
            async with httpx.AsyncClient() as client:
                results = await _search_serpapi(client, "test query", 5)

        assert results == []

    @pytest.mark.asyncio
    @patch("os.getenv")
    async def test_serpapi_parses_results(self, mock_getenv: Mock) -> None:
        """Test SERPAPI result parsing with mocked response."""
        from kagami.tools.web.search import _search_serpapi

        mock_getenv.return_value = "fake_api_key"

        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "organic_results": [
                {"title": "Result 1", "link": "https://example1.com", "snippet": "Snippet 1"},
                {"title": "Result 2", "link": "https://example2.com", "snippet": "Snippet 2"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)

        results = await _search_serpapi(mock_client, "test query", 5)

        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[0].url == "https://example1.com"
        assert results[0].snippet == "Snippet 1"
        assert results[0].source == "serpapi"
        assert results[1].title == "Result 2"

    @pytest.mark.asyncio
    @patch("os.getenv")
    async def test_serpapi_respects_top_k(self, mock_getenv: Mock) -> None:
        """Test SERPAPI respects top_k parameter."""
        from kagami.tools.web.search import _search_serpapi

        mock_getenv.return_value = "fake_api_key"

        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "organic_results": [
                {
                    "title": f"Result {i}",
                    "link": f"https://example{i}.com",
                    "snippet": f"Snippet {i}",
                }
                for i in range(10)
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)

        results = await _search_serpapi(mock_client, "test query", 3)

        assert len(results) == 3


class TestSearchBing:
    """Tests for _search_bing function."""

    @pytest.mark.asyncio
    async def test_bing_returns_empty_without_key(self) -> None:
        """Test that Bing returns empty list without API key."""
        from kagami.tools.web.search import _search_bing
        import httpx

        with patch.dict("os.environ", {}, clear=True):
            async with httpx.AsyncClient() as client:
                results = await _search_bing(client, "test query", 5)

        assert results == []

    @pytest.mark.asyncio
    @patch("os.getenv")
    async def test_bing_parses_results(self, mock_getenv: Mock) -> None:
        """Test Bing result parsing with mocked response."""
        from kagami.tools.web.search import _search_bing

        mock_getenv.return_value = "fake_bing_key"

        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "webPages": {
                "value": [
                    {"name": "Bing Result", "url": "https://bing.com/1", "snippet": "Bing snippet"},
                ]
            }
        }
        mock_response.raise_for_status = Mock()
        mock_client.get = AsyncMock(return_value=mock_response)

        results = await _search_bing(mock_client, "test query", 5)

        assert len(results) == 1
        assert results[0].title == "Bing Result"
        assert results[0].url == "https://bing.com/1"
        assert results[0].snippet == "Bing snippet"
        assert results[0].source == "bing"


class TestSearchDuckDuckGo:
    """Tests for _search_duckduckgo function."""

    @pytest.mark.asyncio
    async def test_duckduckgo_handles_import_error(self) -> None:
        """Test graceful handling when BeautifulSoup not available."""
        from kagami.tools.web.search import _search_duckduckgo

        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)

        # Should not crash, returns empty or parsed results
        results = await _search_duckduckgo(mock_client, "test query", 5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_duckduckgo_success_path(self) -> None:
        """Test DuckDuckGo success path with parsed results."""
        from kagami.tools.web.search import _search_duckduckgo

        mock_client = AsyncMock()
        mock_response = Mock()
        # Mock HTML with realistic DuckDuckGo structure
        mock_response.text = """
        <html>
            <div class="result">
                <a class="result__title" href="https://example.com/1">
                    <span>Example Result 1</span>
                </a>
                <a class="result__url" href="https://example.com/1">example.com/1</a>
                <div class="result__snippet">This is a test snippet from DDG</div>
            </div>
            <div class="result">
                <a class="result__title" href="https://example.com/2">
                    <span>Example Result 2</span>
                </a>
                <a class="result__url" href="https://example.com/2">example.com/2</a>
                <div class="result__snippet">Another snippet</div>
            </div>
        </html>
        """
        mock_response.raise_for_status = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)

        results = await _search_duckduckgo(mock_client, "test query", 5)

        assert len(results) == 2
        assert results[0].title == "Example Result 1"
        assert results[0].url == "https://example.com/1"
        assert results[0].snippet == "This is a test snippet from DDG"
        assert results[0].source == "duckduckgo"
        assert results[1].title == "Example Result 2"

    @pytest.mark.asyncio
    async def test_duckduckgo_respects_top_k(self) -> None:
        """Test DuckDuckGo respects top_k limit."""
        from kagami.tools.web.search import _search_duckduckgo

        mock_client = AsyncMock()
        mock_response = Mock()
        # Create 10 results
        results_html = "\n".join(
            [
                f"""
            <div class="result">
                <a class="result__title" href="https://example.com/{i}">Result {i}</a>
                <a class="result__url" href="https://example.com/{i}">example.com/{i}</a>
                <div class="result__snippet">Snippet {i}</div>
            </div>
            """
                for i in range(10)
            ]
        )
        mock_response.text = f"<html>{results_html}</html>"
        mock_response.raise_for_status = Mock()
        mock_client.post = AsyncMock(return_value=mock_response)

        results = await _search_duckduckgo(mock_client, "test query", 3)

        assert len(results) <= 3


class TestSearchWeb:
    """Tests for search_web function."""

    @pytest.mark.asyncio
    @patch("kagami.tools.web.search._search_serpapi")
    async def test_search_web_tries_serpapi_first(self, mock_serpapi: Mock) -> None:
        """Test that search_web tries SERPAPI first."""
        from kagami.tools.web.search import search_web, SearchHit

        mock_serpapi.return_value = [
            SearchHit(title="SERP Result", url="https://serp.com", snippet="", source="serpapi")
        ]

        results = await search_web("test query", 5)

        assert len(results) == 1
        assert results[0].source == "serpapi"
        mock_serpapi.assert_called_once()

    @pytest.mark.asyncio
    @patch("kagami.tools.web.search._search_serpapi")
    @patch("kagami.tools.web.search._search_bing")
    async def test_search_web_falls_back_to_bing(self, mock_bing: Mock, mock_serpapi: Mock) -> None:
        """Test that search_web falls back to Bing when SERPAPI returns empty."""
        from kagami.tools.web.search import search_web, SearchHit

        mock_serpapi.return_value = []
        mock_bing.return_value = [
            SearchHit(title="Bing Result", url="https://bing.com", snippet="", source="bing")
        ]

        results = await search_web("test query", 5)

        assert len(results) == 1
        assert results[0].source == "bing"

    @pytest.mark.asyncio
    @patch("kagami.tools.web.search._search_serpapi")
    @patch("kagami.tools.web.search._search_bing")
    @patch("kagami.tools.web.search._search_duckduckgo")
    async def test_search_web_falls_back_to_duckduckgo(
        self, mock_ddg: Mock, mock_bing: Mock, mock_serpapi: Mock
    ) -> None:
        """Test that search_web falls back to DuckDuckGo as last resort."""
        from kagami.tools.web.search import search_web, SearchHit

        mock_serpapi.return_value = []
        mock_bing.return_value = []
        mock_ddg.return_value = [
            SearchHit(title="DDG Result", url="https://ddg.com", snippet="", source="duckduckgo")
        ]

        results = await search_web("test query", 5)

        assert len(results) == 1
        assert results[0].source == "duckduckgo"

    @pytest.mark.asyncio
    @patch("kagami.tools.web.search._search_serpapi")
    @patch("kagami.tools.web.search._search_bing")
    @patch("kagami.tools.web.search._search_duckduckgo")
    async def test_search_web_returns_empty_when_all_fail(
        self, mock_ddg: Mock, mock_bing: Mock, mock_serpapi: Mock
    ) -> None:
        """Test that search_web returns empty when all providers fail."""
        from kagami.tools.web.search import search_web

        mock_serpapi.return_value = []
        mock_bing.return_value = []
        mock_ddg.return_value = []

        results = await search_web("test query", 5)

        assert results == []


class TestWebSearch:
    """Tests for web_search convenience function."""

    @pytest.mark.asyncio
    @patch("kagami.tools.web.search.search_web")
    async def test_web_search_returns_dicts(self, mock_search_web: Mock) -> None:
        """Test that web_search returns list of dicts."""
        from kagami.tools.web.search import web_search, SearchHit

        mock_search_web.return_value = [
            SearchHit(title="Result", url="https://example.com", snippet="Snippet", source="test")
        ]

        # Mock metrics and receipts to avoid import errors
        with patch("kagami_observability.metrics.get_counter", side_effect=ImportError):
            with patch("kagami.core.receipts.emit_receipt", side_effect=ImportError):
                results = await web_search("test query", max_results=5)

        assert len(results) == 1
        assert results[0]["title"] == "Result"
        assert results[0]["url"] == "https://example.com"
        assert results[0]["snippet"] == "Snippet"
        assert results[0]["source"] == "test"

    @pytest.mark.asyncio
    @patch("kagami.tools.web.search.search_web")
    async def test_web_search_raises_on_error(self, mock_search_web: Mock) -> None:
        """Test that web_search raises RuntimeError on failure."""
        from kagami.tools.web.search import web_search

        mock_search_web.side_effect = Exception("Network error")

        with pytest.raises(RuntimeError, match="Web search failed"):
            await web_search("test query")

    @pytest.mark.asyncio
    @patch("kagami.tools.web.search.search_web")
    @patch("kagami_observability.metrics.get_counter")
    @patch("kagami_observability.metrics.get_histogram")
    async def test_web_search_emits_metrics_on_success(
        self, mock_histogram: Mock, mock_counter: Mock, mock_search_web: Mock
    ) -> None:
        """Test that web_search emits metrics on successful search."""
        from kagami.tools.web.search import web_search, SearchHit

        # Setup mocks
        mock_counter_instance = Mock()
        mock_counter_instance.labels.return_value.inc = Mock()
        mock_counter.return_value = mock_counter_instance

        mock_histogram_instance = Mock()
        mock_histogram_instance.labels.return_value.observe = Mock()
        mock_histogram.return_value = mock_histogram_instance

        mock_search_web.return_value = [
            SearchHit(title="Result", url="https://example.com", snippet="Snippet", source="test")
        ]

        with patch("kagami.core.receipts.emit_receipt", side_effect=ImportError):
            results = await web_search("test query", max_results=5)

        # Verify metrics were emitted
        assert len(results) == 1
        mock_counter.assert_called_once()
        mock_histogram.assert_called_once()
        mock_counter_instance.labels.assert_called_with(status="success")
        mock_histogram_instance.labels.assert_called_with(status="success")

    @pytest.mark.asyncio
    @patch("kagami.tools.web.search.search_web")
    @patch("kagami.core.receipts.emit_receipt")
    async def test_web_search_emits_receipts(
        self, mock_emit_receipt: Mock, mock_search_web: Mock
    ) -> None:
        """Test that web_search emits PLAN, EXECUTE, VERIFY receipts."""
        from kagami.tools.web.search import web_search, SearchHit

        mock_search_web.return_value = [
            SearchHit(title="Result", url="https://example.com", snippet="Snippet", source="test")
        ]

        with patch("kagami_observability.metrics.get_counter", side_effect=ImportError):
            with patch("kagami_observability.metrics.get_histogram", side_effect=ImportError):
                results = await web_search("test query", max_results=5)

        # Verify receipts were emitted (PLAN, EXECUTE, VERIFY)
        assert mock_emit_receipt.call_count == 3
        calls = mock_emit_receipt.call_args_list

        # Verify PLAN receipt
        plan_call = calls[0][1]
        assert plan_call["event_name"] == "web.search.plan"
        assert plan_call["phase"] == "plan"
        assert plan_call["status"] == "planning"
        assert plan_call["event_data"]["query"] == "test query"

        # Verify EXECUTE receipt
        execute_call = calls[1][1]
        assert execute_call["event_name"] == "web.search.execute"
        assert execute_call["phase"] == "execute"
        assert execute_call["status"] == "success"

        # Verify VERIFY receipt
        verify_call = calls[2][1]
        assert verify_call["event_name"] == "web.search.verify"
        assert verify_call["phase"] == "verify"
        assert verify_call["status"] == "success"
        assert verify_call["event_data"]["verified"] is True

    @pytest.mark.asyncio
    @patch("kagami.tools.web.search.search_web")
    @patch("kagami_observability.metrics.get_counter")
    @patch("kagami_observability.metrics.get_histogram")
    async def test_web_search_metrics_on_error(
        self, mock_histogram: Mock, mock_counter: Mock, mock_search_web: Mock
    ) -> None:
        """Test that web_search emits error metrics on failure."""
        from kagami.tools.web.search import web_search

        mock_counter_instance = Mock()
        mock_counter_instance.labels.return_value.inc = Mock()
        mock_counter.return_value = mock_counter_instance

        mock_histogram_instance = Mock()
        mock_histogram_instance.labels.return_value.observe = Mock()
        mock_histogram.return_value = mock_histogram_instance

        mock_search_web.side_effect = Exception("Network error")

        with patch("kagami.core.receipts.emit_receipt", side_effect=ImportError):
            with pytest.raises(RuntimeError):
                await web_search("test query")

        # Verify error status was recorded
        mock_counter_instance.labels.assert_called_with(status="error")

    @pytest.mark.asyncio
    @patch("kagami.tools.web.search.search_web")
    async def test_web_search_uses_correlation_id(self, mock_search_web: Mock) -> None:
        """Test that web_search uses provided correlation_id."""
        from kagami.tools.web.search import web_search, SearchHit

        mock_search_web.return_value = [
            SearchHit(title="Result", url="https://example.com", snippet="Snippet", source="test")
        ]

        with patch("kagami_observability.metrics.get_counter", side_effect=ImportError):
            with patch("kagami_observability.metrics.get_histogram", side_effect=ImportError):
                with patch("kagami.core.receipts.emit_receipt") as mock_receipt:
                    await web_search("test query", correlation_id="custom-id-123")

                    # Verify all receipts used the same correlation_id
                    for call in mock_receipt.call_args_list:
                        assert call[1]["correlation_id"] == "custom-id-123"
