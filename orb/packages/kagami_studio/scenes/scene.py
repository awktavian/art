"""Scene — A composited view of sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class SceneItem:
    """An item in a scene (source with transform)."""

    source_id: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    z_index: int = 0
    visible: bool = True
    opacity: float = 1.0
    scale: float = 1.0
    rotation: float = 0.0
    crop: tuple[int, int, int, int] | None = None  # top, bottom, left, right


@dataclass
class Scene:
    """A scene containing multiple sources.

    Scenes are the main unit of composition - they define
    how sources are arranged and mixed together.
    """

    name: str
    width: int = 1920
    height: int = 1080
    background_color: tuple[int, int, int] = (0, 0, 0)
    items: list[SceneItem] = field(default_factory=list)
    lower_thirds: list[Any] = field(default_factory=list)
    overlays: list[Any] = field(default_factory=list)

    def add_source(
        self,
        source_id: str,
        position: tuple[int, int] | str = "center",
        scale: float = 1.0,
        z_index: int = 0,
    ) -> SceneItem:
        """Add a source to the scene.

        Args:
            source_id: Source ID to add
            position: (x, y) or preset ("center", "top-left", etc.)
            scale: Scale factor
            z_index: Layer order

        Returns:
            SceneItem
        """
        # Calculate position
        if isinstance(position, str):
            x, y = self._preset_position(position)
        else:
            x, y = position

        item = SceneItem(
            source_id=source_id,
            x=x,
            y=y,
            scale=scale,
            z_index=z_index,
        )

        self.items.append(item)
        # Sort by z_index
        self.items.sort(key=lambda i: i.z_index)

        return item

    def remove_source(self, source_id: str) -> None:
        """Remove a source from the scene."""
        self.items = [i for i in self.items if i.source_id != source_id]

    def _preset_position(self, preset: str) -> tuple[int, int]:
        """Convert position preset to coordinates."""
        presets = {
            "center": (self.width // 2, self.height // 2),
            "top-left": (0, 0),
            "top-right": (self.width, 0),
            "bottom-left": (0, self.height),
            "bottom-right": (self.width, self.height),
            "top-center": (self.width // 2, 0),
            "bottom-center": (self.width // 2, self.height),
        }
        return presets.get(preset, (0, 0))

    def add_overlay(
        self,
        source_id: str,
        position: tuple[int, int] | str,
        scale: float = 1.0,
        z_index: int = 100,
    ) -> SceneItem:
        """Add an overlay (high z-index source)."""
        return self.add_source(source_id, position, scale, z_index)

    def add_lower_third(
        self,
        title: str,
        subtitle: str = "",
        style: str = "default",
    ) -> str:
        """Add a lower third overlay.

        Returns:
            Lower third ID
        """
        from kagami_studio.scenes.overlays import LowerThird

        lt = LowerThird(
            id=f"lt_{len(self.lower_thirds)}",
            title=title,
            subtitle=subtitle,
            style=style,
        )
        self.lower_thirds.append(lt)
        return lt.id

    def remove_lower_third(self, lt_id: str) -> None:
        """Remove a lower third."""
        self.lower_thirds = [lt for lt in self.lower_thirds if lt.id != lt_id]

    async def render(self, source_manager: Any) -> np.ndarray:
        """Render the scene to a frame.

        Args:
            source_manager: SourceManager to get frames

        Returns:
            Composed frame (BGR numpy array)
        """
        import cv2

        # Start with background
        frame = np.full(
            (self.height, self.width, 3),
            self.background_color,
            dtype=np.uint8,
        )

        # Render items in z-order
        for item in self.items:
            if not item.visible:
                continue

            # Get source frame
            source_frame = await source_manager.get_frame(item.source_id)
            if source_frame is None:
                continue

            # Apply transforms
            if item.scale != 1.0:
                h, w = source_frame.shape[:2]
                new_w = int(w * item.scale)
                new_h = int(h * item.scale)
                source_frame = cv2.resize(source_frame, (new_w, new_h))

            if item.rotation != 0:
                h, w = source_frame.shape[:2]
                M = cv2.getRotationMatrix2D((w // 2, h // 2), item.rotation, 1)
                source_frame = cv2.warpAffine(source_frame, M, (w, h))

            # Apply opacity
            if item.opacity < 1.0:
                source_frame = (source_frame * item.opacity).astype(np.uint8)

            # Composite onto frame
            h, w = source_frame.shape[:2]
            x = item.x - w // 2  # Center on position
            y = item.y - h // 2

            # Clamp to frame bounds
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(self.width, x + w)
            y2 = min(self.height, y + h)

            src_x1 = x1 - x
            src_y1 = y1 - y
            src_x2 = src_x1 + (x2 - x1)
            src_y2 = src_y1 + (y2 - y1)

            if x2 > x1 and y2 > y1:
                if item.opacity < 1.0:
                    # Alpha blend
                    frame[y1:y2, x1:x2] = cv2.addWeighted(
                        frame[y1:y2, x1:x2],
                        1 - item.opacity,
                        source_frame[src_y1:src_y2, src_x1:src_x2],
                        item.opacity,
                        0,
                    )
                else:
                    frame[y1:y2, x1:x2] = source_frame[src_y1:src_y2, src_x1:src_x2]

        # Render lower thirds
        for lt in self.lower_thirds:
            frame = lt.render(frame)

        return frame
