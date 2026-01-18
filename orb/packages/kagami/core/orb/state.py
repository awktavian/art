"""Orb State — Canonical State Model.

This module defines the authoritative orb state that is synchronized
across all clients. State is managed server-side and broadcast via
WebSocket to all connected clients.

Design Principles:
    1. Server-authoritative: Clients read state, never write directly
    2. Single source of truth: All clients use this model
    3. Event-driven: State changes emit events for sync
    4. Immutable snapshots: State objects are frozen dataclasses

Colony: Nexus (e₄) — State synchronization

Example:
    >>> from kagami.core.orb import OrbState, create_orb_state
    >>> state = create_orb_state(active_colony="forge", safety_score=0.85)
    >>> state.color.hex
    '#FFB347'
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kagami.core.orb.colors import ColonyColor, get_colony_color, get_safety_color


class OrbActivity(str, Enum):
    """Current orb activity state.

    The activity determines visual behavior:
        - IDLE: Slow breathing animation
        - LISTENING: Pulse following audio input
        - PROCESSING: Spinning indicator
        - RESPONDING: Colony color highlight
        - ERROR: Red pulse
        - SAFETY_ALERT: Amber warning
    """

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    ERROR = "error"
    SAFETY_ALERT = "safety_alert"
    PORTABLE = "portable"  # Hardware orb undocked


class ConnectionState(str, Enum):
    """Orb connection state to API."""

    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass(frozen=True)
class OrbPosition:
    """3D position for spatial orb implementations.

    Coordinates are in meters, relative to head/origin.
    Used by VisionOS and future AR/VR implementations.

    Attributes:
        x: Left/right (positive = right)
        y: Up/down (positive = up)
        z: Forward/back (negative = forward)
        scale: Orb scale multiplier (1.0 = default)
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    scale: float = 1.0

    def as_tuple(self) -> tuple[float, float, float]:
        """Return (x, y, z) tuple.

        Returns:
            Position as tuple for Swift SIMD3 or similar
        """
        return (self.x, self.y, self.z)

    def distance_from_origin(self) -> float:
        """Calculate distance from origin.

        Returns:
            Euclidean distance in meters
        """
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5


