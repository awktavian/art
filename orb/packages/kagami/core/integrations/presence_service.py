"""Unified Presence Service — SINGLE SOURCE for all presence data.

CREATED: December 30, 2025 (Phase 3 Refactor)

Consolidates presence detection from three sources:
- PresenceEngine: Theory of Mind + pattern learning
- DeviceLocalizer: Room-level WiFi triangulation
- DeviceReconciler: Multi-device (phone/laptop/car) reconciliation

Provides:
- Single API for all presence queries
- Event emission for state changes
- Integration with SystemHealthMonitor
- Caching with TTL
- Pattern learning for predictions

Architecture:
    PresenceService (THIS - THE SINGLE SOURCE)
        ├── SmartHomeController (low-level integrations)
        │   ├── PresenceEngine (Theory of Mind)
        │   ├── DeviceLocalizer (Room tracking)
        │   └── DeviceReconciler (Multi-device)
        │
        ├── Presence Events → UnifiedSensoryIntegration
        └── Health Checks → SystemHealthMonitor

Usage:
    from kagami.core.integrations import get_presence_service

    presence = get_presence_service()

    # High-level queries
    is_home = presence.is_home()
    room = presence.current_room()
    travel_mode = presence.travel_mode()

    # Predictions
    next_room = presence.predict_next_room()
    eta = presence.eta_home()

    # Multi-device
    missing = presence.missing_essentials()  # ["laptop"]
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


class PresenceState(str, Enum):
    """Overall presence states."""

    HOME = "home"  # At home
    AWAY = "away"  # Away from home
    ARRIVING = "arriving"  # On the way home
    LEAVING = "leaving"  # Just left
    UNKNOWN = "unknown"


class TravelMode(str, Enum):
    """Travel modes (re-exported from device_reconciler)."""

    HOME = "home"
    DRIVING = "driving"
    CARPOOLING = "carpooling"
    WALKING = "walking"
    TRANSIT = "transit"
    UNKNOWN = "unknown"


@dataclass
class PresenceSnapshot:
    """Complete presence snapshot - THE canonical format.

    All presence queries return data conforming to this structure.
    """

    # Overall state
    state: PresenceState = PresenceState.UNKNOWN
    is_home: bool = True
    travel_mode: TravelMode = TravelMode.HOME

    # Location
    current_room: str | None = None
    previous_room: str | None = None
    room_confidence: float = 0.0

    # Multi-device state
    phone_at_home: bool = True
    laptop_at_home: bool = True
    car_at_home: bool = True
    missing_essentials: list[str] = field(default_factory=list)

    # Web presence (Jan 4, 2026)
    web_presence_active: bool = False
    web_presence_confidence: str = "none"  # high/medium/low/none
    web_active_sessions: int = 0
    web_geo_hash: str | None = None

    # Distance/ETA
    distance_from_home_miles: float | None = None
    eta_minutes: int | None = None

    # Timing
    time_in_current_room: float = 0.0
    time_since_last_motion: float = 0.0

    # Predictions (from pattern learning)
    predicted_next_room: str | None = None
    predicted_next_room_confidence: float = 0.0
    predicted_activity: str | None = None

    # Metadata
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.5
    source: str = "unified"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "state": self.state.value,
            "is_home": self.is_home,
            "travel_mode": self.travel_mode.value,
            "current_room": self.current_room,
            "previous_room": self.previous_room,
            "room_confidence": round(self.room_confidence, 2),
            "phone_at_home": self.phone_at_home,
            "laptop_at_home": self.laptop_at_home,
            "car_at_home": self.car_at_home,
            "missing_essentials": self.missing_essentials,
            # Web presence (Jan 4, 2026)
            "web_presence_active": self.web_presence_active,
            "web_presence_confidence": self.web_presence_confidence,
            "web_active_sessions": self.web_active_sessions,
            "web_geo_hash": self.web_geo_hash,
            # Distance/ETA
            "distance_from_home_miles": round(self.distance_from_home_miles, 2)
            if self.distance_from_home_miles
            else None,
            "eta_minutes": self.eta_minutes,
            "time_in_current_room": round(self.time_in_current_room, 1),
            "predicted_next_room": self.predicted_next_room,
            "predicted_activity": self.predicted_activity,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "confidence": round(self.confidence, 2),
        }


# Callback types
PresenceCallback = Callable[[PresenceSnapshot], Awaitable[None]]


class PresenceService:
    """Unified presence service consolidating all presence sources.

    THE SINGLE SOURCE for all presence data in Kagami.

    Sources:
    - PresenceEngine (kagami_smarthome): ToM + patterns
    - DeviceLocalizer (kagami_smarthome): Room-level tracking
    - DeviceReconciler (kagami_smarthome): Multi-device
    - WebPresenceService: Browser/app heartbeats (Jan 4, 2026)

    Consumers:
    - UnifiedSensoryIntegration (polls via SenseType.PRESENCE)
    - SituationAwarenessEngine (presence context)
    - CrossDomainBridge (triggers)
    """

    def __init__(self):
        # SmartHome controller (provides low-level integrations)
        self._controller: SmartHomeController | None = None

        # Web presence service (Jan 4, 2026)
        self._web_presence = None

        # Cached state
        self._cached_snapshot: PresenceSnapshot | None = None
        self._cache_ttl: float = 30.0  # 30 seconds
        self._last_update: float = 0.0

        # Callbacks
        self._callbacks: list[PresenceCallback] = []

        # State tracking
        self._previous_state: PresenceState = PresenceState.UNKNOWN
        self._state_change_time: float = 0.0

        # Health
        self._initialized = False
        self._last_error: str | None = None

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    async def initialize(self, controller: SmartHomeController | None = None) -> bool:
        """Initialize the presence service.

        Args:
            controller: Optional SmartHomeController instance

        Returns:
            True if initialization successful
        """
        try:
            if controller:
                self._controller = controller
            else:
                # Try to get from singleton
                try:
                    from kagami_smarthome import get_smart_home

                    self._controller = await get_smart_home()
                except ImportError:
                    logger.warning("SmartHome not available, presence will be limited")

            # Initialize web presence service (Jan 4, 2026)
            try:
                from kagami.core.integrations.web_presence import get_web_presence_service

                self._web_presence = await get_web_presence_service()
                logger.info("✅ WebPresenceService integrated")
            except Exception as e:
                logger.debug(f"WebPresenceService not available: {e}")

            # Register with SystemHealthMonitor
            self._register_health_check()

            self._initialized = True
            logger.info("✅ PresenceService initialized")
            return True

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"PresenceService initialization failed: {e}")
            return False

    def _register_health_check(self) -> None:
        """Register with SystemHealthMonitor."""
        try:
            from kagami.core.integrations.system_health import (
                HealthCheckConfig,
                IntegrationTier,
                get_system_health_monitor,
            )

            monitor = get_system_health_monitor()

            async def check_presence() -> bool:
                return self._initialized and self._controller is not None

            monitor.register_check(
                HealthCheckConfig(
                    name="presence_service",
                    check_fn=check_presence,
                    interval_seconds=60.0,
                    tier=IntegrationTier.CRITICAL,
                )
            )

        except ImportError:
            pass

    # =========================================================================
    # HIGH-LEVEL QUERIES (THE API)
    # =========================================================================

    async def get_snapshot(self, force_refresh: bool = False) -> PresenceSnapshot:
        """Get current presence snapshot.

        This is THE main API for presence queries.

        Args:
            force_refresh: Skip cache and fetch fresh data

        Returns:
            Complete presence snapshot
        """
        now = time.time()

        # Use cache if valid
        if not force_refresh and self._cached_snapshot:
            if now - self._last_update < self._cache_ttl:
                return self._cached_snapshot

        # Build fresh snapshot
        snapshot = await self._build_snapshot()

        # Update cache
        self._cached_snapshot = snapshot
        self._last_update = now

        # Check for state change
        if snapshot.state != self._previous_state:
            self._previous_state = snapshot.state
            self._state_change_time = now
            await self._emit_state_change(snapshot)

        return snapshot

    def is_home(self) -> bool:
        """Quick check if Tim is home."""
        if self._cached_snapshot:
            return self._cached_snapshot.is_home
        return True  # Default to home

    def current_room(self) -> str | None:
        """Get current room."""
        if self._cached_snapshot:
            return self._cached_snapshot.current_room
        return None

    def travel_mode(self) -> TravelMode:
        """Get current travel mode."""
        if self._cached_snapshot:
            return self._cached_snapshot.travel_mode
        return TravelMode.HOME

    def missing_essentials(self) -> list[str]:
        """Get list of missing essential items (laptop, etc.)."""
        if self._cached_snapshot:
            return self._cached_snapshot.missing_essentials
        return []

    def eta_home(self) -> int | None:
        """Get ETA to home in minutes (None if at home)."""
        if self._cached_snapshot:
            return self._cached_snapshot.eta_minutes
        return None

    def predict_next_room(self) -> tuple[str | None, float]:
        """Predict next room transition.

        Returns:
            Tuple of (predicted_room, confidence)
        """
        if self._cached_snapshot:
            return (
                self._cached_snapshot.predicted_next_room,
                self._cached_snapshot.predicted_next_room_confidence,
            )
        return None, 0.0

    # =========================================================================
    # SNAPSHOT BUILDING (Internal)
    # =========================================================================

    async def _build_snapshot(self) -> PresenceSnapshot:
        """Build presence snapshot from all sources."""
        snapshot = PresenceSnapshot()

        if not self._controller:
            return snapshot

        try:
            # Get data from controller's presence components

            # 1. Overall home state from HomeState
            home_state = self._controller.get_state()
            if home_state:
                snapshot.is_home = home_state.presence in [
                    # Import these at runtime to avoid circular
                    self._get_presence_state_value("HOME"),
                    self._get_presence_state_value("ACTIVE"),
                ]

                # Room from activity
                if home_state.activity:
                    snapshot.predicted_activity = home_state.activity.value

            # 2. Room-level from DeviceLocalizer
            localizer = self._controller._localizer
            if localizer:
                owner_loc = localizer.get_owner_location()
                if owner_loc:
                    snapshot.current_room = owner_loc.current_room
                    snapshot.previous_room = owner_loc.previous_room
                    snapshot.room_confidence = self._confidence_to_float(owner_loc.room_confidence)
                    snapshot.time_in_current_room = owner_loc.time_in_room

            # 3. Multi-device from DeviceReconciler
            reconciler = self._controller._device_reconciler
            if reconciler:
                reconciled = await reconciler.reconcile()
                if reconciled:
                    snapshot.is_home = reconciled.is_home
                    snapshot.travel_mode = TravelMode(reconciled.travel_mode.value)
                    snapshot.distance_from_home_miles = reconciled.distance_from_home_miles
                    snapshot.eta_minutes = reconciled.eta_minutes
                    snapshot.missing_essentials = reconciled.missing_essentials
                    snapshot.confidence = reconciled.confidence

                    # Device states
                    if reconciled.phone_state:
                        snapshot.phone_at_home = reconciled.phone_state.is_home
                    if reconciled.laptop_state:
                        snapshot.laptop_at_home = reconciled.laptop_state.is_home
                    if reconciled.car_state:
                        snapshot.car_at_home = reconciled.car_state.is_home

            # 4. Pattern predictions from PresenceEngine
            presence_engine = self._controller._presence
            if presence_engine:
                prediction = presence_engine.predict_next_location()
                if prediction:
                    room, conf = prediction
                    snapshot.predicted_next_room = room
                    snapshot.predicted_next_room_confidence = conf

            # 5. Web presence (Jan 4, 2026)
            await self._integrate_web_presence(snapshot)

            # Determine overall state
            snapshot.state = self._determine_state(snapshot)

        except Exception as e:
            logger.error(f"Error building presence snapshot: {e}")
            self._last_error = str(e)

        return snapshot

    async def _integrate_web_presence(self, snapshot: PresenceSnapshot) -> None:
        """Integrate web presence data into snapshot.

        Args:
            snapshot: PresenceSnapshot to update
        """
        if not self._web_presence:
            return

        try:
            # Get web presence for owner (hardcoded to Tim for single-household deployment)
            owner_id = "tim"
            user_presence = self._web_presence.get_user_presence(owner_id)

            if user_presence:
                snapshot.web_presence_active = user_presence.is_present
                snapshot.web_presence_confidence = user_presence.confidence.value
                snapshot.web_active_sessions = user_presence.active_session_count
                snapshot.web_geo_hash = user_presence.primary_geo_hash

                # Boost confidence if web presence corroborates device presence
                if user_presence.is_present and snapshot.confidence < 0.8:
                    snapshot.confidence = min(1.0, snapshot.confidence + 0.2)

        except Exception as e:
            logger.debug(f"Web presence integration error: {e}")

    def _determine_state(self, snapshot: PresenceSnapshot) -> PresenceState:
        """Determine overall presence state from data."""
        if snapshot.is_home:
            return PresenceState.HOME

        if snapshot.eta_minutes and snapshot.eta_minutes < 15:
            return PresenceState.ARRIVING

        # Check if just left (within 5 minutes of state change)
        if self._state_change_time > 0:
            time_since_change = time.time() - self._state_change_time
            if time_since_change < 300 and self._previous_state == PresenceState.HOME:
                return PresenceState.LEAVING

        return PresenceState.AWAY

    def _confidence_to_float(self, confidence) -> float:
        """Convert LocationConfidence enum to float."""
        try:
            from kagami_smarthome.localization import LocationConfidence

            mapping = {
                LocationConfidence.UNKNOWN: 0.0,
                LocationConfidence.LOW: 0.25,
                LocationConfidence.MEDIUM: 0.5,
                LocationConfidence.HIGH: 0.75,
                LocationConfidence.VERIFIED: 1.0,
            }
            return mapping.get(confidence, 0.5)
        except ImportError:
            return 0.5

    def _get_presence_state_value(self, name: str):
        """Get PresenceState enum value by name."""
        try:
            from kagami_smarthome.types import PresenceState as SmartHomePresenceState

            return getattr(SmartHomePresenceState, name, None)
        except ImportError:
            return None

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def on_state_change(self, callback: PresenceCallback) -> None:
        """Register callback for presence state changes."""
        self._callbacks.append(callback)

    async def _emit_state_change(self, snapshot: PresenceSnapshot) -> None:
        """Emit state change to callbacks."""
        for callback in self._callbacks:
            try:
                await callback(snapshot)
            except Exception as e:
                logger.error(f"Presence callback error: {e}")

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get service status."""
        status = {
            "initialized": self._initialized,
            "controller_connected": self._controller is not None,
            "web_presence_connected": self._web_presence is not None,
            "last_update": datetime.fromtimestamp(self._last_update).isoformat()
            if self._last_update
            else None,
            "cache_ttl": self._cache_ttl,
            "last_error": self._last_error,
            "current_state": self._cached_snapshot.state.value
            if self._cached_snapshot
            else "unknown",
        }

        # Add web presence stats if available
        if self._web_presence:
            status["web_presence_stats"] = self._web_presence.get_stats()

        return status


# =============================================================================
# SINGLETON
# =============================================================================

_presence_service: PresenceService | None = None


def get_presence_service() -> PresenceService:
    """Get global PresenceService instance."""
    global _presence_service
    if _presence_service is None:
        _presence_service = PresenceService()
    return _presence_service


def reset_presence_service() -> None:
    """Reset the singleton (for testing)."""
    global _presence_service
    _presence_service = None


async def initialize_presence_service(
    controller: SmartHomeController | None = None,
) -> PresenceService:
    """Initialize and return the presence service.

    Args:
        controller: Optional SmartHomeController instance

    Returns:
        Initialized PresenceService
    """
    service = get_presence_service()
    await service.initialize(controller)
    return service


__all__ = [
    "PresenceCallback",
    "PresenceService",
    "PresenceSnapshot",
    "PresenceState",
    "TravelMode",
    "get_presence_service",
    "initialize_presence_service",
    "reset_presence_service",
]
