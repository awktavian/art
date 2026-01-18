"""Colony Colors — Single Source of Truth.

This module defines the canonical color for each colony.
All clients (VisionOS, Hub LED, Desktop, Hardware) should
reference these colors to maintain visual consistency.

Colors were selected for:
    - Visual distinctiveness (colorblind-accessible)
    - Emotional association with colony purpose
    - LED reproducibility (SK6812 RGBW compatible)

Colony: Grove (e₆) — Documentation and standards

Example:
    >>> from kagami.core.orb.colors import ColonyColor, get_colony_color
    >>> spark = get_colony_color("spark")
    >>> print(spark.hex)  # #FF6B35
    >>> print(spark.rgb)  # (255, 107, 53)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class ColonyColor:
    """Immutable color representation for a colony.

    Attributes:
        name: Colony name (spark, forge, flow, etc.)
        hex: Hex color code (e.g., #FF6B35)
        rgb: RGB tuple (0-255)
        description: Human-readable color name

    Example:
        >>> color = ColonyColor("spark", "#FF6B35", (255, 107, 53), "Phoenix Orange")
        >>> color.css_rgba(0.5)
        'rgba(255, 107, 53, 0.5)'
    """

    name: str
    hex: str
    rgb: tuple[int, int, int]
    description: str

    def css_rgba(self, alpha: float = 1.0) -> str:
        """Return CSS rgba() string.

        Args:
            alpha: Opacity value 0.0-1.0

        Returns:
            CSS rgba string like 'rgba(255, 107, 53, 0.5)'
        """
        r, g, b = self.rgb
        return f"rgba({r}, {g}, {b}, {alpha})"

    def swift_color(self) -> str:
        """Return Swift Color initializer.

        Returns:
            Swift code like 'Color(red: 1.0, green: 0.42, blue: 0.21)'
        """
        r, g, b = self.rgb
        return f"Color(red: {r / 255:.2f}, green: {g / 255:.2f}, blue: {b / 255:.2f})"

    def led_rgbw(self) -> tuple[int, int, int, int]:
        """Return RGBW tuple for SK6812 LEDs.

        The white channel is calculated from RGB brightness.

        Returns:
            (R, G, B, W) tuple with values 0-255
        """
        r, g, b = self.rgb
        # Calculate white component from minimum of RGB
        w = min(r, g, b)
        return (r - w, g - w, b - w, w)


class Colony(str, Enum):
    """Colony identifiers.

    Each colony has a specific role in the cognitive architecture:
        - SPARK: Ideation, creativity, innovation
        - FORGE: Building, implementation, construction
        - FLOW: Recovery, debugging, healing
        - NEXUS: Integration, connection, bridging
        - BEACON: Planning, architecture, strategy
        - GROVE: Research, documentation, learning
        - CRYSTAL: Verification, testing, quality
    """

    SPARK = "spark"
    FORGE = "forge"
    FLOW = "flow"
    NEXUS = "nexus"
    BEACON = "beacon"
    GROVE = "grove"
    CRYSTAL = "crystal"


# =============================================================================
# Canonical Colony Colors (SINGLE SOURCE OF TRUTH)
# Synchronized with packages/kagami-design/design-tokens.json
# =============================================================================

COLONY_COLORS: dict[str, ColonyColor] = {
    "spark": ColonyColor(
        name="spark",
        hex="#FF6B35",
        rgb=(255, 107, 53),
        description="Red-Orange (Ideation e1)",
    ),
    "forge": ColonyColor(
        name="forge",
        hex="#FF9500",
        rgb=(255, 149, 0),
        description="Orange (Implementation e2)",
    ),
    "flow": ColonyColor(
        name="flow",
        hex="#5AC8FA",
        rgb=(90, 200, 250),
        description="Cyan (Adaptation e3)",
    ),
    "nexus": ColonyColor(
        name="nexus",
        hex="#AF52DE",
        rgb=(175, 82, 222),
        description="Purple (Integration e4)",
    ),
    "beacon": ColonyColor(
        name="beacon",
        hex="#FFD60A",
        rgb=(255, 214, 10),
        description="Yellow (Planning e5)",
    ),
    "grove": ColonyColor(
        name="grove",
        hex="#32D74B",
        rgb=(50, 215, 75),
        description="Green (Research e6)",
    ),
    "crystal": ColonyColor(
        name="crystal",
        hex="#64D2FF",
        rgb=(100, 210, 255),
        description="Light Blue (Verification e7)",
    ),
}

# Default/idle color when no colony is active
DEFAULT_COLOR = ColonyColor(
    name="idle",
    hex="#64D2FF",
    rgb=(100, 210, 255),
    description="Crystal Blue (Idle)",
)

# Error/disconnected color (h(x) < 0 violation)
ERROR_COLOR = ColonyColor(
    name="error",
    hex="#F87171",
    rgb=(248, 113, 113),
    description="Safety Violation Red",
)

# Safety caution color (0 <= h(x) < 0.5)
SAFETY_COLOR = ColonyColor(
    name="safety",
    hex="#FBBF24",
    rgb=(251, 191, 36),
    description="Safety Caution Amber",
)


def get_colony_color(colony: str | None) -> ColonyColor:
    """Get the canonical color for a colony.

    Args:
        colony: Colony name (spark, forge, etc.) or None for default

    Returns:
        ColonyColor for the specified colony, or DEFAULT_COLOR if not found

    Example:
        >>> color = get_colony_color("spark")
        >>> color.hex
        '#FF6B35'
        >>> get_colony_color(None).name
        'idle'
    """
    if colony is None:
        return DEFAULT_COLOR
    return COLONY_COLORS.get(colony.lower(), DEFAULT_COLOR)


def get_safety_color(h_x: float) -> ColonyColor:
    """Get color based on safety score h(x).

    Args:
        h_x: Safety score from 0.0 (unsafe) to 1.0 (safe)

    Returns:
        ColonyColor representing safety state:
        - h(x) >= 0.7: Crystal (safe)
        - h(x) >= 0.3: Safety amber (caution)
        - h(x) < 0.3: Error red (danger)
    """
    if h_x >= 0.7:
        return COLONY_COLORS["crystal"]
    elif h_x >= 0.3:
        return SAFETY_COLOR
    else:
        return ERROR_COLOR
