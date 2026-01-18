"""Output Manager — Manages all outputs."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import numpy as np

from kagami_studio.outputs.base import Output, OutputState

logger = logging.getLogger(__name__)


class OutputManager:
    """Manages all output destinations."""

    def __init__(self, config: Any):
        self.config = config
        self._outputs: dict[str, Output] = {}
        self._recording: Any = None
        self._streaming: Any = None
        self._virtual_cam: Any = None

    async def initialize(self) -> None:
        """Initialize the output manager."""
        logger.info("OutputManager initialized")

    async def send_frame(self, frame: np.ndarray) -> None:
        """Send frame to all active outputs."""
        tasks = []
        for output in self._outputs.values():
            if output.state == OutputState.ACTIVE:
                tasks.append(output.send_frame(frame))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def start_recording(
        self,
        path: Path,
        format: Any,
    ) -> None:
        """Start recording to file."""
        from kagami_studio.outputs.recording import RecordingOutput

        self._recording = RecordingOutput(
            path=path,
            config=self.config,
        )
        await self._recording.start()
        self._outputs["recording"] = self._recording

    async def stop_recording(self) -> Path | None:
        """Stop recording."""
        if self._recording:
            path = self._recording.path
            await self._recording.stop()
            del self._outputs["recording"]
            self._recording = None
            return path
        return None

    async def start_streaming(
        self,
        url: str | None,
        platform: Any,
        stream_key: str | None,
    ) -> None:
        """Start RTMP streaming."""
        from kagami_studio.outputs.streaming import StreamingOutput

        # Build URL from platform if needed
        if url is None and platform and stream_key:
            platform_urls = {
                "twitch": f"rtmp://live.twitch.tv/app/{stream_key}",
                "youtube": f"rtmp://a.rtmp.youtube.com/live2/{stream_key}",
                "facebook": f"rtmps://live-api-s.facebook.com:443/rtmp/{stream_key}",
            }
            url = platform_urls.get(platform.value, url)

        if not url:
            raise ValueError("Streaming URL required")

        self._streaming = StreamingOutput(
            url=url,
            config=self.config,
        )
        await self._streaming.start()
        self._outputs["streaming"] = self._streaming

    async def stop_streaming(self) -> None:
        """Stop streaming."""
        if self._streaming:
            await self._streaming.stop()
            del self._outputs["streaming"]
            self._streaming = None

    async def start_multistream(
        self,
        platforms: list[tuple[Any, str]],
    ) -> None:
        """Start streaming to multiple platforms."""
        for platform, stream_key in platforms:
            try:
                await self.start_streaming(None, platform, stream_key)
            except Exception as e:
                logger.error(f"Failed to start {platform.value}: {e}")

    async def start_virtual_camera(self) -> None:
        """Start virtual camera output."""
        from kagami_studio.outputs.virtual_cam import VirtualCamOutput

        self._virtual_cam = VirtualCamOutput(config=self.config)
        await self._virtual_cam.start()
        self._outputs["virtual_cam"] = self._virtual_cam

    async def stop_virtual_camera(self) -> None:
        """Stop virtual camera."""
        if self._virtual_cam:
            await self._virtual_cam.stop()
            del self._outputs["virtual_cam"]
            self._virtual_cam = None

    def get_active_outputs(self) -> list[str]:
        """Get list of active output names."""
        return [
            name for name, output in self._outputs.items() if output.state == OutputState.ACTIVE
        ]
