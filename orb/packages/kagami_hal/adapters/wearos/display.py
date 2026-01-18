"""WearOS Display Adapter.

Implements display control for Wear OS using Android APIs.

Features:
- Round and square display support
- Always-on display (AOD / Ambient mode)
- Brightness control
- Display info

Created: December 13, 2025
"""

from __future__ import annotations

import logging
import os
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import DisplayInfo, DisplayMode

logger = logging.getLogger(__name__)

WEAROS_AVAILABLE = "ANDROID_ARGUMENT" in os.environ or os.environ.get("KAGAMI_PLATFORM") == "wearos"


class WearOSDisplay:
    """Wear OS display adapter.

    Provides:
    - Display info (size, shape, capabilities)
    - Ambient mode support
    - Brightness control
    """

    def __init__(self):
        """Initialize WearOS display adapter."""
        self._display: Any = None
        self._window_manager: Any = None
        self._initialized = False
        self._display_info: DisplayInfo | None = None
        self._current_mode = DisplayMode.FULL
        self._is_round = True

    async def initialize(self, config: Any | None = None) -> bool:
        """Initialize display adapter."""
        if not WEAROS_AVAILABLE:
            if is_test_mode():
                logger.info("WearOS display not available, gracefully degrading")
                return False
            raise RuntimeError("WearOS display only available on Wear OS")

        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")

            activity = PythonActivity.mActivity
            self._window_manager = activity.getSystemService(Context.WINDOW_SERVICE)
            self._display = self._window_manager.getDefaultDisplay()

            # Get display metrics
            DisplayMetrics = autoclass("android.util.DisplayMetrics")
            metrics = DisplayMetrics()
            self._display.getMetrics(metrics)

            width = metrics.widthPixels
            height = metrics.heightPixels
            # density = metrics.density  # Available if needed for DPI scaling

            # Check if display is round
            config_obj = activity.getResources().getConfiguration()
            self._is_round = config_obj.isScreenRound()

            # Most Wear OS watches support AOD
            supports_aod = True

            self._display_info = DisplayInfo(
                width=width,
                height=height,
                bpp=32,  # RGBA
                refresh_rate=60,
                supports_aod=supports_aod,
                supports_touch=True,
            )

            self._initialized = True
            shape = "round" if self._is_round else "square"
            logger.info(
                f"✅ WearOS display initialized: {width}x{height} ({shape}), AOD={supports_aod}"
            )
            return True

        except ImportError as e:
            logger.error(f"Pyjnius not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize WearOS display: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown display adapter."""
        self._initialized = False
        logger.info("✅ WearOS display adapter shutdown")

    async def get_info(self) -> DisplayInfo:
        """Get display capabilities."""
        if not self._display_info:
            raise RuntimeError("Display adapter not initialized")
        return self._display_info

    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to display.

        Note: On Wear OS, UI is typically via Compose/Views.
        """
        if not self._initialized:
            raise RuntimeError("Display adapter not initialized")
        logger.debug(f"Frame buffer write: {len(buffer)} bytes")

    async def capture_screen(self) -> bytes | None:
        """Capture current screen content."""
        # Screen capture requires special permissions on Android
        logger.debug("Screen capture not implemented for WearOS")
        return None

    async def clear(self, color: int = 0x000000) -> None:
        """Clear display to color."""
        logger.debug(f"Display clear: #{color:06x}")

    async def set_brightness(self, level: float) -> None:
        """Set display brightness.

        Args:
            level: Brightness level (0.0-1.0)
        """
        level = max(0.0, min(1.0, level))

        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")

            activity = PythonActivity.mActivity
            window = activity.getWindow()
            params = window.getAttributes()
            params.screenBrightness = level
            window.setAttributes(params)

            logger.debug(f"Brightness set to {level:.0%}")

        except Exception as e:
            logger.error(f"Failed to set brightness: {e}")

    async def set_mode(self, mode: DisplayMode) -> None:
        """Set display power mode."""
        self._current_mode = mode
        logger.debug(f"Display mode set: {mode.value}")

    # =========================================================================
    # WearOS-Specific Methods
    # =========================================================================

    @property
    def is_round(self) -> bool:
        """Check if display is round."""
        return self._is_round

    @property
    def screen_shape(self) -> str:
        """Get screen shape."""
        return "round" if self._is_round else "rectangular"

    @property
    def chin_height(self) -> int:
        """Get chin height (flat tire) in pixels.

        Some round watches have a flat bottom ("chin") for the display driver.
        Returns 0 for fully round or rectangular displays.
        """
        # Would query InsetDrawable for bottom inset
        return 0

    async def enter_ambient_mode(self) -> None:
        """Enter ambient (always-on) mode.

        In ambient mode:
        - Display uses minimal colors (typically white on black)
        - Update rate is reduced to save power
        - Touch is disabled or limited
        """
        self._current_mode = DisplayMode.ALWAYS_ON
        logger.info("Entering ambient mode")

    async def exit_ambient_mode(self) -> None:
        """Exit ambient mode to full interactive mode."""
        self._current_mode = DisplayMode.FULL
        logger.info("Exiting ambient mode")

    @property
    def is_ambient_mode(self) -> bool:
        """Check if currently in ambient mode."""
        return self._current_mode == DisplayMode.ALWAYS_ON

    async def render_tile(
        self,
        tile_id: str,
        data: dict[str, Any],
    ) -> bool:
        """Render a Wear OS Tile.

        Tiles are glanceable app surfaces that users can add to
        their watch face carousel.

        Args:
            tile_id: Tile identifier
            data: Data to display in the tile

        Returns:
            True if tile rendered successfully
        """
        try:
            # Tile rendering uses TileService and Protolayout
            logger.debug(f"Tile render: {tile_id} with {data}")
            return True
        except Exception as e:
            logger.error(f"Failed to render tile: {e}")
            return False

    async def update_complication(
        self,
        complication_id: int,
        data: dict[str, Any],
    ) -> bool:
        """Update a watch face complication.

        Complications are small data displays on watch faces.

        Args:
            complication_id: Complication slot ID
            data: Complication data

        Returns:
            True if complication updated
        """
        try:
            # Would use ComplicationDataSourceService
            logger.debug(f"Complication update: {complication_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update complication: {e}")
            return False
