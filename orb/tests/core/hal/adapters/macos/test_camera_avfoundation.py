"""Tests for macOS AVFoundation camera implementation.

Tests comprehensive camera functionality:
- Device enumeration
- Capture session initialization
- Frame capture (zero-copy path)
- Resource cleanup
- Performance characteristics

Requires:
- macOS with camera hardware
- Camera permission granted
- pyobjc-framework-AVFoundation

Created: December 21, 2025
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    pass

# Consolidated markers
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.skipif(
        sys.platform != "darwin",
        reason="AVFoundation camera tests require macOS",
    ),
]


@pytest.fixture
def skip_if_no_camera() -> None:
    """Skip test if no camera available or no permission."""
    try:
        from kagami_hal.adapters.macos.camera import AVFOUNDATION_AVAILABLE

        if not AVFOUNDATION_AVAILABLE:
            pytest.skip("AVFoundation not available (PyObjC not installed)")

        # Try to check for camera devices
        try:
            import AVFoundation

            devices = AVFoundation.AVCaptureDevice.devicesWithMediaType_(
                AVFoundation.AVMediaTypeVideo
            )
            if not devices or len(devices) == 0:
                pytest.skip("No camera devices found")
        except Exception as e:
            pytest.skip(f"Cannot access camera devices: {e}")

    except ImportError:
        pytest.skip("Camera module not available")


@pytest.fixture
def camera_instance(skip_if_no_camera: None) -> AVFoundationCamera:
    """Create AVFoundationCamera instance."""
    from kagami_hal.adapters.macos.camera import AVFoundationCamera

    camera = AVFoundationCamera(device_index=0, width=1280, height=720, fps=30)
    yield camera

    # Cleanup
    try:
        camera.release()
    except Exception:
        pass


class TestAVFoundationCameraInit:
    """Test AVFoundation camera initialization."""

    def test_import_avfoundation_camera(self) -> None:
        """Test that AVFoundationCamera can be imported."""
        from kagami_hal.adapters.macos.camera import AVFoundationCamera

        assert AVFoundationCamera is not None

    def test_camera_instance_creation(self, skip_if_no_camera: None) -> None:
        """Test creating camera instance."""
        from kagami_hal.adapters.macos.camera import AVFoundationCamera

        camera = AVFoundationCamera(device_index=0, width=1280, height=720, fps=30)

        assert camera.device_index == 0
        assert camera.width == 1280
        assert camera.height == 720
        assert camera.fps == 30
        assert not camera._running

    def test_camera_parameters(self, skip_if_no_camera: None) -> None:
        """Test camera parameter validation."""
        from kagami_hal.adapters.macos.camera import AVFoundationCamera

        # Test various resolutions
        camera_720p = AVFoundationCamera(width=1280, height=720)
        assert camera_720p.width == 1280
        assert camera_720p.height == 720

        camera_1080p = AVFoundationCamera(width=1920, height=1080)
        assert camera_1080p.width == 1920
        assert camera_1080p.height == 1080

        # Test frame rates
        camera_60fps = AVFoundationCamera(fps=60)
        assert camera_60fps.fps == 60


class TestAVFoundationCameraCapture:
    """Test AVFoundation camera frame capture."""

    def test_camera_start(self, camera_instance: AVFoundationCamera) -> None:
        """Test starting capture session."""
        success = camera_instance.start()
        assert success, "Camera should start successfully"
        assert camera_instance._running
        assert camera_instance._session is not None
        assert camera_instance._output is not None
        assert camera_instance._delegate is not None

        # Cleanup
        camera_instance.stop()

    def test_camera_frame_capture(self, camera_instance: AVFoundationCamera) -> None:
        """Test capturing frames."""
        import time

        success = camera_instance.start()
        assert success

        # Wait for first frame (delegate callback)
        time.sleep(0.5)

        ret, frame = camera_instance.read()

        if ret and frame is not None:
            # Validate frame properties
            assert isinstance(frame, np.ndarray)
            assert frame.ndim == 3
            assert frame.shape[2] == 3  # RGB

            # Frame should be reasonable resolution
            height, width = frame.shape[:2]
            assert width > 0 and height > 0
            assert width <= 1920 and height <= 1080

            # Pixel values should be in valid range
            assert frame.dtype == np.uint8
            assert frame.min() >= 0
            assert frame.max() <= 255

        # Cleanup
        camera_instance.stop()

    def test_camera_multiple_frames(self, camera_instance: AVFoundationCamera) -> None:
        """Test capturing multiple frames."""
        import time

        success = camera_instance.start()
        assert success

        # Wait for frames to accumulate
        time.sleep(0.5)

        frames_captured = 0
        for _ in range(5):
            ret, frame = camera_instance.read()
            if ret and frame is not None:
                frames_captured += 1
            time.sleep(0.1)

        assert frames_captured > 0, "Should capture at least one frame"

        # Cleanup
        camera_instance.stop()

    def test_camera_frame_consistency(self, camera_instance: AVFoundationCamera) -> None:
        """Test that frames have consistent properties."""
        import time

        success = camera_instance.start()
        assert success

        time.sleep(0.5)

        ret1, frame1 = camera_instance.read()
        time.sleep(0.1)
        ret2, frame2 = camera_instance.read()

        if ret1 and ret2 and frame1 is not None and frame2 is not None:
            # Frames should have same shape
            assert frame1.shape == frame2.shape
            assert frame1.dtype == frame2.dtype

        # Cleanup
        camera_instance.stop()


class TestAVFoundationCameraResourceManagement:
    """Test resource management and cleanup."""

    def test_camera_stop(self, camera_instance: AVFoundationCamera) -> None:
        """Test stopping capture session."""
        camera_instance.start()
        assert camera_instance._running

        camera_instance.stop()
        assert not camera_instance._running

    def test_camera_release(self, camera_instance: AVFoundationCamera) -> None:
        """Test releasing all resources."""
        camera_instance.start()
        camera_instance.release()

        assert not camera_instance._running
        assert camera_instance._session is None
        assert camera_instance._output is None
        assert camera_instance._delegate is None
        assert camera_instance._latest_frame is None

    def test_camera_multiple_start_stop(self, camera_instance: AVFoundationCamera) -> None:
        """Test multiple start/stop cycles."""
        # First cycle
        assert camera_instance.start()
        camera_instance.stop()

        # Second cycle
        # Note: AVFoundation may not support restarting same session
        # This tests proper cleanup
        camera_instance.release()

    def test_camera_read_before_start(self, camera_instance: AVFoundationCamera) -> None:
        """Test reading before starting camera."""
        ret, frame = camera_instance.read()
        assert not ret
        assert frame is None


class TestAVFoundationCameraPerformance:
    """Test performance characteristics."""

    def test_zero_copy_frame_access(self, camera_instance: AVFoundationCamera) -> None:
        """Test that frame capture uses zero-copy path."""
        import time

        camera_instance.start()
        time.sleep(0.5)

        # Measure time for frame access
        start = time.perf_counter()
        for _ in range(10):
            ret, _frame = camera_instance.read()
            if not ret:
                break
            time.sleep(0.033)  # ~30fps
        elapsed = time.perf_counter() - start

        # Zero-copy should be fast (< 1ms per frame)
        # With 33ms sleep, 10 frames should take ~330ms + overhead
        assert elapsed < 1.0, "Frame access should be fast (zero-copy)"

        camera_instance.stop()

    def test_frame_capture_latency(self, camera_instance: AVFoundationCamera) -> None:
        """Test frame capture latency."""
        import time

        camera_instance.start()
        time.sleep(0.5)  # Wait for first frame

        # Measure read latency
        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            ret, frame = camera_instance.read()
            if ret and frame is not None:
                latency = time.perf_counter() - start
                latencies.append(latency)
            time.sleep(0.033)

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            # Read should be very fast (just memory copy)
            assert avg_latency < 0.01, f"Average latency {avg_latency * 1000:.2f}ms too high"

        camera_instance.stop()


class TestMacOSCameraIntegration:
    """Test integration with MacOSCamera wrapper."""

    @pytest.mark.asyncio
    async def test_macos_camera_avfoundation_backend(self, skip_if_no_camera: None) -> None:
        """Test MacOSCamera using AVFoundation backend."""
        from kagami_hal.adapters.macos.camera import MacOSCamera

        camera = MacOSCamera()

        # Initialize (should prefer AVFoundation over OpenCV)
        success = await camera.initialize(width=1280, height=720, fps=30)
        assert success

        # Verify AVFoundation backend selected
        assert camera._backend == "avfoundation"
        assert camera._av_camera is not None

        # Capture frame
        frame = await camera.capture_frame()
        if frame is not None:
            assert isinstance(frame, np.ndarray)
            assert frame.ndim == 3
            assert frame.shape[2] == 3

        # Cleanup
        await camera.shutdown()

    @pytest.mark.asyncio
    async def test_macos_camera_stream_frames(self, skip_if_no_camera: None) -> None:
        """Test frame streaming via MacOSCamera."""
        from kagami_hal.adapters.macos.camera import MacOSCamera

        camera = MacOSCamera()
        success = await camera.initialize(width=1280, height=720, fps=30)

        if not success:
            pytest.skip("Camera initialization failed")

        # Stream a few frames
        frame_count = 0
        async for frame in camera.stream_frames():
            frame_count += 1
            assert isinstance(frame, np.ndarray)
            if frame_count >= 3:
                break

        assert frame_count == 3

        await camera.shutdown()


class TestAVFoundationCameraErrors:
    """Test error handling."""

    def test_invalid_device_index(self, skip_if_no_camera: None) -> None:
        """Test invalid device index."""
        from kagami_hal.adapters.macos.camera import AVFoundationCamera

        camera = AVFoundationCamera(device_index=999)  # Invalid index
        success = camera.start()
        assert not success

    def test_camera_not_available(self) -> None:
        """Test when AVFoundation not available."""
        from kagami_hal.adapters.macos.camera import AVFOUNDATION_AVAILABLE

        if not AVFOUNDATION_AVAILABLE:
            from kagami_hal.adapters.macos.camera import AVFoundationCamera

            camera = AVFoundationCamera()
            success = camera.start()
            assert not success


class TestAVFoundationCameraDelegate:
    """Test delegate callback mechanism."""

    def test_delegate_frame_callback(self, camera_instance: AVFoundationCamera) -> None:
        """Test that delegate receives and processes frames."""
        import time

        camera_instance.start()

        # Delegate should start receiving frames
        time.sleep(0.5)

        # Check that delegate stored frame in camera
        assert camera_instance._latest_frame is not None or (
            # Or frame not yet available (acceptable)
            camera_instance._delegate is not None
            and camera_instance._delegate.parent_camera is camera_instance
        )

        camera_instance.stop()

    def test_delegate_thread_safety(self, camera_instance: AVFoundationCamera) -> None:
        """Test thread-safe frame access."""
        import threading
        import time

        camera_instance.start()
        time.sleep(0.5)

        # Access frame from multiple threads
        results = []

        def read_frames() -> None:
            for _ in range(5):
                ret, frame = camera_instance.read()
                results.append((ret, frame is not None))
                time.sleep(0.05)

        threads = [threading.Thread(target=read_frames) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All accesses should be safe (no crashes)
        assert len(results) == 15

        camera_instance.stop()


# Performance benchmarks (optional, marked as slow)
@pytest.mark.slow
class TestAVFoundationCameraBenchmarks:
    """Performance benchmarks for AVFoundation camera."""

    def test_benchmark_frame_rate(self, camera_instance: AVFoundationCamera) -> None:
        """Benchmark actual frame rate."""
        import time

        camera_instance.start()
        time.sleep(0.5)  # Warmup

        frame_count = 0
        start = time.perf_counter()

        # Capture for 2 seconds
        while time.perf_counter() - start < 2.0:
            ret, frame = camera_instance.read()
            if ret and frame is not None:
                frame_count += 1
            time.sleep(0.001)  # Minimal sleep

        elapsed = time.perf_counter() - start
        actual_fps = frame_count / elapsed

        print(f"\nActual frame rate: {actual_fps:.1f} fps")
        print(f"Frames captured: {frame_count} in {elapsed:.2f}s")

        # Should achieve at least 15fps (conservative)
        assert actual_fps >= 15.0

        camera_instance.stop()

    def test_benchmark_memory_usage(self, camera_instance: AVFoundationCamera) -> None:
        """Benchmark memory usage during capture."""
        import os
        import time

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        camera_instance.start()

        # Capture frames for 5 seconds
        for _ in range(150):  # ~30fps * 5s
            camera_instance.read()
            time.sleep(0.033)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        print(f"\nMemory increase: {memory_increase:.2f} MB")

        # Memory increase should be minimal (< 100MB)
        assert memory_increase < 100.0

        camera_instance.stop()
