"""Linux Input Adapter.

Implements input event handling via evdev for keyboards, mice, touchscreens.

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import InputEvent, InputType

logger = logging.getLogger(__name__)

# Check evdev availability
INPUT_DEVICES_PATH = Path("/dev/input")
EVDEV_AVAILABLE_PATH = INPUT_DEVICES_PATH.exists()

# Check for evdev library
EVDEV_AVAILABLE = importlib.util.find_spec("evdev") is not None

# Import if available
if EVDEV_AVAILABLE:
    import evdev  # noqa: F401


class LinuxInput:
    """Linux input implementation using evdev.

    Supports keyboards, mice, touchscreens via /dev/input/event*.
    """

    def __init__(self) -> None:
        """Initialize input adapter."""
        self._initialized = False
        self._devices: dict[str, Any] = {}  # path -> evdev.InputDevice
        self._subscribers: dict[InputType, list[Callable[[InputEvent], Awaitable[None]]]] = {}
        self._event_task: asyncio.Task | None = None
        self._running = False

    async def initialize(self) -> bool:
        """Initialize input device discovery."""
        if not EVDEV_AVAILABLE_PATH:
            if is_test_mode():
                logger.info("evdev path not available")
                return False
            raise RuntimeError("Input devices path not available (/dev/input missing)")

        if not EVDEV_AVAILABLE:
            if is_test_mode():
                logger.info("evdev library not available")
                return False
            raise RuntimeError(
                "evdev library not available. Install: pip install evdev "
                "(note: requires permissions to access /dev/input/event*)"
            )

        try:
            import evdev

            # Enumerate input devices
            device_paths = list(INPUT_DEVICES_PATH.glob("event*"))

            for device_path in device_paths:
                try:
                    device = evdev.InputDevice(str(device_path))
                    self._devices[str(device_path)] = device
                    logger.debug(f"Found input device: {device.name} at {device_path}")

                except (PermissionError, OSError) as e:
                    logger.debug(f"Cannot access {device_path}: {e}")
                    continue

            if not self._devices:
                logger.warning(
                    "No accessible input devices found. "
                    "May need to run as root or add user to 'input' group."
                )
                return False

            self._initialized = True
            self._running = True

            # Start event polling task
            self._event_task = asyncio.create_task(self._poll_events())

            logger.info(f"✅ Linux input initialized: {len(self._devices)} devices")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize input devices: {e}", exc_info=True)
            return False

    async def subscribe(
        self, input_type: InputType, callback: Callable[[InputEvent], Awaitable[None]]
    ) -> None:
        """Subscribe to input events.

        Args:
            input_type: Type of input to subscribe to
            callback: Async callback for input events
        """
        if not self._initialized:
            raise RuntimeError("Input not initialized")

        if input_type not in self._subscribers:
            self._subscribers[input_type] = []

        self._subscribers[input_type].append(callback)
        logger.debug(f"Subscribed to {input_type.value} events")

    async def unsubscribe(self, input_type: InputType) -> None:
        """Unsubscribe from input events.

        Args:
            input_type: Type of input to unsubscribe from
        """
        self._subscribers.pop(input_type, None)
        logger.debug(f"Unsubscribed from {input_type.value} events")

    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking).

        Returns:
            InputEvent or None if no events available
        """
        if not self._initialized:
            raise RuntimeError("Input not initialized")

        # Poll all devices
        for device in self._devices.values():
            try:
                event = device.read_one()
                if event:
                    # Determine input type
                    caps = device.capabilities()
                    input_type = self._determine_input_type(caps)

                    return InputEvent(
                        type=input_type,
                        code=event.code,
                        value=event.value,
                        timestamp_ms=int(event.timestamp() * 1000),
                    )

            except BlockingIOError:
                continue

        return None

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic input event.

        Args:
            type: Input type
            code: Event code
            value: Event value

        Returns:
            True if injection successful

        Note: Requires write permissions to /dev/uinput
        """
        logger.warning("Event injection not yet implemented for Linux")
        return False

    async def _poll_events(self) -> None:
        """Poll input devices and dispatch events to subscribers."""
        import evdev

        while self._running:
            try:
                # Use select to wait for events from any device
                devices_list = list(self._devices.values())
                if not devices_list:
                    await asyncio.sleep(0.1)
                    continue

                # Convert to dict for select
                device_dict = {dev.fd: dev for dev in devices_list}

                # Wait for events (with timeout)
                r, _, _ = await asyncio.to_thread(evdev.util.select, device_dict, timeout=0.1)

                for fd in r:
                    device = device_dict[fd]

                    # Read all available events
                    for event in device.read():
                        # Determine input type
                        caps = device.capabilities()
                        input_type = self._determine_input_type(caps)

                        # Create InputEvent
                        input_event = InputEvent(
                            type=input_type,
                            code=event.code,
                            value=event.value,
                            timestamp_ms=int(event.timestamp() * 1000),
                        )

                        # Dispatch to subscribers
                        for callback in self._subscribers.get(input_type, []):
                            try:
                                await callback(input_event)
                            except Exception as e:
                                logger.error(f"Input callback error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event polling error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    @staticmethod
    def _determine_input_type(capabilities: dict[int, list]) -> InputType:
        """Determine input type from device capabilities.

        Args:
            capabilities: Device capabilities dict

        Returns:
            InputType
        """
        import evdev

        if evdev.ecodes.EV_KEY in capabilities:
            if evdev.ecodes.EV_REL in capabilities:
                return InputType.MOUSE
            else:
                return InputType.KEYBOARD

        if evdev.ecodes.EV_ABS in capabilities:
            return InputType.TOUCHSCREEN

        return InputType.BUTTON

    async def shutdown(self) -> None:
        """Shutdown input adapter."""
        self._running = False
        self._initialized = False

        # Cancel event task
        if self._event_task:
            self._event_task.cancel()
            try:
                await self._event_task
            except asyncio.CancelledError:
                pass
            self._event_task = None

        # Close all devices
        for device in self._devices.values():
            try:
                device.close()
            except Exception as e:
                logger.debug(f"Error closing input device: {e}")

        self._devices.clear()
        self._subscribers.clear()

        logger.info("✅ Linux input shutdown complete")


__all__ = ["LinuxInput"]
