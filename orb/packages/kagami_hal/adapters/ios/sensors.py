"""iOS Sensors Adapter using CoreMotion.

Implements SensorManager for iOS using:
- CMMotionManager for accelerometer, gyroscope
- CLLocationManager for GPS
- UIDevice for battery

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
Updated: December 8, 2025 - Refactored to use SensorAdapterBase
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
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

IOS_AVAILABLE = sys.platform == "darwin" and (
    os.uname().machine.startswith("iP") or os.environ.get("KAGAMI_PLATFORM") == "ios"
)


class iOSSensors(SensorAdapterBase):
    """iOS sensor implementation using CoreMotion.

    Note: Overrides subscribe/unsubscribe to handle iOS-specific
    CoreMotion and CoreLocation API calls.
    """

    def __init__(self):
        """Initialize iOS sensors."""
        super().__init__()
        self._motion_manager: Any = None
        self._location_manager: Any = None

    async def initialize(self) -> bool:
        """Initialize sensor discovery."""
        if not IOS_AVAILABLE:
            if is_test_mode():
                logger.info("iOS sensors not available, gracefully degrading")
                return False
            raise RuntimeError("iOS sensors only available on iOS")

        try:
            from CoreLocation import CLLocationManager
            from CoreMotion import CMMotionManager

            # Initialize motion manager
            self._motion_manager = CMMotionManager.alloc().init()

            # Check available sensors
            if self._motion_manager.accelerometerAvailable():
                self._available_sensors.add(SensorType.ACCELEROMETER)

            if self._motion_manager.gyroAvailable():
                self._available_sensors.add(SensorType.GYROSCOPE)

            if self._motion_manager.magnetometerAvailable():
                self._available_sensors.add(SensorType.MAGNETOMETER)

            # Initialize location manager
            self._location_manager = CLLocationManager.alloc().init()
            self._available_sensors.add(SensorType.GPS)

            # Battery is always available
            self._available_sensors.add(SensorType.BATTERY)

            self._running = True
            logger.info(f"✅ iOS sensors initialized: {self._available_sensors}")
            return True

        except ImportError:
            logger.error("CoreMotion not available")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize iOS sensors: {e}", exc_info=True)
            return False

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value."""
        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        try:
            value: Any = None
            accuracy = 1.0

            if sensor == SensorType.ACCELEROMETER:
                if self._motion_manager:
                    data = self._motion_manager.accelerometerData()
                    if data:
                        accel = data.acceleration()
                        value = AccelReading(x=accel.x, y=accel.y, z=accel.z)
                    else:
                        raise RuntimeError(
                            "No accelerometer data. Call subscribe() first to start updates."
                        )
                else:
                    raise RuntimeError("Motion manager not initialized")

            elif sensor == SensorType.GYROSCOPE:
                if self._motion_manager:
                    data = self._motion_manager.gyroData()
                    if data:
                        rate = data.rotationRate()
                        value = GyroReading(x=rate.x, y=rate.y, z=rate.z)
                    else:
                        raise RuntimeError(
                            "No gyroscope data. Call subscribe() first to start updates."
                        )
                else:
                    raise RuntimeError("Motion manager not initialized")

            elif sensor == SensorType.GPS:
                if self._location_manager:
                    loc = self._location_manager.location()
                    if loc:
                        coord = loc.coordinate()
                        value = GPSReading(
                            latitude=coord.latitude,
                            longitude=coord.longitude,
                            altitude=loc.altitude(),
                            accuracy=loc.horizontalAccuracy(),
                        )
                    else:
                        raise RuntimeError(
                            "No GPS data available. Location services may be disabled."
                        )
                else:
                    raise RuntimeError("Location manager not initialized")

            elif sensor == SensorType.BATTERY:
                from UIKit import UIDevice

                device = UIDevice.currentDevice()
                device.setBatteryMonitoringEnabled_(True)
                level = device.batteryLevel()
                value = int(level * 100) if level >= 0 else 100

            else:
                raise RuntimeError(f"Reading not implemented for {sensor}")

            reading = SensorReading(
                sensor=sensor,
                value=value,
                timestamp_ms=int(time.time() * 1000),
                accuracy=accuracy,
            )
            self._last_readings[sensor] = reading
            return reading

        except Exception as e:
            logger.error(f"Failed to read sensor {sensor}: {e}")
            raise

    async def subscribe(
        self,
        sensor: SensorType,
        callback: Callable[[SensorReading], Awaitable[None]],
        rate_hz: int = 10,
    ) -> None:
        """Subscribe to sensor updates with iOS-specific native updates."""
        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        # Start native updates on first subscriber
        if sensor not in self._subscribers:
            interval = 1.0 / rate_hz
            if sensor == SensorType.ACCELEROMETER and self._motion_manager:
                self._motion_manager.setAccelerometerUpdateInterval_(interval)
                self._motion_manager.startAccelerometerUpdates()
            elif sensor == SensorType.GYROSCOPE and self._motion_manager:
                self._motion_manager.setGyroUpdateInterval_(interval)
                self._motion_manager.startGyroUpdates()
            elif sensor == SensorType.GPS and self._location_manager:
                self._location_manager.startUpdatingLocation()

        # Delegate to base class for common subscription logic
        await super().subscribe(sensor, callback, rate_hz)

    async def unsubscribe(self, sensor: SensorType) -> None:
        """Unsubscribe with iOS-specific native cleanup."""
        # Stop native updates
        if sensor == SensorType.ACCELEROMETER and self._motion_manager:
            self._motion_manager.stopAccelerometerUpdates()
        elif sensor == SensorType.GYROSCOPE and self._motion_manager:
            self._motion_manager.stopGyroUpdates()
        elif sensor == SensorType.GPS and self._location_manager:
            self._location_manager.stopUpdatingLocation()

        # Delegate to base class for common cleanup
        await super().unsubscribe(sensor)

    async def shutdown(self) -> None:
        """Shutdown with iOS-specific cleanup."""
        # Stop all native updates
        if self._motion_manager:
            self._motion_manager.stopAccelerometerUpdates()
            self._motion_manager.stopGyroUpdates()
        if self._location_manager:
            self._location_manager.stopUpdatingLocation()

        # Delegate to base class
        await super().shutdown()
