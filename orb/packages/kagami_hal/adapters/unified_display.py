"""Composite Display Controller that broadcasts to both Physical and Virtual displays."""

from __future__ import annotations

import base64
import logging

from kagami.core.events import get_unified_bus

from kagami_hal.data_types import DisplayInfo, DisplayMode
from kagami_hal.display_controller import DisplayController

logger = logging.getLogger(__name__)


class UnifiedDisplayAdapter(DisplayController):
    """
    Unified Display Adapter.

    Strategy:
    1. Writes to Physical Display Adapter (if provided)
    2. BROADCASTS frames via EventBus to AGUI (Virtual Display)
    """

    def __init__(self, physical_adapter: DisplayController | None = None):
        self.physical = physical_adapter
        self._bus = get_unified_bus()
        self._initialized = False

        # Default virtual dimensions if no physical display
        self._width = 1920
        self._height = 1080
        self._mode = DisplayMode.FULL

    async def initialize(self) -> bool:
        """Initialize both physical and virtual displays."""

        if self.physical:
            try:
                # Avoid double-initializing physical displays: if get_info works,
                # treat it as already initialized.
                info = None
                try:
                    info = await self.physical.get_info()
                except Exception:
                    info = None

                if info is None:
                    logger.info("Initializing physical display: %s", type(self.physical).__name__)
                    if await self.physical.initialize():
                        info = await self.physical.get_info()
                    else:
                        logger.warning(
                            "Physical display initialization failed, falling back to virtual-only"
                        )
                        self.physical = None

                if info is not None:
                    self._width = info.width
                    self._height = info.height
            except Exception as e:
                logger.error(f"Error initializing physical display: {e}")
                self.physical = None

        # 2. Initialize Virtual (AGUI)
        # Just emit the init event
        self._initialized = True
        await self._bus.publish(
            "hal.display.init",
            {
                "type": "hal.display.init",
                "width": self._width,
                "height": self._height,
                "mode": self._mode.value,
                "has_physical": self.physical is not None,
            },
        )

        return self._initialized

    async def get_info(self) -> DisplayInfo:
        if self.physical:
            return await self.physical.get_info()

        return DisplayInfo(
            width=self._width,
            height=self._height,
            bpp=32,
            refresh_rate=60,
            supports_aod=True,
            supports_touch=True,
        )

    async def write_frame(self, buffer: bytes) -> None:
        if not self._initialized:
            return

        # 1. Write to Physical
        if self.physical:
            try:
                await self.physical.write_frame(buffer)
            except Exception as e:
                logger.error(f"Physical display write failed: {e}")

        # 2. Broadcast to Virtual (AGUI)
        # Encode buffer to base64 for transport
        # Optimization: In full production, we might want to rate-limit this stream
        encoded = base64.b64encode(buffer).decode("utf-8")

        await self._bus.publish(
            "hal.display.frame",
            {
                "type": "hal.display.frame",
                "buffer": encoded,
                "format": "rgba32",
                "width": self._width,
                "height": self._height,
            },
        )

    async def clear(self, color: int = 0x000000) -> None:
        if not self._initialized:
            return

        # 1. Physical
        if self.physical:
            await self.physical.clear(color)

        # 2. Virtual
        await self._bus.publish(
            "hal.display.clear",
            {
                "type": "hal.display.clear",
                "color": color,
            },
        )

    async def set_brightness(self, level: float) -> None:
        if self.physical:
            await self.physical.set_brightness(level)

        await self._bus.publish(
            "hal.display.control",
            {
                "type": "hal.display.control",
                "command": "set_brightness",
                "value": level,
            },
        )

    async def set_mode(self, mode: DisplayMode) -> None:
        self._mode = mode
        if self.physical:
            await self.physical.set_mode(mode)

        await self._bus.publish(
            "hal.display.control",
            {
                "type": "hal.display.control",
                "command": "set_mode",
                "value": mode.value,
            },
        )

    async def capture_screen(self) -> bytes | None:
        # Prefer physical capture
        if self.physical:
            return await self.physical.capture_screen()
        return None

    async def shutdown(self) -> None:
        self._initialized = False
        if self.physical:
            await self.physical.shutdown()

        await self._bus.publish(
            "hal.display.shutdown",
            {
                "type": "hal.display.shutdown",
            },
        )
