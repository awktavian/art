"""Unit tests for web search functionality.

Tests parsing logic and data conversion without network calls.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_unit



from kagami.tools.web.search import SearchHit


class TestSearchHit:
    """Test SearchHit dataclass."""

    def test_search_hit_creation(self):
        """SearchHit should store all fields correctly."""
        hit = SearchHit(
            title="Example Title",
            url="https://example.com",
            snippet="This is a snippet",
            source="duckduckgo",
        )
        assert hit.title == "Example Title"
        assert hit.url == "https://example.com"
        assert hit.snippet == "This is a snippet"
        assert hit.source == "duckduckgo"

    def test_search_hit_equality(self):
        """Two SearchHits with same data should be equal."""
        hit1 = SearchHit(title="T", url="U", snippet="S", source="test")
        hit2 = SearchHit(title="T", url="U", snippet="S", source="test")
        assert hit1 == hit2

    def test_search_hit_to_dict_conversion(self):
        """SearchHit should convert to dict format expected by API."""
        hit = SearchHit(
            title="Test",
            url="https://test.com",
            snippet="Test snippet",
            source="serpapi",
        )
        # This is the conversion done in web_search()
        result = {
            "title": hit.title,
            "url": hit.url,
            "snippet": hit.snippet,
            "source": hit.source,
        }
        assert result["title"] == "Test"
        assert result["url"] == "https://test.com"
        assert result["source"] == "serpapi"


class TestDuckDuckGoHTMLParsing:
    """Test DuckDuckGo HTML parsing logic."""

    def test_parse_duckduckgo_html_structure(self):
        """Test parsing real DuckDuckGo HTML structure."""
        from bs4 import BeautifulSoup

        # Real DDG HTML structure
        html = """
        <div class="result">
            <a class="result__url" href="https://example.com/page1">example.com/page1</a>
            <a class="result__title" href="https://example.com/page1">Example Page Title</a>
            <div class="result__snippet">This is the search result snippet.</div>
        </div>
        <div class="result">
            <a class="result__url" href="https://another.com">another.com</a>
            <a class="result__title" href="https://another.com">Another Result</a>
            <div class="result__snippet">Second result snippet.</div>
        </div>
        """

        soup = BeautifulSoup(html, "html.parser")
        hits = []

        for result in soup.select(".result"):
            title_elem = result.select_one(".result__title")
            url_elem = result.select_one(".result__url")
            snippet_elem = result.select_one(".result__snippet")

            if title_elem and url_elem:
                hits.append(
                    SearchHit(
                        title=title_elem.get_text(strip=True),
                        url=url_elem.get("href", ""),  # type: ignore[arg-type]
                        snippet=(snippet_elem.get_text(strip=True) if snippet_elem else ""),
                        source="duckduckgo",
                    )
                )

        assert len(hits) == 2
        assert hits[0].title == "Example Page Title"
        assert hits[0].url == "https://example.com/page1"
        assert hits[0].snippet == "This is the search result snippet."
        assert hits[1].title == "Another Result"

    def test_parse_missing_snippet(self):
        """Test parsing when snippet is missing."""
        from bs4 import BeautifulSoup

        html = """
        <div class="result">
            <a class="result__url" href="https://example.com">example.com</a>
            <a class="result__title" href="https://example.com">No Snippet</a>
        </div>
        """

        soup = BeautifulSoup(html, "html.parser")
        result = soup.select_one(".result")
        title_elem = result.select_one(".result__title")  # type: ignore[union-attr]
        url_elem = result.select_one(".result__url")  # type: ignore[union-attr]
        snippet_elem = result.select_one(".result__snippet")  # type: ignore[union-attr]

        hit = SearchHit(
            title=title_elem.get_text(strip=True),  # type: ignore[union-attr]
            url=url_elem.get("href", ""),  # type: ignore[arg-type]  # type: ignore[union-attr]
            snippet=(snippet_elem.get_text(strip=True) if snippet_elem else ""),
            source="duckduckgo",
        )

        assert hit.title == "No Snippet"
        assert hit.snippet == ""

    def test_parse_empty_html(self):
        """Test parsing empty HTML returns empty list."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<div>No results</div>", "html.parser")
        results = soup.select(".result")
        assert len(results) == 0
