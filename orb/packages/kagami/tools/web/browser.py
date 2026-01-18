# SPDX-License-Identifier: MIT
"""Optional dynamic page rendering via Playwright (guarded by env flag)."""

import os
from dataclasses import dataclass


@dataclass
class RenderResult:
    """Result of browser rendering."""

    url: str
    html: str


def render(url: str, timeout_ms: int = 15000) -> RenderResult | None:
    """
    Render a dynamic page using Playwright (optional).

    Requires KAGAMI_PLAYWRIGHT=1 environment variable.

    Args:
        url: Target URL
        timeout_ms: Page load timeout in milliseconds

    Returns:
        RenderResult if Playwright enabled, None otherwise
    """
    if os.getenv("KAGAMI_PLAYWRIGHT") != "1":
        return None

    playwright_module = None
    try:
        from playwright.sync_api import sync_playwright

        playwright_module = sync_playwright
    except ImportError:
        playwright_module = None

    if playwright_module is None:
        # Return None gracefully instead of raising error
        return None

    with playwright_module() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="K os-ResearchBot/1.0")
        page.goto(url, timeout=timeout_ms)
        html = page.content()
        browser.close()

    return RenderResult(url=url, html=html)
