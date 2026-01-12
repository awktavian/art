"""
Tests for HD108 LED Driver

Tests cover:
- Initialization and configuration
- Color conversion (8-bit <-> 16-bit)
- SPI protocol framing
- Animation state machines
- All LED patterns (IDLE, LISTENING, THINKING, etc.)
"""

import pytest
import math
import time
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(pytest.importorskip("pathlib").Path(__file__).parent.parent))

from kagami_orb.drivers.led import (
    HD108Driver,
    RGBW,
    OrbState,
)


class TestRGBW:
    """Test RGBW color class."""
    
    def test_from_8bit_conversion(self):
        """Test 8-bit to 16-bit conversion."""
        color = RGBW.from_8bit(255, 128, 0)
        
        # 255 -> 65280 (255 << 8)
        assert color.r == 65280
        # 128 -> 32768 (128 << 8)
        assert color.g == 32768
        # 0 -> 0
        assert color.b == 0
    
    def test_to_8bit_conversion(self):
        """Test 16-bit to 8-bit conversion."""
        color = RGBW(r=65535, g=32768, b=16384)
        r, g, b, w = color.to_8bit()
        
        # 65535 >> 8 = 255
        assert r == 255
        # 32768 >> 8 = 128
        assert g == 128
        # 16384 >> 8 = 64
        assert b == 64
    
    def test_roundtrip_conversion(self):
        """Test that 8-bit roundtrip is consistent."""
        original = (200, 100, 50, 25)
        color = RGBW.from_8bit(*original)
        result = color.to_8bit()
        
        # Should be within 1 due to bit shifting
        assert abs(result[0] - original[0]) <= 1
        assert abs(result[1] - original[1]) <= 1
        assert abs(result[2] - original[2]) <= 1


class TestHD108Driver:
    """Test HD108 LED driver."""
    
    @pytest.fixture
    def driver(self):
        """Create driver in simulation mode."""
        return HD108Driver(num_leds=16, simulate=True)
    
    def test_initialization(self, driver):
        """Test driver initializes correctly."""
        assert driver.num_leds == 16
        assert driver.is_initialized()
        assert len(driver._buffer) == 16
    
    def test_set_led_8bit(self, driver):
        """Test setting LED with 8-bit colors."""
        driver.set_led(0, 255, 128, 64)
        
        color = driver._buffer[0]
        # Convert back to check
        r, g, b, w = color.to_8bit()
        assert r == 255
        assert g == 128
        assert b == 64
    
    def test_set_led_bounds_checking(self, driver):
        """Test that out-of-bounds LED index is handled."""
        # Should not raise
        driver.set_led(100, 255, 255, 255)
        # Buffer unchanged at valid indices
        assert driver._buffer[0].r == 0
    
    def test_set_all_leds(self, driver):
        """Test setting all LEDs to same color."""
        driver.set_all(100, 200, 50)
        
        for i in range(16):
            r, g, b, w = driver._buffer[i].to_8bit()
            assert r == 100
            assert g == 200
            assert b == 50
    
    def test_clear(self, driver):
        """Test clearing all LEDs."""
        driver.set_all(255, 255, 255)
        driver.clear()
        
        for i in range(16):
            assert driver._buffer[i].r == 0
            assert driver._buffer[i].g == 0
            assert driver._buffer[i].b == 0
    
    def test_spi_frame_structure(self, driver):
        """Test SPI frame has correct structure."""
        driver.set_all(128, 64, 32)
        
        # Get the frame data
        frame = driver._build_spi_frame()
        
        # Frame structure: START (8 bytes) + LED data + END (8 bytes)
        start_frame = bytes([0x00] * 8)
        end_frame = bytes([0xFF] * 8)
        
        assert frame[:8] == start_frame
        assert frame[-8:] == end_frame
        
        # LED data should be 8 bytes per LED (global + RGB 16-bit each)
        led_data_len = 16 * 8  # 16 LEDs * 8 bytes
        expected_len = 8 + led_data_len + 8
        assert len(frame) == expected_len
    
    def test_brightness_control(self, driver):
        """Test global brightness setting."""
        driver.max_brightness = 15  # Half brightness
        
        driver.set_led(0, 255, 255, 255)
        frame = driver._build_spi_frame()
        
        # First LED's brightness byte should be limited
        # (Start frame is 8 bytes, first LED byte is brightness)
        brightness_byte = frame[8]
        assert (brightness_byte & 0x1F) <= 15


