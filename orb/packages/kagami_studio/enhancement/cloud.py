"""Topaz Cloud API — Production Implementation.

SOTA video enhancement via Topaz Labs Cloud API.
Optimized for parallel uploads and batch processing.

API Flow:
1. POST /video/ — Create request, get estimate
2. PATCH /video/{id}/accept — Reserve credits, get upload URLs
3. PUT {uploadUrl} — Upload video parts
4. PATCH /video/{id}/complete-upload/ — Start processing
5. GET /video/{id}/status — Poll until complete
6. GET {downloadUrl} — Download enhanced video

Default Model: Artemis HQ (ahq-12) — Maximum fidelity, minimal hallucination.

Usage:
    from kagami_studio.enhancement.cloud import TopazCloud, enhance_archive_cloud

    # Single video
    cloud = TopazCloud()
    result = await cloud.enhance("/path/to/video.mp4", output_dir="/output")

    # Batch with parallelism
    results = await enhance_archive_cloud(
        source_dir="/Volumes/WesData",
        output_dir="/Volumes/WesData/Enhanced_4K",
        parallel_uploads=3,
    )
"""

import asyncio
import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

import aiofiles
import httpx

# API Configuration
API_BASE = "https://api.topazlabs.com"
CHUNK_SIZE = 100 * 1024 * 1024  # 100MB chunks for multipart


class TopazModel(str, Enum):
    """Topaz Video AI models."""

    ARTEMIS_HQ = "ahq-12"  # 🏆 DEFAULT — Highest quality
    ARTEMIS_MQ = "amq-13"  # Medium quality
    ARTEMIS_LQ = "alq-13"  # Fast
    PROTEUS = "prob-4"  # Manual control
    DIONE_TV = "dtv-4"  # VHS/broadcast
    IRIS = "iris-3"  # Face enhancement


class JobStatus(str, Enum):
    """Cloud job status."""

    CREATED = "created"
    ACCEPTED = "accepted"
    UPLOADING = "uploading"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class VideoInfo:
    """Video metadata for API requests."""

    path: Path
    width: int
    height: int
    duration: float
    fps: float
    frame_count: int
    size: int
    codec: str = "mpeg4"
    container: str = "mp4"

    @classmethod
    def from_file(cls, path: Path, timeout: int = 10) -> "VideoInfo":
        """Extract video info using ffprobe."""
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        data = json.loads(result.stdout)

        vs = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
        fmt = data.get("format", {})

        # Parse frame rate
        fps_str = vs.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) > 0 else 30.0
        else:
            fps = float(fps_str)

        duration = float(fmt.get("duration", 0))
        frame_count = int(vs.get("nb_frames", 0)) or int(duration * fps)

        return cls(
            path=path,
            width=int(vs.get("width", 640)),
            height=int(vs.get("height", 480)),
            duration=duration,
            fps=round(fps, 3),
            frame_count=frame_count,
            size=int(fmt.get("size", path.stat().st_size)),
            codec=vs.get("codec_name", "mpeg4"),
            container=path.suffix.lstrip(".") or "mp4",
        )

    def to_api_source(self) -> dict:
        """Convert to API source format."""
        return {
            "container": self.container,
            "codec": self.codec,
            "resolution": {"width": self.width, "height": self.height},
            "frameRate": self.fps,
            "frameCount": self.frame_count,
            "duration": self.duration,
            "size": self.size,
        }


@dataclass
class CloudJob:
    """Represents a cloud enhancement job."""

    request_id: str
    video_info: VideoInfo
    status: JobStatus = JobStatus.CREATED
    upload_id: str | None = None
    upload_urls: list[str] = field(default_factory=list)
    estimated_credits: tuple[int, int] = (0, 0)
    estimated_time: tuple[int, int] = (0, 0)
    actual_credits: int = 0
    download_url: str | None = None
    output_path: Path | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None


