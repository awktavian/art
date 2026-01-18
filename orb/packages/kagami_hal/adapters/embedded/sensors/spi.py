"""SPI Sensor Interface for embedded platforms.

Supports:
- MCP3008/3208: 8-channel 10/12-bit ADC
- MAX31855: Thermocouple amplifier
- ADXL345: 3-axis accelerometer (SPI mode)

Uses spidev library.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import struct
import time
from enum import Enum
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import AccelReading, SensorReading, SensorType

logger = logging.getLogger(__name__)

# Check for SPI support
SPIDEV_AVAILABLE = False

try:
    import spidev

    SPIDEV_AVAILABLE = True
except ImportError:
    pass


class SPIMode(Enum):
    """SPI clock modes."""

    MODE_0 = 0  # CPOL=0, CPHA=0
    MODE_1 = 1  # CPOL=0, CPHA=1
    MODE_2 = 2  # CPOL=1, CPHA=0
    MODE_3 = 3  # CPOL=1, CPHA=1


class SPISensor:
    """Base class for SPI sensors."""

    def __init__(
        self,
        bus: int = 0,
        device: int = 0,
        max_speed_hz: int = 1000000,
        mode: SPIMode = SPIMode.MODE_0,
    ):
        """Initialize SPI sensor.

        Args:
            bus: SPI bus number
            device: SPI device/chip select number
            max_speed_hz: Maximum SPI clock speed
            mode: SPI clock mode
        """
        self._bus_num = bus
        self._device_num = device
        self._max_speed_hz = max_speed_hz
        self._mode = mode
        self._spi: Any = None
        self._running = False

    async def initialize(self) -> bool:
        """Initialize SPI bus.

        Returns:
            True if successful
        """
        # Check if SPI device exists
        spi_dev = Path(f"/dev/spidev{self._bus_num}.{self._device_num}")
        if not spi_dev.exists():
            if is_test_mode():
                logger.info(f"SPI device {spi_dev} not available, gracefully degrading")
                return False
            raise RuntimeError(f"SPI device {spi_dev} not available")

        if not SPIDEV_AVAILABLE:
            if is_test_mode():
                logger.info("spidev not available, gracefully degrading")
                return False
            raise RuntimeError("spidev not available. Install: pip install spidev")

        try:
            self._spi = spidev.SpiDev()
            self._spi.open(self._bus_num, self._device_num)
            self._spi.max_speed_hz = self._max_speed_hz
            self._spi.mode = self._mode.value

            self._running = True
            logger.info(
                f"SPI sensor initialized: bus {self._bus_num}, device {self._device_num}, "
                f"{self._max_speed_hz} Hz"
            )
            return True

        except Exception as e:
            logger.error(f"SPI init failed: {e}", exc_info=True)
            return False

    def _transfer(self, data: list[int]) -> list[int]:
        """Transfer data over SPI.

        Args:
            data: Bytes to send

        Returns:
            Bytes received
        """
        if not self._spi:
            raise RuntimeError("SPI not initialized")
        return self._spi.xfer2(data)

    async def shutdown(self) -> None:
        """Shutdown SPI sensor."""
        self._running = False
        if self._spi:
            try:
                self._spi.close()
            except Exception as e:
                logger.error(f"SPI shutdown error: {e}")
            self._spi = None


class MCP3008Sensor(SPISensor):
    """MCP3008 8-channel 10-bit ADC.

    Used for reading analog sensors (potentiometers, thermistors, etc.).
    """

    def __init__(self, bus: int = 0, device: int = 0, vref: float = 3.3):
        """Initialize MCP3008.

        Args:
            bus: SPI bus number
            device: SPI device number
            vref: Reference voltage (typically 3.3V)
        """
        super().__init__(bus, device, max_speed_hz=1350000, mode=SPIMode.MODE_0)
        self._vref = vref

    async def read_channel(self, channel: int) -> SensorReading:
        """Read ADC channel.

        Args:
            channel: Channel number (0-7)

        Returns:
            SensorReading with voltage value
        """
        if not 0 <= channel <= 7:
            raise ValueError("Channel must be 0-7")

        if not self._spi:
            raise RuntimeError("SPI not initialized")

        # MCP3008 command: start bit + single-ended + channel
        # [1, (8+channel)<<4, 0]
        cmd = [1, (8 + channel) << 4, 0]
        result = self._transfer(cmd)

        # Parse 10-bit result from 3 bytes
        # Result is in bits 9:0 of the last 2 bytes
        adc_value = ((result[1] & 0x03) << 8) | result[2]

        # Convert to voltage
        voltage = (adc_value / 1023.0) * self._vref

        return SensorReading(
            sensor=SensorType.LIGHT,  # Generic analog sensor
            value=voltage,
            timestamp_ms=int(time.time() * 1000),
            accuracy=0.98,
        )

    async def read_all_channels(self) -> dict[int, float]:
        """Read all 8 channels.

        Returns:
            Dict mapping channel number to voltage
        """
        channels = {}
        for ch in range(8):
            reading = await self.read_channel(ch)
            channels[ch] = reading.value
        return channels


class MAX31855Sensor(SPISensor):
    """MAX31855 thermocouple amplifier (K-type).

    Reads high-temperature thermocouples with cold-junction compensation.
    """

    def __init__(self, bus: int = 0, device: int = 0):
        """Initialize MAX31855.

        Args:
            bus: SPI bus number
            device: SPI device number
        """
        super().__init__(bus, device, max_speed_hz=5000000, mode=SPIMode.MODE_0)

    async def read_temperature(self) -> SensorReading:
        """Read thermocouple temperature in Celsius.

        Returns:
            SensorReading with temperature
        """
        if not self._spi:
            raise RuntimeError("SPI not initialized")

        # Read 4 bytes from MAX31855
        data = self._transfer([0x00, 0x00, 0x00, 0x00])

        # Pack into 32-bit word
        raw = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]

        # Check for faults (bit 16)
        if raw & 0x00010000:
            # Parse fault bits
            faults = []
            if raw & 0x01:
                faults.append("open_circuit")
            if raw & 0x02:
                faults.append("short_to_gnd")
            if raw & 0x04:
                faults.append("short_to_vcc")
            raise RuntimeError(f"Thermocouple fault: {', '.join(faults)}")

        # Extract thermocouple temperature (bits 31:18)
        temp_raw = (raw >> 18) & 0x3FFF

        # Check sign bit (bit 13 of temp_raw)
        if temp_raw & 0x2000:
            # Negative temperature (2's complement)
            temp_raw = temp_raw - 0x4000

        # Convert to Celsius (0.25°C resolution)
        temp_c = temp_raw * 0.25

        return SensorReading(
            sensor=SensorType.TEMPERATURE,
            value=temp_c,
            timestamp_ms=int(time.time() * 1000),
            accuracy=2.0,  # ±2°C typical
        )

    async def read_internal_temperature(self) -> float:
        """Read internal cold-junction temperature in Celsius.

        Returns:
            Internal temperature
        """
        if not self._spi:
            raise RuntimeError("SPI not initialized")

        data = self._transfer([0x00, 0x00, 0x00, 0x00])
        raw = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]

        # Extract internal temperature (bits 15:4)
        temp_raw = (raw >> 4) & 0x0FFF

        # Check sign bit
        if temp_raw & 0x0800:
            temp_raw = temp_raw - 0x1000

        # Convert to Celsius (0.0625°C resolution)
        return temp_raw * 0.0625


class ADXL345Sensor(SPISensor):
    """ADXL345 3-axis accelerometer (SPI mode).

    High-resolution (13-bit) digital accelerometer with ±2g to ±16g range.
    """

    def __init__(self, bus: int = 0, device: int = 0, g_range: int = 2):
        """Initialize ADXL345.

        Args:
            bus: SPI bus number
            device: SPI device number
            g_range: Measurement range in g (2, 4, 8, 16)
        """
        super().__init__(bus, device, max_speed_hz=5000000, mode=SPIMode.MODE_3)
        self._g_range = g_range
        self._scale_factor = 0.0039  # Default for ±2g

    async def initialize(self) -> bool:
        """Initialize ADXL345."""
        if not await super().initialize():
            return False

        try:
            # Verify DEVID (should be 0xE5)
            devid = self._read_register(0x00)
            if devid != 0xE5:
                logger.warning(f"Unexpected ADXL345 DEVID: 0x{devid:02X}")
                return False

            # Set data format
            if self._g_range == 2:
                range_bits = 0x00
                self._scale_factor = 0.0039
            elif self._g_range == 4:
                range_bits = 0x01
                self._scale_factor = 0.0078
            elif self._g_range == 8:
                range_bits = 0x02
                self._scale_factor = 0.0156
            elif self._g_range == 16:
                range_bits = 0x03
                self._scale_factor = 0.0312
            else:
                raise ValueError("g_range must be 2, 4, 8, or 16")

            # Write DATA_FORMAT register (0x31): full resolution + range
            self._write_register(0x31, 0x08 | range_bits)

            # Enable measurement (POWER_CTL register 0x2D)
            self._write_register(0x2D, 0x08)

            return True

        except Exception as e:
            logger.error(f"ADXL345 init failed: {e}")
            return False

    def _read_register(self, reg: int) -> int:
        """Read single register."""
        # SPI read: set MSB, single byte
        cmd = [(reg | 0x80) | 0x40, 0x00]
        result = self._transfer(cmd)
        return result[1]

    def _write_register(self, reg: int, value: int) -> None:
        """Write single register."""
        # SPI write: clear MSB
        cmd = [reg & 0x7F, value]
        self._transfer(cmd)

    async def read_accel(self) -> SensorReading:
        """Read accelerometer (m/s²).

        Returns:
            SensorReading with AccelReading
        """
        if not self._spi:
            raise RuntimeError("SPI not initialized")

        # Read 6 bytes starting at DATAX0 (0x32)
        # Multi-byte read: set MSB and multi-byte bit
        cmd = [(0x32 | 0x80) | 0x40] + [0x00] * 6
        result = self._transfer(cmd)

        # Parse 16-bit signed values (little-endian)
        x = struct.unpack("<h", bytes(result[1:3]))[0]
        y = struct.unpack("<h", bytes(result[3:5]))[0]
        z = struct.unpack("<h", bytes(result[5:7]))[0]

        # Convert to g, then m/s²
        accel = AccelReading(
            x=x * self._scale_factor * 9.81,
            y=y * self._scale_factor * 9.81,
            z=z * self._scale_factor * 9.81,
        )

        return SensorReading(
            sensor=SensorType.ACCELEROMETER,
            value=accel,
            timestamp_ms=int(time.time() * 1000),
            accuracy=0.98,
        )


__all__ = [
    "ADXL345Sensor",
    "MAX31855Sensor",
    "MCP3008Sensor",
    "SPIMode",
    "SPISensor",
]
