"""OBS Filter Management — Filter definitions and factories.

Provides typed filter creation for OBS:
- Chromakey (green screen removal)
- Color correction
- Blur effects
- LUT (color grading)
- Sharpen
- Noise suppression

Usage:
    from kagami_studio.obs import OBSController
    from kagami_studio.obs.filters import create_chromakey_filter

    async with connect_obs() as obs:
        # Add chromakey filter to source
        chromakey = create_chromakey_filter(
            key_color="green",
            similarity=400,
            smoothness=80,
        )
        await obs.add_filter("GreenScreen", "chromakey", "chroma_key_filter_v2", chromakey)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FilterType(str, Enum):
    """OBS filter type identifiers."""

    # Video filters
    CHROMAKEY = "chroma_key_filter_v2"
    CHROMAKEY_LEGACY = "chroma_key_filter"
    COLOR_KEY = "color_key_filter_v2"
    LUT = "clut_filter"
    COLOR_CORRECTION = "color_filter_v2"
    SHARPEN = "sharpness_filter"
    BLUR = "blur_filter"
    CROP = "crop_filter"
    SCROLL = "scroll_filter"
    RENDER_DELAY = "gpu_delay"
    MASK = "mask_filter"
    ASYNC_DELAY = "async_delay_filter"

    # Audio filters
    COMPRESSOR = "compressor_filter"
    EXPANDER = "expander_filter"
    GAIN = "gain_filter"
    LIMITER = "limiter_filter"
    NOISE_GATE = "noise_gate_filter"
    NOISE_SUPPRESS = "noise_suppress_filter_v2"
    VST = "vst_filter"
    EQ = "basic_eq_filter"


@dataclass
class OBSFilter:
    """OBS filter definition."""

    name: str
    kind: FilterType
    settings: dict = field(default_factory=dict)
    enabled: bool = True


# =============================================================================
# VIDEO FILTER FACTORIES
# =============================================================================


def create_chromakey_filter(
    key_color: str = "green",
    similarity: int = 400,
    smoothness: int = 80,
    key_spill_reduction: int = 100,
    opacity: float = 1.0,
    contrast: float = 0.0,
    brightness: float = 0.0,
    gamma: float = 0.0,
) -> dict:
    """Create chromakey (green/blue screen) filter.

    Args:
        key_color: 'green', 'blue', 'magenta', or hex color
        similarity: Color match threshold (1-1000, higher = more tolerance)
        smoothness: Edge smoothness (1-1000)
        key_spill_reduction: Reduce color spill (1-1000)
        opacity: Output opacity (0-1)
        contrast: Contrast adjustment (-1 to 1)
        brightness: Brightness adjustment (-1 to 1)
        gamma: Gamma adjustment (-1 to 1)

    Returns:
        Settings dict for chroma_key_filter_v2
    """
    # Convert color name to type
    color_types = {
        "green": "green",
        "blue": "blue",
        "magenta": "magenta",
        "custom": "custom",
    }
    key_type = color_types.get(key_color.lower(), "custom")

    settings = {
        "key_color_type": key_type,
        "similarity": similarity,
        "smoothness": smoothness,
        "spill": key_spill_reduction,
        "opacity": opacity,
        "contrast": contrast,
        "brightness": brightness,
        "gamma": gamma,
    }

    # If custom color, add hex value
    if key_type == "custom":
        settings["key_color"] = key_color

    return settings


def create_color_key_filter(
    key_color: int = 0x00FF00,  # Green
    similarity: int = 80,
    smoothness: int = 50,
) -> dict:
    """Create color key filter (simpler than chromakey).

    Args:
        key_color: Color to key out (hex RGB)
        similarity: Match threshold (1-1000)
        smoothness: Edge smoothness (1-1000)

    Returns:
        Settings dict for color_key_filter_v2
    """
    return {
        "key_color": key_color,
        "similarity": similarity,
        "smoothness": smoothness,
    }


def create_blur_filter(
    blur_type: str = "gaussian",
    blur_size: int = 3,
) -> dict:
    """Create blur filter.

    Args:
        blur_type: 'box', 'gaussian', 'dual_filtering', 'area'
        blur_size: Blur radius (1-20 for gaussian/box)

    Returns:
        Settings dict for blur_filter
    """
    blur_types = {
        "box": 0,
        "gaussian": 1,
        "dual_filtering": 2,
        "area": 3,
    }

    return {
        "type": blur_types.get(blur_type, 1),
        "size": blur_size,
    }


def create_color_correction_filter(
    saturation: float = 0.0,
    contrast: float = 0.0,
    brightness: float = 0.0,
    gamma: float = 0.0,
    hue_shift: float = 0.0,
    opacity: float = 1.0,
    color_add: int = 0x000000,
    color_multiply: int = 0xFFFFFF,
) -> dict:
    """Create color correction filter.

    All values are offsets from neutral (0.0 = no change).

    Args:
        saturation: Saturation offset (-1 to 1)
        contrast: Contrast offset (-1 to 1)
        brightness: Brightness offset (-1 to 1)
        gamma: Gamma offset (-3 to 3)
        hue_shift: Hue rotation in degrees (-180 to 180)
        opacity: Output opacity (0-1)
        color_add: Color to add (RGB)
        color_multiply: Color multiplier (RGB)

    Returns:
        Settings dict for color_filter_v2
    """
    return {
        "saturation": saturation,
        "contrast": contrast,
        "brightness": brightness,
        "gamma": gamma,
        "hue_shift": hue_shift,
        "opacity": opacity,
        "color_add": color_add,
        "color_multiply": color_multiply,
    }


def create_lut_filter(
    lut_path: str,
    lut_amount: float = 1.0,
) -> dict:
    """Create LUT (color grading) filter.

    LUTs provide professional color grading.
    Supports .cube and .png LUT files.

    Args:
        lut_path: Path to LUT file
        lut_amount: Blend amount (0-1)

    Returns:
        Settings dict for clut_filter
    """
    return {
        "path": lut_path,
        "clut_amount": lut_amount,
    }


def create_sharpen_filter(
    sharpness: float = 0.08,
) -> dict:
    """Create sharpen filter.

    Args:
        sharpness: Sharpness amount (0-1)

    Returns:
        Settings dict for sharpness_filter
    """
    return {
        "sharpness": sharpness,
    }


def create_crop_filter(
    left: int = 0,
    right: int = 0,
    top: int = 0,
    bottom: int = 0,
    relative: bool = True,
) -> dict:
    """Create crop filter.

    Args:
        left: Left crop pixels
        right: Right crop pixels
        top: Top crop pixels
        bottom: Bottom crop pixels
        relative: Whether values are relative (percentage) or absolute

    Returns:
        Settings dict for crop_filter
    """
    return {
        "left": left,
        "right": right,
        "top": top,
        "bottom": bottom,
        "relative": relative,
    }


def create_scroll_filter(
    horizontal_speed: float = 0.0,
    vertical_speed: float = 0.0,
    loop: bool = True,
    limit_width: bool = False,
    limit_height: bool = False,
) -> dict:
    """Create scroll filter.

    Args:
        horizontal_speed: Horizontal scroll speed (pixels/frame)
        vertical_speed: Vertical scroll speed (pixels/frame)
        loop: Loop scrolling
        limit_width: Limit to source width
        limit_height: Limit to source height

    Returns:
        Settings dict for scroll_filter
    """
    return {
        "speed_x": horizontal_speed,
        "speed_y": vertical_speed,
        "loop": loop,
        "limit_cx": limit_width,
        "limit_cy": limit_height,
    }


def create_mask_filter(
    mask_type: str = "alpha",
    mask_path: str | None = None,
    color: int = 0xFFFFFF,
    opacity: float = 1.0,
) -> dict:
    """Create mask/blend filter.

    Args:
        mask_type: 'alpha', 'color', 'blend', 'multiply'
        mask_path: Path to mask image
        color: Mask color
        opacity: Opacity

    Returns:
        Settings dict for mask_filter
    """
    types = {
        "alpha": 0,
        "color": 1,
        "blend": 2,
        "multiply": 3,
    }

    settings = {
        "type": types.get(mask_type, 0),
        "color": color,
        "opacity": opacity,
    }

    if mask_path:
        settings["image_path"] = mask_path

    return settings


def create_render_delay_filter(
    delay_ms: int = 0,
) -> dict:
    """Create render delay filter.

    Useful for lip-sync correction.

    Args:
        delay_ms: Delay in milliseconds

    Returns:
        Settings dict for gpu_delay
    """
    return {
        "delay_ms": delay_ms,
    }


# =============================================================================
# AUDIO FILTER FACTORIES
# =============================================================================


def create_noise_suppress_filter(
    method: str = "rnnoise",
    suppress_level: int = -30,
) -> dict:
    """Create noise suppression filter.

    Args:
        method: 'rnnoise' (AI-based) or 'speex' (traditional)
        suppress_level: Suppression in dB (for speex)

    Returns:
        Settings dict for noise_suppress_filter_v2
    """
    methods = {
        "rnnoise": 0,  # RNNoise (AI)
        "speex": 1,  # Speex
        "nvafx": 2,  # NVIDIA (if available)
    }

    return {
        "method": methods.get(method, 0),
        "suppress_level": suppress_level,
    }


def create_compressor_filter(
    ratio: float = 10.0,
    threshold: float = -18.0,
    attack: float = 6.0,
    release: float = 60.0,
    output_gain: float = 0.0,
    sidechain_source: str | None = None,
) -> dict:
    """Create compressor filter.

    Args:
        ratio: Compression ratio (1-32)
        threshold: Threshold in dB (-60 to 0)
        attack: Attack time in ms (1-100)
        release: Release time in ms (1-1000)
        output_gain: Makeup gain in dB (-20 to 20)
        sidechain_source: Source for sidechain

    Returns:
        Settings dict for compressor_filter
    """
    settings = {
        "ratio": ratio,
        "threshold": threshold,
        "attack_time": attack,
        "release_time": release,
        "output_gain": output_gain,
    }

    if sidechain_source:
        settings["sidechain_source"] = sidechain_source

    return settings


def create_noise_gate_filter(
    open_threshold: float = -26.0,
    close_threshold: float = -32.0,
    attack: float = 25.0,
    hold: float = 200.0,
    release: float = 150.0,
) -> dict:
    """Create noise gate filter.

    Args:
        open_threshold: Open threshold in dB
        close_threshold: Close threshold in dB
        attack: Attack time in ms
        hold: Hold time in ms
        release: Release time in ms

    Returns:
        Settings dict for noise_gate_filter
    """
    return {
        "open_threshold": open_threshold,
        "close_threshold": close_threshold,
        "attack_time": attack,
        "hold_time": hold,
        "release_time": release,
    }


def create_gain_filter(
    gain_db: float = 0.0,
) -> dict:
    """Create gain filter.

    Args:
        gain_db: Gain in dB (-30 to 30)

    Returns:
        Settings dict for gain_filter
    """
    return {
        "db": gain_db,
    }


def create_limiter_filter(
    threshold: float = -6.0,
    release: float = 60.0,
) -> dict:
    """Create limiter filter.

    Args:
        threshold: Limiter threshold in dB
        release: Release time in ms

    Returns:
        Settings dict for limiter_filter
    """
    return {
        "threshold": threshold,
        "release_time": release,
    }


def create_eq_filter(
    bands: list[dict] | None = None,
) -> dict:
    """Create EQ filter.

    Args:
        bands: List of band dicts with 'freq', 'gain', 'q'

    Returns:
        Settings dict for basic_eq_filter

    Example:
        create_eq_filter([
            {"freq": 100, "gain": 3, "q": 1.0},  # Boost bass
            {"freq": 1000, "gain": 0, "q": 1.0},  # Neutral mids
            {"freq": 10000, "gain": -2, "q": 1.0},  # Cut highs
        ])
    """
    settings = {}

    if bands:
        for i, band in enumerate(bands[:6]):  # Max 6 bands
            settings[f"band{i + 1}_freq"] = band.get("freq", 1000)
            settings[f"band{i + 1}_gain"] = band.get("gain", 0)
            settings[f"band{i + 1}_q"] = band.get("q", 1.0)

    return settings
