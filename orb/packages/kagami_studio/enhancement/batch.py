"""Parallel Batch Video Enhancement — M3 Ultra Optimized.

Optimal parallelization for Topaz Video AI on Apple Silicon.

HARDWARE PROFILE (M3 Ultra):
- 32 CPU cores (24 performance + 8 efficiency)
- 80 GPU cores
- 512 GB unified memory
- ~200 GB/s memory bandwidth

PARALLELIZATION STRATEGY:
- GPU: 2-3 concurrent video streams (GPU memory limited)
- CPU encoding: Up to 4 concurrent encodes
- I/O: Async file operations, SSD-optimized buffering

DEFAULT MODEL: Artemis HQ (ahq-12)
- Highest fidelity, minimal hallucination
- Best for archival restoration

Usage:
    from kagami_studio.enhancement.batch import BatchEnhancer

    enhancer = BatchEnhancer(
        output_dir="/path/to/enhanced",
        parallel=2,  # 2 concurrent videos
    )

    # Process entire archive
    results = await enhancer.process_directory("/Volumes/WesData")

    # Or specific files
    results = await enhancer.process_files([
        "/Volumes/WesData/Easter.mp4",
        "/Volumes/WesData/Tape02.mp4",
    ])
"""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from .config import (
    DEFAULT_MODEL,
    EnhanceConfig,
    TopazModel,
    get_default_config,
)


