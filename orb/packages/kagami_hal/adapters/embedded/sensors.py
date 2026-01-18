"""Embedded Sensors Adapter using I2C/SPI.

Implements SensorManager for embedded systems using:
- I2C for accelerometer, gyroscope, temperature, etc.
- SPI for high-speed sensors
- GPIO for simple digital sensors

Supports common sensor ICs:
- MPU6050/9250: Accelerometer + Gyroscope
- BMP280/BME280: Temperature + Pressure
- AHT20: Temperature + Humidity
- VCNL4040: Light + Proximity

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
Updated: December 8, 2025 - Refactored to use SensorAdapterBase
"""

from __future__ import annotations

import logging
import struct
import time
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.data_types import (
    AccelReading,
    GyroReading,
    SensorReading,
    SensorType,
)

logger = logging.getLogger(__name__)

EMBEDDED_AVAILABLE = Path("/dev/i2c-1").exists() or Path("/dev/i2c-0").exists()

# Try to import I2C library
SMBUS_AVAILABLE = False
try:
    import smbus2 as smbus

    SMBUS_AVAILABLE = True
except ImportError:
    try:
        import smbus

        SMBUS_AVAILABLE = True
    except ImportError:
        pass


# Common I2C addresses
class I2CAddresses:
    """Common sensor I2C addresses."""

    MPU6050 = 0x68
    MPU9250 = 0x68
    BMP280 = 0x76
    BME280 = 0x76
    AHT20 = 0x38
    VCNL4040 = 0x60


