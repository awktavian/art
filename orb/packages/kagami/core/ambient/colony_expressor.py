"""Colony Expressor for Ambient OS.

Maps colony states to multi-modal ambient expressions.
Each colony has a characteristic expression through:
- Light (color, pattern)
- Sound (tone, texture)
- Haptic (pattern, intensity)

The mapping is derived from catastrophe dynamics, not arbitrary:
- Spark (Fold): Binary ignition → Flash/pulse
- Forge (Cusp): Hysteresis → Committed pulse
- Flow (Swallowtail): Multi-path → Flowing textures
- Nexus (Butterfly): Multi-attractor → Spatial distribution
- Beacon (Hyperbolic): Sharp focus → Directional light
- Grove (Elliptic): Smooth gradient → Color spectrum
- Crystal (Parabolic): Boundary → Warning signals

Created: December 5, 2025
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from kagami.core.ambient.data_types import (
    Colony,
    ColonyExpression,
    ColonyState,
    LightState,
    Modality,
    SoundElement,
    SoundLayer,
)
from kagami.core.ambient.palette import COLONY_COLORS, get_accent_color, rgb_to_hsv

# Lazy import to avoid dependency on kagami_hal when not installed
HapticPulse: Any = None
try:
    from kagami_hal.adapters.common.haptic import HapticPulse as _HapticPulse

    HapticPulse = _HapticPulse
except ImportError:
    # Define a stub class for when kagami_hal isn't available
    @dataclass
    class _HapticPulseStub:
        """Stub for HapticPulse when kagami_hal isn't installed."""

        frequency_hz: float = 0.0
        intensity: float = 0.0
        duration_ms: int = 100

    HapticPulse = _HapticPulseStub


logger = logging.getLogger(__name__)


# Canonical colors live in kagami.core.ambient.palette (do not duplicate here).


# =============================================================================
# Colony Sound Frequencies (based on musical relationships)
# =============================================================================

# Using pentatonic relationships for harmony
# Base frequency A4 = 440Hz, distributed across colonies
COLONY_FREQUENCIES: dict[Colony, float] = {
    Colony.SPARK: 523.25,  # C5 - Bright, initiating
    Colony.FORGE: 293.66,  # D4 - Grounded, working
    Colony.FLOW: 392.00,  # G4 - Flowing, adaptive
    Colony.NEXUS: 349.23,  # F4 - Integrating, central
    Colony.BEACON: 440.00,  # A4 - Clear, focused
    Colony.GROVE: 329.63,  # E4 - Natural, exploring
    Colony.CRYSTAL: 261.63,  # C4 - Foundational, guarding
}


# =============================================================================
# Colony Haptic Patterns
# =============================================================================

COLONY_HAPTICS: dict[Colony, list[Any]] = {
    # Spark: Quick binary pulse (fold bifurcation)
    Colony.SPARK: [HapticPulse(30, 0.8)],
    # Forge: Double tap with commitment (hysteresis)
    Colony.FORGE: [
        HapticPulse(50, 0.6),
        HapticPulse(80, 0.0),
        HapticPulse(100, 0.7),
    ],
    # Flow: Wave pattern (multi-path)
    Colony.FLOW: [
        HapticPulse(30, 0.3),
        HapticPulse(30, 0.5),
        HapticPulse(30, 0.7),
        HapticPulse(30, 0.5),
        HapticPulse(30, 0.3),
    ],
    # Nexus: Distributed pulse (multi-attractor)
    Colony.NEXUS: [
        HapticPulse(40, 0.4),
        HapticPulse(60, 0.0),
        HapticPulse(40, 0.4),
        HapticPulse(60, 0.0),
        HapticPulse(40, 0.4),
        HapticPulse(60, 0.0),
        HapticPulse(40, 0.4),
    ],
    # Beacon: Sharp single pulse (focus shift)
    Colony.BEACON: [HapticPulse(20, 1.0)],
    # Grove: Gentle rolling (smooth gradient)
    Colony.GROVE: [
        HapticPulse(100, 0.2),
        HapticPulse(100, 0.3),
        HapticPulse(100, 0.4),
        HapticPulse(100, 0.3),
        HapticPulse(100, 0.2),
    ],
    # Crystal: Warning pattern (boundary)
    Colony.CRYSTAL: [
        HapticPulse(50, 0.5),
        HapticPulse(50, 0.0),
        HapticPulse(50, 0.5),
    ],
}


