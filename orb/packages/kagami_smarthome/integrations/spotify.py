"""Spotify Streaming Integration — OAuth + Vorbis Decoding.

AUDIO ARCHITECTURE:
1. Living Room: Mac → ffmpeg decode → system audio → Denon AVR-A10H → KEF Reference 5.2.4
2. Other rooms: Mac → Control4 Airplay → Triad AMS 16x16 matrix

AUTHENTICATION:
    Uses OAuth flow - browser opens for Spotify authorization on first use.
    Credentials cached in ~/.kagami/spotify_credentials.json

QUALITY:
    - VERY_HIGH (320 kbps Ogg Vorbis) - Premium only
    - Decoded to 16-bit/44.1kHz stereo PCM via ffmpeg

Created: December 29, 2025
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path.home() / ".kagami" / "spotify_credentials.json"


# =============================================================================
# AUTO-INSTALL
# =============================================================================


def _ensure_librespot() -> bool:
    """Auto-install librespot-python if needed and fix protobuf compatibility."""
    import importlib.util
    import os

    # Fix protobuf version incompatibility with librespot's generated proto files
    # See: https://github.com/protocolbuffers/protobuf/issues/10051
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

    if importlib.util.find_spec("librespot") is not None:
        return True
    else:
        logger.info("🔧 Installing librespot-python...")
        try:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-q",
                    "git+https://github.com/kokarare1212/librespot-python",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except subprocess.CalledProcessError:
            logger.error("Failed to install librespot-python")
            return False


# =============================================================================
# TYPES
# =============================================================================


class PlaybackState(Enum):
    """Playback state."""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    LOADING = "loading"


class AudioOutput(Enum):
    """Audio output target."""

    SYSTEM = "system"  # Mac default output (HDMI → Denon)


@dataclass
class SpotifyTrack:
    """Track metadata."""

    uri: str = ""
    name: str = ""
    artist: str = ""
    album: str = ""
    duration_ms: int = 0


@dataclass
class SpotifyConfig:
    """Configuration."""

    device_name: str = "Kagami"


@dataclass
class SpotifyState:
    """Current state."""

    playback: PlaybackState = PlaybackState.STOPPED
    track: SpotifyTrack = field(default_factory=SpotifyTrack)
    volume: int = 100
    shuffle: bool = False
    repeat: str = "off"
    device_name: str = "Kagami"
    connected: bool = False
    username: str = ""
    last_updated: datetime = field(default_factory=datetime.now)


# =============================================================================
# SPOTIFY INTEGRATION
# =============================================================================


class SpotifyIntegration:
    """Spotify streaming via librespot-python + ffmpeg.

    Uses OAuth for authentication (browser-based).
    Decodes Vorbis via ffmpeg for proper audio playback.

    Credentials:
        - Streaming: librespot OAuth stored in ~/.kagami/spotify_credentials.json
        - Web API: Client ID/secret can be loaded from Keychain
          (spotify_client_id, spotify_client_secret, spotify_refresh_token)
    """

    def __init__(self, config: SmartHomeConfig | None = None):
        self._config = config
        self._spotify_config = SpotifyConfig()
        self._state = SpotifyState()
        self._session: Any = None

        # Web API credentials (from Keychain)
        self._client_id: str | None = None
        self._client_secret: str | None = None
        self._refresh_token: str | None = None
        self._load_credentials_from_keychain()

        # Playback control
        self._playback_process: subprocess.Popen | None = None
        self._playback_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Callbacks
        self._on_state_change: list[Callable[[SpotifyState], None]] = []

        self._initialized = False

    def _load_credentials_from_keychain(self) -> None:
        """Load Spotify Web API credentials from macOS Keychain.

        These are used for playlist/search/control via Web API.
        Streaming uses librespot with its own stored credentials.
        """
        try:
            from kagami_smarthome.secrets import secrets

            self._client_id = secrets.get("spotify_client_id")
            self._client_secret = secrets.get("spotify_client_secret")
            self._refresh_token = secrets.get("spotify_refresh_token")

            if self._client_id and self._client_secret:
                logger.debug("Spotify: Loaded Web API credentials from Keychain")
        except Exception as e:
            logger.debug(f"Spotify: Could not load from Keychain: {e}")

    def _oauth_callback(self, url: str) -> str:
        """Handle OAuth URL - open browser."""
        logger.info("🌐 Opening browser for Spotify authorization...")
        webbrowser.open(url)
        return url

    async def initialize(self) -> bool:
        """Initialize Spotify session (uses stored credentials or OAuth)."""
        if self._initialized:
            return True

        # Ensure librespot is installed
        if not _ensure_librespot():
            return False

        # Check ffmpeg
        try:
            subprocess.run(["ffplay", "-version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("Spotify: ffmpeg/ffplay not found. Install with: brew install ffmpeg")
            return False

        try:
            from librespot.core import Session

            builder = Session.Builder().set_device_name(self._spotify_config.device_name)

            # Try stored credentials first
            if CREDENTIALS_FILE.exists():
                try:
                    with open(CREDENTIALS_FILE) as f:
                        creds = json.load(f)
                    if "stored" in creds:
                        logger.info("🎵 Connecting to Spotify (stored credentials)...")
                        self._session = builder.stored(creds["stored"]).create()
                        self._state.connected = True
                        self._state.username = self._session.username()
                        self._state.device_name = self._spotify_config.device_name
                        self._initialized = True
                        logger.info(f"✅ Spotify: Connected as {self._state.username} (320kbps)")
                        return True
                except Exception as e:
                    logger.debug(f"Stored credentials failed: {e}, falling back to OAuth")

            # Fall back to OAuth (opens browser)
            logger.info("🎵 Connecting to Spotify (OAuth - browser will open)...")
            self._session = builder.oauth(self._oauth_callback).create()

            # Save credentials for next time
            try:
                CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
                stored = self._session.stored()
                if stored:
                    with open(CREDENTIALS_FILE, "w") as f:
                        json.dump({"stored": stored}, f)
                    logger.debug(f"Saved credentials to {CREDENTIALS_FILE}")
            except Exception as e:
                logger.debug(f"Could not save credentials: {e}")

            self._state.connected = True
            self._state.username = self._session.username()
            self._state.device_name = self._spotify_config.device_name
            self._initialized = True

            logger.info(f"✅ Spotify: Connected as {self._state.username} (320kbps)")
            return True

        except Exception as e:
            logger.error(f"Spotify: Connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        await self.stop()

        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

        self._state.connected = False
        self._initialized = False

    # =========================================================================
    # PLAYBACK
    # =========================================================================

    async def play_track(self, track_uri: str) -> bool:
        """Play a track by URI."""
        if not self._initialized or not self._session:
            if not await self.initialize():
                return False

        try:
            from librespot.audio.decoders import AudioQuality, VorbisOnlyAudioQuality
            from librespot.metadata import TrackId

            # Stop current playback
            await self.stop()

            # Parse track
            track_id = TrackId.from_uri(track_uri)

            # Load stream (320kbps Vorbis)
            self._state.playback = PlaybackState.LOADING
            self._state.track.uri = track_uri
            self._notify_state_change()

            playable = self._session.content_feeder().load(
                track_id, VorbisOnlyAudioQuality(AudioQuality.VERY_HIGH), False, None
            )

            # Get track metadata if available
            try:
                track_meta = playable.track
                if track_meta:
                    self._state.track.name = track_meta.name or ""
                    if track_meta.artist:
                        self._state.track.artist = ", ".join(a.name for a in track_meta.artist)
                    if track_meta.album:
                        self._state.track.album = track_meta.album.name or ""
                    self._state.track.duration_ms = track_meta.duration or 0
            except Exception:
                pass

            # Start playback thread
            self._start_playback(playable)

            logger.info(f"🎵 Spotify: Playing {self._state.track.name or track_uri}")
            return True

        except Exception as e:
            logger.error(f"Spotify: Play failed: {e}")
            self._state.playback = PlaybackState.STOPPED
            return False

    async def play_playlist(self, playlist_uri: str, shuffle: bool = True) -> bool:
        """Play a playlist by name or URI.

        Note: librespot-python doesn't support playlist playback directly.
        This method is a placeholder for Spotify Connect integration.
        For now, use play_track() with individual track URIs.

        Args:
            playlist_uri: Preset name ('focus', 'work', etc.) or Spotify playlist URI
            shuffle: Whether to shuffle (stored in state but not applied)

        Returns:
            False - playlist playback not implemented with librespot
        """
        if not self._initialized:
            if not await self.initialize():
                return False

        # Check for preset
        uri = KAGAMI_PLAYLISTS.get(playlist_uri.lower(), playlist_uri)
        uri = parse_spotify_uri(uri)

        self._state.shuffle = shuffle

        # librespot-python doesn't support playlist context playback
        # This would require Spotify Web API (spotipy) with active device
        logger.warning(
            f"🎵 Spotify: Playlist playback not implemented with librespot. "
            f"Use play_track() with individual track URIs instead. "
            f"Requested playlist: {uri}"
        )
        return False

    async def pause(self) -> bool:
        """Pause playback."""
        if self._state.playback == PlaybackState.PLAYING:
            if self._playback_process:
                # Send 'q' to ffplay to quit gracefully
                try:
                    self._playback_process.terminate()
                except Exception:
                    pass
            self._state.playback = PlaybackState.PAUSED
            self._notify_state_change()
            return True
        return False

    async def play(self) -> bool:
        """Resume playback (not supported - restart track instead)."""
        return False

    async def stop(self) -> bool:
        """Stop playback."""
        self._stop_event.set()

        if self._playback_process:
            try:
                self._playback_process.terminate()
                self._playback_process.wait(timeout=2)
            except Exception:
                try:
                    self._playback_process.kill()
                except Exception:
                    pass
            self._playback_process = None

        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=2)

        self._state.playback = PlaybackState.STOPPED
        self._stop_event.clear()
        self._notify_state_change()
        return True

    async def next_track(self) -> bool:
        """Skip to next track (not implemented)."""
        return False

    async def previous_track(self) -> bool:
        """Go to previous track (not implemented)."""
        return False

    async def set_volume(self, volume: int) -> bool:
        """Set volume (0-100)."""
        self._state.volume = max(0, min(100, volume))
        return True

    # =========================================================================
    # AUDIO PLAYBACK
    # =========================================================================

    def _start_playback(self, playable: Any) -> None:
        """Start audio playback in background thread."""

        def playback_worker():
            try:
                stream = playable.input_stream.stream()

                # Create temp file for the Vorbis stream
                temp_dir = Path(tempfile.gettempdir()) / "kagami_spotify"
                temp_dir.mkdir(exist_ok=True)
                temp_file = temp_dir / f"track_{int(time.time())}.ogg"

                # Download track to temp file
                with open(temp_file, "wb") as f:
                    while not self._stop_event.is_set():
                        chunk = stream.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)

                if self._stop_event.is_set():
                    temp_file.unlink(missing_ok=True)
                    return

                # Play with ffplay (decodes Vorbis and outputs to system audio)
                self._state.playback = PlaybackState.PLAYING
                self._notify_state_change()

                vol = self._state.volume / 100.0
                self._playback_process = subprocess.Popen(
                    [
                        "ffplay",
                        "-nodisp",  # No video display
                        "-autoexit",  # Exit when done
                        "-loglevel",
                        "quiet",
                        "-volume",
                        str(int(vol * 100)),
                        str(temp_file),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                # Wait for playback to finish
                self._playback_process.wait()

                # Cleanup
                temp_file.unlink(missing_ok=True)

                if not self._stop_event.is_set():
                    self._state.playback = PlaybackState.STOPPED
                    self._notify_state_change()

            except Exception as e:
                logger.error(f"Spotify: Playback error: {e}")
                self._state.playback = PlaybackState.STOPPED

        self._playback_thread = threading.Thread(target=playback_worker, daemon=True)
        self._playback_thread.start()

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def on_state_change(self, callback: Callable[[SpotifyState], None]) -> None:
        """Register state change callback."""
        self._on_state_change.append(callback)

    def _notify_state_change(self) -> None:
        """Notify state change."""
        self._state.last_updated = datetime.now()
        for cb in self._on_state_change:
            try:
                cb(self._state)
            except Exception:
                pass

    # =========================================================================
    # STATE
    # =========================================================================

    def get_state(self) -> dict[str, Any]:
        """Get current state."""
        return {
            "connected": self._state.connected,
            "username": self._state.username,
            "playback": self._state.playback.value,
            "track": {
                "uri": self._state.track.uri,
                "name": self._state.track.name,
                "artist": self._state.track.artist,
                "album": self._state.track.album,
                "duration_ms": self._state.track.duration_ms,
            },
            "volume": self._state.volume,
            "shuffle": self._state.shuffle,
            "device_name": self._state.device_name,
        }

    @property
    def is_playing(self) -> bool:
        return self._state.playback == PlaybackState.PLAYING

    @property
    def is_connected(self) -> bool:
        return self._state.connected

    @property
    def current_track(self) -> SpotifyTrack:
        return self._state.track


# =============================================================================
# HELPERS
# =============================================================================


def parse_spotify_uri(uri_or_url: str) -> str:
    """Parse Spotify URI from URL or URI format."""
    if uri_or_url.startswith("spotify:"):
        return uri_or_url

    if "open.spotify.com" in uri_or_url:
        parts = uri_or_url.split("/")
        for i, part in enumerate(parts):
            if part in ("track", "album", "playlist", "artist"):
                item_id = parts[i + 1].split("?")[0]
                return f"spotify:{part}:{item_id}"

    # Assume track ID (22 chars)
    if len(uri_or_url) == 22:
        return f"spotify:track:{uri_or_url}"

    return uri_or_url


# =============================================================================
# PRESET PLAYLISTS
# =============================================================================


KAGAMI_PLAYLISTS: dict[str, str] = {
    "focus": "spotify:playlist:37i9dQZF1DX4sWSpwq3LiO",
    "work": "spotify:playlist:37i9dQZF1DX0SM0LYsmbMT",
    "morning": "spotify:playlist:37i9dQZF1DX4WYpdgoIcn6",
    "evening": "spotify:playlist:37i9dQZF1DWU0ScTcjJBdj",
    "party": "spotify:playlist:37i9dQZF1DX4JAvHpjipBk",
    "relax": "spotify:playlist:37i9dQZF1DX3Ogo9pFvBkY",
    "sleep": "spotify:playlist:37i9dQZF1DWZd79rJ6a7lp",
}


__all__ = [
    "KAGAMI_PLAYLISTS",
    "AudioOutput",
    "PlaybackState",
    "SpotifyConfig",
    "SpotifyIntegration",
    "SpotifyState",
    "SpotifyTrack",
    "parse_spotify_uri",
]
