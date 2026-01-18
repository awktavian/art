"""Mock implementations for testing ONLY.

These mocks are NEVER used in production code.
They are only for tests where hardware is unavailable.

Created: November 10, 2025
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from kagami_hal.data_types import (
    AccelReading,
    GPSReading,
    GyroReading,
    HeartRateReading,
)


class MockHeartRateSensor:
    """Mock heart rate sensor for testing."""

    def __init__(self) -> None:
        self._bpm = 72
        self._initialized = False

    async def probe(self) -> bool:
        return True

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def read_heart_rate(self) -> HeartRateReading:
        if not self._initialized:
            raise RuntimeError("Not initialized")

        import random

        bpm = self._bpm + random.randint(-5, 5)
        return HeartRateReading(bpm=bpm, confidence=0.85)

    async def shutdown(self) -> None:
        pass


class MockIMU:
    """Mock IMU for testing."""

    def __init__(self) -> None:
        self._initialized = False

    async def probe(self) -> bool:
        return True

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def read_accelerometer(self) -> AccelReading:
        if not self._initialized:
            raise RuntimeError("Not initialized")
        return AccelReading(x=0.0, y=0.0, z=9.81)

    async def read_gyroscope(self) -> GyroReading:
        if not self._initialized:
            raise RuntimeError("Not initialized")
        return GyroReading(x=0.0, y=0.0, z=0.0)

    async def shutdown(self) -> None:
        pass


class MockGPS:
    """Mock GPS for testing."""

    def __init__(self) -> None:
        self._initialized = False
        self._lat = 37.7749
        self._lon = -122.4194

    async def probe(self) -> bool:
        return True

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def read_position(self) -> GPSReading:
        if not self._initialized:
            raise RuntimeError("Not initialized")

        return GPSReading(latitude=self._lat, longitude=self._lon, altitude=100.0, accuracy=10.0)

    async def shutdown(self) -> None:
        pass
