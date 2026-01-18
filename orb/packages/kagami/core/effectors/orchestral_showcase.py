"""Orchestral Showcase Generator — Spatial Audio + Expressive Narration.

Creates a complete orchestral showcase with:
- Spatially positioned instruments in realistic orchestra layout
- Expressive narration using ElevenLabs v3 vocal tags
- Professional mixing with crossfades and normalization

SINGLE TTS CALL: All narration is generated in one call, then sliced.
This ensures consistent voice and is faster than many small calls.

Usage:
    from kagami.core.effectors.orchestral_showcase import (
        create_showcase,
        ORCHESTRA_LAYOUT,
        get_showcase_order,
    )

    # Generate complete showcase
    output_path = await create_showcase(
        render_dir=Path("~/.kagami/bbc_virtuoso/rendered"),
        output_path=Path("/tmp/orchestra_showcase.mp3"),
        include_narration=True,
    )

Created: January 1, 2026
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# Orchestral Seating Layout — Pan Positions
# =============================================================================
# Standard American seating with first violins left, seconds inside.
# Pan values: -1.0 (full left) to 1.0 (full right), 0.0 (center)


@dataclass(frozen=True)
class OrchestraSeat:
    """Position of an instrument in the orchestra."""

    pan: float  # -1 (left) to 1 (right)
    depth: float  # 0 (front) to 1 (back) - affects reverb mix
    section: str  # strings, woodwinds, brass, percussion
    row: int  # 1 = front, 4 = back


# Realistic orchestral layout - where instruments actually sit
ORCHESTRA_LAYOUT: dict[str, OrchestraSeat] = {
    # STRINGS - front of stage
    "violins_1": OrchestraSeat(-0.6, 0.15, "strings", 1),  # Far left front
    "violins_2": OrchestraSeat(-0.25, 0.2, "strings", 1),  # Inside left
    "violas": OrchestraSeat(0.25, 0.2, "strings", 1),  # Inside right
    "celli": OrchestraSeat(0.5, 0.25, "strings", 1),  # Right front
    "basses": OrchestraSeat(0.75, 0.35, "strings", 2),  # Far right, slightly back
    # WOODWINDS - center, behind strings
    "flute": OrchestraSeat(-0.2, 0.4, "woodwinds", 2),
    "flutes_a3": OrchestraSeat(-0.2, 0.4, "woodwinds", 2),
    "piccolo": OrchestraSeat(-0.3, 0.4, "woodwinds", 2),
    "oboe": OrchestraSeat(0.0, 0.4, "woodwinds", 2),
    "oboes_a3": OrchestraSeat(0.0, 0.4, "woodwinds", 2),
    "cor_anglais": OrchestraSeat(0.1, 0.45, "woodwinds", 2),
    "clarinet": OrchestraSeat(0.2, 0.4, "woodwinds", 2),
    "clarinets_a3": OrchestraSeat(0.2, 0.4, "woodwinds", 2),
    "bass_clarinet": OrchestraSeat(0.3, 0.45, "woodwinds", 2),
    "bassoon": OrchestraSeat(-0.1, 0.5, "woodwinds", 2),
    "bassoons_a3": OrchestraSeat(-0.1, 0.5, "woodwinds", 2),
    "contrabassoon": OrchestraSeat(0.0, 0.55, "woodwinds", 2),
    # BRASS - back center, elevated
    "horn": OrchestraSeat(-0.35, 0.6, "brass", 3),
    "horns_a4": OrchestraSeat(-0.35, 0.6, "brass", 3),
    "trumpet": OrchestraSeat(0.1, 0.65, "brass", 3),
    "trumpets_a2": OrchestraSeat(0.1, 0.65, "brass", 3),
    "tenor_trombone": OrchestraSeat(0.3, 0.65, "brass", 3),
    "tenor_trombones_a3": OrchestraSeat(0.3, 0.65, "brass", 3),
    "bass_trombones_a2": OrchestraSeat(0.4, 0.7, "brass", 3),
    "contrabass_trombone": OrchestraSeat(0.45, 0.7, "brass", 3),
    "tuba": OrchestraSeat(0.5, 0.7, "brass", 3),
    "cimbasso": OrchestraSeat(0.55, 0.7, "brass", 3),
    "contrabass_tuba": OrchestraSeat(0.6, 0.75, "brass", 3),
    # PERCUSSION - back, spread across stage
    "timpani": OrchestraSeat(-0.5, 0.8, "percussion", 4),  # Left back
    "harp": OrchestraSeat(-0.7, 0.5, "percussion", 2),  # Left side, forward
    "celeste": OrchestraSeat(-0.6, 0.55, "percussion", 2),
    "glockenspiel": OrchestraSeat(0.4, 0.8, "percussion", 4),
    "xylophone": OrchestraSeat(0.5, 0.8, "percussion", 4),
    "marimba": OrchestraSeat(0.3, 0.8, "percussion", 4),
    "vibraphone": OrchestraSeat(0.2, 0.8, "percussion", 4),
    "crotales": OrchestraSeat(0.6, 0.85, "percussion", 4),
    "tubular_bells": OrchestraSeat(0.7, 0.8, "percussion", 4),
    "untuned_percussion": OrchestraSeat(0.0, 0.85, "percussion", 4),  # Center back
}


# =============================================================================
# Showcase Ordering — Musical Flow
# =============================================================================


def get_showcase_order() -> list[str]:
    """Get the instrument order for the showcase.

    Ordered by section, then by musical logic (melodic → harmonic → bass).
    This creates a natural flow through the orchestra.

    Returns:
        List of instrument keys in showcase order
    """
    return [
        # STRINGS - melodic to bass
        "violins_1",
        "violins_2",
        "violas",
        "celli",
        "basses",
        # WOODWINDS - solo instruments first, then ensembles
        "flute",
        "oboe",
        "clarinet",
        "bassoon",
        "piccolo",
        "cor_anglais",
        "bass_clarinet",
        "contrabassoon",
        "flutes_a3",
        "oboes_a3",
        "clarinets_a3",
        "bassoons_a3",
        # BRASS - solo instruments first, then ensembles
        "horn",
        "trumpet",
        "tenor_trombone",
        "tuba",
        "cimbasso",
        "contrabass_trombone",
        "contrabass_tuba",
        "horns_a4",
        "trumpets_a2",
        "tenor_trombones_a3",
        "bass_trombones_a2",
        # PERCUSSION - pitched first, then unpitched
        "timpani",
        "harp",
        "celeste",
        "glockenspiel",
        "xylophone",
        "marimba",
        "vibraphone",
        "crotales",
        "tubular_bells",
        "untuned_percussion",
    ]


def get_section_for_instrument(instrument_key: str) -> str:
    """Get the section name for an instrument."""
    seat = ORCHESTRA_LAYOUT.get(instrument_key)
    if seat:
        return seat.section
    # Fallback based on key patterns
    if any(s in instrument_key for s in ["violin", "viola", "cell", "bass"]):
        if "contra" not in instrument_key and "tuba" not in instrument_key:
            return "strings"
    if any(
        w in instrument_key for w in ["flute", "oboe", "clarinet", "bassoon", "piccolo", "anglais"]
    ):
        return "woodwinds"
    if any(b in instrument_key for b in ["horn", "trumpet", "trombone", "tuba", "cimbasso"]):
        return "brass"
    return "percussion"


# =============================================================================
# Audio Processing
# =============================================================================


@dataclass
class AudioSegment:
    """A segment of audio with metadata."""

    path: Path
    duration_ms: float
    instrument_key: str | None = None
    is_narration: bool = False
    pan: float = 0.0


def get_audio_duration(path: Path) -> float:
    """Get duration of audio file in milliseconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip()) * 1000
    except Exception as e:
        logger.warning(f"Could not get duration for {path}: {e}")
        return 0


