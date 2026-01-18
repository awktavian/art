"""Windows DirectShow Camera Sensor.

Implements camera capture using OpenCV with DirectShow backend.

DirectShow is the native Windows camera API, supported by OpenCV
via VideoCapture with CAP_DSHOW backend.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

WINDOWS_AVAILABLE = sys.platform == "win32"
OPENCV_AVAILABLE = False

if WINDOWS_AVAILABLE:
    try:
        import cv2

        OPENCV_AVAILABLE = True
    except ImportError:
        logger.warning("OpenCV not available - install: pip install opencv-python")


class WindowsDirectShowCamera:
    """Windows DirectShow camera implementation.

    Uses OpenCV with CAP_DSHOW backend for reliable DirectShow access.
    """

    def __init__(self, device_index: int = 0):
        """Initialize DirectShow camera.

        Args:
            device_index: Camera device index (0 = default camera)
        """
        self._device_index = device_index
        self._capture: Any | None = None
        self._width = 640
        self._height = 480
        self._fps = 30

    async def initialize(self, config: dict[str, Any] | None = None) -> bool:
        """Initialize camera with DirectShow backend.

        Args:
            config: Optional config with width, height, fps

        Returns:
            True if initialization successful
        """
        if not WINDOWS_AVAILABLE:
            if is_test_mode():
                logger.info(
                    "Windows DirectShow camera not available (wrong platform), gracefully degrading"
                )
                return False
            raise RuntimeError("Windows DirectShow camera only available on Windows")

        if not OPENCV_AVAILABLE:
            if is_test_mode():
                logger.info("OpenCV not available, gracefully degrading")
                return False
            raise RuntimeError("OpenCV not available. Install: pip install opencv-python")

        try:
            # Parse config
            if config:
                self._width = config.get("width", 640)
                self._height = config.get("height", 480)
                self._fps = config.get("fps", 30)

            # Open camera with DirectShow backend
            self._capture = cv2.VideoCapture(self._device_index, cv2.CAP_DSHOW)

            if not self._capture.isOpened():
                logger.error(f"Failed to open DirectShow camera {self._device_index}")
                return False

            # Configure camera
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._capture.set(cv2.CAP_PROP_FPS, self._fps)

            # Verify settings
            actual_width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self._capture.get(cv2.CAP_PROP_FPS))

            logger.info(
                f"✅ DirectShow camera {self._device_index} initialized: "
                f"{actual_width}x{actual_height} @ {actual_fps}fps"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize DirectShow camera: {e}", exc_info=True)
            return False

    async def read(self) -> SensorReading:
        """Capture frame from camera.

        Returns:
            SensorReading with numpy array frame in value field

        Raises:
            RuntimeError: If camera not initialized or read fails
        """
        if not self._capture or not OPENCV_AVAILABLE:
            raise RuntimeError("Camera not initialized")

        try:
            ret, frame = self._capture.read()

            if not ret or frame is None:
                raise RuntimeError("Failed to capture frame")

            return SensorReading(
                sensor=SensorType.CAMERA,
                value=frame,  # numpy array (H, W, 3) BGR
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"Camera read error: {e}")
            raise RuntimeError(f"Camera read failed: {e}") from e

    async def capture_frame(self) -> bytes | None:
        """Capture frame as JPEG bytes.

        Returns:
            JPEG-encoded frame or None if capture fails
        """
        if not OPENCV_AVAILABLE:
            return None

        try:
            reading = await self.read()
            frame = reading.value

            # Encode as JPEG
            success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

            if success:
                return buffer.tobytes()

            return None

        except Exception as e:
            logger.error(f"Frame capture error: {e}")
            return None

    async def get_capabilities(self) -> dict[str, Any]:
        """Get camera capabilities.

        Returns:
            Dict with supported resolutions, formats, fps
        """
        if not self._capture:
            return {}

        return {
            "backend": "DirectShow",
            "width": int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": int(self._capture.get(cv2.CAP_PROP_FPS)),
            "fourcc": int(self._capture.get(cv2.CAP_PROP_FOURCC)),
            "brightness": self._capture.get(cv2.CAP_PROP_BRIGHTNESS),
            "contrast": self._capture.get(cv2.CAP_PROP_CONTRAST),
            "saturation": self._capture.get(cv2.CAP_PROP_SATURATION),
        }

    async def shutdown(self) -> None:
        """Release camera resources."""
        if self._capture:
            self._capture.release()
            self._capture = None
        logger.info(f"✅ DirectShow camera {self._device_index} shutdown")

    @staticmethod
    def enumerate_cameras() -> list[int]:
        """Enumerate available DirectShow cameras.

        Returns:
            List of camera indices
        """
        if not OPENCV_AVAILABLE:
            return []

        cameras = []
        for i in range(10):  # Check first 10 indices
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                cameras.append(i)
                cap.release()
            else:
                break  # Stop at first missing camera

        return cameras
