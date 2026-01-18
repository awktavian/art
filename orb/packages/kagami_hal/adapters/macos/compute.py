"""macOS Compute Capabilities Detection.

Detects GPU and compute capabilities on macOS:
- Metal GPU detection (Apple Silicon and Intel)
- CPU detection (Apple Silicon vs Intel)
- Memory detection
- Compute API availability (Metal Performance Shaders, MLX)

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

# Platform check
MACOS_AVAILABLE = sys.platform == "darwin"


@dataclass
class ComputeCapabilities:
    """Compute capabilities for macOS."""

    # CPU
    cpu_arch: Literal["arm64", "x86_64", "unknown"]
    cpu_name: str
    cpu_cores_physical: int
    cpu_cores_logical: int

    # Memory
    memory_gb: float

    # GPU
    has_metal: bool
    gpu_name: str | None
    gpu_memory_gb: float | None

    # Compute APIs
    has_mps: bool  # Metal Performance Shaders
    has_mlx: bool  # Apple MLX (ML framework)
    has_cuda: bool  # CUDA (always False on macOS)

    # Platform info
    os_version: str
    is_apple_silicon: bool


class MacOSComputeDetector:
    """Detect compute capabilities on macOS."""

    def __init__(self) -> None:
        """Initialize compute detector."""
        self._capabilities: ComputeCapabilities | None = None

    async def detect(self) -> ComputeCapabilities:
        """Detect all compute capabilities.

        Returns:
            ComputeCapabilities instance
        """
        if not MACOS_AVAILABLE:
            raise RuntimeError("Compute detection only available on macOS")

        # Detect CPU
        cpu_arch = self._detect_cpu_arch()
        cpu_name = self._detect_cpu_name()
        cpu_cores_physical, cpu_cores_logical = self._detect_cpu_cores()

        # Detect memory
        memory_gb = self._detect_memory()

        # Detect GPU
        has_metal, gpu_name, gpu_memory_gb = self._detect_gpu()

        # Detect compute APIs
        has_mps = self._detect_mps()
        has_mlx = self._detect_mlx()

        # Platform info
        os_version = platform.mac_ver()[0]
        is_apple_silicon = cpu_arch == "arm64"

        self._capabilities = ComputeCapabilities(
            cpu_arch=cpu_arch,
            cpu_name=cpu_name,
            cpu_cores_physical=cpu_cores_physical,
            cpu_cores_logical=cpu_cores_logical,
            memory_gb=memory_gb,
            has_metal=has_metal,
            gpu_name=gpu_name,
            gpu_memory_gb=gpu_memory_gb,
            has_mps=has_mps,
            has_mlx=has_mlx,
            has_cuda=False,  # CUDA not available on macOS
            os_version=os_version,
            is_apple_silicon=is_apple_silicon,
        )

        logger.info(
            f"✅ Compute capabilities detected: "
            f"{cpu_arch} {cpu_name}, {memory_gb:.1f}GB RAM, "
            f"Metal={has_metal}, GPU={gpu_name or 'None'}"
        )

        return self._capabilities

    def _detect_cpu_arch(self) -> Literal["arm64", "x86_64", "unknown"]:
        """Detect CPU architecture."""
        arch = platform.machine().lower()
        if arch in ("arm64", "aarch64"):
            return "arm64"
        elif arch in ("x86_64", "amd64"):
            return "x86_64"
        else:
            return "unknown"

    def _detect_cpu_name(self) -> str:
        """Detect CPU name via sysctl."""
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                timeout=1,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        # Fallback to platform
        return platform.processor() or "Unknown CPU"

    def _detect_cpu_cores(self) -> tuple[int, int]:
        """Detect physical and logical CPU cores.

        Returns:
            (physical_cores, logical_cores)
        """
        physical = 1
        logical = 1

        try:
            # Physical cores
            result = subprocess.run(
                ["sysctl", "-n", "hw.physicalcpu"],
                capture_output=True,
                timeout=1,
                text=True,
            )
            if result.returncode == 0:
                physical = int(result.stdout.strip())

            # Logical cores
            result = subprocess.run(
                ["sysctl", "-n", "hw.logicalcpu"],
                capture_output=True,
                timeout=1,
                text=True,
            )
            if result.returncode == 0:
                logical = int(result.stdout.strip())

        except Exception as e:
            logger.debug(f"Failed to detect CPU cores: {e}")

        return (physical, logical)

    def _detect_memory(self) -> float:
        """Detect system memory in GB.

        Returns:
            Memory in gigabytes
        """
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                timeout=1,
                text=True,
            )
            if result.returncode == 0:
                mem_bytes = int(result.stdout.strip())
                mem_gb = mem_bytes / (1024**3)
                return mem_gb
        except Exception as e:
            logger.debug(f"Failed to detect memory: {e}")

        return 0.0

    def _detect_gpu(self) -> tuple[bool, str | None, float | None]:
        """Detect GPU information via system_profiler.

        Returns:
            (has_metal, gpu_name, gpu_memory_gb)
        """
        has_metal = False
        gpu_name = None
        gpu_memory_gb = None

        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                timeout=3,
                text=True,
            )

            if result.returncode == 0:
                output = result.stdout

                # Check for Metal support
                has_metal = "Metal" in output or "apple m" in output.lower()

                # Extract GPU name
                # Look for lines like "Chipset Model: Apple M2" or "NVIDIA GeForce GTX"
                for line in output.split("\n"):
                    line_stripped = line.strip()
                    if "Chipset Model:" in line_stripped:
                        gpu_name = line_stripped.split(":", 1)[1].strip()
                        break

                # Extract VRAM
                # Look for lines like "VRAM (Total): 8 GB" or "Total Memory: 16 GB"
                for line in output.split("\n"):
                    line_stripped = line.strip()
                    if "VRAM" in line_stripped or "Total Memory:" in line_stripped:
                        # Parse memory value
                        parts = line_stripped.split(":")
                        if len(parts) >= 2:
                            mem_str = parts[1].strip()
                            # Extract number
                            import re

                            match = re.search(r"(\d+(?:\.\d+)?)\s*(GB|MB)", mem_str)
                            if match:
                                value = float(match.group(1))
                                unit = match.group(2)
                                if unit == "MB":
                                    value = value / 1024
                                gpu_memory_gb = value
                                break

        except Exception as e:
            logger.debug(f"Failed to detect GPU: {e}")

        return (has_metal, gpu_name, gpu_memory_gb)

    def _detect_mps(self) -> bool:
        """Detect Metal Performance Shaders availability.

        MPS is available on:
        - macOS 12.3+ with Apple Silicon
        - PyTorch with MPS backend support
        """
        try:
            # Check PyTorch MPS support
            import torch

            return hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        except ImportError:
            pass

        # Fallback: Check if Metal is available and macOS version
        try:
            mac_version = platform.mac_ver()[0]
            major, minor = map(int, mac_version.split(".")[:2])

            # MPS requires macOS 12.3+
            if major > 12 or (major == 12 and minor >= 3):
                # Check if Apple Silicon
                if platform.machine().lower() in ("arm64", "aarch64"):
                    return True
        except Exception:
            pass

        return False

    def _detect_mlx(self) -> bool:
        """Detect Apple MLX framework availability.

        MLX is Apple's ML framework for Apple Silicon.
        """
        try:
            import mlx  # noqa: F401

            return True
        except ImportError:
            pass

        return False

    def get_capabilities(self) -> ComputeCapabilities | None:
        """Get cached capabilities.

        Returns:
            ComputeCapabilities if already detected, else None
        """
        return self._capabilities

    def is_apple_silicon(self) -> bool:
        """Check if running on Apple Silicon.

        Returns:
            True if Apple Silicon (M1/M2/M3)
        """
        if self._capabilities:
            return self._capabilities.is_apple_silicon

        return platform.machine().lower() in ("arm64", "aarch64")

    def get_optimal_device(self) -> str:
        """Get optimal compute device string for ML frameworks.

        Returns:
            Device string: "mps", "cpu", or "cuda" (PyTorch/JAX compatible)
        """
        if not self._capabilities:
            return "cpu"

        if self._capabilities.has_mps:
            return "mps"

        return "cpu"


async def detect_compute_capabilities() -> ComputeCapabilities:
    """Convenience function to detect compute capabilities.

    Returns:
        ComputeCapabilities instance
    """
    detector = MacOSComputeDetector()
    return await detector.detect()


__all__ = [
    "ComputeCapabilities",
    "MacOSComputeDetector",
    "detect_compute_capabilities",
]
