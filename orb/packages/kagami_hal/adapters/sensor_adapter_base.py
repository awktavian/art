"""Sensor Adapter Base Class.

Provides common implementation for sensor subscription, polling, and lifecycle.
Platform-specific adapters only need to implement initialize() and read().

Created: December 8, 2025
Purpose: Eliminate duplication across 6+ platform adapters
"""

from __future__ import annotations

import asyncio
import logging
from abc import abstractmethod
from collections.abc import Awaitable, Callable

from kagami_hal.data_types import SensorReading, SensorType
from kagami_hal.sensor_manager import SensorManager

logger = logging.getLogger(__name__)

__all__ = ["SensorAdapterBase"]


class SensorAdapterBase(SensorManager):
    """Base class for sensor adapters with common subscription logic.

    Subclasses must implement:
    - initialize() -> bool: Platform-specific sensor discovery
    - read(sensor: SensorType) -> SensorReading: Platform-specific reading

    This base class provides:
    - list_sensors(): Return available sensors
    - subscribe(): Start polling with callback
    - _poll_sensor(): Polling loop implementation
    - unsubscribe(): Stop polling
    - shutdown(): Clean shutdown
    """

    def __init__(self) -> None:
        """Initialize common sensor adapter state."""
        self._available_sensors: set[SensorType] = set()
        self._subscribers: dict[SensorType, list[Callable[[SensorReading], Awaitable[None]]]] = {}
        self._subscription_tasks: dict[SensorType, asyncio.Task[None]] = {}
        self._running = False
        self._last_readings: dict[SensorType, SensorReading] = {}

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize sensor subsystem.

        Subclasses must:
        1. Check platform availability
        2. Discover available sensors
        3. Populate self._available_sensors
        4. Set self._running = True on success

        Returns:
            True if initialization successful
        """

    @abstractmethod
    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value.

        Subclasses must:
        1. Check sensor in self._available_sensors
        2. Read hardware/API
        3. Return SensorReading

        Args:
            sensor: Sensor type to read

        Returns:
            Current sensor reading

        Raises:
            RuntimeError: If sensor not available or read fails
        """

    async def list_sensors(self) -> list[SensorType]:
        """List available sensors.

        Returns:
            List of available sensor types
        """
        return list(self._available_sensors)

    async def subscribe(
        self,
        sensor: SensorType,
        callback: Callable[[SensorReading], Awaitable[None]],
        rate_hz: int = 10,
    ) -> None:
        """Subscribe to sensor updates.

        Args:
            sensor: Sensor to subscribe to
            callback: Async callback for readings
            rate_hz: Sampling rate in Hz (default 10)

        Raises:
            RuntimeError: If sensor not available
        """
        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        if sensor not in self._subscribers:
            self._subscribers[sensor] = []

        self._subscribers[sensor].append(callback)

        # Start polling task if not already running
        if sensor not in self._subscription_tasks:
            interval = 1.0 / rate_hz
            task = asyncio.create_task(self._poll_sensor(sensor, interval))
            self._subscription_tasks[sensor] = task

    async def _poll_sensor(self, sensor: SensorType, interval: float) -> None:
        """Poll sensor and dispatch to subscribers.

        Args:
            sensor: Sensor to poll
            interval: Polling interval in seconds
        """
        while self._running and sensor in self._subscribers:
            try:
                reading = await self.read(sensor)
                self._last_readings[sensor] = reading

                for callback in self._subscribers.get(sensor, []):
                    try:
                        await callback(reading)
                    except Exception as e:
                        logger.error(f"Error in sensor callback: {e}")

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sensor polling error for {sensor}: {e}")
                await asyncio.sleep(1.0)  # Back off on error

    async def unsubscribe(self, sensor: SensorType) -> None:
        """Unsubscribe from sensor updates.

        Args:
            sensor: Sensor to unsubscribe from
        """
        self._subscribers.pop(sensor, None)

        if sensor in self._subscription_tasks:
            self._subscription_tasks[sensor].cancel()
            try:
                await self._subscription_tasks[sensor]
            except asyncio.CancelledError:
                pass
            del self._subscription_tasks[sensor]

    async def shutdown(self) -> None:
        """Shutdown sensor manager and cleanup resources."""
        self._running = False

        # Cancel all polling tasks
        # Cancel all tasks first
        for task in self._subscription_tasks.values():
            task.cancel()
        # Wait for all cancellations in parallel
        if self._subscription_tasks:
            await asyncio.gather(*self._subscription_tasks.values(), return_exceptions=True)

        self._subscription_tasks.clear()
        self._subscribers.clear()
        self._last_readings.clear()

        logger.info(f"✅ {self.__class__.__name__} shutdown complete")

    def get_last_reading(self, sensor: SensorType) -> SensorReading | None:
        """Get last cached reading for a sensor.

        Useful for sensors that update via events (e.g., WASM DeviceMotion).

        Args:
            sensor: Sensor type

        Returns:
            Last reading or None if not available
        """
        return self._last_readings.get(sensor)

    @property
    def is_running(self) -> bool:
        """Check if sensor manager is running."""
        return self._running

    @property
    def available_sensor_count(self) -> int:
        """Get count of available sensors."""
        return len(self._available_sensors)
