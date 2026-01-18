"""State Manager — Home State, Presence, Organism State.

Extracted from SmartHomeController to handle all state management.

Responsibilities:
- Home state aggregation
- Presence tracking
- Organism state (real-time cache)
- State callbacks
- Room states

Created: January 2, 2026
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.localization import DeviceLocalizer, GeofenceState
    from kagami_smarthome.presence import PresenceEngine
    from kagami_smarthome.room import Room, RoomRegistry
    from kagami_smarthome.types import HomeState, PresenceEvent

logger = logging.getLogger(__name__)


class StateManager:
    """Manages home state, presence, and organism state.

    Extracts ~500 LOC of state management from SmartHomeController.

    Usage:
        state_mgr = StateManager(presence_engine, room_registry)
        state = state_mgr.get_state()
        state_mgr.update_organism_state("lights", {"level": 50})
    """

    def __init__(
        self,
        presence: PresenceEngine,
        rooms: RoomRegistry | None = None,
        localizer: DeviceLocalizer | None = None,
    ) -> None:
        """Initialize state manager.

        Args:
            presence: Presence engine instance
            rooms: Room registry instance
            localizer: Device localizer instance
        """
        self._presence = presence
        self._rooms = rooms
        self._localizer = localizer

        # Organism state (real-time cache for unified interface)
        self._organism_state: dict[str, Any] = {
            "lights": {},
            "shades": {},
            "audio": {},
            "climate": {},
            "presence": {},
            "security": {},
            "vehicle": {},
            "health": {},
            "last_update": 0,
        }

        # Callbacks
        self._state_callbacks: list[Callable[[HomeState], None]] = []
        self._organism_callbacks: list[Callable[[dict[str, Any]], None]] = []

    def set_rooms(self, rooms: RoomRegistry) -> None:
        """Set room registry.

        Args:
            rooms: Room registry instance
        """
        self._rooms = rooms

    def set_localizer(self, localizer: DeviceLocalizer) -> None:
        """Set device localizer.

        Args:
            localizer: Device localizer instance
        """
        self._localizer = localizer

    # =========================================================================
    # Home State
    # =========================================================================

    def get_state(self) -> HomeState:
        """Get current home state.

        Returns:
            HomeState object with all state data
        """
        from kagami_smarthome.types import HomeState

        # Get presence engine's full state
        engine_state = self._presence.get_state()

        # Get occupied rooms from room states
        room_states = self.get_room_states()
        occupied = [name for name, state in room_states.items() if state.get("occupied", False)]

        # Merge with occupied rooms from room states
        if occupied:
            all_occupied = list(set(engine_state.occupied_rooms + occupied))
        else:
            all_occupied = engine_state.occupied_rooms

        return HomeState(
            presence=engine_state.presence,
            security=engine_state.security,
            activity=engine_state.activity,
            owner_room=engine_state.owner_room,
            occupied_rooms=all_occupied,
        )

    def get_home_state(self) -> HomeState:
        """Alias for get_state() for backward compatibility.

        Returns:
            HomeState object
        """
        return self.get_state()

    def get_room_states(self) -> dict[str, dict[str, Any]]:
        """Get state of all rooms.

        Returns:
            Dict of room name -> room state
        """
        if not self._rooms:
            return {}

        states: dict[str, dict[str, Any]] = {}
        for room in self._rooms.get_all():
            states[room.name] = {
                "occupied": room.state.occupied,
                "scene": getattr(room, "current_scene", None),
                "lights": getattr(room.state, "avg_light_level", None),
                "temperature": room.state.current_temp,
            }
        return states

    def _get_device_summary(self) -> dict[str, Any]:
        """Get device summary.

        Returns:
            Summary of device states
        """
        return {
            "total_devices": len(self._organism_state.get("lights", {}))
            + len(self._organism_state.get("shades", {})),
            "lights_on": sum(
                1 for l in self._organism_state.get("lights", {}).values() if l.get("level", 0) > 0
            ),
            "shades_open": sum(
                1 for s in self._organism_state.get("shades", {}).values() if s.get("level", 0) > 0
            ),
        }

    # =========================================================================
    # Room Access
    # =========================================================================

    def get_room(self, name: str) -> Room | None:
        """Get room by name.

        Args:
            name: Room name

        Returns:
            Room instance or None
        """
        if not self._rooms:
            return None
        return self._rooms.get(name)

    def get_all_rooms(self) -> list[Room]:
        """Get all rooms.

        Returns:
            List of Room instances
        """
        if not self._rooms:
            return []
        return list(self._rooms.get_all())

    def get_occupied_rooms(self) -> list[str]:
        """Get names of occupied rooms.

        Returns:
            List of room names
        """
        if not self._rooms:
            return []
        return [room.name for room in self._rooms.get_all() if room.state.occupied]

    def get_occupied_room_objects(self) -> list[Room]:
        """Get occupied Room objects.

        Returns:
            List of occupied Room instances
        """
        if not self._rooms:
            return []
        return [room for room in self._rooms.get_all() if room.state.occupied]

    # =========================================================================
    # Presence
    # =========================================================================

    def get_owner_location(self) -> str | None:
        """Get owner's current location.

        Returns:
            Room name or None
        """
        return self._presence.get_owner_location()

    def get_owner_geofence(self) -> GeofenceState:
        """Get owner's geofence state.

        Returns:
            GeofenceState enum value
        """
        return self._presence.get_geofence_state()

    def is_owner_home(self) -> bool:
        """Check if owner is home.

        Returns:
            True if owner is home
        """
        return self._presence.is_owner_home()

    def is_owner_away(self) -> bool:
        """Check if owner is away.

        Returns:
            True if owner is away
        """
        return self._presence.is_owner_away()

    def is_owner_in_room(self, room: str) -> bool:
        """Check if owner is in a specific room.

        Args:
            room: Room name

        Returns:
            True if owner is in the room
        """
        return self._presence.is_in_room(room)

    def get_owner_occupied_rooms(self) -> list[str]:
        """Get rooms occupied by owner.

        Returns:
            List of room names
        """
        return self._presence.get_occupied_rooms()

    def get_presence_state(self) -> dict[str, Any]:
        """Get full presence state.

        Returns:
            Presence state dict
        """
        return {
            "owner_location": self.get_owner_location(),
            "owner_home": self.is_owner_home(),
            "occupied_rooms": self.get_occupied_rooms(),
            "geofence": str(self.get_owner_geofence()),
        }

    # =========================================================================
    # Localization
    # =========================================================================

    def get_tracked_devices(self) -> dict[str, Any]:
        """Get tracked device information.

        Returns:
            Dict of device tracking info
        """
        if not self._localizer:
            return {}
        return self._localizer.get_tracked_devices()

    def get_localization_status(self) -> dict[str, Any]:
        """Get localization status.

        Returns:
            Localization status dict
        """
        if not self._localizer:
            return {"available": False}
        return self._localizer.get_status()

    # =========================================================================
    # Organism State (Real-time Cache)
    # =========================================================================

    def update_organism_state(self, key: str, value: Any) -> None:
        """Update organism state.

        Args:
            key: State key (e.g., 'lights', 'shades')
            value: State value
        """
        self._organism_state[key] = value
        self._organism_state["last_update"] = time.time()

        # Notify callbacks
        for callback in self._organism_callbacks:
            try:
                callback(self._organism_state)
            except Exception as e:
                logger.warning(f"Organism callback error: {e}")

    def get_organism_state(self) -> dict[str, Any]:
        """Get full organism state.

        Returns:
            Complete organism state dict
        """
        return self._organism_state.copy()

    def register_organism_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register callback for organism state changes.

        Args:
            callback: Function to call on state change
        """
        self._organism_callbacks.append(callback)

    # =========================================================================
    # State Callbacks
    # =========================================================================

    def on_state_change(self, callback: Callable[[HomeState], None]) -> None:
        """Register callback for home state changes.

        Args:
            callback: Function to call on state change
        """
        self._state_callbacks.append(callback)

    def _handle_event(self, event: PresenceEvent) -> None:
        """Handle presence event.

        Args:
            event: Presence event
        """
        # Update state and notify callbacks
        state = self.get_state()
        for callback in self._state_callbacks:
            try:
                callback(state)
            except Exception as e:
                logger.warning(f"State callback error: {e}")

    # =========================================================================
    # Recommendations
    # =========================================================================

    def get_recommendations(self) -> list[dict[str, Any]]:
        """Get Theory of Mind recommendations.

        Returns:
            List of recommendation dicts
        """
        return self._presence.get_recommendations()


__all__ = ["StateManager"]
