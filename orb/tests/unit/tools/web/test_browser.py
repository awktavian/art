"""Tests for kagami/tools/web/browser.py - Browser rendering."""

from __future__ import annotations

from unittest.mock import Mock, patch, MagicMock

import pytest


class TestRenderResult:
    """Tests for RenderResult dataclass."""

    def test_render_result_creation(self) -> None:
        """Test RenderResult dataclass instantiation."""
        from kagami.tools.web.browser import RenderResult

        result = RenderResult(
            url="https://example.com",
            html="<html><body>Content</body></html>",
        )

        assert result.url == "https://example.com"
        assert result.html == "<html><body>Content</body></html>"

    @pytest.mark.parametrize(
        "url,html",
        [
            (
                "https://test.org/page",
                "<!DOCTYPE html><html><head><title>Test</title></head></html>",
            ),
            ("http://localhost:8080", "<html><body><h1>Local</h1></body></html>"),
            ("https://example.com/path/to/page", "<html><div>Complex</div></html>"),
        ],
    )
    def test_render_result_with_various_content(self, url: str, html: str) -> None:
        """Test RenderResult with various URLs and HTML content."""
        from kagami.tools.web.browser import RenderResult

        result = RenderResult(url=url, html=html)

        assert result.url == url
        assert result.html == html
        assert isinstance(result.url, str)
        assert isinstance(result.html, str)


class TestRenderDisabledBehavior:
    """Tests for render() when disabled or unavailable."""

    @pytest.mark.parametrize(
        "env_value",
        [None, "0", "", "false"],
    )
    def test_render_returns_none_when_not_enabled(self, env_value: str | None) -> None:
        """Test that render returns None when KAGAMI_PLAYWRIGHT not set to '1'."""
        from kagami.tools.web.browser import render

        env_dict = {"KAGAMI_PLAYWRIGHT": env_value} if env_value is not None else {}
        with patch.dict("os.environ", env_dict, clear=True):
            result = render("https://example.com")

        assert result is None

    @patch("kagami.tools.web.browser.os.getenv")
    def test_render_checks_env_variable(self, mock_getenv: Mock) -> None:
        """Test that render checks KAGAMI_PLAYWRIGHT env var."""
        from kagami.tools.web.browser import render

        mock_getenv.return_value = "0"

        result = render("https://example.com")

        mock_getenv.assert_called_with("KAGAMI_PLAYWRIGHT")
        assert result is None

    def test_render_accepts_timeout_parameter(self) -> None:
        """Test that render accepts timeout_ms parameter."""
        from kagami.tools.web.browser import render

        # Should not crash with custom timeout
        with patch.dict("os.environ", {}, clear=True):
            result = render("https://example.com", timeout_ms=30000)

        assert result is None  # Disabled by env var


