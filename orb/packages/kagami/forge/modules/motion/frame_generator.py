from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from .motion_retargeting import BoneTransform, MotionFrame

logger = logging.getLogger(__name__)


@dataclass
class FacialExpression:
    """Facial expression data."""

    name: str
    blendshapes: dict[str, float]
    duration: float
    intensity: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "blendshapes": self.blendshapes,
            "duration": self.duration,
            "intensity": self.intensity,
        }


class FrameGenerator:
    """Generates motion frames for expressions."""

    def __init__(
        self, expression_library: dict[str, Any], blendshape_definitions: dict[str, Any]
    ) -> None:
        self.expression_library = expression_library
        self.blendshape_definitions = blendshape_definitions

    def _ease_in_out(self, t: float) -> float:
        if t < 0.5:
            return 2 * t * t
        else:
            return 1 - 2 * (1 - t) * (1 - t)

    def _multiply_quaternions(
        self, q1: np.ndarray[Any, Any], q2: np.ndarray[Any, Any]
    ) -> np.ndarray[Any, Any]:
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        return np.array([w, x, y, z])

    async def generate_expression_frame(
        self,
        timestamp: float,
        expression: FacialExpression,
        intensity: float,
        skeleton_type: str,
        duration: float,
    ) -> MotionFrame:
        progress = timestamp / duration if duration > 0 else 1.0
        eased_progress = self._ease_in_out(progress)
        bone_transforms = {}

        for blendshape_name, weight in expression.blendshapes.items():
            if blendshape_name in self.blendshape_definitions:
                definition = self.blendshape_definitions[blendshape_name]
                final_weight = weight * intensity * eased_progress

                for bone_name in definition["bones"]:
                    if bone_name not in bone_transforms:
                        bone_transforms[bone_name] = BoneTransform(
                            position=np.array([0, 0, 0]), rotation=np.array([1, 0, 0, 0])
                        )

                    axis = definition["axis"]
                    range_values = definition["range"]

                    if axis.startswith("rotation"):
                        angle = np.interp(final_weight, [0, 1], range_values)
                        angle_rad = np.radians(angle)
                        quat = self._get_quaternion_for_axis(axis, angle_rad)
                        bone_transforms[bone_name].rotation = self._multiply_quaternions(
                            bone_transforms[bone_name].rotation, quat
                        )
                    elif axis.startswith("position"):
                        self._apply_position_offset(
                            bone_transforms[bone_name], axis, final_weight, range_values
                        )

        return MotionFrame(timestamp=timestamp, bone_transforms=bone_transforms)

    def _get_quaternion_for_axis(self, axis: str, angle_rad: float) -> np.ndarray[Any, Any]:
        if axis == "rotation_x":
            return np.array([np.cos(angle_rad / 2), np.sin(angle_rad / 2), 0, 0])
        elif axis == "rotation_y":
            return np.array([np.cos(angle_rad / 2), 0, np.sin(angle_rad / 2), 0])
        elif axis == "rotation_z":
            return np.array([np.cos(angle_rad / 2), 0, 0, np.sin(angle_rad / 2)])
        return np.array([1, 0, 0, 0])

    def _apply_position_offset(
        self, transform: BoneTransform, axis: str, weight: float, range_values: tuple[float, float]
    ) -> None:
        offset = np.interp(weight, [0, 1], range_values)
        if axis == "position_x":
            transform.position[0] += offset
        elif axis == "position_y":
            transform.position[1] += offset
        elif axis == "position_z":
            transform.position[2] += offset
