"""Topaz Video AI — Unified Local + Cloud Enhancement.

SINGLE PATH for all video enhancement. No alternatives.

Architecture:
    TopazEnhancer
    ├── Local CLI (Topaz Video AI app) — PREFERRED
    └── Cloud API (Topaz Labs REST) — FALLBACK

Hardware: M3 Ultra (32 cores, 80 GPU, 512GB RAM)
Models: Proteus, Artemis, Dione, Iris, Nyx, Apollo
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_enhanced")

# Topaz-specific error patterns to detect silent failures
TOPAZ_ERROR_PATTERNS = [
    "failed to load model",
    "tvai_up not found",
    "tvai_fi not found",
    "unsupported device",
    "license",
    "no valid license",
    "model not found",
    "could not find model",
    "metal not available",
    "unable to load",
    "initialization failed",
]


def _get_secret(name: str) -> str | None:
    """Get secret from keychain."""
    try:
        from kagami.core.security import get_secret

        return get_secret(name)
    except Exception:
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "kagami", "-a", name, "-w"],
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None


# =============================================================================
# HARDWARE DETECTION (M3 Ultra Optimized)
# =============================================================================


@dataclass
class HardwareInfo:
    """System hardware capabilities."""

    chip: str
    cores: int
    performance_cores: int
    efficiency_cores: int
    memory_gb: int
    gpu_cores: int
    metal_support: bool = True
    neural_engine: bool = True

    @classmethod
    def detect(cls) -> HardwareInfo:
        """Detect system hardware."""
        try:
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType", "-json"],
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)
            hw = data["SPHardwareDataType"][0]

            chip = hw.get("chip_type", "Unknown")
            memory = int(hw.get("physical_memory", "0 GB").split()[0])
            cores_str = hw.get("number_processors", "0")
            total_cores = int(cores_str.split()[0]) if cores_str else 0

            is_m3_ultra = "M3 Ultra" in chip

            return cls(
                chip=chip,
                cores=total_cores,
                performance_cores=24 if is_m3_ultra else (total_cores * 3 // 4),
                efficiency_cores=8 if is_m3_ultra else (total_cores // 4),
                memory_gb=memory,
                gpu_cores=80 if is_m3_ultra else 30,
            )
        except Exception:
            return cls(
                chip="Unknown",
                cores=8,
                performance_cores=6,
                efficiency_cores=2,
                memory_gb=16,
                gpu_cores=10,
            )

    def summary(self) -> str:
        """Human-readable summary."""
        return f"{self.chip} • {self.cores} cores • {self.gpu_cores} GPU • {self.memory_gb}GB"


_hardware: HardwareInfo | None = None


def get_hardware() -> HardwareInfo:
    """Get cached hardware info."""
    global _hardware
    if _hardware is None:
        _hardware = HardwareInfo.detect()
    return _hardware


# =============================================================================
# MODELS & PRESETS
# =============================================================================


class TopazModel(str, Enum):
    """Topaz Video AI models."""

    # Artemis — General Enhancement
    ARTEMIS_MQ = "amq-13"  # Medium quality, balanced
    ARTEMIS_HQ = "ahq-12"  # High quality, slower
    ARTEMIS_LQ = "alq-13"  # Low quality input, fast
    ARTEMIS_AA = "aaa-10"  # Anti-aliasing focus

    # Dione — Interlaced/VHS
    DIONE_TV = "dtv-4"  # Broadcast/VHS
    DIONE_ROBUST = "dtd-4"  # Heavy artifacts
    DIONE_DV = "ddv-3"  # MiniDV camera

    # Proteus — Maximum Control (6 parameters)
    PROTEUS = "prob-4"  # Full control
    PROTEUS_AUTO = "prap-2"  # Auto settings

    # Gaia — CG/Animation
    GAIA_HQ = "ghq-5"  # Animation
    GAIA_CG = "gcg-5"  # 3D renders

    # Specialty
    IRIS = "iris-1"  # Face enhancement
    NYX = "nyx-1"  # Low light

    # Frame Interpolation
    APOLLO = "apo-8"  # High quality FI
    APOLLO_FAST = "apf-1"  # Fast FI
    CHRONOS = "chr-2"  # Slow motion
    CHRONOS_FAST = "chf-3"  # Fast slow-mo


TOPAZ_MODELS = {
    TopazModel.ARTEMIS_MQ: {"name": "Artemis MQ v13", "best_for": ["general", "vhs", "dvd"]},
    TopazModel.ARTEMIS_HQ: {"name": "Artemis HQ v12", "best_for": ["high_quality", "film"]},
    TopazModel.ARTEMIS_LQ: {"name": "Artemis LQ v13", "best_for": ["very_noisy", "old_vhs"]},
    TopazModel.PROTEUS: {"name": "Proteus v4", "best_for": ["custom", "fine_tuning"]},
    TopazModel.DIONE_TV: {"name": "Dione TV v4", "best_for": ["vhs", "interlaced", "broadcast"]},
    TopazModel.IRIS: {"name": "Iris v1", "best_for": ["faces", "portraits"]},
    TopazModel.NYX: {"name": "Nyx v1", "best_for": ["low_light", "dark", "night"]},
    TopazModel.APOLLO: {"name": "Apollo v8", "best_for": ["frame_interpolation"]},
}


class EnhancePreset(str, Enum):
    """Enhancement presets."""

    NONE = "none"
    FAST = "fast"  # 2x, quick
    BALANCED = "balanced"  # 4x, moderate
    CINEMATIC = "cinematic"  # 4x, maximum quality
    VHS = "vhs"  # VHS restoration
    FACES = "faces"  # Face enhancement
    LOW_LIGHT = "low_light"  # Dark footage


PRESET_CONFIGS = {
    EnhancePreset.NONE: None,
    EnhancePreset.FAST: {
        "model": TopazModel.ARTEMIS_LQ,
        "scale": 2,
        "denoise": 10,
        "sharpen": 5,
    },
    EnhancePreset.BALANCED: {
        "model": TopazModel.ARTEMIS_MQ,
        "scale": 4,
        "denoise": 15,
        "sharpen": 10,
        "dehalo": 5,
    },
    EnhancePreset.CINEMATIC: {
        "model": TopazModel.PROTEUS,
        "scale": 4,
        "denoise": 20,
        "sharpen": 15,
        "dehalo": 10,
        "recover_detail": 40,
        "anti_alias": 15,
    },
    EnhancePreset.VHS: {
        "model": TopazModel.DIONE_TV,
        "scale": 4,
        "denoise": 35,
        "sharpen": 20,
        "dehalo": 15,
        "deinterlace": True,
    },
    EnhancePreset.FACES: {
        "model": TopazModel.IRIS,
        "scale": 2,
        "denoise": 15,
    },
    EnhancePreset.LOW_LIGHT: {
        "model": TopazModel.NYX,
        "scale": 2,
        "denoise": 25,
    },
}

VHS_PRESETS = {
    "standard": {
        "model": TopazModel.DIONE_TV,
        "scale": 2,
        "denoise": 25,
        "sharpen": 15,
        "dehalo": 10,
        "deinterlace": True,  # VHS is ALWAYS interlaced (480i)
    },
    "maximum": {
        "model": TopazModel.PROTEUS,
        "scale": 4,
        "denoise": 35,
        "sharpen": 25,
        "dehalo": 20,
        "recover_detail": 50,
        "deinterlace": True,  # VHS is ALWAYS interlaced (480i)
    },
    "fast": {
        "model": TopazModel.ARTEMIS_MQ,  # MQ has cached CoreML models, LQ doesn't
        "scale": 2,
        "denoise": 20,
        "sharpen": 10,
        "deinterlace": True,  # VHS is ALWAYS interlaced (480i)
    },
}


# =============================================================================
# CONFIG & RESULT
# =============================================================================


@dataclass
class TopazConfig:
    """Enhancement configuration."""

    model: TopazModel | str = TopazModel.PROTEUS
    scale: int = 4
    denoise: int = 0
    sharpen: int = 0
    dehalo: int = 0
    recover_detail: int = 0  # Proteus only
    anti_alias: int = 0  # Proteus only
    deinterlace: bool = False
    fps_target: int | None = None  # Frame interpolation

    # Output
    output_format: str = "mp4"
    codec: str = "hevc_videotoolbox"  # Hardware H.265
    bitrate: str = "50M"
    crf: int = 18


@dataclass
class EnhanceResult:
    """Enhancement result."""

    success: bool
    video_path: Path | None = None
    duration_s: float = 0.0
    resolution: tuple[int, int] = (0, 0)
    processing_time_s: float = 0.0
    model_used: str = ""
    preset_used: str = ""
    error: str | None = None
    cost_cents: float = 0.0  # Cloud only


# =============================================================================
# TOPAZ ENHANCER
# =============================================================================


class TopazEnhancer:
    """Unified Topaz Video AI enhancement.

    Automatically uses:
    1. Local CLI (if Topaz Video AI installed) — PREFERRED
    2. Cloud API (if API key available) — FALLBACK

    Usage:
        enhancer = TopazEnhancer()
        await enhancer.initialize()

        # Quick preset
        result = await enhancer.enhance(
            "/path/to/video.mp4",
            preset=EnhancePreset.CINEMATIC,
        )

        # Full control
        result = await enhancer.enhance(
            input_path,
            model=TopazModel.PROTEUS,
            scale=4,
            denoise=25,
            sharpen=20,
            recover_detail=40,
        )
    """

    # Paths - VERIFIED: App is "Topaz Video.app" not "Topaz Video AI.app"
    TOPAZ_APP = Path("/Applications/Topaz Video.app")
    TOPAZ_FFMPEG = TOPAZ_APP / "Contents/MacOS/ffmpeg"  # In MacOS, not Resources
    TOPAZ_MODELS = TOPAZ_APP / "Contents/Resources/models"

    def __init__(self):
        self._has_local = False
        self._has_cloud = False
        self._cloud_key: str | None = None
        self._client: httpx.AsyncClient | None = None
        self._initialized = False
        self.hardware = get_hardware()

    async def initialize(self) -> bool:
        """Initialize enhancer."""
        if self._initialized:
            return True

        # Check local
        if self.TOPAZ_FFMPEG.exists():
            self._has_local = True
            logger.info(f"✓ Topaz Local ready ({self.hardware.summary()})")

        # Check cloud
        self._cloud_key = _get_secret("topaz_api_key")
        if self._cloud_key:
            self._has_cloud = True
            self._client = httpx.AsyncClient(
                base_url="https://api.topazlabs.com",
                headers={
                    "X-API-Key": self._cloud_key,
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30.0, read=300.0),
            )
            logger.info("✓ Topaz Cloud ready")

        self._initialized = True

        if not self._has_local and not self._has_cloud:
            logger.warning("No Topaz available (install app or set API key)")
            return False

        return True

    async def enhance(
        self,
        input_path: Path | str,
        output_path: Path | str | None = None,
        *,
        preset: EnhancePreset | str | None = None,
        model: TopazModel | str | None = None,
        scale: int = 4,
        denoise: int = 0,
        sharpen: int = 0,
        dehalo: int = 0,
        recover_detail: int = 0,
        anti_alias: int = 0,
        deinterlace: bool = False,
        fps_target: int | None = None,
        use_cloud: bool = False,
        progress_callback: Callable | None = None,
    ) -> EnhanceResult:
        """Enhance video.

        Args:
            input_path: Input video
            output_path: Output path (auto-generated if None)
            preset: Preset to use (overridden by explicit params)
            model: Topaz model
            scale: Upscale factor (1-4)
            denoise: Noise reduction (0-100)
            sharpen: Sharpening (0-100)
            dehalo: Halo removal (0-100)
            recover_detail: Detail recovery (0-100, Proteus only)
            anti_alias: Anti-aliasing (0-100, Proteus only)
            deinterlace: Apply deinterlacing
            fps_target: Target FPS for interpolation
            use_cloud: Force cloud API
            progress_callback: Progress updates

        Returns:
            EnhanceResult with enhanced video
        """
        if not self._initialized:
            await self.initialize()

        input_path = Path(input_path)
        if not input_path.exists():
            return EnhanceResult(success=False, error=f"File not found: {input_path}")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if output_path is None:
            output_path = OUTPUT_DIR / f"{input_path.stem}_enhanced.mp4"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get preset config
        if preset:
            if isinstance(preset, str):
                preset = EnhancePreset(preset)
            config = PRESET_CONFIGS.get(preset)
            if config is None:
                # NONE preset - just copy
                import shutil

                shutil.copy(input_path, output_path)
                return EnhanceResult(
                    success=True,
                    video_path=output_path,
                    preset_used="none",
                )
        else:
            config = {}

        # Merge params (explicit > preset)
        final_model = model or config.get("model", TopazModel.PROTEUS)
        if isinstance(final_model, TopazModel):
            final_model = final_model.value
        elif isinstance(final_model, str) and not final_model.startswith(
            ("a", "d", "p", "g", "i", "n")
        ):
            # Try to resolve enum
            try:
                final_model = TopazModel(final_model).value
            except ValueError:
                pass

        final_scale = scale if scale != 4 else config.get("scale", 4)
        final_denoise = denoise if denoise != 0 else config.get("denoise", 0)
        final_sharpen = sharpen if sharpen != 0 else config.get("sharpen", 0)
        final_dehalo = dehalo if dehalo != 0 else config.get("dehalo", 0)
        final_recover = recover_detail if recover_detail != 0 else config.get("recover_detail", 0)
        final_anti_alias = anti_alias if anti_alias != 0 else config.get("anti_alias", 0)
        final_deinterlace = deinterlace or config.get("deinterlace", False)

        # Get input dimensions for aspect ratio preservation
        input_resolution = self._get_video_resolution(input_path)
        input_width, input_height = input_resolution
        if input_width == 0 or input_height == 0:
            return EnhanceResult(
                success=False, error=f"Could not read video dimensions: {input_path}"
            )

        # Calculate target resolution preserving aspect ratio
        target_width = input_width * final_scale
        target_height = input_height * final_scale
        logger.info(
            f"📐 Aspect ratio: {input_width}x{input_height} → {target_width}x{target_height} ({final_scale}x)"
        )

        start = time.perf_counter()

        # Route to local or cloud
        if use_cloud or not self._has_local:
            if not self._has_cloud:
                return EnhanceResult(success=False, error="No Topaz available")
            result = await self._enhance_cloud(
                input_path,
                output_path,
                final_model,
                final_scale,
                final_denoise,
                final_sharpen,
                final_dehalo,
                final_deinterlace,
                progress_callback,
            )
        else:
            result = await self._enhance_local(
                input_path,
                output_path,
                final_model,
                final_scale,
                final_denoise,
                final_sharpen,
                final_dehalo,
                final_recover,
                final_anti_alias,
                final_deinterlace,
                fps_target,
                progress_callback,
                target_width,
                target_height,
            )

        result.processing_time_s = time.perf_counter() - start
        result.model_used = final_model
        result.preset_used = (
            preset.value if isinstance(preset, EnhancePreset) else str(preset or "custom")
        )

        return result

    async def _enhance_local(
        self,
        input_path: Path,
        output_path: Path,
        model: str,
        scale: int,
        denoise: int,
        sharpen: int,
        dehalo: int,
        recover_detail: int,
        anti_alias: int,
        deinterlace: bool,
        fps_target: int | None,
        progress_callback: Callable | None,
        target_width: int,
        target_height: int,
    ) -> EnhanceResult:
        """Enhance using local Topaz CLI with aspect ratio preservation."""
        logger.info(f"🎬 Topaz Local: {model} {scale}x → {target_width}x{target_height}")
        logger.info(f"   {self.hardware.summary()}")

        # Build filter chain
        filters = []

        if deinterlace:
            filters.append("bwdif=mode=0:parity=-1:deint=0")

        # Topaz filter with CORRECT parameter names and scaling
        # VERIFIED against tvai_up filter docs: all params use -1 to 1 range, not 0-100
        tvai_params = [f"model={model}", f"scale={scale}", "device=0"]
        if denoise > 0:
            # noise: -1 to 1 (0-100 maps to 0-1 for positive values)
            tvai_params.append(f"noise={denoise / 100:.2f}")
        if sharpen > 0:
            # blur: -1 to 1 (positive = sharpen, negative = soften)
            tvai_params.append(f"blur={sharpen / 100:.2f}")
        if dehalo > 0:
            # halo: -1 to 1 (removes halo/ring artifacts)
            tvai_params.append(f"halo={dehalo / 100:.2f}")
        if recover_detail > 0:
            # details: -1 to 1 (recovers fine texture lost to in-camera noise suppression)
            tvai_params.append(f"details={recover_detail / 100:.2f}")
        if anti_alias > 0:
            # preblur: -1 to 1 (negative = antialiasing, positive = deblurring)
            tvai_params.append(f"preblur={-anti_alias / 100:.2f}")

        filters.append(f"tvai_up={':'.join(tvai_params)}")

        # CRITICAL: Force output to exact target dimensions (aspect ratio preservation)
        # This ensures 4:3 VHS doesn't become 16:9 letterboxed garbage
        filters.append(f"scale={target_width}:{target_height}:flags=lanczos")
        filters.append(f"setdar={target_width}/{target_height}")  # Set display aspect ratio

        if fps_target:
            filters.append(f"tvai_fi=model=apo-8:fps={fps_target}")

        filter_str = ",".join(filters)
        logger.info(f"   Filter: {filter_str}")

        # Build command with archival-quality codec settings
        cmd = [
            str(self.TOPAZ_FFMPEG),
            "-hide_banner",
            "-i",
            str(input_path),
            "-vf",
            filter_str,
            # Video codec - H.265/HEVC with Apple Silicon hardware acceleration
            "-c:v",
            "hevc_videotoolbox",
            "-q:v",
            "65",  # Quality mode (0-100, higher = better)
            "-b:v",
            "80M",  # Target bitrate (up from 50M for archival quality)
            "-maxrate",
            "120M",  # Peak bitrate cap
            "-bufsize",
            "160M",  # VBV buffer
            "-tag:v",
            "hvc1",  # Apple QuickTime/iOS compatibility
            "-pix_fmt",
            "yuv420p",  # Universally compatible pixel format
            # Audio
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            # Metadata
            "-movflags",
            "+faststart",  # Enable progressive playback
            "-y",
            str(output_path),
        ]

        # Environment
        env = {
            **os.environ,
            "TVAI_MODEL_DATA_DIR": str(self.TOPAZ_MODELS),
            "TVAI_MODEL_DIR": str(self.TOPAZ_MODELS),
        }

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Monitor progress and collect Topaz-specific errors
        topaz_errors = []
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            line_text = line.decode().strip()
            line_lower = line_text.lower()

            if "frame=" in line_text:
                logger.debug(f"   {line_text[:80]}")
                if progress_callback:
                    await progress_callback(50, "enhancing")
            elif "error" in line_lower:
                logger.warning(f"   ⚠️ {line_text}")

            # Check for Topaz-specific failures (these indicate silent filter failure)
            for pattern in TOPAZ_ERROR_PATTERNS:
                if pattern in line_lower:
                    topaz_errors.append(line_text)
                    logger.error(f"🚨 TOPAZ FAILURE: {line_text}")
                    break

        await process.wait()

        # If we detected Topaz-specific errors, fail immediately
        if topaz_errors:
            return EnhanceResult(
                success=False, error=f"Topaz processing failed: {'; '.join(topaz_errors[:3])}"
            )

        if process.returncode != 0:
            stderr = await process.stderr.read()
            return EnhanceResult(success=False, error=f"Topaz failed: {stderr.decode()[:300]}")

        if output_path.exists():
            duration = self._get_video_duration(output_path)
            output_resolution = self._get_video_resolution(output_path)
            size_mb = output_path.stat().st_size / 1024 / 1024

            # CRITICAL: Verify enhancement actually happened (catches silent Topaz filter failures)
            tolerance = 0.99  # Allow 1% rounding tolerance
            if (
                output_resolution[0] < target_width * tolerance
                or output_resolution[1] < target_height * tolerance
            ):
                logger.error(
                    f"🚨 TOPAZ FILTER FAILED SILENTLY: expected {target_width}x{target_height}, "
                    f"got {output_resolution[0]}x{output_resolution[1]}"
                )
                return EnhanceResult(
                    success=False,
                    error=f"Topaz filter failed silently: expected {target_width}x{target_height}, "
                    f"got {output_resolution[0]}x{output_resolution[1]}. "
                    f"Check that Topaz Video.app is installed and model '{model}' is loaded.",
                )

            logger.info(
                f"✅ {output_path.name} ({size_mb:.1f} MB, {output_resolution[0]}x{output_resolution[1]})"
            )
            return EnhanceResult(
                success=True,
                video_path=output_path,
                duration_s=duration,
                resolution=output_resolution,
            )

        return EnhanceResult(success=False, error="Output not created")

    async def _enhance_cloud(
        self,
        input_path: Path,
        output_path: Path,
        model: str,
        scale: int,
        denoise: int,
        sharpen: int,
        dehalo: int,
        deinterlace: bool,
        progress_callback: Callable | None,
    ) -> EnhanceResult:
        """Enhance using Topaz Cloud API."""
        if not self._client:
            return EnhanceResult(success=False, error="Cloud client not initialized")

        logger.info(f"☁️ Topaz Cloud: {model} {scale}x")

        try:
            # Create job
            enhancements: dict[str, Any] = {
                "upscale": {
                    "model": model,
                    "scale": scale,
                }
            }
            if denoise > 0:
                enhancements["upscale"]["noise"] = denoise
            if sharpen > 0:
                enhancements["upscale"]["sharpen"] = sharpen
            if dehalo > 0:
                enhancements["upscale"]["dehalo"] = dehalo
            if deinterlace:
                enhancements["deinterlace"] = {"model": "dtv-4"}

            payload = {
                "filename": input_path.name,
                "filesize": input_path.stat().st_size,
                "enhancements": enhancements,
                "output": {"format": "mp4", "codec": "h265"},
            }

            resp = await self._client.post("/video/", json=payload)
            resp.raise_for_status()
            data = resp.json()
            request_id = data["requestId"]
            estimated = data.get("estimatedCredits", 0)
            logger.info(f"   Job: {request_id} (~{estimated:.1f} credits)")

            # Accept
            resp = await self._client.patch(f"/video/{request_id}/accept")
            resp.raise_for_status()
            upload_data = resp.json()
            upload_id = upload_data["uploadId"]
            part_urls = upload_data["partUrls"]

            # Upload
            if progress_callback:
                await progress_callback(10, "uploading")

            parts = []
            chunk_size = 5 * 1024 * 1024
            with open(input_path, "rb") as f:
                for i, url in enumerate(part_urls, 1):
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    async with httpx.AsyncClient() as upload_client:
                        resp = await upload_client.put(
                            url,
                            content=chunk,
                            headers={"Content-Type": "application/octet-stream"},
                        )
                        resp.raise_for_status()
                        etag = resp.headers.get("ETag", "").strip('"')
                        parts.append({"ETag": etag, "PartNumber": i})

            # Complete upload
            resp = await self._client.patch(
                f"/video/{request_id}/complete-upload/",
                json={"uploadId": upload_id, "parts": parts},
            )
            resp.raise_for_status()

            # Poll
            if progress_callback:
                await progress_callback(30, "processing")

            video_url = None
            credits_used = 0.0
            for _ in range(360):  # 30 min timeout
                resp = await self._client.get(f"/video/{request_id}/status")
                if resp.status_code == 200:
                    status_data = resp.json()
                    status = status_data.get("status")
                    progress = status_data.get("progress", 0)

                    if progress_callback:
                        await progress_callback(30 + int(progress * 0.6), "processing")

                    if status == "completed":
                        video_url = status_data.get("downloadUrl")
                        credits_used = status_data.get("creditsUsed", 0)
                        break
                    elif status == "failed":
                        return EnhanceResult(
                            success=False, error=f"Cloud failed: {status_data.get('error')}"
                        )

                await asyncio.sleep(5)

            if not video_url:
                return EnhanceResult(success=False, error="Cloud timeout")

            # Download
            if progress_callback:
                await progress_callback(90, "downloading")

            async with httpx.AsyncClient() as dl_client:
                resp = await dl_client.get(video_url)
                output_path.write_bytes(resp.content)

            duration = self._get_video_duration(output_path)
            resolution = self._get_video_resolution(output_path)
            logger.info(f"✅ Cloud complete: {credits_used:.1f} credits")

            return EnhanceResult(
                success=True,
                video_path=output_path,
                duration_s=duration,
                resolution=resolution,
                cost_cents=credits_used * 7,  # ~$0.07/credit
            )

        except Exception as e:
            logger.error(f"Cloud error: {e}")
            return EnhanceResult(success=False, error=str(e))

    @staticmethod
    def _get_video_duration(path: Path) -> float:
        """Get video duration."""
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

    @staticmethod
    def _get_video_resolution(path: Path) -> tuple[int, int]:
        """Get video resolution."""
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        try:
            w, h = result.stdout.strip().split(",")
            return (int(w), int(h))
        except Exception:
            return (0, 0)

    async def close(self) -> None:
        """Close resources."""
        if self._client:
            await self._client.aclose()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_enhancer: TopazEnhancer | None = None


async def _get_enhancer() -> TopazEnhancer:
    """Get or create singleton."""
    global _enhancer
    if _enhancer is None:
        _enhancer = TopazEnhancer()
        await _enhancer.initialize()
    return _enhancer


async def enhance_video(
    input_path: Path | str,
    preset: EnhancePreset | str = EnhancePreset.CINEMATIC,
    output_path: Path | str | None = None,
    **kwargs,
) -> EnhanceResult:
    """Enhance video with Topaz.

    Args:
        input_path: Input video
        preset: Enhancement preset (cinematic, balanced, fast, vhs, etc.)
        output_path: Output path (auto-generated if None)
        **kwargs: Additional params (model, scale, denoise, sharpen, etc.)

    Returns:
        EnhanceResult with enhanced video path
    """
    enhancer = await _get_enhancer()
    return await enhancer.enhance(
        input_path=Path(input_path),
        output_path=Path(output_path) if output_path else None,
        preset=preset,
        **kwargs,
    )


async def enhance_vhs(
    input_path: Path | str,
    preset: str = "maximum",
    output_path: Path | str | None = None,
) -> EnhanceResult:
    """Restore VHS footage.

    Args:
        input_path: VHS video
        preset: VHS preset (standard, maximum, fast)
        output_path: Output path

    Returns:
        EnhanceResult
    """
    config = VHS_PRESETS.get(preset, VHS_PRESETS["maximum"])
    enhancer = await _get_enhancer()
    return await enhancer.enhance(
        input_path=Path(input_path),
        output_path=Path(output_path) if output_path else None,
        **config,
    )


__all__ = [
    "PRESET_CONFIGS",
    "TOPAZ_MODELS",
    "VHS_PRESETS",
    "EnhancePreset",
    "EnhanceResult",
    "HardwareInfo",
    "TopazConfig",
    "TopazEnhancer",
    "TopazModel",
    "enhance_vhs",
    "enhance_video",
    "get_hardware",
]
