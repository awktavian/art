"""Hardware Detection Module — System Capability Profiling.

This module provides comprehensive hardware detection and performance
classification for the Genesis rendering pipeline. It supports multiple
platforms and GPU vendors, automatically selecting optimal render settings.

Supported Platforms:
    - macOS (Apple Silicon M1/M2/M3 and Intel)
    - Linux (NVIDIA, AMD, Intel)
    - Windows (NVIDIA, AMD, Intel)

Detection Capabilities:
    - GPU vendor and model identification
    - GPU memory estimation (dedicated or unified)
    - System RAM detection
    - CPU core counting
    - Unified memory architecture detection (Apple Silicon)

Performance Tiers:
    - ultra: M3 Max/Ultra, RTX 4080/4090, 16GB+ VRAM
    - high: M2/M3 Pro, RTX 3000+, 8GB+ VRAM
    - medium: Base M-series, GTX 1060+, 4GB+ VRAM
    - low: Intel integrated, older GPUs, <4GB VRAM

Usage:
    >>> from kagami_genesis.renderer.hardware_detection import get_hardware
    >>> profile = get_hardware()
    >>> print(f"GPU: {profile.gpu_name}")
    >>> print(f"Tier: {profile.performance_tier}")
    >>> if profile.is_apple_silicon:
    ...     print("Using Metal backend")

The module caches detection results for performance. Call `clear_hardware_cache()`
to force re-detection after hardware changes.

Colony: Crystal (e₇) — Verification and system analysis
Created: 2025
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HardwareProfile:
    """System hardware profile for rendering optimization.

    Captures the essential hardware characteristics needed to select
    appropriate render settings, allocate resources, and choose backends.

    Attributes:
        gpu_type: GPU vendor identifier ("apple_silicon", "nvidia", "amd", "intel", "unknown").
        gpu_name: Human-readable GPU model name (e.g., "Apple M3 Max GPU", "NVIDIA RTX 4090").
        gpu_memory_gb: Available GPU memory in gigabytes.
            For Apple Silicon, this is estimated from unified memory.
            For dedicated GPUs, this is the VRAM capacity.
        system_memory_gb: Total system RAM in gigabytes.
        cpu_cores: Number of logical CPU cores available.
        is_apple_silicon: True if running on Apple M-series chip.
            Enables Metal backend and unified memory optimizations.
        performance_tier: Classification for preset selection.
            One of: "low", "medium", "high", "ultra".

    Example:
        >>> profile = HardwareProfile(
        ...     gpu_type="apple_silicon",
        ...     gpu_name="Apple M3 Max GPU",
        ...     gpu_memory_gb=48.0,
        ...     system_memory_gb=64.0,
        ...     cpu_cores=14,
        ...     is_apple_silicon=True,
        ...     performance_tier="ultra",
        ... )
    """

    gpu_type: str
    """GPU vendor: "apple_silicon", "nvidia", "amd", "intel", or "unknown"."""
    gpu_name: str
    """Human-readable GPU model name."""
    gpu_memory_gb: float
    """GPU memory in gigabytes (VRAM or unified memory allocation)."""
    system_memory_gb: float
    """System RAM in gigabytes."""
    cpu_cores: int
    """Number of logical CPU cores."""
    is_apple_silicon: bool
    """True if running on Apple M-series chip."""
    performance_tier: str
    """Performance class: "low", "medium", "high", or "ultra"."""


def detect_hardware() -> HardwareProfile:
    """Detect system hardware capabilities.

    Performs comprehensive hardware detection including GPU identification,
    memory measurement, and performance classification. Platform-specific
    methods are used for accurate detection on macOS, Linux, and Windows.

    The detection process:
        1. Identify operating system and architecture
        2. Detect Apple Silicon unified memory architecture
        3. Count CPU cores via os.cpu_count()
        4. Query system memory via platform-specific methods
        5. Detect GPU via system profiler / nvidia-smi / wmic
        6. Classify performance tier based on detected hardware

    Returns:
        HardwareProfile with all detected hardware characteristics.
        Uses conservative defaults if detection fails.

    Note:
        This function performs subprocess calls which may be slow (~100ms).
        Use `get_hardware()` for cached access in performance-critical code.
    """
    gpu_type = "unknown"
    gpu_name = "Unknown GPU"
    gpu_memory_gb = 2.0  # Conservative default
    system_memory_gb = 8.0  # Conservative default
    cpu_cores = 4  # Conservative default
    is_apple_silicon = False
    performance_tier = "medium"

    # Detect system
    system = platform.system()
    machine = platform.machine()

    # Detect Apple Silicon
    if system == "Darwin" and machine in ("arm64", "arm"):
        is_apple_silicon = True
        gpu_type = "apple_silicon"

    # Get CPU info
    try:
        cpu_cores = os.cpu_count() or 4
    except Exception:
        cpu_cores = 4

    # Detect system memory
    try:
        if system == "Darwin":
            # macOS - use sysctl
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                system_memory_bytes = int(result.stdout.strip())
                system_memory_gb = system_memory_bytes / (1024**3)
        elif system == "Linux":
            # Linux - read /proc/meminfo
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        memory_kb = int(line.split()[1])
                        system_memory_gb = memory_kb / (1024**2)
                        break
    except Exception as e:
        logger.warning(f"Could not detect system memory: {e}")

    # Detect GPU
    try:
        if is_apple_silicon:
            # Apple Silicon GPU detection
            gpu_name = _detect_apple_silicon_gpu(machine)
            gpu_memory_gb = _estimate_apple_silicon_gpu_memory(gpu_name, system_memory_gb)
        elif system == "Darwin":
            # Intel Mac GPU detection
            gpu_info = _detect_macos_gpu()
            if gpu_info:
                gpu_type, gpu_name, gpu_memory_gb = gpu_info
        elif system == "Linux":
            # Linux GPU detection
            gpu_info = _detect_linux_gpu()
            if gpu_info:
                gpu_type, gpu_name, gpu_memory_gb = gpu_info
        elif system == "Windows":
            # Windows GPU detection
            gpu_info = _detect_windows_gpu()
            if gpu_info:
                gpu_type, gpu_name, gpu_memory_gb = gpu_info

    except Exception as e:
        logger.warning(f"Could not detect GPU: {e}")

    # Determine performance tier
    performance_tier = _classify_performance_tier(
        gpu_type,
        gpu_name,
        gpu_memory_gb,
        system_memory_gb,
        cpu_cores,
        is_apple_silicon,
    )

    profile = HardwareProfile(
        gpu_type=gpu_type,
        gpu_name=gpu_name,
        gpu_memory_gb=gpu_memory_gb,
        system_memory_gb=system_memory_gb,
        cpu_cores=cpu_cores,
        is_apple_silicon=is_apple_silicon,
        performance_tier=performance_tier,
    )

    logger.info(f"Detected hardware: {profile}")
    return profile


def _detect_apple_silicon_gpu(machine: str) -> str:
    """Detect Apple Silicon GPU variant from hardware model.

    Uses sysctl to query the hw.model identifier and maps it to
    a human-readable GPU name including the tier (M1/M2/M3 + Pro/Max/Ultra).

    Args:
        machine: Platform machine type (used as fallback context).

    Returns:
        Human-readable GPU name like "Apple M3 Max GPU".
        Falls back to "Apple Silicon GPU" if detection fails.
    """
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.model"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            model = result.stdout.strip()

            # Map hardware models to GPU names
            if "M3" in model:
                if "Max" in model:
                    return "Apple M3 Max GPU"
                if "Pro" in model:
                    return "Apple M3 Pro GPU"
                return "Apple M3 GPU"
            if "M2" in model:
                if "Ultra" in model:
                    return "Apple M2 Ultra GPU"
                if "Max" in model:
                    return "Apple M2 Max GPU"
                if "Pro" in model:
                    return "Apple M2 Pro GPU"
                return "Apple M2 GPU"
            if "M1" in model:
                if "Ultra" in model:
                    return "Apple M1 Ultra GPU"
                if "Max" in model:
                    return "Apple M1 Max GPU"
                if "Pro" in model:
                    return "Apple M1 Pro GPU"
                return "Apple M1 GPU"

    except Exception:
        pass

    return "Apple Silicon GPU"


def _estimate_apple_silicon_gpu_memory(gpu_name: str, system_memory_gb: float) -> float:
    """Estimate GPU memory allocation for Apple Silicon unified memory.

    Apple Silicon uses a unified memory architecture where CPU and GPU
    share the same physical RAM. This function estimates the maximum
    memory the GPU can effectively use based on the chip tier.

    Typical allocations:
        - Ultra variants: Up to 70% of system memory, max 32GB
        - Max variants: Up to 60% of system memory, max 24GB
        - Pro variants: Up to 50% of system memory, max 16GB
        - Base variants: Up to 40% of system memory, max 12GB

    Args:
        gpu_name: Detected GPU name containing tier info (Pro/Max/Ultra).
        system_memory_gb: Total unified memory in gigabytes.

    Returns:
        Estimated GPU memory budget in gigabytes.
    """
    # Apple Silicon uses unified memory architecture
    # GPU shares system memory, typical allocations:
    if "Ultra" in gpu_name:
        return min(32.0, system_memory_gb * 0.7)  # Up to 32GB
    if "Max" in gpu_name:
        return min(24.0, system_memory_gb * 0.6)  # Up to 24GB
    if "Pro" in gpu_name:
        return min(16.0, system_memory_gb * 0.5)  # Up to 16GB
    return min(12.0, system_memory_gb * 0.4)  # Up to 12GB


def _detect_macos_gpu() -> tuple[str, str, float] | None:
    """Detect GPU on Intel macOS using system_profiler.

    Parses the SPDisplaysDataType output to identify GPU vendor,
    model name, and VRAM capacity for Intel-based Macs.

    Returns:
        Tuple of (gpu_type, gpu_name, gpu_memory_gb) if detected,
        None if detection fails or no discrete GPU found.
    """
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            output = result.stdout

            # Parse GPU info
            if "AMD" in output:
                gpu_type = "amd"
            elif "NVIDIA" in output:
                gpu_type = "nvidia"
            elif "Intel" in output:
                gpu_type = "intel"
            else:
                return None

            # Extract GPU name and memory
            lines = output.split("\n")
            gpu_name = "Unknown"
            gpu_memory_gb = 2.0

            for i, line in enumerate(lines):
                if "Chipset Model:" in line:
                    gpu_name = line.split(":")[-1].strip()
                elif "VRAM" in line or "Total Number of Cores:" in line:
                    try:
                        # Extract memory size
                        for j in range(i, min(i + 5, len(lines))):
                            if "GB" in lines[j] or "MB" in lines[j]:
                                memory_str = lines[j]
                                if "GB" in memory_str:
                                    gpu_memory_gb = float(memory_str.split("GB")[0].split()[-1])
                                elif "MB" in memory_str:
                                    gpu_memory_gb = (
                                        float(memory_str.split("MB")[0].split()[-1]) / 1024
                                    )
                                break
                    except Exception:
                        pass

            return gpu_type, gpu_name, gpu_memory_gb

    except Exception:
        pass

    return None


def _detect_linux_gpu() -> tuple[str, str, float] | None:
    """Detect GPU on Linux using nvidia-smi or lspci.

    First attempts nvidia-smi for NVIDIA GPUs (most accurate),
    then falls back to lspci for AMD/Intel detection.

    Returns:
        Tuple of (gpu_type, gpu_name, gpu_memory_gb) if detected,
        None if detection fails.
    """
    try:
        # Try nvidia-smi first
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            line = result.stdout.strip().split("\n")[0]
            name, memory_mb = line.split(", ")
            return "nvidia", name.strip(), float(memory_mb) / 1024

        # Try lspci for other GPUs
        result = subprocess.run(
            ["lspci", "-v"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            output = result.stdout.lower()
            if "amd" in output or "radeon" in output:
                return "amd", "AMD GPU", 4.0  # Default estimate
            if "intel" in output and "graphics" in output:
                return "intel", "Intel GPU", 1.0  # Default estimate

    except Exception:
        pass

    return None


def _detect_windows_gpu() -> tuple[str, str, float] | None:
    """Detect GPU on Windows using WMI queries.

    Uses wmic to query Win32_VideoController for GPU information
    including adapter name and video RAM capacity.

    Returns:
        Tuple of (gpu_type, gpu_name, gpu_memory_gb) if detected,
        None if detection fails.
    """
    try:
        # Use wmic to query GPU info
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name,AdapterRAM"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            for line in lines:
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        memory_bytes = int(parts[0]) if parts[0].isdigit() else 0
                        name = " ".join(parts[1:])

                        gpu_type = "unknown"
                        if "nvidia" in name.lower():
                            gpu_type = "nvidia"
                        elif "amd" in name.lower() or "radeon" in name.lower():
                            gpu_type = "amd"
                        elif "intel" in name.lower():
                            gpu_type = "intel"

                        gpu_memory_gb = memory_bytes / (1024**3) if memory_bytes > 0 else 2.0
                        return gpu_type, name, gpu_memory_gb

    except Exception:
        pass

    return None


def _classify_performance_tier(
    gpu_type: str,
    gpu_name: str,
    gpu_memory_gb: float,
    system_memory_gb: float,
    cpu_cores: int,
    is_apple_silicon: bool,
) -> str:
    """Classify hardware into performance tiers for preset selection.

    Uses a rule-based system to classify hardware into four tiers:
        - ultra: Top-tier workstation hardware (M3 Ultra, RTX 4090)
        - high: Professional hardware (M3 Pro/Max, RTX 3000+)
        - medium: Consumer hardware (base M-series, GTX 1060+)
        - low: Entry-level or integrated graphics

    Args:
        gpu_type: GPU vendor identifier.
        gpu_name: GPU model name for specific model detection.
        gpu_memory_gb: Available GPU memory.
        system_memory_gb: System RAM capacity.
        cpu_cores: Number of CPU cores (unused, reserved for future).
        is_apple_silicon: Whether running on M-series chip.

    Returns:
        Performance tier string: "ultra", "high", "medium", or "low".
    """
    # Ultra tier
    if (is_apple_silicon and ("Ultra" in gpu_name or gpu_memory_gb >= 24)) or (
        gpu_type == "nvidia" and ("RTX 4090" in gpu_name or "RTX 4080" in gpu_name)
    ):
        return "ultra"
    if gpu_memory_gb >= 16 and system_memory_gb >= 32:
        return "ultra"

    # High tier
    if (is_apple_silicon and ("Max" in gpu_name or "Pro" in gpu_name)) or (
        gpu_type == "nvidia" and ("RTX" in gpu_name or "GTX 1080" in gpu_name)
    ):
        return "high"
    if (gpu_type == "amd" and "RX" in gpu_name) or (gpu_memory_gb >= 8 and system_memory_gb >= 16):
        return "high"

    # Medium tier
    if is_apple_silicon or (gpu_memory_gb >= 4 and system_memory_gb >= 8):  # Base M1/M2/M3
        return "medium"

    # Low tier
    return "low"


# Module-level cached hardware profile for performance
_cached_hardware: HardwareProfile | None = None


def get_hardware() -> HardwareProfile:
    """Get cached hardware profile, detecting if needed.

    This is the recommended way to access hardware information in
    performance-critical code. The profile is detected once and cached
    for subsequent calls.

    Returns:
        Cached HardwareProfile instance with detected system capabilities.

    Example:
        >>> hw = get_hardware()
        >>> if hw.performance_tier == "ultra":
        ...     enable_high_quality_raytracing()
    """
    global _cached_hardware
    if _cached_hardware is None:
        _cached_hardware = detect_hardware()
    return _cached_hardware


def clear_hardware_cache() -> None:
    """Clear cached hardware profile to force re-detection.

    Call this after hardware changes (e.g., hot-plugging an eGPU)
    to update the cached profile. Next call to `get_hardware()`
    will perform fresh detection.
    """
    global _cached_hardware
    _cached_hardware = None