class JobStatus(str, Enum):
    """Job processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class JobResult:
    """Result of a single enhancement job."""

    input_path: Path
    output_path: Path | None
    status: JobStatus
    duration_seconds: float = 0.0
    input_size_mb: float = 0.0
    output_size_mb: float = 0.0
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "input": str(self.input_path),
            "output": str(self.output_path) if self.output_path else None,
            "status": self.status.value,
            "duration_seconds": round(self.duration_seconds, 1),
            "input_size_mb": round(self.input_size_mb, 1),
            "output_size_mb": round(self.output_size_mb, 1),
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class BatchResult:
    """Result of batch processing."""

    jobs: list[JobResult] = field(default_factory=list)
    total_input_size_mb: float = 0.0
    total_output_size_mb: float = 0.0
    total_duration_seconds: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def completed_count(self) -> int:
        return sum(1 for j in self.jobs if j.status == JobStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        return sum(1 for j in self.jobs if j.status == JobStatus.FAILED)

    @property
    def success_rate(self) -> float:
        if not self.jobs:
            return 0.0
        return self.completed_count / len(self.jobs) * 100

    def to_dict(self) -> dict:
        return {
            "total_jobs": len(self.jobs),
            "completed": self.completed_count,
            "failed": self.failed_count,
            "success_rate": round(self.success_rate, 1),
            "total_input_size_mb": round(self.total_input_size_mb, 1),
            "total_output_size_mb": round(self.total_output_size_mb, 1),
            "total_duration_seconds": round(self.total_duration_seconds, 1),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "jobs": [j.to_dict() for j in self.jobs],
        }


# Topaz CLI paths
TOPAZ_APP = Path("/Applications/Topaz Video.app")
TOPAZ_FFMPEG = TOPAZ_APP / "Contents/MacOS/ffmpeg"
TOPAZ_MODELS = TOPAZ_APP / "Contents/Resources/models"

# Environment variables required for Topaz CLI
TOPAZ_ENV = {
    "TVAI_MODEL_DIR": str(TOPAZ_MODELS),
    "TVAI_MODEL_DATA_DIR": str(TOPAZ_MODELS),
}


class BatchEnhancer:
    """Parallel batch video enhancement processor.

    Optimized for M3 Ultra with:
    - Concurrent video processing (2-3 streams)
    - GPU memory management
    - Progress tracking
    - Resumable processing (skips completed)

    Args:
        output_dir: Directory for enhanced videos
        config: Enhancement configuration (default: Artemis HQ archival)
        parallel: Number of concurrent videos (default: 2 for GPU balance)
        skip_existing: Skip if output already exists
        progress_callback: Optional callback for progress updates
    """

    def __init__(
        self,
        output_dir: Path | str,
        config: EnhanceConfig | None = None,
        parallel: int = 2,
        skip_existing: bool = True,
        progress_callback: Callable[[str, float], None] | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Default to Artemis HQ archival preset
        self.config = config or get_default_config()

        # Optimal parallelism for M3 Ultra
        # 2 concurrent = ~80% GPU utilization without memory pressure
        # 3 concurrent = max throughput but risk of OOM on long videos
        self.parallel = min(parallel, 3)  # Cap at 3 for stability

        self.skip_existing = skip_existing
        self.progress_callback = progress_callback

        # State file for resumability
        self.state_file = self.output_dir / ".batch_state.json"

        # Verify Topaz installation
        if not TOPAZ_FFMPEG.exists():
            raise RuntimeError(
                f"Topaz Video AI not found at {TOPAZ_APP}. "
                "Install from https://www.topazlabs.com/topaz-video-ai"
            )

    def _get_output_path(self, input_path: Path) -> Path:
        """Generate output path for enhanced video."""
        # Add model suffix to filename
        model_suffix = self.config.model.value
        stem = input_path.stem
        return self.output_dir / f"{stem}_{model_suffix}_4K.mp4"

    def _should_skip(self, input_path: Path, output_path: Path) -> bool:
        """Check if job should be skipped."""
        if not self.skip_existing:
            return False

        if not output_path.exists():
            return False

        # Skip if output is newer and non-empty
        if output_path.stat().st_size > 1024:  # > 1KB
            if output_path.stat().st_mtime > input_path.stat().st_mtime:
                return True

        return False

    async def _enhance_video(self, input_path: Path) -> JobResult:
        """Enhance a single video using Topaz CLI."""
        output_path = self._get_output_path(input_path)

        result = JobResult(
            input_path=input_path,
            output_path=output_path,
            status=JobStatus.PENDING,
            input_size_mb=input_path.stat().st_size / 1024 / 1024,
        )

        # Check if should skip
        if self._should_skip(input_path, output_path):
            result.status = JobStatus.SKIPPED
            result.output_size_mb = output_path.stat().st_size / 1024 / 1024
            return result

        result.status = JobStatus.PROCESSING
        result.started_at = datetime.now()

        # Build ffmpeg command with Topaz filters
        # Using Artemis HQ (ahq-12) as default
        model = self.config.model.value
        scale = self.config.scale

        # Topaz filter parameters
        # Note: Artemis models use automatic parameters, so we just need model and scale
        tvai_filter = f"tvai_up=model={model}:scale={scale}:device=0"

        # Add deinterlacing if needed
        if self.config.deinterlace:
            tvai_filter = f"bwdif=mode=1:parity=-1:deint=0,{tvai_filter}"

        cmd = [
            str(TOPAZ_FFMPEG),
            "-hide_banner",
            "-i",
            str(input_path),
            "-vf",
            tvai_filter,
            "-c:v",
            "hevc_videotoolbox",  # Hardware encoding
            "-b:v",
            self.config.bitrate,
            "-tag:v",
            "hvc1",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-y",  # Overwrite
            str(output_path),
        ]

        try:
            start_time = time.time()

            # Get current environment and add Topaz vars
            import os

            env = os.environ.copy()
            env.update(TOPAZ_ENV)

            # Run ffmpeg with Topaz environment
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            _stdout, stderr = await process.communicate()

            result.duration_seconds = time.time() - start_time
            result.completed_at = datetime.now()

            if process.returncode == 0 and output_path.exists():
                result.status = JobStatus.COMPLETED
                result.output_size_mb = output_path.stat().st_size / 1024 / 1024
            else:
                result.status = JobStatus.FAILED
                result.error = stderr.decode()[-500:] if stderr else "Unknown error"

        except Exception as e:
            result.status = JobStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()

        return result

    async def process_files(
        self,
        files: list[Path | str],
    ) -> BatchResult:
        """Process a list of video files in parallel.

        Args:
            files: List of video file paths

        Returns:
            BatchResult with all job results
        """
        files = [Path(f) for f in files]

        # Filter to valid video files
        video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
        files = [f for f in files if f.suffix.lower() in video_extensions and f.exists()]

        if not files:
            return BatchResult()

        result = BatchResult(started_at=datetime.now())

        # Create semaphore for parallelism control
        semaphore = asyncio.Semaphore(self.parallel)

        async def process_with_semaphore(file: Path) -> JobResult:
            async with semaphore:
                if self.progress_callback:
                    self.progress_callback(f"Processing: {file.name}", 0)
                job_result = await self._enhance_video(file)
                if self.progress_callback:
                    status = "✅" if job_result.status == JobStatus.COMPLETED else "❌"
                    self.progress_callback(f"{status} {file.name}", 100)
                return job_result

        # Process all files with controlled parallelism
        tasks = [process_with_semaphore(f) for f in files]
        job_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        for job_result in job_results:
            if isinstance(job_result, Exception):
                # Handle exceptions
                result.jobs.append(
                    JobResult(
                        input_path=Path("unknown"),
                        output_path=None,
                        status=JobStatus.FAILED,
                        error=str(job_result),
                    )
                )
            else:
                result.jobs.append(job_result)
                result.total_input_size_mb += job_result.input_size_mb
                result.total_output_size_mb += job_result.output_size_mb or 0
                result.total_duration_seconds += job_result.duration_seconds

        result.completed_at = datetime.now()

        # Save state for resumability
        self._save_state(result)

        return result

    async def process_directory(
        self,
        directory: Path | str,
        recursive: bool = False,
    ) -> BatchResult:
        """Process all videos in a directory.

        Args:
            directory: Directory containing videos
            recursive: Include subdirectories

        Returns:
            BatchResult with all job results
        """
        directory = Path(directory)

        if recursive:
            files = list(directory.rglob("*.mp4")) + list(directory.rglob("*.mov"))
        else:
            files = list(directory.glob("*.mp4")) + list(directory.glob("*.mov"))

        # Sort by size (smaller first for faster initial feedback)
        files.sort(key=lambda f: f.stat().st_size)

        return await self.process_files(files)

    def _save_state(self, result: BatchResult):
        """Save batch state for resumability."""
        self.state_file.write_text(json.dumps(result.to_dict(), indent=2))

    def get_estimate(self, files: list[Path | str]) -> dict:
        """Estimate processing time for files.

        Returns dict with:
        - total_duration_hours: Estimated processing time
        - total_size_gb: Total input size
        - videos_count: Number of videos
        """
        files = [Path(f) for f in files if Path(f).exists()]

        total_size = sum(f.stat().st_size for f in files)
        total_size_gb = total_size / 1024 / 1024 / 1024

        # Estimate video duration from file size (rough: ~15 MB/min for SD)
        estimated_video_hours = total_size_gb * 1024 / 15 / 60

        # Processing speed estimate for Artemis HQ 4x on M3 Ultra
        # With parallel=2: ~1.5x realtime
        processing_factor = 1.5 / self.parallel
        estimated_hours = estimated_video_hours * processing_factor

        return {
            "videos_count": len(files),
            "total_size_gb": round(total_size_gb, 2),
            "estimated_video_hours": round(estimated_video_hours, 1),
            "estimated_processing_hours": round(estimated_hours, 1),
            "parallel_streams": self.parallel,
            "model": self.config.model.value,
        }


async def enhance_archive(
    source_dir: Path | str,
    output_dir: Path | str,
    parallel: int = 2,
    model: TopazModel = DEFAULT_MODEL,
) -> BatchResult:
    """Quick function to enhance an entire video archive.

    Args:
        source_dir: Directory with source videos
        output_dir: Directory for enhanced output
        parallel: Concurrent video streams (default: 2)
        model: Topaz model (default: Artemis HQ)

    Returns:
        BatchResult with processing summary

    Example:
        result = await enhance_archive(
            "/Volumes/WesData",
            "/Volumes/WesData/Enhanced",
        )
        print(f"Completed: {result.completed_count}/{len(result.jobs)}")
    """
    config = get_default_config()
    config.model = model

    enhancer = BatchEnhancer(
        output_dir=output_dir,
        config=config,
        parallel=parallel,
    )

    return await enhancer.process_directory(source_dir)
