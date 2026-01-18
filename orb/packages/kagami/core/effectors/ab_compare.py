"""A/B Comparison Module — Compare Different Rendering Backends.

Provides utilities for comparing BBC Symphony Orchestra, FluidSynth,
and Adaptive rendering modes. Useful for quality verification and
debugging rendering issues.

Colony: Crystal (e₇) — Verification
Created: January 1, 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

OUTPUT_DIR = Path.home() / ".kagami/symphony/ab_compare"


@dataclass
class ComparisonMetrics:
    """Audio comparison metrics between two renderings."""

    rms_a: float  # RMS level of audio A
    rms_b: float  # RMS level of audio B
    peak_a: float  # Peak level of audio A
    peak_b: float  # Peak level of audio B
    duration_a: float  # Duration in seconds
    duration_b: float  # Duration in seconds
    correlation: float  # Cross-correlation coefficient
    spectral_diff: float  # Spectral difference (0-1)


@dataclass
class ComparisonResult:
    """Result of A/B comparison."""

    success: bool
    midi_path: Path
    renderers: list[str]
    audio_paths: dict[str, Path]
    render_times: dict[str, float]
    metrics: dict[str, ComparisonMetrics] | None = None
    error: str | None = None


# =============================================================================
# Comparison Functions
# =============================================================================


async def compare_renderers(
    midi_path: Path | str,
    renderers: list[str] | None = None,
    output_dir: Path | None = None,
) -> ComparisonResult:
    """Render same MIDI with different backends and compare.

    Renders the MIDI file with each specified renderer and collects
    timing and quality metrics for comparison.

    Args:
        midi_path: Path to MIDI file
        renderers: List of renderer names. Default: ["bbc", "fluidsynth", "adaptive"]
        output_dir: Directory for output files

    Returns:
        ComparisonResult with audio paths and metrics
    """
    from kagami.core.effectors.orchestra import RenderMode, get_orchestra

    midi_path = Path(midi_path)
    if not midi_path.exists():
        return ComparisonResult(
            success=False,
            midi_path=midi_path,
            renderers=[],
            audio_paths={},
            render_times={},
            error=f"MIDI file not found: {midi_path}",
        )

    # Default renderers
    if renderers is None:
        renderers = ["bbc", "fluidsynth", "adaptive"]

    # Setup output directory
    out_dir = output_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Map renderer names to RenderMode
    mode_map = {
        "bbc": RenderMode.BBC,
        "fluidsynth": None,  # Special case - force FluidSynth
        "adaptive": RenderMode.ADAPTIVE,
        "multitrack": RenderMode.MULTITRACK,
        "auto": RenderMode.AUTO,
    }

    orchestra = await get_orchestra()

    audio_paths: dict[str, Path] = {}
    render_times: dict[str, float] = {}

    logger.info(f"🎵 A/B Comparison: {midi_path.name}")
    logger.info(f"   Renderers: {renderers}")

    for renderer in renderers:
        out_path = out_dir / f"{midi_path.stem}_{renderer}.wav"
        t0 = time.perf_counter()

        try:
            if renderer == "fluidsynth":
                # Force FluidSynth bypass
                result = await orchestra._render_fluidsynth(midi_path, out_path)
            else:
                mode = mode_map.get(renderer, RenderMode.AUTO)
                result = await orchestra.render(midi_path, out_path, mode=mode)

            render_time = time.perf_counter() - t0

            if result.success and result.path:
                audio_paths[renderer] = result.path
                render_times[renderer] = render_time
                logger.info(f"   ✓ {renderer}: {render_time:.1f}s")
            else:
                logger.warning(f"   ✗ {renderer}: {result.error}")

        except Exception as e:
            logger.error(f"   ✗ {renderer}: {e}")

    if not audio_paths:
        return ComparisonResult(
            success=False,
            midi_path=midi_path,
            renderers=renderers,
            audio_paths={},
            render_times={},
            error="All renders failed",
        )

    # Calculate comparison metrics if we have multiple renderings
    metrics = None
    if len(audio_paths) >= 2:
        metrics = await _calculate_metrics(audio_paths)

    return ComparisonResult(
        success=True,
        midi_path=midi_path,
        renderers=list(audio_paths.keys()),
        audio_paths=audio_paths,
        render_times=render_times,
        metrics=metrics,
    )


async def _calculate_metrics(
    audio_paths: dict[str, Path],
) -> dict[str, ComparisonMetrics]:
    """Calculate comparison metrics between audio files.

    Args:
        audio_paths: Dict mapping renderer name to audio path

    Returns:
        Dict mapping comparison pair to metrics
    """
    import soundfile as sf
    from scipy import signal

    metrics: dict[str, ComparisonMetrics] = {}

    # Load all audio
    audio_data: dict[str, tuple[NDArray, int]] = {}
    for name, path in audio_paths.items():
        try:
            audio, sr = sf.read(str(path), dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)  # Convert to mono for analysis
            audio_data[name] = (audio, sr)
        except Exception as e:
            logger.warning(f"Failed to load {name} for metrics: {e}")

    if len(audio_data) < 2:
        return metrics

    # Compare each pair
    names = list(audio_data.keys())
    for i, name_a in enumerate(names):
        for name_b in names[i + 1 :]:
            audio_a, sr_a = audio_data[name_a]
            audio_b, sr_b = audio_data[name_b]

            # Basic metrics
            rms_a = float(np.sqrt(np.mean(audio_a**2)))
            rms_b = float(np.sqrt(np.mean(audio_b**2)))
            peak_a = float(np.max(np.abs(audio_a)))
            peak_b = float(np.max(np.abs(audio_b)))
            duration_a = len(audio_a) / sr_a
            duration_b = len(audio_b) / sr_b

            # Cross-correlation (similarity measure)
            min_len = min(len(audio_a), len(audio_b))
            if min_len > 0:
                corr = np.correlate(audio_a[:min_len], audio_b[:min_len], mode="valid")
                norm = np.sqrt(np.sum(audio_a[:min_len] ** 2) * np.sum(audio_b[:min_len] ** 2))
                correlation = float(corr[0] / norm) if norm > 0 else 0.0
            else:
                correlation = 0.0

            # Spectral difference (using power spectra)
            nperseg = min(2048, min_len // 4)
            if nperseg > 64:
                _, psd_a = signal.welch(audio_a[:min_len], sr_a, nperseg=nperseg)
                _, psd_b = signal.welch(audio_b[:min_len], sr_b, nperseg=nperseg)

                # Normalize and compute difference
                psd_a = psd_a / (np.sum(psd_a) + 1e-10)
                psd_b = psd_b / (np.sum(psd_b) + 1e-10)
                spectral_diff = float(np.sum(np.abs(psd_a - psd_b)))
            else:
                spectral_diff = 1.0

            pair_key = f"{name_a}_vs_{name_b}"
            metrics[pair_key] = ComparisonMetrics(
                rms_a=rms_a,
                rms_b=rms_b,
                peak_a=peak_a,
                peak_b=peak_b,
                duration_a=duration_a,
                duration_b=duration_b,
                correlation=correlation,
                spectral_diff=spectral_diff,
            )

    return metrics


# =============================================================================
# Playback Functions
# =============================================================================


async def play_ab_comparison(
    midi_path: Path | str,
    delay_sec: float = 2.0,
    renderers: list[str] | None = None,
    volume: int = 25,
) -> ComparisonResult:
    """Render and play A/B comparison sequentially.

    Renders the MIDI with each backend, then plays them back-to-back
    with a configurable delay between each for listening comparison.

    Args:
        midi_path: Path to MIDI file
        delay_sec: Delay between playbacks in seconds
        renderers: Renderers to compare (default: ["bbc", "fluidsynth"])
        volume: Playback volume (0-100)

    Returns:
        ComparisonResult with render details
    """
    from kagami.core.effectors.orchestra import get_orchestra

    # Default to BBC vs FluidSynth
    if renderers is None:
        renderers = ["bbc", "fluidsynth"]

    # Render all versions
    result = await compare_renderers(midi_path, renderers)

    if not result.success:
        return result

    orchestra = await get_orchestra()

    # Play each rendering with delay
    logger.info(f"\n🎧 A/B Playback ({delay_sec}s delay between renderers):")

    for i, (renderer, audio_path) in enumerate(result.audio_paths.items()):
        if i > 0:
            logger.info(f"   ⏸ Waiting {delay_sec}s...")
            await asyncio.sleep(delay_sec)

        logger.info(f"   ▶ Playing: {renderer}")
        try:
            await orchestra.play(audio_path, volume=volume)
        except Exception as e:
            logger.warning(f"   ✗ Playback failed: {e}")

    return result


async def play_single_renderer(
    midi_path: Path | str,
    renderer: str = "adaptive",
    volume: int = 25,
) -> Path | None:
    """Render and play with a single renderer.

    Convenience function for quick rendering and playback.

    Args:
        midi_path: Path to MIDI file
        renderer: Renderer to use
        volume: Playback volume

    Returns:
        Path to rendered audio, or None on failure
    """
    from kagami.core.effectors.orchestra import RenderMode, get_orchestra

    mode_map = {
        "bbc": RenderMode.BBC,
        "fluidsynth": None,
        "adaptive": RenderMode.ADAPTIVE,
        "multitrack": RenderMode.MULTITRACK,
        "auto": RenderMode.AUTO,
    }

    orchestra = await get_orchestra()
    midi_path = Path(midi_path)

    out_path = OUTPUT_DIR / f"{midi_path.stem}_{renderer}.wav"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"🎵 Rendering with {renderer}...")

    if renderer == "fluidsynth":
        result = await orchestra._render_fluidsynth(midi_path, out_path)
    else:
        mode = mode_map.get(renderer, RenderMode.AUTO)
        result = await orchestra.render(midi_path, out_path, mode=mode)

    if not result.success:
        logger.error(f"Render failed: {result.error}")
        return None

    logger.info(f"▶ Playing {renderer} render...")
    await orchestra.play(result.path, volume=volume)

    return result.path


# =============================================================================
# Reporting Functions
# =============================================================================


def print_comparison_report(result: ComparisonResult) -> None:
    """Print a formatted comparison report.

    Args:
        result: ComparisonResult from compare_renderers()
    """
    if not result.success:
        print(f"❌ Comparison failed: {result.error}")
        return

    print(f"\n{'=' * 60}")
    print(f"A/B COMPARISON REPORT: {result.midi_path.name}")
    print(f"{'=' * 60}")

    # Render times
    print("\n📊 Render Times:")
    for renderer, t in sorted(result.render_times.items(), key=lambda x: x[1]):
        print(f"   {renderer:15} {t:.1f}s")

    # Audio files
    print("\n📁 Output Files:")
    for renderer, path in result.audio_paths.items():
        print(f"   {renderer:15} {path}")

    # Metrics
    if result.metrics:
        print("\n📈 Comparison Metrics:")
        for pair, m in result.metrics.items():
            print(f"\n   {pair}:")
            print(f"      RMS:         {m.rms_a:.4f} vs {m.rms_b:.4f}")
            print(f"      Peak:        {m.peak_a:.4f} vs {m.peak_b:.4f}")
            print(f"      Duration:    {m.duration_a:.1f}s vs {m.duration_b:.1f}s")
            print(f"      Correlation: {m.correlation:.4f}")
            print(f"      Spectral Δ:  {m.spectral_diff:.4f}")

    print(f"\n{'=' * 60}\n")


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Data classes
    "ComparisonMetrics",
    "ComparisonResult",
    # Functions
    "compare_renderers",
    "play_ab_comparison",
    "play_single_renderer",
    "print_comparison_report",
]
