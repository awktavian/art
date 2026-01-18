"""Parallel Orchestral Rendering.

Renders instruments in parallel via concurrent REAPER instances,
then mixes with VBAP spatialization.

IMPORTANT: BBC Symphony Orchestra requires 1x offline render mode.
This means parallel rendering is limited by real-time - each track
takes approximately its duration to render, not faster.

Strategy:
1. Split MIDI into per-instrument files
2. Create per-instrument REAPER projects (with RENDER_1X 1)
3. Render instruments in parallel batches (limited by RAM)
4. Mix with VBAP spatial positioning
5. Output final spatialized audio

For a 60s piece with 8 instruments:
- Serial: ~60s * 8 = 480s
- Parallel (4 workers): ~60s * 2 batches = 120s

Colony: Forge (e₂)
Created: January 2, 2026
Updated: January 2, 2026 - 1x offline mode for BBC SO sample streaming
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Max parallel REAPER instances (limited by CPU/RAM)
MAX_PARALLEL_RENDERS = min(os.cpu_count() or 4, 8)

# Default spatial positions for orchestra sections (azimuth, elevation, distance)
ORCHESTRA_POSITIONS = {
    # Strings - front arc
    "violins_1": (-30, 0, 5),
    "violins_2": (-15, 0, 5),
    "violas": (0, 0, 5),
    "celli": (15, 0, 5),
    "basses": (30, 0, 6),
    # Woodwinds - behind strings
    "flute": (-20, 5, 7),
    "flutes": (-20, 5, 7),
    "oboe": (-10, 5, 7),
    "oboes": (-10, 5, 7),
    "clarinet": (10, 5, 7),
    "clarinets": (10, 5, 7),
    "bassoon": (20, 5, 7),
    "bassoons": (20, 5, 7),
    # Brass - back
    "horn": (-25, 10, 9),
    "horns": (-25, 10, 9),
    "trumpet": (-10, 10, 9),
    "trumpets": (-10, 10, 9),
    "tenor_trombone": (10, 10, 9),
    "trombones_tenor": (10, 10, 9),
    "bass_trombone": (15, 10, 9),
    "trombones_bass": (15, 10, 9),
    "tuba": (25, 10, 9),
    # Percussion - back/sides
    "timpani": (35, 5, 10),
    "piano": (-40, 0, 6),
    "harp": (-35, 0, 6),
}


@dataclass
class TrackRenderJob:
    """A single track render job."""

    track_name: str
    instrument_key: str
    midi_path: Path
    output_path: Path
    project_path: Path | None = None
    position: tuple[float, float, float] = (0, 0, 5)


@dataclass
class ParallelRenderResult:
    """Result of parallel rendering."""

    success: bool
    output_path: Path | None = None
    duration: float = 0.0
    tracks_rendered: int = 0
    tracks_failed: int = 0
    render_time: float = 0.0
    error: str | None = None
    track_results: list[dict[str, Any]] | None = None


# =============================================================================
# Single Track Rendering (runs in subprocess)
# =============================================================================


def _render_single_track(
    job: TrackRenderJob,
    timeout: int = 120,
    sample_preload_wait: float = 3.0,
) -> dict[str, Any]:
    """Render a single track via REAPER (runs in separate process).

    With BBC SO's RENDER_1X 1 mode, rendering takes approximately real-time.
    We add sample preload wait for initial sample loading.

    Args:
        job: Track render job
        timeout: Render timeout (should be > duration + preload for 1x mode)
        sample_preload_wait: Seconds to wait for sample preloading

    Returns:
        Dict with success, output_path, error
    """
    import subprocess
    import time
    from pathlib import Path

    result = {
        "track_name": job.track_name,
        "instrument_key": job.instrument_key,
        "success": False,
        "output_path": None,
        "error": None,
    }

    try:
        if not job.project_path or not job.project_path.exists():
            result["error"] = "No project file"
            return result

        REAPER_APP = Path("/Applications/REAPER.app/Contents/MacOS/REAPER")
        if not REAPER_APP.exists():
            result["error"] = "REAPER not found"
            return result

        cmd = [
            "nice",
            "-n",
            "10",
            str(REAPER_APP),
            "-nosplash",
            "-newinst",  # New instance for parallel safety
            "-renderproject",
            str(job.project_path),
        ]

        # Start render process
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        # Wait for sample preloading (BBC SO needs time to load samples)
        if sample_preload_wait > 0:
            time.sleep(sample_preload_wait)

        # Wait for render completion (1x mode = approximately real-time)
        proc.wait(timeout=timeout)

        if job.output_path.exists():
            result["success"] = True
            result["output_path"] = str(job.output_path)
        else:
            result["error"] = "No output file"

    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        result["error"] = f"Timeout ({timeout}s) - increase for 1x offline mode"
    except Exception as e:
        result["error"] = str(e)

    return result


# =============================================================================
# Parallel Rendering
# =============================================================================


async def render_parallel(
    midi_path: Path,
    output_path: Path,
    max_workers: int = MAX_PARALLEL_RENDERS,
    timeout_per_track: int = 120,
    apply_spatial: bool = True,
) -> ParallelRenderResult:
    """Render orchestral MIDI with parallel instrument rendering.

    Workflow:
    1. Analyze MIDI → detect instruments
    2. Apply expression (keyswitches for sustained)
    3. Split MIDI by instrument
    4. Create per-instrument REAPER projects
    5. Render ALL in parallel (concurrent REAPER instances)
    6. Mix with VBAP spatial positioning
    7. Output final audio

    Args:
        midi_path: Input MIDI file
        output_path: Final output WAV
        max_workers: Max parallel REAPER instances
        timeout_per_track: Timeout per track render
        apply_spatial: Apply VBAP spatialization

    Returns:
        ParallelRenderResult
    """
    t0 = time.perf_counter()

    if not midi_path.exists():
        return ParallelRenderResult(success=False, error=f"MIDI not found: {midi_path}")

    logger.info("🎼 Parallel Render: %s (max %d workers)", midi_path.name, max_workers)

    try:
        # Import dependencies
        from kagami.core.effectors.expression_engine import ExpressionStyle, add_expression
        from kagami.core.effectors.renderers.reaper import analyze_midi, split_midi_by_instrument
        from kagami.core.effectors.renderers.reaper_project import (
            generate_reaper_project,
            get_rfxchain_path,
        )

        # 1. Analyze MIDI
        logger.info("   1/6 Analyzing MIDI...")
        tracks = await analyze_midi(midi_path)
        if not tracks:
            return ParallelRenderResult(success=False, error="No instruments found")
        logger.info("       → %d instruments", len(tracks))

        # 2. Apply expression
        logger.info("   2/6 Applying expression...")
        work_dir = output_path.parent / f"parallel_work_{output_path.stem}"
        work_dir.mkdir(parents=True, exist_ok=True)

        expressed_path = work_dir / f"{midi_path.stem}_expressed.mid"
        await add_expression(midi_path, expressed_path, style=ExpressionStyle.FILM_SCORE)

        # 3. Split MIDI
        logger.info("   3/6 Splitting MIDI...")
        split_paths = await split_midi_by_instrument(expressed_path, tracks)

        # 4. Create per-instrument projects
        logger.info("   4/6 Creating %d REAPER projects...", len(tracks))
        jobs: list[TrackRenderJob] = []

        for track in tracks:
            if track.key not in split_paths:
                continue

            try:
                get_rfxchain_path(track.key)  # Verify RFX chain exists
            except FileNotFoundError:
                logger.warning("       Skipping %s (no RFX chain)", track.key)
                continue

            track_output = work_dir / f"{track.key}.wav"
            track_midi = split_paths[track.key]

            # Create single-track project
            project_path = generate_reaper_project(
                midi_path=track_midi,
                tracks=[(track.name, track.key, track.pan)],
                output_dir=work_dir,
                output_name=track.key,
                tempo=120.0,
                duration=track.duration_sec + 2,
                split_midi_paths={track.key: track_midi},
            )

            # Get spatial position
            position = ORCHESTRA_POSITIONS.get(track.key, (0, 0, 5))

            jobs.append(
                TrackRenderJob(
                    track_name=track.name,
                    instrument_key=track.key,
                    midi_path=track_midi,
                    output_path=track_output,
                    project_path=project_path,
                    position=position,
                )
            )

        if not jobs:
            return ParallelRenderResult(success=False, error="No tracks to render")

        # 5. Render in parallel
        # For BBC SO 1x mode, each track takes approximately its duration
        # Adjust timeout per track based on actual duration
        max_duration = max(j.midi_path.stat().st_size for j in jobs) / 1000  # Rough estimate
        actual_timeout = max(timeout_per_track, int(max_duration) + 30)

        logger.info(
            "   5/6 Rendering %d tracks in parallel (1x mode, ~%ds timeout)...",
            len(jobs),
            actual_timeout,
        )

        # Use ThreadPoolExecutor to run subprocess renders concurrently
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                loop.run_in_executor(
                    executor,
                    _render_single_track,
                    job,
                    actual_timeout,
                    5.0,  # sample_preload_wait
                )
                for job in jobs
            ]
            results = await asyncio.gather(*futures)

        # Count successes/failures
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]

        logger.info("       → %d succeeded, %d failed", len(successes), len(failures))
        for f in failures:
            logger.warning("         ✗ %s: %s", f["track_name"], f["error"])

        if not successes:
            return ParallelRenderResult(
                success=False,
                error="All tracks failed to render",
                tracks_failed=len(failures),
                track_results=results,
            )

        # 6. Mix with spatial positioning
        logger.info("   6/6 Mixing with VBAP spatialization...")

        final_audio, sample_rate = await _mix_spatial(
            track_results=successes,
            jobs=jobs,
            apply_spatial=apply_spatial,
        )

        if final_audio is None:
            return ParallelRenderResult(
                success=False,
                error="Mixing failed",
                tracks_rendered=len(successes),
                tracks_failed=len(failures),
            )

        # Write output
        import soundfile as sf

        sf.write(str(output_path), final_audio.T, sample_rate)

        render_time = time.perf_counter() - t0
        duration = final_audio.shape[1] / sample_rate

        logger.info(
            "   ✓ Complete: %.1fs audio in %.1fs (%.1fx realtime)",
            duration,
            render_time,
            duration / render_time if render_time > 0 else 0,
        )

        return ParallelRenderResult(
            success=True,
            output_path=output_path,
            duration=duration,
            tracks_rendered=len(successes),
            tracks_failed=len(failures),
            render_time=render_time,
            track_results=results,
        )

    except Exception as e:
        logger.exception("Parallel render failed: %s", e)
        return ParallelRenderResult(success=False, error=str(e))


async def _mix_spatial(
    track_results: list[dict[str, Any]],
    jobs: list[TrackRenderJob],
    apply_spatial: bool = True,
) -> tuple[np.ndarray | None, int]:
    """Mix rendered tracks with VBAP spatialization.

    Args:
        track_results: Successful render results
        jobs: Original render jobs (for position info)
        apply_spatial: Apply VBAP positioning

    Returns:
        Tuple of (mixed audio array (channels x samples), sample_rate) or (None, 0) on failure
    """
    import soundfile as sf

    # Build job lookup
    job_by_key = {j.instrument_key: j for j in jobs}

    # Load all tracks
    track_audio = []
    silent_tracks = []
    detected_sr = None

    for result in track_results:
        output_path = Path(result["output_path"])
        if not output_path.exists():
            continue

        audio, sr = sf.read(str(output_path))

        # Use first file's sample rate as reference
        if detected_sr is None:
            detected_sr = sr
        elif sr != detected_sr:
            logger.warning(
                "       %s has different sample rate (%d vs %d), skipping",
                result["instrument_key"],
                sr,
                detected_sr,
            )
            continue

        # Check for silence
        peak = np.max(np.abs(audio))
        if peak < 0.001:
            silent_tracks.append(result["instrument_key"])
            continue  # Skip silent tracks

        # Ensure stereo
        if audio.ndim == 1:
            audio = np.stack([audio, audio])
        elif audio.ndim == 2:
            audio = audio.T  # (samples, channels) -> (channels, samples)

        job = job_by_key.get(result["instrument_key"])
        position = job.position if job else (0, 0, 5)

        track_audio.append(
            {
                "audio": audio,
                "position": position,
                "key": result["instrument_key"],
                "sr": sr,
            }
        )

    if silent_tracks:
        logger.warning("       Skipping %d silent tracks: %s", len(silent_tracks), silent_tracks)

    if not track_audio:
        logger.error("       No tracks with audio to mix!")
        return None, 0

    sample_rate = detected_sr or 48000

    # Find max length
    max_samples = max(t["audio"].shape[1] for t in track_audio)

    if apply_spatial:
        # 10-channel VBAP output (5.1.4)
        from kagami.core.effectors.vbap_core import vbap_10ch

        output = np.zeros((10, max_samples), dtype=np.float32)

        for track in track_audio:
            audio = track["audio"]
            az, el, dist = track["position"]

            # Pad to max length
            if audio.shape[1] < max_samples:
                pad = max_samples - audio.shape[1]
                audio = np.pad(audio, ((0, 0), (0, pad)))

            # Mono mix for VBAP
            mono = np.mean(audio, axis=0)

            # Compute VBAP gains
            gains = vbap_10ch(az, el, dist)

            # Apply gains to each channel
            for ch, gain in enumerate(gains):
                if gain > 0.001:
                    output[ch] += mono * gain

        # Normalize
        peak = np.max(np.abs(output))
        if peak > 0:
            output = output / peak * 0.95

        return output, sample_rate

    else:
        # Simple stereo mix
        output = np.zeros((2, max_samples), dtype=np.float32)

        for track in track_audio:
            audio = track["audio"]

            # Pad to max length
            if audio.shape[1] < max_samples:
                pad = max_samples - audio.shape[1]
                audio = np.pad(audio, ((0, 0), (0, pad)))

            output += audio[:2]

        # Normalize
        peak = np.max(np.abs(output))
        if peak > 0:
            output = output / peak * 0.95

        return output, sample_rate


# =============================================================================
# Convenience Functions
# =============================================================================


async def render_orchestra_parallel(
    midi_path: str | Path,
    output_path: str | Path,
    max_workers: int = MAX_PARALLEL_RENDERS,
    spatial: bool = True,
) -> ParallelRenderResult:
    """Convenience wrapper for parallel orchestral rendering.

    Args:
        midi_path: Input MIDI file
        output_path: Output WAV file
        max_workers: Max parallel renders
        spatial: Apply VBAP spatialization

    Returns:
        ParallelRenderResult
    """
    return await render_parallel(
        midi_path=Path(midi_path),
        output_path=Path(output_path),
        max_workers=max_workers,
        apply_spatial=spatial,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MAX_PARALLEL_RENDERS",
    "ORCHESTRA_POSITIONS",
    "ParallelRenderResult",
    "TrackRenderJob",
    "render_orchestra_parallel",
    "render_parallel",
]
