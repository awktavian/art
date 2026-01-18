"""Android Display Adapter using SurfaceView.

Implements DisplayController for Android using Pyjnius (JNI).

Supports:
- Screen info via DisplayMetrics
- Brightness via WindowManager.LayoutParams
- Framebuffer access (SurfaceHolder) - limited performance in Python

Created: November 10, 2025
"""

from __future__ import annotations

import logging
import os

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import DisplayInfo, DisplayMode
from kagami_hal.display_controller import DisplayController

logger = logging.getLogger(__name__)

# Check for Android environment
ANDROID_AVAILABLE = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ

JNI_AVAILABLE = False
if ANDROID_AVAILABLE:
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        WindowManager = autoclass("android.view.WindowManager")
        pixel_format = autoclass("android.graphics.PixelFormat")
        JNI_AVAILABLE = True
    except ImportError:
        logger.warning("Pyjnius not available")


class AndroidDisplay(DisplayController):
    def __init__(self):
        self._info: DisplayInfo | None = None
        self._mode = DisplayMode.FULL
        self._brightness = 1.0
        self._activity = None
        self._window = None
        # Last written framebuffer (best-effort; enables capture_screen even when
        # a native Surface/Bitmap renderer isn't wired yet).
        self._buffer: bytes = b""
        self._warned_no_renderer = False

    async def initialize(self) -> bool:
        """Initialize Android display."""
        if not ANDROID_AVAILABLE:
            if is_test_mode():
                logger.info("Android Display not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("Android Display only available on Android")

        if not JNI_AVAILABLE:
            if is_test_mode():
                logger.info("Pyjnius not available, gracefully degrading")
                return False
            raise RuntimeError("Pyjnius not available")

        try:
            self._activity = PythonActivity.mActivity
            self._window = self._activity.getWindow()

            # Get Display Metrics
            metrics = autoclass("android.util.DisplayMetrics")()
            self._window.getWindowManager().getDefaultDisplay().getMetrics(metrics)

            width = metrics.widthPixels
            height = metrics.heightPixels
            # Estimate refresh rate (default 60)
            refresh = 60

            self._info = DisplayInfo(
                width=width,
                height=height,
                bpp=32,  # RGBA_8888
                refresh_rate=refresh,
                supports_aod=False,
                supports_touch=True,
            )

            logger.info(f"✅ Android display initialized: {width}x{height}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Android display: {e}", exc_info=True)
            return False

    async def get_info(self) -> DisplayInfo:
        if not self._info:
            raise RuntimeError("Display not initialized") from None
        return self._info

    async def write_frame(self, buffer: bytes) -> None:
        """Write frame to display.

        On Android, true framebuffer writes require a native path (Surface/Bitmap/Metal/Vulkan).
        Until that is wired, we store the last frame in-memory and (best-effort) degrade
        without raising at runtime. This keeps the HAL usable for headless/remote rendering
        and avoids crashing production flows on mobile.
        """
        if buffer:
            self._buffer = buffer

        # If we're not on Android (or JNI isn't present), treat as a no-op.
        if not ANDROID_AVAILABLE or not JNI_AVAILABLE:
            return
        if is_test_mode():
            return

        # Native renderer not implemented here; log once to avoid spam.
        if not self._warned_no_renderer:
            logger.warning(
                "AndroidDisplay.write_frame: native Surface/Bitmap renderer not wired; "
                "storing frames in-memory only."
            )
            self._warned_no_renderer = True
        return

    async def clear(self, color: int = 0x000000) -> None:
        """Clear the display.

        Implemented as clearing the retained framebuffer (and in the future, should
        draw a solid fill to the native surface).
        """
        self._buffer = b""
        if not ANDROID_AVAILABLE or not JNI_AVAILABLE:
            return
        if is_test_mode():
            return
        if not self._warned_no_renderer:
            logger.warning(
                "AndroidDisplay.clear: native renderer not wired; clearing in-memory buffer only."
            )
            self._warned_no_renderer = True
        return

    async def set_brightness(self, level: float) -> None:
        """Set screen brightness."""
        if not (0.0 <= level <= 1.0):
            raise ValueError("Brightness must be 0.0-1.0")

        self._brightness = level

        if self._activity:
            try:
                # Run on UI thread
                def _set_brightness():
                    lp = self._window.getAttributes()
                    lp.screenBrightness = float(level)
                    self._window.setAttributes(lp)

                self._activity.runOnUiThread(lambda: _set_brightness())
            except Exception as e:
                logger.error(f"Failed to set brightness: {e}")

    async def set_mode(self, mode: DisplayMode) -> None:
        self._mode = mode
        # Could map to FLAG_KEEP_SCREEN_ON based on mode

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

    async def shutdown(self) -> None:
        logger.info("Android display shut down")
