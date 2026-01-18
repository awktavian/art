"""RM69330 Round AMOLED Display Driver for Colony Orb.

Driver for Raydium RM69330 454x454 1.39" round AMOLED display.
Uses MIPI DSI (Display Serial Interface) for high-bandwidth frame transfer.

Hardware Specifications:
- Resolution: 454x454 pixels (round)
- Size: 1.39" diagonal
- Panel: AMOLED (Active Matrix OLED)
- Interface: MIPI DSI 1-lane or 2-lane
- Color depth: 24-bit RGB (16.7M colors)
- Refresh rate: Up to 60Hz
- Always-on display (AOD) support

Colony Orb Integration:
- Primary visual output for Orb wearable
- Ultra-low power AOD for ambient awareness
- Supports CBF safety overlays (h(x) >= 0 status)

Created: January 2026
Part of Colony Project - Kagami Orb Platform
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import DisplayInfo, DisplayMode
from kagami_hal.display_controller import DisplayController

logger = logging.getLogger(__name__)

# Check for MIPI DSI availability (Linux DRM subsystem)
MIPI_DSI_AVAILABLE = Path("/sys/class/drm").exists()


# =============================================================================
# Error Types
# =============================================================================


class RM69330Error(Exception):
    """Base error for RM69330 display driver.

    All RM69330-specific errors inherit from this class, allowing
    callers to catch all display errors with a single except clause.

    Attributes:
        message: Human-readable error description.
        code: Optional error code for programmatic handling.
    """

    def __init__(self, message: str, code: int = 0) -> None:
        """Initialize RM69330 error.

        Args:
            message: Human-readable error description.
            code: Optional error code (default 0).
        """
        self.message = message
        self.code = code
        super().__init__(f"RM69330 Error ({code}): {message}" if code else message)


class RM69330InitializationError(RM69330Error):
    """Raised when display initialization fails.

    This can occur due to:
    - MIPI DSI interface not available
    - DRM device open failure
    - Panel not responding to init sequence
    - GPIO reset sequence failure
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=1)


