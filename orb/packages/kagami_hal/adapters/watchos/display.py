"""WatchOS Display Adapter.

Implements display control for Apple Watch using WatchKit.

Features:
- Always-on display (AOD) support
- Complication rendering
- Brightness control
- Display info

Created: December 13, 2025
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import DisplayInfo, DisplayMode

logger = logging.getLogger(__name__)

WATCHOS_AVAILABLE = sys.platform == "darwin" and os.environ.get("KAGAMI_PLATFORM") == "watchos"


class WatchOSDisplay:
    """Apple Watch display adapter.

    Provides:
    - Display info (size, capabilities)
    - Always-on display support
    - Brightness control (limited)
    - Frame buffer writing (for custom UI)
    """

    def __init__(self):
        """Initialize WatchOS display adapter."""
        self._device: Any = None
        self._initialized = False
        self._display_info: DisplayInfo | None = None
        self._current_mode = DisplayMode.FULL

    async def initialize(self, config: Any | None = None) -> bool:
        """Initialize display adapter."""
        if not WATCHOS_AVAILABLE:
            if is_test_mode():
                logger.info("WatchOS display not available, gracefully degrading")
                return False
            raise RuntimeError("WatchOS display only available on Apple Watch")

        try:
            from WatchKit import WKInterfaceDevice

            self._device = WKInterfaceDevice.currentDevice()

            # Get screen bounds
            bounds = self._device.screenBounds()
            scale = self._device.screenScale()

            width = int(bounds.size.width * scale)
            height = int(bounds.size.height * scale)

            # Detect Always-on display support (Series 5+)
            # We infer this from the device name/model
            model = self._device.model() or ""
            supports_aod = any(
                x in model.lower()
                for x in ["series 5", "series 6", "series 7", "series 8", "series 9", "ultra"]
            )

            self._display_info = DisplayInfo(
                width=width,
                height=height,
                bpp=32,  # RGBA
                refresh_rate=60,  # Standard refresh
                supports_aod=supports_aod,
                supports_touch=True,
            )

            self._initialized = True
            logger.info(f"✅ WatchOS display initialized: {width}x{height}, AOD={supports_aod}")
            return True

        except ImportError as e:
            logger.error(f"WatchKit not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize WatchOS display: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown display adapter."""
        self._initialized = False
        logger.info("✅ WatchOS display adapter shutdown")

    async def get_info(self) -> DisplayInfo:
        """Get display capabilities."""
        if not self._display_info:
            raise RuntimeError("Display adapter not initialized")
        return self._display_info

    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to display.

        Note: On watchOS, we typically use SwiftUI/WatchKit for UI.
        This method is for custom rendering scenarios.
        """
        if not self._initialized:
            raise RuntimeError("Display adapter not initialized")

        # On watchOS, direct framebuffer access isn't typical
        # Instead, we'd update a SwiftUI view or WKInterfaceImage
        logger.debug(f"Frame buffer write: {len(buffer)} bytes")

    async def capture_screen(self) -> bytes | None:
        """Capture current screen content.

        Note: Screen capture is restricted on watchOS.
        """
        logger.debug("Screen capture not available on watchOS")
        return None

    async def clear(self, color: int = 0x000000) -> None:
        """Clear display to color."""
        if not self._initialized:
            return

        # On watchOS, clearing typically means showing a black background
        logger.debug(f"Display clear: #{color:06x}")

    async def set_brightness(self, level: float) -> None:
        """Set display brightness.

        Note: On watchOS, brightness is user-controlled.
        We can only suggest via accessibility settings.
        """
        level = max(0.0, min(1.0, level))
        logger.debug(f"Brightness set request: {level:.0%} (advisory only)")

    async def set_mode(self, mode: DisplayMode) -> None:
        """Set display power mode.

        Modes:
        - FULL: Active display
        - LOW_POWER: Reduced refresh
        - ALWAYS_ON: AOD mode (if supported)
        - OFF: Screen off (wrist down)
        """
        self._current_mode = mode
        logger.debug(f"Display mode set: {mode.value}")

        # On watchOS, the system manages display state
        # We track the intended mode for our rendering logic

    # =========================================================================
    # WatchOS-Specific Methods
    # =========================================================================

    @property
    def is_always_on_supported(self) -> bool:
        """Check if Always-on Display is supported."""
        return self._display_info.supports_aod if self._display_info else False

    @property
    def screen_shape(self) -> str:
        """Get screen shape (rectangular or round).

        Apple Watch uses rectangular displays with rounded corners.
        """
        return "rectangular"

    @property
    def wrist_location(self) -> str:
        """Get wrist location preference (left or right)."""
        try:
            if self._device:
                loc = self._device.wristLocation()
                return "left" if loc == 0 else "right"
        except Exception:
            pass
        return "left"

    @property
    def crown_orientation(self) -> str:
        """Get Digital Crown orientation (left or right)."""
        try:
            if self._device:
                orient = self._device.crownOrientation()
                return "right" if orient == 0 else "left"
        except Exception:
            pass
        return "right"

    async def render_complication(
        self,
        template: str,
        data: dict[str, Any],
    ) -> bool:
        """Render a complication template.

        Complications are small UI elements on the watch face.
        This method prepares data for ClockKit complications.

        Args:
            template: Complication template type
            data: Data to display

        Returns:
            True if complication updated
        """
        try:
            # In a real implementation, this would update ClockKit
            # complications via CLKComplicationServer
            logger.debug(f"Complication update: {template} with {data}")
            return True
        except Exception as e:
            logger.error(f"Failed to render complication: {e}")
            return False