def apply_pan_to_stereo(pan: float) -> tuple[float, float]:
    """Convert pan value to stereo channel gains.

    Uses constant-power panning for natural stereo image.

    Args:
        pan: -1 (left) to 1 (right)

    Returns:
        Tuple of (left_gain, right_gain)
    """
    # Constant power panning
    angle = (pan + 1) * np.pi / 4  # 0 to pi/2
    left = np.cos(angle)
    right = np.sin(angle)
    return float(left), float(right)


async def synthesize_narration(
    text: str,
    output_path: Path,
    colony: str = "kagami",
) -> bool:
    """Synthesize narration using KagamiVoice with V3 model.

    Args:
        text: Expressive text with v3 tags
        output_path: Where to save the audio
        colony: Voice personality

    Returns:
        True if successful
    """
    try:
        from kagami.core.services.voice.kagami_voice import Model, get_kagami_voice

        voice = await get_kagami_voice()
        result = await voice.synthesize(text, colony=colony, model=Model.V3)

        if result.success and result.audio_path:
            # Copy to output path
            import shutil

            shutil.copy(result.audio_path, output_path)
            return True
        return False

    except Exception as e:
        logger.error(f"Narration synthesis failed: {e}")
        return False


# =============================================================================
# Timestamp-Based Splitting (The Clever Way)
# =============================================================================

