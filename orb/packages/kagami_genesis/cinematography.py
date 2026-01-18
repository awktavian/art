"""Genesis Cinematography — Shot Planning and Camera Movement.

Professional camera work for Genesis renders:
- Shot types (wide, medium, close-up, etc.)
- Camera movements (dolly, truck, crane, steadicam)
- Keyframe animation with easing
- Kubrick-inspired techniques (dolly zoom, one-point perspective)

Colony: Spark (e₁) × Forge (e₂)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np


class ShotType(Enum):
    """Standard cinematography shot types."""

    EXTREME_WIDE = auto()  # Establishes location, subject tiny
    WIDE = auto()  # Full environment, subject visible
    FULL = auto()  # Subject head to toe
    MEDIUM = auto()  # Waist up (cowboy shot)
    MEDIUM_CLOSE = auto()  # Chest up
    CLOSE_UP = auto()  # Face only
    EXTREME_CLOSE = auto()  # Detail shot (eyes, hands)
    OVER_SHOULDER = auto()  # OTS for dialogue
    POV = auto()  # Point of view
    INSERT = auto()  # Detail/prop shot


class CameraMovement(Enum):
    """Camera movement types."""

    STATIC = auto()  # Locked off, no movement
    PAN = auto()  # Rotate horizontally on axis
    TILT = auto()  # Rotate vertically on axis
    DOLLY = auto()  # Move toward/away from subject
    TRUCK = auto()  # Move left/right parallel to subject
    CRANE = auto()  # Move up/down vertically
    BOOM = auto()  # Crane with arc
    ARC = auto()  # Orbit around subject
    STEADICAM = auto()  # Smooth handheld tracking
    HANDHELD = auto()  # Organic shake
    DOLLY_ZOOM = auto()  # Vertigo effect (zoom opposite dolly)
    RACK_FOCUS = auto()  # Change focus between subjects
    WHIP_PAN = auto()  # Fast pan (transition)


@dataclass
class CameraKeyframe:
    """Camera state at a point in time."""

    position: tuple[float, float, float]
    lookat: tuple[float, float, float]
    fov: float = 50.0
    aperture: float = 2.8  # f-stop
    focus_distance: float = 4.0

    def to_array(self) -> np.ndarray:
        """Convert to flat array for interpolation."""
        return np.array(
            [
                *self.position,
                *self.lookat,
                self.fov,
                self.aperture,
                self.focus_distance,
            ],
        )

    @classmethod
    def from_array(cls, arr: np.ndarray) -> CameraKeyframe:
        """Construct from flat array."""
        return cls(
            position=(arr[0], arr[1], arr[2]),  # type: ignore[arg-type]
            lookat=(arr[3], arr[4], arr[5]),  # type: ignore[arg-type]
            fov=arr[6],  # type: ignore[arg-type]
            aperture=arr[7],  # type: ignore[arg-type]
            focus_distance=arr[8],  # type: ignore[arg-type]
        )


def ease_linear(t: float) -> float:
    """Linear interpolation."""
    return t


def ease_in_quad(t: float) -> float:
    """Quadratic ease in (slow start)."""
    return t * t


def ease_out_quad(t: float) -> float:
    """Quadratic ease out (slow end)."""
    return 1 - (1 - t) * (1 - t)


def ease_in_out_quad(t: float) -> float:
    """Quadratic ease in-out (slow start and end)."""
    if t < 0.5:
        return 2 * t * t
    return 1 - (-2 * t + 2) ** 2 / 2


def ease_in_out_cubic(t: float) -> float:
    """Cubic ease in-out (smoother)."""
    if t < 0.5:
        return 4 * t * t * t
    return 1 - (-2 * t + 2) ** 3 / 2


def ease_in_out_sine(t: float) -> float:
    """Sinusoidal ease in-out (natural)."""
    return -(math.cos(math.pi * t) - 1) / 2


EASING_FUNCTIONS = {
    "linear": ease_linear,
    "ease_in": ease_in_quad,
    "ease_out": ease_out_quad,
    "ease_in_out": ease_in_out_quad,
    "ease_in_out_cubic": ease_in_out_cubic,
    "ease_in_out_sine": ease_in_out_sine,
}


@dataclass
class Shot:
    """A single camera shot with duration and keyframes."""

    name: str
    duration: float  # seconds
    shot_type: ShotType = ShotType.MEDIUM
    movement: CameraMovement = CameraMovement.STATIC
    keyframes: list[CameraKeyframe] = field(default_factory=list)
    easing: str = "ease_in_out"

    def get_camera_at(self, t: float) -> CameraKeyframe:
        """Get interpolated camera state at time t (0-1 normalized)."""
        if not self.keyframes:
            raise ValueError("Shot has no keyframes")

        if len(self.keyframes) == 1:
            return self.keyframes[0]

        # Apply easing
        ease_fn = EASING_FUNCTIONS.get(self.easing, ease_in_out_quad)
        t_eased = ease_fn(max(0.0, min(1.0, t)))

        # Find segment
        n = len(self.keyframes)
        segment_size = 1.0 / (n - 1)
        segment_idx = min(int(t_eased / segment_size), n - 2)
        local_t = (t_eased - segment_idx * segment_size) / segment_size

        # Interpolate between keyframes
        kf0 = self.keyframes[segment_idx]
        kf1 = self.keyframes[segment_idx + 1]

        arr0 = kf0.to_array()
        arr1 = kf1.to_array()
        arr_interp = arr0 + (arr1 - arr0) * local_t

        return CameraKeyframe.from_array(arr_interp)


@dataclass
class Sequence:
    """A sequence of shots (edit/cut list)."""

    name: str
    shots: list[Shot] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        """Total sequence duration in seconds."""
        return sum(shot.duration for shot in self.shots)

    def get_shot_at(self, time: float) -> tuple[Shot, float]:
        """Get the shot and local time (0-1) for a given sequence time.

        Returns:
            (shot, local_t) where local_t is 0-1 within that shot
        """
        elapsed = 0.0
        for shot in self.shots:
            if elapsed + shot.duration > time:
                local_t = (time - elapsed) / shot.duration
                return shot, local_t
            elapsed += shot.duration

        # Past end, return last shot at t=1
        if self.shots:
            return self.shots[-1], 1.0
        raise ValueError("Sequence has no shots")

    def get_camera_at(self, time: float) -> CameraKeyframe:
        """Get camera state at sequence time."""
        shot, local_t = self.get_shot_at(time)
        return shot.get_camera_at(local_t)


class Cinematographer:
    """High-level cinematography helper for creating complex shots."""

    @staticmethod
    def create_dolly_zoom_shot(
        name: str,
        subject_pos: tuple[float, float, float],
        start_distance: float,
        end_distance: float,
        start_fov: float,
        end_fov: float,
        duration: float = 3.0,
        height: float = 1.5,
        steps: int = 24,
    ) -> Shot:
        """Create a Hitchcock/Spielberg dolly zoom (Vertigo effect).

        The camera moves while zooming opposite to keep subject size constant,
        causing background to appear to shift dramatically.

        Args:
            name: Shot name
            subject_pos: Position of the subject
            start_distance: Initial distance from subject
            end_distance: Final distance from subject
            start_fov: Initial field of view
            end_fov: Final field of view (should be inverse of distance ratio)
            duration: Shot duration in seconds
            height: Camera height
            steps: Number of keyframes for smooth motion
        """
        keyframes = []
        sx, sy, _sz = subject_pos

        for i in range(steps):
            t = i / (steps - 1)
            # Linear interpolation of distance and FOV
            dist = start_distance + (end_distance - start_distance) * t
            fov = start_fov + (end_fov - start_fov) * t

            # Camera position (behind subject on Y axis)
            cam_pos = (sx, sy - dist, height)

            keyframes.append(
                CameraKeyframe(
                    position=cam_pos,
                    lookat=subject_pos,
                    fov=fov,
                    aperture=4.0,  # Medium DOF
                    focus_distance=dist,
                ),
            )

        return Shot(
            name=name,
            duration=duration,
            shot_type=ShotType.MEDIUM,
            movement=CameraMovement.DOLLY_ZOOM,
            keyframes=keyframes,
            easing="ease_in_out_sine",
        )

    @staticmethod
    def create_one_point_perspective_shot(
        name: str,
        corridor_start: tuple[float, float, float],
        corridor_end: tuple[float, float, float],
        duration: float = 5.0,
        fov: float = 35.0,
        steps: int = 60,
    ) -> Shot:
        """Create a Kubrick one-point perspective shot (The Shining hallway).

        Camera moves along a corridor toward a vanishing point.

        Args:
            name: Shot name
            corridor_start: Camera starting position
            corridor_end: Camera ending position (vanishing point direction)
            duration: Shot duration
            fov: Field of view (lower = more dramatic perspective)
            steps: Number of keyframes
        """
        keyframes = []
        start = np.array(corridor_start)
        end = np.array(corridor_end)

        # Vanishing point is always at the end of the corridor
        vanishing = tuple(end)

        for i in range(steps):
            t = i / (steps - 1)
            pos = start + (end - start) * t * 0.8  # Don't go all the way
            pos_tuple = (float(pos[0]), float(pos[1]), float(pos[2]))

            keyframes.append(
                CameraKeyframe(
                    position=pos_tuple,
                    lookat=vanishing,
                    fov=fov,
                    aperture=8.0,  # Deep DOF for architecture
                    focus_distance=np.linalg.norm(end - pos),  # type: ignore[arg-type]
                ),
            )

        return Shot(
            name=name,
            duration=duration,
            shot_type=ShotType.WIDE,
            movement=CameraMovement.STEADICAM,
            keyframes=keyframes,
            easing="linear",  # Kubrick often uses linear for hypnotic effect
        )

    @staticmethod
    def create_steadicam_follow_shot(
        name: str,
        path_points: list[tuple[float, float, float]],
        lookat: tuple[float, float, float],
        duration: float = 5.0,
        fov: float = 50.0,
        aperture: float = 2.8,
    ) -> Shot:
        """Create a smooth Steadicam tracking shot along a path.

        Args:
            name: Shot name
            path_points: List of camera positions along path
            lookat: What the camera looks at (or tracks)
            duration: Shot duration
            fov: Field of view
            aperture: f-stop for DOF
        """
        keyframes = []
        for pos in path_points:
            focus_dist = math.sqrt(
                (pos[0] - lookat[0]) ** 2 + (pos[1] - lookat[1]) ** 2 + (pos[2] - lookat[2]) ** 2,
            )
            keyframes.append(
                CameraKeyframe(
                    position=pos,
                    lookat=lookat,
                    fov=fov,
                    aperture=aperture,
                    focus_distance=focus_dist,
                ),
            )

        return Shot(
            name=name,
            duration=duration,
            shot_type=ShotType.MEDIUM,
            movement=CameraMovement.STEADICAM,
            keyframes=keyframes,
            easing="ease_in_out_cubic",
        )

    @staticmethod
    def create_rack_focus_shot(
        name: str,
        camera_pos: tuple[float, float, float],
        lookat: tuple[float, float, float],
        focus_near: float,
        focus_far: float,
        duration: float = 2.0,
        fov: float = 50.0,
        aperture: float = 1.8,  # Shallow for visible rack
    ) -> Shot:
        """Create a rack focus shot that pulls focus between two distances.

        Args:
            name: Shot name
            camera_pos: Static camera position
            lookat: What camera looks at
            focus_near: Near focus distance
            focus_far: Far focus distance
            duration: Shot duration
            fov: Field of view
            aperture: f-stop (lower = more visible focus change)
        """
        keyframes = [
            CameraKeyframe(
                position=camera_pos,
                lookat=lookat,
                fov=fov,
                aperture=aperture,
                focus_distance=focus_near,
            ),
            CameraKeyframe(
                position=camera_pos,
                lookat=lookat,
                fov=fov,
                aperture=aperture,
                focus_distance=focus_far,
            ),
        ]

        return Shot(
            name=name,
            duration=duration,
            shot_type=ShotType.MEDIUM,
            movement=CameraMovement.RACK_FOCUS,
            keyframes=keyframes,
            easing="ease_in_out_sine",
        )

    @staticmethod
    def create_crane_shot(
        name: str,
        start_pos: tuple[float, float, float],
        end_pos: tuple[float, float, float],
        lookat: tuple[float, float, float],
        duration: float = 4.0,
        fov: float = 50.0,
        steps: int = 30,
    ) -> Shot:
        """Create a crane shot moving vertically.

        Args:
            name: Shot name
            start_pos: Starting camera position
            end_pos: Ending camera position
            lookat: What camera looks at
            duration: Shot duration
            fov: Field of view
            steps: Number of keyframes
        """
        keyframes = []
        start = np.array(start_pos)
        end = np.array(end_pos)
        look = np.array(lookat)

        for i in range(steps):
            t = i / (steps - 1)
            pos = start + (end - start) * t
            pos_tuple = (float(pos[0]), float(pos[1]), float(pos[2]))
            focus_dist = float(np.linalg.norm(look - pos))

            keyframes.append(
                CameraKeyframe(
                    position=pos_tuple,
                    lookat=lookat,
                    fov=fov,
                    aperture=4.0,
                    focus_distance=focus_dist,
                ),
            )

        return Shot(
            name=name,
            duration=duration,
            shot_type=ShotType.WIDE,
            movement=CameraMovement.CRANE,
            keyframes=keyframes,
            easing="ease_in_out_quad",
        )

    @staticmethod
    def create_arc_shot(
        name: str,
        center: tuple[float, float, float],
        radius: float,
        start_angle: float,
        end_angle: float,
        height: float,
        duration: float = 5.0,
        fov: float = 50.0,
        steps: int = 48,
    ) -> Shot:
        """Create an arc/orbit shot around a subject.

        Args:
            name: Shot name
            center: Center point to orbit around
            radius: Orbit radius
            start_angle: Starting angle in degrees
            end_angle: Ending angle in degrees
            height: Camera height
            duration: Shot duration
            fov: Field of view
            steps: Number of keyframes
        """
        keyframes = []
        cx, cy, _cz = center

        for i in range(steps):
            t = i / (steps - 1)
            angle = math.radians(start_angle + (end_angle - start_angle) * t)

            # Camera position on circle
            cam_x = cx + radius * math.cos(angle)
            cam_y = cy + radius * math.sin(angle)
            cam_z = height

            keyframes.append(
                CameraKeyframe(
                    position=(cam_x, cam_y, cam_z),
                    lookat=center,
                    fov=fov,
                    aperture=4.0,
                    focus_distance=radius,
                ),
            )

        return Shot(
            name=name,
            duration=duration,
            shot_type=ShotType.MEDIUM,
            movement=CameraMovement.ARC,
            keyframes=keyframes,
            easing="ease_in_out_sine",
        )


__all__ = [
    "EASING_FUNCTIONS",
    "CameraKeyframe",
    "CameraMovement",
    "Cinematographer",
    "Sequence",
    "Shot",
    "ShotType",
    "ease_in_out_cubic",
    "ease_in_out_quad",
    "ease_in_out_sine",
    "ease_in_quad",
    "ease_linear",
    "ease_out_quad",
]
