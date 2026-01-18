"""Embedded Camera Sensor using libcamera/V4L2.

Supports:
- Raspberry Pi Camera Module via libcamera
- USB cameras via V4L2
- NVIDIA Jetson CSI cameras via nvarguscamerasrc
- Generic V4L2-compatible cameras

Created: December 15, 2025
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

# Check for camera support
PICAMERA2_AVAILABLE = False
CV2_AVAILABLE = False

try:
    from picamera2 import Picamera2

    PICAMERA2_AVAILABLE = True
except ImportError:
    pass

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    pass


class CameraSensor:
    """Camera sensor implementation for embedded platforms.

    Priority order:
    1. libcamera (picamera2) for Raspberry Pi Camera Module
    2. V4L2 (OpenCV) for USB cameras
    3. Jetson CSI (OpenCV GStreamer) for NVIDIA cameras
    """

    def __init__(
        self,
        device_id: int | str = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        format: str = "BGR",
    ):
        """Initialize camera sensor.

        Args:
            device_id: Camera device ID or path (e.g., 0, "/dev/video0")
            width: Frame width
            height: Frame height
            fps: Target frame rate
            format: Pixel format (BGR, RGB, GRAY)
        """
        self._device_id = device_id
        self._width = width
        self._height = height
        self._fps = fps
        self._format = format

        self._camera: Any = None
        self._backend: str = "none"
        self._running = False

    async def initialize(self) -> bool:
        """Initialize camera.

        Returns:
            True if camera initialized successfully
        """
        # Try libcamera (picamera2) for Raspberry Pi
        if PICAMERA2_AVAILABLE and self._try_libcamera():
            logger.info(
                f"Camera initialized: libcamera @ {self._width}x{self._height} {self._fps}fps"
            )
            return True

        # Try V4L2 (OpenCV) for USB cameras
        if CV2_AVAILABLE and self._try_v4l2():
            logger.info(f"Camera initialized: V4L2 @ {self._width}x{self._height} {self._fps}fps")
            return True

        # Try Jetson CSI (OpenCV GStreamer)
        if CV2_AVAILABLE and self._try_jetson_csi():
            logger.info(
                f"Camera initialized: Jetson CSI @ {self._width}x{self._height} {self._fps}fps"
            )
            return True

        if is_test_mode():
            logger.info("Camera not available, gracefully degrading")
            return False

        logger.error("No camera backend available")
        return False

    def _try_libcamera(self) -> bool:
        """Try to initialize libcamera (Raspberry Pi Camera Module).

        Returns:
            True if successful
        """
        try:
            self._camera = Picamera2()

            # Configure camera
            config = self._camera.create_preview_configuration(
                main={"size": (self._width, self._height), "format": self._format},
                controls={"FrameRate": self._fps},
            )
            self._camera.configure(config)
            self._camera.start()

            self._backend = "libcamera"
            self._running = True
            return True

        except Exception as e:
            logger.debug(f"libcamera init failed: {e}")
            return False

    def _try_v4l2(self) -> bool:
        """Try to initialize V4L2 (USB cameras).

        Returns:
            True if successful
        """
        try:
            # Try to open camera device
            device_num = int(self._device_id) if isinstance(self._device_id, int) else 0

            self._camera = cv2.VideoCapture(device_num, cv2.CAP_V4L2)

            if not self._camera.isOpened():
                return False

            # Configure camera
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._camera.set(cv2.CAP_PROP_FPS, self._fps)

            # Verify settings
            actual_w = int(self._camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._camera.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if actual_w != self._width or actual_h != self._height:
                logger.warning(f"Camera resolution adjusted: {actual_w}x{actual_h}")
                self._width = actual_w
                self._height = actual_h

            self._backend = "v4l2"
            self._running = True
            return True

        except Exception as e:
            logger.debug(f"V4L2 init failed: {e}")
            if self._camera:
                self._camera.release()
            return False

    def _try_jetson_csi(self) -> bool:
        """Try to initialize Jetson CSI camera via GStreamer.

        Returns:
            True if successful
        """
        # Check if on Jetson platform
        if not Path("/etc/nv_tegra_release").exists():
            return False

        try:
            # GStreamer pipeline for Jetson CSI camera
            # Using nvarguscamerasrc (NVIDIA Argus camera driver)
            gst_pipeline = (
                f"nvarguscamerasrc sensor-id={self._device_id} ! "
                f"video/x-raw(memory:NVMM), width={self._width}, height={self._height}, "
                f"framerate={self._fps}/1, format=NV12 ! "
                f"nvvidconv ! video/x-raw, format=BGRx ! "
                f"videoconvert ! video/x-raw, format=BGR ! appsink"
            )

            self._camera = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

            if not self._camera.isOpened():
                return False

            self._backend = "jetson_csi"
            self._running = True
            return True

        except Exception as e:
            logger.debug(f"Jetson CSI init failed: {e}")
            if self._camera:
                self._camera.release()
            return False

    async def read(self) -> SensorReading:
        """Capture frame from camera.

        Returns:
            SensorReading with frame data (numpy array)

        Raises:
            RuntimeError: If camera not initialized or capture fails
        """
        if not self._running or not self._camera:
            raise RuntimeError("Camera not initialized")

        try:
            if self._backend == "libcamera":
                # Capture from picamera2
                frame = self._camera.capture_array()

                # Convert format if needed
                if self._format == "RGB" and frame.shape[2] == 3:
                    frame = frame[:, :, ::-1]  # BGR to RGB

            else:
                # Capture from OpenCV
                ret, frame = self._camera.read()

                if not ret or frame is None:
                    raise RuntimeError("Failed to capture frame")

                # Convert format if needed
                if self._format == "RGB":
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                elif self._format == "GRAY":
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            return SensorReading(
                sensor=SensorType.LIGHT,  # Camera as light sensor
                value=frame,
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"Camera capture failed: {e}")
            raise

    def get_frame_shape(self) -> tuple[int, int, int]:
        """Get frame shape (height, width, channels).

        Returns:
            Tuple of (height, width, channels)
        """
        channels = 3 if self._format in ("BGR", "RGB") else 1
        return (self._height, self._width, channels)

    def set_exposure(self, exposure_us: int) -> bool:
        """Set camera exposure time.

        Args:
            exposure_us: Exposure time in microseconds

        Returns:
            True if successful
        """
        try:
            if self._backend == "libcamera":
                self._camera.set_controls({"ExposureTime": exposure_us})
                return True
            elif self._backend in ("v4l2", "jetson_csi"):
                # OpenCV exposure (normalized 0-1)
                normalized = exposure_us / 1000000.0
                self._camera.set(cv2.CAP_PROP_EXPOSURE, normalized)
                return True
        except Exception as e:
            logger.warning(f"Failed to set exposure: {e}")
        return False

    def set_gain(self, gain: float) -> bool:
        """Set camera analog gain.

        Args:
            gain: Analog gain value (1.0 = no gain)

        Returns:
            True if successful
        """
        try:
            if self._backend == "libcamera":
                self._camera.set_controls({"AnalogueGain": gain})
                return True
            elif self._backend in ("v4l2", "jetson_csi"):
                self._camera.set(cv2.CAP_PROP_GAIN, gain)
                return True
        except Exception as e:
            logger.warning(f"Failed to set gain: {e}")
        return False

    def set_awb_mode(self, mode: str) -> bool:
        """Set auto white balance mode.

        Args:
            mode: AWB mode ("auto", "daylight", "cloudy", "tungsten", etc.)

        Returns:
            True if successful
        """
        try:
            if self._backend == "libcamera":
                # Map mode to libcamera AWB mode
                awb_modes = {
                    "auto": 0,
                    "tungsten": 1,
                    "fluorescent": 2,
                    "daylight": 3,
                    "cloudy": 4,
                }
                if mode in awb_modes:
                    self._camera.set_controls({"AwbMode": awb_modes[mode]})
                    return True
            elif self._backend in ("v4l2", "jetson_csi"):
                # OpenCV auto white balance
                self._camera.set(cv2.CAP_PROP_AUTO_WB, 1 if mode == "auto" else 0)
                return True
        except Exception as e:
            logger.warning(f"Failed to set AWB mode: {e}")
        return False

    async def shutdown(self) -> None:
        """Shutdown camera."""
        self._running = False

        if self._camera:
            try:
                if self._backend == "libcamera":
                    self._camera.stop()
                    self._camera.close()
                else:
                    self._camera.release()
            except Exception as e:
                logger.error(f"Camera shutdown error: {e}")

            self._camera = None

        logger.info(f"Camera shutdown ({self._backend})")


__all__ = ["CameraSensor"]
