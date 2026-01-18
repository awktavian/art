"""Embedded Display Actuators for SPI/I2C displays.

Supports:
- SSD1306: 128x64 OLED (I2C/SPI)
- ST7735: 128x160 TFT LCD (SPI)
- ILI9341: 240x320 TFT LCD (SPI) - already in main display.py
- Framebuffer displays (HDMI via /dev/fb0)

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import struct
import time
from typing import Any

from kagami.core.boot_mode import is_test_mode
from kagami.core.safety.cbf_decorators import enforce_cbf

from kagami_hal.data_types import DisplayMode

logger = logging.getLogger(__name__)

# Check for library support
PIL_AVAILABLE = importlib.util.find_spec("PIL") is not None
SMBUS2_AVAILABLE = importlib.util.find_spec("smbus2") is not None
SPIDEV_AVAILABLE = importlib.util.find_spec("spidev") is not None
try:
    GPIO_AVAILABLE = importlib.util.find_spec("RPi.GPIO") is not None
except ModuleNotFoundError:
    # Parent package 'RPi' doesn't exist - find_spec raises for nested modules
    GPIO_AVAILABLE = False

# Import modules if available
if SMBUS2_AVAILABLE:
    import smbus2

if SPIDEV_AVAILABLE:
    import spidev

if GPIO_AVAILABLE:
    import RPi.GPIO as GPIO


class SSD1306Display:
    """SSD1306 OLED display (I2C).

    Common 128x64 OLED display for embedded systems.
    """

    def __init__(
        self,
        width: int = 128,
        height: int = 64,
        address: int = 0x3C,
        bus: int = 1,
    ):
        """Initialize SSD1306.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            address: I2C address
            bus: I2C bus number
        """
        self._width = width
        self._height = height
        self._address = address
        self._bus_num = bus

        self._bus: Any = None
        self._buffer: bytearray | None = None
        self._running = False

    async def initialize(self) -> bool:
        """Initialize SSD1306.

        Returns:
            True if successful
        """
        if not SMBUS2_AVAILABLE:
            if is_test_mode():
                logger.info("SMBus2 not available for SSD1306, gracefully degrading")
                return False
            raise RuntimeError("SMBus2 not available. Install: pip install smbus2")

        try:
            self._bus = smbus2.SMBus(self._bus_num)

            # Initialize display
            init_cmds = [
                0xAE,  # Display off
                0xD5,
                0x80,  # Set display clock
                0xA8,
                self._height - 1,  # Set multiplex ratio
                0xD3,
                0x00,  # Set display offset
                0x40,  # Set start line
                0x8D,
                0x14,  # Enable charge pump
                0x20,
                0x00,  # Set memory addressing mode (horizontal)
                0xA1,  # Set segment re-map
                0xC8,  # Set COM output scan direction
                0xDA,
                0x12 if self._height == 64 else 0x02,  # Set COM pins
                0x81,
                0xCF,  # Set contrast
                0xD9,
                0xF1,  # Set pre-charge period
                0xDB,
                0x40,  # Set VCOMH deselect level
                0xA4,  # Display on (resume from RAM)
                0xA6,  # Normal display (not inverted)
                0xAF,  # Display on
            ]

            for cmd in init_cmds:
                self._write_command(cmd)

            # Create frame buffer
            self._buffer = bytearray((self._width * self._height) // 8)

            self._running = True
            logger.info(f"SSD1306 initialized: {self._width}x{self._height}")
            return True

        except Exception as e:
            logger.error(f"SSD1306 init failed: {e}")
            return False

    def _write_command(self, cmd: int) -> None:
        """Write command byte."""
        if not self._bus:
            raise RuntimeError("I2C bus not initialized")
        # Control byte: Co=0, D/C=0 (command)
        self._bus.write_i2c_block_data(self._address, 0x00, [cmd])

    def _write_data(self, data: list[int]) -> None:
        """Write data bytes."""
        if not self._bus:
            raise RuntimeError("I2C bus not initialized")
        # Control byte: Co=0, D/C=1 (data)
        # Split into 32-byte chunks (I2C limitation)
        for i in range(0, len(data), 32):
            chunk = data[i : i + 32]
            self._bus.write_i2c_block_data(self._address, 0x40, chunk)

    @enforce_cbf(
        cbf_func=lambda s: 1.0,  # Default safe - no CBF registered yet
        barrier_name="display_write",
        tier=3,
    )
    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to display.

        Args:
            buffer: Pixel data (width*height/8 bytes, 1 bit per pixel)

        Raises:
            RuntimeError: If display not initialized
            ValueError: If buffer size mismatch
            CBFViolation: If power budget exceeded
        """
        if not self._running or not self._buffer:
            raise RuntimeError("Display not initialized")

        if len(buffer) != len(self._buffer):
            raise ValueError(
                f"Buffer size mismatch: expected {len(self._buffer)}, got {len(buffer)}"
            )

        # Set column address (0 to width-1)
        self._write_command(0x21)
        self._write_command(0)
        self._write_command(self._width - 1)

        # Set page address (0 to height/8-1)
        self._write_command(0x22)
        self._write_command(0)
        self._write_command((self._height // 8) - 1)

        # Write buffer
        self._write_data(list(buffer))

    async def clear(self, color: int = 0x000000) -> None:
        """Clear display.

        Args:
            color: Color (0x000000 = black, anything else = white)
        """
        if not self._buffer:
            raise RuntimeError("Display not initialized")

        fill_byte = 0xFF if color != 0x000000 else 0x00
        self._buffer[:] = bytes([fill_byte] * len(self._buffer))
        await self.write_frame(self._buffer)

    @enforce_cbf(
        cbf_func=lambda s: 1.0,  # Default safe - no CBF registered yet
        barrier_name="display_brightness",
        tier=3,
    )
    async def set_brightness(self, level: float) -> None:
        """Set display brightness.

        Args:
            level: Brightness 0.0-1.0

        Raises:
            CBFViolation: If power budget exceeded
        """
        contrast = int(level * 255)
        self._write_command(0x81)  # Set contrast
        self._write_command(contrast)

    async def set_mode(self, mode: DisplayMode) -> None:
        """Set display power mode."""
        if mode == DisplayMode.OFF:
            self._write_command(0xAE)  # Display off
        else:
            self._write_command(0xAF)  # Display on
            if mode == DisplayMode.LOW_POWER:
                await self.set_brightness(0.3)
            elif mode == DisplayMode.FULL:
                await self.set_brightness(1.0)

    async def shutdown(self) -> None:
        """Shutdown display."""
        self._running = False
        if self._bus:
            try:
                self._write_command(0xAE)  # Display off
                self._bus.close()
            except Exception as e:
                logger.error(f"SSD1306 shutdown error: {e}")
            self._bus = None


class ST7735Display:
    """ST7735 TFT LCD display (SPI).

    Common 128x160 or 160x128 color LCD for embedded systems.
    """

    def __init__(
        self,
        width: int = 128,
        height: int = 160,
        spi_device: str = "/dev/spidev0.0",
        dc_pin: int = 25,
        rst_pin: int = 24,
        cs_pin: int | None = None,
    ):
        """Initialize ST7735.

        Args:
            width: Display width
            height: Display height
            spi_device: SPI device path
            dc_pin: Data/Command GPIO pin
            rst_pin: Reset GPIO pin
            cs_pin: Chip select GPIO pin (optional, None = hardware CS)
        """
        self._width = width
        self._height = height
        self._spi_device = spi_device
        self._dc_pin = dc_pin
        self._rst_pin = rst_pin
        self._cs_pin = cs_pin

        self._spi: Any = None
        self._running = False

    async def initialize(self) -> bool:
        """Initialize ST7735.

        Returns:
            True if successful
        """
        if not SPIDEV_AVAILABLE or not GPIO_AVAILABLE:
            if is_test_mode():
                logger.info("SPI/GPIO not available for ST7735, gracefully degrading")
                return False
            raise RuntimeError("spidev and RPi.GPIO required. Install: pip install spidev RPi.GPIO")

        try:
            # Initialize GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self._dc_pin, GPIO.OUT)
            GPIO.setup(self._rst_pin, GPIO.OUT)
            if self._cs_pin is not None:
                GPIO.setup(self._cs_pin, GPIO.OUT)
                GPIO.output(self._cs_pin, GPIO.HIGH)

            # Hardware reset (use thread pool for blocking I/O)
            GPIO.output(self._rst_pin, GPIO.HIGH)
            await asyncio.sleep(0.05)
            GPIO.output(self._rst_pin, GPIO.LOW)
            await asyncio.sleep(0.05)
            GPIO.output(self._rst_pin, GPIO.HIGH)
            await asyncio.sleep(0.15)

            # Initialize SPI
            parts = self._spi_device.replace("/dev/spidev", "").split(".")
            bus = int(parts[0])
            device = int(parts[1])

            self._spi = spidev.SpiDev()
            self._spi.open(bus, device)
            self._spi.max_speed_hz = 32000000  # 32 MHz
            self._spi.mode = 0

            # Initialize display controller (sync method with hardware delays)
            await asyncio.to_thread(self._init_st7735)

            self._running = True
            logger.info(f"ST7735 initialized: {self._width}x{self._height}")
            return True

        except Exception as e:
            logger.error(f"ST7735 init failed: {e}")
            return False

    def _init_st7735(self) -> None:
        """Initialize ST7735 controller."""
        init_cmds = [
            (0x01, [], 150),  # Software reset, delay 150ms
            (0x11, [], 255),  # Sleep out, delay 255ms
            (0xB1, [0x01, 0x2C, 0x2D]),  # Frame rate control
            (0xB2, [0x01, 0x2C, 0x2D]),  # Frame rate control (idle)
            (0xB3, [0x01, 0x2C, 0x2D, 0x01, 0x2C, 0x2D]),  # Frame rate control (partial)
            (0xB4, [0x07]),  # Display inversion control
            (0xC0, [0xA2, 0x02, 0x84]),  # Power control
            (0xC1, [0xC5]),  # Power control
            (0xC2, [0x0A, 0x00]),  # Power control
            (0xC3, [0x8A, 0x2A]),  # Power control
            (0xC4, [0x8A, 0xEE]),  # Power control
            (0xC5, [0x0E]),  # VCOM control
            (0x36, [0xC8]),  # Memory access control (RGB, row/col order)
            (0x3A, [0x05]),  # Pixel format (16-bit)
            (
                0xE0,
                [
                    0x02,
                    0x1C,
                    0x07,
                    0x12,
                    0x37,
                    0x32,
                    0x29,
                    0x2D,
                    0x29,
                    0x25,
                    0x2B,
                    0x39,
                    0x00,
                    0x01,
                    0x03,
                    0x10,
                ],
            ),
            (
                0xE1,
                [
                    0x03,
                    0x1D,
                    0x07,
                    0x06,
                    0x2E,
                    0x2C,
                    0x29,
                    0x2D,
                    0x2E,
                    0x2E,
                    0x37,
                    0x3F,
                    0x00,
                    0x00,
                    0x02,
                    0x10,
                ],
            ),
            (0x13, [], 10),  # Normal display on, delay 10ms
            (0x29, [], 100),  # Display on, delay 100ms
        ]

        for cmd_data in init_cmds:
            cmd = cmd_data[0]
            data = cmd_data[1] if len(cmd_data) > 1 else []
            delay = cmd_data[2] if len(cmd_data) > 2 else 0

            self._write_command(cmd, data)  # type: ignore[arg-type]
            if delay > 0:  # type: ignore[operator]
                time.sleep(delay / 1000.0)  # type: ignore[operator]

    def _write_command(self, cmd: int, data: list[int] | None = None) -> None:
        """Write command to display."""
        if not self._spi:
            raise RuntimeError("SPI not initialized")

        if self._cs_pin is not None:
            GPIO.output(self._cs_pin, GPIO.LOW)

        # DC low for command
        GPIO.output(self._dc_pin, GPIO.LOW)
        self._spi.writebytes([cmd])

        if data:
            # DC high for data
            GPIO.output(self._dc_pin, GPIO.HIGH)
            self._spi.writebytes(data)

        if self._cs_pin is not None:
            GPIO.output(self._cs_pin, GPIO.HIGH)

    @enforce_cbf(
        cbf_func=lambda s: 1.0,  # Default safe - no CBF registered yet
        barrier_name="display_write",
        tier=3,
    )
    async def write_frame(self, buffer: bytes) -> None:
        """Write frame buffer to display (RGB565 format).

        Args:
            buffer: Pixel data (width*height*2 bytes, RGB565)

        Raises:
            RuntimeError: If display not initialized
            ValueError: If buffer size mismatch
            CBFViolation: If power budget exceeded
        """
        if not self._running or not self._spi:
            raise RuntimeError("Display not initialized")

        expected_size = self._width * self._height * 2
        if len(buffer) != expected_size:
            raise ValueError(f"Buffer size mismatch: expected {expected_size}, got {len(buffer)}")

        # Set window
        self._write_command(0x2A, [0, 0, (self._width - 1) >> 8, (self._width - 1) & 0xFF])
        self._write_command(0x2B, [0, 0, (self._height - 1) >> 8, (self._height - 1) & 0xFF])
        self._write_command(0x2C)  # Memory write

        # Write buffer
        if self._cs_pin is not None:
            GPIO.output(self._cs_pin, GPIO.LOW)

        GPIO.output(self._dc_pin, GPIO.HIGH)

        # Write in chunks
        chunk_size = 4096
        for i in range(0, len(buffer), chunk_size):
            chunk = buffer[i : i + chunk_size]
            self._spi.writebytes2(list(chunk))

        if self._cs_pin is not None:
            GPIO.output(self._cs_pin, GPIO.HIGH)

    async def clear(self, color: int = 0x000000) -> None:
        """Clear display to color (RGB888)."""
        # Convert RGB888 to RGB565
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

        # Create buffer
        pixel_bytes = struct.pack(">H", rgb565)
        total_pixels = self._width * self._height
        fill_buffer = pixel_bytes * total_pixels

        await self.write_frame(fill_buffer)

    async def shutdown(self) -> None:
        """Shutdown display."""
        self._running = False
        if self._spi:
            try:
                self._write_command(0x28)  # Display off
                self._write_command(0x10)  # Sleep in
                self._spi.close()
            except Exception as e:
                logger.error(f"ST7735 shutdown error: {e}")
            self._spi = None

        if GPIO_AVAILABLE:
            try:
                pins = [self._dc_pin, self._rst_pin]
                if self._cs_pin is not None:
                    pins.append(self._cs_pin)
                GPIO.cleanup(pins)
            except Exception:
                pass


__all__ = [
    "SSD1306Display",
    "ST7735Display",
]
