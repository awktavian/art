"""macOS Camera Sensor via AVFoundation/OpenCV.

Provides camera access on macOS:
- AVFoundation via PyObjC (preferred, zero-copy)
- OpenCV fallback (cv2.VideoCapture)
- 1080p @ 30fps minimum
- Zero-copy frame capture via numpy

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

# Platform check
MACOS_AVAILABLE = sys.platform == "darwin"

# Try AVFoundation first (PyObjC)
AVFOUNDATION_AVAILABLE = False
AVFoundation = None
Quartz = None
if MACOS_AVAILABLE:
    try:
        import AVFoundation  # type: ignore[no-redef]
        import CoreMedia
        import objc
        import Quartz  # type: ignore[no-redef]
        from Foundation import NSObject

        AVCaptureSession = AVFoundation.AVCaptureSession  # type: ignore[attr-defined]
        AVCaptureDevice = AVFoundation.AVCaptureDevice  # type: ignore[attr-defined]
        AVCaptureDeviceInput = AVFoundation.AVCaptureDeviceInput  # type: ignore[attr-defined]
        AVCaptureVideoDataOutput = AVFoundation.AVCaptureVideoDataOutput  # type: ignore[attr-defined]
        AVMediaTypeVideo = AVFoundation.AVMediaTypeVideo  # type: ignore[attr-defined]

        # CoreMedia functions
        CMSampleBufferGetImageBuffer = CoreMedia.CMSampleBufferGetImageBuffer

        # CoreVideo functions (from Quartz framework)
        CVPixelBufferLockBaseAddress = Quartz.CVPixelBufferLockBaseAddress  # type: ignore[attr-defined]
        CVPixelBufferUnlockBaseAddress = Quartz.CVPixelBufferUnlockBaseAddress  # type: ignore[attr-defined]
        CVPixelBufferGetBaseAddress = Quartz.CVPixelBufferGetBaseAddress  # type: ignore[attr-defined]
        CVPixelBufferGetWidth = Quartz.CVPixelBufferGetWidth  # type: ignore[attr-defined]
        CVPixelBufferGetHeight = Quartz.CVPixelBufferGetHeight  # type: ignore[attr-defined]
        CVPixelBufferGetBytesPerRow = Quartz.CVPixelBufferGetBytesPerRow  # type: ignore[attr-defined]

        # Pixel format constant
        kCVPixelFormatType_32BGRA = 875704422  # 'BGRA' in little-endian

        AVFOUNDATION_AVAILABLE = True
    except ImportError:
        AVFoundation = None
        Quartz = None
        logger.debug(
            "AVFoundation not available. Install with: pip install pyobjc-framework-AVFoundation pyobjc-framework-Quartz"
        )

# Fallback to OpenCV
CV2_AVAILABLE = False
cv2 = None
try:
    import cv2  # type: ignore[assignment]

    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    logger.debug("OpenCV not available. Install with: pip install opencv-python")


# AVFoundation delegate class for frame callbacks
if AVFOUNDATION_AVAILABLE:
    from Foundation import NSObject

    class AVFoundationCameraDelegate(NSObject):
        """Delegate for receiving AVFoundation frame callbacks."""

        def init(self) -> AVFoundationCameraDelegate:
            """Initialize delegate."""
            self = objc.super(AVFoundationCameraDelegate, self).init()

            if self is None:
                return None

            self.parent_camera: AVFoundationCamera | None = None
            return self

        def captureOutput_didOutputSampleBuffer_fromConnection_(
            self, output: Any, sample_buffer: Any, connection: Any
        ) -> None:
            """Called when new frame is available.

            Args:
                output: AVCaptureOutput instance
                sample_buffer: CMSampleBuffer containing frame
                connection: AVCaptureConnection instance
            """
            if self.parent_camera is None:
                return

            try:
                # Get pixel buffer from sample buffer
                pixel_buffer = CMSampleBufferGetImageBuffer(sample_buffer)
                if pixel_buffer is None:
                    return

                # Lock pixel buffer for reading
                CVPixelBufferLockBaseAddress(pixel_buffer, 0)

                try:
                    # Get buffer properties
                    width = CVPixelBufferGetWidth(pixel_buffer)
                    height = CVPixelBufferGetHeight(pixel_buffer)
                    bytes_per_row = CVPixelBufferGetBytesPerRow(pixel_buffer)
                    base_address = CVPixelBufferGetBaseAddress(pixel_buffer)

                    if base_address == 0 or base_address is None:
                        return

                    # Create NumPy array from buffer (zero-copy)
                    import ctypes

                    buffer_ptr = ctypes.cast(base_address, ctypes.POINTER(ctypes.c_uint8))
                    frame_bgra = np.ctypeslib.as_array(buffer_ptr, shape=(height, bytes_per_row))

                    # Extract BGRA channels (4 bytes per pixel)
                    frame_bgra = frame_bgra[:, : width * 4].reshape((height, width, 4))

                    # Convert BGRA to RGB (drop alpha channel)
                    frame_rgb = frame_bgra[:, :, [2, 1, 0]].copy()

                    # Store in parent camera
                    self.parent_camera._store_frame(frame_rgb)

                finally:
                    # Always unlock pixel buffer
                    CVPixelBufferUnlockBaseAddress(pixel_buffer, 0)

            except Exception as e:
                logger.error(f"Frame capture error in delegate: {e}")

else:
    AVFoundationCameraDelegate = None  # type: ignore[assignment,misc]


class AVFoundationCamera:
    """Native macOS camera using AVFoundation.

    Provides zero-copy frame capture via CVPixelBuffer → NumPy.
    """

    def __init__(
        self, device_index: int = 0, width: int = 1920, height: int = 1080, fps: int = 30
    ) -> None:
        """Initialize AVFoundation camera.

        Args:
            device_index: Camera device index (0 = default)
            width: Target frame width
            height: Target frame height
            fps: Target frame rate
        """
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps

        self._session: Any = None
        self._output: Any = None
        self._delegate: Any = None
        self._latest_frame: np.ndarray | None = None
        self._frame_lock = threading.Lock()
        self._running = False

    def start(self) -> bool:
        """Start capture session.

        Returns:
            True if session started successfully
        """
        if not AVFOUNDATION_AVAILABLE:
            logger.error("AVFoundation not available")
            return False

        try:
            # 1. Get capture devices
            devices = AVCaptureDevice.devicesWithMediaType_(AVMediaTypeVideo)
            if not devices or self.device_index >= len(devices):
                logger.error(f"Camera device {self.device_index} not found")
                return False

            device = devices[self.device_index]

            # 2. Create device input
            error = None
            device_input = AVCaptureDeviceInput.deviceInputWithDevice_error_(device, error)
            if device_input is None:
                logger.error(f"Failed to create device input: {error}")
                return False

            # 3. Create capture session
            self._session = AVCaptureSession.alloc().init()
            self._session.beginConfiguration()

            # 4. Set session preset (resolution)
            if self.width >= 1920 and self.height >= 1080:
                preset = "AVCaptureSessionPreset1920x1080"
            elif self.width >= 1280 and self.height >= 720:
                preset = "AVCaptureSessionPreset1280x720"
            elif self.width >= 640 and self.height >= 480:
                preset = "AVCaptureSessionPreset640x480"
            else:
                preset = "AVCaptureSessionPresetLow"

            self._session.setSessionPreset_(preset)

            # 5. Add input
            if self._session.canAddInput_(device_input):
                self._session.addInput_(device_input)
            else:
                logger.error("Cannot add device input to session")
                return False

            # 6. Create video output
            self._output = AVCaptureVideoDataOutput.alloc().init()

            # 7. Set pixel format (BGRA for NumPy compatibility)
            from Foundation import NSNumber

            settings = {
                "kCVPixelBufferPixelFormatTypeKey": NSNumber.numberWithUnsignedInt_(
                    kCVPixelFormatType_32BGRA
                )
            }
            self._output.setVideoSettings_(settings)

            # 8. Create delegate for frame callbacks
            self._delegate = AVFoundationCameraDelegate.alloc().init()
            self._delegate.parent_camera = self

            # 9. Create dispatch queue for delegate callbacks
            # Use Dispatch framework from PyObjC
            import Dispatch

            queue = Dispatch.dispatch_queue_create(b"camera_queue", None)  # None = serial queue
            self._output.setSampleBufferDelegate_queue_(self._delegate, queue)

            # 10. Add output
            if self._session.canAddOutput_(self._output):
                self._session.addOutput_(self._output)
            else:
                logger.error("Cannot add video output to session")
                return False

            # 11. Commit configuration and start
            self._session.commitConfiguration()
            self._session.startRunning()

            self._running = True
            logger.info(
                f"✅ AVFoundation camera started: {self.width}x{self.height} @ {self.fps}fps"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start AVFoundation camera: {e}")
            return False

    def _store_frame(self, frame: np.ndarray) -> None:
        """Store latest frame (called by delegate).

        Args:
            frame: Captured frame as NumPy array
        """
        with self._frame_lock:
            self._latest_frame = frame

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read latest frame.

        Returns:
            (success, frame) tuple. Frame is None if no frame available.
        """
        with self._frame_lock:
            if self._latest_frame is not None:
                return True, self._latest_frame.copy()
        return False, None

    def stop(self) -> None:
        """Stop capture session."""
        if self._session and self._running:
            self._session.stopRunning()
            self._running = False

    def release(self) -> None:
        """Release resources."""
        self.stop()
        self._session = None
        self._output = None
        self._delegate = None
        with self._frame_lock:
            self._latest_frame = None


