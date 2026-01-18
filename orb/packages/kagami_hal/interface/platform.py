"""HAL Platform Interfaces.

Defines platform capabilities and power management interfaces.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PowerMode(Enum):
    """Power management modes."""

    OFF = "off"
    LOW_POWER = "low_power"
    BALANCED = "balanced"
    HIGH_PERFORMANCE = "high_performance"


class PlatformType(Enum):
    """Platform types."""

    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    IOS = "ios"
    ANDROID = "android"
    EMBEDDED = "embedded"
    UNKNOWN = "unknown"


class ComputeBackend(Enum):
    """Available compute backends."""

    CPU = "cpu"
    CUDA = "cuda"
    MPS = "mps"  # Apple Metal Performance Shaders
    ROCM = "rocm"  # AMD ROCm
    VULKAN = "vulkan"
    OPENCL = "opencl"


@dataclass
class ComputeCapabilities:
    """Compute capabilities of the platform."""

    cpu_count: int = 1
    cpu_freq_mhz: int = 1000
    cpu_architecture: str = "unknown"

    # Memory
    ram_mb: int = 512
    flash_mb: int = 0
    storage_mb: int = 0

    # Compute backends available
    backends: list[ComputeBackend] = field(default_factory=lambda: [ComputeBackend.CPU])

    # GPU/NPU
    has_gpu: bool = False
    gpu_name: str = ""
    gpu_memory_mb: int = 0
    has_npu: bool = False
    npu_tops: float = 0.0  # Tera-operations per second

    # Floating point
    has_fpu: bool = True
    has_simd: bool = False
    simd_width: int = 0

    # Neural network acceleration
    has_tensor_cores: bool = False
    has_mps: bool = False  # Apple Metal Performance Shaders
    has_cuda: bool = False

    def best_backend(self) -> ComputeBackend:
        """Get the best available compute backend.

        Returns CUDA/MPS if available, otherwise CPU.
        """
        priority = [
            ComputeBackend.CUDA,
            ComputeBackend.MPS,
            ComputeBackend.ROCM,
            ComputeBackend.VULKAN,
            ComputeBackend.OPENCL,
            ComputeBackend.CPU,
        ]

        for backend in priority:
            if backend in self.backends:
                return backend

        return ComputeBackend.CPU

    def supports_backend(self, backend: ComputeBackend) -> bool:
        """Check if a specific backend is supported."""
        return backend in self.backends


@dataclass
class PlatformCapabilities:
    """Full platform capabilities description."""

    # Identification
    platform_id: str = "unknown"
    platform_name: str = "Unknown Platform"
    platform_type: PlatformType = PlatformType.UNKNOWN
    vendor: str = "unknown"
    model: str = "unknown"
    serial: str = ""
    system: str = ""
    machine: str = ""

    # Compute
    compute: ComputeCapabilities = field(default_factory=ComputeCapabilities)

    # Operating system
    os_name: str = "unknown"
    os_version: str = ""
    kernel_version: str = ""

    # Power
    has_battery: bool = False
    battery_capacity_mah: int = 0
    supports_power_modes: list[PowerMode] = field(default_factory=list)
    current_power_mode: PowerMode = PowerMode.BALANCED

    # Connectivity
    has_wifi: bool = False
    has_bluetooth: bool = False
    has_cellular: bool = False
    has_ethernet: bool = False
    has_usb: bool = True
    has_gpio: bool = False
    gpio_count: int = 0

    # Sensors (built-in)
    builtin_sensors: list[str] = field(default_factory=list)

    # Actuators (built-in)
    builtin_actuators: list[str] = field(default_factory=list)

    # Display
    has_display: bool = False
    display_width: int = 0
    display_height: int = 0
    display_type: str = ""

    # Audio
    has_speaker: bool = False
    has_microphone: bool = False
    audio_sample_rate: int = 44100

    # Safety
    supports_emergency_stop: bool = True
    supports_watchdog: bool = False
    watchdog_timeout_ms: int = 5000

    # Extra metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def detect(cls) -> dict[str, Any]:
        """Auto-detect platform capabilities.

        Returns a dictionary with detected platform information.
        """
        import os

        system = platform.system().lower()
        machine = platform.machine()

        # Determine platform type
        if system == "darwin":
            platform_type = PlatformType.MACOS
        elif system == "linux":
            # Check if it's Android
            if os.path.exists("/system/build.prop"):
                platform_type = PlatformType.ANDROID
            else:
                platform_type = PlatformType.LINUX
        elif system == "windows":
            platform_type = PlatformType.WINDOWS
        else:
            platform_type = PlatformType.UNKNOWN

        return {
            "platform_type": platform_type,
            "system": system,
            "machine": machine,
            "python_version": sys.version,
            "os_name": platform.system(),
            "os_version": platform.release(),
        }

    @classmethod
    def detect_compute(cls) -> ComputeCapabilities:
        """Auto-detect compute capabilities."""
        import os

        backends = [ComputeBackend.CPU]

        # Check for CUDA
        try:
            import torch

            if torch.cuda.is_available():
                backends.append(ComputeBackend.CUDA)
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                backends.append(ComputeBackend.MPS)
        except ImportError:
            pass

        # Get CPU info
        cpu_count = os.cpu_count() or 1

        return ComputeCapabilities(
            cpu_count=cpu_count,
            backends=backends,
            has_cuda=ComputeBackend.CUDA in backends,
            has_mps=ComputeBackend.MPS in backends,
        )

    def can_run_model(self, required_memory_mb: int, required_flops: float) -> bool:
        """Check if platform can run a model with given requirements."""
        if self.compute.ram_mb < required_memory_mb:
            return False
        # Rough estimate: 1 GFLOP/s per GHz for modern CPUs
        available_gflops = self.compute.cpu_count * self.compute.cpu_freq_mhz / 1000
        if self.compute.has_gpu:
            available_gflops *= 10  # GPU boost estimate
        return available_gflops >= required_flops / 1e9
