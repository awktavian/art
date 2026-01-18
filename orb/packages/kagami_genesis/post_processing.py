"""Post-processing utilities for Genesis renders.

Provides color grading, tonemapping, and HDR conversion functions.

Created: December 28, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ColorGradeConfig:
    """Color grading configuration."""

    lift: tuple[float, float, float] = (0.0, 0.0, 0.0)
    gamma: tuple[float, float, float] = (1.0, 1.0, 1.0)
    gain: tuple[float, float, float] = (1.0, 1.0, 1.0)
    saturation: float = 1.0


# Preset color grades
GRADE_CINEMATIC_WARM = ColorGradeConfig(
    lift=(-0.05, -0.05, 0.0),
    gamma=(1.1, 1.0, 0.9),
    gain=(1.1, 1.05, 0.95),
    saturation=1.1,
)

GRADE_TEAL_ORANGE = ColorGradeConfig(
    lift=(0.0, -0.02, -0.05),
    gamma=(1.0, 1.0, 1.1),
    gain=(1.15, 1.05, 0.9),
    saturation=1.2,
)

GRADE_NOIR = ColorGradeConfig(
    lift=(0.0, 0.0, 0.0),
    gamma=(1.2, 1.2, 1.2),
    gain=(0.9, 0.9, 0.9),
    saturation=0.0,
)

GRADE_VIBRANT = ColorGradeConfig(
    lift=(0.0, 0.0, 0.0),
    gamma=(0.9, 0.9, 0.9),
    gain=(1.2, 1.2, 1.2),
    saturation=1.4,
)


def aces_tonemap(
    image: np.ndarray,
    exposure: float = 1.0,
) -> np.ndarray:
    """Apply ACES filmic tonemapping.

    Args:
        image: HDR image array (H, W, C) in linear RGB
        exposure: Exposure adjustment multiplier

    Returns:
        Tonemapped image in [0, 1] range
    """
    # Apply exposure
    img = image * exposure

    # ACES filmic curve approximation (Krzysztof Narkowicz)
    # https://knarkowicz.wordpress.com/2016/01/06/aces-filmic-tone-mapping-curve/
    a = 2.51
    b = 0.03
    c = 2.43
    d = 0.59
    e = 0.14

    result = (img * (a * img + b)) / (img * (c * img + d) + e)
    return np.clip(result, 0.0, 1.0)


def hdr_to_srgb(
    image: np.ndarray,
    gamma: float = 2.2,
) -> np.ndarray:
    """Convert HDR linear RGB to sRGB.

    Args:
        image: Linear RGB image array (H, W, C)
        gamma: Gamma correction value (default 2.2 for sRGB)

    Returns:
        sRGB image in [0, 1] range
    """
    from numpy.typing import NDArray

    # Clamp to valid range
    img = np.clip(image, 0.0, None)

    # Apply gamma correction (inverse gamma)
    result: NDArray[np.Any] = np.power(img, 1.0 / gamma)
    return result


def apply_color_grade(
    image: np.ndarray,
    lift: tuple[float, float, float] = (0.0, 0.0, 0.0),
    gamma: tuple[float, float, float] = (1.0, 1.0, 1.0),
    gain: tuple[float, float, float] = (1.0, 1.0, 1.0),
    saturation: float = 1.0,
) -> np.ndarray:
    """Apply lift-gamma-gain color grading.

    Args:
        image: Input image array (H, W, C)
        lift: RGB lift (shadows)
        gamma: RGB gamma (midtones)
        gain: RGB gain (highlights)
        saturation: Saturation adjustment

    Returns:
        Color-graded image
    """
    result = image.copy()

    for i, (l, g, ga) in enumerate(zip(lift, gamma, gain, strict=True)):
        # Apply lift-gamma-gain per channel
        channel = result[..., i]
        channel = channel * ga + l
        if g != 1.0:
            channel = np.power(np.clip(channel, 0.0, None), 1.0 / g)
        result[..., i] = channel

    # Apply saturation
    if saturation != 1.0:
        # Convert to luminance
        luma = 0.2126 * result[..., 0] + 0.7152 * result[..., 1] + 0.0722 * result[..., 2]
        luma = luma[..., np.newaxis]

        # Interpolate between luminance and color
        result = luma + saturation * (result - luma)

    return np.clip(result, 0.0, 1.0)


__all__ = [
    "GRADE_CINEMATIC_WARM",
    "GRADE_NOIR",
    "GRADE_TEAL_ORANGE",
    "GRADE_VIBRANT",
    "ColorGradeConfig",
    "aces_tonemap",
    "apply_color_grade",
    "hdr_to_srgb",
]
