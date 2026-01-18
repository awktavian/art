"""Base Device Driver Interface for K os HAL.

All device drivers inherit from DeviceDriver and implement standard lifecycle:
- probe(): Detect hardware
- initialize(): Configure hardware
- read()/write(): Data transfer
- ioctl(): Device-specific control
- shutdown(): Clean shutdown

Created: November 10, 2025
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class DriverInfo:
    """Driver metadata."""

    name: str
    version: str
    author: str
    description: str


class DeviceDriver(ABC):
    """Base class for all device drivers.

    Lifecycle:
    1. probe() - Detect if hardware present
    2. initialize() - Configure hardware
    3. [read()/write()/ioctl() operations]
    4. shutdown() - Clean shutdown
    """

    def __init__(self) -> None:
        self._initialized = False
        self._info: DriverInfo | None = None

    @property
    def initialized(self) -> bool:
        """Check if driver is initialized."""
        return self._initialized

    @property
    def info(self) -> DriverInfo | None:
        """Get driver info."""
        return self._info

    @abstractmethod
    async def probe(self) -> bool:
        """Detect if hardware is present.

        Returns:
            True if hardware detected
        """

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize hardware.

        Returns:
            True if initialization succeeded
        """

    @abstractmethod
    async def read(self, buffer: bytearray, count: int) -> int:
        """Read from device.

        Args:
            buffer: Buffer to read into
            count: Number of bytes to read

        Returns:
            Number of bytes actually read
        """

    @abstractmethod
    async def write(self, buffer: bytes, count: int) -> int:
        """Write to device.

        Args:
            buffer: Buffer to write from
            count: Number of bytes to write

        Returns:
            Number of bytes actually written
        """

    @abstractmethod
    async def ioctl(self, cmd: int, arg: Any) -> Any:
        """Device-specific control operation.

        Args:
            cmd: Control command
            arg: Command argument

        Returns:
            Command-specific result
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown device cleanly."""
