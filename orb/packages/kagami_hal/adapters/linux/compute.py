"""Linux Compute Capabilities Detection.

Detects GPU and accelerator hardware:
- NVIDIA CUDA
- Vulkan
- OpenCL
- CPU info

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ComputeDevice:
    """Compute device information."""

    name: str
    type: str  # "cuda", "vulkan", "opencl", "cpu"
    memory_mb: int
    compute_capability: str | None = None
    vendor: str | None = None


@dataclass
class ComputeCapabilities:
    """System compute capabilities."""

    devices: list[ComputeDevice]
    has_cuda: bool
    has_vulkan: bool
    has_opencl: bool
    cpu_count: int
    total_memory_mb: int


class LinuxCompute:
    """Linux compute capabilities detector."""

    def __init__(self) -> None:
        """Initialize compute detector."""
        self._capabilities: ComputeCapabilities | None = None

    async def detect(self) -> ComputeCapabilities:
        """Detect all available compute devices.

        Returns:
            ComputeCapabilities with detected hardware
        """
        devices: list[ComputeDevice] = []

        # Detect CUDA
        cuda_devices = await self._detect_cuda()
        devices.extend(cuda_devices)

        # Detect Vulkan
        vulkan_devices = await self._detect_vulkan()
        devices.extend(vulkan_devices)

        # Detect OpenCL
        opencl_devices = await self._detect_opencl()
        devices.extend(opencl_devices)

        # Detect CPU
        cpu_device = await self._detect_cpu()
        if cpu_device:
            devices.append(cpu_device)

        # Get system memory
        total_memory = await self._get_system_memory()

        self._capabilities = ComputeCapabilities(
            devices=devices,
            has_cuda=any(d.type == "cuda" for d in devices),
            has_vulkan=any(d.type == "vulkan" for d in devices),
            has_opencl=any(d.type == "opencl" for d in devices),
            cpu_count=self._get_cpu_count(),
            total_memory_mb=total_memory,
        )

        logger.info(
            f"✅ Compute detection complete: {len(devices)} devices, "
            f"CUDA={self._capabilities.has_cuda}, "
            f"Vulkan={self._capabilities.has_vulkan}, "
            f"OpenCL={self._capabilities.has_opencl}"
        )

        return self._capabilities

    async def _detect_cuda(self) -> list[ComputeDevice]:
        """Detect NVIDIA CUDA devices via nvidia-smi."""
        devices = []  # type: ignore[var-annotated]

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,compute_cap",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )

            if result.returncode != 0:
                return devices

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    name = parts[0]
                    memory_mb = int(parts[1])
                    compute_cap = parts[2]

                    devices.append(
                        ComputeDevice(
                            name=name,
                            type="cuda",
                            memory_mb=memory_mb,
                            compute_capability=compute_cap,
                            vendor="NVIDIA",
                        )
                    )

            logger.info(f"Detected {len(devices)} CUDA device(s)")

        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as e:
            logger.debug(f"CUDA detection failed: {e}")

        return devices

    async def _detect_vulkan(self) -> list[ComputeDevice]:
        """Detect Vulkan devices via vulkaninfo."""
        devices = []  # type: ignore[var-annotated]

        try:
            result = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True,
                text=True,
                timeout=2,
            )

            if result.returncode != 0:
                return devices

            # Parse vulkaninfo output
            current_device = None
            for line in result.stdout.split("\n"):
                line = line.strip()

                # Look for GPU lines
                if "GPU" in line and ":" in line:
                    # Example: "GPU0: NVIDIA GeForce RTX 3080"
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        current_device = parts[1].strip()

                # Look for memory info (approximate)
                if current_device and "deviceName" in line:
                    name = line.split("=")[1].strip() if "=" in line else current_device

                    devices.append(
                        ComputeDevice(
                            name=name,
                            type="vulkan",
                            memory_mb=0,  # vulkaninfo doesn't easily expose memory
                            vendor=None,
                        )
                    )
                    current_device = None

            if devices:
                logger.info(f"Detected {len(devices)} Vulkan device(s)")

        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.debug(f"Vulkan detection failed: {e}")

        return devices

    async def _detect_opencl(self) -> list[ComputeDevice]:
        """Detect OpenCL devices via clinfo."""
        devices = []  # type: ignore[var-annotated]

        try:
            result = subprocess.run(
                ["clinfo", "--list"],
                capture_output=True,
                text=True,
                timeout=2,
                stderr=subprocess.DEVNULL,
            )

            if result.returncode != 0:
                return devices

            # Parse clinfo output
            for line in result.stdout.split("\n"):
                line = line.strip()

                # Look for device lines
                # Example: "Platform #0: NVIDIA CUDA"
                #          "  Device #0: NVIDIA GeForce RTX 3080"
                if "Device #" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        name = parts[1].strip()

                        devices.append(
                            ComputeDevice(
                                name=name,
                                type="opencl",
                                memory_mb=0,  # clinfo --list doesn't show memory
                                vendor=None,
                            )
                        )

            if devices:
                logger.info(f"Detected {len(devices)} OpenCL device(s)")

        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.debug(f"OpenCL detection failed: {e}")

        return devices

    async def _detect_cpu(self) -> ComputeDevice | None:
        """Detect CPU info."""
        try:
            cpuinfo_path = Path("/proc/cpuinfo")

            if not cpuinfo_path.exists():
                return None

            with open(cpuinfo_path) as f:
                lines = f.readlines()

            # Extract model name
            cpu_name = "Unknown CPU"
            for line in lines:
                if line.startswith("model name"):
                    cpu_name = line.split(":", 1)[1].strip()
                    break

            return ComputeDevice(
                name=cpu_name,
                type="cpu",
                memory_mb=0,  # CPU doesn't have dedicated memory
                vendor=None,
            )

        except Exception as e:
            logger.debug(f"CPU detection failed: {e}")
            return None

    @staticmethod
    def _get_cpu_count() -> int:
        """Get number of CPU cores."""
        try:
            with open("/proc/cpuinfo") as f:
                return sum(1 for line in f if line.startswith("processor"))
        except Exception:
            return 1

    async def _get_system_memory(self) -> int:
        """Get total system memory in MB."""
        try:
            meminfo_path = Path("/proc/meminfo")

            if not meminfo_path.exists():
                return 0

            with open(meminfo_path) as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        # MemTotal is in kB
                        kb = int(line.split()[1])
                        return kb // 1024  # Convert to MB

        except Exception as e:
            logger.debug(f"Failed to read system memory: {e}")

        return 0

    def get_capabilities(self) -> ComputeCapabilities | None:
        """Get cached compute capabilities.

        Returns:
            ComputeCapabilities or None if not yet detected
        """
        return self._capabilities

    def get_cuda_devices(self) -> list[ComputeDevice]:
        """Get list of CUDA devices.

        Returns:
            List of CUDA devices
        """
        if not self._capabilities:
            return []
        return [d for d in self._capabilities.devices if d.type == "cuda"]

    def get_best_device(self, prefer_type: str | None = None) -> ComputeDevice | None:
        """Get best available compute device.

        Args:
            prefer_type: Preferred device type ("cuda", "vulkan", "opencl")

        Returns:
            Best device or None if no devices
        """
        if not self._capabilities or not self._capabilities.devices:
            return None

        # Filter by preferred type if specified
        if prefer_type:
            candidates = [d for d in self._capabilities.devices if d.type == prefer_type]
            if candidates:
                # Return device with most memory
                return max(candidates, key=lambda d: d.memory_mb)

        # Otherwise, prioritize: CUDA > Vulkan > OpenCL > CPU
        priority_order = ["cuda", "vulkan", "opencl", "cpu"]

        for device_type in priority_order:
            candidates = [d for d in self._capabilities.devices if d.type == device_type]
            if candidates:
                return max(candidates, key=lambda d: d.memory_mb)

        return None


__all__ = ["ComputeCapabilities", "ComputeDevice", "LinuxCompute"]
