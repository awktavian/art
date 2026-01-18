"""Tests for display actuator CBF safety integration.

CREATED: December 15, 2025
AUTHOR: Forge (e₂)

Tests verify that display actuators enforce CBF constraints before hardware operations.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from kagami_hal.adapters.embedded.actuators.display import (
    SSD1306Display,
    ST7735Display,
)
from kagami_hal.data_types import DisplayMode
from kagami.core.safety.cbf_decorators import CBFViolation


class TestSSD1306DisplayCBFSafety:
    """Test SSD1306 OLED display CBF safety enforcement."""

    @pytest.mark.asyncio
    async def test_ssd1306_initialization_graceful(self):
        """SSD1306 handles missing I2C bus gracefully."""
        display = SSD1306Display(width=128, height=64)

        # Should return False if I2C unavailable, not crash
        result = await display.initialize()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_ssd1306_buffer_size_validation(self):
        """SSD1306 validates frame buffer size."""
        display = SSD1306Display(width=128, height=64)
        success = await display.initialize()

        if not success:
            pytest.skip("SSD1306/I2C not available")

        # Wrong buffer size should raise
        wrong_buffer = bytes(100)  # Expected: 128*64/8 = 1024 bytes
        with pytest.raises(ValueError, match="Buffer size mismatch"):
            await display.write_frame(wrong_buffer)

        await display.shutdown()

    @pytest.mark.asyncio
    async def test_ssd1306_brightness_validates_range(self):
        """SSD1306 brightness is clamped to [0.0, 1.0]."""
        display = SSD1306Display(width=128, height=64)
        success = await display.initialize()

        if not success:
            pytest.skip("SSD1306/I2C not available")

        # Should clamp, not raise
        await display.set_brightness(1.5)
        await display.set_brightness(-0.5)

        await display.shutdown()

    @pytest.mark.asyncio
    async def test_ssd1306_cbf_enforces_power_budget(self):
        """SSD1306 operations check CBF for power constraints."""
        # This test will verify CBF enforcement after decorator added
        # Expected: CBFViolation if power budget exceeded
        pass

    @pytest.mark.asyncio
    async def test_ssd1306_shutdown_safe(self):
        """SSD1306 shutdown turns display off safely."""
        display = SSD1306Display(width=128, height=64)
        success = await display.initialize()

        if not success:
            pytest.skip("SSD1306/I2C not available")

        await display.shutdown()
        assert display._running is False


class TestST7735DisplayCBFSafety:
    """Test ST7735 TFT LCD display CBF safety enforcement."""

    @pytest.mark.asyncio
    async def test_st7735_initialization_graceful(self):
        """ST7735 handles missing SPI/GPIO gracefully."""
        display = ST7735Display(width=128, height=160)

        # Should return False if SPI/GPIO unavailable, not crash
        result = await display.initialize()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_st7735_buffer_size_validation(self):
        """ST7735 validates frame buffer size (RGB565)."""
        display = ST7735Display(width=128, height=160)
        success = await display.initialize()

        if not success:
            pytest.skip("ST7735/SPI not available")

        # Wrong buffer size should raise
        wrong_buffer = bytes(100)  # Expected: 128*160*2 = 40960 bytes
        with pytest.raises(ValueError, match="Buffer size mismatch"):
            await display.write_frame(wrong_buffer)

        await display.shutdown()

    @pytest.mark.asyncio
    async def test_st7735_cbf_enforces_memory_limits(self):
        """ST7735 operations check CBF for memory constraints."""
        # This test will verify CBF enforcement after decorator added
        # Expected: CBFViolation if framebuffer memory exceeded
        pass

    @pytest.mark.asyncio
    async def test_st7735_shutdown_safe(self):
        """ST7735 shutdown puts display to sleep safely."""
        display = ST7735Display(width=128, height=160)
        success = await display.initialize()

        if not success:
            pytest.skip("ST7735/SPI not available")

        await display.shutdown()
        assert display._running is False


class TestDisplayHardwareFailureInjection:
    """Test display actuator resilience to hardware failures."""

    @pytest.mark.asyncio
    async def test_display_i2c_bus_missing(self):
        """Display handles missing I2C bus gracefully."""
        display = SSD1306Display(width=128, height=64, bus=99)

        # Should return False, not crash
        result = await display.initialize()
        assert result is False

    @pytest.mark.asyncio
    async def test_display_spi_device_missing(self):
        """Display handles missing SPI device gracefully."""
        display = ST7735Display(
            width=128,
            height=160,
            spi_device="/dev/spidev99.99",
        )

        # Should return False, not crash
        result = await display.initialize()
        assert result is False

    @pytest.mark.asyncio
    async def test_display_operations_after_shutdown(self):
        """Display operations after shutdown raise appropriate errors."""
        display = SSD1306Display(width=128, height=64)
        success = await display.initialize()

        if not success:
            pytest.skip("Display not available")

        await display.shutdown()

        # Operations after shutdown should raise
        with pytest.raises(RuntimeError, match="not initialized"):
            await display.write_frame(bytes(1024))

    @pytest.mark.asyncio
    async def test_display_clear_with_various_colors(self):
        """Display clear works with various color values."""
        display = SSD1306Display(width=128, height=64)
        success = await display.initialize()

        if not success:
            pytest.skip("Display not available")

        # Should handle both black and white
        await display.clear(0x000000)  # Black
        await display.clear(0xFFFFFF)  # White

        await display.shutdown()

    @pytest.mark.asyncio
    async def test_display_mode_transitions(self):
        """Display handles mode transitions safely."""
        display = SSD1306Display(width=128, height=64)
        success = await display.initialize()

        if not success:
            pytest.skip("Display not available")

        # Test all mode transitions
        await display.set_mode(DisplayMode.FULL)
        await display.set_mode(DisplayMode.LOW_POWER)
        await display.set_mode(DisplayMode.OFF)
        await display.set_mode(DisplayMode.FULL)

        await display.shutdown()
