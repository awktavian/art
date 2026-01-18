"""WatchOS Input Adapter.

Implements input handling for Apple Watch using WatchKit.

Features:
- Digital Crown rotation and press
- Side button press
- Touch gestures
- Taptic Engine haptic feedback

Created: December 13, 2025
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import InputEvent, InputType, KeyCode

logger = logging.getLogger(__name__)

WATCHOS_AVAILABLE = sys.platform == "darwin" and os.environ.get("KAGAMI_PLATFORM") == "watchos"


class WatchOSInput:
    """Apple Watch input adapter.

    Provides:
    - Digital Crown rotation tracking
    - Side button events
    - Touch gestures
    - Taptic Engine haptic feedback (Crown, notifications)
    """

    def __init__(self):
        """Initialize WatchOS input adapter."""
        self._device: Any = None
        self._initialized = False
        self._subscribers: dict[InputType, list[Callable[[InputEvent], Awaitable[None]]]] = {}
        self._crown_value: float = 0.0
        self._haptic_engine: Any = None

    async def initialize(self, config: Any | None = None) -> bool:
        """Initialize input adapter."""
        if not WATCHOS_AVAILABLE:
            if is_test_mode():
                logger.info("WatchOS input not available, gracefully degrading")
                return False
            raise RuntimeError("WatchOS input only available on Apple Watch")

        try:
            from WatchKit import WKInterfaceDevice

            self._device = WKInterfaceDevice.currentDevice()

            self._initialized = True
            logger.info("✅ WatchOS input adapter initialized")
            return True

        except ImportError as e:
            logger.error(f"WatchKit not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize WatchOS input: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown input adapter."""
        self._subscribers.clear()
        self._initialized = False
        logger.info("✅ WatchOS input adapter shutdown")

    async def subscribe(
        self,
        input_type: InputType,
        callback: Callable[[InputEvent], Awaitable[None]],
    ) -> None:
        """Subscribe to input events."""
        if input_type not in self._subscribers:
            self._subscribers[input_type] = []
        self._subscribers[input_type].append(callback)

    async def unsubscribe(self, input_type: InputType) -> None:
        """Unsubscribe from input events."""
        self._subscribers.pop(input_type, None)

    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking)."""
        # On watchOS, input is typically handled via delegates
        # This method returns None as events are pushed via callbacks
        return None

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic input event.

        Note: On watchOS, synthetic input injection is restricted.
        """
        logger.debug(f"Input injection not available on watchOS: {type}, {code}")
        return False

    # =========================================================================
    # Digital Crown
    # =========================================================================

    async def on_crown_rotate(self, delta: float) -> None:
        """Handle Digital Crown rotation.

        Called by WKInterfaceController.crownDidRotate.

        Args:
            delta: Rotation delta (-1.0 to 1.0)
        """
        self._crown_value += delta

        event = InputEvent(
            type=InputType.GESTURE,
            code=1000,  # Custom code for crown
            value=int(delta * 100),  # Scale to int
            timestamp_ms=int(asyncio.get_event_loop().time() * 1000),
        )

        for callback in self._subscribers.get(InputType.GESTURE, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in crown callback: {e}")

    async def on_crown_idle(self) -> None:
        """Handle Digital Crown becoming idle."""
        logger.debug(f"Crown idle at position: {self._crown_value}")

    @property
    def crown_value(self) -> float:
        """Get current accumulated crown value."""
        return self._crown_value

    def reset_crown(self) -> None:
        """Reset crown value to zero."""
        self._crown_value = 0.0

    # =========================================================================
    # Side Button
    # =========================================================================

    async def on_side_button_press(self) -> None:
        """Handle side button single press."""
        event = InputEvent(
            type=InputType.BUTTON,
            code=KeyCode.HOME.value,
            value=1,
            timestamp_ms=int(asyncio.get_event_loop().time() * 1000),
        )

        for callback in self._subscribers.get(InputType.BUTTON, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in button callback: {e}")

    async def on_side_button_long_press(self) -> None:
        """Handle side button long press (opens Control Center / SOS)."""
        event = InputEvent(
            type=InputType.BUTTON,
            code=KeyCode.POWER.value,  # Long press = power-related
            value=2,  # Long press indicator
            timestamp_ms=int(asyncio.get_event_loop().time() * 1000),
        )

        for callback in self._subscribers.get(InputType.BUTTON, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in button callback: {e}")

    # =========================================================================
    # Haptic Feedback (Taptic Engine)
    # =========================================================================

    async def play_haptic(self, type: str = "notification") -> None:
        """Play haptic feedback using Taptic Engine.

        Types:
        - notification: General notification
        - direction_up: Upward direction
        - direction_down: Downward direction
        - success: Success feedback
        - failure: Failure feedback
        - retry: Retry suggestion
        - start: Action start
        - stop: Action stop
        - click: Click feedback (for crown)
        """
        if not self._device:
            return

        try:
            # Map to WKHapticType
            haptic_map = {
                "notification": 0,
                "direction_up": 1,
                "direction_down": 2,
                "success": 3,
                "failure": 4,
                "retry": 5,
                "start": 6,
                "stop": 7,
                "click": 8,
            }

            haptic_type = haptic_map.get(type, 0)
            self._device.playHaptic_(haptic_type)
            logger.debug(f"Haptic played: {type}")

        except Exception as e:
            logger.error(f"Failed to play haptic: {e}")

    # Convenience methods for common haptics
    async def haptic_success(self) -> None:
        """Play success haptic."""
        await self.play_haptic("success")

    async def haptic_failure(self) -> None:
        """Play failure haptic."""
        await self.play_haptic("failure")

    async def haptic_notification(self) -> None:
        """Play notification haptic."""
        await self.play_haptic("notification")

    async def haptic_click(self) -> None:
        """Play click haptic (for crown feedback)."""
        await self.play_haptic("click")