@dataclass
class CreditReport:
    """Credit usage report for batch operations."""

    total_estimated_min: int = 0
    total_estimated_max: int = 0
    total_actual: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_pending: int = 0

    def __str__(self) -> str:
        return (
            f"💰 CREDIT REPORT\n"
            f"   Estimated: {self.total_estimated_min:,}-{self.total_estimated_max:,} credits\n"
            f"   Actual: {self.total_actual:,} credits\n"
            f"   Jobs: {self.jobs_completed} complete, {self.jobs_pending} pending, {self.jobs_failed} failed"
        )


def _get_api_key() -> str:
    """Get Topaz API key from keychain."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", "kagami", "-a", "topaz_api_key", "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(
            "Topaz API key not found in keychain. Set with: "
            "security add-generic-password -s kagami -a topaz_api_key -w YOUR_KEY"
        )
    return result.stdout.strip()


class TopazCloud:
    """Topaz Cloud API client.

    Handles the full enhancement workflow:
    - Create job request
    - Accept and get upload URLs
    - Upload video (parallel chunks)
    - Complete upload to start processing
    - Poll for completion
    - Download result

    Args:
        api_key: Topaz API key (default: from keychain)
        model: Enhancement model (default: Artemis HQ)
        scale: Output scale factor (default: 4 for 4K)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: TopazModel = TopazModel.ARTEMIS_HQ,
        scale: int = 4,
    ):
        self.api_key = api_key or _get_api_key()
        self.model = model
        self.scale = scale
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=API_BASE,
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30.0, read=300.0),
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def create_job(self, video_info: VideoInfo) -> CloudJob:
        """Create enhancement job request."""
        client = await self._get_client()

        # Calculate output resolution
        out_width = video_info.width * self.scale
        out_height = video_info.height * self.scale

        payload = {
            "source": video_info.to_api_source(),
            "filters": [{"model": self.model.value, "scale": self.scale}],
            "output": {
                "resolution": {"width": out_width, "height": out_height},
                "frameRate": video_info.fps,
                "dynamicCompressionLevel": "High",
                "audioTransfer": "Copy",
                "audioCodec": "AAC",
            },
        }

        response = await client.post("/video/", json=payload)
        data = response.json()

        if "requestId" not in data:
            raise ValueError(f"Failed to create job: {data}")

        return CloudJob(
            request_id=data["requestId"],
            video_info=video_info,
            estimated_credits=tuple(data.get("estimates", {}).get("cost", [0, 0])),
            estimated_time=tuple(data.get("estimates", {}).get("time", [0, 0])),
        )

    async def accept_job(self, job: CloudJob, max_retries: int = 12) -> CloudJob:
        """Accept job to reserve credits and get upload URLs.

        Includes retry logic for "credit refill in progress" errors.
        The credit refill can take up to 60 seconds.
        """
        client = await self._get_client()

        for attempt in range(max_retries):
            response = await client.patch(f"/video/{job.request_id}/accept")
            data = response.json()

            if "uploadId" in data:
                job.upload_id = data["uploadId"]
                job.upload_urls = data.get("urls", [])
                job.status = JobStatus.ACCEPTED
                return job

            # Check for retryable errors
            error_msg = data.get("message", "")

            # Insufficient credits - not retryable
            if "insufficient credits" in error_msg.lower():
                raise ValueError(
                    "Topaz Cloud: Insufficient credits! "
                    "Buy more at https://www.topazlabs.com/enhance-api "
                    "or use LOCAL mode with BatchEnhancer (requires Topaz Video AI app)"
                )

            if "refill in progress" in error_msg.lower() or "try again" in error_msg.lower():
                wait_time = 5  # Fixed 5s waits (credit refill takes ~30-60s total)
                print(
                    f"   ⏳ Credit refill in progress... waiting {wait_time}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait_time)
                continue

            # Non-retryable error
            raise ValueError(f"Failed to accept job: {data}")

        raise ValueError(
            f"Failed to accept job after {max_retries} retries ({max_retries * 5}s): credit refill timeout"
        )

    async def upload_video(
        self,
        job: CloudJob,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> CloudJob:
        """Upload video to S3."""
        if not job.upload_urls:
            raise ValueError("No upload URLs - call accept_job first")

        job.status = JobStatus.UPLOADING
        upload_url = job.upload_urls[0]  # Single part upload

        # Read file and upload

        async with aiofiles.open(job.video_info.path, "rb") as f:
            data = await f.read()

        # Upload with httpx (not using base client - direct S3 upload)
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as upload_client:
            response = await upload_client.put(
                upload_url,
                content=data,
                headers={"Content-Type": "video/mp4"},
            )

            if response.status_code not in (200, 201):
                raise ValueError(f"Upload failed: {response.status_code} {response.text[:200]}")

            # Get ETag for completion
            etag = response.headers.get("ETag", "").strip('"')

        job._etag = etag
        return job

    async def complete_upload(self, job: CloudJob) -> CloudJob:
        """Complete upload to start processing."""
        client = await self._get_client()

        # Calculate MD5 hash
        async with aiofiles.open(job.video_info.path, "rb") as f:
            data = await f.read()
        md5_hash = hashlib.md5(data).hexdigest()

        payload = {
            "uploadResults": [{"partNum": 1, "eTag": getattr(job, "_etag", "")}],
            "md5Hash": md5_hash,
        }

        response = await client.patch(
            f"/video/{job.request_id}/complete-upload/",
            json=payload,
        )

        if response.status_code not in (200, 201, 204):
            raise ValueError(f"Complete upload failed: {response.text[:200]}")

        job.status = JobStatus.QUEUED
        return job

    async def get_status(self, job: CloudJob) -> CloudJob:
        """Get job processing status."""
        client = await self._get_client()

        response = await client.get(f"/video/{job.request_id}/status")
        data = response.json()

        status_str = data.get("status", "").lower()
        if status_str in [s.value for s in JobStatus]:
            job.status = JobStatus(status_str)

        # Capture actual credits used
        if "cost" in data:
            job.actual_credits = data["cost"]
        elif "estimates" in data and "cost" in data["estimates"]:
            # Use estimate midpoint as approximation until final
            costs = data["estimates"]["cost"]
            job.actual_credits = (costs[0] + costs[1]) // 2

        if job.status == JobStatus.COMPLETE:
            job.download_url = data.get("download", {}).get("url")
            job.completed_at = datetime.now()
            # Final cost is in the response
            if "cost" in data:
                job.actual_credits = data["cost"]
        elif job.status == JobStatus.FAILED:
            job.error = data.get("error", "Unknown error")

        return job

    async def get_balance(self) -> dict:
        """Get current credit balance."""
        client = await self._get_client()
        try:
            response = await client.get("/credits/balance")
            return response.json()
        except Exception:
            return {"balance": "unknown", "error": "Could not fetch balance"}

    async def wait_for_completion(
        self,
        job: CloudJob,
        poll_interval: float = 10.0,
        timeout: float = 3600.0,
    ) -> CloudJob:
        """Poll until job completes."""
        start = datetime.now()

        while True:
            job = await self.get_status(job)

            if job.status in (JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED):
                return job

            elapsed = (datetime.now() - start).total_seconds()
            if elapsed > timeout:
                job.status = JobStatus.FAILED
                job.error = "Timeout waiting for completion"
                return job

            await asyncio.sleep(poll_interval)

    async def download_result(self, job: CloudJob, output_dir: Path) -> CloudJob:
        """Download enhanced video."""
        if not job.download_url:
            raise ValueError("No download URL - job may not be complete")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{job.video_info.path.stem}_{self.model.value}_4K.mp4"

        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            response = await client.get(job.download_url)

            async with aiofiles.open(output_path, "wb") as f:
                await f.write(response.content)

        job.output_path = output_path
        return job

    async def enhance(
        self,
        video_path: Path | str,
        output_dir: Path | str,
        wait: bool = True,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> CloudJob:
        """Full enhancement workflow for single video.

        Args:
            video_path: Input video file
            output_dir: Directory for output
            wait: Wait for completion (default: True)
            progress_callback: Optional callback(stage, progress)

        Returns:
            CloudJob with result info
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)

        try:
            # Step 1: Get video info
            if progress_callback:
                progress_callback("analyzing", 0)
            video_info = VideoInfo.from_file(video_path)

            # Step 2: Create job
            if progress_callback:
                progress_callback("creating", 10)
            job = await self.create_job(video_info)

            # Step 3: Accept job
            if progress_callback:
                progress_callback("accepting", 20)
            job = await self.accept_job(job)

            # Step 4: Upload
            if progress_callback:
                progress_callback("uploading", 30)
            job = await self.upload_video(job)

            # Step 5: Complete upload
            if progress_callback:
                progress_callback("queuing", 70)
            job = await self.complete_upload(job)

            if not wait:
                return job

            # Step 6: Wait for processing
            if progress_callback:
                progress_callback("processing", 80)
            job = await self.wait_for_completion(job)

            # Step 7: Download
            if job.status == JobStatus.COMPLETE:
                if progress_callback:
                    progress_callback("downloading", 90)
                job = await self.download_result(job, output_dir)
                if progress_callback:
                    progress_callback("complete", 100)

            return job

        except Exception as e:
            job = CloudJob(
                request_id="error",
                video_info=VideoInfo.from_file(video_path) if video_path.exists() else None,
                status=JobStatus.FAILED,
                error=str(e),
            )
            return job
        finally:
            await self.close()


async def enhance_archive_cloud(
    source_dir: Path | str,
    output_dir: Path | str,
    model: TopazModel = TopazModel.ARTEMIS_HQ,
    scale: int = 4,
    parallel_uploads: int = 3,
    parallel_downloads: int = 2,
    wait: bool = True,
) -> tuple[list[CloudJob], CreditReport]:
    """Enhance entire archive via Topaz Cloud with parallelism.

    Args:
        source_dir: Directory with source videos
        output_dir: Directory for enhanced output
        model: Enhancement model (default: Artemis HQ)
        scale: Output scale (default: 4x)
        parallel_uploads: Concurrent uploads (default: 3)
        parallel_downloads: Concurrent downloads (default: 2)
        wait: Wait for all to complete

    Returns:
        Tuple of (List of CloudJob results, CreditReport)
    """
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find video files (exclude any we've already processed)
    video_files = []
    for ext in ["*.mp4", "*.mov", "*.avi", "*.mkv"]:
        for f in source_dir.glob(ext):
            # Skip if output already exists
            output_name = f"{f.stem}_{model.value}_4K.mp4"
            if not (output_dir / output_name).exists():
                video_files.append(f)

    # Sort by size (smaller first for faster feedback)
    video_files.sort(key=lambda f: f.stat().st_size)

    # Initialize credit tracking
    report = CreditReport()

    print(f"📼 TOPAZ CLOUD BATCH — {len(video_files)} videos")
    print(f"   Model: {model.value}")
    print(f"   Scale: {scale}x")
    print(f"   Parallel uploads: {parallel_uploads}")
    print("=" * 60)

    # Create semaphores for rate limiting
    upload_sem = asyncio.Semaphore(parallel_uploads)
    download_sem = asyncio.Semaphore(parallel_downloads)

    api_key = _get_api_key()
    jobs: list[CloudJob] = []

    async def process_video(video_path: Path) -> CloudJob:
        """Process single video with semaphore control."""
        async with upload_sem:
            cloud = TopazCloud(api_key=api_key, model=model, scale=scale)

            try:
                # Steps 1-5: Create, accept, upload, complete
                video_info = VideoInfo.from_file(video_path)
                job = await cloud.create_job(video_info)

                # Track estimated credits
                report.total_estimated_min += job.estimated_credits[0]
                report.total_estimated_max += job.estimated_credits[1]

                size_mb = video_info.size // 1024 // 1024
                print(
                    f"📁 {video_path.name} ({size_mb}MB) → {job.estimated_credits[0]}-{job.estimated_credits[1]} credits"
                )

                job = await cloud.accept_job(job)
                print("   📤 Uploading...")

                job = await cloud.upload_video(job)
                job = await cloud.complete_upload(job)
                print("   ✅ Queued for processing")

                return job

            except Exception as e:
                err_str = str(e)
                if "Insufficient credits" in err_str:
                    print(f"   💳 {video_path.name}: INSUFFICIENT CREDITS — stopping batch")
                    raise  # Re-raise to stop the batch
                print(f"   ❌ {video_path.name}: {err_str[:80]}")
                return CloudJob(
                    request_id="error",
                    video_info=video_info if "video_info" in dir() else None,
                    status=JobStatus.FAILED,
                    error=str(e),
                )
            finally:
                await cloud.close()

    # Upload all videos in parallel
    try:
        tasks = [process_video(f) for f in video_files]
        jobs = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed jobs
        processed_jobs = []
        for _i, result in enumerate(jobs):
            if isinstance(result, Exception):
                processed_jobs.append(
                    CloudJob(
                        request_id="error",
                        video_info=None,
                        status=JobStatus.FAILED,
                        error=str(result),
                    )
                )
            else:
                processed_jobs.append(result)
        jobs = processed_jobs

    except Exception as e:
        print(f"\n⚠️  Batch stopped: {e}")

    # Filter to successful uploads
    pending_jobs = [j for j in jobs if j.status == JobStatus.QUEUED]
    failed_jobs = [j for j in jobs if j.status == JobStatus.FAILED]

    report.jobs_pending = len(pending_jobs)
    report.jobs_failed = len(failed_jobs)

    print(f"\n{'=' * 60}")
    print("📊 UPLOAD SUMMARY")
    print(f"   Queued: {len(pending_jobs)}/{len(jobs)}")
    print(f"   Est. Credits: {report.total_estimated_min:,}-{report.total_estimated_max:,}")

    if not wait or not pending_jobs:
        print(f"\n{report}")
        return jobs, report

    # Wait for all to complete and download
    print(f"\n⏳ Waiting for {len(pending_jobs)} jobs to process...")

    async def wait_and_download(job: CloudJob) -> CloudJob:
        """Wait for job and download result."""
        cloud = TopazCloud(api_key=api_key, model=model, scale=scale)
        try:
            job = await cloud.wait_for_completion(job, poll_interval=30.0)

            if job.status == JobStatus.COMPLETE:
                async with download_sem:
                    job = await cloud.download_result(job, output_dir)
                    print(f"   ✅ {job.output_path.name} ({job.actual_credits} credits)")
            else:
                print(f"   ❌ {job.video_info.path.name}: {job.error}")

            return job
        finally:
            await cloud.close()

    # Wait and download in parallel
    final_tasks = [wait_and_download(j) for j in pending_jobs]
    final_jobs = await asyncio.gather(*final_tasks)

    # Merge results
    result_map = {j.request_id: j for j in final_jobs}
    final_results = []
    for j in jobs:
        if j.request_id in result_map:
            final_results.append(result_map[j.request_id])
        else:
            final_results.append(j)

    # Final credit report
    report.jobs_completed = sum(1 for j in final_results if j.status == JobStatus.COMPLETE)
    report.jobs_failed = sum(1 for j in final_results if j.status == JobStatus.FAILED)
    report.jobs_pending = sum(
        1 for j in final_results if j.status in (JobStatus.QUEUED, JobStatus.PROCESSING)
    )
    report.total_actual = sum(j.actual_credits for j in final_results if j.actual_credits)

    print(f"\n{'=' * 60}")
    print(report)

    return final_results, report
