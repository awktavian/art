from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class TimelineSynchronizer:
    """Synchronizes animation timelines."""

    def synchronize(
        self,
        deca_timeline: dict[str, Any],
        audio2face_timeline: dict[str, Any],
        target_fps: int = 30,
    ) -> dict[str, Any]:
        """Synchronize animations from different sources."""
        deca_keyframes = np.array(deca_timeline.get("keyframes", []))
        deca_values = np.array(deca_timeline.get("values", []))
        audio2face_keyframes = np.array(audio2face_timeline.get("keyframes", []))
        audio2face_values = np.array(audio2face_timeline.get("values", []))

        start_time = 0.0
        end_time = max(
            deca_keyframes[-1] if len(deca_keyframes) > 0 else 0.0,
            audio2face_keyframes[-1] if len(audio2face_keyframes) > 0 else 0.0,
        )

        num_frames = int(end_time * target_fps) + 1
        uniform_keyframes = np.linspace(start_time, end_time, num_frames)

        deca_interpolated = np.interp(uniform_keyframes, deca_keyframes, deca_values)
        audio2face_interpolated = np.interp(
            uniform_keyframes, audio2face_keyframes, audio2face_values
        )

        return {
            "keyframes": uniform_keyframes.tolist(),
            "deca_values": deca_interpolated.tolist(),
            "audio2face_values": audio2face_interpolated.tolist(),
            "fps": target_fps,
            "duration": end_time,
        }
