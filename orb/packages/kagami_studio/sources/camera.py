"""Camera Source — Webcam and capture card input."""

from __future__ import annotations

import asyncio
import logging

import numpy as np

from kagami_studio.sources.base import Source, SourceState, SourceType

logger = logging.getLogger(__name__)


class CameraSource(Source):
    """Camera input source using OpenCV."""

    def __init__(self, source_id: str, name: str, device_id: int = 0):
        super().__init__(source_id, name, SourceType.CAMERA)
        self.device_id = device_id
        self._capture = None
        self._frame = None
        self._task = None

    async def start(self) -> None:
        """Start camera capture."""
        import cv2

        self.state = SourceState.STARTING

        self._capture = cv2.VideoCapture(self.device_id)
        if not self._capture.isOpened():
            self.state = SourceState.ERROR
            raise RuntimeError(f"Failed to open camera {self.device_id}")

        self._width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._fps = self._capture.get(cv2.CAP_PROP_FPS) or 30.0

        # Start capture loop
        self._task = asyncio.create_task(self._capture_loop())
        self.state = SourceState.ACTIVE

        logger.info(f"Camera started: {self._width}x{self._height} @ {self._fps}fps")

    async def stop(self) -> None:
        """Stop camera capture."""
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

    async def _capture_loop(self) -> None:
        """Continuous capture loop."""

        while self.state == SourceState.ACTIVE:
            ret, frame = self._capture.read()
            if ret:
                self._frame = frame
            await asyncio.sleep(1 / self._fps)

    async def get_frame(self) -> np.ndarray | None:
        """Get current frame."""
        return self._frame
