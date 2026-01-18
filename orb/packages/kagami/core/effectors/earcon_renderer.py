"""Earcon Renderer — Renders orchestral earcons through BBC Symphony Orchestra.

Complete pipeline from earcon definition to spatialized audio:
1. Generate MIDI from orchestration
2. Apply expression engine for dynamics and articulation
3. Render through REAPER with BBC SO
4. Apply spatial trajectory via VBAP
5. Cache for instant playback

Quality Standards:
- Fletcher: Precise tempo and articulation
- Williams: Memorable, emotional themes
- Elfman: Character and personality
- Spatial: Meaningful 3D movement

Colony: Forge (e₂) + Flow (e₃)
Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

try:
    import soundfile as sf
except ImportError:
    sf = None  # type: ignore[assignment]

from kagami.core.effectors.earcon_midi import EarconMIDIGenerator, MIDIGeneratorConfig
from kagami.core.effectors.earcon_orchestrator import (
    EarconDefinition,
    SpatialTrajectory,
    get_earcon,
    get_earcon_registry,
)
from kagami.core.effectors.vbap_core import Pos3D, vbap_10ch

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

SAMPLE_RATE = 48000
WORK_DIR = Path.home() / ".kagami" / "earcons"
MIDI_DIR = WORK_DIR / "midi"
RENDERED_DIR = WORK_DIR / "rendered"
SPATIALIZED_DIR = WORK_DIR / "spatialized"


@dataclass
class EarconRendererConfig:
    """Configuration for the earcon renderer."""

    work_dir: Path = WORK_DIR
    sample_rate: int = SAMPLE_RATE
    output_channels: int = 10  # 5.1.4 Atmos

    # REAPER/BBC SO settings
    use_reaper: bool = True
    reaper_timeout: float = 120.0  # Max render time per earcon

    # Spatialization
    spatialize: bool = True
    trajectory_fps: int = 60  # Trajectory sample rate

    # Fallback synthesis (when REAPER unavailable)
    use_fallback_synthesis: bool = True


# =============================================================================
# Fallback Synthesizer
# =============================================================================


class FallbackSynthesizer:
    """Simple synthesizer for when BBC SO is not available.

    This produces basic but musical sounds that capture the intent
    of the orchestration without requiring REAPER/BBC SO.

    Not virtuoso quality, but functional for development.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate

    def synthesize(self, earcon: EarconDefinition) -> np.ndarray:
        """Synthesize basic audio from earcon orchestration.

        Args:
            earcon: Earcon definition with orchestration

        Returns:
            Mono audio array
        """
        duration = earcon.duration
        n_samples = int(duration * self.sample_rate)
        audio = np.zeros(n_samples, dtype=np.float32)
        t = np.linspace(0, duration, n_samples)

        for voice in earcon.orchestration.voices:
            voice_audio = self._synthesize_voice(voice, t)
            audio += voice_audio * 0.3  # Mix down

        # Normalize
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.85

        # Apply master volume
        audio *= earcon.orchestration.master_volume

        return audio

    def _synthesize_voice(
        self,
        voice,
        t: np.ndarray,
    ) -> np.ndarray:
        """Synthesize a single voice."""

        audio = np.zeros_like(t)

        for note_time, pitch, duration, velocity in voice.notes:
            freq = 440.0 * (2.0 ** ((pitch - 69) / 12.0))
            note_samples = t.shape[0]

            # Note envelope
            attack = 0.02
            release = min(0.1, duration * 0.3)
            envelope = np.ones(note_samples)

            # Attack
            attack_samples = int(attack * self.sample_rate)
            for i in range(min(attack_samples, note_samples)):
                t_offset = t[i] - note_time
                if 0 <= t_offset < attack:
                    envelope[i] = t_offset / attack

            # Sustain and release
            note_end = note_time + duration
            release_start = note_end - release
            for i in range(note_samples):
                t_offset = t[i]
                if t_offset >= note_end:
                    envelope[i] = 0
                elif t_offset >= release_start:
                    envelope[i] = (note_end - t_offset) / release
                elif t_offset < note_time:
                    envelope[i] = 0

            # Waveform with harmonics
            wave = np.sin(2 * np.pi * freq * t) * 0.7
            wave += np.sin(2 * np.pi * freq * 2 * t) * 0.2  # Octave
            wave += np.sin(2 * np.pi * freq * 3 * t) * 0.1  # 5th

            audio += wave * envelope * (velocity / 127.0)

        return audio


# =============================================================================
# Spatial Audio Renderer
# =============================================================================


