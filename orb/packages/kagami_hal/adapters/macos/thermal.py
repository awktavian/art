"""macOS Thermal Sensors via sysctl/SMC.

Provides thermal monitoring on macOS:
- CPU thermal levels via sysctl
- SMC temperature sensors (if available)
- Fan speeds (if available)

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import subprocess
import sys

from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

# Platform check
MACOS_AVAILABLE = sys.platform == "darwin"


class MacOSThermal:
    """macOS thermal sensor implementation."""

    def __init__(self) -> None:
        """Initialize thermal sensors."""
        self._initialized = False
        self._has_thermal_level = False
        self._has_smc = False

    async def initialize(self) -> bool:
        """Initialize thermal sensors.

        Returns:
            True if thermal sensors available
        """
        if not MACOS_AVAILABLE:
            logger.warning("Thermal sensors only available on macOS")
            return False

        # Check thermal level via sysctl
        try:
            result = subprocess.run(
                ["sysctl", "machdep.xcpm.cpu_thermal_level"],
                capture_output=True,
                timeout=1,
            )
            self._has_thermal_level = result.returncode == 0
        except Exception:
            self._has_thermal_level = False

        # Check SMC access (requires third-party tool or low-level access)
        # For now, we'll rely on thermal level
        self._has_smc = False

        self._initialized = True

        if self._has_thermal_level:
            logger.info("✅ Thermal sensors initialized (thermal level)")
        else:
            logger.warning("Thermal sensors not available")

        return self._has_thermal_level

    async def read_cpu_thermal_level(self) -> int:
        """Read CPU thermal level.

        Returns:
            Thermal level (0-100, higher = hotter)

        Raises:
            RuntimeError: If thermal level not available
        """
        if not self._initialized or not self._has_thermal_level:
            raise RuntimeError("Thermal level not available")

        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.xcpm.cpu_thermal_level"],
                capture_output=True,
                timeout=1,
                text=True,
            )

            if result.returncode == 0:
                return int(result.stdout.strip())
            else:
                raise RuntimeError("Failed to read thermal level")

        except Exception as e:
            raise RuntimeError(f"Failed to read thermal level: {e}") from e

    async def read_cpu_temperature(self) -> float:
        """Read estimated CPU temperature in Celsius.

        Uses thermal level to estimate temperature:
        - Base temp ~40°C
        - Add ~0.5°C per thermal level

        Returns:
            Temperature in Celsius (approximate)

        Raises:
            RuntimeError: If thermal sensors not available
        """
        thermal_level = await self.read_cpu_thermal_level()

        # Estimate temperature (rough approximation)
        # Base temp ~40°C, add ~0.5°C per level
        temp_celsius = 40.0 + (thermal_level * 0.5)

        return temp_celsius

    async def read_sensor(self) -> SensorReading:
        """Read thermal sensor (for HAL sensor interface compatibility).

        Returns:
            SensorReading with temperature as value
        """
        temp = await self.read_cpu_temperature()

        import time

        return SensorReading(
            sensor=SensorType.TEMPERATURE,
            value=temp,
            timestamp_ms=int(time.time() * 1000),
            accuracy=0.7,  # Approximate (based on thermal level, not direct sensor)
        )

    async def shutdown(self) -> None:
        """Shutdown thermal sensors."""
        self._initialized = False
        logger.info("✅ Thermal sensors shutdown")


__all__ = ["MacOSThermal"]
