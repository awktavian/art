"""Stinger Transitions — Video-based transitions with transparency.

Stinger transitions use video files with alpha channels to create
professional broadcast-style transitions. Common examples:
- Logo animations that wipe across the screen
- Particle effects that reveal the new scene
- Animated shapes or patterns

Usage:
    stinger = StingerTransition(
        video_path="transitions/logo_wipe.webm",
        cut_point=0.5,  # When to switch scenes
    )
    frame = stinger.apply(from_frame, to_frame, progress)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StingerTransition:
    """Video-based stinger transition.

    The stinger video should have:
    - Alpha channel for transparency
    - A "cut point" where the full screen is covered
    - Typical duration of 0.5-2 seconds
    """

    video_path: Path
    cut_point: float = 0.5  # Progress at which to switch scenes (0-1)
    reverse_out: bool = False  # Play in reverse for second half

    _frames: list[np.ndarray] | None = None
    _loaded: bool = False

    def load(self) -> None:
        """Load stinger video frames into memory."""
        if self._loaded:
            return

        cap = cv2.VideoCapture(str(self.video_path))
        self._frames = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            # Keep BGRA if available
            self._frames.append(frame)

        cap.release()
        self._loaded = True
        logger.info(f"Loaded stinger: {len(self._frames)} frames")

    def apply(
        self,
        from_frame: np.ndarray,
        to_frame: np.ndarray,
        progress: float,
    ) -> np.ndarray:
        """Apply stinger transition.

        Args:
            from_frame: Source scene frame
            to_frame: Target scene frame
            progress: Transition progress (0-1)

        Returns:
            Composited frame
        """
        if not self._loaded:
            self.load()

        if not self._frames:
            # Fall back to crossfade
            return cv2.addWeighted(from_frame, 1 - progress, to_frame, progress, 0)

        # Determine which scene to show
        if progress < self.cut_point:
            base_frame = from_frame.copy()
        else:
            base_frame = to_frame.copy()

        # Get stinger frame
        if self.reverse_out and progress >= self.cut_point:
            # Play reverse for second half
            local_progress = 1 - ((progress - self.cut_point) / (1 - self.cut_point))
        else:
            local_progress = progress

        frame_idx = int(local_progress * (len(self._frames) - 1))
        frame_idx = max(0, min(frame_idx, len(self._frames) - 1))
        stinger_frame = self._frames[frame_idx]

        # Resize stinger to match base frame
        h, w = base_frame.shape[:2]
        stinger_resized = cv2.resize(stinger_frame, (w, h))

        # Composite stinger over base
        if stinger_resized.shape[2] == 4:
            # Has alpha channel
            alpha = stinger_resized[:, :, 3:4] / 255.0
            rgb = stinger_resized[:, :, :3]
            result = (base_frame * (1 - alpha) + rgb * alpha).astype(np.uint8)
        else:
            # No alpha, blend
            result = cv2.addWeighted(base_frame, 0.5, stinger_resized, 0.5, 0)

        return result


class StingerLibrary:
    """Collection of stinger transitions.

    Manages a library of stinger videos for easy access.
    """

    def __init__(self, library_path: Path | None = None):
        self.library_path = library_path or Path("assets/transitions/stingers")
        self._stingers: dict[str, StingerTransition] = {}

    def load_all(self) -> None:
        """Load all stingers from library path."""
        if not self.library_path.exists():
            logger.warning(f"Stinger library not found: {self.library_path}")
            return

        for file in self.library_path.glob("*.webm"):
            name = file.stem
            self._stingers[name] = StingerTransition(video_path=file)

        for file in self.library_path.glob("*.mov"):
            name = file.stem
            if name not in self._stingers:
                self._stingers[name] = StingerTransition(video_path=file)

        logger.info(f"Loaded {len(self._stingers)} stingers")

    def get(self, name: str) -> StingerTransition | None:
        """Get a stinger by name."""
        return self._stingers.get(name)

    def list_available(self) -> list[str]:
        """List available stinger names."""
        return list(self._stingers.keys())

    def add(self, name: str, stinger: StingerTransition) -> None:
        """Add a stinger to the library."""
        self._stingers[name] = stinger