class SpatialRenderer:
    """Applies spatial trajectories to audio using VBAP.

    Converts mono audio to multichannel based on 3D position
    over time, creating immersive spatial sound.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        output_channels: int = 10,
        trajectory_fps: int = 60,
    ):
        self.sample_rate = sample_rate
        self.output_channels = output_channels
        self.trajectory_fps = trajectory_fps

    def spatialize(
        self,
        audio: np.ndarray,
        trajectory: SpatialTrajectory,
        duration: float,
    ) -> np.ndarray:
        """Apply spatial trajectory to mono audio.

        Args:
            audio: Mono audio array
            trajectory: Spatial trajectory definition
            duration: Total duration in seconds

        Returns:
            Multichannel audio array (samples, channels)
        """
        n_samples = len(audio)
        output = np.zeros((n_samples, self.output_channels), dtype=np.float32)

        # Sample trajectory at regular intervals
        self.sample_rate / self.trajectory_fps

        # Cache for interpolated positions
        positions = self._interpolate_trajectory(trajectory, duration, n_samples)

        for i in range(n_samples):
            # Get position at this sample
            pos = positions[i]

            # Get VBAP gains
            gains = vbap_10ch(pos.az, pos.el, pos.dist)

            # Apply gains to this sample
            for ch in range(min(self.output_channels, len(gains))):
                output[i, ch] = audio[i] * gains[ch]

        return output

    def _interpolate_trajectory(
        self,
        trajectory: SpatialTrajectory,
        duration: float,
        n_samples: int,
    ) -> list[Pos3D]:
        """Interpolate trajectory keyframes to sample rate.

        Args:
            trajectory: Trajectory with keyframes
            duration: Total duration
            n_samples: Number of output samples

        Returns:
            List of Pos3D for each sample
        """
        positions = []
        keyframes = trajectory.keyframes

        for i in range(n_samples):
            t_ratio = i / n_samples

            # Find surrounding keyframes
            pos = keyframes[0][1]  # Default to first

            for j in range(len(keyframes) - 1):
                kf1_ratio, kf1_pos = keyframes[j]
                kf2_ratio, kf2_pos = keyframes[j + 1]

                if kf1_ratio <= t_ratio <= kf2_ratio:
                    # Interpolate between keyframes
                    if kf2_ratio > kf1_ratio:
                        alpha = (t_ratio - kf1_ratio) / (kf2_ratio - kf1_ratio)
                    else:
                        alpha = 0

                    # Apply easing
                    alpha = self._apply_easing(alpha, trajectory.ease_type)

                    # Interpolate position
                    az = kf1_pos.az + (kf2_pos.az - kf1_pos.az) * alpha
                    el = kf1_pos.el + (kf2_pos.el - kf1_pos.el) * alpha
                    dist = kf1_pos.dist + (kf2_pos.dist - kf1_pos.dist) * alpha
                    pos = Pos3D(az=az, el=el, dist=dist)
                    break
            else:
                # Past last keyframe
                pos = keyframes[-1][1]

            positions.append(pos)

        return positions

    def _apply_easing(self, t: float, ease_type: str) -> float:
        """Apply easing function to interpolation."""
        if ease_type == "ease_in":
            return t * t
        elif ease_type == "ease_out":
            return 1 - (1 - t) * (1 - t)
        elif ease_type == "ease_in_out":
            if t < 0.5:
                return 2 * t * t
            else:
                return 1 - 2 * (1 - t) * (1 - t)
        else:  # linear
            return t


# =============================================================================
# Main Earcon Renderer
# =============================================================================


@dataclass
class EarconRenderResult:
    """Result of rendering an earcon."""

    success: bool
    earcon_name: str
    audio_path: Path | None = None
    duration_sec: float = 0.0
    render_time_sec: float = 0.0
    used_fallback: bool = False
    error: str | None = None


class EarconRenderer:
    """Main earcon renderer - orchestrates the full rendering pipeline.

    Pipeline:
    1. Load earcon definition
    2. Generate MIDI from orchestration
    3. Render MIDI through BBC SO (or fallback)
    4. Apply spatial trajectory
    5. Save and cache result
    """

    def __init__(self, config: EarconRendererConfig | None = None):
        """Initialize the earcon renderer.

        Args:
            config: Configuration options
        """
        self.config = config or EarconRendererConfig()

        # Create directories
        MIDI_DIR.mkdir(parents=True, exist_ok=True)
        RENDERED_DIR.mkdir(parents=True, exist_ok=True)
        SPATIALIZED_DIR.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.midi_generator = EarconMIDIGenerator(MIDIGeneratorConfig(output_dir=MIDI_DIR))
        self.fallback_synth = FallbackSynthesizer(self.config.sample_rate)
        self.spatial_renderer = SpatialRenderer(
            sample_rate=self.config.sample_rate,
            output_channels=self.config.output_channels,
            trajectory_fps=self.config.trajectory_fps,
        )

    async def render_earcon(self, earcon_name: str) -> EarconRenderResult:
        """Render a single earcon by name.

        Args:
            earcon_name: Name of the earcon to render

        Returns:
            EarconRenderResult with status and path
        """
        start_time = time.time()

        # Get earcon definition
        earcon = get_earcon(earcon_name)
        if not earcon:
            return EarconRenderResult(
                success=False,
                earcon_name=earcon_name,
                error=f"Earcon not found: {earcon_name}",
            )

        try:
            # Step 1: Generate MIDI
            midi_path = self.midi_generator.save_midi(earcon)
            logger.info(f"Generated MIDI: {midi_path}")

            # Step 2: Render audio
            audio = None
            used_fallback = False

            if self.config.use_reaper:
                audio = await self._render_via_bbc(earcon, midi_path)

            if audio is None and self.config.use_fallback_synthesis:
                logger.info(f"Using fallback synthesis for {earcon_name}")
                audio = self.fallback_synth.synthesize(earcon)
                used_fallback = True

            if audio is None:
                return EarconRenderResult(
                    success=False,
                    earcon_name=earcon_name,
                    error="Failed to render audio",
                )

            # Step 3: Apply spatial trajectory
            if self.config.spatialize:
                trajectory = earcon.get_trajectory()
                spatialized = self.spatial_renderer.spatialize(audio, trajectory, earcon.duration)
            else:
                # Just duplicate to stereo
                spatialized = np.column_stack([audio, audio])

            # Step 4: Save output
            output_path = SPATIALIZED_DIR / f"{earcon_name}.wav"
            if sf:
                sf.write(str(output_path), spatialized, self.config.sample_rate)
            else:
                logger.error("soundfile not available for saving")
                return EarconRenderResult(
                    success=False,
                    earcon_name=earcon_name,
                    error="soundfile not installed",
                )

            render_time = time.time() - start_time
            logger.info(f"Rendered {earcon_name} in {render_time:.2f}s")

            return EarconRenderResult(
                success=True,
                earcon_name=earcon_name,
                audio_path=output_path,
                duration_sec=earcon.duration,
                render_time_sec=render_time,
                used_fallback=used_fallback,
            )

        except Exception as e:
            logger.error(f"Error rendering {earcon_name}: {e}", exc_info=True)
            return EarconRenderResult(
                success=False,
                earcon_name=earcon_name,
                error=str(e),
            )

    async def _render_via_bbc(
        self,
        earcon: EarconDefinition,
        midi_path: Path,
    ) -> np.ndarray | None:
        """Render MIDI through BBC Symphony Orchestra.

        This uses the existing bbc_renderer pipeline.

        Args:
            earcon: Earcon definition
            midi_path: Path to MIDI file

        Returns:
            Mono audio array or None if failed
        """
        try:
            from kagami.core.effectors.bbc_renderer import BBCRenderer, RenderConfig

            config = RenderConfig(
                output_format="wav",
                sample_rate=self.config.sample_rate,
                bit_depth=24,
            )

            renderer = BBCRenderer(config)
            result = await renderer.render(midi_path)

            if result.success and result.path:
                # Load rendered audio
                audio, _sr = sf.read(str(result.path))
                if audio.ndim > 1:
                    audio = audio.mean(axis=1)  # Mix to mono
                return audio.astype(np.float32)

        except ImportError:
            logger.debug("BBC renderer not available")
        except Exception as e:
            logger.warning(f"BBC render failed: {e}")

        return None

    async def render_all_earcons(
        self,
        parallel: int = 4,
    ) -> dict[str, EarconRenderResult]:
        """Render all registered earcons.

        Args:
            parallel: Maximum parallel renders

        Returns:
            Dict mapping earcon names to results
        """
        registry = get_earcon_registry()
        results = {}

        # Use semaphore to limit parallelism
        semaphore = asyncio.Semaphore(parallel)

        async def render_with_semaphore(name: str) -> tuple[str, EarconRenderResult]:
            async with semaphore:
                result = await self.render_earcon(name)
                return name, result

        tasks = [render_with_semaphore(name) for name in registry.keys()]
        completed = await asyncio.gather(*tasks)

        for name, result in completed:
            results[name] = result

        # Summary
        success = sum(1 for r in results.values() if r.success)
        fallback = sum(1 for r in results.values() if r.used_fallback)
        logger.info(
            f"Rendered {success}/{len(results)} earcons ({fallback} using fallback synthesis)"
        )

        return results


# =============================================================================
# Convenience Functions
# =============================================================================


async def render_earcon(earcon_name: str) -> EarconRenderResult:
    """Render a single earcon by name.

    Args:
        earcon_name: Name of the earcon

    Returns:
        Render result
    """
    renderer = EarconRenderer()
    return await renderer.render_earcon(earcon_name)


async def render_all_earcons() -> dict[str, EarconRenderResult]:
    """Render all registered earcons.

    Returns:
        Dict mapping names to results
    """
    renderer = EarconRenderer()
    return await renderer.render_all_earcons()


def get_cached_earcon_path(earcon_name: str) -> Path | None:
    """Get path to cached earcon audio if it exists.

    Args:
        earcon_name: Name of the earcon

    Returns:
        Path to audio file or None
    """
    path = SPATIALIZED_DIR / f"{earcon_name}.wav"
    return path if path.exists() else None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "EarconRenderResult",
    "EarconRenderer",
    "EarconRendererConfig",
    "FallbackSynthesizer",
    "SpatialRenderer",
    "get_cached_earcon_path",
    "render_all_earcons",
    "render_earcon",
]
