"""Video Compositor — FFmpeg-based compositing with chromakey.

Composites multiple video elements into final output:
- Slides video (background)
- Avatar video (chromakeyed overlay)
- Audio track
- Subtitles (ASS format burned in)

Supports multiple layout modes:
- corner: Avatar in bottom-right corner (default)
- side_by_side: Avatar on right half
- pip: Picture-in-picture with border
- fullscreen: Avatar full screen (no slides)

FFmpeg Filter Chain:
1. chromakey - Remove green/blue screen from avatar
2. scale - Resize avatar for layout
3. overlay - Place avatar on slides
4. ass - Burn in subtitles
5. audio mix - Combine audio tracks

Usage:
    from kagami_studio.production.compositor import composite_video

    result = await composite_video(
        slides_video=Path("/tmp/slides.mp4"),
        avatar_video=Path("/tmp/avatar.mp4"),
        audio_path=Path("/tmp/narration.mp3"),
        subtitle_path=Path("/tmp/subtitles.ass"),
        output_path=Path("/tmp/final.mp4"),
        layout="corner",
    )
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CompositeResult:
    """Result of video compositing."""

    success: bool
    output_path: Path | None = None
    duration_s: float = 0.0
    error: str | None = None


# Layout configurations
LAYOUTS = {
    "corner": {
        "scale": "0.25",
        "x": "W-w-50",
        "y": "H-h-50",
        "description": "Avatar in bottom-right corner",
    },
    "corner_left": {
        "scale": "0.25",
        "x": "50",
        "y": "H-h-50",
        "description": "Avatar in bottom-left corner",
    },
    "side_by_side": {
        "scale": "0.5",
        "x": "W-w",
        "y": "0",
        "description": "Avatar on right half of screen",
    },
    "pip": {
        "scale": "0.30",
        "x": "50",
        "y": "H-h-50",
        "description": "Picture-in-picture with border",
    },
    "pip_top": {
        "scale": "0.30",
        "x": "W-w-50",
        "y": "50",
        "description": "Picture-in-picture top-right",
    },
    "fullscreen": {
        "scale": "1.0",
        "x": "0",
        "y": "0",
        "description": "Avatar fullscreen (no slides)",
    },
}

# Chromakey presets
CHROMAKEY_PRESETS = {
    "green": {
        "color": "0x00ff00",
        "similarity": "0.3",
        "smoothness": "0.1",
    },
    "green_loose": {
        "color": "0x00ff00",
        "similarity": "0.4",
        "smoothness": "0.15",
    },
    "blue": {
        "color": "0x0000ff",
        "similarity": "0.3",
        "smoothness": "0.1",
    },
    "blue_loose": {
        "color": "0x0000ff",
        "similarity": "0.4",
        "smoothness": "0.15",
    },
}


async def composite_video(
    slides_video: Path,
    avatar_video: Path | None,
    audio_path: Path,
    subtitle_path: Path | None = None,
    output_path: Path | str = "/tmp/kagami_production/final.mp4",
    layout: str = "corner",
    chromakey: str = "green",
    resolution: tuple[int, int] = (1920, 1080),
) -> CompositeResult:
    """Composite slides, avatar, audio, and subtitles into final video.

    Args:
        slides_video: Path to slides video (background)
        avatar_video: Path to avatar video (optional, with green screen)
        audio_path: Path to audio track
        subtitle_path: Path to ASS subtitle file (optional)
        output_path: Output video path
        layout: Avatar layout (corner, side_by_side, pip, fullscreen)
        chromakey: Chromakey preset (green, blue, green_loose, blue_loose)
        resolution: Output resolution

    Returns:
        CompositeResult with output path
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Simple case: No avatar, just slides + audio + subtitles
        if not avatar_video or not avatar_video.exists():
            return await _composite_simple(slides_video, audio_path, subtitle_path, output_path)

        # Full composite with avatar
        return await _composite_with_avatar(
            slides_video,
            avatar_video,
            audio_path,
            subtitle_path,
            output_path,
            layout,
            chromakey,
        )

    except Exception as e:
        import traceback

        error_msg = f"{e}\n{traceback.format_exc()}"
        logger.error(f"Compositing failed: {error_msg}")
        return CompositeResult(success=False, error=error_msg)


