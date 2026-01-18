"""Transitions — Scene transition effects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class TransitionType(str, Enum):
    """Transition effect type."""

    CUT = "cut"
    FADE = "fade"
    DISSOLVE = "dissolve"
    WIPE_LEFT = "wipe_left"
    WIPE_RIGHT = "wipe_right"
    WIPE_UP = "wipe_up"
    WIPE_DOWN = "wipe_down"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"


@dataclass
class Transition:
    """A transition between scenes."""

    type: TransitionType
    duration: float = 0.5

    def apply(
        self,
        from_frame: np.ndarray,
        to_frame: np.ndarray,
        progress: float,
    ) -> np.ndarray:
        """Apply transition at given progress (0.0 - 1.0).

        Args:
            from_frame: Source scene frame
            to_frame: Target scene frame
            progress: Transition progress (0=source, 1=target)

        Returns:
            Blended frame
        """
        import cv2

        if self.type == TransitionType.CUT:
            return to_frame if progress >= 0.5 else from_frame

        elif self.type == TransitionType.FADE:
            # Simple crossfade
            return cv2.addWeighted(
                from_frame,
                1 - progress,
                to_frame,
                progress,
                0,
            )

        elif self.type == TransitionType.DISSOLVE:
            # Dissolve with slight blur at midpoint
            if 0.3 < progress < 0.7:
                # Add slight blur
                blurred_from = cv2.GaussianBlur(from_frame, (5, 5), 0)
                blurred_to = cv2.GaussianBlur(to_frame, (5, 5), 0)
                return cv2.addWeighted(
                    blurred_from,
                    1 - progress,
                    blurred_to,
                    progress,
                    0,
                )
            return cv2.addWeighted(
                from_frame,
                1 - progress,
                to_frame,
                progress,
                0,
            )

        elif self.type == TransitionType.WIPE_LEFT:
            h, w = from_frame.shape[:2]
            wipe_x = int(w * progress)
            result = from_frame.copy()
            result[:, :wipe_x] = to_frame[:, :wipe_x]
            return result

        elif self.type == TransitionType.WIPE_RIGHT:
            h, w = from_frame.shape[:2]
            wipe_x = int(w * (1 - progress))
            result = from_frame.copy()
            result[:, wipe_x:] = to_frame[:, wipe_x:]
            return result

        elif self.type == TransitionType.WIPE_UP:
            h, w = from_frame.shape[:2]
            wipe_y = int(h * progress)
            result = from_frame.copy()
            result[:wipe_y, :] = to_frame[:wipe_y, :]
            return result

        elif self.type == TransitionType.WIPE_DOWN:
            h, w = from_frame.shape[:2]
            wipe_y = int(h * (1 - progress))
            result = from_frame.copy()
            result[wipe_y:, :] = to_frame[wipe_y:, :]
            return result

        elif self.type == TransitionType.ZOOM_IN:
            h, w = from_frame.shape[:2]
            # Scale from 1.0 to 1.5, then cross to target
            if progress < 0.5:
                scale = 1.0 + progress
                new_w = int(w * scale)
                new_h = int(h * scale)
                scaled = cv2.resize(from_frame, (new_w, new_h))
                # Center crop
                x = (new_w - w) // 2
                y = (new_h - h) // 2
                return scaled[y : y + h, x : x + w]
            else:
                return cv2.addWeighted(
                    from_frame,
                    1 - progress,
                    to_frame,
                    progress,
                    0,
                )

        elif self.type == TransitionType.ZOOM_OUT:
            # Reverse of zoom_in
            h, w = from_frame.shape[:2]
            if progress < 0.5:
                return cv2.addWeighted(
                    from_frame,
                    1 - progress,
                    to_frame,
                    progress,
                    0,
                )
            else:
                scale = 1.5 - (progress - 0.5)
                new_w = int(w * scale)
                new_h = int(h * scale)
                scaled = cv2.resize(to_frame, (new_w, new_h))
                x = (new_w - w) // 2
                y = (new_h - h) // 2
                return scaled[y : y + h, x : x + w]

        elif self.type == TransitionType.SLIDE_LEFT:
            h, w = from_frame.shape[:2]
            offset = int(w * progress)
            result = np.zeros_like(from_frame)
            # From frame slides out left
            if w - offset > 0:
                result[:, : w - offset] = from_frame[:, offset:]
            # To frame slides in from right
            if offset > 0:
                result[:, w - offset :] = to_frame[:, :offset]
            return result

        elif self.type == TransitionType.SLIDE_RIGHT:
            h, w = from_frame.shape[:2]
            offset = int(w * progress)
            result = np.zeros_like(from_frame)
            # From frame slides out right
            if offset < w:
                result[:, offset:] = from_frame[:, : w - offset]
            # To frame slides in from left
            if offset > 0:
                result[:, :offset] = to_frame[:, w - offset :]
            return result

        # Default: crossfade
        return cv2.addWeighted(
            from_frame,
            1 - progress,
            to_frame,
            progress,
            0,
        )
