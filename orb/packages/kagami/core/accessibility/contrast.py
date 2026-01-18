"""Color Contrast Utilities for WCAG Compliance.

Provides utilities for checking and calculating color contrast ratios
to ensure WCAG AA and AAA compliance.

WCAG Requirements:
- Level AA: 4.5:1 for normal text, 3:1 for large text
- Level AAA: 7:1 for normal text, 4.5:1 for large text

Usage:
    from kagami.core.accessibility.contrast import (
        calculate_contrast_ratio,
        check_contrast,
        suggest_accessible_color,
        get_luminance,
    )

    # Check if colors meet contrast requirements
    ratio = calculate_contrast_ratio("#ffffff", "#000000")
    print(f"Contrast ratio: {ratio}:1")  # 21:1

    # Check WCAG compliance
    is_aa = check_contrast("#ffffff", "#767676", level="AA")  # True (4.5:1)
    is_aaa = check_contrast("#ffffff", "#767676", level="AAA")  # False

    # Get a suggested accessible color
    suggested = suggest_accessible_color("#ffffff", "#cccccc", level="AA")

Created: January 1, 2026
Part of: Apps 100/100 Transformation - Phase 1.4
"""

from __future__ import annotations

import colorsys
import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ContrastResult:
    """Result of a contrast check."""

    foreground: str
    background: str
    ratio: float
    meets_aa: bool
    meets_aa_large: bool
    meets_aaa: bool
    meets_aaa_large: bool

    @property
    def ratio_string(self) -> str:
        """Get the ratio as a formatted string."""
        return f"{self.ratio:.2f}:1"


