"""AV Service — Audio, Video, and Entertainment Control.

Handles all audio/video control through multiple integrations:
- Control4/Triad AMS: Multi-room audio
- Denon AVR: Home theater receiver
- LG TV: webOS control
- Samsung TV: Tizen control
- Spotify: Music streaming

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.integrations.control4 import Control4Integration
    from kagami_smarthome.integrations.denon import DenonIntegration
    from kagami_smarthome.integrations.lg_tv import LGTVIntegration
    from kagami_smarthome.integrations.samsung_tv import SamsungTVIntegration

logger = logging.getLogger(__name__)


class AVService:
    """Service for audio/video control.

    Coordinates multiple AV integrations for unified control.

    Usage:
        av_svc = AVService(control4, denon, lg_tv, samsung_tv)
        await av_svc.set_audio(50, room="Living Room")
        await av_svc.enter_movie_mode()
    """

    def __init__(
        self,
        control4: Control4Integration | None = None,
        denon: DenonIntegration | None = None,
        lg_tv: LGTVIntegration | None = None,
        samsung_tv: SamsungTVIntegration | None = None,
        spotify: Any = None,
    ) -> None:
        """Initialize AV service."""
        self._control4 = control4
        self._denon = denon
        self._lg_tv = lg_tv
        self._samsung_tv = samsung_tv
        self._spotify = spotify
        self._movie_mode = False

    def set_integrations(
        self,
        control4: Control4Integration | None = None,
        denon: DenonIntegration | None = None,
        lg_tv: LGTVIntegration | None = None,
        samsung_tv: SamsungTVIntegration | None = None,
        spotify: Any = None,
    ) -> None:
        """Update integrations."""
        if control4:
            self._control4 = control4
        if denon:
            self._denon = denon
        if lg_tv:
            self._lg_tv = lg_tv
        if samsung_tv:
            self._samsung_tv = samsung_tv
        if spotify:
            self._spotify = spotify

    # =========================================================================
    # Audio Control
    # =========================================================================

    async def set_audio(
        self,
        volume: int,
        room: str | None = None,
        source: str | None = None,
        use_home_theater: bool = False,
    ) -> bool:
        """Set audio volume.

        Args:
            volume: Volume level (0-100)
            room: Optional room name
            source: Optional source input
            use_home_theater: Use Denon instead of Control4

        Returns:
            True if successful
        """
        results: list[bool] = []

        if use_home_theater and self._denon:
            await self._denon.power_on("Main")
            results.append(await self._denon.set_volume(volume, "Main"))
            if source:
                results.append(await self._denon.set_source(source, "Main"))
        elif self._control4:
            if room:
                results.append(
                    await self._control4.set_room_audio(
                        room, volume, int(source) if source else None
                    )
                )
            else:
                for room_id in self._control4.get_audio_zones():
                    results.append(await self._control4.set_room_volume(room_id, volume))

        return any(results)

    async def mute_room(self, room: str, mute: bool = True) -> bool:
        """Mute/unmute room audio."""
        if not self._control4:
            return False
        for room_id, zone in self._control4.get_audio_zones().items():
            if room.lower() in zone["name"].lower():
                return await self._control4.set_room_mute(room_id, mute)
        return False

    def get_audio_rooms(self) -> list[str]:
        """Get list of audio-capable rooms."""
        if not self._control4:
            return []
        zones = self._control4.get_audio_zones()
        return [zone.get("name", f"Zone {zid}") for zid, zone in zones.items()]

    # =========================================================================
    # TV Control (LG)
    # =========================================================================

    async def tv_on(self) -> bool:
        """Turn LG TV on."""
        if self._lg_tv:
            return await self._lg_tv.power_on()
        return False

    async def tv_off(self) -> bool:
        """Turn LG TV off."""
        if self._lg_tv:
            return await self._lg_tv.power_off()
        return False

    async def tv_volume(self, level: int) -> bool:
        """Set LG TV volume."""
        if self._lg_tv:
            return await self._lg_tv.set_volume(level)
        return False

    async def tv_launch_app(self, app: str) -> bool:
        """Launch app on LG TV."""
        if self._lg_tv:
            app_map = {
                "netflix": "netflix",
                "youtube": "youtube.leanback.v4",
                "prime": "amazon",
                "hulu": "hulu",
                "disney": "com.disney.disneyplus-prod",
                "apple": "com.apple.appletv",
                "plex": "cdp-30",
            }
            app_id = app_map.get(app.lower(), app)
            return await self._lg_tv.launch_app(app_id)
        return False

    async def tv_notification(self, message: str) -> bool:
        """Show notification on LG TV."""
        if self._lg_tv:
            return await self._lg_tv.show_notification(message)
        return False

    # =========================================================================
    # Samsung TV Control
    # =========================================================================

    async def samsung_tv_on(self) -> bool:
        """Turn Samsung TV on."""
        if self._samsung_tv:
            return await self._samsung_tv.power_on()
        return False

    async def samsung_tv_off(self) -> bool:
        """Turn Samsung TV off."""
        if self._samsung_tv:
            return await self._samsung_tv.power_off()
        return False

    async def samsung_tv_launch_app(self, app_name: str) -> bool:
        """Launch app on Samsung TV."""
        if self._samsung_tv:
            return await self._samsung_tv.launch_app(app_name)
        return False

    async def samsung_tv_art_mode(self, enable: bool = True) -> bool:
        """Toggle Samsung Frame TV art mode."""
        if self._samsung_tv:
            if enable:
                return await self._samsung_tv.art_mode_on()
            else:
                return await self._samsung_tv.art_mode_off()
        return False

    # =========================================================================
    # Home Theater / Movie Mode
    # =========================================================================

    async def enter_movie_mode(self) -> None:
        """Enter movie mode - coordinate all AV for theater experience."""
        self._movie_mode = True

        # Power on Denon
        if self._denon:
            await self._denon.power_on("Main")
            await self._denon.set_source("TV", "Main")

        # Power on LG TV
        if self._lg_tv:
            await self._lg_tv.power_on()

        logger.info("🎬 Movie mode activated")

    async def exit_movie_mode(self) -> None:
        """Exit movie mode."""
        self._movie_mode = False

        if self._denon:
            await self._denon.power_off("Main")

        logger.info("🎬 Movie mode deactivated")

    def is_movie_mode(self) -> bool:
        """Check if in movie mode."""
        return self._movie_mode

    # =========================================================================
    # Spotify Control
    # =========================================================================

    async def spotify_play_track(self, track_uri: str) -> bool:
        """Play Spotify track."""
        if not self._spotify:
            return False
        return await self._spotify.play_track(track_uri)

    async def spotify_play_playlist(
        self,
        playlist_name: str | None = None,
        playlist_uri: str | None = None,
        shuffle: bool = True,
    ) -> bool:
        """Play Spotify playlist."""
        if not self._spotify:
            return False

        # Preset playlists
        presets = {
            "focus": "spotify:playlist:37i9dQZF1DWZeKCadgRdKQ",
            "work": "spotify:playlist:37i9dQZF1DX5trt9i14X7j",
            "morning": "spotify:playlist:37i9dQZF1DX4sWSpwq3LiO",
            "evening": "spotify:playlist:37i9dQZF1DX6VdMW310YC7",
            "sleep": "spotify:playlist:37i9dQZF1DWZd79rJ6a7lp",
            "party": "spotify:playlist:37i9dQZF1DX0IlCGIUGBsA",
            "chill": "spotify:playlist:37i9dQZF1DX4WYpdgoIcn6",
            "cooking": "spotify:playlist:37i9dQZF1DX0SM0LYsmbMT",
        }

        uri = playlist_uri or presets.get(playlist_name.lower() if playlist_name else "", "")
        if not uri:
            return False

        if shuffle:
            await self._spotify.set_shuffle(True)
        return await self._spotify.play_context(uri)

    async def spotify_pause(self) -> bool:
        """Pause Spotify playback."""
        if not self._spotify:
            return False
        return await self._spotify.pause()

    async def spotify_next(self) -> bool:
        """Skip to next track."""
        if not self._spotify:
            return False
        return await self._spotify.next_track()

    async def spotify_previous(self) -> bool:
        """Go to previous track."""
        if not self._spotify:
            return False
        return await self._spotify.previous_track()

    async def spotify_set_volume(self, volume: int) -> bool:
        """Set Spotify volume."""
        if not self._spotify:
            return False
        return await self._spotify.set_volume(volume)

    def get_spotify_state(self) -> dict[str, Any] | None:
        """Get current Spotify playback state."""
        if not self._spotify:
            return None
        return self._spotify.get_playback_state()


__all__ = ["AVService"]
