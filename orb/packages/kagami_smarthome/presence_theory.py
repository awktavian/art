"""Presence Theory — Bayesian Person Tracking with Uncertainty.

Formalizes presence inference using probabilistic reasoning.
Grounds presence detection in active inference framework.

Architecture:
```
Sensor Observations → Bayesian Filter → Belief State → Presence Estimate
        │                   │                              │
   WiFi, Motion,        Prior + Likelihood            P(person|room)
   Cameras, Sleep                                    with uncertainty
```

Colony: Grove (e6) — Research & Theory
Created: December 31, 2025

References:
- Friston, K. (2010) "The free-energy principle"
- Thrun, S. (2002) "Probabilistic Robotics"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================


class RoomId(str, Enum):
    """Room identifiers."""

    LIVING_ROOM = "Living Room"
    KITCHEN = "Kitchen"
    PRIMARY_BEDROOM = "Primary Bedroom"
    PRIMARY_BATH = "Primary Bath"
    OFFICE = "Office"
    DINING = "Dining"
    ENTRY = "Entry"
    GARAGE = "Garage"
    GAME_ROOM = "Game Room"
    GYM = "Gym"
    BED_3 = "Bed 3"
    BED_4 = "Bed 4"


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class PresenceBelief:
    """Belief state about a person's presence in a room.

    Uses probabilistic representation with uncertainty quantification.
    """

    room: str
    probability: float  # P(person in room)
    uncertainty: float  # Variance in estimate
    last_updated: datetime
    evidence_sources: list[str] = field(default_factory=list)


@dataclass
class PersonState:
    """Complete belief state about a person."""

    person_id: str
    name: str
    beliefs: dict[str, PresenceBelief]  # room -> belief
    most_likely_room: str | None
    is_home: bool
    is_asleep: bool
    confidence: float  # Overall confidence in state
    updated_at: datetime


@dataclass
class SensorObservation:
    """An observation from a sensor."""

    sensor_type: str  # "wifi", "motion", "camera", "sleep", "door"
    room: str | None
    value: Any
    timestamp: datetime
    reliability: float = 0.9  # Sensor reliability factor


# =============================================================================
# BAYESIAN PRESENCE FILTER
# =============================================================================


class BayesianPresenceFilter:
    """Bayesian filter for person presence tracking.

    Uses recursive Bayesian estimation:
        P(x_t | z_{1:t}) ∝ P(z_t | x_t) × P(x_t | z_{1:t-1})

    Where:
        x_t = presence state at time t
        z_t = observation at time t
        P(z_t | x_t) = observation likelihood
        P(x_t | z_{1:t-1}) = prior (prediction from previous state)

    This implements a variant of the Bayes filter suitable for
    discrete room occupancy estimation.
    """

    def __init__(
        self,
        rooms: list[str],
        prior_home_probability: float = 0.7,
        motion_decay_minutes: float = 15.0,
    ) -> None:
        """Initialize the filter.

        Args:
            rooms: List of room names
            prior_home_probability: Prior probability person is home
            motion_decay_minutes: How quickly motion evidence decays
        """
        self.rooms = rooms
        self.prior_home = prior_home_probability
        self.motion_decay = motion_decay_minutes

        # Initialize uniform prior over rooms
        self._beliefs: dict[str, float] = {}
        self._reset_beliefs()

        # Track last observations
        self._last_motion: dict[str, datetime] = {}
        self._last_wifi: datetime | None = None

    def _reset_beliefs(self) -> None:
        """Reset to uniform prior."""
        uniform = 1.0 / len(self.rooms)
        self._beliefs = {room: uniform for room in self.rooms}

    def predict(self, dt_seconds: float) -> None:
        """Prediction step: apply transition model.

        Models person movement between rooms.
        Increases uncertainty over time.

        Args:
            dt_seconds: Time since last update
        """
        # Simple diffusion model: beliefs spread to adjacent rooms over time
        # In practice, would use actual room topology

        diffusion_rate = 0.01 * (dt_seconds / 60.0)  # 1% per minute

        new_beliefs = {}
        for room in self.rooms:
            # Some probability flows to other rooms
            outflow = self._beliefs[room] * diffusion_rate * (len(self.rooms) - 1)
            inflow = sum(
                self._beliefs[other] * diffusion_rate for other in self.rooms if other != room
            )
            new_beliefs[room] = self._beliefs[room] - outflow + inflow

        self._beliefs = new_beliefs

    def update(self, observation: SensorObservation) -> None:
        """Update step: incorporate new observation.

        Applies Bayes rule:
            P(room | obs) ∝ P(obs | room) × P(room)

        Args:
            observation: New sensor observation
        """
        if observation.sensor_type == "motion":
            self._update_motion(observation)
        elif observation.sensor_type == "wifi":
            self._update_wifi(observation)
        elif observation.sensor_type == "door":
            self._update_door(observation)
        elif observation.sensor_type == "sleep":
            self._update_sleep(observation)

        # Normalize beliefs
        total = sum(self._beliefs.values())
        if total > 0:
            self._beliefs = {r: p / total for r, p in self._beliefs.items()}

    def _update_motion(self, obs: SensorObservation) -> None:
        """Update beliefs based on motion sensor."""
        if obs.room is None:
            return

        if obs.value:  # Motion detected
            # High likelihood of being in this room
            likelihood = obs.reliability
            self._beliefs[obs.room] *= likelihood / self._beliefs.get(obs.room, 0.1) + 0.001
            self._last_motion[obs.room] = obs.timestamp

            # Decrease likelihood of other rooms
            for other in self.rooms:
                if other != obs.room:
                    self._beliefs[other] *= 1.0 - likelihood * 0.5

    def _update_wifi(self, obs: SensorObservation) -> None:
        """Update beliefs based on WiFi presence."""
        if obs.value:  # Device detected on network
            self._last_wifi = obs.timestamp
            # Just confirms home, not specific room
            # Slight boost to all room probabilities
        else:
            # Not on WiFi - might be away
            for room in self.rooms:
                self._beliefs[room] *= 0.5

    def _update_door(self, obs: SensorObservation) -> None:
        """Update beliefs based on door sensor."""
        if obs.room and obs.value:  # Door opened
            # Person likely near this door/room
            self._beliefs[obs.room] *= 2.0

    def _update_sleep(self, obs: SensorObservation) -> None:
        """Update beliefs based on sleep sensor (e.g., Eight Sleep)."""
        if obs.room and obs.value:  # In bed
            # Very high confidence in bedroom
            self._beliefs[obs.room] = 0.95
            for other in self.rooms:
                if other != obs.room:
                    self._beliefs[other] = 0.05 / (len(self.rooms) - 1)

    def get_beliefs(self) -> dict[str, PresenceBelief]:
        """Get current presence beliefs for all rooms."""
        now = datetime.now()
        return {
            room: PresenceBelief(
                room=room,
                probability=prob,
                uncertainty=self._compute_uncertainty(room),
                last_updated=now,
                evidence_sources=self._get_evidence_sources(room),
            )
            for room, prob in self._beliefs.items()
        }

    def get_most_likely_room(self) -> tuple[str, float]:
        """Get the most likely room and its probability."""
        if not self._beliefs:
            return self.rooms[0], 0.0
        best = max(self._beliefs.items(), key=lambda x: x[1])
        return best[0], best[1]

    def _compute_uncertainty(self, room: str) -> float:
        """Compute uncertainty (variance proxy) for a room belief."""
        p = self._beliefs[room]
        # Entropy-based uncertainty
        if p <= 0 or p >= 1:
            return 0.0
        import math

        entropy = -p * math.log2(p) - (1 - p) * math.log2(1 - p)
        return entropy

    def _get_evidence_sources(self, room: str) -> list[str]:
        """Get evidence sources supporting belief in this room."""
        sources = []
        if room in self._last_motion:
            age = (datetime.now() - self._last_motion[room]).total_seconds() / 60
            if age < self.motion_decay:
                sources.append(f"motion ({age:.0f}min ago)")
        if self._last_wifi:
            sources.append("wifi")
        return sources


# =============================================================================
# ACTIVE INFERENCE PRESENCE MODEL
# =============================================================================


@dataclass
class ActiveInferencePresenceConfig:
    """Configuration for active inference presence model."""

    # Prior preferences
    prefer_known_locations: float = 0.8
    prefer_recent_evidence: float = 0.9

    # Active inference parameters
    precision_motion: float = 1.0
    precision_wifi: float = 0.5
    precision_sleep: float = 2.0

    # Free energy threshold
    fe_threshold: float = 0.1


class ActiveInferencePresence:
    """Presence inference using active inference framework.

    Implements Friston's Free Energy Principle for presence estimation:

    F = E_q[log q(x) - log p(o,x)]
      = Complexity - Accuracy

    Where:
        q(x) = belief about presence state
        p(o,x) = generative model (how presence generates observations)

    The system maintains beliefs that minimize free energy, balancing:
    - Accuracy: beliefs match observations
    - Complexity: beliefs don't deviate too far from priors

    This provides:
    1. Principled uncertainty quantification
    2. Active sensing suggestions
    3. Robust multi-sensor fusion
    """

    def __init__(
        self,
        rooms: list[str],
        config: ActiveInferencePresenceConfig | None = None,
    ) -> None:
        self.rooms = rooms
        self.config = config or ActiveInferencePresenceConfig()

        # Bayesian filter as core state estimator
        self._filter = BayesianPresenceFilter(rooms)

        # Track free energy components
        self._complexity = 0.0
        self._accuracy = 0.0

    def process_observation(self, obs: SensorObservation) -> None:
        """Process observation and update beliefs."""
        # Map sensor type to precision
        precision = {
            "motion": self.config.precision_motion,
            "wifi": self.config.precision_wifi,
            "sleep": self.config.precision_sleep,
        }.get(obs.sensor_type, 0.5)

        # Weight observation by precision
        weighted_obs = SensorObservation(
            sensor_type=obs.sensor_type,
            room=obs.room,
            value=obs.value,
            timestamp=obs.timestamp,
            reliability=obs.reliability * precision,
        )

        self._filter.update(weighted_obs)
        self._update_free_energy()

    def _update_free_energy(self) -> None:
        """Update free energy estimate."""
        beliefs = self._filter.get_beliefs()

        # Complexity: KL divergence from prior
        # Simplified: sum of deviations from uniform
        uniform = 1.0 / len(self.rooms)
        complexity = sum(abs(b.probability - uniform) for b in beliefs.values())

        # Accuracy: confidence in most likely state
        _, prob = self._filter.get_most_likely_room()
        accuracy = prob

        self._complexity = complexity
        self._accuracy = accuracy

    def get_free_energy(self) -> float:
        """Get current free energy (lower = better)."""
        return self._complexity - self._accuracy

    def suggest_active_sensing(self) -> list[str]:
        """Suggest actions to reduce uncertainty (active inference).

        Returns sensors/rooms that would most reduce free energy if sampled.
        """
        beliefs = self._filter.get_beliefs()

        # Find rooms with high uncertainty
        uncertain_rooms = [room for room, belief in beliefs.items() if belief.uncertainty > 0.5]

        suggestions = []
        for room in uncertain_rooms:
            suggestions.append(f"Check motion sensor in {room}")

        # If overall uncertainty is high, suggest WiFi check
        avg_uncertainty = sum(b.uncertainty for b in beliefs.values()) / len(beliefs)
        if avg_uncertainty > 0.6:
            suggestions.append("Verify WiFi presence")

        return suggestions

    def get_state(self) -> PersonState:
        """Get complete person state estimate."""
        beliefs = self._filter.get_beliefs()
        most_likely, confidence = self._filter.get_most_likely_room()

        # Check if home (sum of all room probabilities)
        home_prob = sum(b.probability for b in beliefs.values())

        # Check if asleep (high bedroom probability + sleep sensor)
        is_asleep = (
            beliefs.get("Primary Bedroom", PresenceBelief("", 0, 0, datetime.now())).probability
            > 0.8
        )

        return PersonState(
            person_id="owner",
            name="Tim",
            beliefs=beliefs,
            most_likely_room=most_likely if confidence > 0.3 else None,
            is_home=home_prob > 0.5,
            is_asleep=is_asleep,
            confidence=confidence,
            updated_at=datetime.now(),
        )


# =============================================================================
# FACTORY
# =============================================================================


def create_presence_model(
    rooms: list[str] | None = None,
) -> ActiveInferencePresence:
    """Create a presence model.

    Args:
        rooms: List of room names (uses defaults if not provided)

    Returns:
        Configured presence model
    """
    if rooms is None:
        rooms = [r.value for r in RoomId]

    return ActiveInferencePresence(rooms)


__all__ = [
    "ActiveInferencePresence",
    "ActiveInferencePresenceConfig",
    "BayesianPresenceFilter",
    "PersonState",
    "PresenceBelief",
    "RoomId",
    "SensorObservation",
    "create_presence_model",
]
