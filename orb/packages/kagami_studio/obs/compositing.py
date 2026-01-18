"""OBS Compositing — Real-time layer composition in OBS.

Provides compositing primitives for building complex OBS scenes:
- Layer management with blend modes
- Position and scale control
- Crop and mask operations
- Pre-built layout factories

This module focuses on OBS-specific compositing.
For video file compositing, see kagami_studio.compositing.

Usage:
    from kagami_studio.obs import OBSController, OBSCompositor

    async with connect_obs() as obs:
        compositor = OBSCompositor(obs)

        # Create PIP layout
        await compositor.create_pip(
            main_source="GameCapture",
            pip_source="Webcam",
            pip_corner="bottom-right",
        )

        # Create split screen
        await compositor.create_split_screen(
            left_source="Camera1",
            right_source="Camera2",
        )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kagami_studio.obs.client import OBSController

logger = logging.getLogger(__name__)


class LayerBlendMode(str, Enum):
    """Layer blend modes (requires OBS blend mode filter)."""

    NORMAL = "normal"
    ADDITIVE = "additive"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    SCREEN = "screen"
    OVERLAY = "overlay"


@dataclass
class CompositeLayer:
    """Layer in a composite."""

    source_name: str
    position: tuple[float, float] = (0, 0)
    scale: tuple[float, float] = (1.0, 1.0)
    rotation: float = 0
    opacity: float = 1.0
    blend_mode: LayerBlendMode = LayerBlendMode.NORMAL
    visible: bool = True

    # Crop
    crop_left: int = 0
    crop_right: int = 0
    crop_top: int = 0
    crop_bottom: int = 0

    # Z-order (higher = on top)
    z_index: int = 0


class OBSCompositor:
    """Real-time compositor for OBS scenes.

    Provides high-level compositing operations that translate
    to OBS scene item transforms and filters.
    """

    def __init__(
        self,
        obs: OBSController,
        canvas_width: int = 1920,
        canvas_height: int = 1080,
    ):
        """Initialize compositor.

        Args:
            obs: OBS controller instance
            canvas_width: Canvas width
            canvas_height: Canvas height
        """
        self.obs = obs
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self._layers: dict[str, CompositeLayer] = {}

    async def add_layer(
        self,
        layer: CompositeLayer,
        scene_name: str | None = None,
    ) -> None:
        """Add compositing layer to scene.

        Args:
            layer: Layer definition
            scene_name: Target scene (current if None)
        """
        self._layers[layer.source_name] = layer

        # Apply transform
        await self.obs.set_source_transform(
            layer.source_name,
            scene_name=scene_name,
            position=layer.position,
            scale=layer.scale,
            rotation=layer.rotation,
            crop={
                "left": layer.crop_left,
                "right": layer.crop_right,
                "top": layer.crop_top,
                "bottom": layer.crop_bottom,
            },
        )

        # Apply visibility
        await self.obs.set_source_visible(layer.source_name, layer.visible, scene_name)

        # Apply opacity via color correction filter
        if layer.opacity < 1.0:
            from kagami_studio.obs.filters import create_color_correction_filter

            await self.obs.add_filter(
                layer.source_name,
                "opacity",
                "color_filter_v2",
                create_color_correction_filter(opacity=layer.opacity),
            )

    async def update_layer(
        self,
        source_name: str,
        scene_name: str | None = None,
        position: tuple[float, float] | None = None,
        scale: tuple[float, float] | None = None,
        rotation: float | None = None,
        opacity: float | None = None,
        visible: bool | None = None,
    ) -> None:
        """Update layer properties.

        Args:
            source_name: Source to update
            scene_name: Scene (current if None)
            position: New position
            scale: New scale
            rotation: New rotation
            opacity: New opacity
            visible: New visibility
        """
        layer = self._layers.get(source_name)
        if layer:
            if position is not None:
                layer.position = position
            if scale is not None:
                layer.scale = scale
            if rotation is not None:
                layer.rotation = rotation
            if opacity is not None:
                layer.opacity = opacity
            if visible is not None:
                layer.visible = visible

        # Apply transform updates
        await self.obs.set_source_transform(
            source_name,
            scene_name=scene_name,
            position=position,
            scale=scale,
            rotation=rotation,
        )

        if visible is not None:
            await self.obs.set_source_visible(source_name, visible, scene_name)

        if opacity is not None:
            await self.obs.set_filter_settings(
                source_name,
                "opacity",
                {"opacity": opacity},
            )

    async def remove_layer(
        self,
        source_name: str,
        scene_name: str | None = None,
    ) -> None:
        """Remove layer from composition.

        Args:
            source_name: Source to remove
            scene_name: Scene (current if None)
        """
        if source_name in self._layers:
            del self._layers[source_name]

        await self.obs.remove_source(source_name, scene_name)

    # =========================================================================
    # PRE-BUILT LAYOUTS
    # =========================================================================

    async def create_pip(
        self,
        main_source: str,
        pip_source: str,
        scene_name: str | None = None,
        pip_corner: str = "bottom-right",
        pip_size: float = 0.25,
        pip_margin: int = 40,
    ) -> None:
        """Create picture-in-picture layout.

        Args:
            main_source: Main/background source
            pip_source: PIP source
            scene_name: Target scene
            pip_corner: 'top-left', 'top-right', 'bottom-left', 'bottom-right'
            pip_size: PIP size as fraction of canvas
            pip_margin: Margin from edges
        """
        # Main source fills canvas
        main_layer = CompositeLayer(
            source_name=main_source,
            position=(0, 0),
            scale=(1.0, 1.0),
            z_index=0,
        )
        await self.add_layer(main_layer, scene_name)

        # Calculate PIP position
        pip_w = self.canvas_width * pip_size
        pip_h = self.canvas_height * pip_size

        positions = {
            "top-left": (pip_margin, pip_margin),
            "top-right": (self.canvas_width - pip_w - pip_margin, pip_margin),
            "bottom-left": (pip_margin, self.canvas_height - pip_h - pip_margin),
            "bottom-right": (
                self.canvas_width - pip_w - pip_margin,
                self.canvas_height - pip_h - pip_margin,
            ),
        }

        pos = positions.get(pip_corner, positions["bottom-right"])

        pip_layer = CompositeLayer(
            source_name=pip_source,
            position=pos,
            scale=(pip_size, pip_size),
            z_index=1,
        )
        await self.add_layer(pip_layer, scene_name)

        logger.info(f"Created PIP layout: {main_source} + {pip_source} ({pip_corner})")

    async def create_split_screen(
        self,
        left_source: str,
        right_source: str,
        scene_name: str | None = None,
        split_ratio: float = 0.5,
        gap: int = 10,
    ) -> None:
        """Create side-by-side split screen.

        Args:
            left_source: Left source
            right_source: Right source
            scene_name: Target scene
            split_ratio: Split position (0.5 = center)
            gap: Gap between sources
        """
        left_w = self.canvas_width * split_ratio - gap // 2

        # Left source
        left_layer = CompositeLayer(
            source_name=left_source,
            position=(0, 0),
            scale=(split_ratio - 0.01, 1.0),  # Slight scale to fit
            crop_right=int(self.canvas_width * (1 - split_ratio)),
            z_index=0,
        )
        await self.add_layer(left_layer, scene_name)

        # Right source
        right_layer = CompositeLayer(
            source_name=right_source,
            position=(left_w + gap, 0),
            scale=(1 - split_ratio - 0.01, 1.0),
            crop_left=int(self.canvas_width * split_ratio),
            z_index=0,
        )
        await self.add_layer(right_layer, scene_name)

        logger.info(f"Created split screen: {left_source} | {right_source}")

    async def create_corner_camera(
        self,
        main_source: str,
        camera_source: str,
        scene_name: str | None = None,
        corner: str = "bottom-right",
        camera_size: float = 0.2,
        circular: bool = True,
        border_width: int = 4,
        border_color: int = 0xFFFFFF,
    ) -> None:
        """Create corner camera (common streaming layout).

        Args:
            main_source: Main content (game, screen, etc.)
            camera_source: Camera/webcam
            scene_name: Target scene
            corner: Which corner
            camera_size: Camera size as fraction
            circular: Use circular mask
            border_width: Border width
            border_color: Border color (RGB)
        """
        # Main source
        main_layer = CompositeLayer(
            source_name=main_source,
            position=(0, 0),
            scale=(1.0, 1.0),
            z_index=0,
        )
        await self.add_layer(main_layer, scene_name)

        # Camera
        cam_w = self.canvas_width * camera_size
        cam_h = self.canvas_height * camera_size
        margin = 30

        positions = {
            "top-left": (margin, margin),
            "top-right": (self.canvas_width - cam_w - margin, margin),
            "bottom-left": (margin, self.canvas_height - cam_h - margin),
            "bottom-right": (
                self.canvas_width - cam_w - margin,
                self.canvas_height - cam_h - margin,
            ),
        }

        pos = positions.get(corner, positions["bottom-right"])

        cam_layer = CompositeLayer(
            source_name=camera_source,
            position=pos,
            scale=(camera_size, camera_size),
            z_index=1,
        )
        await self.add_layer(cam_layer, scene_name)

        # Add circular mask if requested
        if circular:
            # This requires the "Image Mask/Blend" filter
            # with a circular mask image

            await self.obs.add_filter(
                camera_source,
                "circular_mask",
                "mask_filter",
                {"type": 0},  # Alpha mask type
            )

        logger.info(f"Created corner camera: {main_source} + {camera_source} ({corner})")

    async def create_documentary_layout(
        self,
        video_source: str,
        text_source: str,
        scene_name: str | None = None,
        video_width_ratio: float = 0.65,
    ) -> None:
        """Create DCC-style documentary layout.

        Video on left, text/overlay on right.

        Args:
            video_source: Video content source
            text_source: Text/overlay source
            scene_name: Target scene
            video_width_ratio: Video panel width ratio
        """
        # Video panel (left)
        video_w = self.canvas_width * video_width_ratio

        video_layer = CompositeLayer(
            source_name=video_source,
            position=(0, 0),
            scale=(video_width_ratio, 1.0),
            z_index=0,
        )
        await self.add_layer(video_layer, scene_name)

        # Text panel (right)
        text_layer = CompositeLayer(
            source_name=text_source,
            position=(video_w, 0),
            scale=(1 - video_width_ratio, 1.0),
            z_index=1,
        )
        await self.add_layer(text_layer, scene_name)

        logger.info(f"Created documentary layout: {video_source} | {text_source}")

    async def create_interview_layout(
        self,
        host_source: str,
        guest_source: str,
        background_source: str | None = None,
        scene_name: str | None = None,
    ) -> None:
        """Create interview/podcast layout.

        Args:
            host_source: Host camera
            guest_source: Guest camera
            background_source: Optional background
            scene_name: Target scene
        """
        # Background
        if background_source:
            bg_layer = CompositeLayer(
                source_name=background_source,
                position=(0, 0),
                scale=(1.0, 1.0),
                z_index=0,
            )
            await self.add_layer(bg_layer, scene_name)

        # Host (left, slightly larger)
        host_scale = 0.55
        host_layer = CompositeLayer(
            source_name=host_source,
            position=(50, int(self.canvas_height * 0.1)),
            scale=(host_scale, host_scale),
            z_index=1,
        )
        await self.add_layer(host_layer, scene_name)

        # Guest (right)
        guest_scale = 0.45
        guest_layer = CompositeLayer(
            source_name=guest_source,
            position=(int(self.canvas_width * 0.5) + 50, int(self.canvas_height * 0.1)),
            scale=(guest_scale, guest_scale),
            z_index=1,
        )
        await self.add_layer(guest_layer, scene_name)

        logger.info(f"Created interview layout: {host_source} + {guest_source}")


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_pip_layout(
    main_source: str,
    pip_source: str,
    pip_corner: str = "bottom-right",
    pip_size: float = 0.25,
    pip_margin: int = 40,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
) -> list[CompositeLayer]:
    """Create PIP layout layers (without OBS connection).

    Returns layer definitions that can be applied later.
    """
    # Main
    layers = [
        CompositeLayer(
            source_name=main_source,
            position=(0, 0),
            scale=(1.0, 1.0),
            z_index=0,
        )
    ]

    # PIP position
    pip_w = canvas_width * pip_size
    pip_h = canvas_height * pip_size

    positions = {
        "top-left": (pip_margin, pip_margin),
        "top-right": (canvas_width - pip_w - pip_margin, pip_margin),
        "bottom-left": (pip_margin, canvas_height - pip_h - pip_margin),
        "bottom-right": (canvas_width - pip_w - pip_margin, canvas_height - pip_h - pip_margin),
    }

    pos = positions.get(pip_corner, positions["bottom-right"])

    layers.append(
        CompositeLayer(
            source_name=pip_source,
            position=pos,
            scale=(pip_size, pip_size),
            z_index=1,
        )
    )

    return layers


def create_side_by_side_layout(
    left_source: str,
    right_source: str,
    split_ratio: float = 0.5,
    gap: int = 10,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
) -> list[CompositeLayer]:
    """Create side-by-side layout layers."""
    left_w = canvas_width * split_ratio - gap // 2

    return [
        CompositeLayer(
            source_name=left_source,
            position=(0, 0),
            scale=(split_ratio - 0.01, 1.0),
            z_index=0,
        ),
        CompositeLayer(
            source_name=right_source,
            position=(left_w + gap, 0),
            scale=(1 - split_ratio - 0.01, 1.0),
            z_index=0,
        ),
    ]


def create_corner_cam_layout(
    main_source: str,
    camera_source: str,
    corner: str = "bottom-right",
    camera_size: float = 0.2,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
) -> list[CompositeLayer]:
    """Create corner camera layout layers."""
    cam_w = canvas_width * camera_size
    cam_h = canvas_height * camera_size
    margin = 30

    positions = {
        "top-left": (margin, margin),
        "top-right": (canvas_width - cam_w - margin, margin),
        "bottom-left": (margin, canvas_height - cam_h - margin),
        "bottom-right": (canvas_width - cam_w - margin, canvas_height - cam_h - margin),
    }

    pos = positions.get(corner, positions["bottom-right"])

    return [
        CompositeLayer(
            source_name=main_source,
            position=(0, 0),
            scale=(1.0, 1.0),
            z_index=0,
        ),
        CompositeLayer(
            source_name=camera_source,
            position=pos,
            scale=(camera_size, camera_size),
            z_index=1,
        ),
    ]
