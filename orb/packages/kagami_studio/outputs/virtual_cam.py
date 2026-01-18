"""Virtual Camera Output — Virtual webcam for video calls."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from kagami_studio.outputs.base import Output, OutputState, OutputType

logger = logging.getLogger(__name__)


class VirtualCamOutput(Output):
    """Virtual camera output using pyvirtualcam.

    Allows Kagami Studio output to appear as a webcam
    in Zoom, Teams, Discord, Google Meet, etc.
    """

    def __init__(self, config: Any):
        super().__init__(OutputType.VIRTUAL_CAM)
        self.config = config
        self._cam = None

    async def start(self) -> None:
        """Start virtual camera."""
        self.state = OutputState.STARTING

        try:
            import pyvirtualcam

            width, height = self.config.resolution
            fps = self.config.fps

            # Try OBS virtual camera first, then fallback
            try:
                self._cam = pyvirtualcam.Camera(
                    width=width,
                    height=height,
                    fps=fps,
                    backend="obs",
                )
            except Exception:
                # Try other backends
                self._cam = pyvirtualcam.Camera(
                    width=width,
                    height=height,
                    fps=fps,
                )

            self.state = OutputState.ACTIVE
            logger.info(f"Virtual camera started: {self._cam.device}")

        except ImportError:
            logger.error("pyvirtualcam not installed: pip install pyvirtualcam")
            self.state = OutputState.ERROR
        except Exception as e:
            logger.error(f"Virtual camera failed: {e}")
            self.state = OutputState.ERROR

    async def stop(self) -> None:
        """Stop virtual camera."""
        self.state = OutputState.STOPPING

        if self._cam:
            self._cam.close()
            self._cam = None

        self.state = OutputState.INACTIVE
        logger.info("Virtual camera stopped")

    async def send_frame(self, frame: np.ndarray) -> None:
        """Send frame to virtual camera."""
        if not self._cam:
            return

        try:
            import cv2

            # Resize if needed
            h, w = frame.shape[:2]
            target_w, target_h = self.config.resolution

            if w != target_w or h != target_h:
                frame = cv2.resize(frame, (target_w, target_h))

            # Convert BGR to RGB (pyvirtualcam expects RGB)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Send to virtual camera
            self._cam.send(frame_rgb)
            self._cam.sleep_until_next_frame()

        except Exception as e:
            logger.error(f"Virtual camera frame error: {e}")
