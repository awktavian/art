"""Enhancement Configuration — Artemis HQ Default.

All enhancement paths default to Artemis HQ v12 for maximum fidelity.

ARTEMIS HQ (ahq-12) characteristics:
- Highest PSNR/SSIM fidelity to original
- Minimal hallucination
- Good noise reduction
- Automatic parameter optimization
- Best for archival restoration
"""

from dataclasses import dataclass
from enum import Enum


class TopazModel(str, Enum):
    """Available Topaz Video AI models.

    DEFAULT: ARTEMIS_HQ for all restoration work.
    """

    # Artemis family — automatic enhancement
    ARTEMIS_HQ = "ahq-12"  # 🏆 DEFAULT — Highest quality, automatic
    ARTEMIS_MQ = "amq-13"  # Medium quality, faster
    ARTEMIS_LQ = "alq-13"  # Low quality, fastest

    # Proteus — manual control
    PROTEUS = "prob-4"  # Full parameter control

    # Specialized
    DIONE_TV = "dtv-4"  # VHS/broadcast interlaced
    DIONE_DV = "ddv-3"  # DV camcorder
    IRIS = "iris-3"  # Face enhancement
    GAIA_HQ = "ghq-5"  # CG/animation
    THEIA = "thf-4"  # Fidelity preservation

    # Frame interpolation
    AION = "aion-1"  # Slow motion / frame gen
    APOLLO = "apo-8"  # Fast frame interpolation
    CHRONOS = "chr-2"  # Fast motion

    # Stabilization
    REFINE = "ref-2"  # Motion stabilization


# 🏆 GLOBAL DEFAULT: ARTEMIS HQ
# DEFAULT: Artemis MQ (amq-13) - has pre-cached CoreML models
# Change to ARTEMIS_HQ if you download ahq-12 models via Topaz GUI
DEFAULT_MODEL = TopazModel.ARTEMIS_MQ


@dataclass
class EnhanceConfig:
    """Enhancement configuration.

    Default settings optimized for VHS archival restoration.
    """

    # Model selection
    model: TopazModel = DEFAULT_MODEL

    # Output scale
    scale: int = 4  # 4x = SD → 4K

    # Enhancement parameters (0-100 scale for API, 0-1 for some models)
    recover_detail: int = 50  # Detail recovery
    denoise: int = 35  # Noise reduction
    sharpen: int = 25  # Sharpening
    dehalo: int = 20  # Halo removal
    antialias: int = 25  # Anti-aliasing

    # VHS-specific
    deinterlace: bool = True  # Always for VHS

    # Frame interpolation (optional)
    fps_target: int | None = None  # e.g., 60 for smooth playback

    # Output format
    codec: str = "hevc"  # H.265 for quality
    bitrate: str = "50M"  # High bitrate for 4K

    # Processing
    preview_only: bool = False

    def to_cloud_api_params(self) -> dict:
        """Convert to Topaz Cloud API format."""
        return {
            "model": self.model.value,
            "scale": self.scale,
            "recover": self.recover_detail / 100,
            "noise": self.denoise / 100,
            "sharpen": self.sharpen / 100,
            "dehalo": self.dehalo / 100,
            "antialias": self.antialias / 100,
        }

    def to_cli_params(self) -> dict:
        """Convert to Topaz CLI ffmpeg filter format."""
        return {
            "model": self.model.value,
            "scale": self.scale,
            "noise": self.denoise,
            "details": self.recover_detail,
            "halo": self.dehalo,
            "blur": self.sharpen,
        }


# Preset configurations
class EnhancePreset(str, Enum):
    """Pre-configured enhancement presets."""

    # 🏆 RECOMMENDED FOR ARCHIVES
    ARCHIVAL = "archival"  # Artemis HQ, balanced settings
    ARCHIVAL_MAXIMUM = "archival_max"  # Artemis HQ, max quality

    # Specialized
    VHS_RESTORATION = "vhs"  # Dione TV for interlaced VHS
    FACE_FOCUS = "face"  # Iris model for faces
    FAST_PREVIEW = "preview"  # Quick preview, lower quality


PRESETS: dict[EnhancePreset, EnhanceConfig] = {
    # 🏆 DEFAULT ARCHIVAL PRESET
    EnhancePreset.ARCHIVAL: EnhanceConfig(
        model=TopazModel.ARTEMIS_HQ,
        scale=4,
        recover_detail=50,
        denoise=35,
        sharpen=25,
        dehalo=20,
        antialias=25,
        deinterlace=True,
    ),
    # Maximum quality archival
    EnhancePreset.ARCHIVAL_MAXIMUM: EnhanceConfig(
        model=TopazModel.ARTEMIS_HQ,
        scale=4,
        recover_detail=60,
        denoise=40,
        sharpen=30,
        dehalo=25,
        antialias=30,
        deinterlace=True,
        bitrate="80M",
    ),
    # VHS-specific with Dione
    EnhancePreset.VHS_RESTORATION: EnhanceConfig(
        model=TopazModel.DIONE_TV,
        scale=4,
        recover_detail=40,
        denoise=30,
        sharpen=20,
        dehalo=15,
        antialias=20,
        deinterlace=True,
    ),
    # Face enhancement
    EnhancePreset.FACE_FOCUS: EnhanceConfig(
        model=TopazModel.IRIS,
        scale=4,
        recover_detail=40,
        denoise=30,
        sharpen=20,
        dehalo=20,
        antialias=20,
        deinterlace=True,
    ),
    # Fast preview
    EnhancePreset.FAST_PREVIEW: EnhanceConfig(
        model=TopazModel.ARTEMIS_LQ,
        scale=2,
        recover_detail=30,
        denoise=20,
        sharpen=15,
        dehalo=10,
        antialias=10,
        deinterlace=True,
        bitrate="20M",
        preview_only=True,
    ),
}


def get_config(preset: EnhancePreset = EnhancePreset.ARCHIVAL) -> EnhanceConfig:
    """Get enhancement configuration for a preset.

    Args:
        preset: Enhancement preset (default: ARCHIVAL with Artemis HQ)

    Returns:
        EnhanceConfig with appropriate settings
    """
    return PRESETS.get(preset, PRESETS[EnhancePreset.ARCHIVAL])


def get_default_config() -> EnhanceConfig:
    """Get the default enhancement configuration (Artemis HQ archival)."""
    return get_config(EnhancePreset.ARCHIVAL)
