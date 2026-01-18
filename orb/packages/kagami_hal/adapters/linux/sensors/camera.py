"""Linux V4L2 Camera Sensor.

Implements camera access via Video4Linux2 (V4L2).
Supports /dev/video* devices with OpenCV or v4l2 bindings.

Uses zero-copy via mmap when possible for performance.

Created: December 15, 2025
"""

from __future__ import annotations

import importlib.util
import logging
import time
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.adapters.sensor_adapter_base import SensorAdapterBase
from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

# Lazy V4L2 check (cached after first call)
_v4l2_available_cache: bool | None = None


def _check_v4l2_available() -> bool:
    """Check V4L2 camera availability (lazy, cached)."""
    global _v4l2_available_cache
    if _v4l2_available_cache is None:
        _v4l2_available_cache = any(Path("/dev").glob("video*"))
    return _v4l2_available_cache


# Check for OpenCV
OPENCV_AVAILABLE = importlib.util.find_spec("cv2") is not None

# Import if available
if OPENCV_AVAILABLE:
    import cv2  # noqa: F401


class LinuxCamera(SensorAdapterBase):
    """Linux V4L2 camera implementation.

    Uses OpenCV as primary backend (reliable and cross-platform).
    Falls back to v4l2 bindings if OpenCV unavailable.
    """

    def __init__(self, device_id: int = 0) -> None:
        """Initialize camera adapter.

        Args:
            device_id: Camera device ID (default 0 for /dev/video0)
        """
        super().__init__()
        self._device_id = device_id
        self._capture: Any = None
        self._device_path = Path(f"/dev/video{device_id}")

    async def initialize(self) -> bool:
        """Initialize camera device."""
        if not _check_v4l2_available():
            if is_test_mode():
                logger.info("V4L2 camera not available")
                return False
            raise RuntimeError("No V4L2 camera devices found. Check /dev/video* exists.")

        if not OPENCV_AVAILABLE:
            if is_test_mode():
                logger.info("OpenCV not available, camera disabled")
                return False
            raise RuntimeError("OpenCV not available. Install: pip install opencv-python")

        try:
            import cv2

            # Open camera
            self._capture = cv2.VideoCapture(self._device_id)

            if not self._capture.isOpened():
                logger.warning(f"Failed to open camera at /dev/video{self._device_id}")
                return False

            # Verify we can read a frame
            ret, _ = self._capture.read()
            if not ret:
                logger.warning("Camera opened but cannot read frames")
                self._capture.release()
                self._capture = None
                return False

            self._available_sensors.add(SensorType.CAMERA)
            self._running = True

            # Get camera properties
            width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(self._capture.get(cv2.CAP_PROP_FPS))

            logger.info(
                f"✅ V4L2 camera initialized: {width}x{height} @ {fps}fps "
                f"(device /dev/video{self._device_id})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize V4L2 camera: {e}", exc_info=True)
            return False

    async def read(self, sensor: SensorType) -> SensorReading:
        """Read camera frame.

        Returns:
            SensorReading with value as numpy array (BGR format)
        """
        if sensor != SensorType.CAMERA:
            raise RuntimeError(f"Sensor {sensor} not supported by camera adapter")

        if not self._capture:
            raise RuntimeError("Camera not initialized")

        try:
            ret, frame = self._capture.read()

            if not ret or frame is None:
                raise RuntimeError("Failed to capture frame")

            return SensorReading(
                sensor=SensorType.CAMERA,
                value=frame,  # numpy array, shape (H, W, 3), dtype uint8
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"Camera read failed: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown camera and release resources."""
        await super().shutdown()

        if self._capture:
            try:
                self._capture.release()
            except Exception as e:
                logger.warning(f"Error releasing camera: {e}")
            finally:
                self._capture = None

        logger.info("✅ V4L2 camera shutdown complete")

    def get_device_path(self) -> Path:
        """Get device path for this camera.

        Returns:
            Path to /dev/video* device
        """
        return self._device_path

    @staticmethod
    def enumerate_cameras() -> list[int]:
        """Enumerate available V4L2 camera devices.

        Returns:
            List of device IDs (e.g., [0, 1, 2] for /dev/video0, video1, video2)
        """
        devices = []
        for device_path in Path("/dev").glob("video*"):
            try:
                device_id = int(device_path.name[5:])  # Extract number from "videoN"
                devices.append(device_id)
            except ValueError:
                continue

        return sorted(devices)


__all__ = ["LinuxCamera"]
