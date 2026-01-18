"""UnifiedVoiceEffector — THE single voice output system.

All voice output in Kagami routes through this effector:
- Desktop → Stereo speakers
- Home → Spatial audio (Denon → KEF Atmos)
- Car → Tesla cabin/external
- Glasses → Meta Ray-Ban spatial

The effector handles:
1. TTS synthesis (via KagamiVoice)
2. Target routing (where to play)
3. Spatial audio processing
4. Volume/presence management

Usage:
    from kagami.core.effectors.voice import speak, VoiceTarget

    # Auto-route (context-aware)
    await speak("Hello Tim")

    # Explicit target
    await speak("Dinner is ready", target=VoiceTarget.HOME_ALL)

    # With colony conditioning
    await speak("System ready", colony="crystal")

Architecture:
    speak(text)
    → KagamiVoice.synthesize() [TTS, no playback]
    → UnifiedVoiceEffector.route() [target selection]
    → UnifiedSpatialEngine / RoomAudioBridge / etc. [playback]

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.services.voice.kagami_voice import KagamiVoice

logger = logging.getLogger(__name__)


class VoiceTarget(str, Enum):
    """Voice output targets.

    AUTO: Context-aware routing (default)
    HOME_ROOM: Specific room(s) in the house
    HOME_ALL: All 26 audio zones
    CAR: Tesla cabin or external speaker
    GLASSES: Meta Ray-Ban spatial audio
    DESKTOP: Local stereo speakers (fallback)
    """

    AUTO = "auto"
    HOME_ROOM = "home_room"
    HOME_ALL = "home_all"
    CAR = "car"
    GLASSES = "glasses"
    DESKTOP = "desktop"


@dataclass
class VoiceEffectorResult:
    """Result of voice effector operation."""

    success: bool
    target: VoiceTarget
    target_detail: str = ""  # e.g., room name, "all zones", "cabin"
    audio_path: Path | None = None
    synthesis_ms: float = 0.0
    routing_ms: float = 0.0
    playback_ms: float = 0.0
    latency_ms: float = 0.0  # Total end-to-end
    colony: str = "kagami"
    error: str | None = None


class UnifiedVoiceEffector:
    """THE unified voice output effector.

    Single point of control for all voice output in the system.
    Routes to appropriate output based on context and explicit targeting.

    Context Awareness:
    - Checks presence (at home, in car, etc.)
    - Checks time (night mode = quieter)
    - Checks movie mode (ducking)
    - Checks occupied rooms (target active areas)

    Output Routing:
    - Living Room: 8ch PCM → Denon → Neural:X → KEF 5.1.4 Atmos
    - Other rooms: Control4/Triad distributed audio
    - Desktop: Local stereo via afplay
    - Car: Tesla voice adapter
    - Glasses: Meta Ray-Ban spatial
    """

    def __init__(self) -> None:
        """Initialize the effector."""
        self._voice: KagamiVoice | None = None
        self._initialized = False

        # Context state
        self._at_home = True
        self._in_car = False
        self._current_room: str | None = None
        self._movie_mode = False
        self._night_mode = False

        # Volume levels
        self._volume_normal = 1.0
        self._volume_night = 0.5
        self._volume_movie = 0.3

        # Stats
        self._stats = {
            "total_speaks": 0,
            "by_target": {t.value: 0 for t in VoiceTarget},
            "total_latency_ms": 0.0,
            "errors": 0,
        }

    async def initialize(self) -> bool:
        """Initialize the voice effector.

        Returns:
            True if successful
        """
        if self._initialized:
            return True

        try:
            # Initialize KagamiVoice for TTS
            from kagami.core.services.voice.kagami_voice import get_kagami_voice

            self._voice = await get_kagami_voice()

            # Update context from presence service
            await self._update_context()

            self._initialized = True
            logger.info("✓ UnifiedVoiceEffector initialized")
            return True

        except Exception as e:
            logger.error(f"VoiceEffector initialization failed: {e}")
            return False

    async def _update_context(self) -> None:
        """Update context from presence and smart home services."""
        try:
            # Try to get presence info
            try:
                from kagami.core.integrations.presence_service import get_presence_service

                presence = get_presence_service()
                snapshot = await presence.get_snapshot()
                self._at_home = snapshot.is_home
                self._current_room = snapshot.current_room
                self._in_car = snapshot.travel_mode.value == "driving"
            except (ImportError, AttributeError):
                pass

            # Try to get smart home context
            try:
                from kagami_smarthome import get_smart_home

                controller = await get_smart_home()
                state = controller.get_state()
                self._movie_mode = getattr(state, "movie_mode", False)
            except (ImportError, AttributeError):
                pass

            # Check time for night mode
            from datetime import datetime

            hour = datetime.now().hour
            self._night_mode = hour < 7 or hour >= 22

        except Exception as e:
            logger.debug(f"Context update partial: {e}")

    def _determine_target(
        self, target: VoiceTarget, rooms: list[str] | None
    ) -> tuple[VoiceTarget, str]:
        """Determine actual target based on context.

        Args:
            target: Requested target
            rooms: Optional room list

        Returns:
            Tuple of (resolved_target, detail_string)
        """
        if target != VoiceTarget.AUTO:
            # Explicit target
            if target == VoiceTarget.HOME_ROOM and rooms:
                return target, ", ".join(rooms)
            elif target == VoiceTarget.HOME_ALL:
                return target, "all zones"
            elif target == VoiceTarget.CAR:
                return target, "cabin"
            elif target == VoiceTarget.GLASSES:
                return target, "spatial"
            else:
                return target, "stereo"

        # AUTO: Context-aware routing
        if self._in_car:
            return VoiceTarget.CAR, "cabin"

        if not self._at_home:
            # Not at home, not in car → desktop or glasses
            return VoiceTarget.DESKTOP, "stereo"

        # At home
        if self._current_room:
            return VoiceTarget.HOME_ROOM, self._current_room

        # Default to all home zones
        return VoiceTarget.HOME_ALL, "all zones"

    async def speak(
        self,
        text: str,
        target: VoiceTarget = VoiceTarget.AUTO,
        rooms: list[str] | None = None,
        colony: str = "kagami",
        volume: float | None = None,
    ) -> VoiceEffectorResult:
        """Speak text through the appropriate output.

        The main entry point for all voice output in Kagami.
        ALWAYS uses ElevenLabs V3 for audio tag support.

        Args:
            text: Text to speak (can include V3 audio tags like [whispers], [excited])
            target: Output target (AUTO for context-aware)
            rooms: Specific rooms for HOME_ROOM target
            colony: Colony conditioning (kagami, spark, forge, etc.)
            volume: Optional volume override (0.0-1.0)

        Returns:
            VoiceEffectorResult with timing and status

        Example:
            from kagami.core.effectors.voice import speak

            # Context-aware
            await speak("Hello Tim")

            # Specific room
            await speak("Dinner is ready", rooms=["Kitchen"])

            # All zones announcement
            await speak("Goodnight", target=VoiceTarget.HOME_ALL)

            # With V3 audio tags
            await speak("[excited] Great news!", colony="spark")
            await speak("[whispers] Goodnight", colony="flow")
        """
        start = time.perf_counter()

        if not self._initialized:
            await self.initialize()

        if not self._voice:
            return VoiceEffectorResult(
                success=False,
                target=target,
                error="Voice not initialized",
            )

        # Update context for accurate routing
        await self._update_context()

        # Determine target
        resolved_target, target_detail = self._determine_target(target, rooms)

        try:
            # 1. Synthesize audio (TTS) — ALWAYS V3
            synth_start = time.perf_counter()

            # Import here to avoid circular imports
            from kagami.core.services.voice.kagami_voice import Colony

            colony_enum = Colony(colony.lower()) if isinstance(colony, str) else colony

            result = await self._voice.synthesize(text, colony=colony_enum)

            if not result.success:
                return VoiceEffectorResult(
                    success=False,
                    target=resolved_target,
                    target_detail=target_detail,
                    colony=colony,
                    error=result.error,
                )

            synthesis_ms = (time.perf_counter() - synth_start) * 1000

            # 2. Route to target
            route_start = time.perf_counter()

            # Determine volume
            if volume is None:
                if self._night_mode:
                    volume = self._volume_night
                elif self._movie_mode:
                    volume = self._volume_movie
                else:
                    volume = self._volume_normal

            # Route based on target
            playback_success = await self._route_audio(
                audio_path=result.audio_path,
                audio_bytes=result.audio_bytes,
                target=resolved_target,
                target_detail=target_detail,
                volume=volume,
            )

            routing_ms = (time.perf_counter() - route_start) * 1000
            total_ms = (time.perf_counter() - start) * 1000

            # Update stats
            self._stats["total_speaks"] += 1
            self._stats["by_target"][resolved_target.value] += 1
            self._stats["total_latency_ms"] += total_ms

            if not playback_success:
                self._stats["errors"] += 1

            logger.info(
                f"🔊 [{resolved_target.value}:{target_detail}] "
                f"Synth:{synthesis_ms:.0f}ms Route:{routing_ms:.0f}ms Total:{total_ms:.0f}ms"
            )

            return VoiceEffectorResult(
                success=playback_success,
                target=resolved_target,
                target_detail=target_detail,
                audio_path=result.audio_path,
                synthesis_ms=synthesis_ms,
                routing_ms=routing_ms,
                latency_ms=total_ms,
                colony=colony,
            )

        except Exception as e:
            logger.error(f"Voice effector failed: {e}")
            self._stats["errors"] += 1
            return VoiceEffectorResult(
                success=False,
                target=resolved_target,
                target_detail=target_detail,
                colony=colony,
                error=str(e),
            )

    async def _route_audio(
        self,
        audio_path: Path | None,
        audio_bytes: bytes | None,
        target: VoiceTarget,
        target_detail: str,
        volume: float,
    ) -> bool:
        """Route audio to the appropriate output.

        Args:
            audio_path: Path to audio file
            audio_bytes: Raw audio bytes
            target: Output target
            target_detail: Target details (room name, etc.)
            volume: Volume level (0.0-1.0)

        Returns:
            True if playback successful
        """
        if not audio_path and not audio_bytes:
            return False

        try:
            if target == VoiceTarget.DESKTOP:
                # Local playback via afplay
                return await self._play_desktop(audio_path, volume)

            elif target == VoiceTarget.HOME_ROOM:
                # Specific room(s) via smart home
                rooms = target_detail.split(", ") if target_detail else ["Living Room"]
                return await self._play_home_rooms(audio_path, rooms, volume)

            elif target == VoiceTarget.HOME_ALL:
                # All zones via smart home
                return await self._play_home_all(audio_path, volume)

            elif target == VoiceTarget.CAR:
                # Tesla voice adapter
                return await self._play_car(audio_path, audio_bytes, volume)

            elif target == VoiceTarget.GLASSES:
                # Meta glasses spatial audio
                return await self._play_glasses(audio_bytes, volume)

            else:
                # Fallback to desktop
                return await self._play_desktop(audio_path, volume)

        except Exception as e:
            logger.error(f"Audio routing failed: {e}")
            return False

    async def _play_desktop(self, audio_path: Path | None, volume: float) -> bool:
        """Play audio via local speakers."""
        if not audio_path:
            return False

        try:
            import subprocess

            # afplay with volume control
            cmd = ["afplay", "-v", str(volume * 2), str(audio_path)]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0

        except Exception as e:
            logger.error(f"Desktop playback failed: {e}")
            return False

    async def _play_home_rooms(
        self,
        audio_path: Path | None,
        rooms: list[str],
        volume: float,
    ) -> bool:
        """Play audio in specific home rooms via smart home."""
        if not audio_path:
            return False

        try:
            # Try spatial audio for Living Room
            if "Living Room" in rooms:
                try:
                    from kagami.core.effectors.spatial_audio import get_spatial_engine

                    engine = await get_spatial_engine()
                    if engine:
                        await engine.play_spatial(audio_path, volume=volume)
                        return True
                except ImportError:
                    pass

            # Fallback to smart home announce
            from kagami_smarthome import get_smart_home

            controller = await get_smart_home()
            # Play audio file in rooms
            await controller.play_audio(str(audio_path), rooms=rooms, volume=int(volume * 100))
            return True

        except Exception as e:
            logger.error(f"Home room playback failed: {e}")
            # Fallback to desktop
            return await self._play_desktop(audio_path, volume)

    async def _play_home_all(self, audio_path: Path | None, volume: float) -> bool:
        """Play audio in all home zones."""
        if not audio_path:
            return False

        try:
            from kagami_smarthome import get_smart_home

            controller = await get_smart_home()
            await controller.play_audio(str(audio_path), volume=int(volume * 100))
            return True

        except Exception as e:
            logger.error(f"Home all playback failed: {e}")
            return await self._play_desktop(audio_path, volume)

    async def _play_car(
        self,
        audio_path: Path | None,
        audio_bytes: bytes | None,
        volume: float,
    ) -> bool:
        """Play audio in Tesla via voice adapter."""
        try:
            from kagami_smarthome.integrations.tesla import TeslaVoiceAdapter

            adapter = TeslaVoiceAdapter()
            if audio_path:
                await adapter.play_audio(str(audio_path))
            elif audio_bytes:
                await adapter.play_audio_bytes(audio_bytes)
            return True

        except Exception as e:
            logger.warning(f"Car playback failed: {e}")
            return False

    async def _play_glasses(self, audio_bytes: bytes | None, volume: float) -> bool:
        """Play audio via Meta glasses."""
        try:
            from kagami_hal.adapters.meta_glasses import get_glasses_adapter

            adapter = await get_glasses_adapter()
            if adapter and audio_bytes:
                await adapter.play_audio(audio_bytes, volume=volume)
                return True
            return False

        except Exception as e:
            logger.warning(f"Glasses playback failed: {e}")
            return False

    async def play_audio(
        self,
        audio_path: Path | str,
        target: VoiceTarget = VoiceTarget.AUTO,
        rooms: list[str] | None = None,
        volume: float | None = None,
    ) -> VoiceEffectorResult:
        """Play pre-generated audio through the appropriate output.

        Use this when you have audio already generated (e.g., from CharacterVoice)
        and just need routing/playback.

        Args:
            audio_path: Path to audio file
            target: Output target (AUTO for context-aware)
            rooms: Specific rooms for HOME_ROOM target
            volume: Optional volume override (0.0-1.0)

        Returns:
            VoiceEffectorResult
        """
        start = time.perf_counter()

        if not self._initialized:
            await self.initialize()

        audio_path = Path(audio_path)
        if not audio_path.exists():
            return VoiceEffectorResult(
                success=False,
                target=target,
                error=f"Audio file not found: {audio_path}",
            )

        # Update context
        await self._update_context()

        # Determine target
        resolved_target, target_detail = self._determine_target(target, rooms)

        # Determine volume
        if volume is None:
            if self._night_mode:
                volume = self._volume_night
            elif self._movie_mode:
                volume = self._volume_movie
            else:
                volume = self._volume_normal

        # Read audio bytes for some targets
        audio_bytes = audio_path.read_bytes()

        # Route
        playback_success = await self._route_audio(
            audio_path=audio_path,
            audio_bytes=audio_bytes,
            target=resolved_target,
            target_detail=target_detail,
            volume=volume,
        )

        total_ms = (time.perf_counter() - start) * 1000

        # Update stats
        self._stats["total_speaks"] += 1
        self._stats["by_target"][resolved_target.value] += 1
        self._stats["total_latency_ms"] += total_ms

        if not playback_success:
            self._stats["errors"] += 1

        return VoiceEffectorResult(
            success=playback_success,
            target=resolved_target,
            target_detail=target_detail,
            audio_path=audio_path,
            routing_ms=total_ms,
            latency_ms=total_ms,
        )

    # =========================================================================
    # Context Management
    # =========================================================================

    def set_movie_mode(self, enabled: bool) -> None:
        """Set movie mode (reduces voice volume for ducking)."""
        self._movie_mode = enabled

    def set_night_mode(self, enabled: bool) -> None:
        """Set night mode (quieter output)."""
        self._night_mode = enabled

    def set_current_room(self, room: str | None) -> None:
        """Set current room for context-aware routing."""
        self._current_room = room

    def get_stats(self) -> dict[str, Any]:
        """Get effector statistics."""
        total = self._stats["total_speaks"] or 1
        return {
            **self._stats,
            "avg_latency_ms": self._stats["total_latency_ms"] / total,
            "error_rate": self._stats["errors"] / total,
            "context": {
                "at_home": self._at_home,
                "in_car": self._in_car,
                "current_room": self._current_room,
                "movie_mode": self._movie_mode,
                "night_mode": self._night_mode,
            },
            "initialized": self._initialized,
        }


# =============================================================================
# Singleton and Factory
# =============================================================================

_voice_effector: UnifiedVoiceEffector | None = None
_init_lock = asyncio.Lock()


async def get_voice_effector() -> UnifiedVoiceEffector:
    """Get the singleton UnifiedVoiceEffector.

    Returns:
        Initialized UnifiedVoiceEffector
    """
    global _voice_effector

    if _voice_effector is None:
        async with _init_lock:
            if _voice_effector is None:
                _voice_effector = UnifiedVoiceEffector()
                await _voice_effector.initialize()

    return _voice_effector


# =============================================================================
# Convenience Functions (THE FAST PATH)
# =============================================================================


async def speak(
    text: str,
    target: VoiceTarget = VoiceTarget.AUTO,
    rooms: list[str] | None = None,
    colony: str = "kagami",
    volume: float | None = None,
) -> VoiceEffectorResult:
    """Speak text through the unified voice effector.

    THE canonical entry point for voice output.
    ALWAYS uses ElevenLabs V3 for audio tag support.

    Args:
        text: Text to speak (can include V3 audio tags like [whispers], [excited])
        target: Output target (AUTO for context-aware)
        rooms: Specific rooms for HOME_ROOM target
        colony: Colony conditioning
        volume: Optional volume override (0.0-1.0)

    Returns:
        VoiceEffectorResult

    Example:
        from kagami.core.effectors.voice import speak

        # Simple
        await speak("Hello Tim")

        # With target
        await speak("Goodnight", target=VoiceTarget.HOME_ALL)

        # With rooms
        await speak("Dinner time", rooms=["Kitchen", "Living Room"])

        # With V3 audio tags
        await speak("[excited] Great news!", colony="spark")
        await speak("[whispers] Secret message", colony="flow")
    """
    effector = await get_voice_effector()
    return await effector.speak(text, target=target, rooms=rooms, colony=colony, volume=volume)


async def announce(text: str, urgent: bool = False) -> VoiceEffectorResult:
    """Make a home announcement.

    Args:
        text: Announcement text
        urgent: If True, announce in all zones at higher volume

    Returns:
        VoiceEffectorResult
    """
    target = VoiceTarget.HOME_ALL if urgent else VoiceTarget.AUTO
    colony = "beacon" if urgent else "kagami"
    return await speak(text, target=target, colony=colony)


async def whisper(text: str) -> VoiceEffectorResult:
    """Speak quietly (night mode style).

    Args:
        text: Text to speak

    Returns:
        VoiceEffectorResult
    """
    effector = await get_voice_effector()
    effector.set_night_mode(True)
    result = await effector.speak(text, colony="flow")
    effector.set_night_mode(False)
    return result


async def play_audio(
    audio_path: Path | str,
    target: VoiceTarget = VoiceTarget.AUTO,
    rooms: list[str] | None = None,
    **kwargs,
) -> VoiceEffectorResult:
    """Play pre-generated audio file through voice effector.

    Use this when you have audio already generated and just need playback.

    Args:
        audio_path: Path to audio file
        target: Output target
        rooms: Specific rooms for HOME_ROOM target
        **kwargs: Additional args passed to effector

    Returns:
        VoiceEffectorResult
    """
    effector = await get_voice_effector()
    return await effector.play_audio(audio_path, target=target, rooms=rooms, **kwargs)


__all__ = [
    "UnifiedVoiceEffector",
    "VoiceEffectorResult",
    "VoiceTarget",
    "announce",
    "get_voice_effector",
    "play_audio",
    "speak",
    "whisper",
]  # sorted
