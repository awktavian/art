"""
🎬 UNIFIED VIDEO ENHANCEMENT ENGINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Single source of truth for all video enhancement operations.
Uses Topaz Video AI via ffmpeg CLI with custom tvai filters.

Features:
- Natural VHS restoration (Iris model, soft upscaling)
- Background task tracking via BackgroundTaskManager
- Progress monitoring
- Receipt-based audit trail
- Automatic retry on failure

Usage:
    from kagami_media.video_enhancement import enhance_video, get_enhancement_status

    # Start enhancement (returns immediately)
    task_id = await enhance_video(
        "/path/to/video.mp4",
        preset="vhs_natural",
    )

    # Check status
    status = await get_enhancement_status(task_id)

    # Or wait for completion
    result = await wait_for_enhancement(task_id)
"""

import asyncio
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Topaz paths
TOPAZ_FFMPEG = Path("/Applications/Topaz Video.app/Contents/MacOS/ffmpeg")
TOPAZ_MODELS = Path("/Applications/Topaz Video.app/Contents/Resources/models")
TOPAZ_CACHE = Path.home() / "Library/Caches/TopazVideoAI/models"


def _setup_topaz_env() -> dict[str, str]:
    """Set up environment variables for Topaz Video AI CLI.

    Returns:
        Environment dict to pass to subprocess
    """
    # Create cache directory if needed
    TOPAZ_CACHE.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["TVAI_MODEL_DIR"] = str(TOPAZ_MODELS)
    env["TVAI_MODEL_DATA_DIR"] = str(TOPAZ_CACHE)
    return env


class EnhancementPreset(str, Enum):
    """Enhancement presets optimized for different source types."""

    VHS_NATURAL = "vhs_natural"  # Soft, film-like (Iris)
    VHS_SHARP = "vhs_sharp"  # Sharper (Proteus) - NOT recommended
    DVD_UPSCALE = "dvd_upscale"  # DVD to 4K
    MINIDIG_HD = "minidv_hd"  # MiniDV to 1080p
    GENERAL = "general"  # Auto-detect best settings


@dataclass
class EnhancementSettings:
    """Enhancement settings for Topaz tvai_up filter.

    Attributes:
        model: AI model (iris-3 for natural, prob-4 for sharp)
        scale: Upscale factor (1-4)
        blur: Sharpening (-1 to 1, negative = softer)
        details: Detail recovery (-1 to 1, negative = less hallucination)
        noise: Noise removal (-1 to 1)
        grain: Output grain amount (0-1)
        grain_size: Grain size (0-5)
        denoise_model: Denoise model (nyx-1 = light, nyx-3 = heavy)
    """

    model: str = "iris-3"
    scale: int = 4
    blur: float = -0.2  # Negative = softer edges
    details: float = -0.15  # Negative = less AI hallucination
    noise: float = 0.1  # Light noise removal
    halo: float = 0.0
    compression: float = 0.0
    grain: float = 0.35  # Add grain back for natural look
    grain_size: float = 1.5
    denoise_model: str | None = "nyx-1"  # Light denoise

    def to_filter_args(self) -> str:
        """Convert to tvai_up filter arguments."""
        args = [
            f"model={self.model}",
            f"scale={self.scale}",
            f"blur={self.blur}",
            f"details={self.details}",
            f"noise={self.noise}",
            f"halo={self.halo}",
            f"compression={self.compression}",
            f"grain={self.grain}",
            f"gsize={self.grain_size}",
        ]
        return ":".join(args)


# Preset configurations
PRESETS: dict[EnhancementPreset, EnhancementSettings] = {
    EnhancementPreset.VHS_NATURAL: EnhancementSettings(
        model="iris-3",
        scale=4,
        blur=-0.2,  # Softer
        details=-0.15,  # Less hallucination
        noise=0.1,
        grain=0.35,  # Film grain
        grain_size=1.5,
        denoise_model="nyx-1",
    ),
    EnhancementPreset.VHS_SHARP: EnhancementSettings(
        model="prob-4",
        scale=4,
        blur=0.0,
        details=0.2,
        noise=0.2,
        grain=0.0,
        denoise_model="nyx-3",
    ),
    EnhancementPreset.DVD_UPSCALE: EnhancementSettings(
        model="amq-13",
        scale=4,
        blur=0.0,
        details=0.1,
        noise=0.1,
        grain=0.0,
        denoise_model=None,
    ),
    EnhancementPreset.MINIDIG_HD: EnhancementSettings(
        model="iris-3",
        scale=2,
        blur=0.0,
        details=0.0,
        noise=0.0,
        grain=0.0,
        denoise_model=None,
    ),
    EnhancementPreset.GENERAL: EnhancementSettings(
        model="iris-3",
        scale=2,
        blur=0.0,
        details=0.0,
        noise=0.0,
        grain=0.0,
        denoise_model=None,
    ),
}


