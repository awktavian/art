"""WASM Sensors Adapter using Web APIs.

Implements SensorManager for WebAssembly using:
- DeviceMotionEvent for accelerometer/gyroscope
- DeviceOrientationEvent for orientation
- Geolocation API for GPS
- Ambient Light Sensor API

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
Updated: December 8, 2025 - Refactored to use SensorAdapterBase
"""

from __future__ import annotations

import logging
import time
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.data_types import (
    AccelReading,
    GPSReading,
    GyroReading,
    SensorReading,
    SensorType,
)

logger = logging.getLogger(__name__)

WASM_AVAILABLE = False
try:
    import js
    from pyodide.ffi import create_proxy

    WASM_AVAILABLE = True
except ImportError:
    pass


class WASMSensors(SensorAdapterBase):
    """WASM sensor implementation using Web APIs."""

    def __init__(self):
        """Initialize WASM sensors."""
        super().__init__()
        self._event_proxies: list[Any] = []

    async def initialize(self) -> bool:
        """Initialize sensor discovery."""
        if not WASM_AVAILABLE:
            if is_test_mode():
                logger.info("WASM sensors not available, gracefully degrading")
                return False
            raise RuntimeError("WASM sensors only available in browser")

        try:
            # Check DeviceMotionEvent support
            if hasattr(js.window, "DeviceMotionEvent"):
                self._available_sensors.add(SensorType.ACCELEROMETER)
                self._available_sensors.add(SensorType.GYROSCOPE)

            # Check Geolocation API
            if hasattr(js.navigator, "geolocation"):
                self._available_sensors.add(SensorType.GPS)

            # Check AmbientLightSensor API
            try:
                if hasattr(js.window, "AmbientLightSensor"):
                    self._available_sensors.add(SensorType.LIGHT)
            except Exception:
                pass

            # Set up device motion listener
            motion_proxy = create_proxy(self._on_device_motion)
            js.window.addEventListener("devicemotion", motion_proxy)
            self._event_proxies.append(motion_proxy)

            self._running = True
            logger.info(f"✅ WASM sensors initialized: {self._available_sensors}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WASM sensors: {e}", exc_info=True)
            return False

    def _on_device_motion(self, event: Any) -> None:
        """Handle device motion event."""
        try:
            timestamp = int(time.time() * 1000)

            # Accelerometer
            if event.accelerationIncludingGravity:
                accel = event.accelerationIncludingGravity
                reading = SensorReading(
                    sensor=SensorType.ACCELEROMETER,
                    value=AccelReading(
                        x=accel.x or 0.0,
                        y=accel.y or 0.0,
                        z=accel.z or 0.0,
                    ),
                    timestamp_ms=timestamp,
                    accuracy=1.0,
                )
                self._last_readings[SensorType.ACCELEROMETER] = reading

            # Gyroscope
            if event.rotationRate:
                rate = event.rotationRate
                reading = SensorReading(
                    sensor=SensorType.GYROSCOPE,
                    value=GyroReading(
                        x=rate.alpha or 0.0,
                        y=rate.beta or 0.0,
                        z=rate.gamma or 0.0,
                    ),
                    timestamp_ms=timestamp,
                    accuracy=1.0,
                )
                self._last_readings[SensorType.GYROSCOPE] = reading

        except Exception as e:
            logger.error(f"Error handling device motion: {e}")

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value."""
        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        try:
            timestamp = int(time.time() * 1000)

            if sensor == SensorType.ACCELEROMETER:
                if SensorType.ACCELEROMETER in self._last_readings:
                    return self._last_readings[SensorType.ACCELEROMETER]
                raise RuntimeError(
                    "No accelerometer data yet. Ensure DeviceMotionEvent is firing. "
                    "May require user gesture or HTTPS."
                )

            elif sensor == SensorType.GYROSCOPE:
                if SensorType.GYROSCOPE in self._last_readings:
                    return self._last_readings[SensorType.GYROSCOPE]
                raise RuntimeError(
                    "No gyroscope data yet. Ensure DeviceMotionEvent is firing. "
                    "May require user gesture or HTTPS."
                )

            elif sensor == SensorType.GPS:
                # Use Geolocation API
                position = await self._get_geolocation()
                if position:
                    coords = position.coords
                    return SensorReading(
                        sensor=sensor,
                        value=GPSReading(
                            latitude=coords.latitude,
                            longitude=coords.longitude,
                            altitude=coords.altitude or 0.0,
                            accuracy=coords.accuracy or 0.0,
                        ),
                        timestamp_ms=timestamp,
                        accuracy=1.0,
                    )
                raise RuntimeError(
                    "Geolocation failed. User may have denied permission or HTTPS required."
                )

            elif sensor == SensorType.LIGHT:
                # Requires AmbientLightSensor API
                raise RuntimeError(
                    "Light sensor requires AmbientLightSensor API. "
                    "Not widely supported in browsers."
                )

            else:
                raise RuntimeError(f"Reading not implemented for {sensor}")

        except Exception as e:
            logger.error(f"Failed to read sensor {sensor}: {e}")
            raise

    async def _get_geolocation(self) -> Any:
        """Get current geolocation position."""
        if not WASM_AVAILABLE:
            return None

        try:
            return await js.navigator.geolocation.getCurrentPosition()
        except Exception as e:
            logger.warning(f"Geolocation failed: {e}")
            return None

    async def shutdown(self) -> None:
        """Shutdown sensor manager with WASM-specific cleanup."""
        await super().shutdown()
        self._event_proxies.clear()
