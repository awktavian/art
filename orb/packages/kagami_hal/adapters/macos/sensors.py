"""macOS Sensor Adapter via IOKit.

Provides access to hardware sensors on macOS:
- Temperature (SMC via IOKit)
- Accelerometer (via SMS/IOKit if present)
- Location (CoreLocation)
- Ambient Light (via IOKit)

Created: November 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from kagami_hal.data_types import GPSReading, SensorReading, SensorType

logger = logging.getLogger(__name__)


from kagami_hal.adapters.common import SubscriptionMixin


class MacOSSensors(SubscriptionMixin):
    """macOS sensor adapter using IOKit/SMC."""

    def __init__(self) -> None:
        SubscriptionMixin.__init__(self)
        self._initialized = False
        self._available_sensors: list[SensorType] = []

        # Sensor connections
        self._smc_connection: Any = None
        self._location_manager: Any = None
        self._als_service: Any = None
        self._accelerometer_service: Any = None

        # Sensor callbacks
        self._polling = False
        self._polling_task: asyncio.Task | None = None
        self._subscribers: dict[Any, list[Any]] = {}  # Initialize subscribers

    async def initialize(self) -> bool:
        """Initialize macOS sensors."""
        try:
            # Try importing PyObjC frameworks
            try:
                pass
                # Note: IOKit in Python is often accessed via low-level bindings or ctypes
                # For this implementation we'll try to use IOKit via PyObjC if available,
                # or fall back to standard IO registry access
            except ImportError:
                logger.warning("PyObjC frameworks not available. Sensors will be limited.")

            # 1. Temperature via SMC (System Management Controller)
            if await self._init_smc():
                self._available_sensors.append(SensorType.TEMPERATURE)

            # 2. Location via CoreLocation
            try:
                from CoreLocation import CLLocationManager

                self._location_manager = CLLocationManager.alloc().init()
                # We can't request authorization without a UI loop usually, but we can try/check status
                # self._location_manager.requestWhenInUseAuthorization()
                self._available_sensors.append(SensorType.GPS)
                logger.info("CoreLocation available for GPS")
            except Exception as e:
                logger.debug(f"CoreLocation not available: {e}")

            # 3. Ambient Light Sensor (ALS)
            if await self._init_als():
                self._available_sensors.append(SensorType.LIGHT)

            # 4. Accelerometer (SMS)
            if await self._init_accelerometer():
                self._available_sensors.append(SensorType.ACCELEROMETER)

            self._initialized = True
            logger.info(f"macOS sensors initialized: {[s.value for s in self._available_sensors]}")

            return len(self._available_sensors) > 0

        except Exception as e:
            logger.error(f"Failed to initialize macOS sensors: {e}")
            return False

    async def _init_smc(self) -> bool:
        """Initialize connection to SMC."""
        # Real SMC access usually requires C-level IOKit calls.
        # In pure Python/PyObjC this is hard without a bridge.
        # We will fallback to 'sysctl' if direct IOKit fails, but structured to support IOKit later.
        # For now, we check if we can read thermal levels.
        try:
            import subprocess

            result = subprocess.run(
                ["sysctl", "machdep.xcpm.cpu_thermal_level"], capture_output=True, timeout=1
            )
            return result.returncode == 0
        except Exception:
            return False

    async def _init_als(self) -> bool:
        """Initialize Ambient Light Sensor."""
        # Similar to SMC, ALS is IO registry based.
        # For this implementation, we'll look for the service.
        # Placeholder logic - requires IOKit bridge for real access
        return False

    async def _init_accelerometer(self) -> bool:
        """Initialize Sudden Motion Sensor (Accelerometer)."""
        # SMS is IOKit based.
        return False

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value."""
        if not self._initialized:
            raise RuntimeError("Sensors not initialized") from None

        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor not available: {sensor.value}") from None

        if sensor == SensorType.TEMPERATURE:
            return await self._read_temperature()
        elif sensor == SensorType.GPS:
            return await self._read_gps()
        elif sensor == SensorType.LIGHT:
            return await self._read_light()
        elif sensor == SensorType.ACCELEROMETER:
            return await self._read_accelerometer()
        else:
            raise RuntimeError(f"Sensor not implemented: {sensor.value}")

    # Alias for backwards compatibility
    async def read_sensor(self, sensor: SensorType) -> SensorReading:
        """Read sensor value (alias for read)."""
        return await self.read(sensor)

    async def _read_temperature(self) -> SensorReading:
        """Read CPU temperature."""
        # Implementation using sysctl as a robust fallback for SMC
        try:
            import subprocess

            result = subprocess.run(
                ["sysctl", "-n", "machdep.xcpm.cpu_thermal_level"],
                capture_output=True,
                timeout=1,
                text=True,
            )

            if result.returncode == 0:
                # Thermal level 0-100 (higher = hotter)
                thermal_level = int(result.stdout.strip())

                # Estimate temperature (rough approximation)
                # Base temp ~40°C, add ~0.5°C per level
                temp_celsius = 40.0 + (thermal_level * 0.5)

                return SensorReading(
                    sensor=SensorType.TEMPERATURE,
                    value=temp_celsius,
                    timestamp_ms=self._get_timestamp_ms(),
                    accuracy=0.7,  # Approximate
                )

            raise RuntimeError("Failed to read thermal level")

        except Exception as e:
            raise RuntimeError(f"Failed to read temperature: {e}") from None

    async def _read_gps(self) -> SensorReading:
        """Read GPS via CoreLocation."""
        try:
            # Check authorization
            _ = self._location_manager.authorizationStatus()

            # CoreLocation logic in Python requires a runloop or polling,
            # which is tricky in async. We rely on the last known location.

            location = self._location_manager.location()

            if not location:
                raise RuntimeError("No location available")

            coord = location.coordinate()

            gps = GPSReading(
                latitude=float(coord.latitude),
                longitude=float(coord.longitude),
                altitude=float(location.altitude()),
                accuracy=float(location.horizontalAccuracy()),
            )

            # Accuracy score (higher horizontal accuracy = lower confidence)
            accuracy_score = 1.0 / (1.0 + max(1.0, location.horizontalAccuracy()) / 10.0)

            return SensorReading(
                sensor=SensorType.GPS,
                value=gps,
                timestamp_ms=self._get_timestamp_ms(),
                accuracy=min(accuracy_score, 1.0),
            )

        except Exception as e:
            raise RuntimeError(f"Failed to read GPS: {e}") from None

    async def _read_light(self) -> SensorReading:
        """Read Ambient Light via ioreg."""
        try:
            import re
            import subprocess

            # Try AppleLMUController (older Macs) or AppleALSSensor (newer)
            # Command: ioreg -c AppleLMUController -n AppleLMUController -r
            cmd = ["ioreg", "-c", "AppleLMUController", "-n", "AppleLMUController", "-r"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1)

            lux = 0.0
            found = False

            if result.returncode == 0 and "AmbientLightSensor" in result.stdout:
                # Parse output: "AmbientLightSensor" = {"L0"=123,"L1"=456} or similar
                # or just "L0" = 123
                match = re.search(r'"L0"\s*=\s*(\d+)', result.stdout)
                if match:
                    l0 = int(match.group(1))
                    # Rough conversion to Lux? L0 is usually raw ADC.
                    # This is highly hardware dependent. We'll return raw value as "lux" approximation.
                    lux = float(l0)
                    found = True

            if not found:
                # Try newer sensor class
                cmd = ["ioreg", "-c", "AppleALSSensor", "-r"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
                if result.returncode == 0:
                    # Look for "Illuminance" or similar
                    match = re.search(r'"Illuminance"\s*=\s*(\d+)', result.stdout)
                    if match:
                        lux = float(match.group(1))
                        found = True

            return SensorReading(
                sensor=SensorType.LIGHT,
                value=lux,
                timestamp_ms=self._get_timestamp_ms(),
                accuracy=1.0 if found else 0.0,
            )

        except Exception as e:
            logger.debug(f"Failed to read light sensor: {e}")
            return SensorReading(
                sensor=SensorType.LIGHT,
                value=0.0,
                timestamp_ms=self._get_timestamp_ms(),
                accuracy=0.0,
            )

    async def _read_accelerometer(self) -> SensorReading:
        """Read Accelerometer via SMS (Sudden Motion Sensor).

        Note: SMS was removed from most Macs after 2012. This will raise
        an error on modern Macs without SMS.
        """
        raise RuntimeError(
            "Accelerometer (SMS) not available on this Mac. "
            "SMS was removed from Macs with SSDs (post-2012)."
        )

    def _get_timestamp_ms(self) -> int:
        """Get current timestamp in milliseconds."""
        import time

        return int(time.time() * 1000)

    async def subscribe(  # type: ignore[override]
        self,
        sensor: SensorType,
        callback: Any,
    ) -> None:
        """Subscribe to sensor updates."""
        if sensor not in self._subscribers:
            self._subscribers[sensor] = []

        self._subscribers[sensor].append(callback)

        # Start polling if not already running
        if not self._polling:
            await self._start_polling()

    async def unsubscribe(self, sensor: SensorType) -> None:
        """Unsubscribe from sensor updates."""
        if sensor in self._subscribers:
            self._subscribers[sensor].clear()

    async def _start_polling(self) -> None:
        """Start sensor polling loop."""
        if self._polling:
            return

        self._polling = True
        from kagami.core.async_utils import safe_create_task

        self._polling_task = safe_create_task(
            self._polling_loop(),
            name="macos_sensor_polling",
            error_callback=lambda e: logger.error(f"Sensor polling crashed: {e}"),
        )

        logger.info("macOS sensor polling started")

    async def _polling_loop(self) -> None:
        """Poll sensors and notify subscribers."""
        while self._polling:
            try:
                for sensor_type, callbacks in self._subscribers.items():
                    if not callbacks:
                        continue

                    try:
                        if sensor_type in self._available_sensors:
                            reading = await self.read(sensor_type)

                            for callback in callbacks:
                                try:
                                    await callback(reading)
                                except Exception as e:
                                    logger.error(f"Subscriber callback failed: {e}")
                        else:
                            # Skip if unavailable
                            pass

                    except Exception as e:
                        logger.debug(f"Failed to poll {sensor_type.value}: {e}")

                # Poll at 1Hz
                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling loop error: {e}", exc_info=True)

        logger.info("macOS sensor polling stopped")

    async def list_sensors(self) -> list[SensorType]:
        """List available sensors."""
        return self._available_sensors.copy()

    # Alias for backwards compatibility
    async def list_available_sensors(self) -> list[SensorType]:
        """List available sensors (alias for list_sensors)."""
        return await self.list_sensors()

    async def shutdown(self) -> None:
        """Shutdown sensor adapter."""
        self._polling = False

        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

        logger.info("macOS sensors shut down")


__all__ = ["MacOSSensors"]
