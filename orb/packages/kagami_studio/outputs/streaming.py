"""Streaming Output — RTMP streaming using FFmpeg."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np

from kagami_studio.outputs.base import Output, OutputState, OutputType

logger = logging.getLogger(__name__)


class StreamingOutput(Output):
    """Streams video to RTMP server using FFmpeg."""

    def __init__(self, url: str, config: Any):
        super().__init__(OutputType.STREAMING)
        self.url = url
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._started = False

    async def start(self) -> None:
        """Start streaming."""
        self.state = OutputState.STARTING

        width, height = self.config.resolution
        fps = self.config.fps

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "-",
            # Video encoding for streaming
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-maxrate",
            self.config.video_bitrate,
            "-bufsize",
            "4500k",
            "-pix_fmt",
            "yuv420p",
            "-g",
            str(fps * 2),  # Keyframe interval
            # Audio (silence for now - will add audio input)
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-c:a",
            "aac",
            "-b:a",
            self.config.audio_bitrate,
            # Output
            "-f",
            "flv",
            self.url,
        ]

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._started = True
        self.state = OutputState.ACTIVE

        logger.info(f"Streaming started: {self.url[:50]}...")

    async def stop(self) -> None:
        """Stop streaming."""
        self.state = OutputState.STOPPING

        if self._process and self._process.stdin:
            self._process.stdin.close()
            await self._process.wait()

        self._process = None
        self._started = False
        self.state = OutputState.INACTIVE

        logger.info("Streaming stopped")

    async def send_frame(self, frame: np.ndarray) -> None:
        """Send frame to stream."""
        if not self._started or not self._process or not self._process.stdin:
            return

        try:
            # Resize if needed
            h, w = frame.shape[:2]
            target_w, target_h = self.config.resolution

            if w != target_w or h != target_h:
                import cv2

                frame = cv2.resize(frame, (target_w, target_h))

            self._process.stdin.write(frame.tobytes())
            await self._process.stdin.drain()

        except Exception as e:
            logger.error(f"Streaming frame error: {e}")
            self.state = OutputState.ERROR
