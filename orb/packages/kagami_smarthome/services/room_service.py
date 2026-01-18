"""Room Service — Room-Centric Operations.

Handles room-based operations:
- Room lookup and listing
- Room scenes
- Enter/leave room
- Announcements via audio bridge

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.orchestrator import RoomOrchestrator
    from kagami_smarthome.room import Room, RoomRegistry

logger = logging.getLogger(__name__)


class RoomService:
    """Service for room-centric operations.

    Usage:
        room_svc = RoomService(rooms, orchestrator, audio_bridge)
        room = room_svc.get_room("Living Room")
        await room_svc.announce("Hello", rooms=["Kitchen"])
    """

    def __init__(
        self,
        rooms: RoomRegistry | None = None,
        orchestrator: RoomOrchestrator | None = None,
        audio_bridge: Any = None,
    ) -> None:
        """Initialize room service."""
        self._rooms = rooms
        self._orchestrator = orchestrator
        self._audio_bridge = audio_bridge

    def set_integrations(
        self,
        rooms: RoomRegistry | None = None,
        orchestrator: RoomOrchestrator | None = None,
        audio_bridge: Any = None,
    ) -> None:
        """Set or update room integrations."""
        if rooms is not None:
            self._rooms = rooms
        if orchestrator is not None:
            self._orchestrator = orchestrator
        if audio_bridge is not None:
            self._audio_bridge = audio_bridge

    # =========================================================================
    # Room Lookup
    # =========================================================================

    def get_room(self, name: str) -> Room | None:
        """Get a room by name."""
        if not self._rooms:
            return None
        return self._rooms.get_by_name(name)

    def get_all_rooms(self) -> list[Room]:
        """Get all rooms."""
        if not self._rooms:
            return []
        return self._rooms.get_all()

    def get_occupied_room_objects(self) -> list[Room]:
        """Get all currently occupied Room objects."""
        if not self._rooms:
            return []
        return self._rooms.get_occupied()

    def get_room_states(self) -> dict[str, dict[str, Any]]:
        """Get state summary for all rooms."""
        if self._orchestrator:
            return self._orchestrator.get_all_states()
        return {}

    # =========================================================================
    # Room Scene Control
    # =========================================================================

    async def set_room_scene(self, room_name: str, scene_name: str) -> bool:
        """Apply a scene to a room."""
        if not self._rooms or not self._orchestrator:
            return False

        room = self._rooms.get_by_name(room_name)
        if not room:
            logger.warning(f"Room not found: {room_name}")
            return False

        return await self._orchestrator.set_room_scene(room, scene_name)

    async def enter_room(self, room_name: str, activity: str = "unknown") -> None:
        """Handle entering a room with an activity."""
        if not self._rooms or not self._orchestrator:
            return

        room = self._rooms.get_by_name(room_name)
        if not room:
            return

        # Import ActivityContext lazily
        from kagami_smarthome.room import ActivityContext

        try:
            act = ActivityContext(activity)
        except ValueError:
            act = ActivityContext.UNKNOWN

        await self._orchestrator.enter_room(room, act)

    async def leave_room(self, room_name: str) -> None:
        """Handle leaving a room."""
        if not self._rooms or not self._orchestrator:
            return

        room = self._rooms.get_by_name(room_name)
        if not room:
            return

        await self._orchestrator.leave_room(room)

    # =========================================================================
    # Announcements
    # =========================================================================

    async def announce(
        self,
        text: str,
        rooms: list[str] | None = None,
        volume: int | None = None,
        colony: str = "kagami",
    ) -> bool:
        """Announce a message to specific rooms via Parler-TTS."""
        if not self._audio_bridge:
            logger.warning("Audio bridge not initialized")
            return False

        success, _ = await self._audio_bridge.announce(
            text=text,
            rooms=rooms,
            volume=volume,
            colony=colony,
        )
        return success

    async def announce_all(
        self,
        text: str,
        volume: int | None = None,
        colony: str = "beacon",
        exclude_rooms: list[str] | None = None,
    ) -> bool:
        """Announce a message to all rooms (whole-house)."""
        if not self._audio_bridge:
            return False

        success, _ = await self._audio_bridge.announce_all(
            text=text,
            volume=volume,
            colony=colony,
            exclude_rooms=exclude_rooms,
        )
        return success

    async def speak_to_room(
        self,
        room: str,
        text: str,
        colony: str = "kagami",
    ) -> bool:
        """Speak to a specific room with colony voice."""
        if not self._audio_bridge:
            return False

        success, _ = await self._audio_bridge.speak_to_room(
            room=room,
            text=text,
            colony=colony,
        )
        return success

    def get_audio_rooms(self) -> list[str]:
        """Get list of rooms with audio capability."""
        if self._audio_bridge:
            return self._audio_bridge.get_available_rooms()
        return []


__all__ = ["RoomService"]
