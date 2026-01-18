"""macOS CoreGraphics Display Adapter.

Implements DisplayController for macOS using CoreGraphics.

Created: November 10, 2025
"""

from __future__ import annotations

import logging
import sys

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import DisplayInfo, DisplayMode

logger = logging.getLogger(__name__)

# Check if running on macOS
MACOS_AVAILABLE = sys.platform == "darwin"

Quartz = None
cv2 = None
np = None

if MACOS_AVAILABLE:
    try:
        import Quartz  # type: ignore[no-redef]

        COREGRAPHICS_AVAILABLE = True
    except ImportError:
        Quartz = None
        COREGRAPHICS_AVAILABLE = False
        logger.debug(
            "CoreGraphics (Quartz) not available. Install with: pip install pyobjc-framework-Quartz"
        )

    try:
        import cv2  # type: ignore[assignment]
        import numpy as np  # type: ignore[assignment]

        CV2_AVAILABLE = True
    except ImportError:
        cv2 = None
        np = None
        CV2_AVAILABLE = False
        logger.debug("OpenCV not available. Install with: pip install opencv-python numpy")
else:
    COREGRAPHICS_AVAILABLE = False
    CV2_AVAILABLE = False


class MacOSCoreGraphicsDisplay:
    """macOS CoreGraphics display implementation."""

    def __init__(self) -> None:
        """Initialize CoreGraphics display."""
        self._info: DisplayInfo | None = None
        self._mode: DisplayMode = DisplayMode.FULL
        self._brightness: float = 1.0
        self._display_id: int | None = None
        self._window_name = "K os Virtual Display"

    async def initialize(self) -> bool:
        """Initialize display."""
        if not MACOS_AVAILABLE:
            if is_test_mode():
                logger.info("CoreGraphics not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("CoreGraphics only available on macOS")

        if not COREGRAPHICS_AVAILABLE:
            if is_test_mode():
                logger.info("CoreGraphics not available (missing dependency), gracefully degrading")
                return False
            raise RuntimeError(
                "CoreGraphics not available. Install: pip install pyobjc-framework-Quartz\n"
                "Or run in test mode: KAGAMI_BOOT_MODE=test"
            )

        try:
            # Get main display
            self._display_id = Quartz.CGMainDisplayID()  # type: ignore[attr-defined]

            # Get display bounds
            bounds = Quartz.CGDisplayBounds(self._display_id)  # type: ignore[attr-defined]
            width = int(bounds.size.width)
            height = int(bounds.size.height)

            # Get bits per pixel
            mode = Quartz.CGDisplayCopyDisplayMode(self._display_id)  # type: ignore[attr-defined]
            bpp = 32  # Modern displays are always 32-bit

            # Get refresh rate
            refresh = Quartz.CGDisplayModeGetRefreshRate(mode)  # type: ignore[attr-defined]
            if refresh == 0:
                refresh = 60  # Default for non-CRT displays

            self._info = DisplayInfo(
                width=width,
                height=height,
                bpp=bpp,
                refresh_rate=int(refresh),
                supports_aod=False,
                supports_touch=False,
            )

            # NO cv2.namedWindow() or cv2.imshow() - they require tkinter on macOS
            # Frames are written to disk instead via write_frame()

            logger.info(f"✅ CoreGraphics initialized: {width}x{height} @ {int(refresh)}Hz")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize CoreGraphics: {e}", exc_info=True)
            return False

    async def get_info(self) -> DisplayInfo:
        """Get display info."""
        if not self._info:
            raise RuntimeError("Display not initialized") from None
        return self._info

    async def write_frame(self, buffer: bytes, save_path: str | None = None) -> None:
        """Write frame buffer to display.

        NO cv2.imshow() - it requires tkinter on macOS and conflicts with Genesis.
        Frames are saved to disk instead for verification.

        Args:
            buffer: Encoded image (PNG/JPG) or raw RGB/RGBA bytes
            save_path: Optional path to save frame (defaults to /tmp/hal_frame_latest.png)
        """
        if not CV2_AVAILABLE:
            logger.debug(f"Frame write: {len(buffer)} bytes (OpenCV unavailable)")
            return

        try:
            # Decode image from buffer
            nparr = np.frombuffer(buffer, np.uint8)  # type: ignore[attr-defined]
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)  # type: ignore[attr-defined]

            if img is None:
                logger.debug("Could not decode frame as image")
                return

            # Save to disk instead of displaying (NO cv2.imshow - requires tkinter!)
            output_path = save_path or "/tmp/hal_frame_latest.png"
            cv2.imwrite(output_path, img)  # type: ignore[attr-defined]

            logger.debug(f"Frame written: {len(buffer)} bytes → {output_path}")

        except Exception as e:
            logger.error(f"Failed to write frame: {e}")

    async def capture_screen(self) -> bytes | None:
        """Capture current screen content.

        Returns:
            Raw 32-bit BGRA bytes (compatible with OpenCV/numpy)
        """
        if not COREGRAPHICS_AVAILABLE or self._display_id is None:
            return None

        try:
            # Create image from display
            image_ref = Quartz.CGDisplayCreateImage(self._display_id)  # type: ignore[attr-defined]
            if not image_ref:
                return None

            # Get image data
            Quartz.CGImageGetWidth(image_ref)  # type: ignore[attr-defined]
            Quartz.CGImageGetHeight(image_ref)  # type: ignore[attr-defined]

            # Get data provider
            provider = Quartz.CGImageGetDataProvider(image_ref)  # type: ignore[attr-defined]
            data = Quartz.CGDataProviderCopyData(provider)  # type: ignore[attr-defined]

            # Convert to bytes
            # Note: CGImage data is usually BGRA or RGBA depending on internal format
            # We return raw bytes here
            return data

        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return None

    async def clear(self, color: int = 0x000000) -> None:
        """Clear display to color."""
        # Would use CGContextFillRect in production
        logger.debug(f"Clear display: 0x{color:06X}")

    async def set_brightness(self, level: float) -> None:
        """Set display brightness."""
        if self._display_id is None:
            raise RuntimeError("Display not initialized")

        try:
            # Set brightness via CoreGraphics
            Quartz.CGDisplaySetBrightness(self._display_id, level)  # type: ignore[attr-defined]
            self._brightness = level

            logger.debug(f"Brightness set: {level:.1%}")

        except Exception as e:
            logger.warning(f"Failed to set brightness: {e}")

    async def set_mode(self, mode: DisplayMode) -> None:
        """Set display power mode."""
        self._mode = mode

        if mode == DisplayMode.FULL:
            await self.set_brightness(1.0)
        elif mode == DisplayMode.LOW_POWER:
            await self.set_brightness(0.5)
        elif mode == DisplayMode.ALWAYS_ON:
            await self.set_brightness(0.2)
        elif mode == DisplayMode.OFF:
            await self.set_brightness(0.0)

        logger.debug(f"Display mode: {mode.value}")

    async def shutdown(self) -> None:
        """Shutdown display."""
        logger.info("✅ CoreGraphics shutdown")
