"""Virtual display adapter with recording mode.

Created: November 10, 2025
Updated: December 15, 2025 - Recording mode, configurable resolution
"""

from __future__ import annotations

import logging

from kagami_hal.data_types import DisplayInfo, DisplayMode
from kagami_hal.display_controller import DisplayController

from .config import get_virtual_config

logger = logging.getLogger(__name__)


class VirtualDisplay(DisplayController):
    """Virtual display for headless operation.

    Supports:
    - Configurable resolution via environment variables
    - Recording mode (save frames to disk)
    - AGUI streaming compatibility
    """

    def __init__(self) -> None:
        """Initialize virtual display."""
        self._config = get_virtual_config()
        self._brightness = 1.0
        self._mode = DisplayMode.FULL
        self._buffer = b""
        self._frame_count = 0

    async def initialize(self) -> bool:
        """Initialize virtual display."""
        logger.info(
            f"✅ Virtual display initialized: "
            f"{self._config.frame_width}x{self._config.frame_height} "
            f"@ {self._config.frame_fps}fps"
        )
        return True

    async def get_info(self) -> DisplayInfo:
        """Get virtual display info (configurable via environment)."""
        return DisplayInfo(
            width=self._config.frame_width,
            height=self._config.frame_height,
            bpp=32,  # RGBA
            refresh_rate=self._config.frame_fps,
            supports_aod=False,
            supports_touch=False,
        )

    async def write_frame(self, buffer: bytes) -> None:
        """Write frame to virtual display."""
        self._buffer = buffer

        # Record if enabled
        if self._config.record_mode:
            self._record_frame(buffer)

    async def clear(self, color: int = 0x000000) -> None:
        self._buffer = b""

    async def set_brightness(self, level: float) -> None:
        self._brightness = level

    async def get_brightness(self) -> float:
        """Get current brightness level."""
        return self._brightness

    async def set_mode(self, mode: DisplayMode) -> None:
        self._mode = mode

    async def capture_screen(self) -> bytes:
        """Capture current screen content."""
        if not self._buffer:
            # Blank RGBA frame (matches DisplayInfo bpp=32)
            w = self._config.frame_width
            h = self._config.frame_height
            return b"\x00" * (w * h * 4)
        return self._buffer

    async def shutdown(self) -> None:
        """Shutdown virtual display."""
        self._buffer = b""
        logger.info(f"Virtual display shutdown ({self._frame_count} frames written)")

    def _record_frame(self, buffer: bytes) -> None:
        """Record frame to disk.

        Args:
            buffer: Frame buffer to save
        """
        try:
            output_path = (
                self._config.output_dir / "frames" / f"display_{self._frame_count:06d}.raw"
            )
            with open(output_path, "wb") as f:
                f.write(buffer)
            self._frame_count += 1
        except Exception as e:
            logger.warning(f"Failed to record frame: {e}")
