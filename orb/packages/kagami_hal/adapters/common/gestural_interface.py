"""Gestural Interface - Alyx-style Continuous Intent Recognition.

Inspired by Half-Life: Alyx's gravity gloves, this module provides:
- Continuous grip/release intent from sEMG signals
- Physics-based gesture smoothing
- Colony activation via muscle patterns
- Haptic feedback integration

The key insight from Alyx: don't wait for discrete "gesture complete" events.
Instead, stream continuous intent values that physics systems can respond to.

Created: December 20, 2025
Status: Production-ready
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Types of continuous intent."""

    # Grip/manipulation
    GRIP = "grip"  # 0.0 = open, 1.0 = closed fist
    PINCH = "pinch"  # 0.0 = open, 1.0 = thumb-finger pinch
    SPREAD = "spread"  # 0.0 = neutral, 1.0 = fingers spread

    # Directional pointing
    POINT_X = "point_x"  # -1.0 = left, 1.0 = right
    POINT_Y = "point_y"  # -1.0 = down, 1.0 = up
    POINT_Z = "point_z"  # -1.0 = away, 1.0 = toward

    # Rotational
    TWIST = "twist"  # -1.0 = CCW, 1.0 = CW
    TILT = "tilt"  # -1.0 = left, 1.0 = right

    # Abstract
    INTENSITY = "intensity"  # 0.0 = relaxed, 1.0 = maximum effort
    CONFIDENCE = "confidence"  # Intent clarity


class ColonyIntent(Enum):
    """Colony-specific activation intents."""

    SPARK = "spark"  # Quick twitch, creative burst
    FORGE = "forge"  # Sustained grip, building
    FLOW = "flow"  # Smooth wave, adaptation
    NEXUS = "nexus"  # Circular/connecting motion
    BEACON = "beacon"  # Upward point, planning
    GROVE = "grove"  # Gentle sweep, research
    CRYSTAL = "crystal"  # Sharp double activation, verification
    KAGAMI = "kagami"  # All colonies, mirror state


@dataclass
class GestureCommand:
    """A gesture-based command with continuous values."""

    # Primary intent (what action to take)
    action: str

    # Continuous parameters (Alyx-style)
    grip_strength: float = 0.0  # 0-1, how hard
    reach_distance: float = 0.0  # 0-1, how far
    direction: tuple[float, float, float] = (0.0, 0.0, 0.0)
    twist_amount: float = 0.0  # -1 to 1

    # Metadata
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    source: str = "gestural"

    # Colony routing
    colony_intent: ColonyIntent | None = None


@dataclass
class ColonyActivation:
    """Colony activation state from gestural input."""

    colony: ColonyIntent
    activation: float  # 0.0 = inactive, 1.0 = fully active
    confidence: float  # How sure we are this is intentional
    sustain: bool = False  # Whether to maintain activation
    timestamp: float = field(default_factory=time.time)


@dataclass
class GesturePhysics:
    """Physics parameters for gesture smoothing.

    Alyx uses spring-damper physics to make gestures feel organic.
    We do the same: rapid intent changes are smoothed, but sustained
    intent builds up momentum.
    """

    # Spring-damper constants
    spring_k: float = 50.0  # Stiffness (higher = snappier)
    damping_b: float = 10.0  # Damping (higher = less overshoot)
    mass: float = 1.0  # Effective mass

    # Thresholds
    activation_threshold: float = 0.15  # Below this = noise
    sustain_threshold: float = 0.5  # Above this = intentional
    release_threshold: float = 0.1  # Below this = released

    # Timing
    intent_buildup_ms: float = 100.0  # Time to reach full intent
    release_decay_ms: float = 200.0  # Time to decay to zero


class GesturalInterfaceCallback(Protocol):
    """Protocol for gestural interface callbacks."""

    async def __call__(self, command: GestureCommand) -> None: ...


class ColonyActivationCallback(Protocol):
    """Protocol for colony activation callbacks."""

    async def __call__(self, activation: ColonyActivation) -> None: ...


