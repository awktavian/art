"""Overlays — Lower thirds, text, and graphics overlays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass
class Overlay:
    """Base overlay class."""

    id: str
    visible: bool = True
    opacity: float = 1.0


@dataclass
class TextOverlay(Overlay):
    """Simple text overlay."""

    text: str = ""
    font: str = "Arial"
    font_size: int = 32
    color: tuple[int, int, int] = (255, 255, 255)
    x: int = 0
    y: int = 0
    shadow: bool = True

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Render text onto frame."""
        import cv2

        if not self.visible or not self.text:
            return frame

        result = frame.copy()

        # Draw shadow
        if self.shadow:
            cv2.putText(
                result,
                self.text,
                (self.x + 2, self.y + 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                self.font_size / 32,
                (0, 0, 0),
                2,
                cv2.LINE_AA,
            )

        # Draw text
        cv2.putText(
            result,
            self.text,
            (self.x, self.y),
            cv2.FONT_HERSHEY_SIMPLEX,
            self.font_size / 32,
            self.color,
            2,
            cv2.LINE_AA,
        )

        return result


@dataclass
class LowerThird(Overlay):
    """Professional lower third overlay."""

    title: str = ""
    subtitle: str = ""
    style: Literal["default", "modern", "minimal", "news"] = "default"
    position: Literal["left", "center", "right"] = "left"

    # Style colors
    background_color: tuple[int, int, int] = (0, 0, 0)
    accent_color: tuple[int, int, int] = (0, 212, 170)  # Kagami cyan
    title_color: tuple[int, int, int] = (255, 255, 255)
    subtitle_color: tuple[int, int, int] = (200, 200, 200)

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Render lower third onto frame."""
        import cv2

        if not self.visible or not self.title:
            return frame

        result = frame.copy()
        h, w = frame.shape[:2]

        # Position
        if self.position == "left":
            x_start = 50
        elif self.position == "center":
            x_start = w // 4
        else:
            x_start = w // 2

        y_base = h - 150

        if self.style == "default":
            # Classic broadcast style
            # Background bar
            bar_h = 80 if self.subtitle else 50
            overlay = result.copy()
            cv2.rectangle(
                overlay,
                (x_start - 10, y_base - bar_h),
                (x_start + 400, y_base + 10),
                self.background_color,
                -1,
            )

            # Accent stripe
            cv2.rectangle(
                overlay,
                (x_start - 15, y_base - bar_h),
                (x_start - 10, y_base + 10),
                self.accent_color,
                -1,
            )

            # Blend
            result = cv2.addWeighted(overlay, 0.8, result, 0.2, 0)

            # Title
            cv2.putText(
                result,
                self.title,
                (x_start, y_base - 30 if self.subtitle else y_base - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                self.title_color,
                2,
                cv2.LINE_AA,
            )

            # Subtitle
            if self.subtitle:
                cv2.putText(
                    result,
                    self.subtitle,
                    (x_start, y_base - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    self.subtitle_color,
                    1,
                    cv2.LINE_AA,
                )

        elif self.style == "modern":
            # Clean modern style
            # Background pill
            bar_h = 70 if self.subtitle else 45
            overlay = result.copy()
            cv2.rectangle(
                overlay,
                (x_start, y_base - bar_h),
                (x_start + 350, y_base + 5),
                self.background_color,
                -1,
            )
            result = cv2.addWeighted(overlay, 0.85, result, 0.15, 0)

            # Title
            cv2.putText(
                result,
                self.title,
                (x_start + 15, y_base - 25 if self.subtitle else y_base - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                self.title_color,
                2,
                cv2.LINE_AA,
            )

            # Subtitle
            if self.subtitle:
                cv2.putText(
                    result,
                    self.subtitle,
                    (x_start + 15, y_base - 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    self.accent_color,
                    1,
                    cv2.LINE_AA,
                )

        elif self.style == "minimal":
            # Just text with accent
            cv2.putText(
                result,
                self.title,
                (x_start, y_base - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                self.title_color,
                2,
                cv2.LINE_AA,
            )

            # Accent underline
            cv2.line(
                result,
                (x_start, y_base - 10),
                (x_start + 80, y_base - 10),
                self.accent_color,
                3,
            )

            if self.subtitle:
                cv2.putText(
                    result,
                    self.subtitle,
                    (x_start, y_base + 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    self.subtitle_color,
                    1,
                    cv2.LINE_AA,
                )

        elif self.style == "news":
            # News ticker style
            # Full width bar
            overlay = result.copy()
            cv2.rectangle(
                overlay,
                (0, y_base - 60),
                (w, y_base + 10),
                self.background_color,
                -1,
            )

            # Accent bar at top
            cv2.rectangle(
                overlay,
                (0, y_base - 60),
                (w, y_base - 55),
                self.accent_color,
                -1,
            )

            result = cv2.addWeighted(overlay, 0.9, result, 0.1, 0)

            # Title (bold)
            cv2.putText(
                result,
                self.title.upper(),
                (50, y_base - 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                self.title_color,
                2,
                cv2.LINE_AA,
            )

            if self.subtitle:
                cv2.putText(
                    result,
                    self.subtitle,
                    (50, y_base - 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    self.subtitle_color,
                    1,
                    cv2.LINE_AA,
                )

        return result
