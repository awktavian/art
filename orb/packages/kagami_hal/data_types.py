"""Shared HAL data types to break circular dependencies.

This module contains pure data structures (Enums, Dataclasses) used by HAL protocols
and adapters. It must NOT import from other core modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# --- Display Types ---


class DisplayMode(Enum):
    """Display power modes."""

    FULL = "full"
    LOW_POWER = "low_power"
    ALWAYS_ON = "always_on"
    OFF = "off"


@dataclass
class DisplayInfo:
    """Display capabilities."""

    width: int
    height: int
    bpp: int
    refresh_rate: int
    supports_aod: bool
    supports_touch: bool


# --- Audio Types ---


class AudioFormat(Enum):
    """Audio sample formats."""

    PCM_16 = "pcm_16"
    PCM_24 = "pcm_24"
    PCM_32 = "pcm_32"
    FLOAT_32 = "float_32"


@dataclass
class AudioConfig:
    """Audio stream configuration."""

    sample_rate: int
    channels: int
    format: AudioFormat
    buffer_size: int


# --- Input Types ---


class InputType(Enum):
    """Input device types."""

    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    TOUCHSCREEN = "touchscreen"
    BUTTON = "button"
    GESTURE = "gesture"


class KeyCode(Enum):
    """Common key codes."""

    HOME = 102
    BACK = 103
    POWER = 104
    VOLUME_UP = 105
    VOLUME_DOWN = 106


@dataclass
class InputEvent:
    """Input event data."""

    type: InputType
    code: int
    value: int
    timestamp_ms: int


# --- Power Types ---


class PowerMode(Enum):
    """System power modes."""

    FULL = "full"
    BALANCED = "balanced"
    SAVER = "saver"
    CRITICAL = "critical"


class SleepMode(Enum):
    """CPU sleep modes."""

    NONE = "none"
    LIGHT = "light"
    DEEP = "deep"
    HIBERNATE = "hibernate"


@dataclass
class BatteryStatus:
    """Battery status."""

    level: float
    voltage: float
    charging: bool
    plugged: bool
    time_remaining_minutes: int | None
    temperature_c: float | None


@dataclass
class PowerStats:
    """Power consumption statistics.

    Note: Uses watts for consistency with power_controller.py contract.
    """

    current_watts: float
    avg_watts: float
    peak_watts: float
    total_wh: float  # Watt-hours consumed


# --- Sensor Types ---


class SensorType(Enum):
    """Sensor types."""

    # Motion sensors
    ACCELEROMETER = "accelerometer"
    GYROSCOPE = "gyroscope"
    MAGNETOMETER = "magnetometer"
    GRAVITY = "gravity"  # Gravity vector (m/s²)
    LINEAR_ACCELERATION = "linear_acceleration"  # Accel without gravity
    ROTATION = "rotation"  # Rotation vector (quaternion)

    # Position sensors
    GPS = "gps"
    PROXIMITY = "proximity"  # Distance to nearby objects (cm)

    # Environmental sensors
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    LIGHT = "light"

    # Health sensors
    HEART_RATE = "heart_rate"
    SPO2 = "spo2"
    ECG = "ecg"
    BATTERY = "battery"

    # Neural interface
    SEMG = "semg"  # Surface electromyography (neural wristband)

    # Audio/visual sensors (macOS HAL)
    CAMERA = "camera"
    MICROPHONE = "microphone"


@dataclass
class SensorReading:
    """Sensor reading data."""

    sensor: SensorType
    value: Any
    timestamp_ms: int
    accuracy: float


@dataclass
class AccelReading:
    """Accelerometer reading (m/s²)."""

    x: float
    y: float
    z: float


@dataclass
class GyroReading:
    """Gyroscope reading (rad/s)."""

    x: float
    y: float
    z: float


@dataclass
class HeartRateReading:
    """Heart rate reading."""

    bpm: int
    confidence: float


@dataclass
class GPSReading:
    """GPS reading."""

    latitude: float
    longitude: float
    altitude: float
    accuracy: float


# --- sEMG / Neural Interface Types ---


class SEMGGesture(Enum):
    """Discrete gestures recognized from sEMG.

    Based on Meta Neural Band research (Nature, July 2025).
    These are the 9 discrete gestures their model supports.
    """

    # Pinch gestures (thumb to finger)
    PINCH_INDEX = "pinch_index"
    PINCH_MIDDLE = "pinch_middle"
    PINCH_RING = "pinch_ring"
    PINCH_PINKY = "pinch_pinky"

    # Tap gestures
    TAP_INDEX = "tap_index"
    TAP_DOUBLE = "tap_double"

    # Hand gestures
    FIST = "fist"
    OPEN_HAND = "open_hand"
    POINT = "point"

    # Meta gestures (system control)
    NONE = "none"  # Resting / no gesture


class SEMGIntent(Enum):
    """Continuous intent inferred from sEMG motion.

    Beyond discrete gestures — what is the user trying to do?
    Inspired by Half-Life: Alyx gestural model.
    """

    # No active intent
    IDLE = "idle"

    # Reaching / summoning (gravity gloves equivalent)
    REACHING = "reaching"  # Moving toward target
    SUMMONING = "summoning"  # Beckoning / attracting

    # Manipulation
    GRASPING = "grasping"  # Closing on target
    RELEASING = "releasing"  # Opening / letting go
    ROTATING = "rotating"  # Twisting motion

    # Navigation
    SCROLLING = "scrolling"  # Continuous scroll
    POINTING = "pointing"  # Directing attention
    DISMISSING = "dismissing"  # Pushing away


@dataclass
class SEMGFrame:
    """Single frame of sEMG data from neural band.

    48-channel electrode array at 2kHz typical.
    """

    # Raw electrode data: shape (n_channels,) typically 16-48
    channels: list[float]

    # Timestamps
    timestamp_ms: int
    sample_index: int

    # Device info
    device_id: str
    electrode_count: int

    # Quality metrics
    contact_quality: list[float]  # Per-electrode contact quality 0-1
    noise_level: float  # Overall noise estimate


@dataclass
class SEMGGestureResult:
    """Result of discrete gesture classification."""

    gesture: SEMGGesture
    confidence: float  # 0-1
    timestamp_ms: int

    # Per-gesture probabilities for all classes
    probabilities: dict[str, float] | None = None


@dataclass
class SEMGIntentState:
    """Continuous intent state from sEMG stream.

    This is the Alyx-style "what is the user doing right now" state,
    not just discrete gesture events.
    """

    # Current primary intent
    intent: SEMGIntent
    intent_confidence: float

    # Motion vector (normalized direction of intended movement)
    direction_x: float  # -1 to 1
    direction_y: float  # -1 to 1
    direction_z: float  # -1 to 1

    # Motion energy (how vigorous is the gesture)
    energy: float  # 0-1, maps to urgency/force

    # Grip state (continuous, not binary)
    grip_strength: float  # 0-1, 0=open, 1=closed fist

    # Timestamps
    timestamp_ms: int

    # Model confidence
    model_confidence: float


@dataclass
class SEMGHandwritingResult:
    """Result of handwriting recognition from sEMG.

    Meta's model achieves 20.9 WPM writing in air.
    """

    # Recognized text
    text: str

    # Character-level results
    characters: list[str]
    character_confidences: list[float]

    # Timestamps
    timestamp_ms: int
    duration_ms: int


@dataclass
class WristPose:
    """Continuous wrist pose from sEMG.

    Represents wrist position/rotation for fine control.
    """

    # Wrist angles (radians)
    flexion: float  # Flex/extend
    deviation: float  # Radial/ulnar deviation
    pronation: float  # Pronation/supination

    # Angular velocities (rad/s)
    flexion_velocity: float
    deviation_velocity: float
    pronation_velocity: float

    # Confidence
    confidence: float
    timestamp_ms: int
