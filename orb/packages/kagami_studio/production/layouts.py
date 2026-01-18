"""Unified slide layout system — TED-style + Gamma-style.

This module defines all available slide layouts and their metadata.

Layout Categories:
- TED-style: Minimal text, high visual impact (6 words max)
- Gamma-style: Content-rich, detailed information

Usage:
    from kagami_studio.production.layouts import (
        SlideLayoutType,
        LAYOUT_METADATA,
        get_layout_config,
    )

    config = get_layout_config(SlideLayoutType.HERO_FULL)
    print(config.needs_image)  # True
    print(config.max_title_words)  # 6

Design Principles (from research):
- TED: Maximum 6 words visible, one idea per slide
- Hero images that evoke emotion
- Bold typography over bullet lists
- Fibonacci timing for animations

Created: 2026-01-09
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SlideLayoutType(str, Enum):
    """All available slide layouts.

    TED-style layouts are optimized for minimal text and high impact.
    Gamma-style layouts support more detailed content.
    """

    # === TED-STYLE LAYOUTS (minimal text, high impact) ===

    HERO_FULL = "hero_full"
    """Full-bleed background image with title overlay.
    Best for: Opening hooks, emotional impact, chapter breaks."""

    HERO_SPLIT = "hero_split"
    """60/40 image + text split.
    Best for: Explanatory content with supporting visual."""

    STAT_FOCUS = "stat_focus"
    """Giant statistic with label.
    Best for: Surprising data, key numbers, metrics."""

    QUOTE = "quote"
    """Large quote with attribution.
    Best for: Expert quotes, memorable statements, wisdom."""

    MINIMAL_TEXT = "minimal_text"
    """Bold text only, no image.
    Best for: Key takeaways, transitions, emphasis."""

    ICON_GRID = "icon_grid"
    """2-4 icons with labels in a grid.
    Best for: Lists of related concepts, features, steps."""

    RECAP = "recap"
    """Numbered recap points.
    Best for: Summaries, conclusions, key points review."""

    # === GAMMA-STYLE LAYOUTS (content-rich) ===

    HERO_LEFT = "hero_left"
    """Image on left, text on right.
    Best for: Feature explanations with visual context."""

    HERO_RIGHT = "hero_right"
    """Text on left, image on right.
    Best for: Alternate visual rhythm in sequences."""

    HERO_BOTTOM = "hero_bottom"
    """Image at bottom, text above.
    Best for: Product reveals, demonstrations."""

    TITLE_ONLY = "title_only"
    """Big centered title (chapter breaks).
    Best for: Section dividers, dramatic pauses."""

    TITLE_SUBTITLE = "title_subtitle"
    """Title + subtitle.
    Best for: Intro slides, topic introductions."""

    BULLETS = "bullets"
    """Title + bullet points.
    Best for: Lists, multiple related points."""

    BULLETS_ICON = "bullets_icon"
    """Title + bullets with icons.
    Best for: Feature lists, steps with visual markers."""

    TWO_COLUMN = "two_column"
    """Two columns of content.
    Best for: Comparisons, parallel concepts."""

    THREE_COLUMN = "three_column"
    """Three columns (features).
    Best for: Feature grids, triple comparisons."""

    COMPARISON = "comparison"
    """Side-by-side comparison.
    Best for: Before/after, pros/cons, alternatives."""

    TIMELINE = "timeline"
    """Horizontal timeline.
    Best for: Processes, history, sequences."""

    CODE = "code"
    """Code snippet with syntax highlighting.
    Best for: Technical presentations, tutorials."""


class LayoutCategory(str, Enum):
    """Layout category for grouping."""

    TED_STYLE = "ted_style"  # Minimal text, high impact
    GAMMA_STYLE = "gamma_style"  # Content-rich


@dataclass(frozen=True)
class LayoutConfig:
    """Configuration and metadata for a layout type.

    Attributes:
        layout_type: The layout enum value
        category: TED or Gamma style
        needs_image: Whether this layout requires a hero image
        max_title_words: Maximum words in title (TED rule: 6)
        max_display_text_words: Maximum words for display text
        supports_subtitle: Whether subtitle is displayed
        supports_bullets: Whether bullet points are displayed
        supports_stat: Whether stat_value/stat_label are used
        supports_quote: Whether quote_text/quote_author are used
        supports_icons: Whether icon_items are displayed
        supports_recap: Whether recap_points are displayed
        description: Human-readable description
    """

    layout_type: SlideLayoutType
    category: LayoutCategory
    needs_image: bool
    max_title_words: int = 6
    max_display_text_words: int = 20
    supports_subtitle: bool = False
    supports_bullets: bool = False
    supports_stat: bool = False
    supports_quote: bool = False
    supports_icons: bool = False
    supports_recap: bool = False
    description: str = ""


# Layout metadata registry
LAYOUT_METADATA: dict[SlideLayoutType, LayoutConfig] = {
    # TED-style layouts
    SlideLayoutType.HERO_FULL: LayoutConfig(
        layout_type=SlideLayoutType.HERO_FULL,
        category=LayoutCategory.TED_STYLE,
        needs_image=True,
        max_title_words=6,
        description="Full-bleed image with title overlay",
    ),
    SlideLayoutType.HERO_SPLIT: LayoutConfig(
        layout_type=SlideLayoutType.HERO_SPLIT,
        category=LayoutCategory.TED_STYLE,
        needs_image=True,
        max_title_words=6,
        supports_subtitle=True,
        description="60/40 image + text split",
    ),
    SlideLayoutType.STAT_FOCUS: LayoutConfig(
        layout_type=SlideLayoutType.STAT_FOCUS,
        category=LayoutCategory.TED_STYLE,
        needs_image=False,
        max_title_words=4,
        supports_stat=True,
        description="Giant statistic with label",
    ),
    SlideLayoutType.QUOTE: LayoutConfig(
        layout_type=SlideLayoutType.QUOTE,
        category=LayoutCategory.TED_STYLE,
        needs_image=False,
        max_title_words=0,
        supports_quote=True,
        description="Large quote with attribution",
    ),
    SlideLayoutType.MINIMAL_TEXT: LayoutConfig(
        layout_type=SlideLayoutType.MINIMAL_TEXT,
        category=LayoutCategory.TED_STYLE,
        needs_image=False,
        max_title_words=8,
        max_display_text_words=12,
        description="Bold text only, no image",
    ),
    SlideLayoutType.ICON_GRID: LayoutConfig(
        layout_type=SlideLayoutType.ICON_GRID,
        category=LayoutCategory.TED_STYLE,
        needs_image=False,
        max_title_words=6,
        supports_icons=True,
        description="2-4 icons with labels",
    ),
    SlideLayoutType.RECAP: LayoutConfig(
        layout_type=SlideLayoutType.RECAP,
        category=LayoutCategory.TED_STYLE,
        needs_image=False,
        max_title_words=4,
        supports_recap=True,
        description="Numbered recap points",
    ),
    # Gamma-style layouts
    SlideLayoutType.HERO_LEFT: LayoutConfig(
        layout_type=SlideLayoutType.HERO_LEFT,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=True,
        max_title_words=8,
        supports_subtitle=True,
        description="Image left, text right",
    ),
    SlideLayoutType.HERO_RIGHT: LayoutConfig(
        layout_type=SlideLayoutType.HERO_RIGHT,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=True,
        max_title_words=8,
        supports_subtitle=True,
        description="Text left, image right",
    ),
    SlideLayoutType.HERO_BOTTOM: LayoutConfig(
        layout_type=SlideLayoutType.HERO_BOTTOM,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=True,
        max_title_words=8,
        description="Image at bottom, text above",
    ),
    SlideLayoutType.TITLE_ONLY: LayoutConfig(
        layout_type=SlideLayoutType.TITLE_ONLY,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=False,
        max_title_words=6,
        description="Big centered title",
    ),
    SlideLayoutType.TITLE_SUBTITLE: LayoutConfig(
        layout_type=SlideLayoutType.TITLE_SUBTITLE,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=False,
        max_title_words=8,
        supports_subtitle=True,
        description="Title + subtitle",
    ),
    SlideLayoutType.BULLETS: LayoutConfig(
        layout_type=SlideLayoutType.BULLETS,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=False,
        max_title_words=8,
        supports_bullets=True,
        description="Title + bullet points",
    ),
    SlideLayoutType.BULLETS_ICON: LayoutConfig(
        layout_type=SlideLayoutType.BULLETS_ICON,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=False,
        max_title_words=8,
        supports_bullets=True,
        supports_icons=True,
        description="Title + bullets with icons",
    ),
    SlideLayoutType.TWO_COLUMN: LayoutConfig(
        layout_type=SlideLayoutType.TWO_COLUMN,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=False,
        max_title_words=8,
        description="Two columns of content",
    ),
    SlideLayoutType.THREE_COLUMN: LayoutConfig(
        layout_type=SlideLayoutType.THREE_COLUMN,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=False,
        max_title_words=8,
        description="Three columns (features)",
    ),
    SlideLayoutType.COMPARISON: LayoutConfig(
        layout_type=SlideLayoutType.COMPARISON,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=False,
        max_title_words=6,
        description="Side-by-side comparison",
    ),
    SlideLayoutType.TIMELINE: LayoutConfig(
        layout_type=SlideLayoutType.TIMELINE,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=False,
        max_title_words=6,
        description="Horizontal timeline",
    ),
    SlideLayoutType.CODE: LayoutConfig(
        layout_type=SlideLayoutType.CODE,
        category=LayoutCategory.GAMMA_STYLE,
        needs_image=False,
        max_title_words=8,
        description="Code with syntax highlighting",
    ),
}


def get_layout_config(layout: SlideLayoutType | str) -> LayoutConfig:
    """Get configuration for a layout type.

    Args:
        layout: Layout type enum or string value

    Returns:
        LayoutConfig with metadata

    Raises:
        ValueError: If layout type not found
    """
    if isinstance(layout, str):
        try:
            layout = SlideLayoutType(layout)
        except ValueError:
            # Fallback to hero_split for unknown layouts
            layout = SlideLayoutType.HERO_SPLIT

    return LAYOUT_METADATA.get(layout, LAYOUT_METADATA[SlideLayoutType.HERO_SPLIT])


def get_ted_style_layouts() -> list[SlideLayoutType]:
    """Get all TED-style layouts (minimal text, high impact)."""
    return [
        lt for lt, config in LAYOUT_METADATA.items() if config.category == LayoutCategory.TED_STYLE
    ]


def get_gamma_style_layouts() -> list[SlideLayoutType]:
    """Get all Gamma-style layouts (content-rich)."""
    return [
        lt
        for lt, config in LAYOUT_METADATA.items()
        if config.category == LayoutCategory.GAMMA_STYLE
    ]


def get_image_layouts() -> list[SlideLayoutType]:
    """Get all layouts that require hero images."""
    return [lt for lt, config in LAYOUT_METADATA.items() if config.needs_image]


def get_text_only_layouts() -> list[SlideLayoutType]:
    """Get all layouts that don't need images."""
    return [lt for lt, config in LAYOUT_METADATA.items() if not config.needs_image]


__all__ = [
    "LAYOUT_METADATA",
    "LayoutCategory",
    "LayoutConfig",
    "SlideLayoutType",
    "get_gamma_style_layouts",
    "get_image_layouts",
    "get_layout_config",
    "get_ted_style_layouts",
    "get_text_only_layouts",
]
