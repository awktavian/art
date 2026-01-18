"""鏡 RTE Type Definitions.

Data types for the Real-Time Executor subsystem.

Created: January 2, 2026
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum


class LEDPattern(IntEnum):
    """LED animation patterns.

    Must match firmware pattern IDs in kagami-pico/src/led_ring.rs
    """

    IDLE = 0  # Static colony colors
    BREATHING = 1  # Slow ambient pulse
    SPIN = 2  # Rotating chase
    PULSE = 3  # Center-out pulse (listening)
    CASCADE = 4  # Waterfall effect (executing)
    FLASH = 5  # Quick green flash (success)
    ERROR_FLASH = 6  # Quick red flash (error)
    RAINBOW = 7  # HSV rotation
    SPECTRAL = 8  # Prism refraction
    FANO_PULSE = 9  # Fano plane geometry
    SPECTRAL_SWEEP = 10  # Color sweep across ring
    CHROMATIC_SUCCESS = 11  # Green chromatic confirmation
    CHROMATIC_ERROR = 12  # Red chromatic alert
    SAFETY_SAFE = 13  # Green safety indicator (h(x) > 0.5)
    SAFETY_CAUTION = 14  # Yellow caution (0 < h(x) <= 0.5)
    SAFETY_VIOLATION = 15  # Red violation (h(x) <= 0)


class RTEEventType(Enum):
    """Types of events from RTE backends."""

    BUTTON_PRESSED = "button_pressed"
    BUTTON_RELEASED = "button_released"
    SENSOR_READING = "sensor_reading"
    ERROR = "error"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass
class RTEStatus:
    """Status response from an RTE backend.

    Attributes:
        pattern: Current LED pattern ID
        brightness: Current brightness (0-255)
        frame_count: Number of frames rendered since boot
        connected: Whether the backend is connected
        latency_us: Last command round-trip latency in microseconds
        uptime_ms: Backend uptime in milliseconds
        version: Protocol version string
    """

    pattern: int = 0
    brightness: int = 128
    frame_count: int = 0
    connected: bool = False
    latency_us: int = 0
    uptime_ms: int = 0
    version: str = "1.0"

    @property
    def pattern_name(self) -> str:
        """Get human-readable pattern name."""
        try:
            return LEDPattern(self.pattern).name
        except ValueError:
            return f"UNKNOWN({self.pattern})"


@dataclass
class RTEEvent:
    """Event from an RTE backend.

    Attributes:
        event_type: Type of event
        timestamp: When the event occurred
        data: Optional event data (varies by event type)
    """

    event_type: RTEEventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict | None = None

    @classmethod
    def button_pressed(cls) -> "RTEEvent":
        """Create a button pressed event."""
        return cls(event_type=RTEEventType.BUTTON_PRESSED)

    @classmethod
    def error(cls, code: int, message: str = "") -> "RTEEvent":
        """Create an error event."""
        return cls(
            event_type=RTEEventType.ERROR,
            data={"code": code, "message": message},
        )

    @classmethod
    def connected(cls) -> "RTEEvent":
        """Create a connected event."""
        return cls(event_type=RTEEventType.CONNECTED)

    @classmethod
    def disconnected(cls) -> "RTEEvent":
        """Create a disconnected event."""
        return cls(event_type=RTEEventType.DISCONNECTED)


# Colony colors for LED ring (must match firmware)
COLONY_COLORS: dict[str, tuple[int, int, int]] = {
    "spark": (232, 33, 39),  # Red
    "forge": (247, 148, 29),  # Orange
    "flow": (255, 199, 44),  # Gold
    "nexus": (0, 166, 81),  # Green
    "beacon": (0, 174, 239),  # Blue
    "grove": (146, 39, 143),  # Purple
    "crystal": (237, 30, 121),  # Magenta
}

# Safety colors
SAFETY_COLORS: dict[str, tuple[int, int, int]] = {
    "safe": (0, 255, 0),  # Green
    "caution": (255, 255, 0),  # Yellow
    "violation": (255, 0, 0),  # Red
}


__all__ = [
    "COLONY_COLORS",
    "SAFETY_COLORS",
    "LEDPattern",
    "RTEEvent",
    "RTEEventType",
    "RTEStatus",
]
