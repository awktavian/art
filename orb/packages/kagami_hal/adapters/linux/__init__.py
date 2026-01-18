"""Linux HAL Adapters.

Platform-specific implementations for Linux desktop and embedded systems.
Supports:
- V4L2 cameras
- ALSA/PulseAudio audio
- Linux thermal zones
- evdev input devices
- Framebuffer/X11/Wayland display
- GPU detection (CUDA, Vulkan, OpenCL)

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kagami_hal.adapters.linux.audio import LinuxAudio
    from kagami_hal.adapters.linux.display import LinuxDisplay
    from kagami_hal.adapters.linux.input import LinuxInput
    from kagami_hal.adapters.linux.power import LinuxPower
    from kagami_hal.adapters.linux.sensors import LinuxSensors
    from kagami_hal.data_types import AudioConfig

logger = logging.getLogger(__name__)

# Platform check
LINUX_AVAILABLE = sys.platform.startswith("linux")

# Hardware availability checks - LAZY (call _check_*() methods instead)
# DO NOT evaluate at import time to avoid syscall overhead during boot


def _check_v4l2() -> bool:
    """Check V4L2 camera availability (lazy)."""
    return any(Path("/dev").glob("video*"))


def _check_alsa() -> bool:
    """Check ALSA audio availability (lazy)."""
    return Path("/proc/asound").exists()


def _check_framebuffer() -> bool:
    """Check framebuffer availability (lazy)."""
    return Path("/dev/fb0").exists()


def _check_thermal_zones() -> bool:
    """Check thermal zone availability (lazy)."""
    return Path("/sys/class/thermal").exists()


def _check_input_devices() -> bool:
    """Check input device availability (lazy)."""
    return Path("/dev/input").exists()


class LinuxHAL:
    """Linux HAL entry point with hardware detection."""

    def __init__(self) -> None:
        """Initialize Linux HAL."""
        self._initialized = False
        self._detected_hardware: dict[str, bool] = {}

    async def initialize(self) -> bool:
        """Initialize and detect available hardware.

        Returns:
            True if running on Linux and some hardware detected
        """
        if not LINUX_AVAILABLE:
            logger.warning("LinuxHAL only available on Linux platforms")
            return False

        # Detect hardware (lazy evaluation - called during initialize, not import)
        self._detected_hardware = {
            "v4l2_camera": _check_v4l2(),
            "alsa_audio": _check_alsa(),
            "framebuffer": _check_framebuffer(),
            "thermal_zones": _check_thermal_zones(),
            "input_devices": _check_input_devices(),
        }

        # GPU detection (lazy - only called during initialize)
        self._detected_hardware.update(
            {
                "cuda": self._detect_cuda(),
                "vulkan": self._detect_vulkan(),
                "opencl": self._detect_opencl(),
            }
        )

        self._initialized = True
        available_count = sum(self._detected_hardware.values())

        logger.info(f"✅ Linux HAL initialized: {available_count} hardware subsystems available")
        logger.debug(f"Detected hardware: {self._detected_hardware}")

        return available_count > 0

    def _detect_cuda(self) -> bool:
        """Detect CUDA availability via nvidia-smi."""
        try:
            import subprocess

            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                timeout=1,
            )
            return result.returncode == 0 and len(result.stdout.strip()) > 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _detect_vulkan(self) -> bool:
        """Detect Vulkan availability via vulkaninfo."""
        try:
            import subprocess

            result = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True,
                timeout=1,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _detect_opencl(self) -> bool:
        """Detect OpenCL availability via clinfo."""
        try:
            import subprocess

            result = subprocess.run(
                ["clinfo"], capture_output=True, timeout=1, stderr=subprocess.DEVNULL
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_detected_hardware(self) -> dict[str, bool]:
        """Get dictionary of detected hardware capabilities.

        Returns:
            Dict mapping hardware type to availability
        """
        return self._detected_hardware.copy()

    async def create_audio_adapter(self, config: AudioConfig | None = None) -> LinuxAudio:
        """Create Linux audio adapter.

        Args:
            config: Audio configuration (optional)

        Returns:
            LinuxAudio adapter instance

        Raises:
            RuntimeError: If ALSA not available
        """
        from kagami_hal.adapters.linux.audio import LinuxAudio

        adapter = LinuxAudio()
        if config:
            await adapter.initialize(config)
        return adapter

    async def create_sensor_adapter(self) -> LinuxSensors:
        """Create Linux sensor adapter.

        Returns:
            LinuxSensors adapter instance
        """
        from kagami_hal.adapters.linux.sensors import LinuxSensors

        adapter = LinuxSensors()
        await adapter.initialize()
        return adapter

    async def create_display_adapter(self) -> LinuxDisplay:
        """Create Linux display adapter.

        Returns:
            LinuxDisplay adapter instance
        """
        from kagami_hal.adapters.linux.display import LinuxDisplay

        adapter = LinuxDisplay()
        await adapter.initialize()
        return adapter

    async def create_input_adapter(self) -> LinuxInput:
        """Create Linux input adapter.

        Returns:
            LinuxInput adapter instance
        """
        from kagami_hal.adapters.linux.input import LinuxInput

        adapter = LinuxInput()
        await adapter.initialize()
        return adapter

    async def create_power_adapter(self) -> LinuxPower:
        """Create Linux power adapter.

        Returns:
            LinuxPower adapter instance
        """
        from kagami_hal.adapters.linux.power import LinuxPower

        adapter = LinuxPower()
        await adapter.initialize()
        return adapter

    async def shutdown(self) -> None:
        """Shutdown Linux HAL."""
        self._initialized = False
        logger.info("✅ Linux HAL shutdown complete")


__all__ = [
    "LINUX_AVAILABLE",
    "LinuxHAL",
    "_check_alsa",
    "_check_framebuffer",
    "_check_input_devices",
    "_check_thermal_zones",
    # Hardware check functions (lazy evaluation)
    "_check_v4l2",
]