async def _composite_simple(
    slides_video: Path,
    audio_path: Path,
    subtitle_path: Path | None,
    output_path: Path,
) -> CompositeResult:
    """Composite slides + audio + subtitles (no avatar)."""
    filters = []

    if subtitle_path and subtitle_path.exists():
        # Escape path for FFmpeg
        sub_escaped = str(subtitle_path).replace(":", "\\:").replace("'", "\\'")
        filters.append(f"ass={sub_escaped}")

    filter_str = ",".join(filters) if filters else None

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(slides_video),
        "-i",
        str(audio_path),
    ]

    if filter_str:
        cmd.extend(["-vf", filter_str])

    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "slow",  # Higher quality
            "-crf",
            "12",  # Near-lossless quality (was 18)
            "-tune",
            "animation",  # Optimized for graphics
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "256k",  # Higher bitrate audio (was 192k)
            "-shortest",
            "-movflags",
            "+faststart",  # Web optimization
            str(output_path),
        ]
    )

    result = await _run_ffmpeg(cmd)

    if result.returncode != 0:
        return CompositeResult(
            success=False,
            error=f"FFmpeg failed: {result.stderr[:500]}",
        )

    duration = _get_video_duration(output_path)
    logger.info(f"Composited (simple): {output_path} ({duration:.1f}s)")

    return CompositeResult(
        success=True,
        output_path=output_path,
        duration_s=duration,
    )


async def _composite_with_avatar(
    slides_video: Path,
    avatar_video: Path,
    audio_path: Path,
    subtitle_path: Path | None,
    output_path: Path,
    layout: str,
    chromakey: str,
) -> CompositeResult:
    """Composite with chromakeyed avatar overlay."""
    # Get layout config
    layout_config = LAYOUTS.get(layout, LAYOUTS["corner"])

    # Get chromakey config
    chroma_config = CHROMAKEY_PRESETS.get(chromakey, CHROMAKEY_PRESETS["green"])

    # Build filter complex
    filter_parts = []

    # Step 1: Chromakey the avatar video
    filter_parts.append(
        f"[1:v]chromakey={chroma_config['color']}:"
        f"{chroma_config['similarity']}:{chroma_config['smoothness']},"
        f"scale=iw*{layout_config['scale']}:ih*{layout_config['scale']}[avatar]"
    )

    # Step 2: Overlay avatar on slides
    filter_parts.append(f"[0:v][avatar]overlay={layout_config['x']}:{layout_config['y']}[comp]")

    # Step 3: Add subtitles if available
    if subtitle_path and subtitle_path.exists():
        sub_escaped = str(subtitle_path).replace(":", "\\:").replace("'", "\\'")
        filter_parts.append(f"[comp]ass={sub_escaped}[out]")
        output_stream = "[out]"
    else:
        output_stream = "[comp]"

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(slides_video),
        "-i",
        str(avatar_video),
        "-i",
        str(audio_path),
        "-filter_complex",
        filter_complex,
        "-map",
        output_stream,
        "-map",
        "2:a",
        "-c:v",
        "libx264",
        "-preset",
        "slow",  # Higher quality
        "-crf",
        "12",  # Near-lossless quality
        "-tune",
        "animation",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "256k",  # Higher bitrate audio
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    result = await _run_ffmpeg(cmd)

    if result.returncode != 0:
        return CompositeResult(
            success=False,
            error=f"FFmpeg failed: {result.stderr[:500]}",
        )

    duration = _get_video_duration(output_path)
    logger.info(f"Composited (with avatar): {output_path} ({duration:.1f}s)")

    return CompositeResult(
        success=True,
        output_path=output_path,
        duration_s=duration,
    )


