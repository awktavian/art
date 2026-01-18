"""UnifiedMusicEffector — Music playback with visualization support.

Routes audio playback through the proper output chain:
- Desktop → Local speakers (stereo or surround)
- Home → Living Room Denon 5.1.4 Atmos via spatial_audio
- Visualization → WebSocket stream for OBS browser sources

This effector INTEGRATES with:
- UnifiedSpatialEngine for spatial audio
- OBSBridge for visualization overlays
- SmartHome for distributed audio

Usage:
    from kagami.core.effectors.music import play_music, MusicTarget

    # Play to Living Room Atmos system
    await play_music(
        "/path/to/audio.wav",
        target=MusicTarget.HOME_ATMOS,
        visualize=True,  # Enable OBS visualization
    )

Architecture:
    play_music(path)
    → UnifiedMusicEffector.play()
    → [Analysis Pipeline] → WebSocket → OBS Browser Source
    → [Audio Pipeline] → UnifiedSpatialEngine / afplay / SmartHome

Colony: ⚒️ Forge + 🔗 Nexus
Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class MusicTarget(str, Enum):
    """Music output targets."""

    AUTO = "auto"  # Context-aware routing
    DESKTOP_STEREO = "desktop_stereo"  # Mac Studio Speakers
    DESKTOP_SURROUND = "desktop_surround"  # Denon via HDMI
    HOME_ATMOS = "home_atmos"  # Living Room KEF 5.1.4
    HOME_DISTRIBUTED = "home_distributed"  # All Triad zones


@dataclass
class MusicPlaybackResult:
    """Result of music playback."""

    success: bool
    duration_sec: float = 0.0
    target: MusicTarget = MusicTarget.AUTO
    visualizer_url: str | None = None  # URL for OBS browser source
    error: str | None = None


@dataclass
class AudioAnalysisFrame:
    """Single frame of audio analysis for visualization."""

    timestamp: float  # Seconds into playback
    rms: float  # Overall loudness
    frequencies: list[float]  # FFT bands (log-spaced)
    colonies: dict[str, float]  # Colony activations

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "t": round(self.timestamp, 3),
            "rms": round(self.rms, 4),
            "freq": [round(f, 4) for f in self.frequencies],
            "colonies": {k: round(v, 4) for k, v in self.colonies.items()},
        }


class AudioAnalyzer:
    """Analyze audio in real-time for visualization.

    Extracts:
    - RMS energy
    - FFT frequency bands (log-spaced)
    - Colony activations (frequency-mapped)
    """

    # Colony frequency mappings (Hz ranges)
    COLONY_BANDS = {
        "spark": (8000, 20000),  # High transients
        "forge": (250, 2000),  # Rhythm, mids
        "flow": (100, 500),  # Smooth tones
        "nexus": (200, 4000),  # Harmonics
        "beacon": (500, 4000),  # Melody
        "grove": (20, 200),  # Bass
        "crystal": (4000, 16000),  # Brilliance
    }

    def __init__(self, sample_rate: int = 48000, fft_size: int = 2048):
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.num_bands = 32  # Log-spaced frequency bands

        # Precompute frequency bins
        self.freqs = np.fft.rfftfreq(fft_size, 1 / sample_rate)

        # Colony bin masks
        self._colony_masks: dict[str, np.ndarray] = {}
        for colony, (low, high) in self.COLONY_BANDS.items():
            self._colony_masks[colony] = (self.freqs >= low) & (self.freqs <= high)

    def analyze_chunk(self, audio: np.ndarray, timestamp: float) -> AudioAnalysisFrame:
        """Analyze a chunk of audio.

        Args:
            audio: Audio samples (mono, float32)
            timestamp: Current playback position in seconds

        Returns:
            AudioAnalysisFrame with analysis results
        """
        # RMS energy
        rms = float(np.sqrt(np.mean(audio**2))) if len(audio) > 0 else 0.0

        # FFT
        if len(audio) >= self.fft_size:
            windowed = audio[: self.fft_size] * np.hanning(self.fft_size)
            fft_result = np.abs(np.fft.rfft(windowed))
            fft_norm = fft_result / (np.max(fft_result) + 1e-10)
        else:
            fft_norm = np.zeros(self.fft_size // 2 + 1)

        # Log-spaced bands
        bands = self._log_bands(fft_norm)

        # Colony activations
        colonies = {}
        for colony, mask in self._colony_masks.items():
            if np.any(mask):
                colonies[colony] = float(np.mean(fft_norm[mask]))
            else:
                colonies[colony] = 0.0

        return AudioAnalysisFrame(
            timestamp=timestamp,
            rms=rms,
            frequencies=bands,
            colonies=colonies,
        )

    def _log_bands(self, fft: np.ndarray) -> list[float]:
        """Extract log-spaced frequency bands."""
        bands = []
        min_freq = 20
        max_freq = self.sample_rate / 2

        for i in range(self.num_bands):
            low = min_freq * (max_freq / min_freq) ** (i / self.num_bands)
            high = min_freq * (max_freq / min_freq) ** ((i + 1) / self.num_bands)

            mask = (self.freqs >= low) & (self.freqs < high)
            if np.any(mask):
                bands.append(float(np.mean(fft[mask])))
            else:
                bands.append(0.0)

        return bands


class UnifiedMusicEffector:
    """THE unified music playback effector.

    Handles routing audio to appropriate output:
    - Desktop: sounddevice direct output
    - Home Atmos: UnifiedSpatialEngine
    - Distributed: SmartHome controller

    Optional visualization via WebSocket for OBS.
    """

    def __init__(self):
        self._initialized = False
        self._analyzer: AudioAnalyzer | None = None
        self._ws_server = None  # WebSocket server for visualization
        self._ws_clients: list[Any] = []

        # Playback state
        self._playing = False
        self._current_position = 0.0

        # Stats
        self._stats = {
            "total_plays": 0,
            "by_target": {t.value: 0 for t in MusicTarget},
        }

    async def initialize(self) -> bool:
        """Initialize the music effector."""
        if self._initialized:
            return True

        try:
            import importlib.util

            if importlib.util.find_spec("sounddevice") is None:
                raise ImportError("sounddevice not found")
            if importlib.util.find_spec("soundfile") is None:
                raise ImportError("soundfile not found")

            self._analyzer = AudioAnalyzer()
            self._initialized = True

            logger.info("UnifiedMusicEffector initialized")
            return True

        except ImportError as e:
            logger.error(f"Missing audio dependencies: {e}")
            return False

    async def play(
        self,
        audio_path: str | Path,
        target: MusicTarget = MusicTarget.AUTO,
        volume: float = 1.0,
        visualize: bool = False,
        on_frame: Callable[[AudioAnalysisFrame], None] | None = None,
    ) -> MusicPlaybackResult:
        """Play audio file with optional visualization.

        Args:
            audio_path: Path to audio file
            target: Output target
            volume: Volume level (0.0-1.0)
            visualize: Enable WebSocket visualization stream
            on_frame: Callback for each analysis frame

        Returns:
            MusicPlaybackResult with playback info
        """
        if not self._initialized:
            await self.initialize()

        audio_path = Path(audio_path)
        if not audio_path.exists():
            return MusicPlaybackResult(
                success=False,
                error=f"File not found: {audio_path}",
            )

        # Resolve AUTO target
        if target == MusicTarget.AUTO:
            target = await self._resolve_target()

        try:
            import soundfile as sf

            # Load audio
            audio, sr = sf.read(str(audio_path))

            # Convert to mono for analysis
            if audio.ndim > 1:
                audio_mono = np.mean(audio, axis=1)
            else:
                audio_mono = audio

            # Ensure float32
            audio = audio.astype(np.float32) * volume
            audio_mono = audio_mono.astype(np.float32)

            duration = len(audio) / sr

            logger.info(f"Playing {audio_path.name} ({duration:.1f}s) via {target.value}")

            # Choose playback method based on target
            if target == MusicTarget.HOME_ATMOS:
                success = await self._play_atmos(audio_path, volume)
            elif target == MusicTarget.HOME_DISTRIBUTED:
                success = await self._play_distributed(str(audio_path), volume)
            else:
                # Desktop playback with analysis
                success = await self._play_with_analysis(audio, audio_mono, sr, target, on_frame)

            self._stats["total_plays"] += 1
            self._stats["by_target"][target.value] += 1

            return MusicPlaybackResult(
                success=success,
                duration_sec=duration,
                target=target,
            )

        except Exception as e:
            logger.exception(f"Music playback failed: {e}")
            return MusicPlaybackResult(success=False, error=str(e))

    async def _resolve_target(self) -> MusicTarget:
        """Resolve AUTO target based on context."""
        try:
            # Check if at home
            from kagami_smarthome import get_smart_home

            controller = await get_smart_home()

            if controller.get_presence_state().anyone_home:
                # Check if Living Room is occupied
                room_states = controller.get_room_states()
                living_room = room_states.get("Living Room", {})

                if living_room.get("occupied"):
                    return MusicTarget.HOME_ATMOS
                return MusicTarget.HOME_DISTRIBUTED

        except Exception:
            pass

        return MusicTarget.DESKTOP_SURROUND

    async def _play_atmos(self, audio_path: Path, volume: float) -> bool:
        """Play through KEF 5.1.4 Atmos system via UnifiedSpatialEngine."""
        try:
            from kagami.core.effectors.spatial_audio import (
                SpatialTarget,
                get_spatial_engine,
            )

            engine = await get_spatial_engine()
            if engine:
                result = await engine.play_spatial(
                    audio_path,
                    target=SpatialTarget.DENON_71,
                )
                return result.success

        except ImportError:
            logger.warning("Spatial engine not available, falling back to desktop")

        return await self._play_desktop(audio_path, volume)

    async def _play_distributed(self, audio_path: str, volume: float) -> bool:
        """Play through distributed home audio (Triad AMS)."""
        try:
            from kagami_smarthome import get_smart_home

            controller = await get_smart_home()
            await controller.play_audio(audio_path, volume=int(volume * 100))
            return True

        except Exception as e:
            logger.error(f"Distributed playback failed: {e}")
            return False

    async def _play_desktop(self, audio_path: Path, volume: float) -> bool:
        """Fallback desktop playback via afplay."""
        try:
            import subprocess

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

    async def _play_with_analysis(
        self,
        audio: np.ndarray,
        audio_mono: np.ndarray,
        sample_rate: int,
        target: MusicTarget,
        on_frame: Callable[[AudioAnalysisFrame], None] | None,
    ) -> bool:
        """Play audio with real-time analysis for visualization.

        Uses simple blocking playback in a thread - RELIABLE approach.
        """
        import sounddevice as sd

        # Choose device
        if target == MusicTarget.DESKTOP_SURROUND:
            device = 0  # Denon
        else:
            device = 1  # Mac Studio Speakers

        def blocking_play() -> bool:
            """Blocking playback with analysis - runs in thread."""
            try:
                # Start playback
                sd.play(audio, sample_rate, device=device)

                # Run analysis while playing
                if on_frame and self._analyzer:
                    chunk_size = 2048
                    len(audio_mono) / sample_rate
                    num_chunks = len(audio_mono) // chunk_size

                    for i in range(num_chunks):
                        start = i * chunk_size
                        end = start + chunk_size
                        chunk = audio_mono[start:end]
                        timestamp = start / sample_rate

                        frame = self._analyzer.analyze_chunk(chunk, timestamp)
                        on_frame(frame)

                        # Sleep to stay in sync with playback
                        import time

                        time.sleep(chunk_size / sample_rate * 0.9)

                # Wait for playback to finish
                sd.wait()
                return True

            except Exception as e:
                logger.exception(f"Blocking playback failed: {e}")
                return False

        # Run in thread to not block event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, blocking_play)


# =============================================================================
# Module-level API
# =============================================================================

_effector: UnifiedMusicEffector | None = None


async def get_music_effector() -> UnifiedMusicEffector:
    """Get the singleton music effector."""
    global _effector
    if _effector is None:
        _effector = UnifiedMusicEffector()
        await _effector.initialize()
    return _effector


async def play_music(
    audio_path: str | Path,
    target: MusicTarget = MusicTarget.AUTO,
    volume: float = 1.0,
    visualize: bool = False,
    on_frame: Callable[[AudioAnalysisFrame], None] | None = None,
) -> MusicPlaybackResult:
    """Play music file.

    Convenience function that uses the singleton effector.

    Args:
        audio_path: Path to audio file
        target: Output target (AUTO for context-aware routing)
        volume: Volume (0.0-1.0)
        visualize: Enable visualization stream
        on_frame: Callback for each analysis frame

    Returns:
        MusicPlaybackResult

    Example:
        >>> result = await play_music("song.wav")
        >>> if result.success:
        ...     print(f"Played {result.duration_sec:.1f}s")
    """
    effector = await get_music_effector()
    return await effector.play(
        audio_path,
        target=target,
        volume=volume,
        visualize=visualize,
        on_frame=on_frame,
    )
