"""Linux Sensors.

Aggregates multiple Linux sensor implementations:
- Camera (V4L2)
- Microphone (ALSA)
- Thermal (thermal zones)
- Input devices (evdev)

Created: December 15, 2025
"""

from __future__ import annotations

import logging
from typing import Any

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)


class LinuxSensors(SensorAdapterBase):
    """Aggregate Linux sensor adapter.

    Combines multiple sensor types:
    - Thermal zones
    - Camera (V4L2)
    - Microphone (ALSA)
    - Input devices (evdev)
    """

    def __init__(self) -> None:
        """Initialize Linux sensors."""
        super().__init__()
        self._thermal_adapter: Any = None
        self._camera_adapter: Any = None
        self._microphone_adapter: Any = None
        self._input_adapter: Any = None

    async def initialize(self) -> bool:
        """Initialize all available sensor subsystems."""
        from kagami_hal.adapters.linux.sensors.camera import LinuxCamera
        from kagami_hal.adapters.linux.sensors.input import LinuxInput
        from kagami_hal.adapters.linux.sensors.microphone import LinuxMicrophone
        from kagami_hal.adapters.linux.sensors.thermal import LinuxThermal

        # Initialize thermal zones
        self._thermal_adapter = LinuxThermal()
        if await self._thermal_adapter.initialize():
            thermal_sensors = await self._thermal_adapter.list_sensors()
            self._available_sensors.update(thermal_sensors)
            logger.info(f"Thermal zones available: {len(thermal_sensors)}")

        # Initialize camera
        self._camera_adapter = LinuxCamera()
        if await self._camera_adapter.initialize():
            self._available_sensors.add(SensorType.CAMERA)
            logger.info("V4L2 camera available")

        # Initialize microphone
        self._microphone_adapter = LinuxMicrophone()
        if await self._microphone_adapter.initialize():
            self._available_sensors.add(SensorType.MICROPHONE)
            logger.info("ALSA microphone available")

        # Initialize input devices
        self._input_adapter = LinuxInput()
        if await self._input_adapter.initialize():
            input_sensors = self._input_adapter._available_sensors
            self._available_sensors.update(input_sensors)
            logger.info(f"Input devices available: {len(input_sensors)}")

        self._running = True
        logger.info(f"✅ Linux sensors initialized: {len(self._available_sensors)} sensors")
        return len(self._available_sensors) > 0

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value by routing to appropriate adapter."""
        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        # Route to appropriate adapter
        if sensor == SensorType.TEMPERATURE and self._thermal_adapter:
            return await self._thermal_adapter.read(sensor)
        elif sensor == SensorType.CAMERA and self._camera_adapter:
            return await self._camera_adapter.read(sensor)
        elif sensor == SensorType.MICROPHONE and self._microphone_adapter:
            return await self._microphone_adapter.read(sensor)
        elif (
            sensor in (SensorType.KEYBOARD, SensorType.MOUSE, SensorType.TOUCHSCREEN)  # type: ignore[attr-defined]
            and self._input_adapter
        ):
            return await self._input_adapter.read(sensor)
        else:
            raise RuntimeError(f"No adapter available for sensor {sensor}")

    async def shutdown(self) -> None:
        """Shutdown all sensor adapters."""
        if self._thermal_adapter:
            await self._thermal_adapter.shutdown()
        if self._camera_adapter:
            await self._camera_adapter.shutdown()
        if self._microphone_adapter:
            await self._microphone_adapter.shutdown()
        if self._input_adapter:
            await self._input_adapter.shutdown()

        await super().shutdown()


__all__ = ["LinuxSensors"]
