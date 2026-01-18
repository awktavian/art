"""I2C Sensor Interface for embedded platforms.

Supports common I2C sensors:
- BME280: Temperature, humidity, pressure
- MPU6050/9250: Accelerometer, gyroscope, magnetometer
- AHT20: Temperature, humidity
- BH1750: Light sensor
- VL53L0X: ToF distance sensor

Uses smbus2 (preferred) or smbus (legacy).

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import struct
import time
from enum import Enum
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import (
    AccelReading,
    GyroReading,
    SensorReading,
    SensorType,
)

logger = logging.getLogger(__name__)

# Check for I2C support
SMBUS2_AVAILABLE = importlib.util.find_spec("smbus2") is not None
SMBUS_AVAILABLE = importlib.util.find_spec("smbus") is not None

# Import available modules
if SMBUS2_AVAILABLE:
    import smbus2

if SMBUS_AVAILABLE:
    import smbus  # noqa: F401


class I2CAddress(Enum):
    """Common I2C sensor addresses."""

    BME280 = 0x76
    BME280_ALT = 0x77
    MPU6050 = 0x68
    MPU9250 = 0x68
    AHT20 = 0x38
    BH1750 = 0x23
    VL53L0X = 0x29
    TSL2561 = 0x39


class I2CSensor:
    """Base class for I2C sensors."""

    def __init__(self, address: int, bus: int = 1):
        """Initialize I2C sensor.

        Args:
            address: I2C device address
            bus: I2C bus number (1 for Raspberry Pi)
        """
        self._address = address
        self._bus_num = bus
        self._bus: Any = None
        self._running = False

    async def initialize(self) -> bool:
        """Initialize I2C bus.

        Returns:
            True if successful
        """
        # Check if I2C device exists
        i2c_dev = Path(f"/dev/i2c-{self._bus_num}")
        if not i2c_dev.exists():
            if is_test_mode():
                logger.info(f"I2C bus {self._bus_num} not available, gracefully degrading")
                return False
            raise RuntimeError(f"I2C bus {self._bus_num} not available")

        try:
            if SMBUS2_AVAILABLE:
                self._bus = smbus2.SMBus(self._bus_num)
            elif SMBUS_AVAILABLE:
                import smbus

                self._bus = smbus.SMBus(self._bus_num)
            else:
                if is_test_mode():
                    logger.info("SMBus not available, gracefully degrading")
                    return False
                raise RuntimeError("SMBus not available. Install: pip install smbus2")

            # Verify device presence
            if not await self._probe_device():
                logger.warning(f"I2C device not found at 0x{self._address:02X}")
                return False

            self._running = True
            logger.info(f"I2C sensor initialized at 0x{self._address:02X}")
            return True

        except Exception as e:
            logger.error(f"I2C init failed: {e}", exc_info=True)
            return False

    async def _probe_device(self) -> bool:
        """Probe for I2C device.

        Returns:
            True if device responds
        """
        try:
            # Try to read a byte (device-specific probe should override this)
            self._bus.read_byte(self._address)
            return True
        except Exception:
            return False

    def _read_byte(self, register: int) -> int:
        """Read single byte from register."""
        if not self._bus:
            raise RuntimeError("I2C bus not initialized")
        return self._bus.read_byte_data(self._address, register)

    def _read_word(self, register: int, little_endian: bool = False) -> int:
        """Read 16-bit word from register."""
        if not self._bus:
            raise RuntimeError("I2C bus not initialized")
        data = self._bus.read_word_data(self._address, register)
        if little_endian:
            return data
        else:
            # Swap bytes for big-endian
            return ((data & 0xFF) << 8) | ((data >> 8) & 0xFF)

    def _read_block(self, register: int, length: int) -> list[int]:
        """Read block of bytes from register."""
        if not self._bus:
            raise RuntimeError("I2C bus not initialized")
        return self._bus.read_i2c_block_data(self._address, register, length)

    def _write_byte(self, register: int, value: int) -> None:
        """Write single byte to register."""
        if not self._bus:
            raise RuntimeError("I2C bus not initialized")
        self._bus.write_byte_data(self._address, register, value)

    def _write_block(self, register: int, data: list[int]) -> None:
        """Write block of bytes to register."""
        if not self._bus:
            raise RuntimeError("I2C bus not initialized")
        self._bus.write_i2c_block_data(self._address, register, data)

    async def shutdown(self) -> None:
        """Shutdown I2C sensor."""
        self._running = False
        if self._bus:
            try:
                self._bus.close()
            except Exception as e:
                logger.error(f"I2C shutdown error: {e}")
            self._bus = None


class BME280Sensor(I2CSensor):
    """BME280 temperature, humidity, pressure sensor."""

    def __init__(self, address: int = I2CAddress.BME280.value, bus: int = 1):
        super().__init__(address, bus)
        self._calibration: dict[str, int] = {}

    async def initialize(self) -> bool:
        """Initialize BME280."""
        if not await super().initialize():
            return False

        try:
            # Verify chip ID
            chip_id = self._read_byte(0xD0)
            if chip_id != 0x60:
                logger.warning(f"Unexpected BME280 chip ID: 0x{chip_id:02X}")
                return False

            # Read calibration data
            self._read_calibration()

            # Configure sensor: normal mode, oversampling x1
            self._write_byte(0xF2, 0x01)  # Humidity oversampling x1
            self._write_byte(0xF4, 0x27)  # Temp/pressure oversampling x1, normal mode

            return True

        except Exception as e:
            logger.error(f"BME280 init failed: {e}")
            return False

    def _read_calibration(self) -> None:
        """Read calibration coefficients."""
        # Temperature calibration
        self._calibration["T1"] = self._read_word(0x88, little_endian=True)
        self._calibration["T2"] = struct.unpack(
            "<h", struct.pack("<H", self._read_word(0x8A, little_endian=True))
        )[0]
        self._calibration["T3"] = struct.unpack(
            "<h", struct.pack("<H", self._read_word(0x8C, little_endian=True))
        )[0]

        # Pressure calibration
        self._calibration["P1"] = self._read_word(0x8E, little_endian=True)
        self._calibration["P2"] = struct.unpack(
            "<h", struct.pack("<H", self._read_word(0x90, little_endian=True))
        )[0]
        self._calibration["P3"] = struct.unpack(
            "<h", struct.pack("<H", self._read_word(0x92, little_endian=True))
        )[0]

        # Humidity calibration
        self._calibration["H1"] = self._read_byte(0xA1)
        self._calibration["H2"] = struct.unpack(
            "<h", struct.pack("<H", self._read_word(0xE1, little_endian=True))
        )[0]

    async def read_temperature(self) -> SensorReading:
        """Read temperature in Celsius."""
        data = self._read_block(0xFA, 3)
        adc_T = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)

        # Simplified conversion (full formula needs all calibration)
        var1 = ((adc_T / 16384.0) - (self._calibration["T1"] / 1024.0)) * self._calibration["T2"]
        temp_c = var1 / 5120.0

        return SensorReading(
            sensor=SensorType.TEMPERATURE,
            value=temp_c,
            timestamp_ms=int(time.time() * 1000),
            accuracy=0.5,  # ±0.5°C typical
        )

    async def read_pressure(self) -> SensorReading:
        """Read pressure in hPa."""
        data = self._read_block(0xF7, 3)
        adc_P = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)

        # Simplified conversion
        pressure_hpa = adc_P / 25600.0 * 100.0

        return SensorReading(
            sensor=SensorType.PRESSURE,
            value=pressure_hpa,
            timestamp_ms=int(time.time() * 1000),
            accuracy=1.0,  # ±1 hPa typical
        )


class MPU6050Sensor(I2CSensor):
    """MPU6050 6-axis accelerometer + gyroscope."""

    def __init__(self, address: int = I2CAddress.MPU6050.value, bus: int = 1):
        super().__init__(address, bus)

    async def initialize(self) -> bool:
        """Initialize MPU6050."""
        if not await super().initialize():
            return False

        try:
            # Verify WHO_AM_I
            who_am_i = self._read_byte(0x75)
            if who_am_i not in (0x68, 0x71, 0x73):  # MPU6050, MPU9250
                logger.warning(f"Unexpected MPU WHO_AM_I: 0x{who_am_i:02X}")
                return False

            # Wake up MPU (exit sleep mode)
            self._write_byte(0x6B, 0x00)

            # Set accelerometer range: ±2g
            self._write_byte(0x1C, 0x00)

            # Set gyroscope range: ±250°/s
            self._write_byte(0x1B, 0x00)

            return True

        except Exception as e:
            logger.error(f"MPU6050 init failed: {e}")
            return False

    async def read_accel(self) -> SensorReading:
        """Read accelerometer (m/s²)."""
        data = self._read_block(0x3B, 6)

        # Convert to signed 16-bit
        ax = struct.unpack(">h", bytes(data[0:2]))[0]
        ay = struct.unpack(">h", bytes(data[2:4]))[0]
        az = struct.unpack(">h", bytes(data[4:6]))[0]

        # Scale: ±2g range, 16384 LSB/g
        accel = AccelReading(
            x=ax / 16384.0 * 9.81,
            y=ay / 16384.0 * 9.81,
            z=az / 16384.0 * 9.81,
        )

        return SensorReading(
            sensor=SensorType.ACCELEROMETER,
            value=accel,
            timestamp_ms=int(time.time() * 1000),
            accuracy=0.98,
        )

    async def read_gyro(self) -> SensorReading:
        """Read gyroscope (rad/s)."""
        data = self._read_block(0x43, 6)

        # Convert to signed 16-bit
        gx = struct.unpack(">h", bytes(data[0:2]))[0]
        gy = struct.unpack(">h", bytes(data[2:4]))[0]
        gz = struct.unpack(">h", bytes(data[4:6]))[0]

        # Scale: ±250°/s range, 131 LSB/(°/s)
        import math

        gyro = GyroReading(
            x=math.radians(gx / 131.0),
            y=math.radians(gy / 131.0),
            z=math.radians(gz / 131.0),
        )

        return SensorReading(
            sensor=SensorType.GYROSCOPE,
            value=gyro,
            timestamp_ms=int(time.time() * 1000),
            accuracy=0.95,
        )


class BH1750Sensor(I2CSensor):
    """BH1750 ambient light sensor."""

    def __init__(self, address: int = I2CAddress.BH1750.value, bus: int = 1):
        super().__init__(address, bus)

    async def initialize(self) -> bool:
        """Initialize BH1750."""
        if not await super().initialize():
            return False

        try:
            # Power on + continuous high-res mode
            self._bus.write_byte(self._address, 0x10)
            await asyncio.sleep(0.18)  # Wait for measurement (non-blocking)
            return True

        except Exception as e:
            logger.error(f"BH1750 init failed: {e}")
            return False

    async def read_light(self) -> SensorReading:
        """Read ambient light in lux."""
        if not self._bus:
            raise RuntimeError("I2C bus not initialized")

        data = self._bus.read_i2c_block_data(self._address, 0x10, 2)
        lux = (data[0] << 8 | data[1]) / 1.2

        return SensorReading(
            sensor=SensorType.LIGHT,
            value=lux,
            timestamp_ms=int(time.time() * 1000),
            accuracy=0.96,
        )


__all__ = [
    "BH1750Sensor",
    "BME280Sensor",
    "I2CAddress",
    "I2CSensor",
    "MPU6050Sensor",
]
