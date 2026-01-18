"""macOS Input Adapter using IOKit HID.

Implements InputController for macOS using IOKit HID (Human Interface Device).

Uses:
- IOHIDManager for device discovery and monitoring
- Quartz Event Services for keyboard/mouse events
- NSEvent for high-level event handling

Created: November 10, 2025
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import InputEvent, InputType

logger = logging.getLogger(__name__)

# Try to import Quartz/Cocoa (macOS only)
Quartz = None
try:
    import Quartz  # type: ignore[no-redef]

    QUARTZ_AVAILABLE = True
except ImportError:
    Quartz = None
    QUARTZ_AVAILABLE = False
    logger.debug("Quartz not available. Install with: pip install pyobjc-framework-Quartz")


from kagami_hal.adapters.common import SubscriptionMixin


class MacOSIOKitInput(SubscriptionMixin):
    """macOS input controller using IOKit HID."""

    def __init__(self) -> None:
        """Initialize macOS input adapter."""
        SubscriptionMixin.__init__(self)
        self._running = False
        self._polling_task: asyncio.Task | None = None

    async def initialize(self) -> bool:
        """Initialize input controller."""
        if not QUARTZ_AVAILABLE:
            if is_test_mode():
                logger.info("Quartz not available (missing dependency), gracefully degrading")
                return False
            raise RuntimeError(
                "Quartz not available. Install: pip install pyobjc-framework-Quartz\n"
                "Or run in test mode: KAGAMI_BOOT_MODE=test"
            )

        try:
            logger.debug(
                "Quartz module ready (CGEventPost available=%s)",
                hasattr(Quartz, "CGEventPost") if Quartz else False,
            )
            # Create event source
            # Note: Full implementation would set up IOHIDManager
            # For now, we'll use simplified polling approach

            logger.info("✅ macOS input adapter initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize macOS input: {e}", exc_info=True)
            return False

    async def subscribe(  # type: ignore[override]
        self, input_type: InputType, callback: Callable[[InputEvent], Awaitable[None]]
    ) -> None:
        """Subscribe to input events."""
        if input_type not in self._callbacks:
            self._callbacks[input_type] = []
        self._callbacks[input_type].append(callback)

        # Start polling if not already running
        if not self._running:
            await self._start_polling()

    async def unsubscribe(self, input_type: InputType) -> None:
        """Unsubscribe from input events."""
        if input_type in self._callbacks:
            self._callbacks[input_type].clear()

    async def _start_polling(self) -> None:
        """Start input polling loop."""
        if self._running:
            return

        self._running = True
        from kagami.core.async_utils import safe_create_task

        self._polling_task = safe_create_task(
            self._polling_loop(),
            name="macos_input_polling",
            error_callback=lambda e: logger.error(f"Input polling crashed: {e}"),
        )

        logger.info("🖱️  macOS input polling started")

    async def _polling_loop(self) -> None:
        """Poll for input events.

        Note: Production implementation would use proper event tap/monitoring.
        This is simplified polling approach.
        """
        while self._running:
            try:
                # In production, this would:
                # 1. Set up CGEventTap to monitor events
                # 2. Use IOHIDManager to track device connections
                # 3. Convert events to InputEvent format

                # For now, just sleep
                await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling error: {e}", exc_info=True)

        logger.info("🖱️  macOS input polling stopped")

    async def _publish_input_event(self, event: InputEvent) -> None:
        """Publish input event to EventBus for display consumption.

        This bridges physical HAL input to the ambient display.
        """
        try:
            import time

            from kagami.core.events import get_unified_bus

            # Best-effort pointer position → normalized (0..1) display coordinates.
            # AmbientDisplay interprets (0,0) as top-left in its RGBA buffer.
            x_norm = 0.5
            y_norm = 0.5
            x_px: float | None = None
            y_px: float | None = None
            screen_w: float | None = None
            screen_h: float | None = None

            if QUARTZ_AVAILABLE and Quartz is not None:
                try:
                    loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
                    x_px = float(getattr(loc, "x", 0.0))
                    y_px = float(getattr(loc, "y", 0.0))

                    display_id = Quartz.CGMainDisplayID()
                    screen_w = float(Quartz.CGDisplayPixelsWide(display_id) or 0)
                    screen_h = float(Quartz.CGDisplayPixelsHigh(display_id) or 0)

                    if screen_w > 0 and screen_h > 0:
                        x_norm = x_px / screen_w
                        # CoreGraphics uses a bottom-left origin; invert to top-left for buffers.
                        y_norm = 1.0 - (y_px / screen_h)
                        x_norm = max(0.0, min(1.0, x_norm))
                        y_norm = max(0.0, min(1.0, y_norm))
                except Exception:
                    # Keep safe defaults
                    pass

            bus = get_unified_bus()
            payload = {
                "type": "hal.display.input",
                "interaction_type": "click",  # Map from InputType (partial)
                "x": x_norm,
                "y": y_norm,
                "button": event.code,
                "timestamp": time.time(),
            }
            # Include debug context for UI clients (optional)
            if x_px is not None and y_px is not None:
                payload["x_px"] = x_px
                payload["y_px"] = y_px
            if screen_w is not None and screen_h is not None:
                payload["screen_w"] = screen_w
                payload["screen_h"] = screen_h

            await bus.publish("hal.display.input", payload)
        except Exception as e:
            logger.debug(f"Failed to publish input event: {e}")

    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking).

        Returns:
            InputEvent or None if no events available
        """
        # Production would maintain event queue
        return None

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic input event via Quartz.

        Args:
            type: Event type (KEYBOARD, MOUSE, etc.)
            code: Key code (e.g., 0 for 'a', 36 for 'return')
            value: 1=down, 0=up

        Returns:
            True if successful
        """
        if not QUARTZ_AVAILABLE:
            return False

        try:
            if type == InputType.KEYBOARD:
                # Create keyboard event
                # CGEventCreateKeyboardEvent(source, virtualKey, keyDown)
                event = Quartz.CGEventCreateKeyboardEvent(None, code, value == 1)  # type: ignore[attr-defined]
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)  # type: ignore[attr-defined]
                return True
            elif type == InputType.MOUSE:
                # Mouse injection
                # code: 0=left, 1=right, 2=middle (for click) or generic (move)
                # value: 0=up, 1=down (for click)

                # Note: Current API doesn't support coordinates for move
                # We would need to extend inject_event or InputEvent to support x,y
                # For now, we assume code is button index

                mouse_type = None
                if value == 1:  # Down
                    if code == 0:
                        mouse_type = Quartz.kCGEventLeftMouseDown  # type: ignore[attr-defined]
                    elif code == 1:
                        mouse_type = Quartz.kCGEventRightMouseDown  # type: ignore[attr-defined]
                    else:
                        mouse_type = Quartz.kCGEventOtherMouseDown  # type: ignore[attr-defined]
                else:  # Up
                    if code == 0:
                        mouse_type = Quartz.kCGEventLeftMouseUp  # type: ignore[attr-defined]
                    elif code == 1:
                        mouse_type = Quartz.kCGEventRightMouseUp  # type: ignore[attr-defined]
                    else:
                        mouse_type = Quartz.kCGEventOtherMouseUp  # type: ignore[attr-defined]

                # Get current position (dummy for now as we don't have coords)
                # Ideally we'd get current cursor pos
                loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))  # type: ignore[attr-defined]

                event = Quartz.CGEventCreateMouseEvent(  # type: ignore[attr-defined]
                    None, mouse_type, loc, code if code > 1 else 0
                )
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)  # type: ignore[attr-defined]
                return True

            return False
        except Exception as e:
            logger.error(f"Failed to inject event: {e}")
            return False

    async def shutdown(self) -> None:
        """Shutdown input controller."""
        self._running = False

        if self._polling_task:
            self._polling_task.cancel()

        logger.info("✅ macOS input adapter shutdown")


# Simplified implementation for now
# Full IOKit HID implementation would require:
# 1. IOHIDManager setup with device matching
# 2. CFRunLoop integration for event processing
# 3. Proper HID usage page/usage parsing
# 4. Event queue management
#
# Example pseudo-code for full implementation:
#
# from IOKit import IOHIDManager, IOHIDDevice
# from CoreFoundation import CFRunLoopGetCurrent, CFRunLoopRun
#
# manager = IOHIDManager.IOHIDManagerCreate()
# IOHIDManager.IOHIDManagerSetDeviceMatching(manager, matching_dict)
# IOHIDManager.IOHIDManagerRegisterDeviceMatchingCallback(manager, device_added_callback)
# IOHIDManager.IOHIDManagerRegisterInputValueCallback(manager, input_value_callback)
# IOHIDManager.IOHIDManagerScheduleWithRunLoop(manager, CFRunLoopGetCurrent(), kCFRunLoopDefaultMode)
# IOHIDManager.IOHIDManagerOpen(manager, kIOHIDOptionsTypeNone)
