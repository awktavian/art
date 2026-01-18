"""Recording Output — File recording using FFmpeg."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import numpy as np

from kagami_studio.outputs.base import Output, OutputState, OutputType

logger = logging.getLogger(__name__)


class RecordingOutput(Output):
    """Records video to file using FFmpeg."""

    def __init__(self, path: Path, config: Any):
        super().__init__(OutputType.RECORDING)
        self.path = path
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._started = False

    async def start(self) -> None:
        """Start recording."""
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
            "-c:v",
            self.config.video_codec,
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(self.path),
        ]

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._started = True
        self.state = OutputState.ACTIVE

        logger.info(f"Recording started: {self.path}")

    async def stop(self) -> None:
        """Stop recording."""
        self.state = OutputState.STOPPING

        if self._process and self._process.stdin:
            self._process.stdin.close()
            await self._process.wait()

        self._process = None
        self._started = False
        self.state = OutputState.INACTIVE

        logger.info(f"Recording stopped: {self.path}")

    async def send_frame(self, frame: np.ndarray) -> None:
        """Write frame to FFmpeg."""
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
            logger.error(f"Recording frame error: {e}")
