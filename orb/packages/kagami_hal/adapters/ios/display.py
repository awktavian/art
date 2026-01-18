"""iOS Display Adapter using UIKit.

Implements DisplayController for iOS using UIKit via PyObjC.
Grounds in objective science: Accesses UIScreen mainScreen for physical dimensions and brightness.

Created: November 10, 2025
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import DisplayInfo, DisplayMode
from kagami_hal.display_controller import DisplayController

logger = logging.getLogger(__name__)

IOS_AVAILABLE = sys.platform == "darwin" and (
    os.uname().machine.startswith("iP") or os.environ.get("KAGAMI_PLATFORM") == "ios"
)


class iOSDisplay(DisplayController):
    """iOS Display Adapter."""

    def __init__(self) -> None:
        self._info: DisplayInfo | None = None
        self._mode = DisplayMode.FULL
        self._brightness = 1.0
        self._screen: Any = None
        self._buffer: bytes = b""
        self._warned_no_renderer = False

    async def initialize(self) -> bool:
        """Initialize iOS display connection."""
        if not IOS_AVAILABLE:
            if is_test_mode():
                logger.info("iOS Display not available, gracefully degrading")
                return False
            raise RuntimeError("iOS Display only available on iOS")

        try:
            from UIKit import UIScreen

            self._screen = UIScreen.mainScreen()
            bounds = self._screen.bounds()
            scale = self._screen.scale()

            # Native resolution
            width = int(bounds.size.width * scale)
            height = int(bounds.size.height * scale)

            self._info = DisplayInfo(
                width=width,
                height=height,
                bpp=32,  # Standard RGBA
                refresh_rate=60,  # ProMotion devices might be 120, but 60 is safe base
                supports_aod=False,
                supports_touch=True,
            )
            self._brightness = self._screen.brightness()

            logger.info(f"✅ iOS display initialized: {width}x{height} @ {scale}x")
            return True

        except ImportError:
            logger.error("UIKit not found. Ensure PyObjC is installed or running on iOS.")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize iOS display: {e}")
            return False

    async def get_info(self) -> DisplayInfo:
        if not self._info:
            raise RuntimeError("Display not initialized")
        return self._info

    async def write_frame(self, buffer: bytes) -> None:
        """Write framebuffer (best-effort).

        On iOS, direct framebuffer writes are restricted and typically require rendering via
        a UIView/UIImageView or a Metal layer. Until a native rendering pipeline is wired,
        we store the last frame in-memory so the HAL can operate in headless/remote modes
        without crashing.
        """
        if buffer:
            self._buffer = buffer
        if not IOS_AVAILABLE:
            return
        if is_test_mode():
            return
        if not self._warned_no_renderer:
            logger.warning(
                "iOSDisplay.write_frame: native UIKit/Metal renderer not wired; "
                "storing frames in-memory only."
            )
            self._warned_no_renderer = True
        return

    async def clear(self, color: int = 0x000000) -> None:
        self._buffer = b""
        if not IOS_AVAILABLE:
            return
        if is_test_mode():
            return
        if not self._warned_no_renderer:
            logger.warning(
                "iOSDisplay.clear: native UIKit/Metal renderer not wired; clearing buffer only."
            )
            self._warned_no_renderer = True
        return

    async def capture_screen(self) -> bytes | None:
        """Capture current screen content (best-effort).

        If a native capture path isn't available, returns the last written framebuffer
        (or a blank frame if nothing has been written).
        """
        if self._buffer:
            return self._buffer
        if self._info is None:
            return None
        return b"\x00" * (self._info.width * self._info.height * 4)

    async def set_brightness(self, level: float) -> None:
        """Set screen brightness."""
        if not (0.0 <= level <= 1.0):
            raise ValueError("Brightness must be 0.0-1.0")

        self._brightness = level
        if self._screen:
            # UIScreen.setBrightness_ is deprecated/restricted in some contexts,
            # but standard API for app brightness.
            try:
                self._screen.setBrightness_(level)
            except Exception as e:
                logger.warning(f"Could not set brightness: {e}")

    async def set_mode(self, mode: DisplayMode) -> None:
        self._mode = mode

    async def shutdown(self) -> None:
        logger.info("iOS display shut down")
