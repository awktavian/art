"""Spatial Sync — Unified Audio-Visual Synchronization.

LIGHT IS MUSIC IS SPECTRUM.

This module provides real-time synchronization between:
- Spatial audio playback (Denon 5.1.4 via Neural:X)
- Spectrum-driven lighting (Oelo + Govee)
- Music analysis (7-band FFT + loudness)

The synchronization loop:
1. Audio plays through UnifiedSpatialEngine
2. Real-time FFT analysis extracts frequency bands
3. SpectrumEngine maps bands to light parameters
4. Oelo/Govee receive coordinated updates

For orchestral playback, the spatial position can also influence
lighting — sounds panning left toward the lake intensify the
outdoor lights on that side.

Created: January 3, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy import signal

from kagami_smarthome.spectrum.engine import (
    FrequencyBalance,
    MusicalContext,
    MusicMood,
    SpectrumOutput,
    get_spectrum_engine,
)

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class SpatialSyncConfig:
    """Configuration for spatial audio-light sync."""

    # Analysis rate
    analysis_fps: int = 30  # FFT analysis frames per second
    light_update_fps: int = 15  # Light update rate (Oelo can handle ~20)

    # Audio analysis
    fft_size: int = 2048  # FFT window size
    sample_rate: int = 48000  # Match Denon output

    # Spatial-light mapping
    enable_spatial_mapping: bool = True  # Map L/R panning to light position
    lake_side_boost: float = 0.3  # Boost lake-side lights on left panning

    # Light systems
    enable_oelo: bool = True
    enable_govee: bool = True

    # Safety
    max_brightness: float = 1.0
    min_brightness: float = 0.1
    circadian_aware: bool = True


# =============================================================================
# Real-Time Audio Analyzer
# =============================================================================


@dataclass
class AudioFrame:
    """Single frame of analyzed audio."""

    timestamp: float
    frequency_balance: FrequencyBalance
    lufs: float
    peak: float
    stereo_balance: float  # -1 (full left) to +1 (full right)


class RealtimeAnalyzer:
    """Real-time audio analysis for spectrum synchronization.

    Provides streaming FFT analysis that feeds into the SpectrumEngine.
    Designed to run in parallel with audio playback.
    """

    # 7-band filter bank (matches SpectrumEngine)
    BANDS = [
        ("sub_bass", 20, 60),
        ("bass", 60, 250),
        ("low_mid", 250, 500),
        ("mid", 500, 2000),
        ("upper_mid", 2000, 4000),
        ("presence", 4000, 8000),
        ("brilliance", 8000, 20000),
    ]

    def __init__(self, config: SpatialSyncConfig | None = None):
        """Initialize analyzer."""
        self._config = config or SpatialSyncConfig()
        self._filters: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._setup_filters()

    def _setup_filters(self) -> None:
        """Pre-compute bandpass filters for each frequency band."""
        sr = self._config.sample_rate
        nyq = sr / 2

        for name, low, high in self.BANDS:
            low_norm = max(low / nyq, 0.001)
            high_norm = min(high / nyq, 0.999)

            try:
                sos = signal.butter(4, [low_norm, high_norm], "band", output="sos")
                self._filters[name] = sos
            except Exception as e:
                logger.warning(f"Failed to create filter for {name}: {e}")

    def analyze_chunk(
        self,
        audio: np.ndarray,
        timestamp: float = 0.0,
    ) -> AudioFrame:
        """Analyze a chunk of audio.

        Args:
            audio: Audio samples (mono or stereo, float32)
            timestamp: Timestamp of this chunk

        Returns:
            AudioFrame with frequency balance and loudness
        """
        # Handle stereo
        if len(audio.shape) > 1 and audio.shape[1] >= 2:
            left = audio[:, 0]
            right = audio[:, 1]
            mono = (left + right) / 2

            # Stereo balance (-1 to +1)
            l_energy = np.sqrt(np.mean(left**2))
            r_energy = np.sqrt(np.mean(right**2))
            total = l_energy + r_energy + 1e-10
            stereo_balance = (r_energy - l_energy) / total
        else:
            mono = audio.flatten() if len(audio.shape) > 1 else audio
            stereo_balance = 0.0

        # Frequency band analysis
        band_energies = {}
        for name, _, _ in self.BANDS:
            if name in self._filters:
                try:
                    filtered = signal.sosfilt(self._filters[name], mono)
                    energy = np.sqrt(np.mean(filtered**2))
                    energy_db = 20 * np.log10(energy + 1e-10)
                    band_energies[name] = energy_db
                except Exception:
                    band_energies[name] = -100.0
            else:
                band_energies[name] = -100.0

        # Normalize band energies to average = 0
        avg = np.mean(list(band_energies.values()))
        for name in band_energies:
            band_energies[name] -= avg

        # Create FrequencyBalance
        freq_balance = FrequencyBalance(
            sub_bass=band_energies.get("sub_bass", 0.0),
            bass=band_energies.get("bass", 0.0),
            low_mid=band_energies.get("low_mid", 0.0),
            mid=band_energies.get("mid", 0.0),
            upper_mid=band_energies.get("upper_mid", 0.0),
            presence=band_energies.get("presence", 0.0),
            brilliance=band_energies.get("brilliance", 0.0),
        )

        # LUFS approximation
        lufs = -0.691 + 10 * np.log10(np.mean(mono**2) + 1e-10)

        # Peak
        peak = np.max(np.abs(mono))

        return AudioFrame(
            timestamp=timestamp,
            frequency_balance=freq_balance,
            lufs=lufs,
            peak=peak,
            stereo_balance=stereo_balance,
        )


# =============================================================================
# Spatial-Light Mapper
# =============================================================================


class SpatialLightMapper:
    """Maps spatial audio position to light distribution.

    When audio pans left (toward the lake), the outdoor lights
    on the lake side intensify. This creates a unified audio-visual
    spatial experience.
    """

    def __init__(self, config: SpatialSyncConfig | None = None):
        """Initialize mapper."""
        self._config = config or SpatialSyncConfig()

    def apply_spatial_bias(
        self,
        output: SpectrumOutput,
        stereo_balance: float,
    ) -> tuple[SpectrumOutput, float]:
        """Apply spatial audio position to light output.

        Args:
            output: Base spectrum output
            stereo_balance: -1 (full left) to +1 (full right)

        Returns:
            Tuple of (modified output, lake_side_intensity_boost)
        """
        if not self._config.enable_spatial_mapping:
            return output, 0.0

        # Lake is on the LEFT of the living room
        # When audio pans left (negative balance), boost lake-side lights
        lake_boost = 0.0
        if stereo_balance < -0.1:
            # More negative = more left = more lake boost
            lake_boost = abs(stereo_balance) * self._config.lake_side_boost

        # Shift hue slightly based on spatial position
        # Left (lake) = cooler, Right = warmer
        hue_shift = stereo_balance * 15  # +/- 15 degrees
        modified_hue = (output.hue + hue_shift) % 360

        # Create modified output
        modified = SpectrumOutput(
            hue=modified_hue,
            saturation=output.saturation,
            brightness=output.brightness,
            colors=output.colors,
            pattern=output.pattern,
            speed=output.speed,
            transition_ms=output.transition_ms,
            mood=output.mood,
            dominant_band=output.dominant_band,
        )

        return modified, lake_boost


# =============================================================================
# Unified Spatial Sync Controller
# =============================================================================


class SpatialSyncController:
    """Unified controller for synchronized audio-visual playback.

    LIGHT IS MUSIC IS SPECTRUM.

    This is the main integration point that coordinates:
    - Spatial audio playback (via UnifiedSpatialEngine)
    - Real-time audio analysis (via RealtimeAnalyzer)
    - Spectrum-to-light mapping (via SpectrumEngine)
    - Light control (via Oelo + Govee integrations)

    Usage:
        controller = SpatialSyncController(smart_home)
        await controller.play_with_lights(
            audio_path="/path/to/orchestral.wav",
            spatial=True,  # Enable 5.1.4 spatial
        )
    """

    def __init__(
        self,
        smart_home: SmartHomeController | None = None,
        config: SpatialSyncConfig | None = None,
    ):
        """Initialize spatial sync controller."""
        self._smart_home = smart_home
        self._config = config or SpatialSyncConfig()

        self._analyzer = RealtimeAnalyzer(config)
        self._spatial_mapper = SpatialLightMapper(config)
        self._spectrum = get_spectrum_engine()

        self._running = False
        self._current_output: SpectrumOutput | None = None

        # Statistics
        self._frames_analyzed = 0
        self._lights_updated = 0
        self._start_time: float = 0

    async def play_with_lights(
        self,
        audio_path: str | Path,
        spatial: bool = True,
        trajectory: str | None = None,
        musical_context: MusicalContext | None = None,
        on_frame: Callable[[AudioFrame, SpectrumOutput], None] | None = None,
    ) -> dict[str, Any]:
        """Play audio with synchronized lighting.

        Args:
            audio_path: Path to audio file
            spatial: Enable 5.1.4 spatial audio (requires Denon)
            trajectory: Spatial trajectory ("corkscrew", "orbit", "voice", None)
            musical_context: Optional musical context for better mapping
            on_frame: Callback for each analysis frame

        Returns:
            Playback statistics
        """
        import soundfile as sf

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Load audio for analysis
        audio, sr = sf.read(str(audio_path))
        if sr != self._config.sample_rate:
            # Resample
            from scipy import signal as sig

            new_len = int(len(audio) * self._config.sample_rate / sr)
            if len(audio.shape) > 1:
                resampled = np.zeros((new_len, audio.shape[1]), dtype=np.float32)
                for ch in range(audio.shape[1]):
                    resampled[:, ch] = sig.resample(audio[:, ch], new_len)
                audio = resampled
            else:
                audio = sig.resample(audio, new_len).astype(np.float32)
            sr = self._config.sample_rate

        audio = audio.astype(np.float32)
        duration = len(audio) / sr

        logger.info(f"Playing {duration:.1f}s audio with synchronized lights")

        self._running = True
        self._start_time = time.time()
        self._frames_analyzed = 0
        self._lights_updated = 0

        # Start parallel tasks
        tasks = [
            asyncio.create_task(self._analysis_loop(audio, sr, musical_context, on_frame)),
            asyncio.create_task(self._light_update_loop()),
        ]

        # Start spatial audio playback
        if spatial:
            tasks.append(asyncio.create_task(self._play_spatial(audio_path, trajectory, duration)))
        else:
            tasks.append(asyncio.create_task(self._play_stereo(audio, sr)))

        # Wait for playback to complete
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False

        # Return statistics
        elapsed = time.time() - self._start_time
        return {
            "duration_sec": duration,
            "frames_analyzed": self._frames_analyzed,
            "lights_updated": self._lights_updated,
            "analysis_fps": self._frames_analyzed / elapsed if elapsed > 0 else 0,
            "light_fps": self._lights_updated / elapsed if elapsed > 0 else 0,
        }

    async def _analysis_loop(
        self,
        audio: np.ndarray,
        sr: int,
        musical_context: MusicalContext | None,
        on_frame: Callable[[AudioFrame, SpectrumOutput], None] | None,
    ) -> None:
        """Run real-time analysis loop."""
        chunk_size = sr // self._config.analysis_fps
        n_chunks = len(audio) // chunk_size

        for i in range(n_chunks):
            if not self._running:
                break

            start_idx = i * chunk_size
            end_idx = start_idx + chunk_size
            chunk = audio[start_idx:end_idx]

            timestamp = i / self._config.analysis_fps

            # Analyze chunk
            frame = self._analyzer.analyze_chunk(chunk, timestamp)
            self._frames_analyzed += 1

            # Build musical context
            if musical_context:
                context = MusicalContext(
                    frequency_balance=frame.frequency_balance,
                    tempo_bpm=musical_context.tempo_bpm,
                    key=musical_context.key,
                    mode=musical_context.mode,
                    dynamics=(frame.lufs + 30) / 20,  # Normalize to 0-1
                    articulation=musical_context.articulation,
                    mood=musical_context.mood,
                )
            else:
                # Infer from audio only
                dynamics = max(0.0, min(1.0, (frame.lufs + 30) / 20))
                context = MusicalContext(
                    frequency_balance=frame.frequency_balance,
                    dynamics=dynamics,
                )

            # Compute spectrum output
            output = self._spectrum.compute(context)

            # Apply spatial mapping
            output, lake_boost = self._spatial_mapper.apply_spatial_bias(
                output, frame.stereo_balance
            )

            # Store for light update loop
            self._current_output = output
            self._current_lake_boost = lake_boost

            # Callback
            if on_frame:
                on_frame(frame, output)

            # Wait for next frame
            await asyncio.sleep(1.0 / self._config.analysis_fps)

    async def _light_update_loop(self) -> None:
        """Update lights based on current spectrum output."""
        interval = 1.0 / self._config.light_update_fps

        while self._running:
            if self._current_output:
                await self._update_lights(
                    self._current_output,
                    getattr(self, "_current_lake_boost", 0.0),
                )
                self._lights_updated += 1

            await asyncio.sleep(interval)

    async def _update_lights(
        self,
        output: SpectrumOutput,
        lake_boost: float = 0.0,
    ) -> None:
        """Send spectrum output to all light systems."""
        # Apply brightness constraints
        brightness = max(
            self._config.min_brightness,
            min(self._config.max_brightness, output.brightness),
        )

        # Apply circadian dimming if enabled
        if self._config.circadian_aware:
            try:
                from kagami_smarthome.context.context_engine import (
                    CircadianPhase,
                    get_circadian_phase,
                )

                phase = get_circadian_phase()
                if phase in (CircadianPhase.NIGHT, CircadianPhase.LATE_NIGHT):
                    brightness *= 0.5
            except Exception:
                pass

        # Update Oelo (outdoor lights on lake side)
        if self._config.enable_oelo and self._smart_home:
            await self._update_oelo(output, brightness, lake_boost)

        # Update Govee (indoor lights)
        if self._config.enable_govee and self._smart_home:
            await self._update_govee(output, brightness)

    async def _update_oelo(
        self,
        output: SpectrumOutput,
        brightness: float,
        lake_boost: float,
    ) -> None:
        """Update Oelo outdoor lights."""
        oelo_svc = getattr(self._smart_home, "_oelo_service", None)
        if not oelo_svc or not oelo_svc.is_available:
            return

        try:
            from kagami_smarthome.integrations.oelo import Color

            # Apply lake boost to brightness
            boosted_brightness = min(1.0, brightness * (1 + lake_boost))

            # Convert colors with boosted brightness
            colors = []
            for r, g, b in output.colors:
                factor = boosted_brightness / max(output.brightness, 0.1)
                colors.append(
                    Color(
                        int(min(255, r * factor)),
                        int(min(255, g * factor)),
                        int(min(255, b * factor)),
                    )
                )

            # Get Oelo integration
            oelo = getattr(oelo_svc, "_oelo", None)
            if oelo:
                await oelo.set_custom(
                    pattern_type=output.pattern.value,
                    colors=colors,
                    speed=output.speed,
                )

        except Exception as e:
            logger.debug(f"Oelo update error: {e}")

    async def _update_govee(
        self,
        output: SpectrumOutput,
        brightness: float,
    ) -> None:
        """Update Govee lights."""
        govee = getattr(self._smart_home, "_govee", None)
        if not govee:
            return

        try:
            if hasattr(govee, "apply_spectrum_all"):
                await govee.apply_spectrum_all(output)
        except Exception as e:
            logger.debug(f"Govee update error: {e}")

    async def _play_spatial(
        self,
        audio_path: Path,
        trajectory: str | None,
        duration: float,
    ) -> None:
        """Play audio through spatial audio engine."""
        try:
            from kagami.core.effectors.spatial_audio import (
                generate_corkscrew,
                generate_orbit,
                generate_voice_presence,
                get_spatial_engine,
            )

            engine = await get_spatial_engine()

            # Generate trajectory
            traj = None
            if trajectory == "corkscrew":
                traj = generate_corkscrew(duration)
            elif trajectory == "orbit":
                traj = generate_orbit(duration)
            elif trajectory == "voice":
                traj = generate_voice_presence(duration)

            # Play through 5.1.4 system
            await engine.play_spatial(audio_path, traj)

        except ImportError:
            logger.warning("Spatial audio engine not available, falling back to stereo")
            import sounddevice as sd
            import soundfile as sf

            audio, sr = sf.read(str(audio_path))
            sd.play(audio, sr)
            sd.wait()

    async def _play_stereo(self, audio: np.ndarray, sr: int) -> None:
        """Play audio through stereo output."""
        import sounddevice as sd

        sd.play(audio, sr)
        sd.wait()

    def stop(self) -> None:
        """Stop playback and light updates."""
        self._running = False


# =============================================================================
# Convenience Functions
# =============================================================================

# Global controller instance
_sync_controller: SpatialSyncController | None = None


async def play_orchestral_with_lights(
    audio_path: str | Path,
    smart_home: SmartHomeController | None = None,
    tempo_bpm: float = 90,
    key: str = "C",
    mode: str = "major",
    mood: MusicMood = MusicMood.NEUTRAL,
    spatial: bool = True,
    trajectory: str | None = "orbit",
) -> dict[str, Any]:
    """Play orchestral audio with synchronized lighting.

    LIGHT IS MUSIC IS SPECTRUM.

    This is the high-level API for orchestral playback with lights.

    Args:
        audio_path: Path to orchestral audio file
        smart_home: SmartHomeController instance (for light control)
        tempo_bpm: Tempo for light timing
        key: Musical key (C, D, E, etc.)
        mode: Mode (major, minor, etc.)
        mood: Musical mood for color mapping
        spatial: Enable 5.1.4 spatial audio
        trajectory: Spatial trajectory type

    Returns:
        Playback statistics

    Example:
        from kagami_smarthome.spectrum.spatial_sync import play_orchestral_with_lights

        stats = await play_orchestral_with_lights(
            "/path/to/beethoven.wav",
            tempo_bpm=72,
            key="Cm",
            mode="minor",
            mood=MusicMood.DRAMATIC,
        )
    """
    global _sync_controller

    if _sync_controller is None or _sync_controller._smart_home != smart_home:
        _sync_controller = SpatialSyncController(smart_home)

    context = MusicalContext(
        tempo_bpm=tempo_bpm,
        key=key,
        mode=mode,
        mood=mood,
    )

    return await _sync_controller.play_with_lights(
        audio_path=audio_path,
        spatial=spatial,
        trajectory=trajectory,
        musical_context=context,
    )


async def demo_spectrum_sync(
    smart_home: SmartHomeController | None = None,
    duration: float = 10.0,
) -> dict[str, Any]:
    """Demo the spectrum sync with a test tone.

    Generates a sweep through frequency bands to demonstrate
    the light-music synchronization.
    """
    import tempfile

    import numpy as np
    import soundfile as sf

    # Generate frequency sweep
    sr = 48000
    t = np.linspace(0, duration, int(sr * duration))

    # Sweep from 60Hz to 8kHz
    freq = 60 * np.exp(np.log(8000 / 60) * t / duration)
    sweep = 0.5 * np.sin(2 * np.pi * freq * t / sr * np.arange(len(t)))

    # Add harmonics for richer spectrum
    sweep += 0.3 * np.sin(4 * np.pi * freq * t / sr * np.arange(len(t)))
    sweep += 0.2 * np.sin(6 * np.pi * freq * t / sr * np.arange(len(t)))

    # Stereo with panning sweep (L to R to L)
    pan = 0.5 + 0.5 * np.sin(2 * np.pi * t / duration * 2)
    stereo = np.column_stack([sweep * (1 - pan), sweep * pan])

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, stereo.astype(np.float32), sr)
        temp_path = f.name

    # Play with lights
    return await play_orchestral_with_lights(
        temp_path,
        smart_home=smart_home,
        tempo_bpm=120,
        key="C",
        mode="major",
        mood=MusicMood.ENERGETIC,
        spatial=True,
        trajectory="orbit",
    )


__all__ = [
    "AudioFrame",
    "RealtimeAnalyzer",
    "SpatialLightMapper",
    "SpatialSyncConfig",
    "SpatialSyncController",
    "demo_spectrum_sync",
    "play_orchestral_with_lights",
]
