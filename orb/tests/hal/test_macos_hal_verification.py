from __future__ import annotations

import pytest

#!/usr/bin/env python3
"""Comprehensive macOS HAL Verification Test Suite.

Tests all aspects of the macOS HAL implementation:
- Functional correctness
- Performance benchmarks
- Error handling
- Security validation
- Integration with SafeHAL
- Platform compatibility

Created: December 15, 2025 by Crystal (e₇)
"""


import asyncio
import platform
import sys
import time
from typing import Any

# Skip all tests if not on macOS
pytestmark = [
    pytest.mark.skipif(sys.platform != "darwin", reason="macOS only"),
    pytest.mark.tier_integration,
]


class TestMacOSHAL:
    """Test MacOSHAL platform detection and initialization."""

    @pytest.mark.asyncio
    async def test_hal_initialization(self):
        """Test MacOSHAL initialization."""
        from kagami_hal.adapters.macos import MacOSHAL

        hal = MacOSHAL()
        success = await hal.initialize()

        assert success is True, "MacOSHAL should initialize on macOS"
        assert hal._initialized is True

        hardware = hal.get_detected_hardware()
        assert isinstance(hardware, dict)
        assert len(hardware) > 0, "Should detect at least some hardware"

        await hal.shutdown()

    def test_hardware_detection_cached(self) -> None:
        """Test hardware detection is cached."""
        import kagami_hal.adapters.macos as macos_module
        from kagami_hal.adapters.macos import _check_hardware

        # First call
        hw1 = _check_hardware()
        assert macos_module._hardware_checked is True

        # Second call should return cached
        hw2 = _check_hardware()
        assert hw1 == hw2


class TestComputeCapabilities:
    """Test compute capabilities detection."""

    @pytest.mark.asyncio
    async def test_compute_detection(self):
        """Test compute capabilities detection."""
        from kagami_hal.adapters.macos.compute import MacOSComputeDetector

        detector = MacOSComputeDetector()
        caps = await detector.detect()

        # Validate CPU detection
        assert caps.cpu_arch in ("arm64", "x86_64"), "Should detect valid CPU architecture"
        assert len(caps.cpu_name) > 0, "Should detect CPU name"
        assert caps.cpu_cores_physical > 0, "Should detect physical cores"
        assert caps.cpu_cores_logical >= caps.cpu_cores_physical

        # Validate memory detection
        assert caps.memory_gb > 0, "Should detect system memory"

        # Validate OS version
        assert len(caps.os_version) > 0, "Should detect macOS version"

        # Apple Silicon specific checks
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            assert caps.is_apple_silicon is True
            assert caps.has_metal is True, "Apple Silicon should always have Metal"
            assert caps.gpu_name is not None, "Should detect GPU name"
        else:
            assert caps.is_apple_silicon is False

    @pytest.mark.asyncio
    async def test_optimal_device_selection(self):
        """Test optimal device selection."""
        from kagami_hal.adapters.macos.compute import MacOSComputeDetector

        detector = MacOSComputeDetector()
        await detector.detect()

        device = detector.get_optimal_device()
        assert device in ("mps", "cpu", "cuda")

        # Apple Silicon should prefer MPS if available
        if detector.is_apple_silicon():
            # May be "mps" if PyTorch is installed, else "cpu"
            assert device in ("mps", "cpu")

    @pytest.mark.asyncio
    async def test_metal_detection(self):
        """Test Metal GPU detection."""
        from kagami_hal.adapters.macos.compute import MacOSComputeDetector

        detector = MacOSComputeDetector()
        caps = await detector.detect()

        # All modern Macs should have Metal
        assert caps.has_metal is True, "Modern macOS should support Metal"

        if caps.gpu_name:
            assert len(caps.gpu_name) > 0

    def test_compute_performance_benchmark(self) -> None:
        """Benchmark compute detection performance."""
        from kagami_hal.adapters.macos.compute import MacOSComputeDetector

        start = time.perf_counter()

        async def detect():
            detector = MacOSComputeDetector()
            await detector.detect()

        asyncio.run(detect())

        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"Compute detection took {elapsed:.2f}s (should be < 5s)"


class TestThermalSensors:
    """Test thermal sensor implementation."""

    @pytest.mark.asyncio
    async def test_thermal_initialization(self):
        """Test thermal sensor initialization."""
        from kagami_hal.adapters.macos.thermal import MacOSThermal

        thermal = MacOSThermal()
        success = await thermal.initialize()

        # Thermal sensors may not be available on all Macs
        # This is not a failure, just a platform limitation
        if success:
            level = await thermal.read_cpu_thermal_level()
            assert isinstance(level, int)
            assert 0 <= level <= 100, f"Thermal level {level} outside valid range"

            temp = await thermal.read_cpu_temperature()
            assert isinstance(temp, float)
            assert 20.0 <= temp <= 120.0, f"Temperature {temp}°C seems unrealistic"

            await thermal.shutdown()
        else:
            # Expected on some Macs (especially M-series)
            pytest.skip("Thermal sensors not available on this Mac")

    @pytest.mark.asyncio
    async def test_thermal_sensor_reading(self):
        """Test thermal sensor HAL interface."""
        from kagami_hal.adapters.macos.thermal import MacOSThermal

        thermal = MacOSThermal()
        success = await thermal.initialize()

        if success:
            reading = await thermal.read_sensor()
            assert reading.value >= 0
            assert 0.0 <= reading.accuracy <= 1.0
            assert reading.timestamp_ms > 0

            await thermal.shutdown()
        else:
            pytest.skip("Thermal sensors not available")