def parse_color(color: str) -> tuple[int, int, int]:
    """Parse a color string to RGB tuple.

    Supports:
    - Hex: "#ffffff", "#fff", "ffffff"
    - RGB: "rgb(255, 255, 255)"

    Args:
        color: Color string

    Returns:
        Tuple of (R, G, B) values (0-255)

    Raises:
        ValueError: If color format is not recognized
    """
    color = color.strip().lower()

    # Remove # prefix if present
    if color.startswith("#"):
        color = color[1:]

    # Handle shorthand hex (#fff → #ffffff)
    if len(color) == 3:
        color = "".join(c + c for c in color)

    # Parse hex
    if len(color) == 6:
        try:
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            return (r, g, b)
        except ValueError:
            pass

    # Parse rgb()
    if color.startswith("rgb("):
        color = color[4:-1]  # Remove "rgb(" and ")"
        parts = [int(p.strip()) for p in color.split(",")]
        if len(parts) == 3:
            return tuple(parts)  # type: ignore[return-value]

    raise ValueError(f"Cannot parse color: {color}")


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB values to hex string.

    Args:
        r: Red (0-255)
        g: Green (0-255)
        b: Blue (0-255)

    Returns:
        Hex color string (e.g., "#ffffff")
    """
    return f"#{r:02x}{g:02x}{b:02x}"


def get_luminance(color: str) -> float:
    """Calculate the relative luminance of a color.

    Uses the WCAG formula for relative luminance:
    L = 0.2126 * R + 0.7152 * G + 0.0722 * B

    Where R, G, B are:
    - If C <= 0.03928: C / 12.92
    - If C > 0.03928: ((C + 0.055) / 1.055) ^ 2.4

    Args:
        color: Color string (hex or rgb)

    Returns:
        Relative luminance (0-1)
    """
    r, g, b = parse_color(color)

    def linearize(c: int) -> float:
        """Convert sRGB to linear RGB."""
        c_norm = c / 255
        if c_norm <= 0.03928:
            return c_norm / 12.92
        return math.pow((c_norm + 0.055) / 1.055, 2.4)

    r_lin = linearize(r)
    g_lin = linearize(g)
    b_lin = linearize(b)

    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(foreground: str, background: str) -> float:
    """Calculate the contrast ratio between two colors.

    Uses the WCAG formula:
    ratio = (L1 + 0.05) / (L2 + 0.05)
    where L1 is the lighter luminance and L2 is the darker.

    Args:
        foreground: Foreground color
        background: Background color

    Returns:
        Contrast ratio (1-21)
    """
    l1 = get_luminance(foreground)
    l2 = get_luminance(background)

    # Ensure L1 is the lighter color
    if l1 < l2:
        l1, l2 = l2, l1

    return (l1 + 0.05) / (l2 + 0.05)


def check_contrast(
    foreground: str,
    background: str,
    level: str = "AA",
    large_text: bool = False,
) -> bool:
    """Check if colors meet WCAG contrast requirements.

    WCAG contrast requirements:
    - AA normal: 4.5:1
    - AA large: 3:1
    - AAA normal: 7:1
    - AAA large: 4.5:1

    Large text is defined as:
    - 14pt (18.67px) bold or larger
    - 18pt (24px) regular or larger

    Args:
        foreground: Foreground color
        background: Background color
        level: WCAG level ("AA" or "AAA")
        large_text: Whether this is for large text

    Returns:
        True if contrast meets requirements
    """
    ratio = calculate_contrast_ratio(foreground, background)

    if level.upper() == "AAA":
        required = 4.5 if large_text else 7.0
    else:  # AA
        required = 3.0 if large_text else 4.5

    return ratio >= required


def check_contrast_detailed(
    foreground: str,
    background: str,
) -> ContrastResult:
    """Get detailed contrast check results.

    Args:
        foreground: Foreground color
        background: Background color

    Returns:
        ContrastResult with all level checks
    """
    ratio = calculate_contrast_ratio(foreground, background)

    return ContrastResult(
        foreground=foreground,
        background=background,
        ratio=ratio,
        meets_aa=ratio >= 4.5,
        meets_aa_large=ratio >= 3.0,
        meets_aaa=ratio >= 7.0,
        meets_aaa_large=ratio >= 4.5,
    )


def suggest_accessible_color(
    background: str,
    preferred_color: str,
    level: str = "AA",
    large_text: bool = False,
) -> str:
    """Suggest an accessible foreground color.

    If the preferred color doesn't meet contrast requirements,
    adjusts its lightness to find an accessible alternative.

    Args:
        background: Background color
        preferred_color: Desired foreground color
        level: WCAG level to meet
        large_text: Whether this is for large text

    Returns:
        An accessible color (possibly the original if it meets requirements)
    """
    if check_contrast(preferred_color, background, level, large_text):
        return preferred_color

    # Convert to HSL and adjust lightness
    r, g, b = parse_color(preferred_color)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

    bg_luminance = get_luminance(background)

    # Determine if we need to lighten or darken
    if bg_luminance > 0.5:
        # Light background - darken the foreground
        direction = -0.05
    else:
        # Dark background - lighten the foreground
        direction = 0.05

    # Iteratively adjust lightness until we meet contrast requirements
    max_iterations = 20
    for _ in range(max_iterations):
        l = max(0, min(1, l + direction))

        r_new, g_new, b_new = colorsys.hls_to_rgb(h, l, s)
        new_color = rgb_to_hex(int(r_new * 255), int(g_new * 255), int(b_new * 255))

        if check_contrast(new_color, background, level, large_text):
            return new_color

        # If we've hit the extremes, stop
        if l <= 0 or l >= 1:
            break

    # Fallback to black or white
    if bg_luminance > 0.5:
        return "#000000"
    else:
        return "#ffffff"


def get_accessible_pairs(
    colors: list[str],
    level: str = "AA",
) -> list[tuple[str, str]]:
    """Find all color pairs that meet contrast requirements.

    Args:
        colors: List of colors to check
        level: WCAG level to meet

    Returns:
        List of (foreground, background) tuples that meet requirements
    """
    pairs = []

    for i, fg in enumerate(colors):
        for bg in colors[i + 1 :]:
            if check_contrast(fg, bg, level):
                pairs.append((fg, bg))
                pairs.append((bg, fg))  # Both directions

    return pairs


# Color-blind simulation helpers


def simulate_protanopia(color: str) -> str:
    """Simulate how a color appears to someone with protanopia (red-blind).

    Args:
        color: Color to simulate

    Returns:
        Simulated color
    """
    r, g, b = parse_color(color)

    # Protanopia transformation matrix
    r_new = 0.567 * r + 0.433 * g + 0.0 * b
    g_new = 0.558 * r + 0.442 * g + 0.0 * b
    b_new = 0.0 * r + 0.242 * g + 0.758 * b

    return rgb_to_hex(
        int(min(255, max(0, r_new))), int(min(255, max(0, g_new))), int(min(255, max(0, b_new)))
    )


def simulate_deuteranopia(color: str) -> str:
    """Simulate how a color appears to someone with deuteranopia (green-blind).

    Args:
        color: Color to simulate

    Returns:
        Simulated color
    """
    r, g, b = parse_color(color)

    # Deuteranopia transformation matrix
    r_new = 0.625 * r + 0.375 * g + 0.0 * b
    g_new = 0.7 * r + 0.3 * g + 0.0 * b
    b_new = 0.0 * r + 0.3 * g + 0.7 * b

    return rgb_to_hex(
        int(min(255, max(0, r_new))), int(min(255, max(0, g_new))), int(min(255, max(0, b_new)))
    )


def simulate_tritanopia(color: str) -> str:
    """Simulate how a color appears to someone with tritanopia (blue-blind).

    Args:
        color: Color to simulate

    Returns:
        Simulated color
    """
    r, g, b = parse_color(color)

    # Tritanopia transformation matrix
    r_new = 0.95 * r + 0.05 * g + 0.0 * b
    g_new = 0.0 * r + 0.433 * g + 0.567 * b
    b_new = 0.0 * r + 0.475 * g + 0.525 * b

    return rgb_to_hex(
        int(min(255, max(0, r_new))), int(min(255, max(0, g_new))), int(min(255, max(0, b_new)))
    )


def check_colorblind_accessible(
    foreground: str,
    background: str,
    level: str = "AA",
) -> dict[str, bool]:
    """Check if color contrast is maintained for colorblind users.

    Args:
        foreground: Foreground color
        background: Background color
        level: WCAG level to meet

    Returns:
        Dictionary with results for each color blindness type
    """
    results = {
        "normal": check_contrast(foreground, background, level),
    }

    for name, simulate in [
        ("protanopia", simulate_protanopia),
        ("deuteranopia", simulate_deuteranopia),
        ("tritanopia", simulate_tritanopia),
    ]:
        sim_fg = simulate(foreground)
        sim_bg = simulate(background)
        results[name] = check_contrast(sim_fg, sim_bg, level)

    return results


__all__ = [
    "ContrastResult",
    "calculate_contrast_ratio",
    "check_colorblind_accessible",
    "check_contrast",
    "check_contrast_detailed",
    "get_accessible_pairs",
    "get_luminance",
    "parse_color",
    "rgb_to_hex",
    "simulate_deuteranopia",
    "simulate_protanopia",
    "simulate_tritanopia",
    "suggest_accessible_color",
]
