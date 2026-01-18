"""Spatial Mixer — Orchestral Spatialization with Proper Gain Staging.

Professional-grade spatial mixing for orchestral renders:
- Equal-power panning
- VBAP-style spatial positioning
- Binaural conversion for headphones
- Loudness normalization

Created: January 6, 2026
"""

from __future__ import annotations

import logging
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kagami.core.effectors.audio_verification import check_audio_exists
from kagami.core.effectors.virtuoso_orchestra import get_virtuoso_position

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# FFmpeg paths
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"

# Output formats
FORMAT_WAV = "wav"
FORMAT_M4A = "m4a"
FORMAT_MP3 = "mp3"

# Quality settings
AAC_BITRATE = "256k"
MP3_BITRATE = "320k"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class StemMixConfig:
    """Configuration for a single stem in the mix."""

    name: str
    path: Path
    pan: float = 0.0  # -1.0 (left) to 1.0 (right)
    gain_db: float = 0.0  # Gain adjustment in dB
    mute: bool = False


@dataclass
class MixConfig:
    """Configuration for spatial mixing."""

    output_format: str = FORMAT_M4A
    sample_rate: int = 48000
    normalize_loudness: bool = True
    target_lufs: float = -16.0
    binaural: bool = True  # Convert to binaural for headphones
    reverb_amount: float = 0.1  # Light reverb for cohesion
    master_gain_db: float = 0.0


# =============================================================================
# Panning Functions
# =============================================================================


def equal_power_pan(pan: float) -> tuple[float, float]:
    """Calculate equal-power pan gains.

    Equal-power panning maintains constant perceived volume
    as sound moves across the stereo field.

    Args:
        pan: -1.0 (full left) to 1.0 (full right)

    Returns:
        Tuple of (left_gain, right_gain)
    """
    # Clamp pan to valid range
    pan = max(-1.0, min(1.0, pan))

    # Convert to angle (0 to pi/2)
    theta = (pan + 1) * math.pi / 4

    left_gain = math.cos(theta)
    right_gain = math.sin(theta)

    return left_gain, right_gain


def azimuth_to_pan(azimuth: float) -> float:
    """Convert azimuth angle to pan value.

    Args:
        azimuth: -90 (far left) to +90 (far right) degrees

    Returns:
        Pan value -1.0 to 1.0
    """
    return max(-1.0, min(1.0, azimuth / 90.0))


# =============================================================================
# FFmpeg Filter Generation
# =============================================================================


def generate_pan_filter(pan: float) -> str:
    """Generate FFmpeg pan filter for equal-power panning.

    Args:
        pan: -1.0 to 1.0

    Returns:
        FFmpeg filter string
    """
    left, right = equal_power_pan(pan)
    return f"pan=stereo|FL={left:.4f}*FL+{left:.4f}*FR|FR={right:.4f}*FL+{right:.4f}*FR"


def generate_gain_filter(gain_db: float) -> str:
    """Generate FFmpeg volume filter.

    Args:
        gain_db: Gain in dB

    Returns:
        FFmpeg filter string
    """
    if abs(gain_db) < 0.1:
        return ""
    return f"volume={gain_db}dB"


def generate_binaural_filter() -> str:
    """Generate FFmpeg binaural (HRTF) filter.

    Uses the earwax filter for simple binaural conversion.
    For more sophisticated HRTF, use sofalizer with SOFA files.

    Returns:
        FFmpeg filter string
    """
    return "earwax"


def generate_reverb_filter(amount: float = 0.1) -> str:
    """Generate FFmpeg reverb filter.

    Args:
        amount: Reverb mix amount (0.0-1.0)

    Returns:
        FFmpeg filter string
    """
    if amount < 0.01:
        return ""
    # aecho: in_gain | out_gain | delays | decays
    return "aecho=0.8:0.9:40|120|200:0.3|0.2|0.15"


# =============================================================================
# Core Mixing Functions
# =============================================================================


