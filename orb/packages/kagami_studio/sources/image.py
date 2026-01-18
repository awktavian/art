"""Image Source — Static image input."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from kagami_studio.sources.base import Source, SourceState, SourceType

logger = logging.getLogger(__name__)


class ImageSource(Source):
    """Static image source."""

    def __init__(self, source_id: str, name: str, path: Path):
        super().__init__(source_id, name, SourceType.IMAGE)
        self.path = path
        self._frame = None

    async def start(self) -> None:
        """Load the image."""
        import cv2

        self.state = SourceState.STARTING

        if not self.path.exists():
            self.state = SourceState.ERROR
            raise FileNotFoundError(f"Image not found: {self.path}")

        self._frame = cv2.imread(str(self.path))
        if self._frame is None:
            self.state = SourceState.ERROR
            raise RuntimeError(f"Failed to load image: {self.path}")

        self._height, self._width = self._frame.shape[:2]
        self.state = SourceState.ACTIVE

        logger.info(f"Image loaded: {self._width}x{self._height}")

    async def stop(self) -> None:
        """Release the image."""
        self.state = SourceState.INACTIVE
        self._frame = None

    async def get_frame(self) -> np.ndarray | None:
        """Get the image frame."""
        return self._frame

    async def update_image(self, path: Path) -> None:
        """Update with a new image."""
        import cv2

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        frame = cv2.imread(str(path))
        if frame is not None:
            self._frame = frame
            self._height, self._width = frame.shape[:2]
            self.path = path
