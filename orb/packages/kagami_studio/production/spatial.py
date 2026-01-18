"""Spatial Audio Integration — Audio spatialization for video production.

Routes audio through UnifiedSpatialEngine for:
- Stereo mix (standard L/R)
- Binaural (headphone-optimized 3D audio)
- Dolby Atmos (ADM BWF for professional post-production)

In video production context:
- Speaker voice positioned at screen center
- Ambient audio spread across soundstage
- Music positioned behind viewer

Usage:
    from kagami_studio.production.spatial import spatialize_audio

    # Standard stereo output
    stereo_path = await spatialize_audio(audio_path, format="stereo")

    # Headphone-optimized
    binaural_path = await spatialize_audio(audio_path, format="binaural")

    # Professional Atmos for post
    atmos_path = await spatialize_audio(audio_path, format="atmos")
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_spatial")


async def spatialize_audio(
    audio_path: Path | str,
    output_path: Path | str | None = None,
    format: str = "stereo",  # stereo, binaural, atmos
    speaker_position: tuple[float, float, float] = (0, 0, 1),  # x, y, z
) -> Path:
    """Process audio through spatial engine.

    Args:
        audio_path: Input audio file
        output_path: Output path (auto-generated if None)
        format: Output format - stereo, binaural, atmos
        speaker_position: 3D position of speaker voice (x, y, z)
            x: -1 (left) to 1 (right)
            y: -1 (below) to 1 (above)
            z: 0 (close) to 1 (far)

    Returns:
        Path to spatialized audio file

    Note:
        Currently falls back to stereo for all formats until
        UnifiedSpatialEngine integration is complete.
    """
    audio_path = Path(audio_path)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        suffix = ".wav" if format == "atmos" else ".mp3"
        output_path = OUTPUT_DIR / f"{audio_path.stem}_spatial_{format}{suffix}"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if format == "binaural":
            return await _render_binaural(audio_path, output_path, speaker_position)
        elif format == "atmos":
            return await _render_atmos(audio_path, output_path, speaker_position)
        else:
            return await _render_stereo(audio_path, output_path)

    except Exception as e:
        logger.warning(f"Spatial processing failed, copying original: {e}")
        shutil.copy(audio_path, output_path)
        return output_path


async def _render_stereo(audio_path: Path, output_path: Path) -> Path:
    """Render standard stereo mix.

    For most video productions, stereo is sufficient.
    Just ensures proper levels and format.
    """
    try:
        from kagami.core.effectors.spatial import UnifiedSpatialEngine

        engine = UnifiedSpatialEngine()
        result = await engine.render(audio_path, format="stereo")
        if result and result.exists():
            shutil.move(str(result), str(output_path))
            logger.info(f"Spatial stereo: {output_path}")
            return output_path
    except ImportError:
        logger.debug("UnifiedSpatialEngine not available")
    except Exception as e:
        logger.debug(f"Spatial engine error: {e}")

    # Fallback: FFmpeg stereo normalization
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-af",
        "loudnorm=I=-16:LRA=11:TP=-1.5",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Last resort: just copy
        shutil.copy(audio_path, output_path)

    logger.info(f"Stereo (normalized): {output_path}")
    return output_path


async def _render_binaural(
    audio_path: Path,
    output_path: Path,
    position: tuple[float, float, float],
) -> Path:
    """Render binaural audio for headphones.

    Applies HRTF (Head-Related Transfer Function) processing
    to create 3D audio perception through headphones.
    """
    try:
        from kagami.core.effectors.spatial import UnifiedSpatialEngine

        engine = UnifiedSpatialEngine()
        result = await engine.render(
            audio_path,
            format="binaural",
            position=position,
        )
        if result and result.exists():
            shutil.move(str(result), str(output_path))
            logger.info(f"Spatial binaural: {output_path}")
            return output_path
    except ImportError:
        logger.debug("UnifiedSpatialEngine not available")
    except Exception as e:
        logger.debug(f"Spatial engine error: {e}")

    # Fallback: FFmpeg with headphone filter
    # This is a basic approximation, not true binaural
    x, _y, z = position

    # Convert position to angle
    import math

    math.degrees(math.atan2(x, z)) if z != 0 else 0

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-af",
        f"extrastereo=m={1.0 + abs(x) * 0.5},headphone=map=stereo",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        shutil.copy(audio_path, output_path)

    logger.info(f"Binaural (fallback): {output_path}")
    return output_path


async def _render_atmos(
    audio_path: Path,
    output_path: Path,
    position: tuple[float, float, float],
) -> Path:
    """Render Dolby Atmos ADM BWF for professional post-production.

    Creates a broadcast WAV with embedded ADM (Audio Definition Model)
    metadata for object-based audio.
    """
    try:
        from kagami.core.effectors.spatial import UnifiedSpatialEngine

        engine = UnifiedSpatialEngine()
        result = await engine.render(
            audio_path,
            format="atmos",
            position=position,
        )
        if result and result.exists():
            shutil.move(str(result), str(output_path))
            logger.info(f"Spatial Atmos: {output_path}")
            return output_path
    except ImportError:
        logger.debug("UnifiedSpatialEngine not available")
    except Exception as e:
        logger.debug(f"Spatial engine error: {e}")

    # Fallback: Convert to 24-bit WAV (Atmos-compatible container)
    # True Atmos would require Dolby encoding tools
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-c:a",
        "pcm_s24le",
        "-ar",
        "48000",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        shutil.copy(audio_path, output_path.with_suffix(".mp3"))
        return output_path.with_suffix(".mp3")

    logger.info(f"Atmos (WAV fallback): {output_path}")
    return output_path


async def mix_audio_tracks(
    voice_path: Path,
    music_path: Path | None = None,
    ambient_path: Path | None = None,
    output_path: Path | None = None,
    voice_level: float = 0.0,  # dB
    music_level: float = -12.0,  # dB (background)
    ambient_level: float = -18.0,  # dB (subtle)
) -> Path:
    """Mix multiple audio tracks with level control.

    Args:
        voice_path: Primary voice track
        music_path: Background music (optional)
        ambient_path: Ambient sound (optional)
        output_path: Output path (auto-generated if None)
        voice_level: Voice level in dB
        music_level: Music level in dB
        ambient_level: Ambient level in dB

    Returns:
        Path to mixed audio file
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = OUTPUT_DIR / f"{voice_path.stem}_mixed.mp3"

    # Build FFmpeg filter
    inputs = ["-i", str(voice_path)]
    filter_parts = [f"[0:a]volume={voice_level}dB[v]"]
    mix_inputs = ["[v]"]
    input_count = 1

    if music_path and music_path.exists():
        inputs.extend(["-i", str(music_path)])
        filter_parts.append(f"[{input_count}:a]volume={music_level}dB[m]")
        mix_inputs.append("[m]")
        input_count += 1

    if ambient_path and ambient_path.exists():
        inputs.extend(["-i", str(ambient_path)])
        filter_parts.append(f"[{input_count}:a]volume={ambient_level}dB[a]")
        mix_inputs.append("[a]")
        input_count += 1

    if len(mix_inputs) == 1:
        # Only voice - just normalize
        filter_str = f"{filter_parts[0]}; [v]loudnorm=I=-16:LRA=11:TP=-1.5[out]"
    else:
        # Mix all tracks
        filter_str = "; ".join(filter_parts)
        filter_str += f"; {''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=longest[mix]"
        filter_str += "; [mix]loudnorm=I=-16:LRA=11:TP=-1.5[out]"

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_str,
        "-map",
        "[out]",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning(f"Mix failed: {result.stderr[:200]}, copying voice only")
        shutil.copy(voice_path, output_path)

    logger.info(f"Mixed audio: {output_path}")
    return output_path


__all__ = [
    "mix_audio_tracks",
    "spatialize_audio",
]