@dataclass(frozen=True)
class OrbState:
    """Canonical orb state synchronized across all clients.

    This is the authoritative state model. All clients should
    render their orb based on this state.

    Attributes:
        active_colony: Currently active colony (or None for idle)
        activity: Current activity state
        safety_score: h(x) safety score (0.0-1.0)
        connection: Connection state to API
        position: 3D position (for spatial clients)
        active_colonies: List of all active colonies
        home_status: Home automation status
        timestamp: Unix timestamp of state update

    Example:
        >>> state = OrbState(active_colony="forge", safety_score=0.85)
        >>> state.color.hex
        '#FFB347'
        >>> state.is_safe
        True
    """

    active_colony: str | None = None
    activity: OrbActivity = OrbActivity.IDLE
    safety_score: float = 1.0
    connection: ConnectionState = ConnectionState.CONNECTED
    position: OrbPosition = field(default_factory=OrbPosition)
    active_colonies: list[str] = field(default_factory=list)
    home_status: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def color(self) -> ColonyColor:
        """Get the display color based on current state.

        Priority:
            1. Error state → Error red
            2. Safety alert → Safety amber
            3. Active colony → Colony color
            4. Default → Idle blue

        Returns:
            ColonyColor to display
        """
        if self.connection == ConnectionState.ERROR:
            from kagami.core.orb.colors import ERROR_COLOR

            return ERROR_COLOR
        if self.activity == OrbActivity.SAFETY_ALERT:
            return get_safety_color(self.safety_score)
        if self.activity == OrbActivity.ERROR:
            from kagami.core.orb.colors import ERROR_COLOR

            return ERROR_COLOR
        return get_colony_color(self.active_colony)

    @property
    def is_safe(self) -> bool:
        """Check if safety score is in safe range.

        Returns:
            True if h(x) >= 0.5
        """
        return self.safety_score >= 0.5

    @property
    def is_connected(self) -> bool:
        """Check if orb is connected to API.

        Returns:
            True if connection state is CONNECTED
        """
        return self.connection == ConnectionState.CONNECTED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict suitable for WebSocket broadcast
        """
        return {
            "active_colony": self.active_colony,
            "activity": self.activity.value,
            "safety_score": self.safety_score,
            "connection": self.connection.value,
            "position": {
                "x": self.position.x,
                "y": self.position.y,
                "z": self.position.z,
                "scale": self.position.scale,
            },
            "active_colonies": self.active_colonies,
            "home_status": self.home_status,
            "timestamp": self.timestamp,
            "color": {
                "hex": self.color.hex,
                "rgb": self.color.rgb,
                "name": self.color.description,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrbState:
        """Create OrbState from dictionary.

        Args:
            data: Dict from WebSocket message

        Returns:
            OrbState instance
        """
        position_data = data.get("position", {})
        return cls(
            active_colony=data.get("active_colony"),
            activity=OrbActivity(data.get("activity", "idle")),
            safety_score=data.get("safety_score", 1.0),
            connection=ConnectionState(data.get("connection", "connected")),
            position=OrbPosition(
                x=position_data.get("x", 0.0),
                y=position_data.get("y", 0.0),
                z=position_data.get("z", 0.0),
                scale=position_data.get("scale", 1.0),
            ),
            active_colonies=data.get("active_colonies", []),
            home_status=data.get("home_status", {}),
            timestamp=data.get("timestamp", time.time()),
        )


# =============================================================================
# Factory Functions
# =============================================================================

# Global state singleton (server-side)
_current_state: OrbState | None = None


def create_orb_state(
    active_colony: str | None = None,
    activity: OrbActivity = OrbActivity.IDLE,
    safety_score: float = 1.0,
    position: OrbPosition | None = None,
    active_colonies: list[str] | None = None,
    home_status: dict[str, Any] | None = None,
) -> OrbState:
    """Create a new OrbState instance.

    This is the preferred way to create state for broadcasting.

    Args:
        active_colony: Currently active colony
        activity: Current activity state
        safety_score: h(x) safety score
        position: 3D position (optional)
        active_colonies: List of active colonies (optional)
        home_status: Home automation status (optional)

    Returns:
        New OrbState instance

    Example:
        >>> state = create_orb_state(active_colony="forge")
        >>> state.color.description
        'Forge Amber'
    """
    global _current_state
    _current_state = OrbState(
        active_colony=active_colony,
        activity=activity,
        safety_score=safety_score,
        position=position or OrbPosition(),
        active_colonies=active_colonies or [],
        home_status=home_status or {},
        timestamp=time.time(),
    )
    return _current_state


def get_orb_state() -> OrbState:
    """Get the current global orb state.

    Returns:
        Current OrbState, or default if not initialized

    Example:
        >>> state = get_orb_state()
        >>> state.is_connected
        True
    """
    global _current_state
    if _current_state is None:
        _current_state = OrbState()
    return _current_state


def update_orb_state(**kwargs: Any) -> OrbState:
    """Update specific fields of the global orb state.

    This creates a new state with updated fields and replaces
    the global singleton.

    Args:
        **kwargs: Fields to update

    Returns:
        New OrbState with updates applied

    Example:
        >>> state = update_orb_state(active_colony="flow")
        >>> state.active_colony
        'flow'
    """
    global _current_state
    current = get_orb_state()

    # Build new state with updates
    new_data = current.to_dict()
    new_data.update(kwargs)

    # Handle nested position
    if "position" in kwargs and isinstance(kwargs["position"], dict):
        new_data["position"] = kwargs["position"]

    _current_state = OrbState.from_dict(new_data)
    return _current_state