# DELIMITER is imported from orchestra_script.py


def _find_delimiter_times(
    alignment: list[tuple[float, float, str]],
    delimiter: str = "|||",
) -> list[float]:
    """Find timestamps where delimiter appears in alignment data.

    Returns list of timestamps (middle of delimiter).
    """
    split_times = []

    # Build full text from alignment
    chars = [c for _, _, c in alignment]
    text = "".join(chars)

    # Find all occurrences of delimiter
    idx = 0
    while True:
        pos = text.find(delimiter, idx)
        if pos == -1:
            break

        # Get timestamp at middle of delimiter
        mid_pos = pos + len(delimiter) // 2
        if mid_pos < len(alignment):
            _, end_time, _ = alignment[mid_pos]
            split_times.append(end_time)

        idx = pos + 1

    return split_times


def _split_at_timestamps(
    audio_path: Path,
    output_dir: Path,
    split_times: list[float],
) -> list[Path]:
    """Split audio at exact timestamps.

    Args:
        audio_path: Source audio
        output_dir: Where to save slices
        split_times: List of times (seconds) to split at

    Returns:
        List of paths to split segments
    """
    duration = get_audio_duration(audio_path) / 1000

    # Build boundaries: [0, t1, t2, ..., duration]
    boundaries = [0.0, *sorted(split_times), duration]

    output_paths = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]

        # Small trim to remove delimiter sound
        trim_start = start + 0.15 if i > 0 else start
        trim_end = end - 0.15 if i < len(boundaries) - 2 else end

        out_path = output_dir / f"slice_{i:03d}.mp3"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-ss",
            str(trim_start),
            "-to",
            str(trim_end),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(out_path),
        ]
        subprocess.run(cmd, capture_output=True)

        if out_path.exists() and out_path.stat().st_size > 0:
            output_paths.append(out_path)
            logger.debug(f"  Slice {i}: {trim_start:.2f}s - {trim_end:.2f}s")

    return output_paths


# =============================================================================
# Main Showcase Generation
# =============================================================================


