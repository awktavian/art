"""Browser Source — Web page capture.

Captures and renders web pages as video sources using
Playwright for headless browser automation.

Usage:
    source = BrowserSource(source_id="browser_1", name="Dashboard", url="https://...")
    await source.start()
    frame = await source.get_frame()
"""

from __future__ import annotations

import asyncio
import logging

import numpy as np

from kagami_studio.sources.base import Source, SourceState, SourceType

logger = logging.getLogger(__name__)


class BrowserSource(Source):
    """Web browser source using Playwright.

    Renders web pages in a headless browser and captures
    them as video frames. Useful for:
    - Live dashboards
    - Social media feeds
    - Chat overlays
    - Custom HTML graphics
    - Animated web content
    """

    def __init__(
        self,
        source_id: str,
        name: str,
        url: str,
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
        css: str | None = None,
    ):
        """Initialize browser source.

        Args:
            source_id: Unique source identifier
            name: Display name
            url: URL to load
            width: Browser viewport width
            height: Browser viewport height
            fps: Capture rate
            css: Custom CSS to inject
        """
        super().__init__(source_id, name, SourceType.BROWSER)
        self.url = url
        self._width = width
        self._height = height
        self._fps = fps
        self.custom_css = css

        self._browser = None
        self._page = None
        self._frame = None
        self._task = None

    async def start(self) -> None:
        """Start browser and begin capturing."""
        self.state = SourceState.STARTING

        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()

            # Launch chromium
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

            # Create page
            self._page = await self._browser.new_page(
                viewport={"width": self._width, "height": self._height}
            )

            # Navigate to URL
            await self._page.goto(self.url, wait_until="networkidle")

            # Inject custom CSS if provided
            if self.custom_css:
                await self._page.add_style_tag(content=self.custom_css)

            # Start capture loop
            self._task = asyncio.create_task(self._capture_loop())
            self.state = SourceState.ACTIVE

            logger.info(f"Browser source started: {self.url[:50]}...")

        except ImportError:
            logger.error("Playwright not available: pip install playwright && playwright install")
            self.state = SourceState.ERROR
        except Exception as e:
            logger.error(f"Browser source failed: {e}")
            self.state = SourceState.ERROR

    async def stop(self) -> None:
        """Stop browser capture."""
        self.state = SourceState.INACTIVE

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._page:
            await self._page.close()
            self._page = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if hasattr(self, "_playwright") and self._playwright:
            await self._playwright.stop()

        logger.info("Browser source stopped")

    async def _capture_loop(self) -> None:
        """Continuous capture loop."""
        import cv2

        while self.state == SourceState.ACTIVE:
            try:
                # Take screenshot
                screenshot = await self._page.screenshot(type="png")

                # Convert to numpy
                import io

                from PIL import Image

                img = Image.open(io.BytesIO(screenshot))
                frame = np.array(img)

                # Convert RGBA to BGR
                if frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                else:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                self._frame = frame

            except Exception as e:
                logger.error(f"Browser capture error: {e}")

            await asyncio.sleep(1 / self._fps)

    async def get_frame(self) -> np.ndarray | None:
        """Get current frame."""
        return self._frame

    async def navigate(self, url: str) -> None:
        """Navigate to a new URL."""
        if self._page:
            self.url = url
            await self._page.goto(url, wait_until="networkidle")

    async def execute_js(self, script: str) -> any:
        """Execute JavaScript in the page."""
        if self._page:
            return await self._page.evaluate(script)
        return None

    async def click(self, selector: str) -> None:
        """Click an element."""
        if self._page:
            await self._page.click(selector)

    async def type_text(self, selector: str, text: str) -> None:
        """Type text into an input."""
        if self._page:
            await self._page.fill(selector, text)

    async def reload(self) -> None:
        """Reload the page."""
        if self._page:
            await self._page.reload(wait_until="networkidle")
