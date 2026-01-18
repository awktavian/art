"""Linux evdev Input Device Sensor.

Implements input device access via evdev library.
Supports keyboards, mice, touchscreens from /dev/input/event*.

Created: December 15, 2025
"""

from __future__ import annotations

import importlib.util
import logging
import time
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.data_types import InputEvent, InputType, SensorReading, SensorType

logger = logging.getLogger(__name__)

# Check evdev availability
INPUT_DEVICES_PATH = Path("/dev/input")
EVDEV_AVAILABLE_PATH = INPUT_DEVICES_PATH.exists()

# Check for evdev library
EVDEV_AVAILABLE = importlib.util.find_spec("evdev") is not None

# Import if available
if EVDEV_AVAILABLE:
    import evdev  # noqa: F401


class LinuxInput(SensorAdapterBase):
    """Linux input device implementation using evdev.

    Supports keyboards, mice, touchscreens, and other input devices
    via /dev/input/event*.
    """

    def __init__(self) -> None:
        """Initialize input device adapter."""
        super().__init__()
        self._devices: dict[str, Any] = {}  # path -> evdev.InputDevice

    async def initialize(self) -> bool:
        """Initialize input device discovery."""
        if not EVDEV_AVAILABLE_PATH:
            if is_test_mode():
                logger.info("evdev path not available")
                return False
            logger.warning("Input devices path not available (/dev/input missing)")
            return False

        if not EVDEV_AVAILABLE:
            if is_test_mode():
                logger.info("evdev library not available")
                return False
            logger.warning(
                "evdev library not available. Install: pip install evdev "
                "(note: requires permissions to access /dev/input/event*)"
            )
            return False

        try:
            import evdev

            # Enumerate input devices
            device_paths = list(INPUT_DEVICES_PATH.glob("event*"))

            for device_path in device_paths:
                try:
                    device = evdev.InputDevice(str(device_path))
                    self._devices[str(device_path)] = device

                    # Determine device type based on capabilities
                    caps = device.capabilities()

                    # Check for various input types
                    # EV_KEY = keyboard/mouse buttons
                    # EV_REL = relative axes (mouse)
                    # EV_ABS = absolute axes (touchscreen)

                    if evdev.ecodes.EV_KEY in caps:
                        # Has keys - could be keyboard or mouse
                        if evdev.ecodes.EV_REL in caps:
                            # Has relative axes - mouse
                            self._available_sensors.add(SensorType.MOUSE)  # type: ignore[attr-defined]
                        else:
                            # Just keys - keyboard
                            self._available_sensors.add(SensorType.KEYBOARD)  # type: ignore[attr-defined]

                    if evdev.ecodes.EV_ABS in caps:
                        # Has absolute axes - touchscreen
                        self._available_sensors.add(SensorType.TOUCHSCREEN)  # type: ignore[attr-defined]

                except (PermissionError, OSError) as e:
                    logger.debug(f"Cannot access {device_path}: {e}")
                    continue

            if not self._devices:
                logger.warning(
                    "No accessible input devices found. "
                    "May need to run as root or add user to 'input' group."
                )
                return False

            self._running = True
            logger.info(f"✅ Linux input devices initialized: {len(self._devices)} devices")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize input devices: {e}", exc_info=True)
            return False

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read input event.

        Note: This is a non-blocking read. Returns None if no events available.

        Args:
            sensor: Input sensor type (KEYBOARD, MOUSE, TOUCHSCREEN)

        Returns:
            SensorReading with InputEvent as value, or None if no events
        """
        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        try:
            import evdev

            # Poll all devices for the requested sensor type
            for device in self._devices.values():
                # Check if device matches sensor type
                caps = device.capabilities()

                matches = False
                if sensor == SensorType.KEYBOARD:  # type: ignore[attr-defined]
                    matches = evdev.ecodes.EV_KEY in caps and evdev.ecodes.EV_REL not in caps
                elif sensor == SensorType.MOUSE:  # type: ignore[attr-defined]
                    matches = evdev.ecodes.EV_KEY in caps and evdev.ecodes.EV_REL in caps
                elif sensor == SensorType.TOUCHSCREEN:  # type: ignore[attr-defined]
                    matches = evdev.ecodes.EV_ABS in caps

                if not matches:
                    continue

                # Try to read event (non-blocking)
                try:
                    event = device.read_one()
                    if event:
                        # Convert evdev event to InputEvent
                        input_event = InputEvent(
                            type=self._evdev_to_input_type(sensor),
                            code=event.code,
                            value=event.value,
                            timestamp_ms=int(event.timestamp() * 1000),
                        )

                        return SensorReading(
                            sensor=sensor,
                            value=input_event,
                            timestamp_ms=int(time.time() * 1000),
                            accuracy=1.0,
                        )

                except BlockingIOError:
                    # No events available from this device
                    continue

            # No events from any device
            return SensorReading(
                sensor=sensor,
                value=None,
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"Failed to read input device: {e}")
            raise

    @staticmethod
    def _evdev_to_input_type(sensor: SensorType) -> InputType:
        """Convert sensor type to InputType."""
        mapping = {
            SensorType.KEYBOARD: InputType.KEYBOARD,  # type: ignore[attr-defined]
            SensorType.MOUSE: InputType.MOUSE,  # type: ignore[attr-defined]
            SensorType.TOUCHSCREEN: InputType.TOUCHSCREEN,  # type: ignore[attr-defined]
        }
        return mapping.get(sensor, InputType.BUTTON)

    async def shutdown(self) -> None:
        """Shutdown input devices."""
        await super().shutdown()

        for device in self._devices.values():
            try:
                device.close()
            except Exception as e:
                logger.debug(f"Error closing input device: {e}")

        self._devices.clear()
        logger.info("✅ Linux input devices shutdown complete")

    def list_devices(self) -> list[dict[str, Any]]:
        """List available input devices with details.

        Returns:
            List of device info dicts with keys: path, name, capabilities
        """
        if not EVDEV_AVAILABLE:
            return []

        import evdev

        devices = []
        for path, device in self._devices.items():
            caps = device.capabilities()

            # Determine device types
            types = []
            if evdev.ecodes.EV_KEY in caps:
                if evdev.ecodes.EV_REL in caps:
                    types.append("mouse")
                else:
                    types.append("keyboard")
            if evdev.ecodes.EV_ABS in caps:
                types.append("touchscreen")

            devices.append(
                {
                    "path": path,
                    "name": device.name,
                    "types": types,
                    "phys": device.phys or "unknown",
                }
            )

        return devices


__all__ = ["LinuxInput"]
