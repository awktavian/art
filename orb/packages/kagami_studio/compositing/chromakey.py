"""Chromakey Processing — Green/blue screen removal.

Provides chromakey (color keying) for video compositing:
- Green screen removal
- Blue screen removal
- Custom color keying
- Automatic key color detection
- Spill suppression
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class ChromakeyConfig:
    """Chromakey configuration."""

    # Key color
    key_color: str = "green"  # green, blue, or hex
    key_rgb: tuple[int, int, int] | None = None  # Override with exact RGB

    # Thresholds
    similarity: float = 0.3  # Color match threshold (0-1)
    smoothness: float = 0.2  # Edge smoothness (0-1)
    spill_reduction: float = 0.5  # Color spill suppression (0-1)

    # Edge refinement
    edge_blur: int = 3  # Edge blur radius
    edge_dilate: int = 0  # Edge dilation
    edge_erode: int = 0  # Edge erosion

    # Output
    premultiply_alpha: bool = True


def get_key_color_rgb(color: str) -> tuple[int, int, int]:
    """Convert color name or hex to RGB.

    Args:
        color: 'green', 'blue', 'magenta', or hex '#RRGGBB'

    Returns:
        (R, G, B) tuple
    """
    presets = {
        "green": (0, 255, 0),
        "bright_green": (0, 177, 64),  # Standard chroma green
        "blue": (0, 0, 255),
        "bright_blue": (0, 71, 187),  # Standard chroma blue
        "magenta": (255, 0, 255),
    }

    if color.lower() in presets:
        return presets[color.lower()]

    # Parse hex
    if color.startswith("#"):
        color = color[1:]
    if len(color) == 6:
        return (
            int(color[0:2], 16),
            int(color[2:4], 16),
            int(color[4:6], 16),
        )

    return presets["green"]


def detect_key_color(
    image: np.ndarray,
    sample_region: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int]:
    """Automatically detect the key color from an image.

    Analyzes the image to find the dominant background color,
    useful for non-standard green screens.

    Args:
        image: BGR image
        sample_region: (x1, y1, x2, y2) region to sample, or None for edges

    Returns:
        Detected key color as (R, G, B)
    """
    h, w = image.shape[:2]

    if sample_region:
        x1, y1, x2, y2 = sample_region
        sample = image[y1:y2, x1:x2]
    else:
        # Sample from edges (likely background)
        top = image[0:50, :]
        bottom = image[h - 50 : h, :]
        left = image[:, 0:50]
        right = image[:, w - 50 : w]
        sample = np.vstack(
            [
                top.reshape(-1, 3),
                bottom.reshape(-1, 3),
                left.reshape(-1, 3),
                right.reshape(-1, 3),
            ]
        )

    # Get dominant color using k-means
    sample_flat = sample.reshape(-1, 3).astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(sample_flat, 3, None, criteria, 3, cv2.KMEANS_PP_CENTERS)

    # Find the most common cluster
    counts = np.bincount(labels.flatten())
    dominant_idx = np.argmax(counts)
    dominant_color = centers[dominant_idx].astype(int)

    # BGR to RGB
    return (dominant_color[2], dominant_color[1], dominant_color[0])


def apply_chromakey(
    foreground: np.ndarray,
    config: ChromakeyConfig | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply chromakey to extract subject from green screen.

    Args:
        foreground: BGR image with green/blue screen background
        config: Chromakey configuration

    Returns:
        (extracted_bgra, mask) - BGRA image with alpha and binary mask
    """
    config = config or ChromakeyConfig()

    _h, _w = foreground.shape[:2]

    # Get key color
    if config.key_rgb:
        key_r, key_g, key_b = config.key_rgb
    else:
        key_r, key_g, key_b = get_key_color_rgb(config.key_color)

    # Convert to HSV for better color matching
    hsv = cv2.cvtColor(foreground, cv2.COLOR_BGR2HSV)

    # Define range based on key color
    # Green: H=60, Blue: H=120
    if config.key_color in ("green", "bright_green"):
        lower = np.array([35, 50, 50])
        upper = np.array([85, 255, 255])
    elif config.key_color in ("blue", "bright_blue"):
        lower = np.array([100, 50, 50])
        upper = np.array([130, 255, 255])
    else:
        # Custom color - create range from RGB
        key_hsv = cv2.cvtColor(
            np.uint8([[[key_b, key_g, key_r]]]),
            cv2.COLOR_BGR2HSV,
        )[0][0]
        hue = key_hsv[0]
        lower = np.array([max(0, hue - 20), 50, 50])
        upper = np.array([min(180, hue + 20), 255, 255])

    # Create initial mask
    mask = cv2.inRange(hsv, lower, upper)

    # Invert (we want the subject, not the background)
    mask = cv2.bitwise_not(mask)

    # Refine edges
    if config.edge_erode > 0:
        kernel = np.ones((config.edge_erode, config.edge_erode), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)

    if config.edge_dilate > 0:
        kernel = np.ones((config.edge_dilate, config.edge_dilate), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)

    if config.edge_blur > 0:
        mask = cv2.GaussianBlur(mask, (config.edge_blur * 2 + 1, config.edge_blur * 2 + 1), 0)

    # Apply spill suppression
    if config.spill_reduction > 0:
        foreground = _suppress_spill(foreground, config.key_color, config.spill_reduction)

    # Create output with alpha
    bgra = cv2.cvtColor(foreground, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = mask

    if config.premultiply_alpha:
        # Premultiply alpha
        alpha = mask.astype(np.float32) / 255
        for c in range(3):
            bgra[:, :, c] = (bgra[:, :, c] * alpha).astype(np.uint8)

    return bgra, mask


def _suppress_spill(
    image: np.ndarray,
    key_color: str,
    strength: float,
) -> np.ndarray:
    """Suppress color spill from green/blue screen onto subject.

    Args:
        image: BGR image
        key_color: 'green' or 'blue'
        strength: Suppression strength (0-1)

    Returns:
        Spill-corrected BGR image
    """
    result = image.copy().astype(np.float32)

    if key_color in ("green", "bright_green"):
        # Reduce green channel where it exceeds average of R and B
        avg_rb = (result[:, :, 2] + result[:, :, 0]) / 2
        excess = np.maximum(0, result[:, :, 1] - avg_rb)
        result[:, :, 1] -= excess * strength

    elif key_color in ("blue", "bright_blue"):
        # Reduce blue channel where it exceeds average of R and G
        avg_rg = (result[:, :, 2] + result[:, :, 1]) / 2
        excess = np.maximum(0, result[:, :, 0] - avg_rg)
        result[:, :, 0] -= excess * strength

    return np.clip(result, 0, 255).astype(np.uint8)


async def chromakey_video(
    input_path: Path | str,
    output_path: Path | str,
    config: ChromakeyConfig | None = None,
) -> bool:
    """Apply chromakey to entire video using FFmpeg.

    Args:
        input_path: Input video path
        output_path: Output video path (with alpha if format supports)
        config: Chromakey configuration

    Returns:
        True if successful
    """
    config = config or ChromakeyConfig()
    input_path = Path(input_path)
    output_path = Path(output_path)

    # Get key color as hex for FFmpeg
    r, g, b = config.key_rgb or get_key_color_rgb(config.key_color)
    color_hex = f"0x{r:02x}{g:02x}{b:02x}"

    # FFmpeg colorkey filter
    filter_str = f"colorkey={color_hex}:{config.similarity}:{config.smoothness}"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        filter_str,
        "-c:v",
        "prores_ks",  # ProRes supports alpha
        "-profile:v",
        "4444",  # ProRes 4444 with alpha
        "-c:a",
        "copy",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0
