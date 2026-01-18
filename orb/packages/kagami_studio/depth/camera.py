"""3D Camera Motion — Simulate camera movement through depth.

Create cinematic camera motion from photos and video using depth maps.

Supported Motions:
- Dolly: Forward/backward through scene
- Truck: Left/right movement
- Pedestal: Up/down movement
- Pan: Horizontal rotation
- Tilt: Vertical rotation
- Ken Burns 3D: Classic photo animation with parallax
- Dolly Zoom (Vertigo): Zoom + dolly for dramatic effect

Usage:
    from kagami_studio.depth import create_camera_motion, CameraPath

    result = await create_camera_motion(
        image="portrait.jpg",
        camera_path=CameraPath.DOLLY_IN,
        duration=3.0,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from kagami_studio.depth.estimator import DepthResult

logger = logging.getLogger(__name__)


class CameraPath(Enum):
    """Preset camera motion paths."""

    # Dolly (forward/back)
    DOLLY_IN = auto()  # Move toward subject
    DOLLY_OUT = auto()  # Move away from subject
    DOLLY_THROUGH = auto()  # Move through scene

    # Truck (left/right)
    TRUCK_LEFT = auto()
    TRUCK_RIGHT = auto()

    # Pedestal (up/down)
    PEDESTAL_UP = auto()
    PEDESTAL_DOWN = auto()

    # Rotations
    PAN_LEFT = auto()
    PAN_RIGHT = auto()
    TILT_UP = auto()
    TILT_DOWN = auto()

    # Combined motions
    ORBIT_LEFT = auto()  # Dolly + pan (circle around subject)
    ORBIT_RIGHT = auto()
    CRANE_UP = auto()  # Pedestal + tilt (crane shot)
    CRANE_DOWN = auto()

    # Classic effects
    KEN_BURNS = auto()  # Subtle zoom + pan
    DOLLY_ZOOM = auto()  # Vertigo effect (dolly + opposite zoom)
    PARALLAX_DRIFT = auto()  # Subtle depth parallax

    # Custom
    CUSTOM = auto()


@dataclass
class CameraConfig:
    """Camera motion configuration."""

    # Field of view
    fov: float = 60.0  # Degrees

    # Motion range
    dolly_range: float = 0.3  # 0-1, how much to move forward
    truck_range: float = 0.2  # 0-1, left/right range
    pedestal_range: float = 0.15  # 0-1, up/down range
    pan_range: float = 15.0  # Degrees
    tilt_range: float = 10.0  # Degrees

    # Zoom
    zoom_range: float = 1.2  # End zoom / start zoom

    # Timing
    easing: str = "ease_in_out"  # linear, ease_in, ease_out, ease_in_out

    # Depth handling
    depth_scale: float = 1.0  # Scale depth effect
    inpaint_disocclusions: bool = True  # Fill revealed areas

    # Output
    fps: int = 30
    width: int | None = None  # None = same as input
    height: int | None = None


@dataclass
class CameraKeyframe:
    """Single camera position/orientation."""

    time: float  # 0-1 normalized time

    # Position (normalized, 0 = center)
    x: float = 0.0  # -1 to 1
    y: float = 0.0  # -1 to 1
    z: float = 0.0  # 0 = original, positive = forward

    # Rotation (degrees)
    pan: float = 0.0
    tilt: float = 0.0
    roll: float = 0.0

    # Zoom
    zoom: float = 1.0


@dataclass
class CameraMotion:
    """Complete camera motion sequence."""

    keyframes: list[CameraKeyframe] = field(default_factory=list)
    config: CameraConfig = field(default_factory=CameraConfig)

    def add_keyframe(
        self,
        time: float,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        pan: float = 0.0,
        tilt: float = 0.0,
        roll: float = 0.0,
        zoom: float = 1.0,
    ) -> None:
        """Add a keyframe to the motion."""
        self.keyframes.append(
            CameraKeyframe(
                time=time,
                x=x,
                y=y,
                z=z,
                pan=pan,
                tilt=tilt,
                roll=roll,
                zoom=zoom,
            )
        )
        self.keyframes.sort(key=lambda k: k.time)

    def interpolate(self, t: float) -> CameraKeyframe:
        """Get interpolated camera position at time t (0-1)."""
        if not self.keyframes:
            return CameraKeyframe(time=t)

        if t <= self.keyframes[0].time:
            return self.keyframes[0]
        if t >= self.keyframes[-1].time:
            return self.keyframes[-1]

        # Find surrounding keyframes
        k1 = self.keyframes[0]
        k2 = self.keyframes[-1]
        for i in range(len(self.keyframes) - 1):
            if self.keyframes[i].time <= t <= self.keyframes[i + 1].time:
                k1 = self.keyframes[i]
                k2 = self.keyframes[i + 1]
                break

        # Interpolation factor
        if k2.time == k1.time:
            alpha = 0.0
        else:
            alpha = (t - k1.time) / (k2.time - k1.time)

        # Apply easing
        alpha = self._ease(alpha, self.config.easing)

        # Interpolate all values
        return CameraKeyframe(
            time=t,
            x=k1.x + alpha * (k2.x - k1.x),
            y=k1.y + alpha * (k2.y - k1.y),
            z=k1.z + alpha * (k2.z - k1.z),
            pan=k1.pan + alpha * (k2.pan - k1.pan),
            tilt=k1.tilt + alpha * (k2.tilt - k1.tilt),
            roll=k1.roll + alpha * (k2.roll - k1.roll),
            zoom=k1.zoom + alpha * (k2.zoom - k1.zoom),
        )

    def _ease(self, t: float, easing: str) -> float:
        """Apply easing function."""
        if easing == "linear":
            return t
        elif easing == "ease_in":
            return t * t
        elif easing == "ease_out":
            return 1 - (1 - t) * (1 - t)
        elif easing == "ease_in_out":
            if t < 0.5:
                return 2 * t * t
            else:
                return 1 - 2 * (1 - t) * (1 - t)
        return t


def create_motion_from_path(
    path: CameraPath,
    config: CameraConfig | None = None,
) -> CameraMotion:
    """Create camera motion from preset path.

    Args:
        path: Preset camera path
        config: Camera configuration

    Returns:
        CameraMotion with keyframes
    """
    config = config or CameraConfig()
    motion = CameraMotion(config=config)

    if path == CameraPath.DOLLY_IN:
        motion.add_keyframe(0.0, z=0.0)
        motion.add_keyframe(1.0, z=config.dolly_range)

    elif path == CameraPath.DOLLY_OUT:
        motion.add_keyframe(0.0, z=config.dolly_range)
        motion.add_keyframe(1.0, z=0.0)

    elif path == CameraPath.DOLLY_THROUGH:
        motion.add_keyframe(0.0, z=-config.dolly_range / 2)
        motion.add_keyframe(1.0, z=config.dolly_range)

    elif path == CameraPath.TRUCK_LEFT:
        motion.add_keyframe(0.0, x=config.truck_range)
        motion.add_keyframe(1.0, x=-config.truck_range)

    elif path == CameraPath.TRUCK_RIGHT:
        motion.add_keyframe(0.0, x=-config.truck_range)
        motion.add_keyframe(1.0, x=config.truck_range)

    elif path == CameraPath.PEDESTAL_UP:
        motion.add_keyframe(0.0, y=config.pedestal_range)
        motion.add_keyframe(1.0, y=-config.pedestal_range)

    elif path == CameraPath.PEDESTAL_DOWN:
        motion.add_keyframe(0.0, y=-config.pedestal_range)
        motion.add_keyframe(1.0, y=config.pedestal_range)

    elif path == CameraPath.PAN_LEFT:
        motion.add_keyframe(0.0, pan=config.pan_range)
        motion.add_keyframe(1.0, pan=-config.pan_range)

    elif path == CameraPath.PAN_RIGHT:
        motion.add_keyframe(0.0, pan=-config.pan_range)
        motion.add_keyframe(1.0, pan=config.pan_range)

    elif path == CameraPath.TILT_UP:
        motion.add_keyframe(0.0, tilt=config.tilt_range)
        motion.add_keyframe(1.0, tilt=-config.tilt_range)

    elif path == CameraPath.TILT_DOWN:
        motion.add_keyframe(0.0, tilt=-config.tilt_range)
        motion.add_keyframe(1.0, tilt=config.tilt_range)

    elif path == CameraPath.ORBIT_LEFT:
        motion.add_keyframe(0.0, x=config.truck_range, pan=-config.pan_range)
        motion.add_keyframe(1.0, x=-config.truck_range, pan=config.pan_range)

    elif path == CameraPath.ORBIT_RIGHT:
        motion.add_keyframe(0.0, x=-config.truck_range, pan=config.pan_range)
        motion.add_keyframe(1.0, x=config.truck_range, pan=-config.pan_range)

    elif path == CameraPath.CRANE_UP:
        motion.add_keyframe(0.0, y=config.pedestal_range, tilt=-config.tilt_range)
        motion.add_keyframe(1.0, y=-config.pedestal_range, tilt=config.tilt_range)

    elif path == CameraPath.CRANE_DOWN:
        motion.add_keyframe(0.0, y=-config.pedestal_range, tilt=config.tilt_range)
        motion.add_keyframe(1.0, y=config.pedestal_range, tilt=-config.tilt_range)

    elif path == CameraPath.KEN_BURNS:
        # Subtle zoom with slight pan
        motion.add_keyframe(0.0, zoom=1.0, x=-0.05, y=-0.03)
        motion.add_keyframe(1.0, zoom=config.zoom_range, x=0.05, y=0.03)

    elif path == CameraPath.DOLLY_ZOOM:
        # Vertigo effect: dolly in while zooming out
        motion.add_keyframe(0.0, z=0.0, zoom=config.zoom_range)
        motion.add_keyframe(1.0, z=config.dolly_range, zoom=1.0 / config.zoom_range)

    elif path == CameraPath.PARALLAX_DRIFT:
        # Very subtle depth-based drift
        motion.add_keyframe(0.0, x=-0.03, z=0.0)
        motion.add_keyframe(0.5, x=0.03, z=0.1)
        motion.add_keyframe(1.0, x=-0.03, z=0.0)

    else:
        # Default: static
        motion.add_keyframe(0.0)
        motion.add_keyframe(1.0)

    return motion


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def create_camera_motion(
    image: np.ndarray | str | Path,
    depth: DepthResult | None = None,
    camera_path: CameraPath = CameraPath.DOLLY_IN,
    duration: float = 3.0,
    output: str | Path | None = None,
    config: CameraConfig | None = None,
) -> Path:
    """Create 3D camera motion video from image.

    Args:
        image: Source image
        depth: Pre-computed depth (estimated if None)
        camera_path: Camera motion preset
        duration: Video duration in seconds
        output: Output path (auto-generated if None)
        config: Camera configuration

    Returns:
        Path to output video
    """
    from kagami_studio.depth.estimator import estimate_depth
    from kagami_studio.depth.renderer import render_3d_motion

    # Load image
    if isinstance(image, (str, Path)):
        img_path = Path(image)
        img = cv2.imread(str(img_path))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        img = image
        img_path = Path("/tmp/input.jpg")

    # Estimate depth if not provided
    if depth is None:
        depth = await estimate_depth(img)

    # Create motion
    config = config or CameraConfig()
    motion = create_motion_from_path(camera_path, config)

    # Generate output path
    if output is None:
        output = img_path.with_suffix(".motion.mp4")
    output = Path(output)

    # Render
    return await render_3d_motion(
        image=img,
        depth=depth,
        motion=motion,
        duration=duration,
        output=output,
    )


async def create_ken_burns_3d(
    image: np.ndarray | str | Path,
    duration: float = 5.0,
    output: str | Path | None = None,
    zoom_range: float = 1.3,
) -> Path:
    """Create classic Ken Burns effect with 3D parallax.

    Args:
        image: Source image
        duration: Video duration
        output: Output path
        zoom_range: How much to zoom (1.3 = 30% zoom)

    Returns:
        Path to output video
    """
    config = CameraConfig(zoom_range=zoom_range, easing="ease_in_out")
    return await create_camera_motion(
        image=image,
        camera_path=CameraPath.KEN_BURNS,
        duration=duration,
        output=output,
        config=config,
    )


async def create_dolly_zoom(
    image: np.ndarray | str | Path,
    duration: float = 3.0,
    output: str | Path | None = None,
    intensity: float = 1.0,
) -> Path:
    """Create Vertigo-style dolly zoom effect.

    Camera moves forward while zooming out (or vice versa),
    keeping subject same size while background warps.

    Args:
        image: Source image
        duration: Video duration
        output: Output path
        intensity: Effect strength (0.5-2.0)

    Returns:
        Path to output video
    """
    config = CameraConfig(
        dolly_range=0.3 * intensity,
        zoom_range=1.5 * intensity,
        easing="ease_in_out",
    )
    return await create_camera_motion(
        image=image,
        camera_path=CameraPath.DOLLY_ZOOM,
        duration=duration,
        output=output,
        config=config,
    )


async def create_parallax_pan(
    image: np.ndarray | str | Path,
    direction: str = "left",
    duration: float = 4.0,
    output: str | Path | None = None,
) -> Path:
    """Create parallax pan effect.

    Foreground moves faster than background, creating depth.

    Args:
        image: Source image
        direction: 'left', 'right', 'up', 'down'
        duration: Video duration
        output: Output path

    Returns:
        Path to output video
    """
    path_map = {
        "left": CameraPath.TRUCK_LEFT,
        "right": CameraPath.TRUCK_RIGHT,
        "up": CameraPath.PEDESTAL_UP,
        "down": CameraPath.PEDESTAL_DOWN,
    }

    config = CameraConfig(
        truck_range=0.15,
        pedestal_range=0.1,
        depth_scale=1.5,  # Emphasize parallax
    )

    return await create_camera_motion(
        image=image,
        camera_path=path_map.get(direction, CameraPath.TRUCK_LEFT),
        duration=duration,
        output=output,
        config=config,
    )
