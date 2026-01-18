"""
HD108 LED Driver

16-bit RGB LED driver for the Kagami Orb equator ring.
Uses SPI interface with HD108 protocol (similar to APA102 but 16-bit).

Hardware:
- 16× HD108 5050 LEDs
- SPI clock: 20MHz max
- Data format: 32-bit start frame, 64-bit per LED, 32-bit end frame
"""

import math
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum

try:
    import spidev
    HAS_SPIDEV = True
except ImportError:
    HAS_SPIDEV = False


class OrbState(Enum):
    """Orb LED animation states."""
    OFF = "off"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"
    CHARGING = "charging"


# Alias for backward compatibility
AnimationType = OrbState


@dataclass
class RGBW:
    """16-bit RGBW color value."""
    r: int  # 0-65535
    g: int  # 0-65535
    b: int  # 0-65535
    w: int = 0  # 0-65535 (HD108 doesn't have W, but we track it)
    
    def to_8bit(self) -> Tuple[int, int, int, int]:
        """Convert to 8-bit values."""
        return (
            self.r >> 8,
            self.g >> 8,
            self.b >> 8,
            self.w >> 8,
        )
    
    @classmethod
    def from_8bit(cls, r: int, g: int, b: int, w: int = 0) -> "RGBW":
        """Create from 8-bit values."""
        return cls(r << 8, g << 8, b << 8, w << 8)


