"""Tesla Integration Types — Consolidated Type Definitions.

All shared types for the Tesla integration are defined here to avoid
duplication and ensure consistency across:
- tesla.py (main integration)
- tesla_event_bus.py (real-time event processing)
- tesla_safety.py (CBF safety barrier)
- tesla_commands.py (command execution)

Created: January 11, 2026
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

# =============================================================================
# VEHICLE STATE ENUMS
# =============================================================================


class VehicleState(Enum):
    """Vehicle connectivity state."""

    ONLINE = "online"
    ASLEEP = "asleep"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class ChargingState(Enum):
    """Battery charging state."""

    DISCONNECTED = "Disconnected"
    CHARGING = "Charging"
    STOPPED = "Stopped"
    COMPLETE = "Complete"
    NO_POWER = "NoPower"
    UNKNOWN = "unknown"


class DrivingState(Enum):
    """Vehicle driving state from speed and gear.

    Consolidated from tesla_event_bus.py and tesla_safety.py.

    Granular states (event bus):
    - PARKED: In Park gear
    - STOPPED: In D/R/N but speed=0
    - MOVING_SLOW: < 15 mph
    - MOVING_FAST: >= 15 mph

    For safety barrier, use is_moving property to check if vehicle is in motion.
    """

    PARKED = "parked"  # P gear
    STOPPED = "stopped"  # D/R/N but speed=0
    MOVING_SLOW = "moving_slow"  # < 15 mph
    MOVING_FAST = "moving_fast"  # >= 15 mph
    MOVING = "moving"  # Any speed > 0 (for safety barrier compatibility)
    UNKNOWN = "unknown"

    @property
    def is_moving(self) -> bool:
        """Check if this state represents vehicle in motion."""
        return self in (DrivingState.MOVING_SLOW, DrivingState.MOVING_FAST, DrivingState.MOVING)

    @property
    def is_parked(self) -> bool:
        """Check if vehicle is in Park."""
        return self == DrivingState.PARKED

    @property
    def is_stopped(self) -> bool:
        """Check if vehicle is stopped (including parked)."""
        return self in (DrivingState.PARKED, DrivingState.STOPPED)


class TeslaPresenceState(Enum):
    """Derived presence state from telemetry."""

    PARKED_HOME = "parked_home"
    PARKED_AWAY = "parked_away"
    DRIVING_AWAY = "driving_away"
    DRIVING_HOME = "driving_home"
    ARRIVING = "arriving"  # Within 5 min of home
    DEPARTING = "departing"  # Just left home (< 2 min)
    UNKNOWN = "unknown"


class TeslaEventType(Enum):
    """Events emitted by the Tesla Event Bus."""

    # Presence events
    ARRIVAL_IMMINENT = "arrival_imminent"  # Within 5 min of home
    ARRIVAL_DETECTED = "arrival_detected"  # Entered home geofence
    DEPARTURE_DETECTED = "departure_detected"  # Left home geofence
    PARKED_HOME = "parked_home"  # Parked in garage
    PARKED_AWAY = "parked_away"  # Parked somewhere else

    # Driving events
    DRIVING_STARTED = "driving_started"  # Started moving
    DRIVING_STOPPED = "driving_stopped"  # Stopped moving
    HEADING_HOME = "heading_home"  # Direction changed toward home
    HEADING_AWAY = "heading_away"  # Direction changed away from home

    # Safety events
    SAFETY_ALERT = "safety_alert"  # CRITICAL alert from vehicle
    PET_TEMP_WARNING = "pet_temp_warning"  # Dog mode temp rising
    PET_TEMP_CRITICAL = "pet_temp_critical"  # Dog mode temp dangerous
    SECURITY_CHANGED = "security_changed"  # Sentry mode toggled

    # Charging events
    CHARGE_STARTED = "charge_started"
    CHARGE_COMPLETE = "charge_complete"
    CHARGE_REMINDER = "charge_reminder"  # Low battery, not plugged in
    CHARGE_NEEDED = "charge_needed"  # Not enough for next trip

    # Climate events
    PRECONDITION_STARTED = "precondition_started"
    PRECONDITION_COMPLETE = "precondition_complete"
    CLIMATE_KEEPER_ACTIVE = "climate_keeper_active"  # Dog/Camp mode

    # Compound events
    GARAGE_APPROACH = "garage_approach"  # HomeLink nearby + approaching
    WINDOWS_NEED_CLOSE = "windows_need_close"  # Windows open + weather alert


class ConfirmationType(Enum):
    """Type of confirmation required for safety barrier."""

    NONE = "none"  # No confirmation needed
    SOFT = "soft"  # In-app confirmation OK
    KEY_CARD = "key_card"  # Physical key card tap required
    BLOCKED = "blocked"  # Command blocked entirely while driving


# =============================================================================
# VEHICLE STATE DATACLASSES
# =============================================================================


@dataclass
class TeslaState:
    """Current Tesla vehicle state snapshot."""

    state: VehicleState
    latitude: float | None
    longitude: float | None
    battery_level: int
    charging_state: ChargingState
    charge_limit: int
    inside_temp: float | None
    outside_temp: float | None
    climate_on: bool
    locked: bool
    odometer: float
    last_seen: datetime | None


# =============================================================================
# TELEMETRY DATACLASSES
# =============================================================================


@dataclass
class TelemetryValue:
    """A telemetry value with timestamp."""

    value: Any
    timestamp: float

    @property
    def age_seconds(self) -> float:
        """How old is this telemetry reading."""
        return time.time() - self.timestamp


@dataclass
class TelemetrySnapshot:
    """Point-in-time snapshot of all telemetry."""

    timestamp: float
    location: tuple[float, float] | None
    speed: float
    shift_state: str
    heading: float
    battery_level: int
    charge_state: str
    inside_temp: float | None
    climate_keeper_mode: str | None
    locked: bool
    sentry_mode: bool


# =============================================================================
# EVENT BUS DATACLASSES
# =============================================================================


@dataclass
class EventPayload:
    """Payload for an emitted event."""

    event_type: TeslaEventType
    timestamp: float
    data: dict[str, Any]


# =============================================================================
# SAFETY BARRIER DATACLASSES
# =============================================================================


@dataclass
class ConfirmationRequest:
    """Pending confirmation request for safety barrier."""

    command: str
    args: dict[str, Any]
    confirmation_type: ConfirmationType
    requested_at: float
    expires_at: float
    confirmed: bool = False
    confirmation_token: str = ""

    @property
    def is_expired(self) -> bool:
        """Check if this request has expired."""
        return time.time() > self.expires_at


@dataclass
class SafetyState:
    """Current safety state from telemetry."""

    driving_state: DrivingState = DrivingState.UNKNOWN
    speed_mph: float = 0.0
    shift_state: str = "P"
    locked: bool = True
    key_card_present: bool = False
    last_key_card_tap: float = 0.0  # Timestamp of last key card event
    last_update: float = 0.0


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "ChargingState",
    "ConfirmationType",
    "DrivingState",
    "TeslaEventType",
    "TeslaPresenceState",
    "VehicleState",
    # Dataclasses
    "ConfirmationRequest",
    "EventPayload",
    "SafetyState",
    "TelemetrySnapshot",
    "TelemetryValue",
    "TeslaState",
]
