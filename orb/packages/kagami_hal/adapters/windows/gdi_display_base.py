"""Windows GDI Display Base - Shared Display Operations.

Provides common GDI display operations shared by WindowsGDIDisplayAdapter
and WindowsGDIDisplayActuator to eliminate code duplication.

Created: December 22, 2025
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import DisplayInfo, DisplayMode

logger = logging.getLogger(__name__)

# Platform detection
WINDOWS_AVAILABLE = sys.platform == "win32"
GDI_AVAILABLE = False

# Pre-declare Windows-specific modules for type checking
ctypes: Any = None
wintypes: Any = None
user32: Any = None
gdi32: Any = None

if WINDOWS_AVAILABLE:
    try:
        import ctypes as _ctypes
        from ctypes import wintypes as _wintypes

        ctypes = _ctypes
        wintypes = _wintypes
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        GDI_AVAILABLE = True
    except (ImportError, AttributeError):
        logger.warning("Win32 GDI not available")


# ===== GDI BITMAP STRUCTURES =====
# Shared by display adapters and actuators

BITMAPINFOHEADER: Any = None
BITMAPINFO: Any = None

if GDI_AVAILABLE:

    class BITMAPINFOHEADER(ctypes.Structure):  # type: ignore[no-redef]
        """Windows BITMAPINFOHEADER structure for DIB operations."""

        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):  # type: ignore[no-redef]
        """Windows BITMAPINFO structure for DIB operations."""

        _fields_ = [
            ("bmiHeader", BITMAPINFOHEADER),
            ("bmiColors", wintypes.DWORD * 3),
        ]


class WindowsGDIDisplayBase:
    """Base class for Windows GDI display operations.

    Provides shared functionality for display adapters and actuators:
    - GDI device context management
    - Screen clearing
    - Brightness control (via WMI)
    - Display mode management

    Subclasses should:
    1. Call super().__init__() in their __init__
    2. Set self._hdc and self._info in their initialize() method
    3. Release resources in shutdown() by calling super().shutdown()
    """

    def __init__(self) -> None:
        """Initialize base display state."""
        self._hdc: Any = None  # Handle to device context
        self._info: DisplayInfo | None = None
        self._brightness: float = 1.0
        self._mode: DisplayMode = DisplayMode.NORMAL

    @property
    def is_initialized(self) -> bool:
        """Check if display is initialized."""
        return self._hdc is not None and self._info is not None

    async def clear(self, color: int = 0x000000) -> None:
        """Clear display to solid color.

        Args:
            color: RGB color as 0xRRGGBB

        Raises:
            RuntimeError: If display not initialized
        """
        if not self._hdc or not self._info:
            raise RuntimeError("Display not initialized")

        if is_test_mode():
            logger.debug(f"Test mode: clear(color=0x{color:06X})")
            return

        if not GDI_AVAILABLE:
            logger.warning("GDI not available for clear operation")
            return

        info = self._info

        try:
            # Extract RGB components
            r = color & 0xFF
            g = (color >> 8) & 0xFF
            b = (color >> 16) & 0xFF

            # GDI uses BGR format: 0x00BBGGRR
            color_ref = r | (g << 8) | (b << 16)

            # Create solid brush and fill
            brush = gdi32.CreateSolidBrush(color_ref)
            rect = wintypes.RECT(0, 0, info.width, info.height)
            user32.FillRect(self._hdc, ctypes.byref(rect), brush)
            gdi32.DeleteObject(brush)

        except Exception as e:
            logger.error(f"Failed to clear display: {e}")

    async def set_brightness(self, level: float) -> None:
        """Set display brightness via WMI.

        Args:
            level: Brightness level 0.0-1.0

        Raises:
            ValueError: If level out of range

        Note:
            Requires WMI module and may need admin privileges on some systems.
        """
        if not (0.0 <= level <= 1.0):
            raise ValueError("Brightness must be between 0.0 and 1.0")

        self._brightness = level

        if is_test_mode():
            logger.debug(f"Test mode: set_brightness({level})")
            return

        target_percent = int(level * 100)

        try:
            import wmi

            c = wmi.WMI(namespace="wmi")
            methods = c.WmiMonitorBrightnessMethods()

            if methods:
                method = methods[0]
                method.WmiSetBrightness(1, target_percent)
                logger.debug(f"Brightness set to {target_percent}% via WMI")
            else:
                logger.warning("No WMI brightness methods found")

        except ImportError:
            logger.warning("WMI module not found (pip install WMI)")
        except Exception as e:
            logger.error(f"Failed to set brightness via WMI: {e}")

    async def set_mode(self, mode: DisplayMode) -> None:
        """Set display power mode.

        Args:
            mode: Display power mode (NORMAL, DIMMED, OFF, etc.)
        """
        self._mode = mode
        logger.debug(f"Display mode set to: {mode.value}")

    def _release_dc(self) -> None:
        """Release GDI device context.

        Call this in subclass shutdown() methods.
        """
        if self._hdc and GDI_AVAILABLE:
            try:
                user32.ReleaseDC(0, self._hdc)
                logger.debug("Released GDI device context")
            except Exception as e:
                logger.error(f"Failed to release DC: {e}")
            finally:
                self._hdc = None


__all__ = [
    "BITMAPINFO",
    # GDI bitmap structures
    "BITMAPINFOHEADER",
    "GDI_AVAILABLE",
    "WINDOWS_AVAILABLE",
    "WindowsGDIDisplayBase",
    "ctypes",
    "gdi32",
    "user32",
    "wintypes",
]
