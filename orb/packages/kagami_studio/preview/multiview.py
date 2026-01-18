"""Multi-View Preview — Monitor multiple sources and scenes.

Professional multi-view display showing:
- All scenes in grid layout
- Program output (live)
- Preview output (next scene)
- Individual sources
- Audio meters

Similar to OBS Multiview, vMix, and broadcast switchers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class MultiViewLayout(str, Enum):
    """Multi-view layout presets."""

    LAYOUT_4 = "4"  # 2x2 grid
    LAYOUT_6 = "6"  # 2 large + 4 small
    LAYOUT_8 = "8"  # 2 large + 6 small
    LAYOUT_9 = "9"  # 3x3 grid
    LAYOUT_16 = "16"  # 4x4 grid


@dataclass
class MultiViewConfig:
    """Multi-view configuration."""

    width: int = 1920
    height: int = 1080
    layout: MultiViewLayout = MultiViewLayout.LAYOUT_8
    show_labels: bool = True
    show_safe_areas: bool = True
    show_audio_meters: bool = True
    highlight_program: bool = True
    highlight_preview: bool = True
    background_color: tuple[int, int, int] = (30, 30, 30)
    label_color: tuple[int, int, int] = (255, 255, 255)
    program_border_color: tuple[int, int, int] = (0, 0, 255)  # Red in BGR
    preview_border_color: tuple[int, int, int] = (0, 255, 0)  # Green in BGR


class MultiView:
    """Multi-view preview renderer.

    Creates a composite view of multiple sources/scenes
    for monitoring during live production.
    """

    def __init__(self, config: MultiViewConfig | None = None):
        self.config = config or MultiViewConfig()
        self._scene_manager: Any = None
        self._source_manager: Any = None
        self._audio_mixer: Any = None
        self._program_scene: str | None = None
        self._preview_scene: str | None = None

    def set_managers(
        self,
        scene_manager: Any,
        source_manager: Any,
        audio_mixer: Any = None,
    ) -> None:
        """Set manager references."""
        self._scene_manager = scene_manager
        self._source_manager = source_manager
        self._audio_mixer = audio_mixer

    def set_program(self, scene_name: str) -> None:
        """Set the program (live) scene."""
        self._program_scene = scene_name

    def set_preview(self, scene_name: str) -> None:
        """Set the preview (next) scene."""
        self._preview_scene = scene_name

    async def render(self) -> np.ndarray:
        """Render multi-view display.

        Returns:
            Composite multi-view frame
        """
        # Create background
        frame = np.full(
            (self.config.height, self.config.width, 3),
            self.config.background_color,
            dtype=np.uint8,
        )

        if not self._scene_manager:
            return frame

        # Get layout configuration
        layout = self._get_layout_config()
        scenes = self._scene_manager.list_scenes()

        # Render each slot
        for i, slot in enumerate(layout["slots"]):
            if i >= len(scenes):
                continue

            scene_name = scenes[i]
            scene = self._scene_manager.get_scene(scene_name)

            # Render scene thumbnail
            if self._source_manager:
                scene_frame = await scene.render(self._source_manager)
            else:
                scene_frame = np.full(
                    (1080, 1920, 3),
                    scene.background_color,
                    dtype=np.uint8,
                )

            # Resize to slot size
            x, y, w, h = slot["x"], slot["y"], slot["w"], slot["h"]
            thumbnail = cv2.resize(scene_frame, (w, h))

            # Place in frame
            frame[y : y + h, x : x + w] = thumbnail

            # Add border
            border_color = self.config.background_color
            border_width = 2

            if self.config.highlight_program and scene_name == self._program_scene:
                border_color = self.config.program_border_color
                border_width = 4
            elif self.config.highlight_preview and scene_name == self._preview_scene:
                border_color = self.config.preview_border_color
                border_width = 3

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                border_color,
                border_width,
            )

            # Add label
            if self.config.show_labels:
                label = scene_name
                if scene_name == self._program_scene:
                    label = f"🔴 {scene_name}"
                elif scene_name == self._preview_scene:
                    label = f"🟢 {scene_name}"

                cv2.putText(
                    frame,
                    label,
                    (x + 10, y + 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    self.config.label_color,
                    1,
                    cv2.LINE_AA,
                )

            # Add safe area guides
            if self.config.show_safe_areas:
                self._draw_safe_areas(frame, x, y, w, h)

        # Add audio meters
        if self.config.show_audio_meters and self._audio_mixer:
            self._draw_audio_meters(frame)

        return frame

    def _get_layout_config(self) -> dict:
        """Get slot positions for current layout."""
        w, h = self.config.width, self.config.height
        padding = 10

        if self.config.layout == MultiViewLayout.LAYOUT_4:
            # 2x2 grid
            slot_w = (w - 3 * padding) // 2
            slot_h = (h - 3 * padding) // 2
            return {
                "slots": [
                    {"x": padding, "y": padding, "w": slot_w, "h": slot_h},
                    {"x": slot_w + 2 * padding, "y": padding, "w": slot_w, "h": slot_h},
                    {"x": padding, "y": slot_h + 2 * padding, "w": slot_w, "h": slot_h},
                    {
                        "x": slot_w + 2 * padding,
                        "y": slot_h + 2 * padding,
                        "w": slot_w,
                        "h": slot_h,
                    },
                ]
            }

        elif self.config.layout == MultiViewLayout.LAYOUT_8:
            # 2 large (program + preview) + 6 small
            large_w = (w - 3 * padding) // 2
            large_h = (h - 3 * padding) * 2 // 3
            small_w = (w - 4 * padding) // 3
            small_h = (h - 3 * padding) // 3

            return {
                "slots": [
                    # Top row - 2 large
                    {"x": padding, "y": padding, "w": large_w, "h": large_h},
                    {"x": large_w + 2 * padding, "y": padding, "w": large_w, "h": large_h},
                    # Bottom row - 6 small (we'll show first 6)
                    {"x": padding, "y": large_h + 2 * padding, "w": small_w, "h": small_h},
                    {
                        "x": small_w + 2 * padding,
                        "y": large_h + 2 * padding,
                        "w": small_w,
                        "h": small_h,
                    },
                    {
                        "x": 2 * small_w + 3 * padding,
                        "y": large_h + 2 * padding,
                        "w": small_w,
                        "h": small_h,
                    },
                    # Additional if needed
                    {
                        "x": padding,
                        "y": large_h + small_h + 3 * padding,
                        "w": small_w,
                        "h": small_h // 2,
                    },
                    {
                        "x": small_w + 2 * padding,
                        "y": large_h + small_h + 3 * padding,
                        "w": small_w,
                        "h": small_h // 2,
                    },
                    {
                        "x": 2 * small_w + 3 * padding,
                        "y": large_h + small_h + 3 * padding,
                        "w": small_w,
                        "h": small_h // 2,
                    },
                ]
            }

        elif self.config.layout == MultiViewLayout.LAYOUT_9:
            # 3x3 grid
            slot_w = (w - 4 * padding) // 3
            slot_h = (h - 4 * padding) // 3
            slots = []
            for row in range(3):
                for col in range(3):
                    slots.append(
                        {
                            "x": padding + col * (slot_w + padding),
                            "y": padding + row * (slot_h + padding),
                            "w": slot_w,
                            "h": slot_h,
                        }
                    )
            return {"slots": slots}

        elif self.config.layout == MultiViewLayout.LAYOUT_16:
            # 4x4 grid
            slot_w = (w - 5 * padding) // 4
            slot_h = (h - 5 * padding) // 4
            slots = []
            for row in range(4):
                for col in range(4):
                    slots.append(
                        {
                            "x": padding + col * (slot_w + padding),
                            "y": padding + row * (slot_h + padding),
                            "w": slot_w,
                            "h": slot_h,
                        }
                    )
            return {"slots": slots}

        # Default: 2x2
        slot_w = (w - 3 * padding) // 2
        slot_h = (h - 3 * padding) // 2
        return {
            "slots": [
                {"x": padding, "y": padding, "w": slot_w, "h": slot_h},
                {"x": slot_w + 2 * padding, "y": padding, "w": slot_w, "h": slot_h},
            ]
        }

    def _draw_safe_areas(
        self,
        frame: np.ndarray,
        x: int,
        y: int,
        w: int,
        h: int,
    ) -> None:
        """Draw title and action safe area guides."""
        # Title safe (90%)
        title_margin = int(min(w, h) * 0.05)
        cv2.rectangle(
            frame,
            (x + title_margin, y + title_margin),
            (x + w - title_margin, y + h - title_margin),
            (80, 80, 80),
            1,
        )

        # Action safe (95%)
        action_margin = int(min(w, h) * 0.025)
        cv2.rectangle(
            frame,
            (x + action_margin, y + action_margin),
            (x + w - action_margin, y + h - action_margin),
            (60, 60, 60),
            1,
        )

    def _draw_audio_meters(self, frame: np.ndarray) -> None:
        """Draw audio level meters."""
        if not self._audio_mixer:
            return

        levels = self._audio_mixer.get_levels()
        meter_width = 20
        meter_height = 200
        x_start = self.config.width - 100
        y_start = self.config.height - meter_height - 50

        for i, (channel_id, level) in enumerate(levels.items()):
            x = x_start + i * (meter_width + 5)
            if x > self.config.width - meter_width:
                break

            # Background
            cv2.rectangle(
                frame,
                (x, y_start),
                (x + meter_width, y_start + meter_height),
                (50, 50, 50),
                -1,
            )

            # Level bar
            level_height = int(level * meter_height)
            level_y = y_start + meter_height - level_height

            # Color based on level
            if level > 0.9:
                color = (0, 0, 255)  # Red
            elif level > 0.7:
                color = (0, 165, 255)  # Orange
            else:
                color = (0, 255, 0)  # Green

            cv2.rectangle(
                frame,
                (x, level_y),
                (x + meter_width, y_start + meter_height),
                color,
                -1,
            )

            # Label
            label = channel_id[:3] if channel_id != "master" else "M"
            cv2.putText(
                frame,
                label,
                (x + 2, y_start + meter_height + 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                self.config.label_color,
                1,
            )
