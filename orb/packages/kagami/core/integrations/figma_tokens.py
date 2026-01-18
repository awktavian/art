"""Bidirectional design token sync with Figma.

This module provides synchronization between Figma styles and
code-based design tokens (config/design-tokens/).

Pipeline:
1. Export: Read Figma styles → Generate token JSON/CSS
2. Import: Read token files → Update Figma variables (requires scope approval)

Key Features:
- Prismorphism color token extraction
- Typography token generation
- Spacing/sizing token management
- CSS custom property generation
- Tailwind config generation

Scopes Required:
- file_content:read (available)
- file_styles:read (available via file_content)
- file_variables:read/write (pending Figma approval)

Created: January 5, 2026
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Design token output paths
TOKENS_DIR = Path("config/design-tokens")
FIGMA_TOKENS_FILE = TOKENS_DIR / "figma.json"
CSS_TOKENS_FILE = TOKENS_DIR / "tokens.css"
TAILWIND_TOKENS_FILE = TOKENS_DIR / "tailwind-tokens.js"


@dataclass
class DesignToken:
    """A design token value.

    Attributes:
        name: Token name (e.g., "color-spark").
        value: Token value (e.g., "#FF5722").
        type: Token type (color, spacing, typography, etc.).
        description: Optional description.
        figma_id: Figma style/variable ID if synced.
    """

    name: str
    value: str
    type: str
    description: str = ""
    figma_id: str | None = None

    def to_css_var(self) -> str:
        """Convert to CSS custom property."""
        css_name = self.name.replace(".", "-").replace("_", "-")
        return f"--{css_name}: {self.value};"


@dataclass
class DesignTokenSet:
    """Collection of design tokens.

    Attributes:
        tokens: List of tokens.
        source: Source of tokens (figma, code).
        last_sync: Last synchronization timestamp.
        figma_file_key: Associated Figma file key.
    """

    tokens: list[DesignToken] = field(default_factory=list)
    source: str = "figma"
    last_sync: str = ""
    figma_file_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source": self.source,
            "last_sync": self.last_sync,
            "figma_file_key": self.figma_file_key,
            "tokens": [
                {
                    "name": t.name,
                    "value": t.value,
                    "type": t.type,
                    "description": t.description,
                    "figma_id": t.figma_id,
                }
                for t in self.tokens
            ],
        }

    def to_css(self) -> str:
        """Generate CSS custom properties."""
        lines = [
            "/* Design Tokens - Auto-generated from Figma */",
            f"/* Last sync: {self.last_sync} */",
            "",
            ":root {",
        ]

        # Group by type
        by_type: dict[str, list[DesignToken]] = {}
        for token in self.tokens:
            by_type.setdefault(token.type, []).append(token)

        for token_type, type_tokens in by_type.items():
            lines.append(f"  /* {token_type.title()} */")
            for token in type_tokens:
                lines.append(f"  {token.to_css_var()}")
            lines.append("")

        lines.append("}")
        return "\n".join(lines)

    def to_tailwind(self) -> str:
        """Generate Tailwind config extension."""
        lines = [
            "// Design Tokens - Auto-generated from Figma",
            f"// Last sync: {self.last_sync}",
            "",
            "module.exports = {",
            "  theme: {",
            "    extend: {",
        ]

        # Group by type
        colors = [t for t in self.tokens if t.type == "color"]
        spacing = [t for t in self.tokens if t.type == "spacing"]
        [t for t in self.tokens if t.type == "typography"]

        if colors:
            lines.append("      colors: {")
            for token in colors:
                name = token.name.replace("color-", "").replace(".", "-")
                lines.append(f"        '{name}': '{token.value}',")
            lines.append("      },")

        if spacing:
            lines.append("      spacing: {")
            for token in spacing:
                name = token.name.replace("spacing-", "")
                lines.append(f"        '{name}': '{token.value}',")
            lines.append("      },")

        lines.extend(
            [
                "    },",
                "  },",
                "};",
            ]
        )
        return "\n".join(lines)


# Prismorphism color tokens (canonical source)
PRISMORPHISM_COLORS: dict[str, str] = {
    "color.spark": "#FF5722",  # e1 - 620nm Red
    "color.forge": "#FF9800",  # e2 - 590nm Orange
    "color.flow": "#4DB6AC",  # e3 - 570nm Teal
    "color.nexus": "#9C27B0",  # e4 - 510nm Purple
    "color.beacon": "#FFB74D",  # e5 - 475nm Amber
    "color.grove": "#4CAF50",  # e6 - 445nm Green
    "color.crystal": "#7E57C2",  # e7 - 400nm Violet
    # Background variants
    "color.bg.primary": "#0D0D0D",
    "color.bg.secondary": "#1A1A1A",
    "color.bg.glass": "rgba(26, 26, 26, 0.8)",
    # Text
    "color.text.primary": "#FFFFFF",
    "color.text.secondary": "rgba(255, 255, 255, 0.7)",
    "color.text.muted": "rgba(255, 255, 255, 0.5)",
}

# Fibonacci timing tokens
TIMING_TOKENS: dict[str, str] = {
    "timing.instant": "89ms",
    "timing.fast": "144ms",
    "timing.normal": "233ms",
    "timing.slow": "377ms",
    "timing.dramatic": "610ms",
}

# Spacing tokens (8px grid)
SPACING_TOKENS: dict[str, str] = {
    "spacing.xs": "4px",
    "spacing.sm": "8px",
    "spacing.md": "16px",
    "spacing.lg": "24px",
    "spacing.xl": "32px",
    "spacing.2xl": "48px",
    "spacing.3xl": "64px",
}


async def export_tokens_to_code(
    file_key: str = "27pdTgOq30LHZuaeVYtkEN",
) -> DesignTokenSet:
    """Export Figma styles to design tokens.

    Reads styles from the Figma design system file and exports them
    as JSON, CSS, and Tailwind tokens.

    Args:
        file_key: Figma file key. Defaults to Kagami Design System.

    Returns:
        DesignTokenSet containing all extracted tokens.
    """
    try:
        from kagami.core.integrations.figma_direct import get_figma_client

        client = await get_figma_client()

        # Get file styles
        styles_response = await client.get_file_styles(file_key)
        styles = styles_response.get("meta", {}).get("styles", {})

        tokens: list[DesignToken] = []

        # Process color styles (FILL type)
        for style_id, style_data in styles.items() if isinstance(styles, dict) else []:
            style_type = style_data.get("style_type", "")
            name = style_data.get("name", "")

            if style_type == "FILL":
                # This is a color style
                tokens.append(
                    DesignToken(
                        name=f"color.{_sanitize_name(name)}",
                        value=f"#{style_data.get('key', 'UNKNOWN')}",  # Would need to fetch full style
                        type="color",
                        description=style_data.get("description", ""),
                        figma_id=style_id,
                    )
                )
            elif style_type == "TEXT":
                # This is a typography style
                tokens.append(
                    DesignToken(
                        name=f"typography.{_sanitize_name(name)}",
                        value=name,
                        type="typography",
                        description=style_data.get("description", ""),
                        figma_id=style_id,
                    )
                )

        # Add canonical Prismorphism tokens
        for name, value in PRISMORPHISM_COLORS.items():
            if not any(t.name == name for t in tokens):
                tokens.append(
                    DesignToken(
                        name=name,
                        value=value,
                        type="color",
                        description="Prismorphism canonical color",
                    )
                )

        # Add timing tokens
        for name, value in TIMING_TOKENS.items():
            tokens.append(
                DesignToken(
                    name=name,
                    value=value,
                    type="timing",
                    description="Fibonacci timing",
                )
            )

        # Add spacing tokens
        for name, value in SPACING_TOKENS.items():
            tokens.append(
                DesignToken(
                    name=name,
                    value=value,
                    type="spacing",
                    description="8px grid spacing",
                )
            )

        token_set = DesignTokenSet(
            tokens=tokens,
            source="figma",
            last_sync=datetime.now().isoformat(),
            figma_file_key=file_key,
        )

        # Write output files
        await _write_token_files(token_set)

        logger.info(f"Exported {len(tokens)} tokens from Figma")
        return token_set

    except Exception as e:
        logger.error(f"Token export failed: {e}")
        # Return canonical tokens as fallback
        return _get_canonical_tokens()


async def sync_tokens_from_code(
    file_key: str = "27pdTgOq30LHZuaeVYtkEN",
    tokens: DesignTokenSet | None = None,
) -> bool:
    """Sync code tokens back to Figma.

    NOTE: This requires file_variables:write scope which is pending
    Figma approval. Currently this function will fail gracefully.

    Args:
        file_key: Figma file key.
        tokens: Token set to sync. If None, reads from files.

    Returns:
        True if sync successful, False otherwise.
    """
    try:
        from kagami.core.integrations.figma_direct import get_figma_client

        client = await get_figma_client()

        # Load tokens if not provided
        if tokens is None:
            tokens = await _load_token_files()

        if not tokens or not tokens.tokens:
            logger.warning("No tokens to sync")
            return False

        # Convert tokens to Figma variable format
        variables = []
        for token in tokens.tokens:
            if token.type == "color":
                # Create color variable
                variables.append(
                    {
                        "name": token.name,
                        "resolvedType": "COLOR",
                        "value": _hex_to_figma_color(token.value),
                    }
                )

        # Try to create/update variables (requires file_variables:write)
        result = await client.create_variables(file_key, variables)

        if result.get("error"):
            error_msg = result.get("message", "Unknown error")
            if "scope" in error_msg.lower():
                logger.warning(
                    "file_variables:write scope not available. "
                    "Token sync to Figma requires Figma approval."
                )
            else:
                logger.error(f"Variable sync failed: {error_msg}")
            return False

        logger.info(f"Synced {len(variables)} variables to Figma")
        return True

    except Exception as e:
        logger.error(f"Token sync failed: {e}")
        return False


async def _write_token_files(token_set: DesignTokenSet) -> None:
    """Write token files to disk."""
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)

    # Write JSON
    with open(FIGMA_TOKENS_FILE, "w") as f:
        json.dump(token_set.to_dict(), f, indent=2)

    # Write CSS
    with open(CSS_TOKENS_FILE, "w") as f:
        f.write(token_set.to_css())

    # Write Tailwind
    with open(TAILWIND_TOKENS_FILE, "w") as f:
        f.write(token_set.to_tailwind())

    logger.info(f"Wrote token files to {TOKENS_DIR}")


async def _load_token_files() -> DesignTokenSet | None:
    """Load tokens from JSON file."""
    try:
        if FIGMA_TOKENS_FILE.exists():
            with open(FIGMA_TOKENS_FILE) as f:
                data = json.load(f)

            tokens = [
                DesignToken(
                    name=t["name"],
                    value=t["value"],
                    type=t["type"],
                    description=t.get("description", ""),
                    figma_id=t.get("figma_id"),
                )
                for t in data.get("tokens", [])
            ]

            return DesignTokenSet(
                tokens=tokens,
                source=data.get("source", "file"),
                last_sync=data.get("last_sync", ""),
                figma_file_key=data.get("figma_file_key", ""),
            )
    except Exception as e:
        logger.error(f"Failed to load token files: {e}")

    return None


def _get_canonical_tokens() -> DesignTokenSet:
    """Get canonical Prismorphism tokens."""
    tokens = []

    for name, value in PRISMORPHISM_COLORS.items():
        tokens.append(DesignToken(name=name, value=value, type="color"))

    for name, value in TIMING_TOKENS.items():
        tokens.append(DesignToken(name=name, value=value, type="timing"))

    for name, value in SPACING_TOKENS.items():
        tokens.append(DesignToken(name=name, value=value, type="spacing"))

    return DesignTokenSet(
        tokens=tokens,
        source="canonical",
        last_sync=datetime.now().isoformat(),
    )


def _sanitize_name(name: str) -> str:
    """Sanitize style name for token naming."""
    return name.lower().replace(" ", "-").replace("/", ".").replace("_", "-")


def _hex_to_figma_color(hex_color: str) -> dict[str, float]:
    """Convert hex color to Figma RGBA format."""
    hex_color = hex_color.lstrip("#")

    # Handle rgba format
    if hex_color.startswith("rgba"):
        return {"r": 0.5, "g": 0.5, "b": 0.5, "a": 0.5}

    # Parse hex
    try:
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        a = int(hex_color[6:8], 16) / 255 if len(hex_color) == 8 else 1.0
        return {"r": r, "g": g, "b": b, "a": a}
    except (ValueError, IndexError):
        return {"r": 0.5, "g": 0.5, "b": 0.5, "a": 1.0}
