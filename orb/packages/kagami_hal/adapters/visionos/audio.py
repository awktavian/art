"""visionOS Spatial Audio Adapter.

Provides spatial audio capabilities for Apple Vision Pro.

Supports:
- Spatial audio positioning
- Head tracking for audio
- Ambient sound integration

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from kagami.core.boot_mode import is_test_mode

from kagami_hal.audio_controller import AudioController
from kagami_hal.data_types import AudioConfig, AudioFormat

logger = logging.getLogger(__name__)


class SpatialAudioMode(Enum):
    """Spatial audio rendering mode."""

    STEREO = "stereo"
    SPATIAL = "spatial"
    SURROUND = "surround"


@dataclass
class AudioSource:
    """Represents a spatial audio source."""

    source_id: str
    position: tuple[float, float, float]  # x, y, z in meters
    volume: float  # 0.0-1.0
    is_playing: bool


class VisionOSAudio(AudioController):
    """visionOS spatial audio adapter.

    Provides spatial audio control for Apple Vision Pro.
    Communicates with the visionOS client via Kagami API.
    """

    def __init__(self) -> None:
        self._config: AudioConfig | None = None
        self._mode = SpatialAudioMode.SPATIAL
        self._sources: dict[str, AudioSource] = {}
        self._master_volume = 0.8
        self._api_base_url: str | None = None

    async def initialize(
        self, config: AudioConfig | None = None, api_base_url: str = "http://kagami.local:8001"
    ) -> bool:
        """Initialize spatial audio.

        Args:
            config: Audio configuration (optional for visionOS)
            api_base_url: Base URL of the Kagami API

        Returns:
            True if initialization successful
        """
        self._api_base_url = api_base_url

        if config:
            self._config = config
        else:
            # Default config for visionOS
            self._config = AudioConfig(
                sample_rate=48000, channels=2, format=AudioFormat.FLOAT_32, buffer_size=1024
            )

        if is_test_mode():
            logger.info("visionOS Audio adapter in test mode")
            return True

        logger.info("✅ visionOS Spatial Audio initialized")
        return True

    async def set_mode(self, mode: SpatialAudioMode) -> None:
        """Set spatial audio mode.

        Args:
            mode: Desired audio mode
        """
        self._mode = mode

        if self._api_base_url:
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    await session.post(
                        f"{self._api_base_url}/api/vision/audio/mode", json={"mode": mode.value}
                    )
            except Exception as e:
                logger.debug(f"Failed to set audio mode: {e}")

    async def create_source(
        self, source_id: str, position: tuple[float, float, float], volume: float = 1.0
    ) -> AudioSource:
        """Create a spatial audio source.

        Args:
            source_id: Unique identifier for the source
            position: Position in meters (x, y, z)
            volume: Initial volume (0.0-1.0)

        Returns:
            Created audio source
        """
        source = AudioSource(
            source_id=source_id, position=position, volume=volume, is_playing=False
        )
        self._sources[source_id] = source

        if self._api_base_url:
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    await session.post(
                        f"{self._api_base_url}/api/vision/audio/sources",
                        json={"id": source_id, "position": list(position), "volume": volume},
                    )
            except Exception as e:
                logger.debug(f"Failed to create audio source: {e}")

        return source

    async def update_source_position(
        self, source_id: str, position: tuple[float, float, float]
    ) -> bool:
        """Update position of a spatial audio source.

        Args:
            source_id: ID of the source
            position: New position in meters

        Returns:
            True if updated successfully
        """
        if source_id not in self._sources:
            return False

        self._sources[source_id].position = position

        if self._api_base_url:
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    await session.put(
                        f"{self._api_base_url}/api/vision/audio/sources/{source_id}",
                        json={"position": list(position)},
                    )
            except Exception as e:
                logger.debug(f"Failed to update source position: {e}")

        return True

    async def play(self, buffer: bytes) -> None:
        """Play audio buffer (standard AudioController interface).

        For spatial audio, consider using play_at_source instead.
        """
        # Default playback goes to head-locked stereo
        if self._api_base_url:
            try:
                import base64

                import aiohttp

                async with aiohttp.ClientSession() as session:
                    await session.post(
                        f"{self._api_base_url}/api/vision/audio/play",
                        json={"buffer": base64.b64encode(buffer).decode(), "spatial": False},
                    )
            except Exception as e:
                logger.debug(f"Failed to play audio: {e}")

    async def play_at_source(self, source_id: str, buffer: bytes) -> None:
        """Play audio at a specific spatial source.

        Args:
            source_id: ID of the spatial source
            buffer: Audio buffer to play
        """
        if source_id not in self._sources:
            logger.warning(f"Unknown audio source: {source_id}")
            return

        self._sources[source_id].is_playing = True

        if self._api_base_url:
            try:
                import base64

                import aiohttp

                async with aiohttp.ClientSession() as session:
                    await session.post(
                        f"{self._api_base_url}/api/vision/audio/sources/{source_id}/play",
                        json={"buffer": base64.b64encode(buffer).decode()},
                    )
            except Exception as e:
                logger.debug(f"Failed to play at source: {e}")

    async def record(self, duration_ms: int) -> bytes:
        """Record audio from spatial microphone.

        Args:
            duration_ms: Recording duration in milliseconds

        Returns:
            Recorded audio buffer
        """
        if not self._api_base_url:
            return b""

        try:
            import aiohttp

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self._api_base_url}/api/vision/audio/record",
                    json={"duration_ms": duration_ms},
                ) as response,
            ):
                if response.status == 200:
                    import base64

                    data = await response.json()
                    return base64.b64decode(data.get("buffer", ""))
        except Exception as e:
            logger.debug(f"Failed to record: {e}")

        return b""

    async def set_volume(self, level: float) -> None:
        """Set master volume.

        Args:
            level: Volume level (0.0-1.0)
        """
        self._master_volume = max(0.0, min(1.0, level))

        if self._api_base_url:
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    await session.post(
                        f"{self._api_base_url}/api/vision/audio/volume",
                        json={"level": self._master_volume},
                    )
            except Exception as e:
                logger.debug(f"Failed to set volume: {e}")

    async def get_volume(self) -> float:
        """Get master volume.

        Returns:
            Current volume level
        """
        return self._master_volume

    async def shutdown(self) -> None:
        """Shutdown spatial audio."""
        self._sources.clear()
        logger.info("visionOS Spatial Audio shutdown")


"""
Mirror
h(x) >= 0. Always.

Sound is presence.
Position is meaning.
"""