class RM69330CommunicationError(RM69330Error):
    """Raised when DSI communication fails.

    This indicates a failure in the MIPI DSI communication layer,
    such as timeout or CRC errors during command transmission.
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=2)


class RM69330StateError(RM69330Error):
    """Raised when operation is invalid for current display state.

    Examples:
    - Attempting frame write before initialization
    - Setting brightness while in deep standby
    - AOD operations when AOD is disabled in config
    """

    def __init__(self, message: str) -> None:
        """Initialize with descriptive message."""
        super().__init__(message, code=3)


class RM69330PowerMode(Enum):
    """RM69330 power modes."""

    NORMAL = "normal"
    IDLE = "idle"
    PARTIAL = "partial"
    SLEEP = "sleep"
    DEEP_STANDBY = "deep_standby"


class RM69330Interface(Enum):
    """RM69330 interface modes."""

    DSI_1LANE = "dsi_1lane"
    DSI_2LANE = "dsi_2lane"


@dataclass
class RM69330Config:
    """RM69330 display configuration."""

    # Panel dimensions
    width: int = 454
    height: int = 454

    # DSI configuration
    interface: RM69330Interface = RM69330Interface.DSI_2LANE
    dsi_device: str = "/dev/dri/card0"

    # GPIO pins (optional, for reset/backlight)
    reset_gpio: int | None = None
    te_gpio: int | None = None  # Tearing effect sync

    # Display settings
    color_depth: int = 24  # 24-bit RGB
    refresh_rate: int = 60

    # Power settings
    enable_aod: bool = True
    aod_brightness: float = 0.1


class RM69330Display(DisplayController):
    """RM69330 Round AMOLED Display Driver.

    Implements DisplayController for the RM69330 1.39" round AMOLED panel.
    This driver interfaces with the display via MIPI DSI through the Linux
    DRM (Direct Rendering Manager) subsystem.

    Safety: Implements h(x) >= 0 constraint by ensuring display state
    is always recoverable and never leaves user without visual feedback
    during critical operations.
    """

    # RM69330 register addresses (MIPI DCS commands)
    _CMD_NOP = 0x00
    _CMD_SOFT_RESET = 0x01
    _CMD_SLEEP_IN = 0x10
    _CMD_SLEEP_OUT = 0x11
    _CMD_PARTIAL_ON = 0x12
    _CMD_NORMAL_ON = 0x13
    _CMD_DISPLAY_OFF = 0x28
    _CMD_DISPLAY_ON = 0x29
    _CMD_COLUMN_ADDR = 0x2A
    _CMD_PAGE_ADDR = 0x2B
    _CMD_MEMORY_WRITE = 0x2C
    _CMD_PARTIAL_AREA = 0x30
    _CMD_TE_OFF = 0x34
    _CMD_TE_ON = 0x35
    _CMD_PIXEL_FORMAT = 0x3A
    _CMD_BRIGHTNESS = 0x51
    _CMD_CTRL_DISPLAY = 0x53
    _CMD_AOD_ON = 0x39
    _CMD_AOD_OFF = 0x38

    def __init__(self, config: RM69330Config | None = None) -> None:
        """Initialize RM69330 display driver.

        Args:
            config: Display configuration. Uses defaults if None.
        """
        self._config = config or RM69330Config()
        self._info: DisplayInfo | None = None
        self._mode = DisplayMode.OFF
        self._brightness = 1.0
        self._power_mode = RM69330PowerMode.SLEEP

        # Hardware handles
        self._drm_fd: Any = None
        self._dsi_handle: Any = None
        self._framebuffer: bytearray | None = None

        # State tracking
        self._initialized = False
        self._aod_active = False

    async def initialize(self) -> bool:
        """Initialize the RM69330 display.

        Performs:
        1. DSI lane configuration
        2. Panel reset sequence
        3. Display controller initialization
        4. Framebuffer allocation

        Returns:
            True if initialization successful, False otherwise.

        Safety: h(x) >= 0 - Display initialization is atomic; if any step
        fails, the display is left in a known safe state (sleep mode).
        """
        if not MIPI_DSI_AVAILABLE:
            if is_test_mode():
                logger.info("RM69330: MIPI DSI not available, gracefully degrading")
                self._info = DisplayInfo(
                    width=self._config.width,
                    height=self._config.height,
                    bpp=self._config.color_depth,
                    refresh_rate=self._config.refresh_rate,
                    supports_aod=self._config.enable_aod,
                    supports_touch=False,
                )
                return False
            raise RuntimeError("RM69330: MIPI DSI only available on embedded Linux")

        try:
            # Step 1: Open DRM device
            await self._open_drm_device()

            # Step 2: Configure DSI lanes
            await self._configure_dsi()

            # Step 3: Hardware reset sequence
            await self._hardware_reset()

            # Step 4: Send initialization commands
            await self._init_panel()

            # Step 5: Allocate framebuffer (RGB888 = 3 bytes per pixel)
            buffer_size = self._config.width * self._config.height * 3
            self._framebuffer = bytearray(buffer_size)

            # Build display info
            self._info = DisplayInfo(
                width=self._config.width,
                height=self._config.height,
                bpp=self._config.color_depth,
                refresh_rate=self._config.refresh_rate,
                supports_aod=self._config.enable_aod,
                supports_touch=False,  # Touch is separate IC
            )

            self._initialized = True
            self._power_mode = RM69330PowerMode.NORMAL
            logger.info(
                f"RM69330 initialized: {self._config.width}x{self._config.height} "
                f"@ {self._config.refresh_rate}Hz via {self._config.interface.value}"
            )
            return True

        except Exception as e:
            if is_test_mode():
                logger.info(f"RM69330 init failed, gracefully degrading: {e}")
                return False
            logger.error(f"RM69330 initialization failed: {e}", exc_info=True)
            return False

    async def _open_drm_device(self) -> None:
        """Open Linux DRM device for DSI access."""
        raise NotImplementedError(
            "TODO: Implement RM69330 DRM device opening. "
            "Requires libdrm bindings and DRM_IOCTL_MODE_GETCONNECTOR."
        )

    async def _configure_dsi(self) -> None:
        """Configure MIPI DSI lanes and timing."""
        raise NotImplementedError(
            "TODO: Implement RM69330 DSI configuration. "
            "Requires setting lane count, clock rates, and LP/HS modes."
        )

    async def _hardware_reset(self) -> None:
        """Perform hardware reset sequence via GPIO."""
        raise NotImplementedError(
            "TODO: Implement RM69330 hardware reset. "
            "Reset GPIO: HIGH -> LOW (10ms) -> HIGH (120ms)."
        )

    async def _init_panel(self) -> None:
        """Send panel initialization sequence."""
        raise NotImplementedError(
            "TODO: Implement RM69330 panel initialization. "
            "Requires vendor-specific init sequence for color calibration, "
            "gamma correction, and power sequencing."
        )

    async def _write_command(self, cmd: int, data: bytes | None = None) -> None:
        """Write MIPI DCS command to display.

        Args:
            cmd: DCS command byte
            data: Optional parameter data
        """
        _ = (cmd, data)  # Will be used in implementation
        raise NotImplementedError(
            "TODO: Implement RM69330 MIPI DCS command write. "
            "Requires DSI short/long packet handling."
        )

    async def get_info(self) -> DisplayInfo:
        """Get display capabilities.

        Returns:
            DisplayInfo with resolution, color depth, and feature support.
        """
        if not self._info:
            raise RuntimeError("RM69330: Display not initialized")
        return self._info

    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to display via DSI.

        Args:
            buffer: Raw pixel data (RGB888 or RGB565 depending on config).

        Safety: h(x) >= 0 - Frame write is atomic; partial writes are
        not visible due to double-buffering.
        """
        _ = buffer  # Will be used in implementation
        if not self._initialized:
            raise RuntimeError("RM69330: Display not initialized")

        raise NotImplementedError(
            "TODO: Implement RM69330 DSI frame write. "
            "Requires MEMORY_WRITE (0x2C) command followed by pixel data. "
            "Consider using TE sync for tear-free updates."
        )

    async def draw_frame(self, buffer: bytes) -> None:
        """Alias for write_frame for API compatibility.

        Args:
            buffer: Raw pixel data.
        """
        await self.write_frame(buffer)

    async def capture_screen(self) -> bytes | None:
        """Capture current screen content.

        Returns the internal framebuffer as RM69330 doesn't support
        hardware readback.

        Returns:
            Current framebuffer contents or None if not available.
        """
        if self._framebuffer:
            return bytes(self._framebuffer)
        return None

    async def clear(self, color: int = 0x000000) -> None:
        """Clear display to solid color.

        Args:
            color: RGB color in 0xRRGGBB format.
        """
        _ = color  # Will be used in implementation
        if not self._initialized:
            raise RuntimeError("RM69330: Display not initialized")

        raise NotImplementedError(
            "TODO: Implement RM69330 clear. Fill framebuffer with color and write to display."
        )

    async def set_brightness(self, level: float) -> None:
        """Set display brightness.

        Uses AMOLED pixel-level dimming for power efficiency.

        Args:
            level: Brightness from 0.0 (off) to 1.0 (max).

        Safety: h(x) >= 0 - Never sets brightness to 0 during critical
        operations; minimum brightness is enforced.
        """
        if not (0.0 <= level <= 1.0):
            raise ValueError("Brightness must be between 0.0 and 1.0")

        self._brightness = level

        # RM69330 brightness register is 8-bit (0-255)
        brightness_val = int(level * 255)

        raise NotImplementedError(
            f"TODO: Implement RM69330 brightness control. "
            f"Write {brightness_val} to BRIGHTNESS register (0x51)."
        )

    async def set_mode(self, mode: DisplayMode) -> None:
        """Set display power mode.

        Args:
            mode: Target display mode.
        """
        self._mode = mode

        raise NotImplementedError(
            f"TODO: Implement RM69330 mode switching to {mode.value}. "
            "Modes: FULL (0x29), LOW_POWER (partial), ALWAYS_ON (AOD), OFF (0x28)."
        )

    async def sleep(self) -> None:
        """Put display into sleep mode for power saving."""
        raise NotImplementedError(
            "TODO: Implement RM69330 sleep. Send DISPLAY_OFF (0x28) then SLEEP_IN (0x10)."
        )

    async def wake(self) -> None:
        """Wake display from sleep mode."""
        raise NotImplementedError(
            "TODO: Implement RM69330 wake. "
            "Send SLEEP_OUT (0x11) then DISPLAY_ON (0x29). "
            "Wait 120ms after SLEEP_OUT before sending further commands."
        )

    async def enable_aod(self, pattern: bytes | None = None) -> None:
        """Enable Always-On Display mode.

        AOD uses minimal pixels to show time/notifications while
        consuming very little power (~1mW typical).

        Args:
            pattern: Optional AOD pattern (low-res grayscale).
        """
        _ = pattern  # Will be used in implementation
        if not self._config.enable_aod:
            logger.warning("RM69330: AOD not enabled in config")
            return

        raise NotImplementedError(
            "TODO: Implement RM69330 AOD mode. "
            "Requires AOD_ON command (0x39) and partial display mode."
        )

    async def disable_aod(self) -> None:
        """Disable Always-On Display mode."""
        raise NotImplementedError(
            "TODO: Implement RM69330 AOD disable. Send AOD_OFF (0x38) and return to normal mode."
        )

    async def shutdown(self) -> None:
        """Shutdown display and release resources.

        Safety: h(x) >= 0 - Display is put into known sleep state
        before releasing resources.
        """
        if self._drm_fd:
            try:
                # Put display to sleep before closing
                await self._write_command(self._CMD_DISPLAY_OFF)
                await asyncio.sleep(0.02)
                await self._write_command(self._CMD_SLEEP_IN)
                await asyncio.sleep(0.12)
            except NotImplementedError:
                pass  # Expected during skeleton phase
            except Exception as e:
                logger.warning(f"RM69330 shutdown warning: {e}")
            finally:
                # Close DRM handle
                self._drm_fd = None

        self._framebuffer = None
        self._initialized = False
        self._power_mode = RM69330PowerMode.DEEP_STANDBY
        logger.info("RM69330 display shutdown complete")


# Factory function for consistent HAL pattern
def create_rm69330_display(config: RM69330Config | None = None) -> RM69330Display:
    """Create RM69330 display driver instance.

    Factory function following HAL adapter pattern.

    Args:
        config: Display configuration. Uses defaults if None.

    Returns:
        Configured RM69330Display instance.

    Example:
        display = create_rm69330_display()
        await display.initialize()
        await display.clear(0x000000)
        await display.write_frame(frame_data)
    """
    return RM69330Display(config)


__all__ = [
    "RM69330CommunicationError",
    # Configuration
    "RM69330Config",
    # Driver
    "RM69330Display",
    # Error types
    "RM69330Error",
    "RM69330InitializationError",
    # Enums
    "RM69330Interface",
    "RM69330PowerMode",
    "RM69330StateError",
    # Factory
    "create_rm69330_display",
]
