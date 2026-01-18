"""Smart Home Audio Bridge — Multi-Room Audio Routing.

⚠️  DEPRECATED FOR VOICE OUTPUT ⚠️
All voice output MUST go through UnifiedVoiceEffector for spatial audio.
This module is retained for room routing utilities only.

CANONICAL VOICE PATH:
    from kagami.core.effectors.voice import speak, VoiceTarget
    await speak("Hello", target=VoiceTarget.HOME_ROOM, rooms=["Living Room"])

AUDIO ARCHITECTURE:
1. Living Room: UnifiedSpatialEngine → 8ch PCM → Denon → Neural:X → 5.1.4 Atmos
2. Other Rooms: Control4 Airplay → Triad AMS 16x16 → Room speakers

ROOM ROUTING UTILITIES (still valid):
- Room ID mapping for Control4
- ShairBridge wake/status for multi-room streaming
- Volume and source selection helpers

Created: December 29, 2025
Updated: January 1, 2026 - Deprecated direct voice playback
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController
    from kagami_smarthome.integrations.control4 import Control4Integration

logger = logging.getLogger(__name__)


# Control4 Device IDs
CONTROL4_AIRPLAY_ID = 308  # AirPlay streaming source
TRIAD_AMS_ID = 259  # Audio matrix switch
DIGITAL_MEDIA_ID = 100002  # Streaming coordinator

# Room → Control4 ID mapping
ROOM_IDS: dict[str, int] = {
    "living room": 57,
    "kitchen": 59,
    "dining": 58,
    "entry": 55,
    "mudroom": 54,
    "garage": 53,
    "stairway": 52,
    "deck": 51,
    "porch": 50,
    "patio": 49,
    "loft": 48,
    "office": 47,
    "bed 3": 46,
    "office bathroom": 45,
    "bathroom 3": 44,
    "laundry room": 43,
    "rack room": 42,
    "gym": 41,
    "bed 4": 40,
    "game room": 39,
    "bathroom 4": 38,
    "primary bath": 37,
    "primary bed": 36,
    "primary closet": 35,
    "primary hall": 34,
    "powder room": 56,
    "family room": 60,
}

# Rooms that use Denon/HDMI (Mac default output)
DENON_ROOMS = {"living room"}

# Rooms that use Triad AMS (via Control4 Airplay)
TRIAD_ROOMS = set(ROOM_IDS.keys()) - DENON_ROOMS


@dataclass
class RoomResult:
    """Result for a single room."""

    room: str
    success: bool
    source: str = ""  # "denon" or "triad"
    latency_ms: float = 0.0
    error: str | None = None


class RoomAudioBridge:
    """Multi-room streaming TTS via Control4 and Denon.

    Supports parallel playback to multiple rooms simultaneously:
    - Living Room: Mac HDMI → Denon → KEF speakers
    - Other rooms: Control4 Airplay → Triad AMS → Room speakers
    """

    def __init__(self, controller: SmartHomeController):
        self.controller = controller
        self._initialized = False

    @property
    def _control4(self) -> Control4Integration | None:
        """Get Control4 integration."""
        return getattr(self.controller, "_control4", None)

    async def initialize(self) -> bool:
        """Initialize and verify Control4 connection."""
        if self._initialized:
            return True

        logger.info("Initializing multi-room audio bridge...")

        # Verify Control4
        c4 = self._control4
        if c4 and c4.is_connected:
            logger.info(f"Control4: {len(ROOM_IDS)} rooms, Triad AMS ready")
        else:
            logger.warning("Control4 not connected - only Living Room available")

        self._initialized = True
        logger.info("Multi-room audio ready")
        return True

    async def _select_source_for_room(
        self, room_id: int, source_id: int = CONTROL4_AIRPLAY_ID
    ) -> bool:
        """Select audio source for a room via Control4."""
        c4 = self._control4
        if not c4 or not c4.is_connected:
            return False

        try:
            result = await c4._api_post(
                f"/items/{room_id}/commands",
                {"command": "SELECT_AUDIO_DEVICE", "params": {"deviceid": source_id}},
            )
            return bool(result)
        except Exception as e:
            logger.debug(f"Source selection failed for room {room_id}: {e}")
            return False

    async def wake_shairbridge(self, rooms: list[str] | None = None) -> bool:
        """Wake ShairBridge by activating it for specified rooms.

        This is required before iPhone/iPad can see "Control4 Airplay" in AirPlay picker.
        The ShairBridge needs to be "selected" as source in at least one room to advertise
        on _airplay._tcp (AirPlay 2) rather than just _raop._tcp (AirPlay 1).

        Args:
            rooms: List of room names to activate. Defaults to ["kitchen"].

        Returns:
            True if at least one room was activated successfully.

        Note:
            After calling this, Control4 Airplay will appear in iOS AirPlay picker.
            Audio streamed via AirPlay will play through all activated rooms.
        """
        c4 = self._control4
        if not c4 or not c4.is_connected:
            logger.warning("Control4 not connected - cannot wake ShairBridge")
            return False

        target_rooms = rooms or ["kitchen"]
        success = False

        for room in target_rooms:
            room_lower = room.lower()
            if room_lower in ROOM_IDS:
                room_id = ROOM_IDS[room_lower]
                try:
                    # Select ShairBridge as source
                    result = await c4._api_post(
                        f"/items/{room_id}/commands",
                        {
                            "command": "SELECT_AUDIO_DEVICE",
                            "params": {"deviceid": CONTROL4_AIRPLAY_ID},
                        },
                    )
                    if result:
                        # Set reasonable volume
                        await c4.set_room_volume(room_id, 70)
                        await c4._api_post(f"/items/{room_id}/commands", {"command": "MUTE_OFF"})
                        logger.info(f"✅ ShairBridge activated for {room}")
                        success = True
                except Exception as e:
                    logger.debug(f"Failed to activate ShairBridge for {room}: {e}")

        if success:
            logger.info("🔊 ShairBridge is now visible in iOS AirPlay picker")

        return success

    async def get_shairbridge_status(self) -> dict[str, Any]:
        """Get current ShairBridge/AirPlay status.

        Returns:
            Dict with status info including active rooms and visibility.
        """
        import pyatv

        status = {
            "visible_in_pyatv": False,
            "visible_in_mdns": False,
            "active_rooms": [],
            "protocol": None,
        }

        # Check pyatv visibility
        try:
            atvs = await pyatv.scan(asyncio.get_event_loop(), timeout=3)
            for atv in atvs:
                if "control4" in atv.name.lower():
                    status["visible_in_pyatv"] = True
                    for svc in atv.services:
                        status["protocol"] = svc.protocol.name
                    break
        except Exception:
            pass

        # Check which rooms have ShairBridge selected
        c4 = self._control4
        if c4 and c4.is_connected:
            for room, room_id in ROOM_IDS.items():
                try:
                    state = await c4.get_room_audio_state(room_id)
                    if state.get("device_id") == CONTROL4_AIRPLAY_ID:
                        status["active_rooms"].append(room)
                except Exception:
                    pass

        return status

    async def _setup_room(
        self,
        room: str,
        room_id: int,
        volume: int,
        select_source: bool = True,
    ) -> RoomResult:
        """Configure a single room for playback."""
        c4 = self._control4
        is_denon_room = room.lower() in DENON_ROOMS
        source = "denon" if is_denon_room else "triad"

        result = RoomResult(room=room, success=False, source=source)

        if not c4 or not c4.is_connected:
            if is_denon_room:
                # Living room works via HDMI even without Control4
                result.success = True
            return result

        try:
            start = time.perf_counter()

            # For Triad rooms, select Control4 Airplay as source
            if not is_denon_room and select_source:
                await self._select_source_for_room(room_id, CONTROL4_AIRPLAY_ID)

            # Set volume and unmute
            await c4.set_room_mute(room_id, False)
            await c4.set_room_volume(room_id, volume)

            result.success = True
            result.latency_ms = (time.perf_counter() - start) * 1000

        except Exception as e:
            result.error = str(e)
            logger.debug(f"Room setup failed for {room}: {e}")

        return result

    async def _setup_rooms_parallel(
        self,
        rooms: list[str],
        volume: int,
        select_source: bool = True,
    ) -> list[RoomResult]:
        """Setup multiple rooms in parallel."""
        tasks = []
        for room in rooms:
            room_lower = room.lower()
            room_id = ROOM_IDS.get(room_lower)
            if room_id:
                tasks.append(self._setup_room(room, room_id, volume, select_source))

        if not tasks:
            return []

        return await asyncio.gather(*tasks)

    def get_available_rooms(self) -> list[str]:
        """Get available rooms."""
        return list(ROOM_IDS.keys())

    def get_denon_rooms(self) -> list[str]:
        """Get rooms that use Denon (HDMI) output."""
        return list(DENON_ROOMS)

    def get_triad_rooms(self) -> list[str]:
        """Get rooms that use Triad AMS."""
        return list(TRIAD_ROOMS)

    @property
    def is_initialized(self) -> bool:
        return self._initialized


# Singleton
_AUDIO_BRIDGE: RoomAudioBridge | None = None


async def get_audio_bridge(controller: SmartHomeController) -> RoomAudioBridge:
    """Get or create audio bridge."""
    global _AUDIO_BRIDGE
    if _AUDIO_BRIDGE is None:
        _AUDIO_BRIDGE = RoomAudioBridge(controller)
        await _AUDIO_BRIDGE.initialize()
    return _AUDIO_BRIDGE
