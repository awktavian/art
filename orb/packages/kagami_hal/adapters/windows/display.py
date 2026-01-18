"""Windows GDI Display Adapter.

Implements DisplayController for Windows using GDI (Graphics Device Interface).

Supports:
- Win32 GDI for rendering
- Multiple monitor support
- Screen capture

Common operations (clear, brightness, mode) are inherited from WindowsGDIDisplayBase.

Created: November 10, 2025
Refactored: December 22, 2025 - Use shared base class
"""

from __future__ import annotations

import logging

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
from kagami_hal.display_controller import DisplayController

logger = logging.getLogger(__name__)

# GDI constants
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0


class WindowsGDIDisplay(WindowsGDIDisplayBase, DisplayController):
    """Windows GDI display implementation.

    Inherits common operations from WindowsGDIDisplayBase.
    Implements DisplayController protocol.
    """

    def __init__(self):
        """Initialize GDI display."""
        super().__init__()
        self._mode = DisplayMode.FULL

    async def initialize(self) -> bool:
        """Initialize display."""
        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info("Windows GDI not available (wrong platform), gracefully degrading")
                return False
            raise RuntimeError("Windows GDI only available on Windows")

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
                refresh = 60  # Default

            self._info = DisplayInfo(
                width=width,
                height=height,
                bpp=bpp,
                refresh_rate=refresh,
                supports_aod=False,
                supports_touch=user32.GetSystemMetrics(94) != 0,  # SM_DIGITIZER
            )

            logger.info(
                f"✅ Windows GDI display initialized: {width}x{height} @ {bpp}bpp, {refresh}Hz"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Windows GDI display: {e}", exc_info=True)
            return False

    async def get_info(self) -> DisplayInfo:
        """Get display information."""
        if not self._info:
            raise RuntimeError("Display not initialized") from None
        return self._info

    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to display."""
        if not self._hdc or not self._info:
            raise RuntimeError("Display not initialized")

        info = self._info
        try:
            # Prepare BITMAPINFO
            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = info.width
            bmi.bmiHeader.biHeight = -info.height  # Top-down
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32  # Assume 32-bit buffer
            bmi.bmiHeader.biCompression = BI_RGB

            # Draw
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

    async def capture_screen(self) -> bytes | None:
        """Capture current screen content.

        Returns:
            Raw 32-bit BGRA bytes
        """
        if not self._hdc or not self._info:
            return None

        info = self._info
        try:
            # Create compatible DC
            mem_dc = gdi32.CreateCompatibleDC(self._hdc)

            # Create compatible bitmap
            bitmap = gdi32.CreateCompatibleBitmap(self._hdc, info.width, info.height)

            # Select bitmap into DC
            gdi32.SelectObject(mem_dc, bitmap)

            # Copy screen to bitmap
            gdi32.BitBlt(mem_dc, 0, 0, info.width, info.height, self._hdc, 0, 0, SRCCOPY)

            # Get bitmap bits
            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = info.width
            bmi.bmiHeader.biHeight = -info.height  # Top-down
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = BI_RGB

            buffer_size = info.width * info.height * 4
            buffer = ctypes.create_string_buffer(buffer_size)

            gdi32.GetDIBits(
                mem_dc, bitmap, 0, info.height, buffer, ctypes.byref(bmi), DIB_RGB_COLORS
            )

            # Cleanup
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)

            return bytes(buffer)

        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return None

    async def shutdown(self) -> None:
        """Shutdown display."""
        self._release_dc()
        logger.info("Windows GDI display shut down")