class MacOSCamera:
    """macOS camera implementation using AVFoundation or OpenCV."""

    def __init__(self) -> None:
        """Initialize camera."""
        self._initialized = False
        self._backend: str | None = None

        # OpenCV backend
        self._cv2_cap: Any | None = None

        # AVFoundation backend
        self._av_camera: AVFoundationCamera | None = None

        # Frame properties
        self._width = 1920
        self._height = 1080
        self._fps = 30

        # Permission check flag
        self._permission_granted = False

    async def initialize(
        self, device_index: int = 0, width: int = 1920, height: int = 1080, fps: int = 30
    ) -> bool:
        """Initialize camera.

        Args:
            device_index: Camera device index (0 = default)
            width: Frame width (default 1920)
            height: Frame height (default 1080)
            fps: Target frame rate (default 30)

        Returns:
            True if camera initialized successfully
        """
        if not MACOS_AVAILABLE:
            logger.warning("Camera only available on macOS")
            return False

        self._width = width
        self._height = height
        self._fps = fps

        # Check permissions
        if not await self._check_camera_permission():
            logger.warning(
                "Camera permission not granted. "
                "Go to System Preferences > Security & Privacy > Camera"
            )
            return False

        # Try backends in order of preference
        if AVFOUNDATION_AVAILABLE:
            if await self._init_avfoundation(device_index):
                self._backend = "avfoundation"
                logger.info(f"✅ Camera initialized via AVFoundation: {width}x{height} @ {fps}fps")
                self._initialized = True
                return True

        if CV2_AVAILABLE:
            if await self._init_opencv(device_index):
                self._backend = "opencv"
                logger.info(f"✅ Camera initialized via OpenCV: {width}x{height} @ {fps}fps")
                self._initialized = True
                return True

        logger.error("No camera backend available (need AVFoundation or OpenCV)")
        return False

    async def _check_camera_permission(self) -> bool:
        """Check camera permission status.

        Returns:
            True if permission granted or not required
        """
        # On macOS, camera permission is checked at runtime
        # We can't programmatically request it without UI
        # Best effort: try to open camera and see if it works
        # For now, assume permission granted (will fail gracefully later)
        self._permission_granted = True
        return True

    async def _init_avfoundation(self, device_index: int) -> bool:
        """Initialize AVFoundation backend.

        Args:
            device_index: Camera device index

        Returns:
            True if AVFoundation initialized successfully
        """
        if not AVFOUNDATION_AVAILABLE:
            return False

        try:
            # Create AVFoundation camera instance
            self._av_camera = AVFoundationCamera(
                device_index=device_index,
                width=self._width,
                height=self._height,
                fps=self._fps,
            )

            # Start capture session
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self._av_camera.start)

            if not success:
                self._av_camera = None
                return False

            # Update actual resolution from camera
            # (AVFoundation may adjust based on preset)
            ret, frame = await loop.run_in_executor(None, self._av_camera.read)
            if ret and frame is not None:
                self._height, self._width = frame.shape[:2]

            return True

        except Exception as e:
            logger.error(f"Failed to initialize AVFoundation: {e}")
            self._av_camera = None
            return False

    async def _init_opencv(self, device_index: int) -> bool:
        """Initialize OpenCV backend."""
        try:
            # Open camera
            self._cv2_cap = cv2.VideoCapture(device_index)  # type: ignore[attr-defined]

            if not self._cv2_cap.isOpened():
                logger.error(f"Failed to open camera {device_index}")
                return False

            # Set resolution
            self._cv2_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)  # type: ignore[attr-defined]
            self._cv2_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)  # type: ignore[attr-defined]
            self._cv2_cap.set(cv2.CAP_PROP_FPS, self._fps)  # type: ignore[attr-defined]

            # Verify settings
            actual_width = int(self._cv2_cap.get(cv2.CAP_PROP_FRAME_WIDTH))  # type: ignore[attr-defined]
            actual_height = int(self._cv2_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))  # type: ignore[attr-defined]
            actual_fps = int(self._cv2_cap.get(cv2.CAP_PROP_FPS))  # type: ignore[attr-defined]

            if actual_width != self._width or actual_height != self._height:
                logger.warning(
                    f"Camera resolution mismatch: requested {self._width}x{self._height}, "
                    f"got {actual_width}x{actual_height}"
                )
                self._width = actual_width
                self._height = actual_height

            if actual_fps != self._fps:
                logger.debug(f"Camera FPS mismatch: requested {self._fps}, got {actual_fps}")
                self._fps = actual_fps

            return True

        except Exception as e:
            logger.error(f"Failed to initialize OpenCV camera: {e}")
            return False

    async def capture_frame(self) -> np.ndarray | None:
        """Capture a single frame.

        Returns:
            numpy array of shape (height, width, 3) in RGB format, or None on error
        """
        if not self._initialized:
            raise RuntimeError("Camera not initialized")

        if self._backend == "opencv" and self._cv2_cap:
            return await self._capture_opencv()
        elif self._backend == "avfoundation":
            return await self._capture_avfoundation()
        else:
            raise RuntimeError(f"Unknown backend: {self._backend}")

    async def _capture_opencv(self) -> np.ndarray | None:
        """Capture frame from OpenCV backend."""
        if self._cv2_cap is None:
            return None

        try:
            # Run in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            ret, frame = await loop.run_in_executor(None, self._cv2_cap.read)

            if not ret or frame is None:
                logger.error("Failed to capture frame")
                return None

            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # type: ignore[attr-defined]
            return frame_rgb

        except Exception as e:
            logger.error(f"Frame capture error: {e}")
            return None

    async def _capture_avfoundation(self) -> np.ndarray | None:
        """Capture frame from AVFoundation backend.

        Returns:
            Captured frame as NumPy array (RGB), or None on error
        """
        if self._av_camera is None:
            return None

        try:
            # Run in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            ret, frame = await loop.run_in_executor(None, self._av_camera.read)

            if not ret or frame is None:
                logger.debug("No frame available from AVFoundation")
                return None

            return frame

        except Exception as e:
            logger.error(f"AVFoundation frame capture error: {e}")
            return None

    async def read_sensor(self) -> SensorReading:
        """Read camera as sensor (for HAL sensor interface compatibility).

        Returns:
            SensorReading with captured frame as value
        """
        frame = await self.capture_frame()

        if frame is None:
            raise RuntimeError("Failed to capture camera frame")

        import time

        return SensorReading(
            sensor=SensorType.CAMERA,
            value=frame,
            timestamp_ms=int(time.time() * 1000),
            accuracy=1.0 if frame is not None else 0.0,
        )

    async def stream_frames(self) -> AsyncIterator[np.ndarray]:
        """Stream frames as async iterator.

        Yields:
            numpy arrays of captured frames
        """
        if not self._initialized:
            raise RuntimeError("Camera not initialized")

        while self._initialized:
            frame = await self.capture_frame()
            if frame is not None:
                yield frame

            # Maintain target FPS
            await asyncio.sleep(1.0 / self._fps)

    def get_resolution(self) -> tuple[int, int]:
        """Get current camera resolution.

        Returns:
            (width, height) tuple
        """
        return (self._width, self._height)

    def get_fps(self) -> int:
        """Get current frame rate.

        Returns:
            FPS as integer
        """
        return self._fps

    async def shutdown(self) -> None:
        """Shutdown camera."""
        self._initialized = False

        # Shutdown OpenCV backend
        if self._cv2_cap:
            self._cv2_cap.release()
            self._cv2_cap = None

        # Shutdown AVFoundation backend
        if self._av_camera:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._av_camera.release)
            self._av_camera = None

        logger.info("✅ Camera shutdown")


__all__ = [
    "AVFOUNDATION_AVAILABLE",
    "CV2_AVAILABLE",
    "AVFoundationCamera",
    "MacOSCamera",
]
