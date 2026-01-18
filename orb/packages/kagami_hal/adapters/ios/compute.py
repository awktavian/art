"""iOS Compute Adapter for Metal and Neural Engine detection.

Provides capability detection for Apple Silicon compute resources:
- Metal GPU capabilities (family, features, performance tiers)
- Neural Engine availability and generation
- Unified memory architecture detection
- A-series chip identification

Created: January 12, 2026
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any

from kagami.core.boot_mode import is_test_mode

logger = logging.getLogger(__name__)

# Check if we're on iOS/macOS with Metal support
IOS_AVAILABLE = sys.platform == "darwin" and (
    os.uname().machine.startswith("iP")  # iPhone, iPad
    or os.environ.get("KAGAMI_PLATFORM") == "ios"
)

METAL_AVAILABLE = False
METAL_DEVICE: Any = None

if sys.platform == "darwin":
    try:
        import Metal

        METAL_DEVICE = Metal.MTLCreateSystemDefaultDevice()
        METAL_AVAILABLE = METAL_DEVICE is not None
    except ImportError:
        logger.debug("Metal framework not available")


class MetalGPUFamily(Enum):
    """Metal GPU family tiers."""

    # iOS/iPadOS families
    APPLE1 = "apple1"  # A7, A8
    APPLE2 = "apple2"  # A8X, A9
    APPLE3 = "apple3"  # A9X, A10
    APPLE4 = "apple4"  # A11 Bionic
    APPLE5 = "apple5"  # A12 Bionic
    APPLE6 = "apple6"  # A13 Bionic
    APPLE7 = "apple7"  # A14 Bionic, M1
    APPLE8 = "apple8"  # A15 Bionic, M2
    APPLE9 = "apple9"  # A16 Bionic, M3
    APPLE10 = "apple10"  # A17 Pro, M3 Pro/Max

    # Mac families
    MAC1 = "mac1"  # Intel Macs
    MAC2 = "mac2"  # M1/M2/M3

    UNKNOWN = "unknown"


class NeuralEngineGeneration(Enum):
    """Neural Engine generations by chip."""

    NONE = "none"  # Pre-A11, no Neural Engine
    GEN1 = "gen1"  # A11 Bionic - 600 billion ops/s
    GEN2 = "gen2"  # A12 Bionic - 5 trillion ops/s
    GEN3 = "gen3"  # A13 Bionic - optimized ML
    GEN4 = "gen4"  # A14, M1 - 11 trillion ops/s
    GEN5 = "gen5"  # A15, M1 Pro/Max - 15.8 trillion ops/s
    GEN6 = "gen6"  # A16, M2 - 17 trillion ops/s
    GEN7 = "gen7"  # A17 Pro, M3 - 35 trillion ops/s


class ComputeCapabilityTier(Enum):
    """Overall compute capability tier for ML workloads."""

    MINIMAL = "minimal"  # Basic inference only
    LOW = "low"  # Small models, basic ML
    MEDIUM = "medium"  # Medium models, real-time inference
    HIGH = "high"  # Large models, advanced ML
    ULTRA = "ultra"  # Flagship, max performance


@dataclass
class MetalCapabilities:
    """Metal GPU capabilities."""

    # Device info
    device_name: str
    is_low_power: bool
    is_headless: bool
    recommended_max_working_set_size: int  # bytes

    # GPU family
    gpu_family: MetalGPUFamily
    supports_ray_tracing: bool
    supports_mesh_shaders: bool
    supports_function_pointers: bool

    # Memory
    max_buffer_length: int
    max_threads_per_threadgroup: int
    unified_memory: bool

    # Feature sets
    supports_32bit_float_filtering: bool
    supports_32bit_msaa: bool
    supports_bc_texture_compression: bool
    supports_dynamic_libraries: bool

    # Performance hints
    max_threadgroup_memory_length: int
    sparse_tile_size_in_bytes: int


@dataclass
class NeuralEngineCapabilities:
    """Neural Engine capabilities."""

    available: bool
    generation: NeuralEngineGeneration
    estimated_tops: float  # Trillion operations per second
    supports_fp16: bool
    supports_int8: bool
    supports_ane_dynamic_shapes: bool


@dataclass
class ComputeProfile:
    """Complete compute capability profile for the device."""

    # Identification
    chip_name: str
    chip_generation: str
    platform: str  # "ios", "ipados", "macos", "visionos"

    # Compute tier
    capability_tier: ComputeCapabilityTier

    # Metal
    metal: MetalCapabilities | None

    # Neural Engine
    neural_engine: NeuralEngineCapabilities

    # Unified memory
    unified_memory_gb: float
    memory_bandwidth_gbps: float

    # Feature flags for quick checks
    supports_coreml: bool = True
    supports_ane: bool = False
    supports_metal_ml: bool = False
    supports_transformers: bool = False

    # Model size recommendations
    max_recommended_model_params_millions: int = 0

    def __post_init__(self):
        """Compute derived feature flags."""
        self.supports_ane = self.neural_engine.available
        self.supports_metal_ml = self.metal is not None
        self.supports_transformers = self.capability_tier in (
            ComputeCapabilityTier.HIGH,
            ComputeCapabilityTier.ULTRA,
        )


class IOSCompute:
    """iOS/macOS compute capability detector.

    Detects Metal GPU and Neural Engine capabilities for ML workload planning.
    """

    def __init__(self) -> None:
        self._profile: ComputeProfile | None = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize compute detection."""
        if self._initialized:
            return True

        if not METAL_AVAILABLE:
            if is_test_mode():
                logger.info("Metal not available, using minimal compute profile")
                self._profile = self._create_minimal_profile()
                self._initialized = True
                return True
            # On non-Metal systems, still provide a profile
            self._profile = self._create_minimal_profile()
            self._initialized = True
            return True

        try:
            self._profile = self._detect_capabilities()
            self._initialized = True
            logger.info(
                f"Compute profile detected: {self._profile.chip_name} "
                f"({self._profile.capability_tier.value})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to detect compute capabilities: {e}", exc_info=True)
            self._profile = self._create_minimal_profile()
            self._initialized = True
            return False

    @property
    def profile(self) -> ComputeProfile:
        """Get the compute profile (initializes if needed)."""
        if not self._initialized:
            import asyncio

            asyncio.get_event_loop().run_until_complete(self.initialize())
        return self._profile or self._create_minimal_profile()

    def _detect_capabilities(self) -> ComputeProfile:
        """Detect compute capabilities from Metal device."""
        if not METAL_DEVICE:
            return self._create_minimal_profile()

        device_name = METAL_DEVICE.name() or "Unknown"
        chip_name, chip_gen = self._identify_chip(device_name)
        gpu_family = self._detect_gpu_family()
        neural_engine = self._detect_neural_engine(chip_gen)
        metal_caps = self._detect_metal_capabilities(gpu_family)
        tier = self._compute_capability_tier(chip_gen, neural_engine, metal_caps)

        # Memory estimates based on chip
        unified_memory, bandwidth = self._estimate_memory(chip_gen)

        # Model size recommendations
        max_params = self._estimate_max_model_params(tier, unified_memory)

        return ComputeProfile(
            chip_name=chip_name,
            chip_generation=chip_gen,
            platform=self._detect_platform(),
            capability_tier=tier,
            metal=metal_caps,
            neural_engine=neural_engine,
            unified_memory_gb=unified_memory,
            memory_bandwidth_gbps=bandwidth,
            max_recommended_model_params_millions=max_params,
        )

    def _identify_chip(self, device_name: str) -> tuple[str, str]:
        """Identify Apple Silicon chip from Metal device name."""
        name_lower = device_name.lower()

        # A-series identification patterns
        chip_patterns = [
            ("a17", "A17 Pro", "a17"),
            ("a16", "A16 Bionic", "a16"),
            ("a15", "A15 Bionic", "a15"),
            ("a14", "A14 Bionic", "a14"),
            ("a13", "A13 Bionic", "a13"),
            ("a12", "A12 Bionic", "a12"),
            ("a11", "A11 Bionic", "a11"),
            ("a10", "A10 Fusion", "a10"),
            ("m3 max", "M3 Max", "m3_max"),
            ("m3 pro", "M3 Pro", "m3_pro"),
            ("m3", "M3", "m3"),
            ("m2 ultra", "M2 Ultra", "m2_ultra"),
            ("m2 max", "M2 Max", "m2_max"),
            ("m2 pro", "M2 Pro", "m2_pro"),
            ("m2", "M2", "m2"),
            ("m1 ultra", "M1 Ultra", "m1_ultra"),
            ("m1 max", "M1 Max", "m1_max"),
            ("m1 pro", "M1 Pro", "m1_pro"),
            ("m1", "M1", "m1"),
        ]

        for pattern, name, gen in chip_patterns:
            if pattern in name_lower:
                return name, gen

        # Try machine type
        machine = platform.machine()
        if machine.startswith("arm64"):
            return "Apple Silicon", "apple_silicon"

        return device_name, "unknown"

    def _detect_gpu_family(self) -> MetalGPUFamily:
        """Detect Metal GPU family."""
        if not METAL_DEVICE:
            return MetalGPUFamily.UNKNOWN

        # Check GPU families from newest to oldest
        try:
            import Metal

            family_checks = [
                (Metal.MTLGPUFamilyApple9, MetalGPUFamily.APPLE9),
                (Metal.MTLGPUFamilyApple8, MetalGPUFamily.APPLE8),
                (Metal.MTLGPUFamilyApple7, MetalGPUFamily.APPLE7),
                (Metal.MTLGPUFamilyApple6, MetalGPUFamily.APPLE6),
                (Metal.MTLGPUFamilyApple5, MetalGPUFamily.APPLE5),
                (Metal.MTLGPUFamilyApple4, MetalGPUFamily.APPLE4),
                (Metal.MTLGPUFamilyApple3, MetalGPUFamily.APPLE3),
                (Metal.MTLGPUFamilyApple2, MetalGPUFamily.APPLE2),
                (Metal.MTLGPUFamilyApple1, MetalGPUFamily.APPLE1),
                (Metal.MTLGPUFamilyMac2, MetalGPUFamily.MAC2),
                (Metal.MTLGPUFamilyMac1, MetalGPUFamily.MAC1),
            ]

            for family_enum, family in family_checks:
                if METAL_DEVICE.supportsFamily_(family_enum):
                    return family
        except (AttributeError, ImportError):
            pass

        return MetalGPUFamily.UNKNOWN

    def _detect_neural_engine(self, chip_gen: str) -> NeuralEngineCapabilities:
        """Detect Neural Engine capabilities based on chip generation."""
        # Neural Engine capabilities by generation
        ne_specs = {
            # A-series
            "a17": (NeuralEngineGeneration.GEN7, 35.0, True, True, True),
            "a16": (NeuralEngineGeneration.GEN6, 17.0, True, True, True),
            "a15": (NeuralEngineGeneration.GEN5, 15.8, True, True, True),
            "a14": (NeuralEngineGeneration.GEN4, 11.0, True, True, True),
            "a13": (NeuralEngineGeneration.GEN3, 6.0, True, True, False),
            "a12": (NeuralEngineGeneration.GEN2, 5.0, True, True, False),
            "a11": (NeuralEngineGeneration.GEN1, 0.6, True, False, False),
            # M-series
            "m3_max": (NeuralEngineGeneration.GEN7, 35.0, True, True, True),
            "m3_pro": (NeuralEngineGeneration.GEN7, 35.0, True, True, True),
            "m3": (NeuralEngineGeneration.GEN7, 18.0, True, True, True),
            "m2_ultra": (NeuralEngineGeneration.GEN6, 31.6, True, True, True),
            "m2_max": (NeuralEngineGeneration.GEN6, 15.8, True, True, True),
            "m2_pro": (NeuralEngineGeneration.GEN6, 15.8, True, True, True),
            "m2": (NeuralEngineGeneration.GEN6, 15.8, True, True, True),
            "m1_ultra": (NeuralEngineGeneration.GEN5, 22.0, True, True, True),
            "m1_max": (NeuralEngineGeneration.GEN5, 11.0, True, True, True),
            "m1_pro": (NeuralEngineGeneration.GEN5, 11.0, True, True, True),
            "m1": (NeuralEngineGeneration.GEN4, 11.0, True, True, True),
        }

        if chip_gen in ne_specs:
            gen, tops, fp16, int8, dynamic = ne_specs[chip_gen]
            return NeuralEngineCapabilities(
                available=True,
                generation=gen,
                estimated_tops=tops,
                supports_fp16=fp16,
                supports_int8=int8,
                supports_ane_dynamic_shapes=dynamic,
            )

        # Check if it's at least Apple Silicon
        if "apple" in chip_gen.lower() or chip_gen.startswith("m"):
            return NeuralEngineCapabilities(
                available=True,
                generation=NeuralEngineGeneration.GEN4,
                estimated_tops=11.0,
                supports_fp16=True,
                supports_int8=True,
                supports_ane_dynamic_shapes=False,
            )

        return NeuralEngineCapabilities(
            available=False,
            generation=NeuralEngineGeneration.NONE,
            estimated_tops=0.0,
            supports_fp16=False,
            supports_int8=False,
            supports_ane_dynamic_shapes=False,
        )

    def _detect_metal_capabilities(self, gpu_family: MetalGPUFamily) -> MetalCapabilities | None:
        """Detect Metal GPU capabilities."""
        if not METAL_DEVICE:
            return None

        try:
            return MetalCapabilities(
                device_name=METAL_DEVICE.name() or "Unknown",
                is_low_power=METAL_DEVICE.isLowPower(),
                is_headless=METAL_DEVICE.isHeadless(),
                recommended_max_working_set_size=METAL_DEVICE.recommendedMaxWorkingSetSize(),
                gpu_family=gpu_family,
                supports_ray_tracing=self._check_feature("supportsRaytracing"),
                supports_mesh_shaders=gpu_family
                in (
                    MetalGPUFamily.APPLE7,
                    MetalGPUFamily.APPLE8,
                    MetalGPUFamily.APPLE9,
                    MetalGPUFamily.APPLE10,
                    MetalGPUFamily.MAC2,
                ),
                supports_function_pointers=gpu_family
                in (
                    MetalGPUFamily.APPLE6,
                    MetalGPUFamily.APPLE7,
                    MetalGPUFamily.APPLE8,
                    MetalGPUFamily.APPLE9,
                    MetalGPUFamily.APPLE10,
                    MetalGPUFamily.MAC2,
                ),
                max_buffer_length=METAL_DEVICE.maxBufferLength(),
                max_threads_per_threadgroup=METAL_DEVICE.maxThreadsPerThreadgroup().width,
                unified_memory=not METAL_DEVICE.hasUnifiedMemory()
                if hasattr(METAL_DEVICE, "hasUnifiedMemory")
                else True,
                supports_32bit_float_filtering=self._check_feature("supports32BitFloatFiltering"),
                supports_32bit_msaa=self._check_feature("supports32BitMSAA"),
                supports_bc_texture_compression=self._check_feature("supportsBCTextureCompression"),
                supports_dynamic_libraries=self._check_feature("supportsDynamicLibraries"),
                max_threadgroup_memory_length=METAL_DEVICE.maxThreadgroupMemoryLength(),
                sparse_tile_size_in_bytes=METAL_DEVICE.sparseTileSizeInBytes()
                if hasattr(METAL_DEVICE, "sparseTileSizeInBytes")
                else 0,
            )
        except Exception as e:
            logger.warning(f"Error detecting Metal capabilities: {e}")
            return None

    def _check_feature(self, feature_name: str) -> bool:
        """Check if a Metal feature is supported."""
        if not METAL_DEVICE:
            return False
        try:
            method = getattr(METAL_DEVICE, feature_name, None)
            if callable(method):
                return bool(method())
            return False
        except Exception:
            return False

    def _compute_capability_tier(
        self,
        chip_gen: str,
        neural_engine: NeuralEngineCapabilities,
        metal: MetalCapabilities | None,
    ) -> ComputeCapabilityTier:
        """Compute overall capability tier."""
        # Ultra tier: M3 Max, M2 Ultra, M1 Ultra, A17 Pro
        ultra_chips = {"m3_max", "m2_ultra", "m1_ultra", "a17"}
        if chip_gen in ultra_chips:
            return ComputeCapabilityTier.ULTRA

        # High tier: M3 Pro, M2 Max/Pro, M1 Max/Pro, A16, A15
        high_chips = {"m3_pro", "m3", "m2_max", "m2_pro", "m2", "m1_max", "m1_pro", "a16", "a15"}
        if chip_gen in high_chips:
            return ComputeCapabilityTier.HIGH

        # Medium tier: M1, A14, A13
        medium_chips = {"m1", "a14", "a13", "apple_silicon"}
        if chip_gen in medium_chips:
            return ComputeCapabilityTier.MEDIUM

        # Low tier: A12, A11
        low_chips = {"a12", "a11"}
        if chip_gen in low_chips:
            return ComputeCapabilityTier.LOW

        # Check Neural Engine presence
        if neural_engine.available:
            if neural_engine.estimated_tops >= 10:
                return ComputeCapabilityTier.MEDIUM
            return ComputeCapabilityTier.LOW

        return ComputeCapabilityTier.MINIMAL

    def _estimate_memory(self, chip_gen: str) -> tuple[float, float]:
        """Estimate unified memory and bandwidth."""
        # (unified_memory_gb, bandwidth_gbps)
        memory_specs = {
            "m3_max": (128.0, 400.0),
            "m3_pro": (36.0, 200.0),
            "m3": (24.0, 100.0),
            "m2_ultra": (192.0, 800.0),
            "m2_max": (96.0, 400.0),
            "m2_pro": (32.0, 200.0),
            "m2": (24.0, 100.0),
            "m1_ultra": (128.0, 800.0),
            "m1_max": (64.0, 400.0),
            "m1_pro": (32.0, 200.0),
            "m1": (16.0, 68.25),
            "a17": (8.0, 102.0),
            "a16": (6.0, 68.25),
            "a15": (6.0, 42.7),
            "a14": (6.0, 42.7),
            "a13": (4.0, 34.1),
            "a12": (4.0, 34.1),
            "a11": (3.0, 25.6),
        }

        return memory_specs.get(chip_gen, (4.0, 25.6))

    def _estimate_max_model_params(self, tier: ComputeCapabilityTier, memory_gb: float) -> int:
        """Estimate maximum recommended model parameters (in millions)."""
        # Rough rule: 4 bytes per param (FP32), need 2-3x overhead
        # So ~0.3-0.5GB per billion params for inference
        base_params = int(memory_gb * 200)  # ~200M params per GB

        tier_multipliers = {
            ComputeCapabilityTier.ULTRA: 1.5,
            ComputeCapabilityTier.HIGH: 1.0,
            ComputeCapabilityTier.MEDIUM: 0.7,
            ComputeCapabilityTier.LOW: 0.4,
            ComputeCapabilityTier.MINIMAL: 0.2,
        }

        return int(base_params * tier_multipliers.get(tier, 0.5))

    def _detect_platform(self) -> str:
        """Detect the current platform."""
        machine = os.uname().machine

        if machine.startswith("iPhone"):
            return "ios"
        if machine.startswith("iPad"):
            return "ipados"
        if machine.startswith("arm64") and os.environ.get("KAGAMI_PLATFORM") == "visionos":
            return "visionos"
        if sys.platform == "darwin":
            return "macos"

        return "unknown"

    def _create_minimal_profile(self) -> ComputeProfile:
        """Create a minimal compute profile for unsupported devices."""
        return ComputeProfile(
            chip_name="Unknown",
            chip_generation="unknown",
            platform=self._detect_platform() if sys.platform == "darwin" else "unknown",
            capability_tier=ComputeCapabilityTier.MINIMAL,
            metal=None,
            neural_engine=NeuralEngineCapabilities(
                available=False,
                generation=NeuralEngineGeneration.NONE,
                estimated_tops=0.0,
                supports_fp16=False,
                supports_int8=False,
                supports_ane_dynamic_shapes=False,
            ),
            unified_memory_gb=0.0,
            memory_bandwidth_gbps=0.0,
            max_recommended_model_params_millions=10,
        )

    def can_run_model(self, params_millions: int, requires_ane: bool = False) -> bool:
        """Check if the device can run a model of given size.

        Args:
            params_millions: Model parameter count in millions
            requires_ane: Whether the model requires Neural Engine

        Returns:
            True if the device can likely run the model
        """
        profile = self.profile

        if requires_ane and not profile.supports_ane:
            return False

        return params_millions <= profile.max_recommended_model_params_millions

    def get_optimal_compute_unit(self) -> str:
        """Get the optimal compute unit for CoreML.

        Returns:
            "all", "cpuAndNeuralEngine", "cpuAndGPU", or "cpuOnly"
        """
        profile = self.profile

        if profile.supports_ane and profile.supports_metal_ml:
            return "all"
        if profile.supports_ane:
            return "cpuAndNeuralEngine"
        if profile.supports_metal_ml:
            return "cpuAndGPU"
        return "cpuOnly"


# Module-level instance for convenience
_compute_instance: IOSCompute | None = None


def get_compute() -> IOSCompute:
    """Get the singleton compute detector instance."""
    global _compute_instance
    if _compute_instance is None:
        _compute_instance = IOSCompute()
    return _compute_instance


"""
Mirror (Kagami)
h(x) >= 0. Always.

Detect before you deploy.
Know your silicon.
"""