async def composite_multi_shot(
    slides_video: Path,
    shot_videos: list[dict],
    audio_path: Path,
    subtitle_path: Path | None,
    output_path: Path,
    chromakey: str = "green",
) -> CompositeResult:
    """Composite with multiple shot videos at different times.

    Each shot dict contains:
    - video: Path to shot video
    - start_ms: When to show this shot
    - end_ms: When to stop showing
    - layout: Layout for this shot (optional, defaults to "corner")
    - type: Shot type for layout decisions

    For complex productions with cuts between different shot types.
    """
    # For multi-shot, we need to:
    # 1. Trim each shot video to its duration
    # 2. Concatenate with appropriate transitions
    # 3. Overlay on slides with time-based enable

    # This is complex - for now, use the first shot as primary overlay
    if not shot_videos:
        return await _composite_simple(slides_video, audio_path, subtitle_path, output_path)

    # Find primary dialogue shot
    primary_shot = None
    for shot in shot_videos:
        if shot.get("type") in ("dialogue", "monologue", "front_medium"):
            primary_shot = shot
            break

    if not primary_shot:
        primary_shot = shot_videos[0]

    avatar_video = primary_shot.get("video")
    if avatar_video:
        avatar_video = Path(avatar_video)

    layout = primary_shot.get("layout", "corner")

    return await composite_video(
        slides_video=slides_video,
        avatar_video=avatar_video,
        audio_path=audio_path,
        subtitle_path=subtitle_path,
        output_path=output_path,
        layout=layout,
        chromakey=chromakey,
    )


async def concatenate_videos(
    video_paths: list[Path],
    output_path: Path,
    audio_path: Path | None = None,
) -> CompositeResult:
    """Concatenate multiple videos sequentially.

    Useful for combining shots that should play one after another.

    Args:
        video_paths: List of video files to concatenate
        output_path: Output video path
        audio_path: Optional audio track to use instead of video audio

    Returns:
        CompositeResult with output path
    """
    if not video_paths:
        return CompositeResult(success=False, error="No videos to concatenate")

    if len(video_paths) == 1:
        # Single video - just copy (or add audio)
        if audio_path:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(video_paths[0]),
                "-i",
                str(audio_path),
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(output_path),
            ]
        else:
            cmd = ["cp", str(video_paths[0]), str(output_path)]

        result = await _run_ffmpeg(cmd)
        if result.returncode != 0:
            return CompositeResult(success=False, error="Copy failed")
        return CompositeResult(success=True, output_path=output_path)

    # Create concat file
    concat_file = output_path.parent / "concat_list.txt"
    concat_content = "\n".join(f"file '{p}'" for p in video_paths)
    concat_file.write_text(concat_content)

    try:
        if audio_path:
            # Concat with new audio
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-i",
                str(audio_path),
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(output_path),
            ]
        else:
            # Concat keeping original audio
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(output_path),
            ]

        result = await _run_ffmpeg(cmd)

        if result.returncode != 0:
            return CompositeResult(
                success=False,
                error=f"Concatenation failed: {result.stderr[:500]}",
            )

        duration = _get_video_duration(output_path)
        return CompositeResult(
            success=True,
            output_path=output_path,
            duration_s=duration,
        )

    finally:
        concat_file.unlink(missing_ok=True)


async def _run_ffmpeg(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run FFmpeg command asynchronously (via thread to avoid event loop issues)."""

    def _run_sync() -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

    return await asyncio.to_thread(_run_sync)


def _get_video_duration(path: Path) -> float:
    """Get video duration in seconds."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip()) if result.stdout.strip() else 0.0


__all__ = [
    "CHROMAKEY_PRESETS",
    "LAYOUTS",
    "CompositeResult",
    "composite_multi_shot",
    "composite_video",
    "concatenate_videos",
]
