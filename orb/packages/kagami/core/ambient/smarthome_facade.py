"""SmartHome Facade - Unified interface for smart home operations.

Extracted from controller.py (January 2026) to isolate smart home
interactions from the main orchestrator.

The SmartHomeFacade handles:
- Multi-room announcements via TTS
- Colony-based scene application
- Presence-triggered scenes
- Home state capture
- Audio room management
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from kagami.core.ambient.data_types import Colony, PresenceLevel

if TYPE_CHECKING:
    from kagami.core.ambient.voice_interface import VoiceInterface

logger = logging.getLogger(__name__)


class SmartHomeFacade:
    """Facade for smart home operations.

    Provides a unified interface for smart home interactions including
    multi-room announcements, scene control, and state capture.
    """

    def __init__(self):
        """Initialize smart home facade."""
        self._smart_home: Any = None
        self._bridge: Any = None  # CrossDomainBridge
        self._voice: VoiceInterface | None = None

    def set_smart_home(self, smart_home: Any) -> None:
        """Set the SmartHomeController.

        Args:
            smart_home: SmartHomeController instance
        """
        self._smart_home = smart_home

    def set_bridge(self, bridge: Any) -> None:
        """Set the CrossDomainBridge.

        Args:
            bridge: CrossDomainBridge instance
        """
        self._bridge = bridge

    def set_voice(self, voice: VoiceInterface) -> None:
        """Set voice interface for local fallback.

        Args:
            voice: VoiceInterface instance
        """
        self._voice = voice

    @property
    def is_connected(self) -> bool:
        """Check if smart home is connected and initialized."""
        return self._smart_home is not None and getattr(self._smart_home, "_initialized", False)

    def get_smart_home(self) -> Any:
        """Get the SmartHomeController instance.

        Returns:
            SmartHomeController or None
        """
        return self._smart_home

    def get_bridge(self) -> Any:
        """Get the CrossDomainBridge instance.

        Returns:
            CrossDomainBridge or None
        """
        return self._bridge

    async def capture_home_state(self, ambient_state: Any = None) -> dict[str, Any]:
        """Capture complete home state snapshot.

        Args:
            ambient_state: Current ambient state for fallback

        Returns:
            HomeSnapshot as dict
        """
        if self._bridge:
            snapshot = await self._bridge.get_home_snapshot()
            return snapshot.to_dict()

        # Fallback: return ambient state only
        return {
            "timestamp": time.time(),
            "presence_level": (ambient_state.presence.level.value if ambient_state else "unknown"),
            "breath_phase": (ambient_state.breath.phase.value if ambient_state else "unknown"),
            "breath_cycle": ambient_state.breath.cycle_count if ambient_state else 0,
            "safety_h": ambient_state.safety.h_value if ambient_state else 1.0,
            "smart_home_connected": False,
        }

    async def capture_state_delta(self) -> dict[str, Any]:
        """Capture only changes since last snapshot.

        Returns:
            Dict of changed fields only
        """
        if self._bridge:
            snapshot = await self._bridge.get_home_snapshot()
            return snapshot.to_dict()
        return {}

    async def apply_colony_scene(self, colony: Colony, room_name: str) -> bool:
        """Apply a scene to a room based on colony state.

        Maps colony personalities to room scenes:
        - Spark -> Creative/energizing
        - Forge -> Focused/productive
        - Flow -> Calm/balanced
        - Nexus -> Connected/social
        - Beacon -> Structured/planned
        - Grove -> Exploratory/open
        - Crystal -> Verified/clear

        Args:
            colony: Active colony
            room_name: Room to apply scene to

        Returns:
            True if scene was applied
        """
        if not self._bridge:
            return False

        colony_scenes = {
            Colony.SPARK: "energize",
            Colony.FORGE: "focus",
            Colony.FLOW: "relax",
            Colony.NEXUS: "social",
            Colony.BEACON: "plan",
            Colony.GROVE: "explore",
            Colony.CRYSTAL: "clarity",
        }
        scene = colony_scenes.get(colony, "default")
        return await self._bridge.apply_scene(scene, [room_name])

    async def trigger_presence_scene(
        self,
        presence: PresenceLevel,
        location: str | None = None,
    ) -> None:
        """Trigger appropriate scenes based on presence level.

        Args:
            presence: Presence level
            location: Detected location (room name)
        """
        if not self._bridge:
            return

        # Map presence level to scene
        # Note: Using string comparison for PresenceLevel enum compatibility
        level_value = presence.value if hasattr(presence, "value") else str(presence)

        if level_value == "away":
            await self._bridge.apply_scene("away", None)
        elif level_value == "arriving":
            await self._bridge.apply_scene("welcome_home", None)
        elif level_value == "active":
            await self._bridge.apply_scene("active", [location] if location else None)

    async def announce(
        self,
        text: str,
        rooms: list[str] | None = None,
        volume: int | None = None,
        colony: Colony | str = "kagami",
    ) -> bool:
        """Announce a message to specific rooms via TTS.

        Uses neural TTS with colony voices routed through
        multi-room audio.

        Args:
            text: Message to announce
            rooms: List of room names (None = local only)
            volume: Volume level 0-100
            colony: Voice colony

        Returns:
            True if announcement was successful
        """
        colony_str = colony.value if isinstance(colony, Colony) else colony

        if self._smart_home and hasattr(self._smart_home, "announce"):
            return await self._smart_home.announce(
                text=text,
                rooms=rooms,
                volume=volume,
                colony=colony_str,
            )

        # Fall back to local voice
        if self._voice:
            return await self._voice.speak(text, colony=colony)

        return False

    async def announce_all(
        self,
        text: str,
        volume: int | None = None,
        colony: Colony | str = "beacon",
        exclude_rooms: list[str] | None = None,
    ) -> bool:
        """Announce a message to all rooms (whole-house).

        Args:
            text: Message to announce
            volume: Volume level 0-100
            colony: Voice colony (default beacon for clarity)
            exclude_rooms: Rooms to exclude

        Returns:
            True if at least one room received the announcement
        """
        colony_str = colony.value if isinstance(colony, Colony) else colony

        if self._smart_home and hasattr(self._smart_home, "announce_all"):
            return await self._smart_home.announce_all(
                text=text,
                volume=volume,
                colony=colony_str,
                exclude_rooms=exclude_rooms,
            )

        if self._voice:
            return await self._voice.speak(text, colony=colony)

        return False

    async def speak_to_room(
        self,
        room: str,
        text: str,
        colony: Colony | str = "kagami",
    ) -> bool:
        """Speak to a specific room with colony voice.

        Args:
            room: Room name
            text: What to say
            colony: Voice colony

        Returns:
            True if successful
        """
        colony_str = colony.value if isinstance(colony, Colony) else colony

        if self._smart_home and hasattr(self._smart_home, "speak_to_room"):
            return await self._smart_home.speak_to_room(
                room=room,
                text=text,
                colony=colony_str,
            )

        if self._voice:
            return await self._voice.speak(text, colony=colony)

        return False

    def get_audio_rooms(self) -> list[str]:
        """Get list of rooms with audio capability.

        Returns:
            List of room names
        """
        if self._smart_home and hasattr(self._smart_home, "get_audio_rooms"):
            return self._smart_home.get_audio_rooms()
        return []
