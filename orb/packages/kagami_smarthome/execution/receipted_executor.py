"""Receipted Executor — All physical actions flow through here.

This is the Markov Blanket for SmartHome actions. Every action:
1. Emits a start receipt
2. Executes via the appropriate integration
3. Emits a complete or error receipt

NO EXCEPTIONS. Every action is auditable.

Created: December 31, 2025
h(x) >= 0 always.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)

# Global executor instance
_executor: ReceiptedExecutor | None = None


@dataclass
class Action:
    """An action to execute."""

    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result of an action execution."""

    success: bool
    action_type: str
    params: dict[str, Any]
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "action_type": self.action_type,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "correlation_id": self.correlation_id,
        }


class ReceiptedExecutor:
    """All physical actions flow through here. No exceptions.

    This is the single point of truth for all SmartHome actions.
    Every action emits receipts for full auditability.

    Usage:
        executor = ReceiptedExecutor(controller)
        result = await executor.execute("set_lights", {"level": 50, "rooms": ["Living Room"]})
    """

    def __init__(self, controller: SmartHomeController | None = None):
        """Initialize executor with controller reference."""
        self._controller = controller
        self._action_count = 0
        self._error_count = 0
        self._total_duration_ms = 0.0

    def set_controller(self, controller: SmartHomeController) -> None:
        """Set or update controller reference."""
        self._controller = controller

    async def execute(
        self,
        action: str,
        params: dict[str, Any],
        routine_id: str | None = None,
        correlation_id: str | None = None,
    ) -> ActionResult:
        """Execute an action with full receipt trail.

        Args:
            action: Action type (e.g., "set_lights", "announce", "lock_all")
            params: Action parameters
            routine_id: Optional routine ID for correlation
            correlation_id: Optional correlation ID (auto-generated if not provided)

        Returns:
            ActionResult with success/failure and details
        """
        # Generate correlation ID if not provided
        cid = correlation_id or self._generate_correlation_id(action)

        # Emit start receipt
        self._emit_receipt(
            cid,
            f"smarthome.{action}.start",
            event_data={"params": params, "routine_id": routine_id},
        )

        start_time = time.monotonic()

        try:
            # Dispatch to appropriate handler
            result = await self._dispatch(action, params)

            duration_ms = (time.monotonic() - start_time) * 1000
            self._action_count += 1
            self._total_duration_ms += duration_ms

            # Emit success receipt
            self._emit_receipt(
                cid,
                f"smarthome.{action}.complete",
                status="success",
                event_data={
                    "result": result if not isinstance(result, bool) else {"success": result},
                    "duration_ms": duration_ms,
                    "routine_id": routine_id,
                },
            )

            return ActionResult(
                success=True,
                action_type=action,
                params=params,
                result=result,
                duration_ms=duration_ms,
                correlation_id=cid,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._error_count += 1

            logger.error(f"Action {action} failed: {e}")

            # Emit error receipt
            self._emit_receipt(
                cid,
                f"smarthome.{action}.error",
                status="error",
                event_data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                    "routine_id": routine_id,
                },
            )

            return ActionResult(
                success=False,
                action_type=action,
                params=params,
                error=str(e),
                duration_ms=duration_ms,
                correlation_id=cid,
            )

    async def _dispatch(self, action: str, params: dict[str, Any]) -> Any:
        """Dispatch action to appropriate integration.

        This is where we route actions to the correct controller method.
        """
        if not self._controller:
            raise RuntimeError("Controller not initialized")

        # Action dispatch table
        dispatch_table: dict[str, Any] = {
            # Lights
            "set_lights": self._controller.set_lights,
            "set_light_level": self._controller.set_light_level,
            # Shades
            "open_shades": self._controller.open_shades,
            "close_shades": self._controller.close_shades,
            "set_shades": self._controller.set_shades,
            # TV Mount
            "lower_tv": self._controller.lower_tv,
            "raise_tv": self._controller.raise_tv,
            # Fireplace
            "fireplace_on": self._controller.fireplace_on,
            "fireplace_off": self._controller.fireplace_off,
            # Locks
            "lock_all": self._controller.lock_all,
            "unlock_door": self._controller.unlock_door,
            # Audio
            "announce": self._controller.announce,
            "announce_all": self._controller.announce_all,
            # Climate
            "set_room_temp": self._controller.set_room_temp,
            "set_room_hvac_mode": self._controller.set_room_hvac_mode,
            # Spotify
            "spotify_play_playlist": self._controller.spotify_play_playlist,
            "spotify_pause": self._controller.spotify_pause,
            "spotify_next": self._controller.spotify_next,
            # Security
            "arm_security": self._controller.arm_security,
            "disarm_security": self._controller.disarm_security,
            # Oelo Outdoor Lights
            "oelo_on": self._oelo_on,
            "oelo_off": self._oelo_off,
            "oelo_set_pattern": self._oelo_set_pattern,
            "oelo_set_color": self._oelo_set_color,
            # Outdoor Music
            "outdoor_music": self._outdoor_music_play,
            "outdoor_music_stop": self._outdoor_music_stop,
            # Adaptive Music-Reactive Lights (Spectrum Engine)
            "start_adaptive_lights": self._start_adaptive_lights,
            "stop_adaptive_lights": self._stop_adaptive_lights,
            # Orchestral Playback with Lights (LIGHT IS MUSIC IS SPECTRUM)
            "play_orchestral": self._play_orchestral,
            "stop_orchestral": self._stop_orchestral,
            # USB Drive / Media Archive Management
            "scan_usb_drives": self._scan_usb_drives,
            "start_usb_watcher": self._start_usb_watcher,
            "stop_usb_watcher": self._stop_usb_watcher,
            "get_family_archive": self._get_family_archive,
        }

        handler = dispatch_table.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")

        # Call handler with params
        return await handler(**params)

    # =========================================================================
    # Oelo Outdoor Lighting Handlers
    # =========================================================================

    async def _oelo_on(self) -> bool:
        """Turn Oelo outdoor lights on."""
        oelo_svc = getattr(self._controller, "_oelo_service", None)
        if oelo_svc and oelo_svc.is_available:
            return await oelo_svc.outdoor_lights_on()
        logger.warning("Oelo service not available")
        return False

    async def _oelo_off(self) -> bool:
        """Turn Oelo outdoor lights off."""
        oelo_svc = getattr(self._controller, "_oelo_service", None)
        if oelo_svc and oelo_svc.is_available:
            return await oelo_svc.outdoor_lights_off()
        logger.warning("Oelo service not available")
        return False

    async def _oelo_set_pattern(
        self,
        pattern: str,
        zone: int | None = None,
        speed_override: int | None = None,
    ) -> bool:
        """Set Oelo outdoor lights to a pattern."""
        oelo_svc = getattr(self._controller, "_oelo_service", None)
        if oelo_svc and oelo_svc.is_available:
            return await oelo_svc.outdoor_lights_pattern(pattern, zone, speed_override)
        logger.warning("Oelo service not available")
        return False

    async def _oelo_set_color(self, color: str) -> bool:
        """Set Oelo outdoor lights to a color."""
        oelo_svc = getattr(self._controller, "_oelo_service", None)
        if oelo_svc and oelo_svc.is_available:
            return await oelo_svc.outdoor_lights_color(color)
        logger.warning("Oelo service not available")
        return False

    # =========================================================================
    # Outdoor Music Handlers
    # =========================================================================

    async def _outdoor_music_play(
        self,
        playlist_uri: str,
        zones: list[str] | None = None,
        volume: int = 50,
        shuffle: bool = True,
    ) -> bool:
        """Play music on outdoor audio zones.

        Args:
            playlist_uri: Spotify playlist URI
            zones: Outdoor zones (deck, porch, patio)
            volume: Volume level (0-100)
            shuffle: Enable shuffle

        Returns:
            True if music started
        """
        target_zones = zones or ["deck", "porch", "patio"]

        # Set audio source and volume for outdoor zones via Control4
        control4 = getattr(self._controller, "_control4", None)
        if control4:
            from kagami_smarthome.audio_bridge import CONTROL4_AIRPLAY_ID, ROOM_IDS

            for zone in target_zones:
                zone_lower = zone.lower()
                if zone_lower in ROOM_IDS:
                    room_id = ROOM_IDS[zone_lower]
                    try:
                        # Select Spotify/AirPlay source
                        await control4._api_post(
                            f"/items/{room_id}/commands",
                            {
                                "command": "SELECT_AUDIO_DEVICE",
                                "params": {"deviceid": CONTROL4_AIRPLAY_ID},
                            },
                        )
                        # Set volume
                        await control4.set_room_volume(room_id, volume)
                        await control4.set_room_mute(room_id, False)
                    except Exception as e:
                        logger.debug(f"Failed to setup outdoor zone {zone}: {e}")

        # Start Spotify playback
        av_svc = getattr(self._controller, "_av_service", None)
        if av_svc:
            try:
                if shuffle:
                    spotify = getattr(av_svc, "_spotify", None)
                    if spotify:
                        await spotify.set_shuffle(True)
                return (
                    await av_svc._spotify.play_context(playlist_uri) if av_svc._spotify else False
                )
            except Exception as e:
                logger.debug(f"Failed to start Spotify: {e}")
                return False

        return False

    async def _outdoor_music_stop(self, zones: list[str] | None = None) -> bool:
        """Stop music on outdoor audio zones.

        Args:
            zones: Outdoor zones to stop

        Returns:
            True if stopped
        """
        target_zones = zones or ["deck", "porch", "patio"]

        # Mute outdoor zones via Control4
        control4 = getattr(self._controller, "_control4", None)
        if control4:
            from kagami_smarthome.audio_bridge import ROOM_IDS

            for zone in target_zones:
                zone_lower = zone.lower()
                if zone_lower in ROOM_IDS:
                    room_id = ROOM_IDS[zone_lower]
                    try:
                        await control4.set_room_mute(room_id, True)
                    except Exception as e:
                        logger.debug(f"Failed to mute outdoor zone {zone}: {e}")

        # Pause Spotify
        av_svc = getattr(self._controller, "_av_service", None)
        if av_svc and av_svc._spotify:
            try:
                await av_svc._spotify.pause()
            except Exception:
                pass

        return True

    # =========================================================================
    # Adaptive Music-Reactive Lights (Spectrum Engine)
    # =========================================================================

    async def _start_adaptive_lights(
        self,
        update_rate_ms: int = 250,
        transition_smoothing: float = 0.3,
        max_brightness: float = 1.0,
        max_pattern_speed: int = 15,
    ) -> bool:
        """Start the adaptive music-reactive light controller.

        LIGHT IS MUSIC IS SPECTRUM.

        Uses the SpectrumEngine to map real-time music to Oelo lights.

        Args:
            update_rate_ms: Update frequency (default 4 Hz)
            transition_smoothing: Smooth transitions (0-1)
            max_brightness: Maximum brightness (0-1)
            max_pattern_speed: Max Oelo pattern speed (1-20)

        Returns:
            True if started successfully
        """
        try:
            from kagami_smarthome.spectrum.adaptive_lights import (
                AdaptiveLightConfig,
                get_adaptive_lights,
            )

            config = AdaptiveLightConfig(
                update_interval_ms=update_rate_ms,
                transition_smoothing=transition_smoothing,
                max_brightness=max_brightness,
                max_pattern_speed=max_pattern_speed,
            )

            controller = await get_adaptive_lights(self._controller, config)
            return await controller.start()

        except Exception as e:
            logger.error(f"Failed to start adaptive lights: {e}")
            return False

    async def _stop_adaptive_lights(self) -> bool:
        """Stop the adaptive music-reactive light controller."""
        try:
            from kagami_smarthome.spectrum.adaptive_lights import get_adaptive_lights

            controller = await get_adaptive_lights(self._controller)
            await controller.stop()
            return True

        except Exception as e:
            logger.debug(f"Failed to stop adaptive lights: {e}")
            return False

    # =========================================================================
    # Orchestral Playback with Lights (LIGHT IS MUSIC IS SPECTRUM)
    # =========================================================================

    async def _play_orchestral(
        self,
        source: str,
        tempo_bpm: float = 90,
        key: str = "C",
        mode: str = "major",
        mood: str = "neutral",
        spatial: bool = True,
        trajectory: str = "orbit",
        expression_style: str = "virtuoso",
    ) -> dict[str, Any]:
        """Play orchestral audio/MIDI with synchronized lights.

        LIGHT IS MUSIC IS SPECTRUM.

        Uses BBC Symphony Orchestra renderer for MIDI, spatial audio
        through Denon 5.1.4, and real-time spectrum-synchronized lights.

        Args:
            source: Path to MIDI (.mid) or audio (.wav/.flac) file
            tempo_bpm: Tempo for light timing (auto-detected for MIDI)
            key: Musical key (auto-detected for MIDI)
            mode: Mode (major/minor, auto-detected for MIDI)
            mood: Musical mood (peaceful, gentle, neutral, energetic, dramatic, intense)
            spatial: Enable 5.1.4 spatial audio via Denon
            trajectory: Spatial trajectory (corkscrew, orbit, voice, static)
            expression_style: BBC SO expression (virtuoso, romantic, modern, baroque)

        Returns:
            Playback statistics
        """
        try:
            from kagami_smarthome.spectrum.engine import MusicMood
            from kagami_smarthome.spectrum.orchestral import (
                OrchestralPlaybackConfig,
                OrchestralPlaybackController,
            )

            # Map mood string to enum
            mood_map = {
                "peaceful": MusicMood.PEACEFUL,
                "gentle": MusicMood.GENTLE,
                "neutral": MusicMood.NEUTRAL,
                "energetic": MusicMood.ENERGETIC,
                "dramatic": MusicMood.DRAMATIC,
                "intense": MusicMood.INTENSE,
            }
            mood_enum = mood_map.get(mood.lower(), MusicMood.NEUTRAL)

            config = OrchestralPlaybackConfig(
                enable_spatial=spatial,
                trajectory=trajectory,
                expression_style=expression_style,
            )

            controller = OrchestralPlaybackController(self._controller, config)

            # Route based on file type
            from pathlib import Path

            source_path = Path(source)
            if source_path.suffix.lower() in (".mid", ".midi"):
                return await controller.play_midi(
                    source_path,
                    expression_style=expression_style,
                )
            else:
                return await controller.play_audio(
                    source_path,
                    tempo_bpm=tempo_bpm,
                    key=key,
                    mode=mode,
                    mood=mood_enum,
                    trajectory=trajectory,
                )

        except Exception as e:
            logger.error(f"Orchestral playback failed: {e}")
            return {"success": False, "error": str(e)}

    async def _stop_orchestral(self) -> bool:
        """Stop orchestral playback."""
        try:
            from kagami_smarthome.spectrum.orchestral import stop_orchestral

            stop_orchestral()
            return True

        except Exception as e:
            logger.debug(f"Failed to stop orchestral: {e}")
            return False

    # =========================================================================
    # USB Drive / Media Archive Management
    # =========================================================================

    async def _scan_usb_drives(self) -> list[dict[str, Any]]:
        """Scan for currently mounted USB drives.

        Returns info about all detected USB drives including:
        - Drive name and mount path
        - Media content counts (video, audio, images)
        - Whether profile data exists (family_profiles.json)
        - Family name and character count if profile exists

        Returns:
            List of drive info dictionaries
        """
        try:
            from kagami.core.services.usb_watcher import scan_current_drives

            drives = await scan_current_drives()
            return [d.to_dict() for d in drives]

        except Exception as e:
            logger.error(f"USB scan failed: {e}")
            return []

    async def _start_usb_watcher(self) -> bool:
        """Start the USB drive watcher service.

        Monitors for USB drive mount/unmount events and automatically:
        - Analyzes new drives for media content
        - Loads family profiles from recognized archive drives
        - Registers drives with MediaStorageService

        Returns:
            True if started successfully
        """
        try:
            from kagami.core.services.usb_watcher import start_usb_watcher

            watcher = await start_usb_watcher()

            # Set up callbacks to log events
            def on_mount(info: Any) -> None:
                logger.info(f"USB mounted: {info.name} ({info.drive_type.value})")

            def on_unmount(path: str) -> None:
                logger.info(f"USB unmounted: {path}")

            watcher.on_mount = on_mount
            watcher.on_unmount = on_unmount

            return True

        except Exception as e:
            logger.error(f"Failed to start USB watcher: {e}")
            return False

    async def _stop_usb_watcher(self) -> bool:
        """Stop the USB drive watcher service."""
        try:
            from kagami.core.services.usb_watcher import get_usb_watcher

            watcher = get_usb_watcher()
            await watcher.stop()
            return True

        except Exception as e:
            logger.debug(f"Failed to stop USB watcher: {e}")
            return False

    async def _get_family_archive(
        self,
        drive_name: str | None = None,
    ) -> dict[str, Any]:
        """Get family archive data from USB drive.

        Args:
            drive_name: Specific drive to query (default: first media archive found)

        Returns:
            Family archive info including characters, videos, and metadata
        """
        try:
            from kagami.core.services.media_storage import get_media_storage

            storage = get_media_storage()
            if not storage._initialized:
                await storage.initialize()

            # Find the target drive
            if drive_name:
                drive = storage.get_drive(drive_name)
                if not drive:
                    return {"success": False, "error": f"Drive not found: {drive_name}"}
            else:
                # Find first USB media archive
                for name, config in storage._drives.items():
                    if config.storage_type.value == "usb_drive":
                        drive_name = name
                        break

                if not drive_name:
                    return {"success": False, "error": "No USB media drive found"}

            # Get family characters
            characters = storage.get_family_characters()

            # Get video info if scene database exists
            scene_db = await storage.get_scene_database(drive_name)

            return {
                "success": True,
                "drive_name": drive_name,
                "character_count": len(characters),
                "characters": [c.to_dict() for c in characters],
                "scene_database": scene_db,
            }

        except Exception as e:
            logger.error(f"Failed to get family archive: {e}")
            return {"success": False, "error": str(e)}

    def _generate_correlation_id(self, action: str) -> str:
        """Generate a correlation ID for the action."""
        try:
            from kagami.core.receipts.facade import URF

            return URF.generate_correlation_id(prefix=f"sh_{action}")
        except ImportError:
            import uuid

            return f"sh_{action}_{uuid.uuid4().hex[:8]}"

    def _emit_receipt(
        self,
        correlation_id: str,
        event_name: str,
        status: str = "success",
        event_data: dict[str, Any] | None = None,
    ) -> None:
        """Emit receipt for action."""
        try:
            from kagami.core.receipts.facade import emit_receipt

            emit_receipt(
                correlation_id,
                event_name,
                status=status,
                event_data=event_data or {},
            )
        except ImportError:
            # Receipt system not available - log instead
            logger.debug(f"Receipt: {event_name} [{status}] - {event_data}")

    def get_stats(self) -> dict[str, Any]:
        """Get executor statistics."""
        return {
            "action_count": self._action_count,
            "error_count": self._error_count,
            "success_rate": (
                (self._action_count - self._error_count) / self._action_count
                if self._action_count > 0
                else 1.0
            ),
            "total_duration_ms": self._total_duration_ms,
            "avg_duration_ms": (
                self._total_duration_ms / self._action_count if self._action_count > 0 else 0.0
            ),
        }


def get_executor(controller: SmartHomeController | None = None) -> ReceiptedExecutor:
    """Get or create global executor instance."""
    global _executor
    if _executor is None:
        _executor = ReceiptedExecutor(controller)
    elif controller is not None:
        _executor.set_controller(controller)
    return _executor


__all__ = [
    "Action",
    "ActionResult",
    "ReceiptedExecutor",
    "get_executor",
]