class TestCameraSensor:
    """Test camera sensor implementation."""

    @pytest.mark.asyncio
    async def test_camera_initialization_graceful_failure(self):
        """Test camera initialization fails gracefully without permissions."""
        from kagami_hal.adapters.macos.camera import MacOSCamera

        camera = MacOSCamera()

        # May fail due to:
        # 1. No camera permission
        # 2. No camera hardware
        # 3. Camera in use
        success = await camera.initialize()

        # Either succeeds or fails gracefully (no exceptions)
        if success:
            assert camera._initialized is True
            assert camera._backend in ("opencv", "avfoundation")

            resolution = camera.get_resolution()
            assert len(resolution) == 2
            assert resolution[0] > 0 and resolution[1] > 0

            fps = camera.get_fps()
            assert fps > 0

            await camera.shutdown()
        else:
            # Expected when permission not granted or no camera
            assert camera._initialized is False

    @pytest.mark.asyncio
    @pytest.mark.manual
    @pytest.mark.skip(reason="Requires camera permission - run with: pytest -m manual")
    async def test_camera_frame_capture(self):
        """Test camera frame capture (requires permission)."""
        from kagami_hal.adapters.macos.camera import MacOSCamera

        camera = MacOSCamera()
        success = await camera.initialize(width=1920, height=1080, fps=30)

        if not success:
            pytest.skip("Camera not available")

        # Capture single frame
        frame = await camera.capture_frame()
        assert frame is not None, "Should capture frame"
        assert frame.shape[2] == 3, "Frame should be RGB (3 channels)"
        assert frame.dtype.name.startswith("uint"), "Frame should be unsigned int"

        await camera.shutdown()

    def test_camera_backend_detection(self) -> None:
        """Test camera backend availability detection."""
        from kagami_hal.adapters.macos.camera import (
            AVFOUNDATION_AVAILABLE,
            CV2_AVAILABLE,
        )

        # At least one backend should be available
        assert CV2_AVAILABLE or AVFOUNDATION_AVAILABLE, "No camera backend available"


class TestMicrophoneSensor:
    """Test microphone sensor implementation."""

    @pytest.mark.asyncio
    async def test_microphone_initialization_graceful_failure(self):
        """Test microphone initialization fails gracefully without dependencies."""
        from kagami_hal.adapters.macos.microphone import MacOSMicrophone

        mic = MacOSMicrophone()

        # May fail due to:
        # 1. No microphone permission
        # 2. Missing dependencies (PyAudio, sounddevice)
        # 3. No microphone hardware
        success = await mic.initialize()

        if success:
            assert mic._initialized is True
            assert mic._backend in ("pyaudio", "sounddevice")

            config = mic.get_config()
            assert config["sample_rate"] > 0
            assert config["channels"] > 0
            assert config["chunk_size"] > 0

            await mic.shutdown()
        else:
            # Expected without PyAudio or sounddevice
            assert mic._initialized is False

    @pytest.mark.asyncio
    @pytest.mark.manual
    @pytest.mark.skip(reason="Requires audio dependencies - run with: pytest -m manual")
    async def test_microphone_record_chunk(self):
        """Test microphone recording (requires dependencies)."""
        from kagami_hal.adapters.macos.microphone import MacOSMicrophone

        mic = MacOSMicrophone()
        success = await mic.initialize(sample_rate=48000, channels=1, chunk_size=1024)

        if not success:
            pytest.skip("Microphone not available")

        # Record single chunk
        chunk = await mic.record_chunk()
        assert chunk is not None
        assert chunk.shape[0] == 1024
        assert chunk.dtype.name == "float32"

        # Check audio is in valid range [-1.0, 1.0]
        assert chunk.min() >= -1.0
        assert chunk.max() <= 1.0

        await mic.shutdown()

    def test_microphone_backend_detection(self) -> None:
        """Test microphone backend availability detection."""
        from kagami_hal.adapters.macos.microphone import (
            PYAUDIO_AVAILABLE,
            SOUNDDEVICE_AVAILABLE,
        )

        # Either both are unavailable (expected in CI), or at least one is available
        # This is informational, not a failure
        if not (PYAUDIO_AVAILABLE or SOUNDDEVICE_AVAILABLE):
            pytest.skip("No audio backend installed (PyAudio or sounddevice)")


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_camera_capture_without_initialization(self):
        """Test camera capture fails properly without initialization."""
        from kagami_hal.adapters.macos.camera import MacOSCamera

        camera = MacOSCamera()

        with pytest.raises(RuntimeError, match="not initialized"):
            await camera.capture_frame()

    @pytest.mark.asyncio
    async def test_microphone_record_without_initialization(self):
        """Test microphone recording fails properly without initialization."""
        from kagami_hal.adapters.macos.microphone import MacOSMicrophone

        mic = MacOSMicrophone()

        with pytest.raises(RuntimeError, match="not initialized"):
            await mic.record_chunk()

    @pytest.mark.asyncio
    async def test_microphone_stream_without_initialization(self):
        """Test microphone streaming fails properly without initialization."""
        from kagami_hal.adapters.macos.microphone import MacOSMicrophone

        mic = MacOSMicrophone()

        # Should fail with "not streaming" error
        with pytest.raises(RuntimeError, match="not streaming"):
            async for _chunk in mic.stream_audio():
                pass

    @pytest.mark.asyncio
    async def test_thermal_read_without_initialization(self):
        """Test thermal sensor fails properly without initialization."""
        from kagami_hal.adapters.macos.thermal import MacOSThermal

        thermal = MacOSThermal()

        with pytest.raises(RuntimeError):
            await thermal.read_cpu_thermal_level()


