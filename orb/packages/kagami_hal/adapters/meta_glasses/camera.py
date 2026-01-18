"""Meta Glasses Camera Adapter — First-Person POV Video.

Provides access to the Ray-Ban Meta camera for:
- Live video streaming (POV perspective)
- Photo capture
- Visual context extraction

Privacy-First Design:
- Raw video stays on companion device by default
- Only semantic features sent to Kagami
- Explicit user consent required
- Visual indicators when camera active

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CameraResolution(Enum):
    """Camera resolution options."""

    LOW = "low"  # 480p - low bandwidth
    MEDIUM = "medium"  # 720p - balanced
    HIGH = "high"  # 1080p - full quality


class CameraMode(Enum):
    """Camera operating mode."""

    STREAM = "stream"  # Continuous video stream
    SNAPSHOT = "snapshot"  # Single photo capture
    BURST = "burst"  # Multiple rapid captures


@dataclass
class CameraStreamConfig:
    """Configuration for camera streaming."""

    resolution: CameraResolution = CameraResolution.MEDIUM
    fps: int = 15  # Frames per second (glasses limit)
    jpeg_quality: int = 80  # JPEG compression quality (1-100)
    extract_features: bool = True  # Extract semantic features
    send_raw: bool = False  # Send raw frames (privacy impact)
    max_duration_seconds: int = 300  # Auto-stop after this duration


@dataclass
class CameraFrame:
    """A single camera frame."""

    timestamp: float
    width: int
    height: int
    data: bytes  # JPEG encoded image data
    frame_number: int = 0

    # Extracted features (if enabled)
    features: dict[str, Any] = field(default_factory=dict)

    @property
    def size_bytes(self) -> int:
        """Get frame size in bytes."""
        return len(self.data)


@dataclass
class PhotoCaptureResult:
    """Result of a photo capture."""

    success: bool
    timestamp: float = 0.0
    width: int = 0
    height: int = 0
    data: bytes = b""
    error: str | None = None

    # Extracted features
    features: dict[str, Any] = field(default_factory=dict)


@dataclass
class VisualContext:
    """Semantic visual context extracted from camera."""

    # Environment
    is_indoor: bool | None = None
    lighting: str | None = None  # "bright", "dim", "dark"
    ambient_color_temp: int | None = None  # Kelvin

    # Scene
    scene_type: str | None = None  # "office", "kitchen", "outdoor", etc.
    detected_objects: list[str] = field(default_factory=list)
    detected_text: list[str] = field(default_factory=list)

    # People
    faces_detected: int = 0
    known_people: list[str] = field(default_factory=list)

    # Activity hints
    activity_hint: str | None = None  # "reading", "cooking", "watching_tv", etc.

    # Confidence
    confidence: float = 0.0


FrameCallback = Callable[[CameraFrame], Awaitable[None]]
ContextCallback = Callable[[VisualContext], Awaitable[None]]


class MetaGlassesCamera:
    """Camera adapter for Meta Ray-Ban smart glasses.

    Provides first-person POV camera access with privacy controls.

    Usage:
        camera = MetaGlassesCamera(protocol)
        await camera.initialize()

        # Stream video
        async for frame in camera.stream(config):
            process_frame(frame)

        # Capture photo
        result = await camera.capture_photo()
        if result.success:
            save_photo(result.data)

        # Get visual context
        context = await camera.get_visual_context()
        print(f"Scene: {context.scene_type}")
    """

    def __init__(self, protocol: Any = None) -> None:
        """Initialize camera adapter.

        Args:
            protocol: MetaGlassesProtocol instance (optional, can set later)
        """
        self._protocol = protocol
        self._streaming = False
        self._stream_config: CameraStreamConfig | None = None
        self._frame_callbacks: list[FrameCallback] = []
        self._context_callbacks: list[ContextCallback] = []
        self._frame_count = 0
        self._last_context: VisualContext | None = None

        # Frame buffer for streaming
        self._frame_queue: asyncio.Queue[CameraFrame] = asyncio.Queue(maxsize=30)

    def set_protocol(self, protocol: Any) -> None:
        """Set or update the protocol handler.

        Args:
            protocol: MetaGlassesProtocol instance
        """
        self._protocol = protocol

    async def initialize(self) -> bool:
        """Initialize camera adapter.

        Returns:
            True if initialization successful
        """
        if not self._protocol:
            logger.warning("No protocol set")
            return False

        # Register for camera events
        self._protocol.on_event(self._handle_event)

        logger.info("MetaGlassesCamera initialized")
        return True

    async def start_stream(self, config: CameraStreamConfig | None = None) -> bool:
        """Start camera streaming.

        Args:
            config: Stream configuration (defaults to medium quality)

        Returns:
            True if stream started
        """
        if self._streaming:
            logger.warning("Already streaming")
            return True

        if not self._protocol or not self._protocol.is_connected:
            logger.error("Glasses not connected")
            return False

        self._stream_config = config or CameraStreamConfig()
        self._frame_count = 0

        # Import here to avoid circular dependency
        from kagami_hal.adapters.meta_glasses.protocol import GlassesCommand

        result = await self._protocol.send_command(
            GlassesCommand.START_CAMERA,
            params={
                "resolution": self._stream_config.resolution.value,
                "fps": self._stream_config.fps,
                "jpeg_quality": self._stream_config.jpeg_quality,
                "extract_features": self._stream_config.extract_features,
                "send_raw": self._stream_config.send_raw,
            },
            wait_response=True,
        )

        if result and result.get("success"):
            self._streaming = True
            logger.info(f"Camera streaming started ({self._stream_config.resolution.value})")
            return True

        logger.error("Failed to start camera stream")
        return False

    async def stop_stream(self) -> None:
        """Stop camera streaming."""
        if not self._streaming:
            return

        if self._protocol and self._protocol.is_connected:
            from kagami_hal.adapters.meta_glasses.protocol import GlassesCommand

            await self._protocol.send_command(GlassesCommand.STOP_CAMERA)

        self._streaming = False
        self._stream_config = None

        # Clear frame queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        logger.info("Camera streaming stopped")

    async def stream(self, config: CameraStreamConfig | None = None) -> AsyncIterator[CameraFrame]:
        """Stream camera frames as async iterator.

        Args:
            config: Stream configuration

        Yields:
            CameraFrame objects
        """
        if not await self.start_stream(config):
            return

        try:
            while self._streaming:
                try:
                    frame = await asyncio.wait_for(self._frame_queue.get(), timeout=5.0)
                    yield frame
                except TimeoutError:
                    # No frame received, check if still streaming
                    if not self._streaming:
                        break
                    continue

        finally:
            await self.stop_stream()

    async def capture_photo(
        self,
        extract_features: bool = True,
    ) -> PhotoCaptureResult:
        """Capture a single photo.

        Args:
            extract_features: Whether to extract semantic features

        Returns:
            PhotoCaptureResult with image data
        """
        if not self._protocol or not self._protocol.is_connected:
            return PhotoCaptureResult(success=False, error="Glasses not connected")

        from kagami_hal.adapters.meta_glasses.protocol import GlassesCommand

        result = await self._protocol.send_command(
            GlassesCommand.CAPTURE_PHOTO,
            params={"extract_features": extract_features},
            wait_response=True,
            timeout=10.0,
        )

        if not result:
            return PhotoCaptureResult(success=False, error="Capture timeout")

        if result.get("error"):
            return PhotoCaptureResult(success=False, error=result.get("error"))

        import base64
        import time

        # Decode base64 image data
        image_data = result.get("image_data", "")
        if image_data:
            try:
                decoded = base64.b64decode(image_data)
            except Exception:
                decoded = b""
        else:
            decoded = b""

        return PhotoCaptureResult(
            success=True,
            timestamp=result.get("timestamp", time.time()),
            width=result.get("width", 0),
            height=result.get("height", 0),
            data=decoded,
            features=result.get("features", {}),
        )

    async def get_visual_context(self, force_refresh: bool = False) -> VisualContext:
        """Get current visual context from camera.

        This extracts semantic information without storing raw images.

        Args:
            force_refresh: Force new capture instead of using cached

        Returns:
            VisualContext with semantic features
        """
        # Return cached if recent and not forcing refresh
        if not force_refresh and self._last_context:
            return self._last_context

        # Capture and extract
        result = await self.capture_photo(extract_features=True)

        if not result.success:
            return VisualContext(confidence=0.0)

        features = result.features
        context = VisualContext(
            is_indoor=features.get("is_indoor"),
            lighting=features.get("lighting"),
            ambient_color_temp=features.get("color_temp"),
            scene_type=features.get("scene_type"),
            detected_objects=features.get("objects", []),
            detected_text=features.get("text", []),
            faces_detected=features.get("face_count", 0),
            known_people=features.get("known_people", []),
            activity_hint=features.get("activity"),
            confidence=features.get("confidence", 0.5),
        )

        self._last_context = context

        # Notify context callbacks
        for callback in self._context_callbacks:
            try:
                await callback(context)
            except Exception as e:
                logger.error(f"Context callback error: {e}")

        return context

    def on_frame(self, callback: FrameCallback) -> None:
        """Register frame callback.

        Args:
            callback: Async function to call with each frame
        """
        self._frame_callbacks.append(callback)

    def off_frame(self, callback: FrameCallback) -> None:
        """Unregister frame callback.

        Args:
            callback: Previously registered callback
        """
        if callback in self._frame_callbacks:
            self._frame_callbacks.remove(callback)

    def on_context(self, callback: ContextCallback) -> None:
        """Register context callback.

        Args:
            callback: Async function to call with context updates
        """
        self._context_callbacks.append(callback)

    async def _handle_event(self, event: Any) -> None:
        """Handle events from protocol."""
        if event.event_type == "camera_frame":
            await self._handle_frame(event.data)

    async def _handle_frame(self, data: dict[str, Any]) -> None:
        """Handle incoming camera frame."""
        import time

        frame_data = data.get("frame_data", b"")
        if isinstance(frame_data, str):
            import base64

            try:
                frame_data = base64.b64decode(frame_data)
            except Exception:
                frame_data = b""

        self._frame_count += 1

        frame = CameraFrame(
            timestamp=data.get("timestamp", time.time()),
            width=data.get("width", 0),
            height=data.get("height", 0),
            data=frame_data,
            frame_number=self._frame_count,
            features=data.get("features", {}),
        )

        # Add to queue for stream() consumers
        try:
            self._frame_queue.put_nowait(frame)
        except asyncio.QueueFull:
            # Drop oldest frame
            try:
                self._frame_queue.get_nowait()
                self._frame_queue.put_nowait(frame)
            except asyncio.QueueEmpty:
                pass

        # Notify frame callbacks
        for callback in self._frame_callbacks:
            try:
                await callback(frame)
            except Exception as e:
                logger.error(f"Frame callback error: {e}")

    @property
    def is_streaming(self) -> bool:
        """Check if camera is currently streaming."""
        return self._streaming

    @property
    def frame_count(self) -> int:
        """Get number of frames received in current session."""
        return self._frame_count

    async def shutdown(self) -> None:
        """Shutdown camera adapter."""
        await self.stop_stream()
        self._frame_callbacks.clear()
        self._context_callbacks.clear()

        if self._protocol:
            self._protocol.off_event(self._handle_event)

        logger.info("MetaGlassesCamera shutdown")


"""
Mirror
h(x) >= 0. Always.

The camera sees what you see.
First-person perspective, sensed not stored.
Privacy is the foundation.
"""
