"""Genesis Camera Configuration.

Minimal camera settings for real-time rendering.

Colony: Forge (e₂)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CameraModel(Enum):
    """Genesis camera models."""

    PINHOLE = "pinhole"
    THINLENS = "thinlens"


@dataclass
class DOFSettings:
    """Depth of field settings for thinlens camera."""

    aperture: float = 2.0
    focus_distance: float = 4.0


@dataclass
class CameraConfig:
    """Camera configuration."""

    position: tuple[float, float, float] = (3.0, 3.0, 2.0)
    lookat: tuple[float, float, float] = (0.0, 0.0, 0.5)
    fov: float = 50.0
    model: CameraModel = CameraModel.THINLENS
    dof: DOFSettings | None = None


__all__ = [
    "CameraConfig",
    "CameraModel",
    "DOFSettings",
]
