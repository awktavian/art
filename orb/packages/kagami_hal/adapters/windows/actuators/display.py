"""Windows GDI Display Actuator.

Implements display output using Windows GDI (Graphics Device Interface).

Provides frame rendering via GDI. Common operations (clear, brightness, mode)
are inherited from WindowsGDIDisplayBase.

Created: December 15, 2025
Refactored: December 22, 2025 - Use shared base class
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.adapters.windows.gdi_display_base import (
    BITMAPINFO,
    BITMAPINFOHEADER,
    GDI_AVAILABLE,
    WINDOWS_AVAILABLE,
    WindowsGDIDisplayBase,
    ctypes,
    gdi32,
    user32,
)
from kagami_hal.data_types import DisplayInfo, DisplayMode

logger = logging.getLogger(__name__)

# GDI constants
DIB_RGB_COLORS = 0
SRCCOPY = 0x00CC0020


class WindowsGDIDisplayActuator(WindowsGDIDisplayBase):
    """Windows GDI display actuator implementation.

    Implements IActuator protocol for display output.
    Inherits common operations from WindowsGDIDisplayBase.
    """

    def __init__(self):
        """Initialize GDI display actuator."""
        super().__init__()
        self._mode = DisplayMode.FULL

    async def initialize(self, config: dict[str, Any] | None = None) -> bool:
        """Initialize display actuator.

        Returns:
            True if initialization successful
        """
        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info(
                    "Windows GDI display not available (wrong platform), gracefully degrading"
                )
                return False
            raise RuntimeError("Windows GDI display only available on Windows")

        if not GDI_AVAILABLE:
            if is_test_mode():
                logger.info("Windows GDI not available (missing dependency), gracefully degrading")
                return False
            raise RuntimeError("Windows GDI not available")

        try:
            # Get primary display device context
            self._hdc = user32.GetDC(0)

            # Get display dimensions
            width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            height = user32.GetSystemMetrics(1)  # SM_CYSCREEN

            # Get bits per pixel
            bpp = gdi32.GetDeviceCaps(self._hdc, 12)  # BITSPIXEL

            # Get refresh rate
            refresh = gdi32.GetDeviceCaps(self._hdc, 116)  # VREFRESH
            if refresh == 0 or refresh == 1:
                refresh = 60

            self._info = DisplayInfo(
                width=width,
                height=height,
                bpp=bpp,
                refresh_rate=refresh,
                supports_aod=False,
                supports_touch=user32.GetSystemMetrics(94) != 0,  # SM_DIGITIZER
            )

            logger.info(
                f"✅ GDI display actuator initialized: {width}x{height} @ {bpp}bpp, {refresh}Hz"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize GDI display actuator: {e}", exc_info=True)
            return False

    async def actuate(self, data: bytes) -> None:
        """Write frame buffer to display.

        Args:
            data: Raw frame buffer bytes (RGBA or BGRA)

        Raises:
            RuntimeError: If not initialized or write fails
        """
        await self.write_frame(data)

    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to display.

        Args:
            buffer: Raw frame buffer (32-bit BGRA)
        """
        if not self._hdc or not self._info:
            raise RuntimeError("Display not initialized")

        info = self._info

        try:
            # Prepare BITMAPINFO (using shared structures from gdi_display_base)
            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = info.width
            bmi.bmiHeader.biHeight = -info.height  # Top-down (negative = top-to-bottom)
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0  # BI_RGB

            # Draw with StretchDIBits
            gdi32.StretchDIBits(
                self._hdc,
                0,
                0,
                info.width,
                info.height,
                0,
                0,
                info.width,
                info.height,
                buffer,
                ctypes.byref(bmi),
                DIB_RGB_COLORS,
                SRCCOPY,
            )

        except Exception as e:
            logger.error(f"Failed to write frame: {e}")
            raise RuntimeError(f"Frame write failed: {e}") from e

    async def get_info(self) -> DisplayInfo:
        """Get display information.

        Returns:
            DisplayInfo with capabilities
        """
        if not self._info:
            raise RuntimeError("Display not initialized")
        return self._info

    async def shutdown(self) -> None:
        """Release display resources."""
        self._release_dc()
        logger.info("✅ GDI display actuator shutdown")