class TestOrbAnimations:
    """Test orb animation states."""
    
    @pytest.fixture
    def driver(self):
        """Create driver for animation tests."""
        return HD108Driver(num_leds=16, simulate=True)
    
    def test_idle_animation(self, driver):
        """Test IDLE state produces breathing pattern."""
        driver.set_state(OrbState.IDLE)
        
        # Render multiple frames
        values_at_t = []
        for i in range(100):
            t = i * 0.05
            colors = driver.render_frame(t)
            # Get center LED brightness
            center_brightness = colors[8][0]  # R channel of center LED
            values_at_t.append(center_brightness)
        
        # Should have variation (breathing)
        assert max(values_at_t) > min(values_at_t)
        # Should be within valid range
        assert all(0 <= v <= 255 for v in values_at_t)
    
    def test_listening_animation(self, driver):
        """Test LISTENING state produces pulsing pattern."""
        driver.set_state(OrbState.LISTENING)
        
        colors = driver.render_frame(0)
        
        # Should have blue tint for listening
        # Check that blue channel is prominent
        total_blue = sum(c[2] for c in colors)
        total_red = sum(c[0] for c in colors)
        assert total_blue >= total_red
    
    def test_thinking_animation(self, driver):
        """Test THINKING state produces rotating pattern."""
        driver.set_state(OrbState.THINKING)
        
        colors_t0 = driver.render_frame(0)
        colors_t1 = driver.render_frame(0.5)
        
        # Pattern should be different at different times (rotation)
        assert colors_t0 != colors_t1
    
    def test_speaking_animation(self, driver):
        """Test SPEAKING state produces wave pattern."""
        driver.set_state(OrbState.SPEAKING)
        
        colors = driver.render_frame(0)
        
        # Should have greenish tint for speaking
        # All LEDs should be on
        for c in colors:
            assert max(c[:3]) > 0
    
    def test_error_animation(self, driver):
        """Test ERROR state produces red pulse."""
        driver.set_state(OrbState.ERROR)
        
        colors = driver.render_frame(0)
        
        # Should be red-dominant
        total_red = sum(c[0] for c in colors)
        total_green = sum(c[1] for c in colors)
        total_blue = sum(c[2] for c in colors)
        
        assert total_red > total_green
        assert total_red > total_blue
    
    def test_charging_animation(self, driver):
        """Test CHARGING state shows charge level."""
        driver.set_state(OrbState.CHARGING)
        driver.charge_level = 0.5  # 50%
        
        colors = driver.render_frame(0)
        
        # Should have some LEDs on (proportional to charge)
        # Count LEDs that are significantly brighter than dim (>30)
        bright_count = sum(1 for c in colors if c[0] > 30)
        
        # At 50%, roughly half should be bright
        assert 4 <= bright_count <= 12
    
    def test_state_transition(self, driver):
        """Test smooth state transitions."""
        driver.set_state(OrbState.IDLE)
        idle_colors = driver.render_frame(0)
        
        driver.set_state(OrbState.LISTENING)
        listening_colors = driver.render_frame(0)
        
        # Colors should be different
        assert idle_colors != listening_colors


class TestSPIProtocol:
    """Test SPI protocol details."""
    
    @pytest.fixture
    def driver(self):
        """Create driver with mock SPI."""
        return HD108Driver(num_leds=16, simulate=True)
    
    def test_frame_start_bytes(self, driver):
        """Test frame starts with correct bytes."""
        frame = driver._build_spi_frame()
        
        # HD108 start frame: 8 bytes of 0x00
        assert frame[0:8] == bytes([0x00] * 8)
    
    def test_frame_end_bytes(self, driver):
        """Test frame ends with correct bytes."""
        frame = driver._build_spi_frame()
        
        # HD108 end frame: 8 bytes of 0xFF
        assert frame[-8:] == bytes([0xFF] * 8)
    
    def test_led_data_format(self, driver):
        """Test LED data follows HD108 format."""
        # Set first LED to known color
        driver._buffer[0] = RGBW(r=0x1234, g=0x5678, b=0x9ABC)
        driver.max_brightness = 31
        
        frame = driver._build_spi_frame()
        
        # LED data starts at byte 8 (after 8-byte start frame)
        led_start = 8
        
        # HD108 LED format (8 bytes):
        # Byte 0: [111:3][brightness:5] = 0b111xxxxx
        # Byte 1: Padding (0x00)
        # Byte 2-3: Red (16-bit big-endian)
        # Byte 4-5: Green (16-bit big-endian)
        # Byte 6-7: Blue (16-bit big-endian)
        
        # Check brightness (bits 4:0 of byte 0)
        brightness = frame[led_start] & 0x1F
        assert brightness == 31
        
        # Check that the high 3 bits are 111
        assert (frame[led_start] >> 5) == 0b111
        
        # Check red (big-endian)
        red = (frame[led_start + 2] << 8) | frame[led_start + 3]
        assert red == 0x1234
        
        # Check green
        green = (frame[led_start + 4] << 8) | frame[led_start + 5]
        assert green == 0x5678
        
        # Check blue
        blue = (frame[led_start + 6] << 8) | frame[led_start + 7]
        assert blue == 0x9ABC


class TestPerformance:
    """Test driver performance."""
    
    def test_frame_rate(self):
        """Test that frame rendering is fast enough for 60fps."""
        driver = HD108Driver(num_leds=16, simulate=True)
        driver.set_state(OrbState.THINKING)
        
        # Render 60 frames
        start = time.monotonic()
        for i in range(60):
            driver.render_frame(i / 60.0)
            driver._build_spi_frame()
        elapsed = time.monotonic() - start
        
        # Should complete in under 1 second (60fps)
        assert elapsed < 1.0
    
    def test_memory_efficiency(self):
        """Test that driver uses reasonable memory."""
        import sys
        
        driver = HD108Driver(num_leds=16, simulate=True)
        
        # Buffer should be small
        buffer_size = sys.getsizeof(driver._buffer)
        
        # 16 LEDs * ~32 bytes per RGBW should be under 1KB
        assert buffer_size < 1024


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
