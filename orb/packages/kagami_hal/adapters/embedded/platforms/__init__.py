"""Embedded platform detection and HAL initialization.

Supports:
- Raspberry Pi (3, 4, 5)
- NVIDIA Jetson (Nano, Xavier, Orin)
- Generic ARM64 devices

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EmbeddedPlatform(Enum):
    """Supported embedded platforms."""

    RASPBERRY_PI_3 = "rpi3"
    RASPBERRY_PI_4 = "rpi4"
    RASPBERRY_PI_5 = "rpi5"
    JETSON_NANO = "jetson_nano"
    JETSON_XAVIER = "jetson_xavier"
    JETSON_ORIN = "jetson_orin"
    GENERIC_ARM64 = "arm64_generic"
    UNKNOWN = "unknown"


@dataclass
class ComputeCapabilities:
    """Platform compute capabilities."""

    # CPU
    cpu_cores: int
    cpu_freq_mhz: int
    cpu_arch: str  # armv7l, aarch64

    # GPU
    has_gpu: bool
    gpu_type: str  # VideoCore, CUDA, Mali, etc.
    gpu_compute_units: int

    # Accelerators
    has_npu: bool
    has_vulkan: bool
    has_opencl: bool
    has_cuda: bool

    # Memory
    ram_mb: int
    gpu_ram_mb: int

    # Power
    tdp_watts: float  # Thermal design power


@dataclass
class PlatformFeatures:
    """Platform hardware features."""

    # I/O
    gpio_available: bool
    i2c_buses: list[int]
    spi_buses: list[int]
    uart_ports: list[str]

    # Video
    camera_support: str  # libcamera, v4l2, nvarguscamerasrc
    display_support: str  # framebuffer, spi, hdmi

    # Power
    battery_support: bool
    thermal_zones: list[str]


class EmbeddedHAL:
    """Embedded HAL entry point with platform detection."""

    def __init__(self) -> None:
        """Initialize HAL with automatic platform detection."""
        self._platform = EmbeddedPlatform.UNKNOWN
        self._compute_caps: ComputeCapabilities | None = None
        self._features: PlatformFeatures | None = None

    def detect_platform(self) -> EmbeddedPlatform:
        """Detect current embedded platform.

        Returns:
            Detected platform type
        """
        # Check for Raspberry Pi
        if Path("/proc/device-tree/model").exists():
            model = Path("/proc/device-tree/model").read_text().strip().lower()
            if "raspberry pi" in model:
                if "pi 5" in model:
                    self._platform = EmbeddedPlatform.RASPBERRY_PI_5
                elif "pi 4" in model:
                    self._platform = EmbeddedPlatform.RASPBERRY_PI_4
                elif "pi 3" in model:
                    self._platform = EmbeddedPlatform.RASPBERRY_PI_3
                logger.info(f"Detected platform: {self._platform.value}")
                return self._platform

        # Check for Jetson
        jetson_release = Path("/etc/nv_tegra_release")
        if jetson_release.exists():
            release_text = jetson_release.read_text().lower()
            if "orin" in release_text:
                self._platform = EmbeddedPlatform.JETSON_ORIN
            elif "xavier" in release_text:
                self._platform = EmbeddedPlatform.JETSON_XAVIER
            elif "nano" in release_text:
                self._platform = EmbeddedPlatform.JETSON_NANO
            logger.info(f"Detected platform: {self._platform.value}")
            return self._platform

        # Generic ARM64
        machine = platform.machine().lower()
        if machine in ("aarch64", "arm64", "armv8"):
            self._platform = EmbeddedPlatform.GENERIC_ARM64
            logger.info("Detected generic ARM64 platform")
            return self._platform

        logger.warning(f"Unknown embedded platform: {machine}")
        self._platform = EmbeddedPlatform.UNKNOWN
        return self._platform

    def get_compute_capabilities(self) -> ComputeCapabilities:
        """Get platform compute capabilities.

        Returns:
            ComputeCapabilities for current platform
        """
        if self._compute_caps:
            return self._compute_caps

        if self._platform == EmbeddedPlatform.UNKNOWN:
            self.detect_platform()

        # Default capabilities
        cpu_cores = self._get_cpu_cores()
        cpu_freq = self._get_cpu_freq()
        cpu_arch = platform.machine()
        ram_mb = self._get_ram_mb()

        # Platform-specific capabilities
        if self._platform == EmbeddedPlatform.RASPBERRY_PI_5:
            self._compute_caps = ComputeCapabilities(
                cpu_cores=4,
                cpu_freq_mhz=2400,
                cpu_arch="aarch64",
                has_gpu=True,
                gpu_type="VideoCore VII",
                gpu_compute_units=16,
                has_npu=False,
                has_vulkan=True,
                has_opencl=True,
                has_cuda=False,
                ram_mb=ram_mb,
                gpu_ram_mb=512,  # Shared
                tdp_watts=5.0,
            )

        elif self._platform == EmbeddedPlatform.RASPBERRY_PI_4:
            self._compute_caps = ComputeCapabilities(
                cpu_cores=4,
                cpu_freq_mhz=1800,
                cpu_arch="aarch64",
                has_gpu=True,
                gpu_type="VideoCore VI",
                gpu_compute_units=32,
                has_npu=False,
                has_vulkan=True,
                has_opencl=True,
                has_cuda=False,
                ram_mb=ram_mb,
                gpu_ram_mb=512,
                tdp_watts=5.1,
            )

        elif self._platform == EmbeddedPlatform.RASPBERRY_PI_3:
            self._compute_caps = ComputeCapabilities(
                cpu_cores=4,
                cpu_freq_mhz=1400,
                cpu_arch="armv7l",
                has_gpu=True,
                gpu_type="VideoCore IV",
                gpu_compute_units=12,
                has_npu=False,
                has_vulkan=False,
                has_opencl=True,
                has_cuda=False,
                ram_mb=min(ram_mb, 1024),
                gpu_ram_mb=256,
                tdp_watts=4.0,
            )

        elif self._platform == EmbeddedPlatform.JETSON_ORIN:
            self._compute_caps = ComputeCapabilities(
                cpu_cores=12,
                cpu_freq_mhz=2000,
                cpu_arch="aarch64",
                has_gpu=True,
                gpu_type="NVIDIA Ampere",
                gpu_compute_units=2048,
                has_npu=True,  # DLA
                has_vulkan=True,
                has_opencl=True,
                has_cuda=True,
                ram_mb=ram_mb,
                gpu_ram_mb=8192,  # Shared with system
                tdp_watts=15.0,
            )

        elif self._platform == EmbeddedPlatform.JETSON_XAVIER:
            self._compute_caps = ComputeCapabilities(
                cpu_cores=8,
                cpu_freq_mhz=2260,
                cpu_arch="aarch64",
                has_gpu=True,
                gpu_type="NVIDIA Volta",
                gpu_compute_units=512,
                has_npu=True,  # DLA
                has_vulkan=True,
                has_opencl=True,
                has_cuda=True,
                ram_mb=ram_mb,
                gpu_ram_mb=4096,
                tdp_watts=10.0,
            )

        elif self._platform == EmbeddedPlatform.JETSON_NANO:
            self._compute_caps = ComputeCapabilities(
                cpu_cores=4,
                cpu_freq_mhz=1430,
                cpu_arch="aarch64",
                has_gpu=True,
                gpu_type="NVIDIA Maxwell",
                gpu_compute_units=128,
                has_npu=False,
                has_vulkan=True,
                has_opencl=True,
                has_cuda=True,
                ram_mb=min(ram_mb, 4096),
                gpu_ram_mb=2048,
                tdp_watts=5.0,
            )

        else:
            # Generic ARM64
            self._compute_caps = ComputeCapabilities(
                cpu_cores=cpu_cores,
                cpu_freq_mhz=cpu_freq,
                cpu_arch=cpu_arch,
                has_gpu=False,
                gpu_type="unknown",
                gpu_compute_units=0,
                has_npu=False,
                has_vulkan=False,
                has_opencl=False,
                has_cuda=False,
                ram_mb=ram_mb,
                gpu_ram_mb=0,
                tdp_watts=10.0,
            )

        return self._compute_caps

    def get_platform_features(self) -> PlatformFeatures:
        """Get platform hardware features.

        Returns:
            PlatformFeatures for current platform
        """
        if self._features:
            return self._features

        if self._platform == EmbeddedPlatform.UNKNOWN:
            self.detect_platform()

        # Detect I2C buses
        i2c_buses = []
        for i2c_path in Path("/dev").glob("i2c-*"):
            try:
                bus_num = int(i2c_path.name.split("-")[1])
                i2c_buses.append(bus_num)
            except (IndexError, ValueError):
                pass

        # Detect SPI buses
        spi_buses = []
        for spi_path in Path("/dev").glob("spidev*"):
            try:
                bus_num = int(spi_path.name.replace("spidev", "").split(".")[0])
                if bus_num not in spi_buses:
                    spi_buses.append(bus_num)
            except (IndexError, ValueError):
                pass

        # Detect UART ports
        uart_ports = []
        for uart_path in Path("/dev").glob("tty[AS]*"):
            uart_ports.append(str(uart_path))

        # GPIO availability
        gpio_available = Path("/sys/class/gpio").exists()

        # Platform-specific features
        if "RASPBERRY_PI" in self._platform.name:
            camera_support = "libcamera"  # Pi Camera via libcamera
            display_support = "hdmi"  # Primary HDMI, also supports SPI displays
            battery_support = False  # Desktop board
        elif "JETSON" in self._platform.name:
            camera_support = "nvarguscamerasrc"  # NVIDIA Argus for CSI
            display_support = "hdmi"
            battery_support = False
        else:
            camera_support = "v4l2"
            display_support = "framebuffer"
            battery_support = False

        # Thermal zones
        thermal_zones = []
        thermal_path = Path("/sys/class/thermal")
        if thermal_path.exists():
            for zone in thermal_path.glob("thermal_zone*"):
                thermal_zones.append(zone.name)

        self._features = PlatformFeatures(
            gpio_available=gpio_available,
            i2c_buses=sorted(i2c_buses),
            spi_buses=sorted(spi_buses),
            uart_ports=uart_ports,
            camera_support=camera_support,
            display_support=display_support,
            battery_support=battery_support,
            thermal_zones=thermal_zones,
        )

        return self._features

    def parse_device_tree(self) -> dict[str, Any]:
        """Parse device tree for hardware information.

        Returns:
            Dict of device tree properties
        """
        dt_base = Path("/proc/device-tree")
        if not dt_base.exists():
            return {}

        dt_info: dict[str, Any] = {}

        # Model
        model_file = dt_base / "model"
        if model_file.exists():
            dt_info["model"] = model_file.read_text().strip()

        # Serial
        serial_file = dt_base / "serial-number"
        if serial_file.exists():
            dt_info["serial"] = serial_file.read_text().strip()

        # Compatible
        compatible_file = dt_base / "compatible"
        if compatible_file.exists():
            dt_info["compatible"] = compatible_file.read_bytes().decode().split("\x00")

        return dt_info

    def _get_cpu_cores(self) -> int:
        """Get CPU core count."""
        try:
            import os

            return os.cpu_count() or 4
        except Exception:
            return 4

    def _get_cpu_freq(self) -> int:
        """Get max CPU frequency in MHz."""
        try:
            freq_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")
            if freq_path.exists():
                return int(freq_path.read_text().strip()) // 1000
        except Exception:
            pass
        return 1000

    def _get_ram_mb(self) -> int:
        """Get total RAM in MB."""
        try:
            meminfo = Path("/proc/meminfo").read_text()
            for line in meminfo.splitlines():
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb // 1024
        except Exception:
            pass
        return 1024


__all__ = [
    "ComputeCapabilities",
    "EmbeddedHAL",
    "EmbeddedPlatform",
    "PlatformFeatures",
]
