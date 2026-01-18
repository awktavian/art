"""Edge Compute Detection for embedded platforms.

Detects and configures:
- Jetson: CUDA support, TensorRT, DLA
- Raspberry Pi: VideoCore GPU, OpenCL
- Generic ARM64: OpenCL, Vulkan

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from kagami_hal.adapters.embedded.platforms import (
    EmbeddedPlatform,
)

logger = logging.getLogger(__name__)


class EdgeComputeDetector:
    """Detect edge compute capabilities."""

    def __init__(self, platform: EmbeddedPlatform):
        """Initialize compute detector.

        Args:
            platform: Detected embedded platform
        """
        self._platform = platform

    def detect_cuda(self) -> bool:
        """Detect CUDA support (Jetson).

        Returns:
            True if CUDA available
        """
        if "JETSON" not in self._platform.name:
            return False

        # Check for CUDA toolkit
        cuda_paths = [
            Path("/usr/local/cuda"),
            Path("/usr/local/cuda-11.4"),
            Path("/usr/local/cuda-12.0"),
        ]

        for cuda_path in cuda_paths:
            if cuda_path.exists():
                logger.info(f"CUDA detected at {cuda_path}")
                return True

        return False

    def detect_tensorrt(self) -> bool:
        """Detect TensorRT (Jetson).

        Returns:
            True if TensorRT available
        """
        if "JETSON" not in self._platform.name:
            return False

        # Check for TensorRT library
        tensorrt_paths = [
            Path("/usr/lib/aarch64-linux-gnu/libnvinfer.so"),
            Path("/usr/lib/aarch64-linux-gnu/libnvinfer.so.8"),
        ]

        for trt_path in tensorrt_paths:
            if trt_path.exists():
                logger.info("TensorRT detected")
                return True

        return False

    def detect_dla(self) -> bool:
        """Detect Deep Learning Accelerator (Jetson Xavier/Orin).

        Returns:
            True if DLA available
        """
        if self._platform not in (EmbeddedPlatform.JETSON_XAVIER, EmbeddedPlatform.JETSON_ORIN):
            return False

        # Check for DLA devices
        dla_path = Path("/proc/device-tree/dla")
        if dla_path.exists():
            logger.info("DLA accelerator detected")
            return True

        return False

    def detect_opencl(self) -> bool:
        """Detect OpenCL support.

        Returns:
            True if OpenCL available
        """
        # Check for OpenCL library
        opencl_paths = [
            Path("/usr/lib/aarch64-linux-gnu/libOpenCL.so"),
            Path("/usr/lib/arm-linux-gnueabihf/libOpenCL.so"),
            Path("/opt/vc/lib/libOpenCL.so"),  # VideoCore (RPi)
        ]

        for ocl_path in opencl_paths:
            if ocl_path.exists():
                logger.info(f"OpenCL detected at {ocl_path}")
                return True

        return False

    def detect_vulkan(self) -> bool:
        """Detect Vulkan support.

        Returns:
            True if Vulkan available
        """
        # Check for Vulkan library
        vulkan_paths = [
            Path("/usr/lib/aarch64-linux-gnu/libvulkan.so"),
            Path("/usr/lib/arm-linux-gnueabihf/libvulkan.so"),
        ]

        for vk_path in vulkan_paths:
            if vk_path.exists():
                logger.info(f"Vulkan detected at {vk_path}")
                return True

        return False

    def detect_videocore(self) -> bool:
        """Detect VideoCore GPU (Raspberry Pi).

        Returns:
            True if VideoCore available
        """
        if "RASPBERRY_PI" not in self._platform.name:
            return False

        # Check for VideoCore libraries
        vc_path = Path("/opt/vc/lib")
        if vc_path.exists():
            logger.info("VideoCore GPU detected")
            return True

        return False

    def get_cuda_version(self) -> str | None:
        """Get CUDA version.

        Returns:
            CUDA version string or None
        """
        if not self.detect_cuda():
            return None

        try:
            result = subprocess.run(
                ["nvcc", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse version from output
                for line in result.stdout.splitlines():
                    if "release" in line.lower():
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part.lower() == "release" and i + 1 < len(parts):
                                return parts[i + 1].rstrip(",")
        except Exception as e:
            logger.debug(f"Failed to get CUDA version: {e}")

        return None

    def get_tensorrt_version(self) -> str | None:
        """Get TensorRT version.

        Returns:
            TensorRT version string or None
        """
        if not self.detect_tensorrt():
            return None

        try:
            # Try to read version from dpkg
            result = subprocess.run(
                ["dpkg", "-l", "libnvinfer8"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith("ii"):
                        parts = line.split()
                        if len(parts) >= 3:
                            return parts[2]
        except Exception as e:
            logger.debug(f"Failed to get TensorRT version: {e}")

        return None

    def get_opencl_devices(self) -> list[dict[str, Any]]:
        """Get OpenCL device information.

        Returns:
            List of OpenCL device info dicts
        """
        if not self.detect_opencl():
            return []

        devices = []

        try:
            # Try to use pyopencl if available
            import pyopencl as cl

            platforms = cl.get_platforms()
            for platform in platforms:
                for device in platform.get_devices():
                    devices.append(
                        {
                            "name": device.name,
                            "type": device.type,
                            "vendor": device.vendor,
                            "version": device.version,
                            "compute_units": device.max_compute_units,
                            "max_work_group_size": device.max_work_group_size,
                            "global_mem_mb": device.global_mem_size // (1024 * 1024),
                        }
                    )

        except ImportError:
            logger.debug("pyopencl not available, cannot query OpenCL devices")
        except Exception as e:
            logger.debug(f"Failed to query OpenCL devices: {e}")

        return devices

    def get_vulkan_devices(self) -> list[dict[str, Any]]:
        """Get Vulkan device information.

        Returns:
            List of Vulkan device info dicts
        """
        if not self.detect_vulkan():
            return []

        devices = []

        try:
            # Use vulkaninfo command
            result = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Parse vulkaninfo output (simplified)
                current_device = {}  # type: ignore[var-annotated]
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if "GPU" in line and ":" in line:
                        if current_device:
                            devices.append(current_device)
                        current_device = {"name": line.split(":")[1].strip()}
                    elif "apiVersion" in line and current_device:
                        current_device["api_version"] = line.split("=")[1].strip()
                    elif "driverVersion" in line and current_device:
                        current_device["driver_version"] = line.split("=")[1].strip()

                if current_device:
                    devices.append(current_device)

        except FileNotFoundError:
            logger.debug("vulkaninfo not available")
        except Exception as e:
            logger.debug(f"Failed to query Vulkan devices: {e}")

        return devices

    def get_jetson_model(self) -> str | None:
        """Get Jetson model name.

        Returns:
            Model name or None
        """
        if "JETSON" not in self._platform.name:
            return None

        jetson_release = Path("/etc/nv_tegra_release")
        if jetson_release.exists():
            content = jetson_release.read_text()
            for line in content.splitlines():
                if "#" in line:
                    return line.split("#")[1].strip()

        return None

    def get_compute_info(self) -> dict[str, Any]:
        """Get comprehensive compute information.

        Returns:
            Dict with all compute capabilities
        """
        info: dict[str, Any] = {
            "platform": self._platform.value,
            "cuda": self.detect_cuda(),
            "tensorrt": self.detect_tensorrt(),
            "dla": self.detect_dla(),
            "opencl": self.detect_opencl(),
            "vulkan": self.detect_vulkan(),
            "videocore": self.detect_videocore(),
        }

        # Add version info
        if info["cuda"]:
            info["cuda_version"] = self.get_cuda_version()
        if info["tensorrt"]:
            info["tensorrt_version"] = self.get_tensorrt_version()

        # Add device info
        if info["opencl"]:
            info["opencl_devices"] = self.get_opencl_devices()
        if info["vulkan"]:
            info["vulkan_devices"] = self.get_vulkan_devices()

        # Jetson-specific
        if "JETSON" in self._platform.name:
            info["jetson_model"] = self.get_jetson_model()

        return info


__all__ = ["EdgeComputeDetector"]