async def create_showcase(
    render_dir: Path,
    output_path: Path,
    include_narration: bool = True,
    crossfade_ms: float = 500,
    gap_ms: float = 1500,
    normalize: bool = True,
) -> Path | None:
    """Create the complete orchestral showcase with narration.

    Generates ONE TTS call for all narration, then slices and mixes.
    This ensures consistent voice and faster generation.

    Args:
        render_dir: Directory containing rendered WAV files
        output_path: Where to save the final MP3
        include_narration: Whether to include voice narration
        crossfade_ms: Crossfade duration (currently unused, using gaps)
        gap_ms: Gap between segments in milliseconds
        normalize: Whether to normalize final output

    Returns:
        Path to created MP3 or None if failed
    """
    from kagami.core.services.voice.orchestra_script import (
        DELIMITER,
        get_segment_keys,
    )

    render_dir = Path(render_dir).expanduser()
    output_path = Path(output_path).expanduser()

    # Create temp directory for intermediate files
    with tempfile.TemporaryDirectory(prefix="showcase_") as temp_dir:
        temp_path = Path(temp_dir)

        get_showcase_order()

        # The script has everything pre-ordered with segment keys
        segment_keys = get_segment_keys() if include_narration else []

        # Generate TTS in batches (5000 char limit per call)
        narration_map: dict[str, Path] = {}
        MAX_CHARS = 4500  # Leave buffer

        if include_narration and segment_keys:
            from kagami.core.services.voice.orchestra_script import get_segment

            try:
                from kagami.core.services.voice.kagami_voice import Model, get_kagami_voice

                voice = await get_kagami_voice()

                # Build batches that fit under the limit
                batches: list[list[str]] = []
                current_batch: list[str] = []
                current_chars = 0

                for key in segment_keys:
                    text = get_segment(key)
                    text_len = len(text) + len(DELIMITER)

                    if current_chars + text_len > MAX_CHARS and current_batch:
                        batches.append(current_batch)
                        current_batch = []
                        current_chars = 0

                    current_batch.append(key)
                    current_chars += text_len

                if current_batch:
                    batches.append(current_batch)

                logger.info(
                    f"Synthesizing {len(segment_keys)} segments in {len(batches)} batches..."
                )

                # Process each batch
                for batch_idx, batch_keys in enumerate(batches):
                    batch_script = DELIMITER.join(get_segment(k) for k in batch_keys)
                    logger.info(
                        f"Batch {batch_idx + 1}/{len(batches)}: {len(batch_keys)} segments, {len(batch_script)} chars"
                    )

                    # Retry on server errors
                    for attempt in range(3):
                        result, alignment = await voice.synthesize_with_timestamps(
                            batch_script, Model.V3
                        )
                        if result.success:
                            break
                        if "500" in str(result.error):
                            logger.warning(f"Server error, retry {attempt + 1}/3...")
                            await asyncio.sleep(2)
                        else:
                            break

                    if result.success and result.audio_path and alignment:
                        # Ensure output dir exists FIRST
                        batch_dir = temp_path / f"batch_{batch_idx}"
                        batch_dir.mkdir(exist_ok=True)

                        # Find delimiter timestamps
                        split_times = _find_delimiter_times(alignment, "|||")

                        # Split at exact timestamps
                        sliced_paths = _split_at_timestamps(
                            result.audio_path,
                            batch_dir,
                            split_times,
                        )

                        logger.info(f"  Split into {len(sliced_paths)} slices")

                        # Map slices back to their keys
                        for i, key in enumerate(batch_keys):
                            if i < len(sliced_paths):
                                narration_map[key] = sliced_paths[i]
                    else:
                        logger.error(f"Batch {batch_idx + 1} failed: {result.error}")

                logger.info(f"Synthesized {len(narration_map)}/{len(segment_keys)} segments")

            except Exception as e:
                logger.error(f"Timestamp synthesis failed: {e}")

        # Build segments in script order (narration keys align with instrument order)
        segments: list[AudioSegment] = []

        for key in segment_keys:
            # Add narration for this key
            if key in narration_map:
                segments.append(
                    AudioSegment(
                        path=narration_map[key],
                        duration_ms=get_audio_duration(narration_map[key]),
                        instrument_key=key
                        if not key.startswith(("intro", "section_", "finale"))
                        else None,
                        is_narration=True,
                        pan=0.0,  # Narration always center
                    )
                )

            # If this is an instrument key (not intro/section/finale), add the audio
            if not key.startswith(("intro", "section_", "finale")):
                wav_path = render_dir / f"{key}_virtuoso.wav"
                if wav_path.exists():
                    seat = ORCHESTRA_LAYOUT.get(key, OrchestraSeat(0.0, 0.5, "misc", 2))
                    segments.append(
                        AudioSegment(
                            path=wav_path,
                            duration_ms=get_audio_duration(wav_path),
                            instrument_key=key,
                            is_narration=False,
                            pan=seat.pan,
                        )
                    )

        if not segments:
            logger.error("No segments to process!")
            return None

        logger.info(f"Mixing {len(segments)} segments...")

        output_mp3 = await _mix_segments_ffmpeg(segments, output_path, temp_path, gap_ms, normalize)

        return output_mp3