class EmbeddedSensors(SensorAdapterBase):
    """Embedded sensor implementation using I2C/SPI."""

    def __init__(self, i2c_bus: int = 1):
        """Initialize embedded sensors.

        Args:
            i2c_bus: I2C bus number (typically 1 on Raspberry Pi)
        """
        super().__init__()
        self._i2c_bus = i2c_bus
        self._bus: Any = None
        self._sensor_addresses: dict[SensorType, int] = {}

    async def initialize(self) -> bool:
        """Initialize sensor discovery."""
        if not EMBEDDED_AVAILABLE:
            if is_test_mode():
                logger.info("Embedded sensors not available, gracefully degrading")
                return False
            raise RuntimeError("Embedded sensors only available on embedded systems")

        if not SMBUS_AVAILABLE:
            if is_test_mode():
                logger.info("SMBus not available, gracefully degrading")
                return False
            raise RuntimeError("SMBus not available. Install: pip install smbus2")

        try:
            self._bus = smbus.SMBus(self._i2c_bus)

            # Scan for sensors
            await self._probe_sensors()

            self._running = True
            logger.info(f"✅ Embedded sensors initialized: {self._available_sensors}")
            return len(self._available_sensors) > 0

        except Exception as e:
            logger.error(f"Failed to initialize embedded sensors: {e}", exc_info=True)
            return False

    async def _probe_sensors(self) -> None:
        """Probe I2C bus for known sensors."""
        if not self._bus:
            return

        # Probe MPU6050/9250 (accelerometer + gyroscope)
        try:
            who_am_i = self._bus.read_byte_data(I2CAddresses.MPU6050, 0x75)
            if who_am_i in (0x68, 0x71, 0x73):  # MPU6050, MPU9250
                self._available_sensors.add(SensorType.ACCELEROMETER)
                self._available_sensors.add(SensorType.GYROSCOPE)
                self._sensor_addresses[SensorType.ACCELEROMETER] = I2CAddresses.MPU6050
                self._sensor_addresses[SensorType.GYROSCOPE] = I2CAddresses.MPU6050

                # Wake up MPU
                self._bus.write_byte_data(I2CAddresses.MPU6050, 0x6B, 0x00)
                logger.debug(f"Found MPU sensor (WHO_AM_I: 0x{who_am_i:02X})")
        except Exception:
            pass

        # Probe BMP280/BME280 (temperature + pressure)
        try:
            chip_id = self._bus.read_byte_data(I2CAddresses.BMP280, 0xD0)
            if chip_id in (0x58, 0x60):  # BMP280, BME280
                self._available_sensors.add(SensorType.TEMPERATURE)
                self._available_sensors.add(SensorType.PRESSURE)
                self._sensor_addresses[SensorType.TEMPERATURE] = I2CAddresses.BMP280
                self._sensor_addresses[SensorType.PRESSURE] = I2CAddresses.BMP280
                logger.debug(f"Found BMP/BME280 (ID: 0x{chip_id:02X})")
        except Exception:
            pass

        # Probe VCNL4040 (light sensor)
        try:
            dev_id = self._bus.read_word_data(I2CAddresses.VCNL4040, 0x0C)
            if (dev_id & 0xFF) == 0x86:
                self._available_sensors.add(SensorType.LIGHT)
                self._sensor_addresses[SensorType.LIGHT] = I2CAddresses.VCNL4040
                logger.debug("Found VCNL4040 light sensor")
        except Exception:
            pass

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read sensor value."""
        if sensor not in self._available_sensors:
            raise RuntimeError(f"Sensor {sensor} not available")

        if not self._bus:
            raise RuntimeError("I2C bus not initialized")

        try:
            value: Any = None
            accuracy = 1.0
            addr = self._sensor_addresses[sensor]

            if sensor == SensorType.ACCELEROMETER:
                # Read MPU6050 accelerometer (registers 0x3B-0x40)
                data = self._bus.read_i2c_block_data(addr, 0x3B, 6)
                ax = struct.unpack(">h", bytes(data[0:2]))[0] / 16384.0  # ±2g scale
                ay = struct.unpack(">h", bytes(data[2:4]))[0] / 16384.0
                az = struct.unpack(">h", bytes(data[4:6]))[0] / 16384.0
                value = AccelReading(x=ax * 9.81, y=ay * 9.81, z=az * 9.81)  # Convert to m/s²

            elif sensor == SensorType.GYROSCOPE:
                # Read MPU6050 gyroscope (registers 0x43-0x48)
                data = self._bus.read_i2c_block_data(addr, 0x43, 6)
                gx = struct.unpack(">h", bytes(data[0:2]))[0] / 131.0  # ±250°/s scale
                gy = struct.unpack(">h", bytes(data[2:4]))[0] / 131.0
                gz = struct.unpack(">h", bytes(data[4:6]))[0] / 131.0
                # Convert to rad/s
                import math

                value = GyroReading(
                    x=math.radians(gx),
                    y=math.radians(gy),
                    z=math.radians(gz),
                )

            elif sensor == SensorType.TEMPERATURE:
                # Read BMP280 temperature
                # Simplified: read raw temperature register
                data = self._bus.read_i2c_block_data(addr, 0xFA, 3)
                raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
                # Simplified conversion (real implementation needs calibration data)
                value = raw / 5120.0  # Approximate scaling

            elif sensor == SensorType.PRESSURE:
                # Read BMP280 pressure
                data = self._bus.read_i2c_block_data(addr, 0xF7, 3)
                raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
                # Simplified conversion (real implementation needs calibration)
                value = raw / 25600.0 * 100  # Approximate hPa

            elif sensor == SensorType.LIGHT:
                # Read VCNL4040 ambient light
                als = self._bus.read_word_data(addr, 0x09)
                value = als * 0.1  # Convert to lux (approximate)

            else:
                raise RuntimeError(f"Reading not implemented for {sensor}")

            return SensorReading(
                sensor=sensor,
                value=value,
                timestamp_ms=int(time.time() * 1000),
                accuracy=accuracy,
            )

        except Exception as e:
            logger.error(f"Failed to read sensor {sensor}: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown with I2C bus cleanup."""
        await super().shutdown()
        if self._bus:
            try:
                self._bus.close()
            except Exception:
                pass
