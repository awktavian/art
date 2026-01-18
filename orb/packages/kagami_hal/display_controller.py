"""Display Controller HAL for K os.

Unified interface for display management across platforms.

Supported:
- Linux: Framebuffer (/dev/fb0)
- macOS: CoreGraphics
- Embedded: Direct display controller (OLED/LCD)

Features:
- Frame buffer management
- Brightness control
- Low-power always-on display mode
- Rotation/scaling

Created: November 10, 2025
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# Import from shared data_types to avoid duplicate definitions and LSP violations
from kagami_hal.data_types import DisplayInfo, DisplayMode


class DisplayController(ABC):
    """Abstract display controller interface."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize display.

        Returns:
            True if successful
        """

    @abstractmethod
    async def get_info(self) -> DisplayInfo:
        """Get display capabilities."""

    @abstractmethod
    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to display.

        Args:
            buffer: Raw pixel data (format depends on bpp)
        """

    @abstractmethod
    async def capture_screen(self) -> bytes | None:
        """Capture current screen content.

        Returns:
            Raw RGB/RGBA bytes of the screen content, or None if failed.
            Format should match DisplayInfo.bpp (usually 32-bit RGBA).
        """

    @abstractmethod
    async def clear(self, color: int = 0x000000) -> None:
        """Clear display to color.

        Args:
            color: RGB color (0xRRGGBB)
        """

    @abstractmethod
    async def set_brightness(self, level: float) -> None:
        """Set display brightness.

        Args:
            level: Brightness (0.0-1.0)
        """

    @abstractmethod
    async def set_mode(self, mode: DisplayMode) -> None:
        """Set display power mode.

        Args:
            mode: Display mode
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown display."""