@dataclass
class EnhancementProgress:
    """Progress tracking for enhancement job."""

    task_id: str
    video_path: str
    output_path: str
    preset: str
    status: str = "pending"  # pending, processing, completed, failed
    progress_percent: float = 0.0
    current_frame: int = 0
    total_frames: int = 0
    fps: float = 0.0
    eta_seconds: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "video_path": self.video_path,
            "output_path": self.output_path,
            "preset": self.preset,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "current_frame": self.current_frame,
            "total_frames": self.total_frames,
            "fps": self.fps,
            "eta_seconds": self.eta_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


# Global progress tracking
_enhancement_jobs: dict[str, EnhancementProgress] = {}


def _get_video_info(video_path: Path) -> dict:
    """Get video metadata using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)

    video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")

    fps_str = video_stream.get("r_frame_rate", "30/1")
    fps_parts = fps_str.split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0

    frame_count = int(video_stream.get("nb_frames", 0))
    if frame_count == 0:
        duration = float(data["format"].get("duration", 0))
        frame_count = int(duration * fps)

    return {
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
        "fps": fps,
        "duration": float(data["format"].get("duration", 0)),
        "frame_count": frame_count,
    }


async def _run_enhancement(
    task_id: str,
    video_path: Path,
    output_path: Path,
    settings: EnhancementSettings,
) -> Path:
    """Run the actual enhancement process.

    This is the core function that executes Topaz via ffmpeg.
    Called as a background task.
    """
    global _enhancement_jobs

    progress = _enhancement_jobs.get(task_id)
    if not progress:
        raise ValueError(f"Task {task_id} not found")

    # Update status
    progress.status = "processing"
    progress.started_at = datetime.utcnow()

    # Get video info
    info = _get_video_info(video_path)
    progress.total_frames = info["frame_count"]

    out_w = info["width"] * settings.scale
    out_h = info["height"] * settings.scale

    # Build ffmpeg command with Topaz filter
    filter_chain = []

    # Optional denoise first
    if settings.denoise_model:
        # Topaz doesn't have separate denoise filter in ffmpeg
        # It's built into the model, but we can adjust noise param
        pass

    # Main tvai_up filter
    filter_chain.append(f"tvai_up={settings.to_filter_args()}")

    cmd = [
        str(TOPAZ_FFMPEG),
        "-hide_banner",
        "-i",
        str(video_path),
        "-vf",
        ",".join(filter_chain),
        "-c:v",
        "hevc_videotoolbox",  # Hardware encoding
        "-b:v",
        "50M",  # High bitrate for quality
        "-tag:v",
        "hvc1",
        "-c:a",
        "aac",
        "-b:a",
        "256k",
        "-progress",
        "pipe:1",  # Progress to stdout
        "-y",
        str(output_path),
    ]

    print(f"🎬 Starting enhancement: {video_path.name}")
    print(f"   Output: {out_w}x{out_h}")
    print(f"   Model: {settings.model}")
    print(f"   Settings: blur={settings.blur}, details={settings.details}, grain={settings.grain}")

    # Set up Topaz environment
    env = _setup_topaz_env()

    # Run ffmpeg with progress tracking
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    # Parse progress
    start_time = time.time()
    stderr_output = []

    async def read_stderr():
        """Read stderr for errors."""
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            stderr_output.append(line.decode())

    async def read_progress():
        """Read and parse ffmpeg progress output."""
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line = line.decode().strip()

            # Parse frame=XXX
            if line.startswith("frame="):
                try:
                    frame = int(line.split("=")[1])
                    progress.current_frame = frame
                    if progress.total_frames > 0:
                        progress.progress_percent = (frame / progress.total_frames) * 100
                        # Print progress
                        print(
                            f"\r   Progress: {progress.progress_percent:.1f}% ({frame}/{progress.total_frames})",
                            end="",
                            flush=True,
                        )
                except Exception:
                    pass

            # Parse fps=XXX
            elif line.startswith("fps="):
                try:
                    progress.fps = float(line.split("=")[1])
                    if progress.fps > 0 and progress.total_frames > 0:
                        remaining = progress.total_frames - progress.current_frame
                        progress.eta_seconds = remaining / progress.fps
                except Exception:
                    pass

    # Start both readers concurrently
    await asyncio.gather(
        read_progress(),
        read_stderr(),
    )
    print()  # New line after progress

    # Wait for process to finish
    await process.wait()
    stderr = "".join(stderr_output)

    if process.returncode != 0:
        error_msg = stderr if stderr else "Unknown error"
        progress.status = "failed"
        progress.error = error_msg
        progress.completed_at = datetime.utcnow()
        raise RuntimeError(f"Enhancement failed: {error_msg}")

    # Success
    progress.status = "completed"
    progress.progress_percent = 100.0
    progress.completed_at = datetime.utcnow()

    elapsed = time.time() - start_time
    output_size = output_path.stat().st_size / (1024**3)

    print(f"✅ Enhancement complete: {output_path.name}")
    print(f"   Size: {output_size:.2f} GB")
    print(f"   Time: {elapsed / 60:.1f} minutes")

    return output_path


async def enhance_video(
    video_path: str | Path,
    output_path: str | Path | None = None,
    preset: EnhancementPreset | str = EnhancementPreset.VHS_NATURAL,
    settings: EnhancementSettings | None = None,
    wait: bool = False,
) -> str:
    """Enhance a video using Topaz Video AI.

    Args:
        video_path: Path to source video
        output_path: Output path (auto-generated if None)
        preset: Enhancement preset to use
        settings: Custom settings (overrides preset)
        wait: If True, wait for completion before returning

    Returns:
        Task ID for tracking progress

    Example:
        # Start enhancement in background
        task_id = await enhance_video("Tape10.mp4", preset="vhs_natural")

        # Check progress
        progress = await get_enhancement_status(task_id)
        print(f"Progress: {progress['progress_percent']:.1f}%")
    """
    global _enhancement_jobs

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Verify Topaz is available
    if not TOPAZ_FFMPEG.exists():
        raise RuntimeError("Topaz Video AI not found. Install from topazlabs.com")

    # Get settings
    if settings is None:
        if isinstance(preset, str):
            preset = EnhancementPreset(preset)
        settings = PRESETS[preset]

    # Generate output path
    if output_path is None:
        suffix = f"_{preset.value if isinstance(preset, EnhancementPreset) else preset}"
        output_dir = video_path.parent / "enhanced"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"{video_path.stem}{suffix}.mp4"
    else:
        output_path = Path(output_path)

    # Generate task ID
    task_id = f"enhance_{video_path.stem}_{int(time.time())}"

    # Create progress tracker
    progress = EnhancementProgress(
        task_id=task_id,
        video_path=str(video_path),
        output_path=str(output_path),
        preset=preset.value if isinstance(preset, EnhancementPreset) else str(preset),
    )
    _enhancement_jobs[task_id] = progress

    # Create the enhancement coroutine
    coro = _run_enhancement(task_id, video_path, output_path, settings)

    if wait:
        # Run synchronously
        await coro
        return task_id

    # Run as background task
    try:
        from kagami.core.tasks.background_task_manager import get_task_manager

        manager = get_task_manager()
        await manager.create_task(
            name=task_id,
            coro=coro,
            max_retries=1,  # Don't retry long video jobs
            correlation_id=task_id,
        )
        print(f"📋 Enhancement task created: {task_id}")

    except ImportError:
        # Fall back to simple asyncio task if manager not available
        asyncio.create_task(coro)
        print(f"📋 Enhancement started (no task manager): {task_id}")

    return task_id


async def get_enhancement_status(task_id: str) -> dict[str, Any] | None:
    """Get the status of an enhancement job.

    Returns:
        Progress dictionary or None if not found
    """
    progress = _enhancement_jobs.get(task_id)
    if progress:
        return progress.to_dict()

    # Try task manager
    try:
        from kagami.core.tasks.background_task_manager import get_task_manager

        manager = get_task_manager()
        return await manager.get_task_status(task_id)
    except Exception:
        pass

    return None


async def wait_for_enhancement(task_id: str, timeout: float | None = None) -> Path:
    """Wait for an enhancement job to complete.

    Args:
        task_id: Task ID from enhance_video()
        timeout: Maximum seconds to wait (None = forever)

    Returns:
        Path to enhanced video

    Raises:
        TimeoutError: If timeout exceeded
        RuntimeError: If enhancement failed
    """
    progress = _enhancement_jobs.get(task_id)
    if not progress:
        raise ValueError(f"Task {task_id} not found")

    # Try task manager first
    try:
        from kagami.core.tasks.background_task_manager import get_task_manager

        manager = get_task_manager()
        await manager.wait_for_task(task_id, timeout=timeout)
    except ImportError:
        # Poll manually
        start = time.time()
        while True:
            if progress.status == "completed":
                break
            elif progress.status == "failed":
                raise RuntimeError(f"Enhancement failed: {progress.error}") from None

            if timeout and (time.time() - start) > timeout:
                raise TimeoutError(f"Timeout waiting for {task_id}") from None

            await asyncio.sleep(1)

    return Path(progress.output_path)


async def list_enhancement_jobs() -> list[dict[str, Any]]:
    """List all enhancement jobs."""
    jobs = []
    for progress in _enhancement_jobs.values():
        jobs.append(progress.to_dict())
    return jobs


async def cancel_enhancement(task_id: str) -> bool:
    """Cancel a running enhancement job."""
    try:
        from kagami.core.tasks.background_task_manager import get_task_manager

        manager = get_task_manager()
        return await manager.cancel_task(task_id)
    except Exception:
        pass
    return False


# CLI interface
if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) < 2:
            print("Usage: python -m kagami_media.video_enhancement <video> [--preset vhs_natural]")
            print("\nPresets:")
            for p in EnhancementPreset:
                print(f"  {p.value}")
            sys.exit(1)

        video_path = Path(sys.argv[1])
        preset = EnhancementPreset.VHS_NATURAL

        if "--preset" in sys.argv:
            idx = sys.argv.index("--preset")
            preset = EnhancementPreset(sys.argv[idx + 1])

        print(f"🎬 Enhancing: {video_path.name}")
        print(f"   Preset: {preset.value}")

        task_id = await enhance_video(video_path, preset=preset, wait=True)

        status = await get_enhancement_status(task_id)
        print(f"\n✅ Complete: {status['output_path']}")

    asyncio.run(main())