def mix_stems(
    stems: list[StemMixConfig],
    output_path: Path,
    config: MixConfig | None = None,
) -> tuple[bool, str]:
    """Mix multiple stems into a single file with spatial positioning.

    Args:
        stems: List of stem configurations
        output_path: Output file path
        config: Mix configuration

    Returns:
        Tuple of (success, error_message)
    """
    if config is None:
        config = MixConfig()

    # Filter out muted and missing stems
    active_stems = []
    for stem in stems:
        if stem.mute:
            continue
        if not stem.path.exists():
            logger.warning("Stem not found: %s", stem.path)
            continue
        if not check_audio_exists(stem.path):
            logger.warning("Stem is silent: %s", stem.name)
            continue
        active_stems.append(stem)

    if not active_stems:
        return False, "No valid stems to mix"

    logger.info("Mixing %d stems to %s", len(active_stems), output_path.name)

    # Build FFmpeg command
    cmd = [FFMPEG, "-y"]

    # Add inputs
    for stem in active_stems:
        cmd.extend(["-i", str(stem.path)])

    # Build filter graph
    filter_parts = []

    # Process each input
    for i, stem in enumerate(active_stems):
        filters = []

        # Pan filter
        if abs(stem.pan) > 0.01:
            filters.append(generate_pan_filter(stem.pan))

        # Gain filter
        if abs(stem.gain_db) > 0.1:
            filters.append(generate_gain_filter(stem.gain_db))

        # Apply filters or pass through
        if filters:
            filter_chain = ",".join(filters)
            filter_parts.append(f"[{i}:a]{filter_chain}[s{i}]")
        else:
            filter_parts.append(f"[{i}:a]acopy[s{i}]")

    # Mix all streams
    mix_inputs = "".join(f"[s{i}]" for i in range(len(active_stems)))
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(active_stems)}:duration=longest:normalize=0[mixed]"
    )

    # Apply master processing
    master_filters = ["[mixed]"]

    # Master gain
    if abs(config.master_gain_db) > 0.1:
        master_filters.append(f"volume={config.master_gain_db}dB")

    # Reverb for cohesion
    if config.reverb_amount > 0.01:
        reverb = generate_reverb_filter(config.reverb_amount)
        if reverb:
            master_filters.append(reverb)

    # Binaural conversion
    if config.binaural:
        master_filters.append(generate_binaural_filter())

    # Loudness normalization
    if config.normalize_loudness:
        master_filters.append(f"loudnorm=I={config.target_lufs}:TP=-1.5:LRA=11")

    # Limiter to prevent clipping
    master_filters.append("alimiter=limit=0.95:attack=5:release=50")

    # Join master chain
    if len(master_filters) > 1:
        filter_parts.append(",".join(master_filters) + "[out]")
    else:
        filter_parts.append("[mixed]acopy[out]")

    # Complete filter graph
    filter_graph = ";".join(filter_parts)
    cmd.extend(["-filter_complex", filter_graph])
    cmd.extend(["-map", "[out]"])

    # Output format
    if config.output_format == FORMAT_M4A:
        cmd.extend(["-c:a", "aac", "-b:a", AAC_BITRATE])
    elif config.output_format == FORMAT_MP3:
        cmd.extend(["-c:a", "libmp3lame", "-b:a", MP3_BITRATE])
    else:  # WAV
        cmd.extend(["-c:a", "pcm_s24le"])

    cmd.extend(["-ar", str(config.sample_rate)])
    cmd.append(str(output_path))

    # Run FFmpeg
    logger.debug("FFmpeg command: %s", " ".join(cmd[:10]) + "...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        if result.returncode != 0:
            logger.error("FFmpeg error: %s", result.stderr[-500:] if result.stderr else "Unknown")
            return False, f"FFmpeg failed: {result.stderr[-200:] if result.stderr else 'Unknown'}"

        if not output_path.exists():
            return False, "Output file not created"

        size_mb = output_path.stat().st_size / 1024 / 1024
        logger.info("✓ Mixed to %s (%.1fMB)", output_path.name, size_mb)
        return True, ""

    except subprocess.TimeoutExpired:
        return False, "FFmpeg timeout"
    except Exception as e:
        return False, str(e)


def mix_orchestral_stems(
    stems_dir: Path,
    output_path: Path,
    config: MixConfig | None = None,
) -> tuple[bool, str]:
    """Mix all WAV stems in a directory using orchestral positions.

    Automatically applies spatial positioning based on instrument names
    using VIRTUOSO_POSITIONS.

    Args:
        stems_dir: Directory containing WAV stems
        output_path: Output file path
        config: Mix configuration

    Returns:
        Tuple of (success, error_message)
    """
    # Find all WAV files
    wav_files = sorted(stems_dir.glob("*.wav"))
    if not wav_files:
        return False, f"No WAV files in {stems_dir}"

    # Build stem configs
    stems = []
    for wav in wav_files:
        stem_name = wav.stem

        # Get orchestral position
        pos = get_virtuoso_position(stem_name)
        pan = azimuth_to_pan(pos.azimuth)

        stems.append(
            StemMixConfig(
                name=stem_name,
                path=wav,
                pan=pan,
            )
        )

        logger.debug("  %s: azimuth=%.0f° pan=%.2f", stem_name, pos.azimuth, pan)

    return mix_stems(stems, output_path, config)


# =============================================================================
# Convenience Functions
# =============================================================================


def create_spatial_mix(
    stems_dir: Path,
    output_name: str,
    output_format: str = FORMAT_M4A,
) -> Path | None:
    """Create a spatial mix from stems directory.

    Args:
        stems_dir: Directory containing WAV stems
        output_name: Base name for output file
        output_format: Output format (m4a, mp3, wav)

    Returns:
        Path to output file, or None if failed
    """
    output_path = stems_dir.parent / f"{output_name}.{output_format}"

    config = MixConfig(
        output_format=output_format,
        binaural=True,
        normalize_loudness=True,
    )

    success, error = mix_orchestral_stems(stems_dir, output_path, config)

    if success:
        return output_path
    else:
        logger.error("Mix failed: %s", error)
        return None


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "FORMAT_M4A",
    "FORMAT_MP3",
    "FORMAT_WAV",
    "MixConfig",
    "StemMixConfig",
    "azimuth_to_pan",
    "create_spatial_mix",
    "equal_power_pan",
    "mix_orchestral_stems",
    "mix_stems",
]