class TestRenderWithMockedPlaywright:
    """Tests for render() with mocked Playwright."""

    @patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"})
    def test_render_returns_none_when_playwright_not_installed(self) -> None:
        """Test graceful handling when playwright not installed."""
        from kagami.tools.web.browser import render

        # Mock the import to fail
        with patch("builtins.__import__", side_effect=ImportError("playwright not installed")):
            result = render("https://example.com")

        # Should return None gracefully
        assert result is None

    @patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"})
    @patch("playwright.sync_api.sync_playwright")
    def test_render_with_mocked_playwright_success(self, mock_sync_playwright: Mock) -> None:
        """Test successful rendering with mocked Playwright."""
        from kagami.tools.web.browser import render

        # Setup mock playwright chain
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body>Rendered Content</body></html>"

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_instance

        result = render("https://example.com")

        # Verify result
        assert result is not None
        assert result.url == "https://example.com"
        assert result.html == "<html><body>Rendered Content</body></html>"

        # Verify playwright calls
        mock_playwright_instance.chromium.launch.assert_called_once_with(headless=True)
        mock_browser.new_page.assert_called_once_with(user_agent="K os-ResearchBot/1.0")
        mock_page.goto.assert_called_once_with("https://example.com", timeout=15000)
        mock_page.content.assert_called_once()
        mock_browser.close.assert_called_once()

    @pytest.mark.parametrize(
        "timeout_ms,expected_timeout",
        [
            (5000, 5000),
            (15000, 15000),
            (30000, 30000),
            (60000, 60000),
        ],
    )
    @patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"})
    @patch("playwright.sync_api.sync_playwright")
    def test_render_with_custom_timeout(
        self, mock_sync_playwright: Mock, timeout_ms: int, expected_timeout: int
    ) -> None:
        """Test rendering with various custom timeouts."""
        from kagami.tools.web.browser import render

        # Setup mock playwright chain
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body>Test</body></html>"

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_instance

        result = render("https://example.com", timeout_ms=timeout_ms)

        # Verify custom timeout was used
        mock_page.goto.assert_called_once_with("https://example.com", timeout=expected_timeout)
        assert result is not None

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com",
            "https://test.org/page",
            "http://localhost:8080/test",
            "https://api.example.com/v1/endpoint",
        ],
    )
    @patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"})
    @patch("playwright.sync_api.sync_playwright")
    def test_render_with_different_urls(self, mock_sync_playwright: Mock, url: str) -> None:
        """Test rendering different URLs."""
        from kagami.tools.web.browser import render

        # Setup mock playwright chain
        mock_page = MagicMock()
        mock_page.content.return_value = "<html><body>Content</body></html>"

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_instance

        result = render(url)

        assert result is not None
        assert result.url == url
        mock_page.goto.assert_called_once_with(url, timeout=15000)

    @patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"})
    @patch("playwright.sync_api.sync_playwright")
    def test_render_user_agent_set_correctly(self, mock_sync_playwright: Mock) -> None:
        """Test that custom user agent is set."""
        from kagami.tools.web.browser import render

        # Setup mock playwright chain
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_instance

        render("https://example.com")

        # Verify user agent was set
        mock_browser.new_page.assert_called_once_with(user_agent="K os-ResearchBot/1.0")

    @patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"})
    @patch("playwright.sync_api.sync_playwright")
    def test_render_browser_cleanup(self, mock_sync_playwright: Mock) -> None:
        """Test that browser is properly closed after rendering."""
        from kagami.tools.web.browser import render

        # Setup mock playwright chain
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_instance

        render("https://example.com")

        # Verify browser was closed
        mock_browser.close.assert_called_once()

    @patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"})
    @patch("playwright.sync_api.sync_playwright")
    def test_render_headless_mode_enabled(self, mock_sync_playwright: Mock) -> None:
        """Test that browser is launched in headless mode."""
        from kagami.tools.web.browser import render

        # Setup mock playwright chain
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_instance

        render("https://example.com")

        # Verify headless mode
        mock_playwright_instance.chromium.launch.assert_called_once_with(headless=True)

    @patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"})
    @patch("playwright.sync_api.sync_playwright")
    def test_render_returns_page_html(self, mock_sync_playwright: Mock) -> None:
        """Test that render returns the page HTML content."""
        from kagami.tools.web.browser import render

        expected_html = "<html><body><div>Test Content</div></body></html>"

        # Setup mock playwright chain
        mock_page = MagicMock()
        mock_page.content.return_value = expected_html

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_instance

        result = render("https://example.com")

        assert result is not None
        assert result.html == expected_html
        mock_page.content.assert_called_once()

    @patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"})
    @patch("playwright.sync_api.sync_playwright")
    def test_render_context_manager_cleanup(self, mock_sync_playwright: Mock) -> None:
        """Test that playwright context manager is properly used."""
        from kagami.tools.web.browser import render

        # Setup mock playwright chain
        mock_page = MagicMock()
        mock_page.content.return_value = "<html></html>"

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_playwright_instance
        mock_sync_playwright.return_value = mock_context

        render("https://example.com")

        # Verify context manager was entered and exited
        mock_context.__enter__.assert_called_once()
        mock_context.__exit__.assert_called_once()


# Check if playwright browsers are actually available for integration tests
PLAYWRIGHT_AVAILABLE = False
try:
    import playwright.sync_api
    from playwright.sync_api import sync_playwright
    # Try to actually launch a browser to verify browsers are installed
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        browser.close()
        PLAYWRIGHT_AVAILABLE = True
except Exception:
    # Any error (missing browsers, etc.) means we can't use playwright
    PLAYWRIGHT_AVAILABLE = False


class TestPlaywrightIntegration:
    """Integration tests for Playwright (when available)."""

    @pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Requires Playwright to be installed")
    @pytest.mark.integration
    def test_render_with_real_playwright(self) -> None:
        """Test actual rendering with Playwright (only runs if installed)."""
        from kagami.tools.web.browser import render

        with patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"}):
            # Use a simple, reliable test page
            result = render("https://example.com")

        assert result is not None
        assert result.url == "https://example.com"
        assert "<html" in result.html.lower()
        assert "</html>" in result.html.lower()
        assert len(result.html) > 0

    @pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Requires Playwright to be installed")
    @pytest.mark.integration
    def test_render_with_custom_timeout_real(self) -> None:
        """Test rendering with custom timeout (real Playwright)."""
        from kagami.tools.web.browser import render

        with patch.dict("os.environ", {"KAGAMI_PLAYWRIGHT": "1"}):
            result = render("https://example.com", timeout_ms=20000)

        assert result is not None
        assert "<html" in result.html.lower()
        assert len(result.html) > 0
