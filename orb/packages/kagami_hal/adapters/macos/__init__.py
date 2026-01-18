"""macOS HAL Adapters.

Platform-specific implementations for macOS desktop.
Supports:
- AVFoundation cameras (1080p @ 30fps)
- CoreAudio audio I/O (48kHz, 16-bit)
- CoreGraphics display
- IOKit sensors (thermal, light, GPS)
- Metal GPU detection
- IOKit power management

Created: November 10, 2025
Enhanced: December 15, 2025 - Camera/microphone sensors, Metal detection
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kagami_hal.adapters.macos.audio import MacOSCoreAudio
    from kagami_hal.adapters.macos.display import MacOSCoreGraphicsDisplay
    from kagami_hal.adapters.macos.input import MacOSIOKitInput
    from kagami_hal.adapters.macos.power import MacOSPower
    from kagami_hal.adapters.macos.sensors import MacOSSensors
    from kagami_hal.data_types import AudioConfig

logger = logging.getLogger(__name__)

# Platform check
MACOS_AVAILABLE = sys.platform == "darwin"

# Hardware availability checks (lazy, checked at runtime)
_hardware_checked = False
_detected_hardware: dict[str, bool] = {}


def _check_hardware() -> dict[str, bool]:
    """Check hardware availability (cached)."""
    global _hardware_checked, _detected_hardware

    if _hardware_checked:
        return _detected_hardware

    import subprocess

    detected = {}

    # Camera (AVFoundation or OpenCV)
    try:
        import cv2

        detected["camera"] = True
    except ImportError:
        try:
            import AVFoundation

            detected["camera"] = True
        except ImportError:
            detected["camera"] = False
            logger.debug(
                "Camera support unavailable. Install opencv-python or pyobjc-framework-AVFoundation"
            )

    # Audio I/O (PyAudio or sounddevice)
    try:
        import pyaudio

        detected["audio_io"] = True
    except ImportError:
        try:
            import sounddevice

            detected["audio_io"] = True
        except ImportError:
            detected["audio_io"] = False
            logger.debug("Audio I/O unavailable. Install pyaudio or sounddevice")

    # CoreGraphics display
    try:
        import Quartz

        detected["display"] = True
    except ImportError:
        detected["display"] = False
        logger.debug("CoreGraphics display unavailable. Install pyobjc-framework-Quartz")

    # Thermal sensors via sysctl
    try:
        result = subprocess.run(
            ["sysctl", "machdep.xcpm.cpu_thermal_level"],
            capture_output=True,
            timeout=1,
        )
        detected["thermal"] = result.returncode == 0
    except Exception:
        detected["thermal"] = False

    # Metal GPU
    detected["metal"] = _detect_metal()

    # IOKit power
    try:
        result = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            timeout=1,
        )
        detected["power_management"] = result.returncode == 0
    except Exception:
        detected["power_management"] = False

    _hardware_checked = True
    _detected_hardware = detected
    return detected


def _detect_metal() -> bool:
    """Detect Metal GPU support."""
    try:
        import subprocess

        # Use system_profiler to check for GPU
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            timeout=2,
            text=True,
        )

        if result.returncode == 0:
            output = result.stdout.lower()
            # Check for Metal support indicators
            # Apple Silicon (M1/M2/M3) always has Metal
            # Intel Macs with Metal-capable GPUs
            return (
                "metal" in output
                or "apple m" in output
                or "radeon" in output
                or "intel iris" in output
            )
    except Exception:
        pass

    return False


class MacOSHAL:
    """macOS HAL entry point with hardware detection."""

    def __init__(self) -> None:
        """Initialize macOS HAL."""
        self._initialized = False
        self._detected_hardware: dict[str, bool] = {}

    async def initialize(self) -> bool:
        """Initialize and detect available hardware.

        Returns:
            True if running on macOS and some hardware detected
        """
        if not MACOS_AVAILABLE:
            logger.warning("MacOSHAL only available on macOS/Darwin platforms")
            return False

        # Detect hardware
        self._detected_hardware = _check_hardware()

        self._initialized = True
        available_count = sum(self._detected_hardware.values())

        logger.info(f"✅ macOS HAL initialized: {available_count} hardware subsystems available")
        logger.debug(f"Detected hardware: {self._detected_hardware}")

        return available_count > 0

    def get_detected_hardware(self) -> dict[str, bool]:
        """Get dictionary of detected hardware capabilities.

        Returns:
            Dict mapping hardware type to availability
        """
        return self._detected_hardware.copy()

    async def create_audio_adapter(self, config: AudioConfig | None = None) -> MacOSCoreAudio:
        """Create macOS audio adapter.

        Args:
            config: Audio configuration (optional)

        Returns:
            MacOSCoreAudio adapter instance
        """
        from kagami_hal.adapters.macos.audio import MacOSCoreAudio

        adapter = MacOSCoreAudio()
        if config:
            await adapter.initialize(config)
        return adapter

    async def create_sensor_adapter(self) -> MacOSSensors:
        """Create macOS sensor adapter.

        Returns:
            MacOSSensors adapter instance
        """
        from kagami_hal.adapters.macos.sensors import MacOSSensors

        adapter = MacOSSensors()
        await adapter.initialize()
        return adapter

    async def create_display_adapter(self) -> MacOSCoreGraphicsDisplay:
        """Create macOS display adapter.

        Returns:
            MacOSCoreGraphicsDisplay adapter instance
        """
        from kagami_hal.adapters.macos.display import MacOSCoreGraphicsDisplay

        adapter = MacOSCoreGraphicsDisplay()
        await adapter.initialize()
        return adapter

    async def create_input_adapter(self) -> MacOSIOKitInput:
        """Create macOS input adapter.

        Returns:
            MacOSIOKitInput adapter instance
        """
        from kagami_hal.adapters.macos.input import MacOSIOKitInput

        adapter = MacOSIOKitInput()
        await adapter.initialize()
        return adapter

    async def create_power_adapter(self) -> MacOSPower:
        """Create macOS power adapter.

        Returns:
            MacOSPower adapter instance
        """
        from kagami_hal.adapters.macos.power import MacOSPower

        adapter = MacOSPower()
        await adapter.initialize()
        return adapter

    async def shutdown(self) -> None:
        """Shutdown macOS HAL."""
        self._initialized = False
        logger.info("✅ macOS HAL shutdown complete")


__all__ = [
    "MACOS_AVAILABLE",
    "MacOSHAL",
]