class HD108Driver:
    """
    Driver for HD108 16-bit RGB LEDs.
    
    The HD108 protocol:
    - Start frame: 64 bits of zeros
    - Per LED: 16-bit brightness + 16-bit R + 16-bit G + 16-bit B
    - End frame: 64 bits of ones
    """
    
    # HD108 protocol constants
    START_FRAME = bytes([0x00] * 8)  # 64 bits of zeros
    END_FRAME = bytes([0xFF] * 8)    # 64 bits of ones
    
    def __init__(
        self,
        spi_bus: int = 0,
        spi_device: int = 0,
        num_leds: int = 16,
        max_brightness: int = 31,  # HD108 has 5-bit global brightness (0-31)
        simulate: bool = False,
    ):
        """
        Initialize HD108 LED driver.
        
        Args:
            spi_bus: SPI bus number (0 or 1 on most Linux systems)
            spi_device: SPI device number (chip select)
            num_leds: Number of LEDs in the chain
            max_brightness: Global brightness limit (0-31)
            simulate: If True, run in simulation mode without hardware
        """
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.num_leds = num_leds
        self.max_brightness = min(31, max(0, max_brightness))
        self.simulate = simulate or not HAS_SPIDEV
        
        # LED buffer (16-bit per channel)
        self._buffer: List[RGBW] = [RGBW(0, 0, 0, 0) for _ in range(num_leds)]
        
        # Animation state
        self._animation = OrbState.OFF
        self._animation_start = time.time()
        
        # Charge level for CHARGING animation (0.0 - 1.0)
        self.charge_level: float = 0.0
        
        # SPI handle
        self._spi: Optional[spidev.SpiDev] = None
        self._initialized = False
        
        # Initialize
        self._init_spi()
    
    def _init_spi(self) -> None:
        """Initialize SPI interface."""
        if self.simulate:
            self._initialized = True
            return
        
        try:
            self._spi = spidev.SpiDev()
            self._spi.open(self.spi_bus, self.spi_device)
            self._spi.max_speed_hz = 20_000_000  # 20 MHz
            self._spi.mode = 0b00  # CPOL=0, CPHA=0
            self._initialized = True
        except Exception as e:
            print(f"SPI initialization failed: {e}")
            self._initialized = False
            self.simulate = True
    
    def is_initialized(self) -> bool:
        """Check if driver is initialized."""
        return self._initialized
    
    def set_led(self, index: int, r: int, g: int, b: int, w: int = 0) -> None:
        """
        Set a single LED color (8-bit values).
        
        Args:
            index: LED index (0 to num_leds-1)
            r, g, b, w: Color values (0-255)
        """
        if 0 <= index < self.num_leds:
            self._buffer[index] = RGBW.from_8bit(r, g, b, w)
    
    def set_led_16bit(self, index: int, r: int, g: int, b: int, w: int = 0) -> None:
        """
        Set a single LED color (16-bit values).
        
        Args:
            index: LED index (0 to num_leds-1)
            r, g, b, w: Color values (0-65535)
        """
        if 0 <= index < self.num_leds:
            self._buffer[index] = RGBW(r, g, b, w)
    
    def set_all(self, r: int, g: int, b: int, w: int = 0) -> None:
        """Set all LEDs to the same color (8-bit values)."""
        color = RGBW.from_8bit(r, g, b, w)
        self._buffer = [color for _ in range(self.num_leds)]
    
    def clear(self) -> None:
        """Turn off all LEDs."""
        self.set_all(0, 0, 0, 0)
        self.show()
    
    def get_buffer(self) -> List[Tuple[int, int, int, int]]:
        """Get current LED buffer as 8-bit tuples."""
        return [led.to_8bit() for led in self._buffer]
    
    def _build_spi_frame(self) -> bytes:
        """
        Build the SPI frame for the current buffer.
        
        Returns:
            bytes: Complete SPI frame ready for transmission
        """
        data = bytearray(self.START_FRAME)
        
        for led in self._buffer:
            # HD108 format: [brightness:16][red:16][green:16][blue:16]
            # Brightness byte: [111:3][brightness:5][00000000:8]
            brightness_high = (0b111 << 5) | self.max_brightness
            brightness_low = 0x00
            
            data.extend([
                brightness_high,
                brightness_low,
                (led.r >> 8) & 0xFF,
                led.r & 0xFF,
                (led.g >> 8) & 0xFF,
                led.g & 0xFF,
                (led.b >> 8) & 0xFF,
                led.b & 0xFF,
            ])
        
        data.extend(self.END_FRAME)
        return bytes(data)
    
    def show(self) -> None:
        """Send buffer to LEDs."""
        if not self._initialized:
            return
        
        data = self._build_spi_frame()
        
        if not self.simulate and self._spi:
            self._spi.xfer2(list(data))
    
    def set_animation(self, animation: str) -> None:
        """Set the current animation pattern by string."""
        try:
            self._animation = OrbState(animation)
        except ValueError:
            self._animation = OrbState.OFF
        self._animation_start = time.time()
    
    def set_state(self, state: OrbState) -> None:
        """Set the current animation state."""
        self._animation = state
        self._animation_start = time.time()
    
    def render_frame(self, t: Optional[float] = None) -> List[Tuple[int, int, int, int]]:
        """
        Render a single animation frame.
        
        Args:
            t: Time offset (if None, uses time since animation start)
        
        Returns:
            List of (r, g, b, w) tuples for each LED
        """
        if t is None:
            t = time.time() - self._animation_start
        
        if self._animation == OrbState.OFF:
            self.set_all(0, 0, 0)
        
        elif self._animation == OrbState.IDLE:
            # Gentle breathing in warm white
            brightness = int((math.sin(t * 0.5) + 1) * 0.5 * 40 + 10)
            self.set_all(brightness, brightness // 2, brightness // 4)
        
        elif self._animation == OrbState.LISTENING:
            # Cyan pulse
            brightness = int((math.sin(t * 4) + 1) * 0.5 * 200 + 55)
            self.set_all(0, brightness, brightness)
        
        elif self._animation == OrbState.THINKING:
            # Purple/blue chase
            for i in range(self.num_leds):
                angle = (i / self.num_leds) * math.pi * 2
                wave = (math.sin(t * 3 + angle) + 1) * 0.5
                r = int(128 * wave)
                b = int(255 * wave)
                self.set_led(i, r, 0, b)
        
        elif self._animation == OrbState.SPEAKING:
            # Green pulse with audio-reactive simulation
            brightness = int((math.sin(t * 8) + 1) * 0.5 * 200 + 55)
            self.set_all(0, brightness, brightness // 4)
        
        elif self._animation == OrbState.ERROR:
            # Red blink
            on = int(t * 2) % 2 == 0
            self.set_all(255 if on else 0, 0, 0)
        
        elif self._animation == OrbState.CHARGING:
            # Amber fill based on charge level with subtle animation
            lit_count = int(self.charge_level * self.num_leds)
            pulse = (math.sin(t * 2) + 1) * 0.1 + 0.9  # 0.9-1.1
            for i in range(self.num_leds):
                if i < lit_count:
                    # Lit segments - amber
                    brightness = int(255 * pulse)
                    self.set_led(i, brightness, brightness // 2, 0)
                elif i == lit_count:
                    # Current segment - pulsing
                    progress = (self.charge_level * self.num_leds) % 1.0
                    brightness = int(255 * progress * pulse)
                    self.set_led(i, brightness, brightness // 2, 0)
                else:
                    # Unlit segments - dim
                    self.set_led(i, 20, 10, 0)
        
        return self.get_buffer()
    
    async def tick(self) -> None:
        """Render and display current animation frame (async)."""
        self.render_frame()
        self.show()
    
    def close(self) -> None:
        """Clean up resources."""
        self.clear()
        if self._spi:
            self._spi.close()
            self._spi = None
        self._initialized = False
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