class TestSecurity:
    """Security validation tests."""

    def test_no_shell_injection_in_sysctl(self) -> None:
        """Test sysctl calls are safe from shell injection."""
        # Check that we're not using shell=True in subprocess calls
        import inspect

        from kagami_hal.adapters.macos.thermal import MacOSThermal

        source = inspect.getsource(MacOSThermal)

        # Should not use shell=True anywhere
        assert "shell=True" not in source, "Shell=True is a security risk"

    def test_no_arbitrary_command_execution(self) -> None:
        """Test compute detection doesn't allow arbitrary command execution."""
        import inspect

        from kagami_hal.adapters.macos.compute import MacOSComputeDetector

        source = inspect.getsource(MacOSComputeDetector)

        # Check no eval/exec usage
        assert "eval(" not in source, "eval() is a security risk"
        assert "exec(" not in source, "exec() is a security risk"
        assert "__import__" not in source, "Dynamic imports are risky"

    def test_subprocess_timeout_enforced(self) -> None:
        """Test all subprocess calls have timeouts."""
        import inspect

        from kagami_hal.adapters.macos import compute, thermal

        for module in [compute, thermal]:
            source = inspect.getsource(module)
            # Count subprocess.run calls
            import re

            calls = re.findall(r"subprocess\.run\([^)]+\)", source)

            for call in calls:
                # Each call should have a timeout parameter
                assert "timeout=" in call, f"subprocess.run missing timeout: {call}"


class TestPerformance:
    """Performance benchmark tests."""

    def test_camera_initialization_performance(self) -> None:
        """Benchmark camera initialization time."""
        from kagami_hal.adapters.macos.camera import MacOSCamera

        start = time.perf_counter()

        async def init():
            camera = MacOSCamera()
            await camera.initialize()
            await camera.shutdown()

        asyncio.run(init())

        elapsed = time.perf_counter() - start
        # Should be fast even if it fails
        assert elapsed < 5.0, f"Camera init took {elapsed:.2f}s (should be < 5s)"

    def test_thermal_read_performance(self) -> None:
        """Benchmark thermal sensor read time."""
        from kagami_hal.adapters.macos.thermal import MacOSThermal

        async def read():
            thermal = MacOSThermal()
            success = await thermal.initialize()
            if success:
                start = time.perf_counter()
                await thermal.read_cpu_thermal_level()
                elapsed = time.perf_counter() - start
                await thermal.shutdown()
                return elapsed
            return 0.0

        elapsed = asyncio.run(read())

        if elapsed > 0:
            assert elapsed < 1.0, f"Thermal read took {elapsed:.2f}s (should be < 1s)"


class TestPlatformCompatibility:
    """Platform-specific compatibility tests."""

    def test_apple_silicon_detection(self) -> None:
        """Test Apple Silicon detection accuracy."""
        from kagami_hal.adapters.macos.compute import MacOSComputeDetector

        detector = MacOSComputeDetector()
        is_arm = detector.is_apple_silicon()

        # Verify against platform.machine()
        machine = platform.machine().lower()
        expected = machine in ("arm64", "aarch64")

        assert is_arm == expected, "Apple Silicon detection mismatch"

    @pytest.mark.asyncio
    async def test_macos_version_detection(self):
        """Test macOS version is detected correctly."""
        from kagami_hal.adapters.macos.compute import MacOSComputeDetector

        detector = MacOSComputeDetector()
        caps = await detector.detect()

        # Verify version format
        version_parts = caps.os_version.split(".")
        assert len(version_parts) >= 2, "Version should be major.minor at minimum"

        major = int(version_parts[0])
        assert major >= 10, f"macOS version {major} seems invalid"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
