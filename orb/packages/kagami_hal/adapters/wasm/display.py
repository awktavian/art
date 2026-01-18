"""WASM Display Adapter using Web APIs.

Implements DisplayController for WebAssembly using:
- Canvas API for rendering
- requestAnimationFrame for refresh
- Screen API for display info

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import DisplayInfo, DisplayMode
from kagami_hal.display_controller import DisplayController

logger = logging.getLogger(__name__)

# Check for Pyodide/WASM environment
WASM_AVAILABLE = False
try:
    import js
    from pyodide.ffi import create_proxy  # noqa: F401 - availability check

    WASM_AVAILABLE = True
except ImportError:
    pass


class WASMDisplay(DisplayController):
    """WASM display implementation using Canvas API."""

    def __init__(self, canvas_id: str = "kagami-canvas"):
        """Initialize WASM display.

        Args:
            canvas_id: HTML canvas element ID
        """
        self._canvas_id = canvas_id
        self._canvas: Any = None
        self._ctx: Any = None
        self._info: DisplayInfo | None = None
        self._mode = DisplayMode.FULL
        self._brightness = 1.0

    async def initialize(self) -> bool:
        """Initialize display."""
        if not WASM_AVAILABLE:
            if is_test_mode():
                logger.info("WASM display not available, gracefully degrading")
                return False
            raise RuntimeError("WASM display only available in browser")

        try:
            # Get canvas element
            self._canvas = js.document.getElementById(self._canvas_id)
            if not self._canvas:
                # Create canvas if not exists
                self._canvas = js.document.createElement("canvas")
                self._canvas.id = self._canvas_id
                js.document.body.appendChild(self._canvas)

            # Get 2D context
            self._ctx = self._canvas.getContext("2d")

            # Set size from window
            width = js.window.innerWidth or 1920
            height = js.window.innerHeight or 1080
            self._canvas.width = width
            self._canvas.height = height

            # Get refresh rate (approximate)
            refresh_rate = 60
            try:
                if hasattr(js.screen, "refreshRate"):
                    refresh_rate = js.screen.refreshRate or 60
            except Exception:
                pass

            self._info = DisplayInfo(
                width=int(width),
                height=int(height),
                bpp=32,
                refresh_rate=int(refresh_rate),
                supports_aod=False,
                supports_touch="ontouchstart" in js.window,
            )

            logger.info(f"✅ WASM display initialized: {width}x{height}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WASM display: {e}", exc_info=True)
            return False

    async def get_info(self) -> DisplayInfo:
        """Get display info."""
        if not self._info:
            raise RuntimeError("Display not initialized")
        return self._info

    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to canvas.

        Expects RGBA buffer matching canvas dimensions.
        """
        if not self._ctx or not self._info:
            raise RuntimeError("Display not initialized")

        try:
            # Create ImageData from buffer
            width = self._info.width
            height = self._info.height

            # Convert bytes to Uint8ClampedArray
            import js

            arr = js.Uint8ClampedArray.new(len(buffer))
            for i, b in enumerate(buffer):
                arr[i] = b

            image_data = js.ImageData.new(arr, width, height)
            self._ctx.putImageData(image_data, 0, 0)

        except Exception as e:
            logger.error(f"Failed to write frame: {e}")

    async def capture_screen(self) -> bytes | None:
        """Capture canvas content."""
        if not self._ctx or not self._info:
            return None

        try:
            image_data = self._ctx.getImageData(0, 0, self._info.width, self._info.height)
            # Convert Uint8ClampedArray to bytes
            return bytes(image_data.data.to_py())

        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return None

    async def clear(self, color: int = 0x000000) -> None:
        """Clear display to color."""
        if not self._ctx or not self._info:
            raise RuntimeError("Display not initialized")

        try:
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF

            self._ctx.fillStyle = f"rgb({r},{g},{b})"
            self._ctx.fillRect(0, 0, self._info.width, self._info.height)

        except Exception as e:
            logger.error(f"Failed to clear display: {e}")

    async def set_brightness(self, level: float) -> None:
        """Set display brightness via CSS filter."""
        if not self._canvas:
            raise RuntimeError("Display not initialized")

        try:
            self._brightness = max(0.0, min(1.0, level))
            self._canvas.style.filter = f"brightness({self._brightness})"

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

    async def shutdown(self) -> None:
        """Shutdown display."""
        self._ctx = None
        logger.info("✅ WASM display shutdown")
