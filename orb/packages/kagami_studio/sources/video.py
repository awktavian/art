"""Video Source — Video file playback."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import numpy as np

from kagami_studio.sources.base import Source, SourceState, SourceType

logger = logging.getLogger(__name__)


class VideoSource(Source):
    """Video file source with loop support."""

    def __init__(self, source_id: str, name: str, path: Path, loop: bool = True):
        super().__init__(source_id, name, SourceType.VIDEO)
        self.path = path
        self.loop = loop
        self._capture = None
        self._frame = None
        self._task = None
        self._paused = False

    async def start(self) -> None:
        """Start video playback."""
        import cv2

        self.state = SourceState.STARTING

        if not self.path.exists():
            self.state = SourceState.ERROR
            raise FileNotFoundError(f"Video not found: {self.path}")

        self._capture = cv2.VideoCapture(str(self.path))
        if not self._capture.isOpened():
            self.state = SourceState.ERROR
            raise RuntimeError(f"Failed to open video: {self.path}")

        self._width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._fps = self._capture.get(cv2.CAP_PROP_FPS) or 30.0

        # Start playback loop
        self._task = asyncio.create_task(self._playback_loop())
        self.state = SourceState.ACTIVE

        logger.info(f"Video started: {self._width}x{self._height} @ {self._fps}fps")

    async def stop(self) -> None:
        """Stop video playback."""
        self.state = SourceState.INACTIVE

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._capture:
            self._capture.release()
            self._capture = None

    async def _playback_loop(self) -> None:
        """Continuous playback loop."""
        while self.state == SourceState.ACTIVE:
            if self._paused:
                await asyncio.sleep(0.1)
                continue

            ret, frame = self._capture.read()

            if not ret:
                if self.loop:
                    # Restart from beginning
                    self._capture.set(0, 0)  # CV_CAP_PROP_POS_FRAMES
                    continue
                else:
                    break

            self._frame = frame
            await asyncio.sleep(1 / self._fps)

    async def get_frame(self) -> np.ndarray | None:
        """Get current frame."""
        return self._frame

    def pause(self) -> None:
        """Pause playback."""
        self._paused = True
        self.state = SourceState.PAUSED

    def resume(self) -> None:
        """Resume playback."""
        self._paused = False
        self.state = SourceState.ACTIVE

    def seek(self, position_ms: float) -> None:
        """Seek to position."""
        import cv2

        if self._capture:
            self._capture.set(cv2.CAP_PROP_POS_MSEC, position_ms)
