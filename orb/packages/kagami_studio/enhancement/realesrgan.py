"""Real-ESRGAN Video Enhancement — ncnn-vulkan Backend.

Integrates Real-ESRGAN ncnn-vulkan for 4x video upscaling.
Optimized for Apple Silicon with Metal acceleration.

MODELS:
- realesr-animevideov3-x4: Fast, good for general content (DEFAULT)
- realesrgan-x4plus: Higher quality, slower
- realesrgan-x4plus-anime: Optimized for animated content

Usage:
    from kagami_studio.enhancement.realesrgan import RealESRGANEnhancer

    enhancer = RealESRGANEnhancer(output_dir="/output")
    result = await enhancer.enhance("/path/to/video.mp4")

    # Or batch processing
    result = await enhancer.enhance_batch([video1, video2, video3])
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class RealESRGANModel(str, Enum):
    """Available Real-ESRGAN models."""

    ANIMEVIDEO_V3 = "realesr-animevideov3-x4"  # Fast, general purpose
    REALESRGAN_PLUS = "realesrgan-x4plus"  # High quality
    ANIME_PLUS = "realesrgan-x4plus-anime"  # Anime optimized


class JobStatus(str, Enum):
    """Enhancement job status."""

    PENDING = "pending"
    EXTRACTING = "extracting"
    ENHANCING = "enhancing"
    ENCODING = "encoding"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class HardwareProfile:
    """Detected hardware capabilities for parallelization."""

    gpu_name: str = "Unknown"
    gpu_cores: int = 1
    cpu_cores: int = os.cpu_count() or 4
    ram_gb: float = 16.0

    # Computed settings
    max_parallel_videos: int = 1
    threads_per_video: str = "1:2:2"  # load:proc:save

    def __post_init__(self):
        self._compute_optimal_settings()

    def _compute_optimal_settings(self):
        """Compute optimal parallelization based on hardware."""
        if "M3 Ultra" in self.gpu_name or self.gpu_cores >= 60:
            self.max_parallel_videos = min(6, int(self.ram_gb / 80))
            self.threads_per_video = "4:4:4"
        elif "M3 Max" in self.gpu_name or self.gpu_cores >= 30:
            self.max_parallel_videos = min(3, int(self.ram_gb / 80))
            self.threads_per_video = "2:4:2"
        elif "M3 Pro" in self.gpu_name or self.gpu_cores >= 14:
            self.max_parallel_videos = min(2, int(self.ram_gb / 80))
            self.threads_per_video = "2:2:2"
        else:
            self.max_parallel_videos = 1
            self.threads_per_video = "1:2:2"

        self.max_parallel_videos = max(1, self.max_parallel_videos)


@dataclass
class EnhanceResult:
    """Result of a single enhancement job."""

    input_path: Path
    output_path: Path | None = None
    status: JobStatus = JobStatus.PENDING

    # Metrics
    frame_count: int = 0
    frames_processed: int = 0
    duration_seconds: float = 0.0
    input_size_mb: float = 0.0
    output_size_mb: float = 0.0
    fps: float = 0.0

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Error info
    error: str | None = None

    @property
    def progress(self) -> float:
        if self.frame_count == 0:
            return 0.0
        return (self.frames_processed / self.frame_count) * 100

    def to_dict(self) -> dict:
        return {
            "input": str(self.input_path),
            "output": str(self.output_path) if self.output_path else None,
            "status": self.status.value,
            "frame_count": self.frame_count,
            "frames_processed": self.frames_processed,
            "progress": round(self.progress, 1),
            "duration_seconds": round(self.duration_seconds, 1),
            "input_size_mb": round(self.input_size_mb, 1),
            "output_size_mb": round(self.output_size_mb, 1),
            "fps": round(self.fps, 1),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


@dataclass
class BatchResult:
    """Result of batch enhancement."""

    results: list[EnhanceResult] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def completed_count(self) -> int:
        return sum(1 for r in self.results if r.status == JobStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status == JobStatus.FAILED)

    @property
    def total_frames(self) -> int:
        return sum(r.frame_count for r in self.results)

    @property
    def frames_processed(self) -> int:
        return sum(r.frames_processed for r in self.results)

    @property
    def total_duration(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return sum(r.duration_seconds for r in self.results)

    @property
    def overall_fps(self) -> float:
        if self.total_duration > 0:
            return self.frames_processed / self.total_duration
        return 0.0

    def to_dict(self) -> dict:
        return {
            "total_jobs": len(self.results),
            "completed": self.completed_count,
            "failed": self.failed_count,
            "total_frames": self.total_frames,
            "frames_processed": self.frames_processed,
            "total_duration": round(self.total_duration, 1),
            "overall_fps": round(self.overall_fps, 1),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "results": [r.to_dict() for r in self.results],
        }


# Default paths — search order
REALESRGAN_SEARCH_PATHS = [
    Path.home() / "bin" / "realesrgan-ncnn-vulkan",
    Path.home()
    / "bin"
    / "realesrgan"
    / "realesrgan-ncnn-vulkan-v0.2.0-macos"
    / "realesrgan-ncnn-vulkan",
    Path("/tmp/realesrgan/realesrgan-ncnn-vulkan"),
    Path("/usr/local/bin/realesrgan-ncnn-vulkan"),
    Path("/opt/homebrew/bin/realesrgan-ncnn-vulkan"),
]

REALESRGAN_MODELS_SEARCH_PATHS = [
    Path.home() / "share" / "realesrgan" / "models",
    Path.home() / "bin" / "realesrgan" / "realesrgan-ncnn-vulkan-v0.2.0-macos" / "models",
    Path("/tmp/realesrgan/models"),
    Path("/usr/local/share/realesrgan/models"),
]


def find_realesrgan_binary() -> Path | None:
    """Find the Real-ESRGAN binary in common locations."""
    # Check PATH first
    path_bin = shutil.which("realesrgan-ncnn-vulkan")
    if path_bin:
        return Path(path_bin)

    # Check known locations
    for path in REALESRGAN_SEARCH_PATHS:
        if path.exists() and path.is_file():
            return path

    return None


def find_realesrgan_models() -> Path | None:
    """Find the Real-ESRGAN models directory."""
    for path in REALESRGAN_MODELS_SEARCH_PATHS:
        if path.exists() and path.is_dir():
            # Verify models exist
            if list(path.glob("*.param")):
                return path
    return None


DEFAULT_REALESRGAN_BIN = find_realesrgan_binary() or Path("/tmp/realesrgan/realesrgan-ncnn-vulkan")
DEFAULT_REALESRGAN_MODELS = find_realesrgan_models() or Path("/tmp/realesrgan/models")


def detect_hardware() -> HardwareProfile:
    """Detect hardware capabilities."""
    import psutil

    profile = HardwareProfile(ram_gb=psutil.virtual_memory().total / (1024**3))

    # Get GPU info from system_profiler on macOS
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(result.stdout)
        displays = data.get("SPDisplaysDataType", [])
        for display in displays:
            chipset = display.get("sppci_model", "")
            if chipset:
                profile.gpu_name = chipset
                if "Ultra" in chipset:
                    profile.gpu_cores = 80
                elif "Max" in chipset:
                    profile.gpu_cores = 40
                elif "Pro" in chipset:
                    profile.gpu_cores = 18
                break
    except Exception:
        pass

    profile._compute_optimal_settings()
    return profile


def get_video_info(video_path: Path) -> dict:
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

    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})

    fps_str = video_stream.get("r_frame_rate", "30/1")
    fps_parts = fps_str.split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0

    duration = float(data.get("format", {}).get("duration", 0))
    nb_frames = int(video_stream.get("nb_frames", 0))
    if nb_frames == 0:
        nb_frames = int(fps * duration)

    return {
        "width": int(video_stream.get("width", 640)),
        "height": int(video_stream.get("height", 480)),
        "fps": fps,
        "fps_str": fps_str,
        "duration": duration,
        "frame_count": nb_frames,
    }


class RealESRGANEnhancer:
    """Real-ESRGAN video enhancement using ncnn-vulkan.

    Provides 4x upscaling using Metal-accelerated inference.

    Args:
        output_dir: Directory for enhanced videos
        model: Real-ESRGAN model to use (default: animevideo-v3)
        scale: Upscaling factor (default: 4)
        realesrgan_bin: Path to realesrgan-ncnn-vulkan binary
        models_dir: Path to models directory
        hardware: Hardware profile for parallelization
        progress_callback: Callback for progress updates (video_name, progress, status)
    """

    def __init__(
        self,
        output_dir: Path | str,
        model: RealESRGANModel = RealESRGANModel.ANIMEVIDEO_V3,
        scale: int = 4,
        realesrgan_bin: Path | str | None = None,
        models_dir: Path | str | None = None,
        hardware: HardwareProfile | None = None,
        progress_callback: Callable[[str, float, str], None] | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.model = model
        self.scale = scale
        self.realesrgan_bin = Path(realesrgan_bin) if realesrgan_bin else DEFAULT_REALESRGAN_BIN
        self.models_dir = Path(models_dir) if models_dir else DEFAULT_REALESRGAN_MODELS
        self.hardware = hardware or detect_hardware()
        self.progress_callback = progress_callback

        # Verify binary exists
        if not self.realesrgan_bin.exists():
            raise FileNotFoundError(
                f"realesrgan-ncnn-vulkan not found at {self.realesrgan_bin}. "
                "Download from https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases"
            )

        # Verify models exist
        if not self.models_dir.exists():
            raise FileNotFoundError(
                f"Models directory not found at {self.models_dir}. "
                "Download models from https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases"
            )

        # Verify specific model exists
        model_param = self.models_dir / f"{model.value}.param"
        if not model_param.exists():
            raise FileNotFoundError(
                f"Model {model.value} not found at {model_param}. "
                f"Available models: {[p.stem for p in self.models_dir.glob('*.param')]}"
            )

    def _notify(self, video_name: str, progress: float, status: str):
        """Send progress notification."""
        if self.progress_callback:
            self.progress_callback(video_name, progress, status)

    async def enhance(
        self,
        video_path: Path | str,
        output_name: str | None = None,
    ) -> EnhanceResult:
        """Enhance a single video.

        Args:
            video_path: Path to input video
            output_name: Custom output filename (default: {stem}_enhanced.mp4)

        Returns:
            EnhanceResult with status and metrics
        """
        video_path = Path(video_path)

        if output_name:
            output_path = self.output_dir / output_name
        else:
            output_path = self.output_dir / f"{video_path.stem}_enhanced.mp4"

        result = EnhanceResult(
            input_path=video_path,
            output_path=output_path,
            input_size_mb=video_path.stat().st_size / (1024 * 1024),
            started_at=datetime.now(),
        )

        try:
            # Get video info
            info = get_video_info(video_path)
            result.frame_count = info["frame_count"]

            self._notify(video_path.name, 0, "extracting")
            result.status = JobStatus.EXTRACTING

            # Create temp directory for frames
            with tempfile.TemporaryDirectory(prefix=f"enhance_{video_path.stem}_") as temp_dir:
                temp_path = Path(temp_dir)
                frames_dir = temp_path / "frames"
                enhanced_dir = temp_path / "enhanced"
                frames_dir.mkdir()
                enhanced_dir.mkdir()

                # Extract frames
                extract_cmd = [
                    "ffmpeg",
                    "-i",
                    str(video_path),
                    "-qscale:v",
                    "2",
                    str(frames_dir / "frame_%06d.jpg"),
                ]

                await asyncio.create_subprocess_exec(
                    *extract_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )

                # Wait for extraction
                proc = await asyncio.create_subprocess_exec(
                    *extract_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()

                actual_frames = len(list(frames_dir.glob("frame_*.jpg")))
                if actual_frames == 0:
                    raise ValueError("No frames extracted from video")

                result.frame_count = actual_frames

                # Enhance with Real-ESRGAN
                self._notify(video_path.name, 5, "enhancing")
                result.status = JobStatus.ENHANCING

                enhance_cmd = [
                    str(self.realesrgan_bin),
                    "-i",
                    str(frames_dir),
                    "-o",
                    str(enhanced_dir),
                    "-m",
                    str(self.models_dir),  # Models path
                    "-n",
                    self.model.value,
                    "-s",
                    str(self.scale),
                    "-f",
                    "jpg",
                    "-j",
                    self.hardware.threads_per_video,
                ]

                enhance_start = time.time()

                proc = await asyncio.create_subprocess_exec(
                    *enhance_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                    cwd=str(self.realesrgan_bin.parent),
                )

                # Monitor progress
                while proc.returncode is None:
                    await asyncio.sleep(1)

                    enhanced_count = len(list(enhanced_dir.glob("frame_*.jpg")))
                    result.frames_processed = enhanced_count

                    elapsed = time.time() - enhance_start
                    if elapsed > 0 and enhanced_count > 0:
                        result.fps = enhanced_count / elapsed

                    progress = 5 + (enhanced_count / actual_frames) * 85
                    self._notify(video_path.name, progress, "enhancing")

                    # Check if process finished
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=0.1)
                    except TimeoutError:
                        pass

                await proc.wait()

                # Verify enhancement
                enhanced_frames = list(enhanced_dir.glob("frame_*.jpg"))
                if len(enhanced_frames) == 0:
                    raise ValueError("No enhanced frames created")

                result.frames_processed = len(enhanced_frames)

                # Encode output video
                self._notify(video_path.name, 90, "encoding")
                result.status = JobStatus.ENCODING

                # Try hardware encoder first
                encode_cmd = [
                    "ffmpeg",
                    "-y",
                    "-framerate",
                    info["fps_str"],
                    "-i",
                    str(enhanced_dir / "frame_%06d.jpg"),
                    "-i",
                    str(video_path),
                    "-c:v",
                    "h264_videotoolbox",
                    "-b:v",
                    "25M",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0?",
                    "-shortest",
                    str(output_path),
                ]

                proc = await asyncio.create_subprocess_exec(
                    *encode_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()

                # Fallback to software if hardware fails
                if proc.returncode != 0 or not output_path.exists():
                    encode_cmd = [
                        "ffmpeg",
                        "-y",
                        "-framerate",
                        info["fps_str"],
                        "-i",
                        str(enhanced_dir / "frame_%06d.jpg"),
                        "-i",
                        str(video_path),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "fast",
                        "-crf",
                        "20",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "192k",
                        "-map",
                        "0:v:0",
                        "-map",
                        "1:a:0?",
                        "-shortest",
                        str(output_path),
                    ]

                    proc = await asyncio.create_subprocess_exec(
                        *encode_cmd,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await proc.wait()

                if not output_path.exists():
                    raise ValueError("Output file not created")

                result.output_size_mb = output_path.stat().st_size / (1024 * 1024)

            # Success
            result.status = JobStatus.COMPLETED
            result.completed_at = datetime.now()
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()

            self._notify(video_path.name, 100, "completed")

        except Exception as e:
            result.status = JobStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()

            logger.error(f"Enhancement failed for {video_path}: {e}")
            self._notify(video_path.name, 0, f"failed: {e}")

        return result

    async def enhance_batch(
        self,
        videos: list[Path | str],
        parallel: int | None = None,
    ) -> BatchResult:
        """Enhance multiple videos in parallel.

        Args:
            videos: List of video paths
            parallel: Number of concurrent enhancements (default: auto-detected)

        Returns:
            BatchResult with all results
        """
        videos = [Path(v) for v in videos if Path(v).exists()]

        if not videos:
            return BatchResult()

        parallel = parallel or self.hardware.max_parallel_videos

        result = BatchResult(started_at=datetime.now())

        # Create semaphore for parallelization
        semaphore = asyncio.Semaphore(parallel)

        async def process_with_limit(video: Path) -> EnhanceResult:
            async with semaphore:
                return await self.enhance(video)

        # Process all videos
        tasks = [process_with_limit(v) for v in videos]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                result.results.append(
                    EnhanceResult(
                        input_path=Path("unknown"),
                        status=JobStatus.FAILED,
                        error=str(r),
                    )
                )
            else:
                result.results.append(r)

        result.completed_at = datetime.now()

        return result

    async def enhance_directory(
        self,
        directory: Path | str,
        skip_existing: bool = True,
        parallel: int | None = None,
    ) -> BatchResult:
        """Enhance all videos in a directory.

        Args:
            directory: Directory containing videos
            skip_existing: Skip videos that already have enhanced output
            parallel: Number of concurrent enhancements

        Returns:
            BatchResult with all results
        """
        directory = Path(directory)

        videos = []
        for ext in (".mp4", ".mov", ".avi", ".mkv"):
            videos.extend(directory.glob(f"*{ext}"))

        if skip_existing:
            videos = [
                v for v in videos if not (self.output_dir / f"{v.stem}_enhanced.mp4").exists()
            ]

        # Sort by size (smaller first for faster initial feedback)
        videos.sort(key=lambda v: v.stat().st_size)

        return await self.enhance_batch(videos, parallel)


async def enhance_video(
    video_path: Path | str,
    output_dir: Path | str,
    model: RealESRGANModel = RealESRGANModel.ANIMEVIDEO_V3,
    scale: int = 4,
) -> EnhanceResult:
    """Quick function to enhance a single video.

    Args:
        video_path: Path to input video
        output_dir: Directory for output
        model: Real-ESRGAN model
        scale: Upscaling factor

    Returns:
        EnhanceResult

    Example:
        result = await enhance_video(
            "/path/to/video.mp4",
            "/output/dir",
        )
        print(f"Enhanced: {result.output_path}")
    """
    enhancer = RealESRGANEnhancer(
        output_dir=output_dir,
        model=model,
        scale=scale,
    )
    return await enhancer.enhance(video_path)


async def enhance_archive(
    source_dir: Path | str,
    output_dir: Path | str,
    parallel: int | None = None,
    model: RealESRGANModel = RealESRGANModel.ANIMEVIDEO_V3,
) -> BatchResult:
    """Quick function to enhance an entire archive.

    Args:
        source_dir: Directory with source videos
        output_dir: Directory for enhanced output
        parallel: Concurrent enhancements (default: auto)
        model: Real-ESRGAN model

    Returns:
        BatchResult with all results

    Example:
        result = await enhance_archive(
            "/Volumes/WesData",
            "/Volumes/WesData/enhanced",
        )
        print(f"Completed: {result.completed_count}/{len(result.results)}")
    """
    enhancer = RealESRGANEnhancer(
        output_dir=output_dir,
        model=model,
    )
    return await enhancer.enhance_directory(
        source_dir,
        skip_existing=True,
        parallel=parallel,
    )
