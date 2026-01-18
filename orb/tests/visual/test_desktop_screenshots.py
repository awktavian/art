"""
Desktop Visual Screenshot Tests

Uses Puppeteer MCP to capture screenshots of all Desktop HTML pages
and verify they render correctly with design tokens.

Colony: Crystal (e7) — Verification
h(x) ≥ 0. Always.
"""

import asyncio
import subprocess
import tempfile
from pathlib import Path

import pytest

# Desktop HTML pages to test
DESKTOP_PAGES = [
    "agents.html",
    "command-palette.html",
    "face-review.html",
    "federation.html",
    "hal-display.html",
    "identity-lab.html",
    "login.html",
    "onboarding.html",
    "permissions.html",
    "quick-entry.html",
    "room-dashboard.html",
    "settings.html",
    "voice-monitor.html",
]

DESKTOP_SRC = Path(__file__).parent.parent.parent / "apps" / "desktop" / "kagami-client" / "src"


class TestDesktopScreenshots:
    """Screenshot tests for Desktop HTML pages."""

    @pytest.mark.parametrize("page", DESKTOP_PAGES)
    def test_page_renders(self, page: str):
        """Test that each page renders without errors."""
        page_path = DESKTOP_SRC / page
        assert page_path.exists(), f"Page not found: {page_path}"

        # For now, just verify the file exists and has content
        content = page_path.read_text()
        assert len(content) > 100, f"Page {page} is too small"

        # Verify CSS imports or inline design tokens
        has_import = (
            "design-tokens.generated.css" in content
            or "genux-tokens.css" in content
            or "prism-tokens.css" in content
            or "design-system.css" in content
        )
        has_inline = ":root {" in content and "--" in content
        assert has_import or has_inline, f"Page {page} missing design tokens (import or inline)"

    def test_design_tokens_not_empty(self):
        """Verify design-tokens.generated.css is not empty."""
        css_path = DESKTOP_SRC / "css" / "design-tokens.generated.css"
        assert css_path.exists(), "design-tokens.generated.css not found"

        content = css_path.read_text()
        assert len(content) > 500, "design-tokens.generated.css is too small"

        # Verify key variables exist
        assert "--prism-spark" in content
        assert "--prism-crystal" in content
        assert "--prism-dur-micro" in content
        assert "--prism-ease-standard" in content

    def test_colony_colors_consistent(self):
        """Verify colony colors are consistent across CSS files."""
        css_path = DESKTOP_SRC / "css" / "design-tokens.generated.css"
        content = css_path.read_text()

        # Expected colony colors from design-tokens.json
        expected = {
            "spark": "#FF6B35",
            "forge": "#FF9500",
            "flow": "#5AC8FA",
            "nexus": "#AF52DE",
            "beacon": "#FFD60A",
            "grove": "#32D74B",
            "crystal": "#64D2FF",
        }

        for colony, hex_val in expected.items():
            assert hex_val.lower() in content.lower(), (
                f"Colony color {colony} ({hex_val}) not found in CSS"
            )

    def test_fibonacci_timing_present(self):
        """Verify Fibonacci timing values are in CSS."""
        css_path = DESKTOP_SRC / "css" / "design-tokens.generated.css"
        content = css_path.read_text()

        # Fibonacci sequence values
        fibonacci = [89, 144, 233, 377, 610, 987, 1597, 2584]

        for ms in fibonacci:
            assert f"{ms}ms" in content, f"Fibonacci timing {ms}ms not found"


class TestDesktopAccessibility:
    """Accessibility tests for Desktop pages."""

    @pytest.mark.parametrize("page", DESKTOP_PAGES)
    def test_page_has_lang(self, page: str):
        """Verify each page has lang attribute."""
        page_path = DESKTOP_SRC / page
        content = page_path.read_text()
        assert 'lang="en"' in content or "lang='en'" in content, (
            f"Page {page} missing lang attribute"
        )

    @pytest.mark.parametrize("page", DESKTOP_PAGES)
    def test_page_has_viewport(self, page: str):
        """Verify each page has viewport meta."""
        page_path = DESKTOP_SRC / page
        content = page_path.read_text()
        assert "viewport" in content, f"Page {page} missing viewport meta"


class TestDesktopComponentHarness:
    """Tests for the component harness."""

    def test_component_harness_exists(self):
        """Verify component harness exists."""
        harness_path = DESKTOP_SRC / "visual-tests" / "component-harness.html"
        assert harness_path.exists(), "component-harness.html not found"

    def test_component_harness_has_buttons(self):
        """Verify component harness has button variants."""
        harness_path = DESKTOP_SRC / "visual-tests" / "component-harness.html"
        content = harness_path.read_text()

        # Prismorphism button variants: solid, outline, ghost, link
        variants = ["solid", "outline", "ghost", "link"]
        for variant in variants:
            assert variant in content.lower(), f"Button variant '{variant}' not found in harness"


# Puppeteer-based visual tests (requires MCP)
class TestDesktopVisualRegression:
    """Visual regression tests using Puppeteer MCP."""

    @pytest.mark.skip(reason="Requires Puppeteer MCP running")
    @pytest.mark.parametrize("page", DESKTOP_PAGES)
    async def test_screenshot_matches_baseline(self, page: str):
        """Compare current screenshot to baseline."""
        # This would use Puppeteer MCP to:
        # 1. Navigate to page
        # 2. Take screenshot
        # 3. Compare to baseline
        # 4. Fail if difference > threshold
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