@dataclass
class ExpressionConfig:
    """Configuration for colony expression."""

    # Thresholds
    activation_threshold: float = 0.1  # Below this, don't express
    full_expression_threshold: float = 0.8  # Above this, full intensity

    # Light
    light_base_brightness: float = 0.3
    light_max_brightness: float = 1.0
    light_transition_ms: int = 500

    # Sound
    sound_base_amplitude: float = 0.1
    sound_max_amplitude: float = 0.5

    # Haptic
    haptic_base_intensity: float = 0.3
    haptic_max_intensity: float = 1.0


class ColonyExpressor:
    """Expresses colony states through ambient modalities.

    Takes colony states from the world model and generates
    multi-modal ambient expressions that can be rendered by
    the HAL adapters.
    """

    def __init__(self, config: ExpressionConfig | None = None):
        """Initialize colony expressor.

        Args:
            config: Expression configuration
        """
        self.config = config or ExpressionConfig()
        self._last_expressions: dict[Colony, list[ColonyExpression]] = {}

    def express(self, state: ColonyState) -> list[ColonyExpression]:
        """Generate expressions for a colony state.

        Args:
            state: Colony state to express

        Returns:
            List of expressions across modalities
        """
        colony = state.colony
        activation = state.activation

        # Skip if below threshold
        if activation < self.config.activation_threshold:
            return []

        # Normalize activation to expression intensity
        intensity = self._normalize_activation(activation)

        expressions = []

        # Generate light expression
        light_expr = self._express_light(colony, intensity, state)
        if light_expr:
            expressions.append(light_expr)

        # Generate sound expression
        sound_expr = self._express_sound(colony, intensity, state)
        if sound_expr:
            expressions.append(sound_expr)

        # Generate haptic expression (only if above threshold)
        if activation > 0.5:
            haptic_expr = self._express_haptic(colony, intensity, state)
            if haptic_expr:
                expressions.append(haptic_expr)

        self._last_expressions[colony] = expressions
        return expressions

    def _normalize_activation(self, activation: float) -> float:
        """Normalize activation to expression intensity.

        Args:
            activation: Raw activation 0-1

        Returns:
            Expression intensity 0-1
        """
        # Map activation range to intensity range
        threshold = self.config.activation_threshold
        full = self.config.full_expression_threshold

        if activation < threshold:
            return 0.0
        if activation > full:
            return 1.0

        # Linear interpolation in the active range
        return (activation - threshold) / (full - threshold)

    def _express_light(
        self, colony: Colony, intensity: float, state: ColonyState
    ) -> ColonyExpression | None:
        """Generate light expression for colony.

        Args:
            colony: Colony to express
            intensity: Expression intensity
            state: Full colony state

        Returns:
            Light expression or None
        """
        r, g, b = COLONY_COLORS[colony]

        # Convert RGB to HSV for easier manipulation
        h, s, _v = rgb_to_hsv(r, g, b)

        # Scale brightness by intensity
        brightness = self.config.light_base_brightness + (
            intensity * (self.config.light_max_brightness - self.config.light_base_brightness)
        )

        # Create light state
        light_state = LightState(
            on=True,
            brightness=brightness,
            hue=h,
            saturation=s,
            temperature=None,  # Use color, not temp
            transition_ms=self.config.light_transition_ms,
        )

        return ColonyExpression(
            colony=colony,
            modality=Modality.LIGHT_COLOR,
            value=light_state,
            intensity=intensity,
            duration_ms=self.config.light_transition_ms,
        )

    def _express_sound(
        self, colony: Colony, intensity: float, state: ColonyState
    ) -> ColonyExpression | None:
        """Generate sound expression for colony.

        Args:
            colony: Colony to express
            intensity: Expression intensity
            state: Full colony state

        Returns:
            Sound expression or None
        """
        frequency = COLONY_FREQUENCIES[colony]

        # Scale amplitude by intensity
        amplitude = self.config.sound_base_amplitude + (
            intensity * (self.config.sound_max_amplitude - self.config.sound_base_amplitude)
        )

        # Pan based on colony position on Fano plane
        # Colonies are roughly arranged in a circle
        colony_idx = list(Colony).index(colony)
        angle = (colony_idx / 7) * 2 * math.pi
        pan = math.sin(angle)  # -1 to 1

        # Create sound element
        sound = SoundElement(
            layer=SoundLayer.ACCENT,
            frequency=frequency,
            amplitude=amplitude,
            pan=pan,
            modulation={"colony_potential": state.potential},
        )

        return ColonyExpression(
            colony=colony,
            modality=Modality.SOUND_TONE,
            value=sound,
            intensity=intensity,
            duration_ms=500,
        )

    def _express_haptic(
        self, colony: Colony, intensity: float, state: ColonyState
    ) -> ColonyExpression | None:
        """Generate haptic expression for colony.

        Args:
            colony: Colony to express
            intensity: Expression intensity
            state: Full colony state

        Returns:
            Haptic expression or None
        """
        base_pulses = COLONY_HAPTICS[colony]

        # Scale pulse intensities
        scaled_intensity = self.config.haptic_base_intensity + (
            intensity * (self.config.haptic_max_intensity - self.config.haptic_base_intensity)
        )

        scaled_pulses = [
            HapticPulse(
                duration_ms=p.duration_ms,
                intensity=p.intensity * scaled_intensity,
            )
            for p in base_pulses
        ]

        return ColonyExpression(
            colony=colony,
            modality=Modality.HAPTIC_PULSE,
            value=scaled_pulses,
            intensity=intensity,
            duration_ms=sum(p.duration_ms for p in scaled_pulses),
        )

    def express_all(
        self, states: dict[Colony, ColonyState]
    ) -> dict[Colony, list[ColonyExpression]]:
        """Express colony states.

        Visual identity rule: colonies speak **one at a time**.
        This method therefore returns expressions for the dominant colony only.

        Args:
            states: Map of colony to state

        Returns:
            Map of (dominant) colony to expressions (empty if none above threshold)
        """
        dominant = self.get_dominant_colony(states)
        if not dominant:
            return {}
        colony, _activation = dominant
        state = states.get(colony)
        if state is None:
            return {}
        expressions = self.express(state)
        return {colony: expressions} if expressions else {}

    def get_dominant_colony(self, states: dict[Colony, ColonyState]) -> tuple[Colony, float] | None:
        """Get the most active colony.

        Args:
            states: Map of colony to state

        Returns:
            Tuple of (colony, activation) or None
        """
        if not states:
            return None

        dominant = max(states.items(), key=lambda x: x[1].activation)
        if dominant[1].activation < self.config.activation_threshold:
            return None

        return (dominant[0], dominant[1].activation)

    def blend_colors(self, states: dict[Colony, ColonyState]) -> tuple[int, int, int]:
        """Return the single active accent color.

        Visual identity rule: never blend multiple colony colors.
        If no colony is active, return GOLD as the default accent.

        Args:
            states: Map of colony to state

        Returns:
            Accent RGB tuple[Any, ...]
        """
        accent, _colony, _activation = get_accent_color(
            states, activation_threshold=self.config.activation_threshold
        )
        return accent


# =============================================================================
# Global Instance
# =============================================================================

_COLONY_EXPRESSOR: ColonyExpressor | None = None


def get_colony_expressor() -> ColonyExpressor:
    """Get global colony expressor instance."""
    global _COLONY_EXPRESSOR
    if _COLONY_EXPRESSOR is None:
        _COLONY_EXPRESSOR = ColonyExpressor()
    return _COLONY_EXPRESSOR
