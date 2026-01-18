"""OBS Scene Management — Scene and transition definitions.

Provides typed scene composition for OBS:
- Scene creation and management
- Scene item positioning and transforms
- Transition types and settings

Usage:
    from kagami_studio.obs import OBSController, OBSScene, TransitionType

    async with connect_obs() as obs:
        # Create scene
        await obs.create_scene("Kagami Live")

        # Add sources with transforms
        await obs.add_source("Background", "image_source", {"file": "bg.png"})
        await obs.add_source("Avatar", "browser_source", avatar_settings)

        # Position avatar in corner
        await obs.set_source_transform(
            "Avatar",
            position=(1400, 600),
            scale=(0.5, 0.5),
        )

        # Switch with transition
        await obs.switch_scene("Kagami Live", transition="Fade", duration=500)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TransitionType(str, Enum):
    """Standard OBS transition types."""

    CUT = "cut_transition"
    FADE = "fade_transition"
    SWIPE = "swipe_transition"
    SLIDE = "slide_transition"
    STINGER = "obs_stinger_transition"
    FADE_TO_COLOR = "fade_to_color_transition"
    LUMA_WIPE = "wipe_transition"

    # Custom/Plugin transitions
    SHADER = "shader_transition"
    MOVE = "move_transition"


@dataclass
class OBSTransition:
    """OBS transition definition."""

    name: str
    kind: TransitionType
    duration: int = 500  # ms
    settings: dict = field(default_factory=dict)

    @classmethod
    def fade(cls, duration: int = 500) -> OBSTransition:
        """Create fade transition."""
        return cls(
            name="Fade",
            kind=TransitionType.FADE,
            duration=duration,
        )

    @classmethod
    def cut(cls) -> OBSTransition:
        """Create cut (instant) transition."""
        return cls(
            name="Cut",
            kind=TransitionType.CUT,
            duration=0,
        )

    @classmethod
    def stinger(
        cls,
        video_path: str,
        transition_point: int = 500,
        audio_fade_style: str = "crossfade",
    ) -> OBSTransition:
        """Create stinger transition.

        Args:
            video_path: Path to stinger video
            transition_point: Point in video where scene changes (ms)
            audio_fade_style: 'crossfade', 'fade_out_fade_in', or 'none'
        """
        return cls(
            name="Stinger",
            kind=TransitionType.STINGER,
            settings={
                "path": video_path,
                "transition_point_type": "time",
                "transition_point": transition_point,
                "audio_fade_style": audio_fade_style,
            },
        )

    @classmethod
    def slide(
        cls,
        direction: str = "left",
        duration: int = 500,
    ) -> OBSTransition:
        """Create slide transition.

        Args:
            direction: 'left', 'right', 'up', 'down'
            duration: Duration in ms
        """
        return cls(
            name="Slide",
            kind=TransitionType.SLIDE,
            duration=duration,
            settings={"direction": direction},
        )

    @classmethod
    def swipe(
        cls,
        direction: str = "left",
        duration: int = 500,
    ) -> OBSTransition:
        """Create swipe transition (with motion blur effect)."""
        return cls(
            name="Swipe",
            kind=TransitionType.SWIPE,
            duration=duration,
            settings={"direction": direction},
        )


@dataclass
class OBSSceneItem:
    """Item within an OBS scene."""

    name: str
    source_name: str
    scene_item_id: int | None = None
    visible: bool = True

    # Transform
    position_x: float = 0
    position_y: float = 0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation: float = 0
    alignment: int = 5  # Center (OBS alignment bitfield)

    # Crop
    crop_top: int = 0
    crop_bottom: int = 0
    crop_left: int = 0
    crop_right: int = 0

    # Bounds
    bounds_type: str = "OBS_BOUNDS_NONE"
    bounds_width: float = 0
    bounds_height: float = 0

    def to_transform_dict(self) -> dict:
        """Convert to OBS transform settings."""
        return {
            "positionX": self.position_x,
            "positionY": self.position_y,
            "scaleX": self.scale_x,
            "scaleY": self.scale_y,
            "rotation": self.rotation,
            "alignment": self.alignment,
            "cropTop": self.crop_top,
            "cropBottom": self.crop_bottom,
            "cropLeft": self.crop_left,
            "cropRight": self.crop_right,
            "boundsType": self.bounds_type,
            "boundsWidth": self.bounds_width,
            "boundsHeight": self.bounds_height,
        }


@dataclass
class OBSScene:
    """OBS scene definition."""

    name: str
    items: list[OBSSceneItem] = field(default_factory=list)
    is_group: bool = False

    def add_item(
        self,
        source_name: str,
        position: tuple[float, float] = (0, 0),
        scale: tuple[float, float] = (1.0, 1.0),
        visible: bool = True,
    ) -> OBSSceneItem:
        """Add item to scene.

        Args:
            source_name: Name of source to add
            position: (x, y) position
            scale: (x, y) scale
            visible: Initial visibility

        Returns:
            Created scene item
        """
        item = OBSSceneItem(
            name=f"{self.name}_{source_name}",
            source_name=source_name,
            visible=visible,
            position_x=position[0],
            position_y=position[1],
            scale_x=scale[0],
            scale_y=scale[1],
        )
        self.items.append(item)
        return item

    def get_item(self, source_name: str) -> OBSSceneItem | None:
        """Get item by source name."""
        for item in self.items:
            if item.source_name == source_name:
                return item
        return None


# =============================================================================
# SCENE LAYOUT PRESETS
# =============================================================================


def create_pip_scene_layout(
    background_source: str,
    pip_source: str,
    pip_corner: str = "bottom-right",
    pip_scale: float = 0.3,
    pip_margin: int = 40,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
) -> list[OBSSceneItem]:
    """Create picture-in-picture layout.

    Args:
        background_source: Background source name
        pip_source: PIP source name
        pip_corner: 'top-left', 'top-right', 'bottom-left', 'bottom-right'
        pip_scale: PIP size as fraction of canvas
        pip_margin: Margin from edges
        canvas_width: Canvas width
        canvas_height: Canvas height

    Returns:
        List of scene items
    """
    # Background fills canvas
    bg_item = OBSSceneItem(
        name="background",
        source_name=background_source,
        position_x=0,
        position_y=0,
        scale_x=1.0,
        scale_y=1.0,
    )

    # Calculate PIP position
    pip_w = canvas_width * pip_scale
    pip_h = canvas_height * pip_scale

    positions = {
        "top-left": (pip_margin, pip_margin),
        "top-right": (canvas_width - pip_w - pip_margin, pip_margin),
        "bottom-left": (pip_margin, canvas_height - pip_h - pip_margin),
        "bottom-right": (canvas_width - pip_w - pip_margin, canvas_height - pip_h - pip_margin),
    }

    pos = positions.get(pip_corner, positions["bottom-right"])

    pip_item = OBSSceneItem(
        name="pip",
        source_name=pip_source,
        position_x=pos[0],
        position_y=pos[1],
        scale_x=pip_scale,
        scale_y=pip_scale,
    )

    return [bg_item, pip_item]


def create_side_by_side_layout(
    left_source: str,
    right_source: str,
    split_ratio: float = 0.5,
    gap: int = 10,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
) -> list[OBSSceneItem]:
    """Create side-by-side layout.

    Args:
        left_source: Left source name
        right_source: Right source name
        split_ratio: Position of split (0.5 = center)
        gap: Gap between sources
        canvas_width: Canvas width
        canvas_height: Canvas height

    Returns:
        List of scene items
    """
    left_w = int(canvas_width * split_ratio) - gap // 2
    right_w = canvas_width - left_w - gap

    left_item = OBSSceneItem(
        name="left",
        source_name=left_source,
        position_x=0,
        position_y=0,
        bounds_type="OBS_BOUNDS_SCALE_INNER",
        bounds_width=left_w,
        bounds_height=canvas_height,
    )

    right_item = OBSSceneItem(
        name="right",
        source_name=right_source,
        position_x=left_w + gap,
        position_y=0,
        bounds_type="OBS_BOUNDS_SCALE_INNER",
        bounds_width=right_w,
        bounds_height=canvas_height,
    )

    return [left_item, right_item]


def create_lower_third_layout(
    main_source: str,
    lower_third_source: str,
    lower_third_height: float = 0.2,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
) -> list[OBSSceneItem]:
    """Create layout with lower third.

    Args:
        main_source: Main content source
        lower_third_source: Lower third overlay source
        lower_third_height: Height as fraction of canvas
        canvas_width: Canvas width
        canvas_height: Canvas height

    Returns:
        List of scene items
    """
    lt_h = int(canvas_height * lower_third_height)
    lt_y = canvas_height - lt_h

    main_item = OBSSceneItem(
        name="main",
        source_name=main_source,
        position_x=0,
        position_y=0,
        scale_x=1.0,
        scale_y=1.0,
    )

    lt_item = OBSSceneItem(
        name="lower_third",
        source_name=lower_third_source,
        position_x=0,
        position_y=lt_y,
        bounds_type="OBS_BOUNDS_SCALE_INNER",
        bounds_width=canvas_width,
        bounds_height=lt_h,
    )

    return [main_item, lt_item]


def create_interview_layout(
    host_source: str,
    guest_source: str,
    background_source: str | None = None,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
) -> list[OBSSceneItem]:
    """Create interview layout (two people talking).

    Args:
        host_source: Host camera source
        guest_source: Guest camera source
        background_source: Optional background
        canvas_width: Canvas width
        canvas_height: Canvas height

    Returns:
        List of scene items
    """
    items = []

    if background_source:
        items.append(
            OBSSceneItem(
                name="background",
                source_name=background_source,
                position_x=0,
                position_y=0,
                scale_x=1.0,
                scale_y=1.0,
            )
        )

    # Host on left (slightly larger)
    items.append(
        OBSSceneItem(
            name="host",
            source_name=host_source,
            position_x=50,
            position_y=canvas_height * 0.1,
            scale_x=0.55,
            scale_y=0.55,
        )
    )

    # Guest on right
    items.append(
        OBSSceneItem(
            name="guest",
            source_name=guest_source,
            position_x=canvas_width * 0.5 + 50,
            position_y=canvas_height * 0.1,
            scale_x=0.45,
            scale_y=0.45,
        )
    )

    return items