async def _mix_segments_ffmpeg(
    segments: list[AudioSegment],
    output_path: Path,
    temp_dir: Path,
    gap_ms: float,
    normalize: bool,
) -> Path | None:
    """Mix segments using ffmpeg with panning.

    This uses ffmpeg's adelay and pan filters to create
    proper spatial positioning and sequencing.
    """
    # Create concat file with silence gaps
    concat_file = temp_dir / "concat.txt"

    # Generate silence file for gaps
    silence_path = temp_dir / "silence.wav"
    silence_dur = gap_ms / 1000
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=48000:cl=stereo:d={silence_dur}",
            "-c:a",
            "pcm_s16le",
            str(silence_path),
        ],
        capture_output=True,
        check=True,
    )

    # Process each segment with panning
    processed_files = []
    for i, seg in enumerate(segments):
        processed_path = temp_dir / f"proc_{i:03d}.wav"

        # Apply panning
        left_gain, right_gain = apply_pan_to_stereo(seg.pan)

        # Convert to stereo with panning
        pan_filter = f"pan=stereo|c0={left_gain}*c0|c1={right_gain}*c0"
        if seg.path.suffix.lower() == ".wav":
            # Check if already stereo
            probe_result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-show_entries",
                    "stream=channels",
                    "-of",
                    "csv=p=0",
                    str(seg.path),
                ],
                capture_output=True,
                text=True,
            )
            channels = probe_result.stdout.strip().split("\n")[0] if probe_result.stdout else "1"
            if channels == "2":
                # Already stereo, just apply pan adjustment
                pan_filter = f"pan=stereo|c0={left_gain}*c0+{left_gain}*c1|c1={right_gain}*c0+{right_gain}*c1"

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(seg.path),
                "-af",
                f"aresample=48000,{pan_filter}",
                "-c:a",
                "pcm_s16le",
                str(processed_path),
            ],
            capture_output=True,
            check=True,
        )

        processed_files.append(processed_path)

    # Write concat file
    with open(concat_file, "w") as f:
        for i, pf in enumerate(processed_files):
            f.write(f"file '{pf}'\n")
            # Add silence gap after each segment (except last)
            if i < len(processed_files) - 1:
                f.write(f"file '{silence_path}'\n")

    # Concatenate all
    concat_output = temp_dir / "concatenated.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c:a",
            "pcm_s16le",
            str(concat_output),
        ],
        capture_output=True,
        check=True,
    )

    # Final encode to MP3 with optional normalization
    filters = []
    if normalize:
        filters.append("loudnorm=I=-14:LRA=11:TP=-1")

    filter_str = ",".join(filters) if filters else None

    cmd = ["ffmpeg", "-y", "-i", str(concat_output)]
    if filter_str:
        cmd.extend(["-af", filter_str])
    cmd.extend(["-c:a", "libmp3lame", "-q:a", "2", str(output_path)])

    result = subprocess.run(cmd, capture_output=True)

    if result.returncode == 0 and output_path.exists():
        logger.info(f"✓ Showcase created: {output_path}")
        return output_path
    else:
        logger.error(f"FFmpeg error: {result.stderr.decode()}")
        return None


__all__ = [
    "ORCHESTRA_LAYOUT",
    # Processing
    "AudioSegment",
    # Layout
    "OrchestraSeat",
    "apply_pan_to_stereo",
    "create_showcase",
    "get_audio_duration",
    "get_section_for_instrument",
    # Order
    "get_showcase_order",
    # Generation
    "synthesize_narration",
]
