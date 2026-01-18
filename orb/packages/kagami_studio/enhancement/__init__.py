"""Video Enhancement — Multi-Engine Pipeline.

SINGLE SOURCE OF TRUTH for all video enhancement.

THREE ENHANCEMENT ENGINES:
1. Real-ESRGAN (RECOMMENDED) — Fast, local, Metal-accelerated
2. Topaz Cloud API — Best quality, requires credits
3. Topaz Local CLI — Requires Topaz installation

🏆 RECOMMENDED FOR ARCHIVAL: Real-ESRGAN animevideo-v3
   - 4x upscale (640x480 → 2560x1920)
   - ~6-10 fps on M3 Ultra
   - No API costs, runs locally
   - Metal-accelerated via ncnn-vulkan

Usage:
    # REAL-ESRGAN (recommended for VHS archives)
    from kagami_studio.enhancement import RealESRGANEnhancer, enhance_video_realesrgan

    # Quick single video
    result = await enhance_video_realesrgan(
        "/path/to/video.mp4",
        "/output/dir",
    )

    # Full archive
    enhancer = RealESRGANEnhancer(output_dir="/output")
    result = await enhancer.enhance_directory("/Volumes/WesData")

    # TOPAZ CLOUD (highest quality, costs credits)
    from kagami_studio.enhancement import TopazCloud, enhance_archive_cloud

    cloud = TopazCloud()
    job = await cloud.enhance("/path/to/video.mp4", output_dir="/output")

    # TOPAZ LOCAL (if you have Topaz installed)
    from kagami_studio.enhancement import BatchEnhancer

    enhancer = BatchEnhancer(output_dir="/output", parallel=2)
    result = await enhancer.process_directory("/source")
"""

from kagami_studio.enhancement.batch import (
    # Local batch processing
    BatchEnhancer,
    BatchResult,
    JobResult,
    enhance_archive,
)
from kagami_studio.enhancement.batch import (
    JobStatus as LocalJobStatus,
)
from kagami_studio.enhancement.cloud import (
    CloudJob,
    CreditReport,
    JobStatus,
    # Cloud API (RECOMMENDED)
    TopazCloud,
    VideoInfo,
    enhance_archive_cloud,
)
from kagami_studio.enhancement.config import (
    DEFAULT_MODEL,
    PRESETS,
    # Config helpers
    EnhanceConfig,
    get_config,
    get_default_config,
)
from kagami_studio.enhancement.realesrgan import (
    BatchResult as RealESRGANBatchResult,
)
from kagami_studio.enhancement.realesrgan import (
    EnhanceResult as RealESRGANResult,
)
from kagami_studio.enhancement.realesrgan import (
    HardwareProfile as RealESRGANHardware,
)
from kagami_studio.enhancement.realesrgan import (
    # Real-ESRGAN (LOCAL, FAST)
    RealESRGANEnhancer,
    RealESRGANModel,
    detect_hardware,
    get_video_info,
)
from kagami_studio.enhancement.realesrgan import (
    enhance_archive as enhance_archive_realesrgan,
)
from kagami_studio.enhancement.realesrgan import (
    enhance_video as enhance_video_realesrgan,
)
from kagami_studio.enhancement.topaz import (
    TOPAZ_MODELS,
    VHS_PRESETS,
    EnhancePreset,
    # Results
    EnhanceResult,
    # Hardware
    HardwareInfo,
    # Config
    TopazConfig,
    # Main class
    TopazEnhancer,
    # Models
    TopazModel,
    enhance_vhs,
    # Functions
    enhance_video,
    get_hardware,
)

__all__ = [
    "DEFAULT_MODEL",
    "PRESETS",
    "TOPAZ_MODELS",
    "VHS_PRESETS",
    "BatchEnhancer",
    "BatchResult",
    "CloudJob",
    "CreditReport",
    "EnhanceConfig",
    "EnhancePreset",
    "EnhanceResult",
    "HardwareInfo",
    "JobResult",
    "JobStatus",
    "LocalJobStatus",
    "RealESRGANBatchResult",
    "RealESRGANEnhancer",
    "RealESRGANHardware",
    "RealESRGANModel",
    "RealESRGANResult",
    "TopazCloud",
    "TopazConfig",
    "TopazEnhancer",
    "TopazModel",
    "VideoInfo",
    "detect_hardware",
    "enhance_archive",
    "enhance_archive_cloud",
    "enhance_archive_realesrgan",
    "enhance_vhs",
    "enhance_video",
    "enhance_video_realesrgan",
    "get_config",
    "get_default_config",
    "get_hardware",
    "get_video_info",
]
