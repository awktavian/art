"""Ambient OS visual palette (canonical).

This module is the single source of truth for Ambient OS colors.

Rules:
- Base palette is Void / Light / Gold.
- Colony colors are contextual only: **one colony at a time**.
  When no colony is speaking, use Gold. When one colony speaks, that colony's
  color replaces Gold as the accent color.
"""

from __future__ import annotations

from typing import Final

from kagami.core.ambient.data_types import Colony, ColonyState


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert #RRGGBB or RRGGBB to (r,g,b)."""
    v = value.strip()
    if v.startswith("#"):
        v = v[1:]
    if len(v) != 6:
        raise ValueError(f"Invalid hex color: {value!r}")
    r = int(v[0:2], 16)
    g = int(v[2:4], 16)
    b = int(v[4:6], 16)
    return (r, g, b)


def rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB to HSV.

    Args:
        r, g, b: RGB values (0-255)

    Returns:
        (hue 0-360, saturation 0-1, value 0-1)
    """
    r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
    max_c = max(r_norm, g_norm, b_norm)
    min_c = min(r_norm, g_norm, b_norm)
    diff = max_c - min_c

    # Value
    v = max_c

    # Saturation
    s = 0.0 if max_c == 0 else diff / max_c

    # Hue
    h = 0.0
    if diff != 0:
        if max_c == r_norm:
            h = 60 * (((g_norm - b_norm) / diff) % 6)
        elif max_c == g_norm:
            h = 60 * (((b_norm - r_norm) / diff) + 2)
        else:
            h = 60 * (((r_norm - g_norm) / diff) + 4)

    return (h, s, v)


# -----------------------------------------------------------------------------
# Base palette (Void / Light / Forge)
# Synchronized with packages/kagami-design/design-tokens.json
# -----------------------------------------------------------------------------

VOID_HEX: Final[str] = "#07060B"  # color.core.void
LIGHT_HEX: Final[str] = "#FFFFFF"  # color.core.white
GOLD_HEX: Final[str] = "#FF9500"  # Forge orange (default accent)

VOID_RGB: Final[tuple[int, int, int]] = _hex_to_rgb(VOID_HEX)
LIGHT_RGB: Final[tuple[int, int, int]] = _hex_to_rgb(LIGHT_HEX)
GOLD_RGB: Final[tuple[int, int, int]] = _hex_to_rgb(GOLD_HEX)


# -----------------------------------------------------------------------------
# Colony accent colors (contextual; ONE at a time)
# Synchronized with packages/kagami-design/design-tokens.json
# -----------------------------------------------------------------------------

COLONY_COLOR_HEX: Final[dict[Colony, str]] = {
    Colony.SPARK: "#FF6B35",  # e1 - Ideation (Red-Orange)
    Colony.FORGE: "#FF9500",  # e2 - Implementation (Orange)
    Colony.FLOW: "#5AC8FA",  # e3 - Adaptation (Cyan)
    Colony.NEXUS: "#AF52DE",  # e4 - Integration (Purple)
    Colony.BEACON: "#FFD60A",  # e5 - Planning (Yellow)
    Colony.GROVE: "#32D74B",  # e6 - Research (Green)
    Colony.CRYSTAL: "#64D2FF",  # e7 - Verification (Light Blue)
}

COLONY_COLORS: Final[dict[Colony, tuple[int, int, int]]] = {
    c: _hex_to_rgb(h) for c, h in COLONY_COLOR_HEX.items()
}


def get_accent_color(
    states: dict[Colony, ColonyState] | None,
    *,
    activation_threshold: float = 0.1,
) -> tuple[tuple[int, int, int], Colony | None, float]:
    """Return (accent_rgb, active_colony, active_activation).

    If no colony is above `activation_threshold`, returns (GOLD_RGB, None, 0.0).
    """
    if not states:
        return (GOLD_RGB, None, 0.0)

    dominant = max(states.items(), key=lambda kv: kv[1].activation)
    colony, state = dominant
    activation = float(state.activation)

    if activation < activation_threshold:
        return (GOLD_RGB, None, 0.0)

    return (COLONY_COLORS.get(colony, GOLD_RGB), colony, activation)
