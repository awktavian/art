"""Avatar Source — AI avatar with real-time animation."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import numpy as np

from kagami_studio.sources.base import Source, SourceState, SourceType

logger = logging.getLogger(__name__)


class AvatarSource(Source):
    """AI avatar source with real-time speech animation.

    Uses HeyGen streaming or pre-generated avatar videos.
    Can switch to idle animation when not speaking.
    """

    def __init__(self, source_id: str, name: str, avatar_id: str = "kagami"):
        super().__init__(source_id, name, SourceType.AVATAR)
        self.avatar_id = avatar_id
        self._frame = None
        self._idle_frame = None
        self._speaking = False
        self._video_queue: asyncio.Queue = asyncio.Queue()
        self._task = None

        # Avatar identity image paths
        self._identity_dir = Path("assets/identities") / avatar_id

    async def start(self) -> None:
        """Start the avatar source."""
        import cv2

        self.state = SourceState.STARTING

        # Load idle frame (identity image)
        identity_path = self._identity_dir / "halfbody_professional.png"
        if not identity_path.exists():
            # Try alternate paths
            identity_path = self._identity_dir / "reference_1.png"
        if not identity_path.exists():
            # Generate a placeholder
            self._idle_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            logger.warning(f"Avatar identity image not found: {identity_path}")
        else:
            self._idle_frame = cv2.imread(str(identity_path))

        if self._idle_frame is not None:
            self._height, self._width = self._idle_frame.shape[:2]
        else:
            self._width, self._height = 1920, 1080

        self._frame = self._idle_frame
        self._fps = 30.0

        # Start animation loop
        self._task = asyncio.create_task(self._animation_loop())
        self.state = SourceState.ACTIVE

        logger.info(f"Avatar source started: {self.avatar_id}")

    async def stop(self) -> None:
        """Stop the avatar source."""
        self.state = SourceState.INACTIVE

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _animation_loop(self) -> None:
        """Animation loop - plays queued videos or shows idle."""

        while self.state == SourceState.ACTIVE:
            try:
                # Check for queued video
                video_path = self._video_queue.get_nowait()
                await self._play_video(video_path)
            except asyncio.QueueEmpty:
                # Show idle frame
                self._frame = self._idle_frame
                await asyncio.sleep(1 / self._fps)

    async def _play_video(self, video_path: Path) -> None:
        """Play a generated avatar video."""
        import cv2

        self._speaking = True
        cap = cv2.VideoCapture(str(video_path))

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        while cap.isOpened() and self.state == SourceState.ACTIVE:
            ret, frame = cap.read()
            if not ret:
                break
            self._frame = frame
            await asyncio.sleep(1 / fps)

        cap.release()
        self._speaking = False
        self._frame = self._idle_frame

    async def get_frame(self) -> np.ndarray | None:
        """Get current frame."""
        return self._frame

    async def speak(self, text: str) -> None:
        """Generate and play speech animation.

        This uses HeyGen to generate the avatar video,
        then queues it for playback.
        """
        from kagami_media.production.generators.avatar import AvatarGenerator

        generator = AvatarGenerator()
        await generator.initialize()

        # Get identity image
        identity_path = self._identity_dir / "halfbody_professional.png"
        if not identity_path.exists():
            identity_path = self._identity_dir / "reference_1.png"

        if identity_path.exists():
            result = await generator.speak(
                image_path=identity_path,
                text=text,
            )
            # Queue the video for playback
            await self._video_queue.put(result.path)

    async def queue_video(self, video_path: Path) -> None:
        """Queue a pre-generated video for playback."""
        await self._video_queue.put(video_path)

    @property
    def is_speaking(self) -> bool:
        """Check if avatar is currently speaking."""
        return self._speaking
