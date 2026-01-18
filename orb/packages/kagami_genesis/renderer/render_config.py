"""Render Configuration Module - Render presets and configuration management.

Responsibilities:
- Render preset definitions (DAILIES, PROOF, FINAL)
- Foveation configuration
- Frame statistics tracking
- Object motion tracking
- Realtime rendering configuration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .hardware_detection import HardwareProfile, get_hardware

logger = logging.getLogger(__name__)


class RenderPreset(Enum):
    """Hardware-aware render presets."""

    DAILIES = "dailies"  # Fast, low quality
    PROOF = "proof"  # Balanced quality/speed
    FINAL = "final"  # High quality, slower


@dataclass
class PresetConfig:
    """Configuration for a render preset."""

    # Ray tracing
    max_depth: int
    samples_per_pixel: int

    # Foveation
    center_spp_multiplier: float  # Multiplier for center region SPP
    mid_spp_multiplier: float  # Multiplier for mid region SPP
    peripheral_spp_multiplier: float  # Multiplier for peripheral SPP

    # Performance
    motion_blur: bool
    caustics: bool
    global_illumination: bool

    # Quality
    denoise: bool
    temporal_accumulation: bool


def get_preset_config(
    preset: RenderPreset,
    hardware: HardwareProfile | None = None,
) -> PresetConfig:
    """Get configuration for render preset, adapted to hardware."""
    if hardware is None:
        hardware = get_hardware()

    # Base configurations
    base_configs = {
        RenderPreset.DAILIES: PresetConfig(
            max_depth=3,
            samples_per_pixel=16,
            center_spp_multiplier=2.0,
            mid_spp_multiplier=1.0,
            peripheral_spp_multiplier=0.25,
            motion_blur=False,
            caustics=False,
            global_illumination=False,
            denoise=True,
            temporal_accumulation=True,
        ),
        RenderPreset.PROOF: PresetConfig(
            max_depth=6,
            samples_per_pixel=64,
            center_spp_multiplier=2.0,
            mid_spp_multiplier=1.5,
            peripheral_spp_multiplier=0.5,
            motion_blur=True,
            caustics=True,
            global_illumination=True,
            denoise=True,
            temporal_accumulation=True,
        ),
        RenderPreset.FINAL: PresetConfig(
            max_depth=12,
            samples_per_pixel=256,
            center_spp_multiplier=3.0,
            mid_spp_multiplier=2.0,
            peripheral_spp_multiplier=1.0,
            motion_blur=True,
            caustics=True,
            global_illumination=True,
            denoise=True,
            temporal_accumulation=True,
        ),
    }

    config = base_configs[preset]

    # Adapt to hardware performance
    if hardware.performance_tier == "low":
        # Reduce quality for low-end hardware
        config.samples_per_pixel = max(8, config.samples_per_pixel // 4)
        config.max_depth = max(2, config.max_depth // 2)
        config.motion_blur = False
        config.caustics = False
        config.global_illumination = False

    elif hardware.performance_tier == "medium":
        # Moderate reduction for medium hardware
        config.samples_per_pixel = max(16, config.samples_per_pixel // 2)
        config.max_depth = max(3, config.max_depth // 1.5)

    elif hardware.performance_tier == "ultra":
        # Increase quality for high-end hardware
        config.samples_per_pixel = min(512, int(config.samples_per_pixel * 1.5))
        config.max_depth = min(16, int(config.max_depth * 1.2))

    # Apple Silicon optimizations
    if hardware.is_apple_silicon:
        # Apple Silicon is efficient at certain operations
        config.denoise = True  # Hardware-accelerated
        config.temporal_accumulation = True
        # Reduce SPP slightly as unified memory architecture is efficient
        config.samples_per_pixel = max(8, int(config.samples_per_pixel * 0.8))

    return config


@dataclass
class FrameStats:
    """Frame rendering statistics."""

    frame_number: int
    render_time_ms: float
    total_rays: int
    samples_per_pixel: int
    max_depth: int
    memory_usage_mb: float


@dataclass
class FoveationConfig:
    """Foveated rendering configuration."""

    enabled: bool = True
    center_radius: float = 0.2  # Fraction of screen width
    mid_radius: float = 0.5  # Fraction of screen width
    transition_width: float = 0.1  # Smooth transition width

    # SPP multipliers for each region
    center_spp_multiplier: float = 2.0
    mid_spp_multiplier: float = 1.0
    peripheral_spp_multiplier: float = 0.25

    # Gaze tracking
    use_eye_tracking: bool = False
    fallback_to_cursor: bool = True

    # Performance
    max_gaze_lag_ms: float = 16.0  # Maximum acceptable gaze lag


@dataclass
class ObjectMotion:
    """Object motion data for temporal reprojection."""

    object_id: str
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]  # Quaternion
    velocity: tuple[float, float, float]
    angular_velocity: tuple[float, float, float]
    timestamp: float


@dataclass
class RealtimeConfig:
    """Real-time rendering configuration."""

    # Rendering
    target_fps: float = 60.0
    max_frame_time_ms: float = 16.67  # 1000/60
    adaptive_quality: bool = True
    preset: RenderPreset = RenderPreset.PROOF

    # Resolution
    width: int = 1920
    height: int = 1080
    scale_factor: float = 1.0  # For dynamic resolution

    # Foveation
    foveation: FoveationConfig = field(default_factory=FoveationConfig)

    # Motion reprojection
    motion_reprojection: bool = True
    max_reprojection_distance: float = 10.0  # pixels
    reprojection_confidence_threshold: float = 0.8

    # Temporal features
    temporal_accumulation: bool = True
    history_buffer_size: int = 8
    temporal_alpha: float = 0.1  # Blend factor for new frames

    # Performance
    cpu_threads: int = 0  # 0 = auto-detect
    memory_limit_mb: float = 2048.0
    disk_cache_mb: float = 512.0

    # Quality vs Performance
    quality_bias: float = 0.5  # 0.0 = performance, 1.0 = quality

    # Audio
    audio_enabled: bool = True
    audio_sample_rate: int = 44100
    audio_buffer_ms: int = 50

    @classmethod
    def from_preset(
        cls,
        preset: RenderPreset,
        width: int = 1920,
        height: int = 1080,
        target_fps: float = 60.0,
        hardware: HardwareProfile | None = None,
    ) -> RealtimeConfig:
        """Create configuration from preset."""
        if hardware is None:
            hardware = get_hardware()

        config = cls(
            preset=preset,
            width=width,
            height=height,
            target_fps=target_fps,
            max_frame_time_ms=1000.0 / target_fps,
        )

        # Adapt to hardware
        if hardware.performance_tier == "low":
            # Reduce settings for low-end hardware
            config.scale_factor = 0.75
            config.foveation.center_spp_multiplier = 1.5
            config.foveation.peripheral_spp_multiplier = 0.1
            config.motion_reprojection = True  # Important for low-end
            config.temporal_accumulation = True
            config.history_buffer_size = 4
            config.quality_bias = 0.2

        elif hardware.performance_tier == "medium":
            # Balanced settings
            config.scale_factor = 1.0
            config.quality_bias = 0.5

        elif hardware.performance_tier == "high":
            # Higher quality settings
            config.scale_factor = 1.0
            config.foveation.center_spp_multiplier = 2.5
            config.temporal_accumulation = True
            config.history_buffer_size = 8
            config.quality_bias = 0.7

        elif hardware.performance_tier == "ultra":
            # Maximum quality settings
            config.scale_factor = 1.0
            config.foveation.center_spp_multiplier = 3.0
            config.foveation.mid_spp_multiplier = 1.5
            config.foveation.peripheral_spp_multiplier = 0.75
            config.temporal_accumulation = True
            config.history_buffer_size = 12
            config.quality_bias = 0.9
            config.memory_limit_mb = 4096.0

        # Apple Silicon specific optimizations
        if hardware.is_apple_silicon:
            # Unified memory architecture benefits
            config.memory_limit_mb = min(
                config.memory_limit_mb,
                hardware.gpu_memory_gb * 1024 * 0.8,
            )
            config.disk_cache_mb = 256.0  # Faster SSD on Apple Silicon
            config.cpu_threads = max(4, hardware.cpu_cores // 2)  # Leave room for system

        # GPU memory adjustments
        if hardware.gpu_memory_gb < 4.0:
            config.memory_limit_mb = min(config.memory_limit_mb, 1024.0)
            config.history_buffer_size = max(4, config.history_buffer_size // 2)

        return config

    def estimate_render_time(self, duration_seconds: float) -> str:
        """Estimate total render time for given duration."""
        total_frames = int(duration_seconds * self.target_fps)
        time_per_frame = self.max_frame_time_ms / 1000.0

        # Account for quality settings
        quality_multiplier = 1.0 + (self.quality_bias * 2.0)  # 1.0 to 3.0
        preset_multipliers = {
            RenderPreset.DAILIES: 1.0,
            RenderPreset.PROOF: 2.5,
            RenderPreset.FINAL: 6.0,
        }

        estimated_time_per_frame = (
            time_per_frame * quality_multiplier * preset_multipliers.get(self.preset, 2.5)
        )

        total_time_seconds = total_frames * estimated_time_per_frame
        total_time_minutes = total_time_seconds / 60.0

        if total_time_minutes < 1:
            return f"{total_time_seconds:.0f} seconds"
        if total_time_minutes < 60:
            return f"{total_time_minutes:.1f} minutes"
        hours = total_time_minutes / 60.0
        return f"{hours:.1f} hours"

    def __str__(self) -> str:
        """String representation."""
        return (
            f"RealtimeConfig({self.preset.value}, {self.width}x{self.height}@{self.target_fps}fps, "
            f"quality_bias={self.quality_bias:.1f})"
        )


def _build_material_modes() -> dict[str, dict]:
    """Build material rendering modes for different presets."""
    return {
        "DAILIES": {
            "subsurface": False,
            "transmission": False,
            "emission": True,
            "metallic": True,
            "roughness_detail": False,
            "normal_detail": False,
        },
        "PROOF": {
            "subsurface": True,
            "transmission": True,
            "emission": True,
            "metallic": True,
            "roughness_detail": True,
            "normal_detail": True,
        },
        "FINAL": {
            "subsurface": True,
            "transmission": True,
            "emission": True,
            "metallic": True,
            "roughness_detail": True,
            "normal_detail": True,
            "micro_detail": True,
        },
    }


def get_material_mode(preset: RenderPreset) -> dict[str, Any]:
    """Get material rendering mode for preset."""
    modes = _build_material_modes()
    return modes.get(preset.value.upper(), modes["PROOF"])


def optimize_config_for_memory(
    config: RealtimeConfig,
    available_memory_mb: float,
) -> RealtimeConfig:
    """Optimize configuration for available memory."""
    optimized = RealtimeConfig(**config.__dict__)

    if available_memory_mb < optimized.memory_limit_mb:
        # Reduce memory-intensive settings
        scale_factor = available_memory_mb / optimized.memory_limit_mb
        optimized.memory_limit_mb = available_memory_mb * 0.9  # Leave some headroom

        # Reduce history buffer
        optimized.history_buffer_size = max(2, int(optimized.history_buffer_size * scale_factor))

        # Reduce resolution if needed
        if scale_factor < 0.5:
            optimized.scale_factor *= scale_factor * 2  # Don't go below 0.5x

        # Disable temporal accumulation if memory is very tight
        if available_memory_mb < 1024:
            optimized.temporal_accumulation = False
            optimized.history_buffer_size = 1

        logger.info(f"Optimized config for {available_memory_mb:.0f}MB memory")

    return optimized
