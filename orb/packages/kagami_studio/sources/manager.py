"""Source Manager — Manages all input sources."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from kagami_studio.sources.base import Source

logger = logging.getLogger(__name__)


class SourceManager:
    """Manages all input sources for the studio."""

    def __init__(self, config: Any):
        self.config = config
        self._sources: dict[str, Source] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the source manager."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("SourceManager initialized")

    async def cleanup(self) -> None:
        """Stop all sources and cleanup."""
        if self._sources:
            await asyncio.gather(
                *[source.stop() for source in self._sources.values()], return_exceptions=True
            )
        self._sources.clear()

    def _generate_id(self, prefix: str) -> str:
        """Generate unique source ID."""
        return f"{prefix}_{uuid.uuid4().hex[:6]}"

    async def add_camera(
        self,
        device_id: int = 0,
        name: str | None = None,
    ) -> str:
        """Add a camera source."""
        from kagami_studio.sources.camera import CameraSource

        source_id = self._generate_id("cam")
        source_name = name or f"Camera {device_id}"

        source = CameraSource(
            source_id=source_id,
            name=source_name,
            device_id=device_id,
        )

        await source.start()
        self._sources[source_id] = source

        logger.info(f"Added camera source: {source_id}")
        return source_id

    async def add_screen(
        self,
        monitor: int = 0,
        name: str | None = None,
    ) -> str:
        """Add screen capture source."""
        from kagami_studio.sources.screen import ScreenSource

        source_id = self._generate_id("screen")
        source_name = name or f"Screen {monitor}"

        source = ScreenSource(
            source_id=source_id,
            name=source_name,
            monitor=monitor,
        )

        await source.start()
        self._sources[source_id] = source

        logger.info(f"Added screen source: {source_id}")
        return source_id

    async def add_image(
        self,
        path: Path,
        name: str | None = None,
    ) -> str:
        """Add image source."""
        from kagami_studio.sources.image import ImageSource

        source_id = self._generate_id("img")
        source_name = name or path.stem

        source = ImageSource(
            source_id=source_id,
            name=source_name,
            path=path,
        )

        await source.start()
        self._sources[source_id] = source

        logger.info(f"Added image source: {source_id}")
        return source_id

    async def add_video(
        self,
        path: Path,
        loop: bool = True,
        name: str | None = None,
    ) -> str:
        """Add video source."""
        from kagami_studio.sources.video import VideoSource

        source_id = self._generate_id("video")
        source_name = name or path.stem

        source = VideoSource(
            source_id=source_id,
            name=source_name,
            path=path,
            loop=loop,
        )

        await source.start()
        self._sources[source_id] = source

        logger.info(f"Added video source: {source_id}")
        return source_id

    async def add_avatar(
        self,
        avatar_id: str = "kagami",
        name: str | None = None,
    ) -> str:
        """Add AI avatar source."""
        from kagami_studio.sources.avatar import AvatarSource

        source_id = self._generate_id("avatar")
        source_name = name or f"Avatar {avatar_id}"

        source = AvatarSource(
            source_id=source_id,
            name=source_name,
            avatar_id=avatar_id,
        )

        await source.start()
        self._sources[source_id] = source

        logger.info(f"Added avatar source: {source_id}")
        return source_id

    async def add_audio(
        self,
        device_id: int = 0,
        name: str | None = None,
    ) -> str:
        """Add audio input source."""
        from kagami_studio.sources.audio import AudioSource

        source_id = self._generate_id("audio")
        source_name = name or f"Audio {device_id}"

        source = AudioSource(
            source_id=source_id,
            name=source_name,
            device_id=device_id,
        )

        await source.start()
        self._sources[source_id] = source

        logger.info(f"Added audio source: {source_id}")
        return source_id

    async def remove(self, source_id: str) -> None:
        """Remove a source."""
        if source_id in self._sources:
            source = self._sources[source_id]
            await source.stop()
            del self._sources[source_id]
            logger.info(f"Removed source: {source_id}")

    def get(self, source_id: str) -> Source | None:
        """Get a source by ID."""
        return self._sources.get(source_id)

    def list_all(self) -> list[dict]:
        """List all sources."""
        return [
            {
                "id": s.id,
                "name": s.name,
                "type": s.type.value,
                "state": s.state.value,
            }
            for s in self._sources.values()
        ]

    async def get_frame(self, source_id: str):
        """Get frame from a source."""
        source = self._sources.get(source_id)
        if source:
            return await source.get_frame()
        return None
