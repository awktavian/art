"""Ambient OS Data Types.

Pure data structures for ambient computing layer.
No imports from other core modules to break circular dependencies.

Created: December 5, 2025
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# =============================================================================
# Breath Cycle Types
# =============================================================================


class BreathPhase(Enum):
    """Breath cycle phases mapped to receipt phases."""

    INHALE = "plan"  # Gathering, focusing
    HOLD = "execute"  # Acting, implementing
    EXHALE = "verify"  # Releasing, confirming
    REST = "rest"  # Between cycles


@dataclass
class BreathState:
    """Current breath cycle state."""

    phase: BreathPhase
    phase_progress: float  # 0.0-1.0 within phase
    cycle_count: int
    bpm: float  # Breaths per minute
    intensity: float  # 0.0-1.0 breath depth
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# Colony Expression Types
# =============================================================================

# Import canonical Colony definition to avoid duplication
# Note: Using DomainType as Colony for compatibility
from kagami.core.unified_agents.colony_constants import DomainType as Colony


class Modality(Enum):
    """Output modalities for ambient expression."""

    LIGHT_COLOR = "light_color"  # Color temperature/hue
    LIGHT_BRIGHTNESS = "light_brightness"  # Intensity
    LIGHT_PATTERN = "light_pattern"  # Pulse/breathe/flash
    SOUND_TONE = "sound_tone"  # Tonal frequency
    SOUND_TEXTURE = "sound_texture"  # Ambient texture
    SOUND_SPATIAL = "sound_spatial"  # 3D position
    HAPTIC_PULSE = "haptic_pulse"  # Vibration pattern
    HAPTIC_INTENSITY = "haptic_intensity"  # Strength


@dataclass
class ColonyState:
    """State of a single colony."""

    colony: Colony
    activation: float  # 0.0-1.0 activation level
    potential: float  # Catastrophe potential value
    gradient: tuple[float, ...]  # Gradient of potential
    params: tuple[float, ...]  # Control parameters
    timestamp: float = field(default_factory=time.time)


@dataclass
class ColonyExpression:
    """Expression of colony state through a modality."""

    colony: Colony
    modality: Modality
    value: Any  # Modality-specific value
    intensity: float  # 0.0-1.0
    duration_ms: int  # How long to express


# =============================================================================
# Safety Expression Types
# =============================================================================


@dataclass
class SafetyState:
    """Safety barrier state h(x)."""

    h_value: float  # h(x) value, >= 0 is safe
    x_threat: float
    x_uncertainty: float
    x_complexity: float
    x_risk: float
    gradient: tuple[float, float, float, float]  # ∇h
    timestamp: float = field(default_factory=time.time)

    @property
    def is_safe(self) -> bool:
        """Check if currently safe."""
        return self.h_value >= 0

    @property
    def safety_margin(self) -> float:
        """Normalized safety margin 0-1."""
        # Sigmoid to normalize h to 0-1 range
        import math

        return 1.0 / (1.0 + math.exp(-self.h_value))


# =============================================================================
# Presence/Context Types
# =============================================================================


class PresenceLevel(Enum):
    """Level of user presence/engagement."""

    ABSENT = "absent"  # User not detected
    PERIPHERAL = "peripheral"  # User nearby but not engaged
    AWARE = "aware"  # User aware of system
    ENGAGED = "engaged"  # User actively engaged
    FOCUSED = "focused"  # Deep focus/flow state


@dataclass
class PresenceState:
    """Detected user presence."""

    level: PresenceLevel
    confidence: float  # 0.0-1.0
    attention_target: str | None  # What user is focused on
    activity_type: str | None  # What user is doing
    location: str | None  # Where user is
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# Smart Light Types
# =============================================================================


@dataclass
class LightState:
    """Smart light state."""

    on: bool
    brightness: float  # 0.0-1.0
    hue: float  # 0-360 degrees
    saturation: float  # 0.0-1.0
    temperature: int | None  # Color temp in Kelvin (2000-6500)
    transition_ms: int = 0  # Transition time


@dataclass
class LightZone:
    """Zone of lights that act together."""

    id: str
    name: str
    lights: list[str]  # Light IDs
    state: LightState


# =============================================================================
# Soundscape Types
# =============================================================================


class SoundLayer(Enum):
    """Layers in the ambient soundscape."""

    BASE = "base"  # Foundation tone/drone
    TEXTURE = "texture"  # Ambient texture
    RHYTHM = "rhythm"  # Breath sync rhythm
    ACCENT = "accent"  # Colony expression accents
    ALERT = "alert"  # Safety/notification


@dataclass
class SoundElement:
    """Element in the soundscape."""

    layer: SoundLayer
    frequency: float | None  # Hz, or None for noise
    amplitude: float  # 0.0-1.0
    pan: float  # -1.0 to 1.0 (left to right)
    modulation: dict[str, float] = field(default_factory=dict[str, Any])


@dataclass
class SoundscapeConfig:
    """Soundscape configuration."""

    elements: list[SoundElement]
    master_volume: float = 0.3
    breath_sync: bool = True
    colony_reactive: bool = True


# =============================================================================
# Ambient State Aggregate
# =============================================================================


@dataclass
class AmbientState:
    """Complete ambient system state."""

    breath: BreathState
    colonies: dict[Colony, ColonyState]
    safety: SafetyState
    presence: PresenceState
    lights: list[LightZone]
    soundscape: SoundscapeConfig
    timestamp: float = field(default_factory=time.time)
