"""OIDN (Open Image Denoise) Wrapper for Apple Silicon Metal.

Uses Intel's Open Image Denoise library via Homebrew installation.
OIDN 2.2+ supports Metal acceleration on Apple Silicon.

This provides REAL denoising with pretrained neural network weights,
not a blurry untrained approximation.

Requirements:
    brew install open-image-denoise

Usage:
    from kagami.core.multimodal.vision.oidn_denoiser import OIDNDenoiser

    denoiser = OIDNDenoiser(device='metal')  # or 'cpu'
    clean = denoiser.denoise(noisy_rgb)  # [H, W, 3] float32 0-1

    # With auxiliary buffers (better quality):
    clean = denoiser.denoise(noisy_rgb, albedo=albedo, normal=normal)

Author: Forge Colony (e₂)
Created: December 2025
"""

from __future__ import annotations

import ctypes
import logging
import os
from ctypes import POINTER, c_bool, c_char_p, c_float, c_int, c_size_t, c_void_p
from typing import Any

import numpy as np
from numpy.typing import NDArray

from kagami.core.utils.optional_imports import MissingOptionalDependency

logger = logging.getLogger(__name__)


# =============================================================================
# OIDN C API BINDINGS
# =============================================================================


# Find OIDN library
def _find_oidn_library() -> str | None:
    """Find OIDN library path.

    Prioritizes the Metal-enabled version from external/oidn if available.
    """
    # Project-local Metal-enabled OIDN (priority)
    # __file__ is kagami/core/multimodal/vision/oidn_denoiser.py
    # Go up 5 levels: vision -> multimodal -> core -> kagami -> chronOS
    this_file = os.path.abspath(__file__)
    kagami_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(this_file))))
    project_root = os.path.dirname(kagami_dir)  # chronOS
    local_oidn = os.path.join(project_root, "external", "oidn", "lib", "libOpenImageDenoise.dylib")

    candidates = [
        local_oidn,  # Metal-enabled build (priority)
        "/opt/homebrew/lib/libOpenImageDenoise.dylib",
        "/opt/homebrew/Cellar/open-image-denoise/2.3.3/lib/libOpenImageDenoise.dylib",
        "/usr/local/lib/libOpenImageDenoise.dylib",
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    return None


# OIDN constants
OIDN_DEVICE_TYPE_DEFAULT = 0
OIDN_DEVICE_TYPE_CPU = 1
OIDN_DEVICE_TYPE_SYCL = 2
OIDN_DEVICE_TYPE_CUDA = 3
OIDN_DEVICE_TYPE_HIP = 4
OIDN_DEVICE_TYPE_METAL = 5

OIDN_FORMAT_UNDEFINED = 0
OIDN_FORMAT_FLOAT = 1
OIDN_FORMAT_FLOAT2 = 2
OIDN_FORMAT_FLOAT3 = 3
OIDN_FORMAT_FLOAT4 = 4
OIDN_FORMAT_HALF = 5
OIDN_FORMAT_HALF2 = 6
OIDN_FORMAT_HALF3 = 7
OIDN_FORMAT_HALF4 = 8

OIDN_QUALITY_DEFAULT = 0
OIDN_QUALITY_HIGH = 1
OIDN_QUALITY_BALANCED = 2
OIDN_QUALITY_FAST = 3


class OIDNLibrary:
    """Wrapper for OIDN C library."""

    _instance: OIDNLibrary | None = None

    def __new__(cls) -> OIDNLibrary:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # type: ignore[has-type]
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:  # type: ignore[has-type]
            return

        lib_path = _find_oidn_library()
        if lib_path is None:
            raise MissingOptionalDependency(
                package_name="open-image-denoise",
                feature_name="Open Image Denoise (OIDN)",
                install_cmd="brew install open-image-denoise",
                additional_info=(
                    "OIDN provides high-quality denoising for path-traced renders.\n"
                    "Supports Metal acceleration on Apple Silicon (M1/M2/M3).\n\n"
                    "Alternative installation:\n"
                    "  - Download from: https://www.openimagedenoise.org/downloads.html\n"
                    "  - Or build from source: https://github.com/OpenImageDenoise/oidn"
                ),
            )

        self.lib = ctypes.CDLL(lib_path)
        self._setup_functions()
        self._initialized = True
        logger.info(f"OIDN library loaded from {lib_path}")

    def _setup_functions(self) -> None:
        """Setup ctypes function signatures."""
        lib = self.lib

        # Device functions
        lib.oidnNewDevice.argtypes = [c_int]
        lib.oidnNewDevice.restype = c_void_p

        lib.oidnCommitDevice.argtypes = [c_void_p]
        lib.oidnCommitDevice.restype = None

        lib.oidnReleaseDevice.argtypes = [c_void_p]
        lib.oidnReleaseDevice.restype = None

        lib.oidnGetDeviceError.argtypes = [c_void_p, POINTER(c_char_p)]
        lib.oidnGetDeviceError.restype = c_int

        # Buffer functions (for GPU/Metal)
        lib.oidnNewBuffer.argtypes = [c_void_p, c_size_t]
        lib.oidnNewBuffer.restype = c_void_p

        lib.oidnReleaseBuffer.argtypes = [c_void_p]
        lib.oidnReleaseBuffer.restype = None

        lib.oidnReadBuffer.argtypes = [c_void_p, c_size_t, c_size_t, c_void_p]
        lib.oidnReadBuffer.restype = None

        lib.oidnWriteBuffer.argtypes = [c_void_p, c_size_t, c_size_t, c_void_p]
        lib.oidnWriteBuffer.restype = None

        # Filter functions
        lib.oidnNewFilter.argtypes = [c_void_p, c_char_p]
        lib.oidnNewFilter.restype = c_void_p

        # Use oidnSetSharedFilterImage for host memory (CPU)
        lib.oidnSetSharedFilterImage.argtypes = [
            c_void_p,  # filter
            c_char_p,  # name
            c_void_p,  # ptr
            c_int,  # format
            c_size_t,  # width
            c_size_t,  # height
            c_size_t,  # byteOffset
            c_size_t,  # pixelByteStride
            c_size_t,  # rowByteStride
        ]
        lib.oidnSetSharedFilterImage.restype = None

        # Use oidnSetFilterImage for device buffers (Metal/CUDA)
        lib.oidnSetFilterImage.argtypes = [
            c_void_p,  # filter
            c_char_p,  # name
            c_void_p,  # buffer
            c_int,  # format
            c_size_t,  # width
            c_size_t,  # height
            c_size_t,  # byteOffset
            c_size_t,  # pixelByteStride
            c_size_t,  # rowByteStride
        ]
        lib.oidnSetFilterImage.restype = None

        lib.oidnSetFilterBool.argtypes = [c_void_p, c_char_p, c_bool]
        lib.oidnSetFilterBool.restype = None

        lib.oidnSetFilterInt.argtypes = [c_void_p, c_char_p, c_int]
        lib.oidnSetFilterInt.restype = None

        lib.oidnSetFilterFloat.argtypes = [c_void_p, c_char_p, c_float]
        lib.oidnSetFilterFloat.restype = None

        lib.oidnCommitFilter.argtypes = [c_void_p]
        lib.oidnCommitFilter.restype = None

        lib.oidnExecuteFilter.argtypes = [c_void_p]
        lib.oidnExecuteFilter.restype = None

        lib.oidnReleaseFilter.argtypes = [c_void_p]
        lib.oidnReleaseFilter.restype = None


# =============================================================================
# DENOISER CLASS
# =============================================================================


class OIDNDenoiser:
    """OIDN-based denoiser with Metal support.

    Uses Intel Open Image Denoise with pretrained neural network weights
    for high-quality path tracing denoising.

    Args:
        device: 'metal', 'cpu', or 'default'
        quality: 'high', 'balanced', or 'fast'
        hdr: Whether input is HDR (affects tonemapping)
    """

    def __init__(
        self,
        device: str = "metal",
        quality: str = "high",
        hdr: bool = False,
    ):
        self._lib = OIDNLibrary()
        self._quality = self._parse_quality(quality)
        self._hdr = hdr

        # Try requested device, fallback to CPU if Metal fails
        self._device_type = self._parse_device(device)
        self._device = self._lib.lib.oidnNewDevice(self._device_type)

        # Metal can fail on some macOS configurations - fallback to CPU
        if not self._device and device.lower() == "metal":
            logger.warning("OIDN Metal device failed, falling back to CPU")
            self._device_type = OIDN_DEVICE_TYPE_CPU
            self._device = self._lib.lib.oidnNewDevice(self._device_type)
            device = "cpu"

        if not self._device:
            raise RuntimeError(f"Failed to create OIDN {device} device")

        self._lib.lib.oidnCommitDevice(self._device)
        self._check_error("device creation")

        logger.info(f"OIDN denoiser initialized (device={device}, quality={quality})")

    def _parse_device(self, device: str) -> int:
        """Parse device string to OIDN constant."""
        devices = {
            "default": OIDN_DEVICE_TYPE_DEFAULT,
            "cpu": OIDN_DEVICE_TYPE_CPU,
            "metal": OIDN_DEVICE_TYPE_METAL,
            "cuda": OIDN_DEVICE_TYPE_CUDA,
        }
        return devices.get(device.lower(), OIDN_DEVICE_TYPE_DEFAULT)

    def _parse_quality(self, quality: str) -> int:
        """Parse quality string to OIDN constant."""
        qualities = {
            "default": OIDN_QUALITY_DEFAULT,
            "high": OIDN_QUALITY_HIGH,
            "balanced": OIDN_QUALITY_BALANCED,
            "fast": OIDN_QUALITY_FAST,
        }
        return qualities.get(quality.lower(), OIDN_QUALITY_DEFAULT)

    def _check_error(self, context: str = "") -> None:
        """Check for OIDN errors."""
        error_msg = c_char_p()
        error_code = self._lib.lib.oidnGetDeviceError(self._device, ctypes.byref(error_msg))
        if error_code != 0:
            msg = error_msg.value.decode() if error_msg.value else "Unknown error"
            raise RuntimeError(f"OIDN error ({context}): {msg}")

    def denoise(
        self,
        color: NDArray[np.float32],
        albedo: NDArray[np.float32] | None = None,
        normal: NDArray[np.float32] | None = None,
        clean_aux: bool = False,
    ) -> NDArray[np.float32]:
        """Denoise a rendered image.

        Args:
            color: Noisy RGB image [H, W, 3] float32, range 0-1 (or HDR)
            albedo: Optional albedo buffer [H, W, 3] float32
            normal: Optional normal buffer [H, W, 3] float32 (camera space, normalized)
            clean_aux: Whether auxiliary buffers are noise-free

        Returns:
            Denoised RGB image [H, W, 3] float32
        """
        # Ensure float32 contiguous
        color = np.ascontiguousarray(color, dtype=np.float32)
        H, W, C = color.shape
        assert C == 3, f"Expected 3 channels, got {C}"

        # Prepare output
        output = np.zeros_like(color)

        # Use device buffers for Metal/CUDA, shared memory for CPU
        use_device_buffers = self._device_type in (OIDN_DEVICE_TYPE_METAL, OIDN_DEVICE_TYPE_CUDA)

        # Create filter
        filter_type = b"RT"  # Ray Tracing filter
        filt = self._lib.lib.oidnNewFilter(self._device, filter_type)
        if not filt:
            raise RuntimeError("Failed to create OIDN filter")

        # Buffers to release
        buffers = []

        try:
            buffer_size = H * W * 3 * 4  # HWC float32

            if use_device_buffers:
                # Create device buffers for GPU
                color_buf = self._lib.lib.oidnNewBuffer(self._device, buffer_size)
                output_buf = self._lib.lib.oidnNewBuffer(self._device, buffer_size)
                buffers.extend([color_buf, output_buf])

                # Upload color to device
                self._lib.lib.oidnWriteBuffer(
                    color_buf, 0, buffer_size, c_void_p(color.ctypes.data)
                )

                # Set buffers
                self._lib.lib.oidnSetFilterImage(
                    filt, b"color", color_buf, OIDN_FORMAT_FLOAT3, W, H, 0, 3 * 4, W * 3 * 4
                )
                self._lib.lib.oidnSetFilterImage(
                    filt, b"output", output_buf, OIDN_FORMAT_FLOAT3, W, H, 0, 3 * 4, W * 3 * 4
                )
            else:
                # Use shared memory for CPU
                self._lib.lib.oidnSetSharedFilterImage(
                    filt,
                    b"color",
                    c_void_p(color.ctypes.data),
                    OIDN_FORMAT_FLOAT3,
                    W,
                    H,
                    0,
                    3 * 4,
                    W * 3 * 4,
                )
                self._lib.lib.oidnSetSharedFilterImage(
                    filt,
                    b"output",
                    c_void_p(output.ctypes.data),
                    OIDN_FORMAT_FLOAT3,
                    W,
                    H,
                    0,
                    3 * 4,
                    W * 3 * 4,
                )

            # Set albedo if provided
            if albedo is not None:
                albedo = np.ascontiguousarray(albedo, dtype=np.float32)
                if use_device_buffers:
                    albedo_buf = self._lib.lib.oidnNewBuffer(self._device, buffer_size)
                    buffers.append(albedo_buf)
                    self._lib.lib.oidnWriteBuffer(
                        albedo_buf, 0, buffer_size, c_void_p(albedo.ctypes.data)
                    )
                    self._lib.lib.oidnSetFilterImage(
                        filt, b"albedo", albedo_buf, OIDN_FORMAT_FLOAT3, W, H, 0, 3 * 4, W * 3 * 4
                    )
                else:
                    self._lib.lib.oidnSetSharedFilterImage(
                        filt,
                        b"albedo",
                        c_void_p(albedo.ctypes.data),
                        OIDN_FORMAT_FLOAT3,
                        W,
                        H,
                        0,
                        3 * 4,
                        W * 3 * 4,
                    )

            # Set normal if provided
            if normal is not None:
                normal = np.ascontiguousarray(normal, dtype=np.float32)
                if use_device_buffers:
                    normal_buf = self._lib.lib.oidnNewBuffer(self._device, buffer_size)
                    buffers.append(normal_buf)
                    self._lib.lib.oidnWriteBuffer(
                        normal_buf, 0, buffer_size, c_void_p(normal.ctypes.data)
                    )
                    self._lib.lib.oidnSetFilterImage(
                        filt, b"normal", normal_buf, OIDN_FORMAT_FLOAT3, W, H, 0, 3 * 4, W * 3 * 4
                    )
                else:
                    self._lib.lib.oidnSetSharedFilterImage(
                        filt,
                        b"normal",
                        c_void_p(normal.ctypes.data),
                        OIDN_FORMAT_FLOAT3,
                        W,
                        H,
                        0,
                        3 * 4,
                        W * 3 * 4,
                    )

            # Set options
            self._lib.lib.oidnSetFilterBool(filt, b"hdr", self._hdr)
            if albedo is not None or normal is not None:
                self._lib.lib.oidnSetFilterBool(filt, b"cleanAux", clean_aux)

            # Commit and execute
            self._lib.lib.oidnCommitFilter(filt)
            self._check_error("filter commit")

            self._lib.lib.oidnExecuteFilter(filt)
            self._check_error("filter execute")

            # Read back from device buffer if needed
            if use_device_buffers:
                self._lib.lib.oidnReadBuffer(
                    output_buf, 0, buffer_size, c_void_p(output.ctypes.data)
                )

        finally:
            self._lib.lib.oidnReleaseFilter(filt)
            for buf in buffers:
                if buf:
                    self._lib.lib.oidnReleaseBuffer(buf)

        return output

    def denoise_uint8(
        self,
        color: NDArray[np.uint8],
        albedo: NDArray[np.uint8] | None = None,
        normal: NDArray[np.uint8] | None = None,
    ) -> NDArray[np.uint8]:
        """Convenience method for uint8 input/output.

        Args:
            color: Noisy RGB image [H, W, 3] uint8
            albedo: Optional albedo buffer [H, W, 3] uint8
            normal: Optional normal buffer [H, W, 3] uint8

        Returns:
            Denoised RGB image [H, W, 3] uint8
        """
        # Convert to float32
        color_f = color.astype(np.float32) / 255.0
        albedo_f = albedo.astype(np.float32) / 255.0 if albedo is not None else None
        normal_f = normal.astype(np.float32) / 255.0 if normal is not None else None

        # Denoise
        output_f = self.denoise(color_f, albedo_f, normal_f)

        # Convert back
        return (output_f * 255).clip(0, 255).astype(np.uint8)

    def __del__(self) -> None:
        """Release OIDN device."""
        if hasattr(self, "_device") and self._device:
            self._lib.lib.oidnReleaseDevice(self._device)


# =============================================================================
# GENESIS INTEGRATION
# =============================================================================


class GenesisOIDNDenoiser:
    """OIDN wrapper for Genesis rendering pipeline.

    Drop-in replacement for GenesisDenoiserWrapper that uses
    real OIDN denoising instead of untrained neural network.

    Usage:
        denoiser = GenesisOIDNDenoiser()

        result = cam.render()
        rgb = result[0]

        clean = denoiser.denoise(rgb)
    """

    def __init__(
        self,
        device: str = "metal",
        quality: str = "high",
    ):
        """Initialize OIDN denoiser for Genesis.

        Args:
            device: 'metal' (GPU) or 'cpu'
            quality: 'high', 'balanced', or 'fast'
        """
        try:
            self._denoiser = OIDNDenoiser(device=device, quality=quality)
            self._available = True
            logger.info(f"OIDN denoiser ready (device={device})")
        except Exception as e:
            logger.warning(
                f"OIDN not available: {e}. Install with: brew install open-image-denoise"
            )
            self._denoiser = None  # type: ignore[assignment]
            self._available = False

    @property
    def available(self) -> bool:
        """Whether OIDN is available."""
        return self._available

    def denoise(
        self,
        rgb: Any,
        depth: Any | None = None,
        normals: Any | None = None,
        albedo: Any | None = None,
    ) -> NDArray[np.uint8]:
        """Denoise a Genesis render result.

        Args:
            rgb: RGB from cam.render()[0]
            depth: Depth buffer (not used by OIDN, but kept for API compat)
            normals: Normal buffer from cam.render()
            albedo: Albedo buffer (if available)

        Returns:
            Denoised RGB as numpy uint8 [H, W, 3]
        """
        # Convert Genesis tensor to numpy
        if hasattr(rgb, "numpy"):
            rgb = rgb.numpy()
        rgb = np.asarray(rgb, dtype=np.uint8)

        if not self._available:
            logger.warning("OIDN not available, returning original")
            return rgb

        # Convert normals if provided
        normals_np = None
        if normals is not None:
            if hasattr(normals, "numpy"):
                normals = normals.numpy()
            normals_np = np.asarray(normals, dtype=np.uint8)

        # Convert albedo if provided
        albedo_np = None
        if albedo is not None:
            if hasattr(albedo, "numpy"):
                albedo = albedo.numpy()
            albedo_np = np.asarray(albedo, dtype=np.uint8)

        return self._denoiser.denoise_uint8(rgb, albedo_np, normals_np)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_oidn_denoiser(
    device: str = "metal",
    quality: str = "high",
) -> GenesisOIDNDenoiser:
    """Create an OIDN denoiser for Genesis.

    Args:
        device: 'metal' (GPU acceleration) or 'cpu'
        quality: 'high', 'balanced', or 'fast'

    Returns:
        GenesisOIDNDenoiser instance
    """
    return GenesisOIDNDenoiser(device=device, quality=quality)


# =============================================================================
# MODULE EXPORTS
# =============================================================================


__all__ = [
    "GenesisOIDNDenoiser",
    "OIDNDenoiser",
    "create_oidn_denoiser",
]
