"""Studio Engine — Central orchestrator for Kagami Studio.

The StudioEngine coordinates all subsystems:
- Sources: Input from cameras, screens, AI, etc.
- Scenes: Composition with transitions and overlays
- Outputs: Recording, streaming, virtual camera
- Generation: AI content creation
- Pipeline: Real-time processing

Usage:
    from kagami_studio import Studio

    async with Studio() as studio:
        # Add sources
        cam = await studio.add_camera_source()
        avatar = await studio.add_avatar_source("Kagami")

        # Create and switch scenes
        scene = studio.create_scene("Main")
        scene.add_source(avatar, position="center")
        await studio.switch_scene("Main")

        # Output
        await studio.start_recording("output.mp4")
        await studio.start_streaming("rtmp://...")
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


class OutputFormat(str, Enum):
    """Video output format."""

    MP4 = "mp4"
    MKV = "mkv"
    MOV = "mov"
    WEBM = "webm"


class StreamingPlatform(str, Enum):
    """Streaming platform presets."""

    TWITCH = "twitch"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    CUSTOM = "custom"


@dataclass
class StudioConfig:
    """Configuration for Studio session."""

    # Video settings
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30
    video_bitrate: str = "4500k"
    video_codec: str = "libx264"

    # Audio settings
    sample_rate: int = 48000
    audio_bitrate: str = "192k"
    audio_codec: str = "aac"
    channels: int = 2

    # Spatial audio
    enable_spatial_audio: bool = True
    spatial_layout: str = "5.1.4"

    # Processing
    enable_gpu: bool = True
    max_sources: int = 20
    preview_enabled: bool = True

    # Output directory
    output_dir: Path = field(default_factory=lambda: Path("/tmp/kagami_studio"))

    # AI settings
    default_avatar: str = "kagami"
    enable_ai_generation: bool = True


@dataclass
class StudioSession:
    """Active studio session state."""

    session_id: str
    started_at: float
    config: StudioConfig
    active_scene: str | None = None
    is_recording: bool = False
    is_streaming: bool = False
    is_virtual_cam: bool = False
    frame_count: int = 0
    dropped_frames: int = 0


# =============================================================================
# STUDIO ENGINE
# =============================================================================


class StudioEngine:
    """Central orchestrator for Kagami Studio.

    Coordinates all subsystems for unified production:
    - SourceManager: Input sources (camera, screen, AI avatar, etc.)
    - SceneManager: Scene composition with transitions
    - OutputManager: Recording, streaming, virtual camera
    - GenerationHub: AI content generation
    - ProcessingPipeline: Real-time video/audio processing
    """

    def __init__(self, config: StudioConfig | None = None):
        self.config = config or StudioConfig()
        self._session: StudioSession | None = None

        # Subsystem managers (lazy loaded)
        self._source_manager: Any = None
        self._scene_manager: Any = None
        self._output_manager: Any = None
        self._generation_hub: Any = None
        self._pipeline: Any = None

        # State
        self._initialized = False
        self._running = False
        self._frame_buffer: asyncio.Queue = asyncio.Queue(maxsize=30)

    async def initialize(self) -> None:
        """Initialize all subsystems."""
        if self._initialized:
            return

        logger.info("Initializing Kagami Studio...")
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize subsystems
        from kagami_studio.generation import GenerationHub
        from kagami_studio.outputs import OutputManager
        from kagami_studio.scenes import SceneManager
        from kagami_studio.sources import SourceManager

        self._source_manager = SourceManager(self.config)
        self._scene_manager = SceneManager(self.config)
        self._output_manager = OutputManager(self.config)
        self._generation_hub = GenerationHub(self.config)

        # Initialize all subsystems in parallel (non-blocking)
        await asyncio.gather(
            self._source_manager.initialize(),
            self._scene_manager.initialize(),
            self._output_manager.initialize(),
            self._generation_hub.initialize(),
        )

        self._initialized = True
        logger.info("✅ Kagami Studio initialized")

    async def start_session(self) -> StudioSession:
        """Start a new studio session."""
        if not self._initialized:
            await self.initialize()

        session_id = str(uuid.uuid4())[:8]
        self._session = StudioSession(
            session_id=session_id,
            started_at=time.time(),
            config=self.config,
        )

        # Create default scene
        self._scene_manager.create_scene("Default")
        self._session.active_scene = "Default"

        logger.info(f"Session started: {session_id}")
        return self._session

    async def stop_session(self) -> None:
        """Stop the current session and cleanup."""
        if not self._session:
            return

        # Stop all outputs
        if self._session.is_recording:
            await self.stop_recording()
        if self._session.is_streaming:
            await self.stop_streaming()
        if self._session.is_virtual_cam:
            await self.stop_virtual_camera()

        # Cleanup sources
        await self._source_manager.cleanup()

        session_id = self._session.session_id
        duration = time.time() - self._session.started_at
        self._session = None

        logger.info(f"Session ended: {session_id} ({duration:.1f}s)")

    # -------------------------------------------------------------------------
    # SOURCE MANAGEMENT
    # -------------------------------------------------------------------------

    async def add_camera_source(
        self,
        device_id: int = 0,
        name: str | None = None,
    ) -> str:
        """Add a camera source.

        Args:
            device_id: Camera device index
            name: Source name (auto-generated if None)

        Returns:
            Source ID
        """
        return await self._source_manager.add_camera(device_id, name)

    async def add_screen_source(
        self,
        monitor: int = 0,
        name: str | None = None,
    ) -> str:
        """Add screen capture source.

        Args:
            monitor: Monitor index
            name: Source name

        Returns:
            Source ID
        """
        return await self._source_manager.add_screen(monitor, name)

    async def add_image_source(
        self,
        path: Path | str,
        name: str | None = None,
    ) -> str:
        """Add image source.

        Args:
            path: Path to image file
            name: Source name

        Returns:
            Source ID
        """
        return await self._source_manager.add_image(Path(path), name)

    async def add_video_source(
        self,
        path: Path | str,
        loop: bool = True,
        name: str | None = None,
    ) -> str:
        """Add video source.

        Args:
            path: Path to video file
            loop: Whether to loop
            name: Source name

        Returns:
            Source ID
        """
        return await self._source_manager.add_video(Path(path), loop, name)

    async def add_avatar_source(
        self,
        avatar_id: str = "kagami",
        name: str | None = None,
    ) -> str:
        """Add AI avatar source.

        The avatar can speak in real-time via generate_and_speak().

        Args:
            avatar_id: Avatar identifier
            name: Source name

        Returns:
            Source ID
        """
        return await self._source_manager.add_avatar(avatar_id, name)

    async def add_audio_source(
        self,
        device_id: int = 0,
        name: str | None = None,
    ) -> str:
        """Add audio input source.

        Args:
            device_id: Audio device index
            name: Source name

        Returns:
            Source ID
        """
        return await self._source_manager.add_audio(device_id, name)

    async def remove_source(self, source_id: str) -> None:
        """Remove a source."""
        await self._source_manager.remove(source_id)

    def list_sources(self) -> list[dict]:
        """List all sources."""
        return self._source_manager.list_all()

    # -------------------------------------------------------------------------
    # SCENE MANAGEMENT
    # -------------------------------------------------------------------------

    def create_scene(
        self,
        name: str,
        copy_from: str | None = None,
    ) -> Any:
        """Create a new scene.

        Args:
            name: Scene name
            copy_from: Optional scene to copy from

        Returns:
            Scene object
        """
        return self._scene_manager.create_scene(name, copy_from)

    def get_scene(self, name: str) -> Any:
        """Get a scene by name."""
        return self._scene_manager.get_scene(name)

    async def switch_scene(
        self,
        name: str,
        transition: str = "cut",
        duration: float = 0.5,
    ) -> None:
        """Switch to a scene with optional transition.

        Args:
            name: Target scene name
            transition: Transition type (cut, fade, dissolve, wipe, zoom)
            duration: Transition duration in seconds
        """
        await self._scene_manager.switch_scene(
            name,
            transition=transition,
            duration=duration,
        )
        if self._session:
            self._session.active_scene = name

    def list_scenes(self) -> list[str]:
        """List all scene names."""
        return self._scene_manager.list_scenes()

    def add_overlay(
        self,
        scene_name: str,
        source_id: str,
        position: tuple[int, int] | str = "center",
        scale: float = 1.0,
        z_index: int = 0,
    ) -> None:
        """Add a source as overlay to a scene."""
        scene = self._scene_manager.get_scene(scene_name)
        scene.add_overlay(source_id, position, scale, z_index)

    def add_lower_third(
        self,
        scene_name: str,
        title: str,
        subtitle: str = "",
        style: str = "default",
    ) -> str:
        """Add a lower third to a scene.

        Args:
            scene_name: Target scene
            title: Main text
            subtitle: Secondary text
            style: Style preset

        Returns:
            Lower third ID
        """
        scene = self._scene_manager.get_scene(scene_name)
        return scene.add_lower_third(title, subtitle, style)

    # -------------------------------------------------------------------------
    # OUTPUT MANAGEMENT
    # -------------------------------------------------------------------------

    async def start_recording(
        self,
        path: Path | str | None = None,
        format: OutputFormat = OutputFormat.MP4,
    ) -> Path:
        """Start recording to file.

        Args:
            path: Output path (auto-generated if None)
            format: Output format

        Returns:
            Path to output file
        """
        if path is None:
            timestamp = int(time.time())
            path = self.config.output_dir / f"recording_{timestamp}.{format.value}"
        else:
            path = Path(path)

        await self._output_manager.start_recording(path, format)

        if self._session:
            self._session.is_recording = True

        logger.info(f"Recording started: {path}")
        return path

    async def stop_recording(self) -> Path | None:
        """Stop recording.

        Returns:
            Path to recorded file
        """
        path = await self._output_manager.stop_recording()
        if self._session:
            self._session.is_recording = False
        logger.info(f"Recording stopped: {path}")
        return path

    async def start_streaming(
        self,
        url: str | None = None,
        platform: StreamingPlatform = StreamingPlatform.CUSTOM,
        stream_key: str | None = None,
    ) -> None:
        """Start streaming to RTMP server.

        Args:
            url: RTMP URL (built from platform if None)
            platform: Streaming platform preset
            stream_key: Stream key for platform presets
        """
        await self._output_manager.start_streaming(url, platform, stream_key)
        if self._session:
            self._session.is_streaming = True
        logger.info(f"Streaming started: {platform.value}")

    async def stop_streaming(self) -> None:
        """Stop streaming."""
        await self._output_manager.stop_streaming()
        if self._session:
            self._session.is_streaming = False
        logger.info("Streaming stopped")

    async def start_virtual_camera(self) -> None:
        """Start virtual camera output.

        The virtual camera appears as a webcam in other apps
        like Zoom, Teams, Discord, etc.
        """
        await self._output_manager.start_virtual_camera()
        if self._session:
            self._session.is_virtual_cam = True
        logger.info("Virtual camera started")

    async def stop_virtual_camera(self) -> None:
        """Stop virtual camera."""
        await self._output_manager.stop_virtual_camera()
        if self._session:
            self._session.is_virtual_cam = False
        logger.info("Virtual camera stopped")

    async def start_multistream(
        self,
        platforms: list[tuple[StreamingPlatform, str]],
    ) -> None:
        """Start streaming to multiple platforms.

        Args:
            platforms: List of (platform, stream_key) tuples
        """
        await self._output_manager.start_multistream(platforms)
        if self._session:
            self._session.is_streaming = True
        logger.info(f"Multistreaming to {len(platforms)} platforms")

    # -------------------------------------------------------------------------
    # AI GENERATION
    # -------------------------------------------------------------------------

    async def generate_image(
        self,
        prompt: str,
        aspect: str = "16:9",
    ) -> str:
        """Generate an image and add as source.

        Args:
            prompt: Image generation prompt
            aspect: Aspect ratio

        Returns:
            Source ID for the generated image
        """
        result = await self._generation_hub.generate_image(prompt, aspect)
        return await self.add_image_source(result.path, name=f"gen_{prompt[:20]}")

    async def generate_video(
        self,
        prompt: str,
        duration: float = 5.0,
    ) -> str:
        """Generate a video and add as source.

        Args:
            prompt: Video generation prompt
            duration: Duration in seconds

        Returns:
            Source ID for the generated video
        """
        result = await self._generation_hub.generate_video(prompt, duration)
        return await self.add_video_source(result.path, name=f"gen_{prompt[:20]}")

    async def generate_and_speak(
        self,
        text: str,
        avatar_source: str | None = None,
    ) -> None:
        """Generate speech and optionally animate avatar.

        Args:
            text: Text to speak
            avatar_source: Avatar source ID to animate (if any)
        """
        await self._generation_hub.generate_and_speak(
            text=text,
            avatar_source=avatar_source,
            source_manager=self._source_manager,
        )

    async def present(
        self,
        topic: str,
        style: str = "announcement",
        mood: str = "warm",
        duration: str = "auto",
        output_path: Path | str | None = None,
    ):
        """Create a presentation video (kagami.present integration).

        Args:
            topic: Presentation topic
            style: Presentation style
            mood: Emotional tone
            duration: Target duration
            output_path: Output path

        Returns:
            PresentationResult
        """
        from kagami.present import present

        return await present(
            topic=topic,
            style=style,
            mood=mood,
            duration=duration,
            output_path=output_path,
        )

    # -------------------------------------------------------------------------
    # REAL-TIME PIPELINE
    # -------------------------------------------------------------------------

    async def _run_pipeline(self) -> None:
        """Run the real-time processing pipeline."""
        self._running = True

        while self._running:
            try:
                # Get current scene composition
                frame = await self._scene_manager.render_frame()

                # Process through pipeline stages
                if self._pipeline:
                    frame = await self._pipeline.process(frame)

                # Send to outputs
                await self._output_manager.send_frame(frame)

                if self._session:
                    self._session.frame_count += 1

                # Maintain frame rate
                await asyncio.sleep(1 / self.config.fps)

            except Exception as e:
                logger.error(f"Pipeline error: {e}")
                if self._session:
                    self._session.dropped_frames += 1

    def get_stats(self) -> dict:
        """Get session statistics."""
        if not self._session:
            return {}

        duration = time.time() - self._session.started_at
        fps_actual = self._session.frame_count / duration if duration > 0 else 0

        return {
            "session_id": self._session.session_id,
            "duration_s": duration,
            "frame_count": self._session.frame_count,
            "dropped_frames": self._session.dropped_frames,
            "fps_actual": fps_actual,
            "is_recording": self._session.is_recording,
            "is_streaming": self._session.is_streaming,
            "is_virtual_cam": self._session.is_virtual_cam,
            "active_scene": self._session.active_scene,
            "source_count": len(self._source_manager.list_all()),
            "scene_count": len(self._scene_manager.list_scenes()),
        }


# =============================================================================
# CONVENIENCE API
# =============================================================================


@asynccontextmanager
async def Studio(config: StudioConfig | None = None) -> AsyncIterator[StudioEngine]:
    """Context manager for studio sessions.

    Usage:
        async with Studio() as studio:
            avatar = await studio.add_avatar_source("kagami")
            await studio.start_recording()
            await studio.generate_and_speak("Hello!")
            await studio.stop_recording()
    """
    engine = StudioEngine(config)
    await engine.start_session()

    try:
        yield engine
    finally:
        await engine.stop_session()
