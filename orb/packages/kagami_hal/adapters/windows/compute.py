"""Windows GPU Compute Detection.

Detects available GPU compute capabilities on Windows:
- CUDA (NVIDIA)
- DirectX / DirectML (Microsoft)
- Vulkan (Khronos)
- OpenCL (cross-vendor)

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

WINDOWS_AVAILABLE = sys.platform == "win32"


@dataclass
class ComputeCapabilities:
    """GPU compute capabilities.

    Attributes:
        cuda_available: CUDA support available
        cuda_version: CUDA version string
        cuda_device_count: Number of CUDA devices
        cuda_devices: List of CUDA device names
        directml_available: DirectML support available
        directx_version: DirectX version string
        vulkan_available: Vulkan support available
        vulkan_version: Vulkan version string
        opencl_available: OpenCL support available
        opencl_version: OpenCL version string
        cpu_fallback: CPU fallback available
    """

    cuda_available: bool = False
    cuda_version: str | None = None
    cuda_device_count: int = 0
    cuda_devices: list[str] | None = None

    directml_available: bool = False
    directx_version: str | None = None

    vulkan_available: bool = False
    vulkan_version: str | None = None

    opencl_available: bool = False
    opencl_version: str | None = None

    cpu_fallback: bool = True


class WindowsComputeDetector:
    """Windows GPU compute detector.

    Detects available GPU compute frameworks on Windows.
    """

    def __init__(self):
        """Initialize compute detector."""
        self._capabilities: ComputeCapabilities | None = None

    async def detect(self) -> ComputeCapabilities:
        """Detect available compute capabilities.

        Returns:
            ComputeCapabilities with all detected frameworks
        """
        if self._capabilities is not None:
            return self._capabilities

        caps = ComputeCapabilities()

        # Detect CUDA
        cuda_info = await self._detect_cuda()
        caps.cuda_available = cuda_info["available"]
        caps.cuda_version = cuda_info.get("version")
        caps.cuda_device_count = cuda_info.get("device_count", 0)
        caps.cuda_devices = cuda_info.get("devices")

        # Detect DirectML
        directml_info = await self._detect_directml()
        caps.directml_available = directml_info["available"]
        caps.directx_version = directml_info.get("version")

        # Detect Vulkan
        vulkan_info = await self._detect_vulkan()
        caps.vulkan_available = vulkan_info["available"]
        caps.vulkan_version = vulkan_info.get("version")

        # Detect OpenCL
        opencl_info = await self._detect_opencl()
        caps.opencl_available = opencl_info["available"]
        caps.opencl_version = opencl_info.get("version")

        self._capabilities = caps

        logger.info(
            f"Compute capabilities: CUDA={caps.cuda_available}, "
            f"DirectML={caps.directml_available}, Vulkan={caps.vulkan_available}, "
            f"OpenCL={caps.opencl_available}"
        )

        return caps

    async def _detect_cuda(self) -> dict[str, Any]:
        """Detect CUDA availability.

        Returns:
            Dict with CUDA detection results
        """
        try:
            import torch

            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                devices = [torch.cuda.get_device_name(i) for i in range(device_count)]
                version = torch.version.cuda

                return {
                    "available": True,
                    "version": version,
                    "device_count": device_count,
                    "devices": devices,
                }

        except ImportError:
            logger.debug("PyTorch not available for CUDA detection")
        except Exception as e:
            logger.debug(f"CUDA detection failed: {e}")

        return {"available": False}

    async def _detect_directml(self) -> dict[str, Any]:
        """Detect DirectML availability.

        Returns:
            Dict with DirectML detection results
        """
        if not WINDOWS_AVAILABLE:
            return {"available": False}

        try:
            # Try to import DirectML bindings
            import torch_directml  # type: ignore

            # Check if DirectML device is available
            if torch_directml.is_available():
                device_count = torch_directml.device_count()

                return {
                    "available": True,
                    "version": "1.x",  # DirectML version
                    "device_count": device_count,
                }

        except ImportError:
            logger.debug("torch-directml not available")
        except Exception as e:
            logger.debug(f"DirectML detection failed: {e}")

        # Fallback: Check if DirectX 12 is available via dxdiag
        try:
            import subprocess

            result = subprocess.run(
                ["dxdiag", "/t", "nul"],
                capture_output=True,
                timeout=2,
                check=False,
            )

            if result.returncode == 0:
                return {
                    "available": True,
                    "version": "12.0",  # Assume DX12
                }

        except Exception:
            pass

        return {"available": False}

    async def _detect_vulkan(self) -> dict[str, Any]:
        """Detect Vulkan availability.

        Returns:
            Dict with Vulkan detection results
        """
        try:
            # Try vulkan library
            import vulkan as vk  # type: ignore

            # Try to enumerate physical devices
            app_info = vk.VkApplicationInfo(
                sType=vk.VK_STRUCTURE_TYPE_APPLICATION_INFO,
                pApplicationName="KagamiHAL",
                applicationVersion=vk.VK_MAKE_VERSION(1, 0, 0),
                pEngineName="Kagami",
                engineVersion=vk.VK_MAKE_VERSION(1, 0, 0),
                apiVersion=vk.VK_API_VERSION_1_0,
            )

            create_info = vk.VkInstanceCreateInfo(
                sType=vk.VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
                pApplicationInfo=app_info,
            )

            instance = vk.vkCreateInstance(create_info, None)
            devices = vk.vkEnumeratePhysicalDevices(instance)
            vk.vkDestroyInstance(instance, None)

            if devices:
                return {
                    "available": True,
                    "version": "1.0",
                    "device_count": len(devices),
                }

        except ImportError:
            logger.debug("vulkan library not available")
        except Exception as e:
            logger.debug(f"Vulkan detection failed: {e}")

        # Fallback: Check if vulkaninfo.exe exists
        try:
            import subprocess

            result = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True,
                timeout=2,
                check=False,
            )

            if result.returncode == 0 and b"Vulkan Instance Version" in result.stdout:
                return {"available": True, "version": "1.x"}

        except Exception:
            pass

        return {"available": False}

    async def _detect_opencl(self) -> dict[str, Any]:
        """Detect OpenCL availability.

        Returns:
            Dict with OpenCL detection results
        """
        try:
            import pyopencl as cl  # type: ignore

            platforms = cl.get_platforms()
            if platforms:
                devices = platforms[0].get_devices()
                version = platforms[0].version

                return {
                    "available": True,
                    "version": version,
                    "device_count": len(devices),
                }

        except ImportError:
            logger.debug("pyopencl not available")
        except Exception as e:
            logger.debug(f"OpenCL detection failed: {e}")

        return {"available": False}

    def get_preferred_backend(self) -> str:
        """Get recommended compute backend for this system.

        Returns:
            Backend name: "cuda", "directml", "vulkan", "opencl", or "cpu"
        """
        if not self._capabilities:
            return "cpu"

        caps = self._capabilities

        # Preference order: CUDA > DirectML > Vulkan > OpenCL > CPU
        if caps.cuda_available:
            return "cuda"
        elif caps.directml_available:
            return "directml"
        elif caps.vulkan_available:
            return "vulkan"
        elif caps.opencl_available:
            return "opencl"
        else:
            return "cpu"

    def get_device_list(self) -> list[dict[str, Any]]:
        """Get list of all available compute devices.

        Returns:
            List of device info dicts
        """
        if not self._capabilities:
            return []

        devices = []
        caps = self._capabilities

        # Add CUDA devices
        if caps.cuda_available and caps.cuda_devices:
            for i, device_name in enumerate(caps.cuda_devices):
                devices.append(
                    {
                        "backend": "cuda",
                        "index": i,
                        "name": device_name,
                        "type": "gpu",
                    }
                )

        # Add DirectML device (generic)
        if caps.directml_available:
            devices.append(
                {
                    "backend": "directml",
                    "index": 0,
                    "name": "DirectML GPU",
                    "type": "gpu",
                }
            )

        # Add Vulkan device (generic)
        if caps.vulkan_available:
            devices.append(
                {
                    "backend": "vulkan",
                    "index": 0,
                    "name": "Vulkan GPU",
                    "type": "gpu",
                }
            )

        # Add OpenCL device (generic)
        if caps.opencl_available:
            devices.append(
                {
                    "backend": "opencl",
                    "index": 0,
                    "name": "OpenCL Device",
                    "type": "gpu",
                }
            )

        # Always add CPU fallback
        devices.append(
            {
                "backend": "cpu",
                "index": 0,
                "name": "CPU",
                "type": "cpu",
            }
        )

        return devices