class GesturalInterface:
    """Continuous gestural interface inspired by Alyx gravity gloves.

    Key principles:
    1. Intent is continuous, not discrete
    2. Physics smoothing makes gestures feel natural
    3. Colony activation is muscle-pattern-based
    4. Haptic feedback closes the loop

    Usage:
        interface = GesturalInterface()
        interface.register_command_callback(handle_command)
        interface.register_colony_callback(handle_colony)

        # Feed sEMG data continuously
        while running:
            await interface.feed_emg(emg_sample)
    """

    def __init__(self, physics: GesturePhysics | None = None, enable_haptics: bool = True) -> None:
        self.physics = physics or GesturePhysics()
        self.enable_haptics = enable_haptics

        # Current state
        self._intent_values: dict[IntentType, float] = dict.fromkeys(IntentType, 0.0)
        self._smoothed_values: dict[IntentType, float] = dict.fromkeys(IntentType, 0.0)
        self._velocities: dict[IntentType, float] = dict.fromkeys(IntentType, 0.0)

        # Colony state
        self._colony_activations: dict[ColonyIntent, float] = dict.fromkeys(ColonyIntent, 0.0)
        self._active_colony: ColonyIntent | None = None

        # Callbacks
        self._command_callbacks: list[GesturalInterfaceCallback] = []
        self._colony_callbacks: list[ColonyActivationCallback] = []

        # Timing
        self._last_update: float = time.time()
        self._running: bool = False

        # sEMG channel mapping (8 channels typical for neural bands)
        # These weights determine how EMG channels map to intents
        self._emg_to_intent_weights = self._init_emg_weights()

        # Colony patterns (which intent combinations activate which colony)
        self._colony_patterns = self._init_colony_patterns()

        logger.info("GesturalInterface initialized")

    def _init_emg_weights(self) -> np.ndarray:
        """Initialize EMG channel to intent mapping.

        8 EMG channels (typical neural band) → 10 intent dimensions.
        These are learned in practice, but we start with biomechanically
        plausible defaults.
        """
        # Shape: [8 channels, 10 intents]
        # Rows: flexor digitorum, extensor, bicep, tricep,
        #       pronator, supinator, wrist flex, wrist extend
        # Cols: GRIP, PINCH, SPREAD, POINT_X, POINT_Y, POINT_Z,
        #       TWIST, TILT, INTENSITY, CONFIDENCE

        weights = np.array(
            [
                # GRIP  PINCH SPREAD PX    PY    PZ    TWIST TILT  INT   CONF
                [0.9, 0.3, -0.5, 0.0, 0.0, 0.3, 0.0, 0.0, 0.5, 0.0],  # flexor dig
                [-0.5, 0.2, 0.8, 0.0, 0.0, -0.2, 0.0, 0.0, 0.3, 0.0],  # extensor
                [0.2, 0.0, 0.0, 0.0, 0.6, 0.4, 0.0, 0.0, 0.4, 0.0],  # bicep
                [0.1, 0.0, 0.0, 0.0, -0.4, 0.5, 0.0, 0.0, 0.3, 0.0],  # tricep
                [0.0, 0.0, 0.0, -0.3, 0.0, 0.0, 0.7, -0.3, 0.2, 0.0],  # pronator
                [0.0, 0.0, 0.0, 0.3, 0.0, 0.0, -0.7, 0.3, 0.2, 0.0],  # supinator
                [0.3, 0.5, 0.0, 0.0, 0.3, 0.0, 0.0, 0.5, 0.2, 0.0],  # wrist flex
                [0.1, 0.2, 0.3, 0.0, -0.2, 0.0, 0.0, -0.4, 0.2, 0.0],  # wrist ext
            ],
            dtype=np.float32,
        )

        return weights

    def _init_colony_patterns(self) -> dict[ColonyIntent, np.ndarray]:
        """Initialize colony activation patterns.

        Each colony has a characteristic intent signature.
        """
        patterns = {}

        # Spark: Quick burst, high intensity, low grip
        patterns[ColonyIntent.SPARK] = np.array([0.2, 0.3, 0.5, 0.0, 0.3, 0.0, 0.0, 0.0, 0.9, 0.8])

        # Forge: Strong sustained grip
        patterns[ColonyIntent.FORGE] = np.array([0.9, 0.4, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.7, 0.9])

        # Flow: Smooth wave motion
        patterns[ColonyIntent.FLOW] = np.array([0.3, 0.2, 0.3, 0.5, 0.2, 0.2, 0.3, 0.3, 0.4, 0.7])

        # Nexus: Circular/twist motion
        patterns[ColonyIntent.NEXUS] = np.array([0.4, 0.4, 0.2, 0.3, 0.3, 0.3, 0.7, 0.0, 0.5, 0.8])

        # Beacon: Point up/forward
        patterns[ColonyIntent.BEACON] = np.array([0.1, 0.6, 0.7, 0.0, 0.8, 0.3, 0.0, 0.0, 0.5, 0.9])

        # Grove: Gentle sweep
        patterns[ColonyIntent.GROVE] = np.array([0.2, 0.2, 0.4, 0.4, 0.0, 0.0, 0.2, 0.3, 0.3, 0.6])

        # Crystal: Sharp double activation
        patterns[ColonyIntent.CRYSTAL] = np.array(
            [0.6, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.8, 0.9]
        )

        # Kagami: Balanced all-colony
        patterns[ColonyIntent.KAGAMI] = np.array(
            [0.5, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.6, 0.95]
        )

        return patterns

    def register_command_callback(self, callback: GesturalInterfaceCallback) -> None:
        """Register callback for gesture commands."""
        self._command_callbacks.append(callback)

    def register_colony_callback(self, callback: ColonyActivationCallback) -> None:
        """Register callback for colony activations."""
        self._colony_callbacks.append(callback)

    async def feed_emg(self, emg_sample: np.ndarray | list[float]) -> GestureCommand | None:
        """Feed an sEMG sample and update state.

        Args:
            emg_sample: 8-channel EMG values (typically 0-1 normalized RMS)

        Returns:
            GestureCommand if intent is above threshold, None otherwise
        """
        emg = np.array(emg_sample, dtype=np.float32)
        if emg.shape[0] != 8:
            logger.warning(f"Expected 8 EMG channels, got {emg.shape[0]}")
            emg = np.pad(emg, (0, max(0, 8 - len(emg))))[:8]

        # Map EMG to intent space
        raw_intent = emg @ self._emg_to_intent_weights

        # Update raw intent values
        intent_types = list(IntentType)
        for i, intent in enumerate(intent_types):
            self._intent_values[intent] = float(raw_intent[i])

        # Apply physics smoothing
        now = time.time()
        dt = now - self._last_update
        self._last_update = now

        self._apply_physics(dt)

        # Check colony activation
        await self._update_colony_activation()

        # Generate command if above threshold
        intensity = self._smoothed_values[IntentType.INTENSITY]
        _confidence = self._smoothed_values[IntentType.CONFIDENCE]  # Reserved for future use

        if intensity > self.physics.activation_threshold:
            command = self._generate_command()

            for cb in self._command_callbacks:
                try:
                    await cb(command)
                except Exception as e:
                    logger.warning(f"Command callback error: {e}")

            return command

        return None

    def _apply_physics(self, dt: float) -> None:
        """Apply spring-damper physics to smooth intent values.

        This is the Alyx magic: raw EMG is noisy, but physics makes it feel good.
        """
        dt = min(dt, 0.1)  # Cap for stability

        for intent in IntentType:
            target = self._intent_values[intent]
            current = self._smoothed_values[intent]
            velocity = self._velocities[intent]

            # Spring-damper: F = -k*x - b*v
            error = target - current
            force = self.physics.spring_k * error - self.physics.damping_b * velocity

            # Integrate
            acceleration = force / self.physics.mass
            velocity += acceleration * dt
            current += velocity * dt

            # Clamp
            if intent in (
                IntentType.GRIP,
                IntentType.PINCH,
                IntentType.SPREAD,
                IntentType.INTENSITY,
                IntentType.CONFIDENCE,
            ):
                current = np.clip(current, 0.0, 1.0)
            else:
                current = np.clip(current, -1.0, 1.0)

            self._smoothed_values[intent] = current
            self._velocities[intent] = velocity

    async def _update_colony_activation(self) -> None:
        """Update colony activation based on current intent pattern."""
        # Get current intent vector
        intent_vector = np.array([self._smoothed_values[intent] for intent in IntentType])

        # Compare against each colony pattern
        best_colony: ColonyIntent | None = None
        best_match = 0.0

        for colony, pattern in self._colony_patterns.items():
            # Cosine similarity
            similarity = np.dot(intent_vector, pattern) / (
                np.linalg.norm(intent_vector) * np.linalg.norm(pattern) + 1e-6
            )

            self._colony_activations[colony] = float(similarity)

            if similarity > best_match and similarity > 0.6:
                best_match = similarity
                best_colony = colony

        # Emit colony activation if changed or significant
        if best_colony and (best_colony != self._active_colony or best_match > 0.8):
            self._active_colony = best_colony

            activation = ColonyActivation(
                colony=best_colony,
                activation=best_match,
                confidence=self._smoothed_values[IntentType.CONFIDENCE],
                sustain=best_match > self.physics.sustain_threshold,
            )

            for cb in self._colony_callbacks:
                try:
                    await cb(activation)
                except Exception as e:
                    logger.warning(f"Colony callback error: {e}")

    def _generate_command(self) -> GestureCommand:
        """Generate a gesture command from current state."""
        return GestureCommand(
            action="gesture",
            grip_strength=self._smoothed_values[IntentType.GRIP],
            reach_distance=max(0, self._smoothed_values[IntentType.POINT_Z]),
            direction=(
                self._smoothed_values[IntentType.POINT_X],
                self._smoothed_values[IntentType.POINT_Y],
                self._smoothed_values[IntentType.POINT_Z],
            ),
            twist_amount=self._smoothed_values[IntentType.TWIST],
            confidence=self._smoothed_values[IntentType.CONFIDENCE],
            colony_intent=self._active_colony,
        )

    def get_intent(self, intent_type: IntentType) -> float:
        """Get current smoothed intent value."""
        return self._smoothed_values.get(intent_type, 0.0)

    def get_colony_activation(self, colony: ColonyIntent) -> float:
        """Get current activation level for a colony."""
        return self._colony_activations.get(colony, 0.0)

    def get_all_intents(self) -> dict[str, float]:
        """Get all current intent values."""
        return {intent.value: self._smoothed_values[intent] for intent in IntentType}

    def get_all_colony_activations(self) -> dict[str, float]:
        """Get all colony activation levels."""
        return {colony.value: self._colony_activations[colony] for colony in ColonyIntent}

    async def start(self) -> None:
        """Start the gestural interface."""
        self._running = True
        self._last_update = time.time()
        logger.info("GesturalInterface started")

    async def stop(self) -> None:
        """Stop the gestural interface."""
        self._running = False
        logger.info("GesturalInterface stopped")
