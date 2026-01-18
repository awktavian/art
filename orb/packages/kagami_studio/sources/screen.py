"""Screen Source — Display capture."""

from __future__ import annotations

import asyncio
import logging

import numpy as np

from kagami_studio.sources.base import Source, SourceState, SourceType

logger = logging.getLogger(__name__)


class ScreenSource(Source):
    """Screen capture source using mss."""

    def __init__(self, source_id: str, name: str, monitor: int = 0):
        super().__init__(source_id, name, SourceType.SCREEN)
        self.monitor = monitor
        self._sct = None
        self._frame = None
        self._task = None
        self._monitor_info = None

    async def start(self) -> None:
        """Start screen capture."""
        import mss

        self.state = SourceState.STARTING

        self._sct = mss.mss()

        # Get monitor info (0 = all monitors, 1+ = specific monitor)
        monitors = self._sct.monitors
        if self.monitor >= len(monitors):
            self.monitor = 1  # Default to primary

        self._monitor_info = monitors[self.monitor]
        self._width = self._monitor_info["width"]
        self._height = self._monitor_info["height"]
        self._fps = 30.0  # Target FPS for screen capture

        # Start capture loop
        self._task = asyncio.create_task(self._capture_loop())
        self.state = SourceState.ACTIVE

        logger.info(f"Screen capture started: {self._width}x{self._height}")

    async def stop(self) -> None:
        """Stop screen capture."""
        self.state = SourceState.INACTIVE

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._sct:
            self._sct.close()
            self._sct = None

    async def _capture_loop(self) -> None:
        """Continuous capture loop."""
        import cv2

        while self.state == SourceState.ACTIVE:
            try:
                screenshot = self._sct.grab(self._monitor_info)
                # Convert to numpy array (BGRA)
                frame = np.array(screenshot)
                # Convert BGRA to BGR
                self._frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            except Exception as e:
                logger.error(f"Screen capture error: {e}")

            await asyncio.sleep(1 / self._fps)

    async def get_frame(self) -> np.ndarray | None:
        """Get current frame."""
        return self._frame
