"""Slide Design System — Gamma-inspired visual layouts.

Modern presentation design with:
- Card-based layouts with accent images
- Hero images (AI-generated or stock)
- Gradient backgrounds
- Icon integration for bullet points
- Smart visual layouts (side-by-side, full-bleed, centered)
- IBM Plex typography (Kagami standard)

Design Philosophy (from Gamma + NotebookLM research):
- Visual storytelling over bullet points
- One idea per slide
- Hero images that reinforce the message
- Consistent theming with gradients
- Dark mode aesthetic with warm accents

Usage:
    from kagami_studio.production.slide_design import (
        SlideLayout, SlideDesign, generate_slide_html
    )

    design = SlideDesign(
        layout=SlideLayout.HERO_LEFT,
        title="Welcome Home",
        subtitle="The future of intelligent living",
        hero_image="/path/to/image.png",  # or generate with AI
        gradient=("0d1117", "1a1a2e"),
        accent_color="4a9eff",
    )

    html = generate_slide_html(design)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SlideLayout(str, Enum):
    """Gamma-inspired slide layouts.

    Each layout is optimized for different content types.
    """

    # Hero layouts - large visual impact
    HERO_FULL = "hero_full"  # Full-bleed background image with text overlay
    HERO_LEFT = "hero_left"  # Image on left, text on right
    HERO_RIGHT = "hero_right"  # Text on left, image on right
    HERO_BOTTOM = "hero_bottom"  # Image at bottom, text above

    # Content layouts - text-focused
    TITLE_ONLY = "title_only"  # Big centered title (chapter breaks)
    TITLE_SUBTITLE = "title_subtitle"  # Title + subtitle (intro slides)
    BULLETS = "bullets"  # Title + bullet points
    BULLETS_ICON = "bullets_icon"  # Title + bullets with icons
    TWO_COLUMN = "two_column"  # Two columns of content
    THREE_COLUMN = "three_column"  # Three columns (features)

    # Visual layouts - diagram/chart focused
    DIAGRAM = "diagram"  # Central diagram/flowchart
    QUOTE = "quote"  # Large quote with attribution
    STATS = "stats"  # Big numbers/statistics
    COMPARISON = "comparison"  # Side-by-side comparison
    TIMELINE = "timeline"  # Horizontal timeline

    # Special layouts
    VIDEO = "video"  # Embedded video placeholder
    CODE = "code"  # Code snippet with syntax highlighting


class GradientPreset(str, Enum):
    """Pre-defined gradient themes."""

    DARK_BLUE = "dark_blue"  # #0d1117 → #1a1a2e (Kagami default)
    MIDNIGHT = "midnight"  # #0f0c29 → #302b63 → #24243e
    OCEAN = "ocean"  # #0f2027 → #203a43 → #2c5364
    SUNSET = "sunset"  # #1a1a2e → #2d1b3d → #1a1a2e
    FOREST = "forest"  # #0d1117 → #1b2f1b → #0d1117
    WARM = "warm"  # #1a1a2e → #2a1a1a → #1a1a2e


GRADIENT_COLORS: dict[GradientPreset, list[str]] = {
    GradientPreset.DARK_BLUE: ["0d1117", "1a1a2e"],
    GradientPreset.MIDNIGHT: ["0f0c29", "302b63", "24243e"],
    GradientPreset.OCEAN: ["0f2027", "203a43", "2c5364"],
    GradientPreset.SUNSET: ["1a1a2e", "2d1b3d", "1a1a2e"],
    GradientPreset.FOREST: ["0d1117", "1b2f1b", "0d1117"],
    GradientPreset.WARM: ["1a1a2e", "2a1a1a", "1a1a2e"],
}


# Lucide icons for bullet points (SVG paths) - CRAFT ENHANCED
# Reference: https://lucide.dev/
ICONS: dict[str, str] = {
    # Check/Success
    "check": "M20 6L9 17l-5-5",
    "check-circle": "M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4L12 14.01l-3-3",
    # Arrows
    "arrow-right": "M5 12h14M12 5l7 7-7 7",
    "arrow-up-right": "M7 17L17 7M7 7h10v10",
    "chevron-right": "M9 18l6-6-6-6",
    # Achievement
    "star": "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
    "trophy": "M6 9H4.5a2.5 2.5 0 0 1 0-5H6M18 9h1.5a2.5 2.5 0 0 0 0-5H18M4 22h16M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22M18 2H6v7a6 6 0 0 0 12 0V2Z",
    # Energy
    "zap": "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
    "flame": "M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z",
    # Emotion
    "heart": "M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z",
    "smile": "M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
    # Security
    "shield": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
    "lock": "M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2zM7 11V7a5 5 0 0 1 10 0v4",
    "shield-check": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10zM9 12l2 2 4-4",
    # Space/Location
    "home": "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 22V12h6v10",
    "globe": "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z",
    "map-pin": "M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0zM12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    # Ideas/Mind
    "lightbulb": "M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5M9 18h6M10 22h4",
    "brain": "M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2zM14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2z",
    "sparkles": "M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0zM20 3v4M22 5h-4M4 17v2M5 18H3",
    # People
    "users": "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
    "user": "M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
    # Science
    "beaker": "M4.5 3h15M6 3v16a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V3M6 14h12",
    "microscope": "M6 18h8M3 22h18M14 22a7 7 0 1 0 0-14h-1M9 14h2M9 12a2 2 0 0 1-2-2V6h6v4a2 2 0 0 1-2 2zM12 6V3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3",
    "dna": "M2 15c6.667-6 13.333 0 20-6M9 22c1.798-1.998 2.518-3.995 2.807-5.993M15 2c-1.798 1.998-2.518 3.995-2.807 5.993M17 6l-2.5-2.5M14 8l-1.5-1.5M7 18l2.5 2.5M3.5 14.5l.5.5M20.5 9.5l-.5-.5M10 16l1.5 1.5",
    # Tech/Tools
    "cpu": "M18 12h2M4 12h2M12 4v2M12 18v2M17 17l1.5 1.5M5.5 5.5L7 7M7 17l-1.5 1.5M17 7l1.5-1.5M9 9h6v6H9z",
    "settings": "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
    # Time
    "clock": "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 6v6l4 2",
    "timer": "M10 2h4M12 14l3-3M12 22a8 8 0 1 0 0-16 8 8 0 0 0 0 16z",
}


@dataclass
class SlideDesign:
    """Design specification for a single slide.

    Attributes:
        layout: Slide layout type
        title: Main title text
        subtitle: Optional subtitle
        points: Bullet points (for bullet layouts)
        icons: Icons for each bullet point (list of icon names)
        hero_image: Path to hero image or URL
        hero_prompt: AI prompt to generate hero image (if no hero_image)
        gradient: Gradient preset or tuple of hex colors
        accent_color: Accent color for highlights (hex without #)
        text_color: Main text color
        stat_value: For STATS layout - the big number
        stat_label: For STATS layout - what the number represents
        quote_text: For QUOTE layout - the quote
        quote_author: For QUOTE layout - attribution
        columns: For multi-column layouts - list of column content
        code: For CODE layout - code snippet
        code_language: For CODE layout - syntax highlighting language
    """

    layout: SlideLayout = SlideLayout.TITLE_SUBTITLE
    title: str = ""
    subtitle: str = ""
    points: list[str] = field(default_factory=list)
    icons: list[str] = field(default_factory=list)
    hero_image: str | Path | None = None
    hero_prompt: str | None = None
    gradient: GradientPreset | tuple[str, ...] = GradientPreset.DARK_BLUE
    accent_color: str = "4a9eff"
    text_color: str = "ffffff"
    stat_value: str = ""
    stat_label: str = ""
    quote_text: str = ""
    quote_author: str = ""
    columns: list[dict[str, Any]] = field(default_factory=list)
    code: str = ""
    code_language: str = "python"

    def get_gradient_css(self) -> str:
        """Get CSS gradient string."""
        if isinstance(self.gradient, GradientPreset):
            colors = GRADIENT_COLORS[self.gradient]
        else:
            colors = list(self.gradient)

        if len(colors) == 1:
            return f"#{colors[0]}"
        elif len(colors) == 2:
            return f"linear-gradient(135deg, #{colors[0]} 0%, #{colors[1]} 100%)"
        else:
            stops = ", ".join(
                f"#{c} {int(i * 100 / (len(colors) - 1))}%" for i, c in enumerate(colors)
            )
            return f"linear-gradient(135deg, {stops})"


def generate_slide_html(design: SlideDesign, index: int = 0) -> str:
    """Generate HTML for a single slide.

    Args:
        design: SlideDesign specification
        index: Slide index (for IDs)

    Returns:
        HTML string for the slide
    """
    gradient = design.get_gradient_css()
    layout = design.layout

    # Base slide container
    html = f"""
<div class="slide" id="slide-{index}" style="background: {gradient};">
    <div class="slide-content layout-{layout.value}">
"""

    # Generate layout-specific content
    if layout == SlideLayout.TITLE_ONLY:
        html += _render_title_only(design)
    elif layout == SlideLayout.TITLE_SUBTITLE:
        html += _render_title_subtitle(design)
    elif layout == SlideLayout.BULLETS:
        html += _render_bullets(design)
    elif layout == SlideLayout.BULLETS_ICON:
        html += _render_bullets_icon(design)
    elif layout == SlideLayout.HERO_FULL:
        html += _render_hero_full(design)
    elif layout == SlideLayout.HERO_LEFT:
        html += _render_hero_split(design, image_side="left")
    elif layout == SlideLayout.HERO_RIGHT:
        html += _render_hero_split(design, image_side="right")
    elif layout == SlideLayout.QUOTE:
        html += _render_quote(design)
    elif layout == SlideLayout.STATS:
        html += _render_stats(design)
    elif layout == SlideLayout.TWO_COLUMN:
        html += _render_columns(design, count=2)
    elif layout == SlideLayout.THREE_COLUMN:
        html += _render_columns(design, count=3)
    elif layout == SlideLayout.CODE:
        html += _render_code(design)
    else:
        # Fallback to title/subtitle
        html += _render_title_subtitle(design)

    html += """
    </div>
</div>
"""
    return html


def _render_title_only(design: SlideDesign) -> str:
    """Big centered title - for chapter breaks."""
    return f"""
        <h1 class="title-only">{design.title}</h1>
"""


def _render_title_subtitle(design: SlideDesign) -> str:
    """Title + subtitle - for intro slides."""
    subtitle_html = f'<p class="subtitle">{design.subtitle}</p>' if design.subtitle else ""
    return f"""
        <div class="title-block">
            <h1 class="title">{design.title}</h1>
            {subtitle_html}
        </div>
"""


def _render_bullets(design: SlideDesign) -> str:
    """Title + bullet points."""
    points_html = "\n".join(f'<li class="bullet-item">{point}</li>' for point in design.points)
    return f"""
        <h2 class="section-title">{design.title}</h2>
        <ul class="bullet-list">
            {points_html}
        </ul>
"""


def _render_bullets_icon(design: SlideDesign) -> str:
    """Title + bullets with icons."""
    items_html = []
    for i, point in enumerate(design.points):
        icon_name = design.icons[i] if i < len(design.icons) else "check"
        icon_path = ICONS.get(icon_name, ICONS["check"])
        items_html.append(f"""
            <li class="bullet-item-icon">
                <svg class="bullet-icon" viewBox="0 0 24 24" fill="none"
                     stroke="#{design.accent_color}" stroke-width="2"
                     stroke-linecap="round" stroke-linejoin="round">
                    <path d="{icon_path}"/>
                </svg>
                <span>{point}</span>
            </li>
        """)

    return f"""
        <h2 class="section-title">{design.title}</h2>
        <ul class="bullet-list-icon">
            {"".join(items_html)}
        </ul>
"""


def _image_to_data_uri(image_path: str) -> str:
    """Convert image file to base64 data URI for reliable embedding."""
    import base64
    from pathlib import Path

    if not image_path:
        return ""

    path = Path(image_path)
    if not path.exists():
        logger.warning(f"Image not found: {image_path}")
        return ""

    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        # Determine MIME type
        suffix = path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime = mime_types.get(suffix, "image/png")

        return f"data:{mime};base64,{data}"
    except Exception as e:
        logger.warning(f"Failed to embed image {image_path}: {e}")
        return ""


def _render_hero_full(design: SlideDesign) -> str:
    """Full-bleed background image with text overlay."""
    # Embed image as base64 data URI for reliable loading
    image_data = _image_to_data_uri(design.hero_image) if design.hero_image else ""

    if image_data:
        bg_style = f"background-image: url('{image_data}');"
    else:
        bg_style = ""

    return f"""
        <div class="hero-full" style="{bg_style}">
            <div class="hero-overlay">
                <h1 class="hero-title">{design.title}</h1>
                <p class="hero-subtitle">{design.subtitle}</p>
            </div>
        </div>
"""


def _render_hero_split(design: SlideDesign, image_side: str = "left") -> str:
    """Split layout with image on one side, text on other."""
    # Embed image as base64 data URI for reliable loading
    image_data = _image_to_data_uri(design.hero_image) if design.hero_image else ""

    points_html = ""
    if design.points:
        points_html = (
            "<ul class='hero-points'>" + "".join(f"<li>{p}</li>" for p in design.points) + "</ul>"
        )

    if image_data:
        image_div = f"""
        <div class="hero-image-container">
            <img src="{image_data}" class="hero-image" alt="{design.title}">
        </div>
"""
    else:
        image_div = '<div class="hero-image-container"></div>'
    text_div = f"""
        <div class="hero-text-container">
            <h1 class="hero-title">{design.title}</h1>
            <p class="hero-subtitle">{design.subtitle}</p>
            {points_html}
        </div>
"""
    if image_side == "left":
        return f'<div class="hero-split">{image_div}{text_div}</div>'
    else:
        return f'<div class="hero-split">{text_div}{image_div}</div>'


def _render_quote(design: SlideDesign) -> str:
    """Large quote with attribution."""
    return f"""
        <blockquote class="quote-block">
            <p class="quote-text">"{design.quote_text}"</p>
            <cite class="quote-author">— {design.quote_author}</cite>
        </blockquote>
"""


def _render_stats(design: SlideDesign) -> str:
    """Big number/statistic."""
    return f"""
        <div class="stats-block">
            <div class="stat-value" style="color: #{design.accent_color};">
                {design.stat_value}
            </div>
            <div class="stat-label">{design.stat_label}</div>
        </div>
"""


def _render_columns(design: SlideDesign, count: int) -> str:
    """Multi-column layout."""
    columns_html = []
    for _i, col in enumerate(design.columns[:count]):
        title = col.get("title", "")
        content = col.get("content", "")
        icon_name = col.get("icon", "")

        icon_html = ""
        if icon_name and icon_name in ICONS:
            icon_html = f"""
                <svg class="column-icon" viewBox="0 0 24 24" fill="none"
                     stroke="#{design.accent_color}" stroke-width="2"
                     stroke-linecap="round" stroke-linejoin="round">
                    <path d="{ICONS[icon_name]}"/>
                </svg>
            """

        columns_html.append(f"""
            <div class="column">
                {icon_html}
                <h3 class="column-title">{title}</h3>
                <p class="column-content">{content}</p>
            </div>
        """)

    return f"""
        <h2 class="section-title">{design.title}</h2>
        <div class="columns columns-{count}">
            {"".join(columns_html)}
        </div>
"""


def _render_code(design: SlideDesign) -> str:
    """Code snippet with syntax highlighting placeholder."""
    return f"""
        <h2 class="section-title">{design.title}</h2>
        <pre class="code-block" data-language="{design.code_language}">
            <code>{design.code}</code>
        </pre>
"""


def get_slide_css(resolution: tuple[int, int] = (1920, 1080)) -> str:
    """Get CSS for all slide layouts.

    Uses IBM Plex fonts per Kagami visual standards.
    """
    width, height = resolution
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    width: {width}px;
    height: {height}px;
    overflow: hidden;
    font-family: 'IBM Plex Sans', -apple-system, sans-serif;
    color: #ffffff;
    background: linear-gradient(135deg, #0a0a12 0%, #0d1117 50%, #0a0f1a 100%);
}}

/* ═══════════════════════════════════════════════════════════════════
   TRANSCENDENT EFFECTS — 150/100 QUALITY
   ═══════════════════════════════════════════════════════════════════ */

/* Animated gradient background overlay */
.slide::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background:
        radial-gradient(ellipse at 20% 80%, rgba(0, 240, 255, 0.08) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 20%, rgba(255, 215, 0, 0.06) 0%, transparent 50%),
        radial-gradient(ellipse at 50% 50%, rgba(74, 158, 255, 0.04) 0%, transparent 60%);
    animation: ambientPulse 8s ease-in-out infinite;
    pointer-events: none;
    z-index: 0;
}}

@keyframes ambientPulse {{
    0%, 100% {{ opacity: 0.6; transform: scale(1); }}
    50% {{ opacity: 1; transform: scale(1.02); }}
}}

/* Floating particles overlay */
.slide::after {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-image:
        radial-gradient(2px 2px at 10% 20%, rgba(0, 240, 255, 0.4) 50%, transparent 50%),
        radial-gradient(2px 2px at 30% 70%, rgba(255, 215, 0, 0.3) 50%, transparent 50%),
        radial-gradient(1px 1px at 50% 30%, rgba(255, 255, 255, 0.5) 50%, transparent 50%),
        radial-gradient(2px 2px at 70% 80%, rgba(0, 240, 255, 0.3) 50%, transparent 50%),
        radial-gradient(1px 1px at 90% 40%, rgba(255, 215, 0, 0.4) 50%, transparent 50%),
        radial-gradient(1px 1px at 20% 90%, rgba(255, 255, 255, 0.3) 50%, transparent 50%),
        radial-gradient(2px 2px at 80% 10%, rgba(74, 158, 255, 0.4) 50%, transparent 50%);
    animation: floatParticles 20s linear infinite;
    pointer-events: none;
    z-index: 1;
    opacity: 0.7;
}}

@keyframes floatParticles {{
    0% {{ transform: translateY(0) rotate(0deg); }}
    100% {{ transform: translateY(-20px) rotate(5deg); }}
}}

/* Decorative corner accents */
.slide-content::before {{
    content: "";
    position: absolute;
    top: 40px;
    left: 40px;
    width: 120px;
    height: 120px;
    border-left: 3px solid rgba(0, 240, 255, 0.4);
    border-top: 3px solid rgba(0, 240, 255, 0.4);
    border-radius: 4px 0 0 0;
    animation: cornerPulse 4s ease-in-out infinite;
    z-index: 2;
}}

.slide-content::after {{
    content: "";
    position: absolute;
    bottom: 240px;
    right: 40px;
    width: 120px;
    height: 120px;
    border-right: 3px solid rgba(255, 215, 0, 0.3);
    border-bottom: 3px solid rgba(255, 215, 0, 0.3);
    border-radius: 0 0 4px 0;
    animation: cornerPulse 4s ease-in-out infinite 2s;
    z-index: 2;
}}

@keyframes cornerPulse {{
    0%, 100% {{ opacity: 0.4; }}
    50% {{ opacity: 0.8; }}
}}

.slide {{
    position: absolute;
    width: 100%;
    height: 100%;
    display: none;
    padding: 50px 70px 200px 70px;  /* BOTTOM padding reserves space for lower third */
}}

.slide.active {{
    display: flex;
}}

.slide-content {{
    width: 100%;
    height: 100%;  /* Fill available (parent has bottom padding for subtitles) */
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    overflow: visible;
}}

/* Title Only - TRANSCENDENT */
.title-only {{
    font-size: 140px;  /* MASSIVE */
    font-weight: 700;
    text-align: center;
    line-height: 1.05;
    padding: 60px 40px;
    background: linear-gradient(135deg,
        #fff 0%,
        #00f0ff 25%,
        #fff 40%,
        #ffd700 55%,
        #00f0ff 70%,
        #fff 100%);
    background-size: 400% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation:
        shimmer 4s ease-in-out infinite,
        titlePulse 2s ease-in-out infinite;
    filter: drop-shadow(0 0 60px rgba(0, 240, 255, 0.5));
    position: relative;
    z-index: 10;
}}

.title-only::after {{
    content: attr(data-text);
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(135deg, #00f0ff, #ffd700);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: blur(30px);
    opacity: 0.5;
    animation: glowPulse 3s ease-in-out infinite;
    z-index: -1;
}}

@keyframes titlePulse {{
    0%, 100% {{ transform: scale(1); }}
    50% {{ transform: scale(1.01); }}
}}

@keyframes glowPulse {{
    0%, 100% {{ opacity: 0.3; filter: blur(30px); }}
    50% {{ opacity: 0.6; filter: blur(40px); }}
}}

/* Title + Subtitle - CRAFT ENHANCED */
.title-block {{
    text-align: center;
    padding: 80px 60px;
}}

.title {{
    font-size: 96px;
    font-weight: 700;
    margin-bottom: 32px;
    background: linear-gradient(135deg,
        #fff 0%,
        #00f0ff 30%,
        #fff 50%,
        #ffd700 70%,
        #fff 100%);
    background-size: 300% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 6s ease-in-out infinite;
    filter: drop-shadow(0 0 30px rgba(0, 240, 255, 0.3));
}}

.subtitle {{
    font-size: 44px;
    font-weight: 400;
    color: rgba(255, 255, 255, 1);  /* MAXIMUM CONTRAST */
    max-width: 1200px;
    margin: 0 auto;
    line-height: 1.5;
    opacity: 0;
    transform: translateY(20px);
    animation: fadeUp 610ms cubic-bezier(0.16, 1, 0.3, 1) 233ms forwards;
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
}}

@keyframes fadeUp {{
    to {{
        opacity: 1;
        transform: translateY(0);
    }}
}}

/* Section Title - TRANSCENDENT */
.section-title {{
    font-size: 88px;  /* EVEN BIGGER */
    font-weight: 700;
    margin-bottom: 48px;
    background: linear-gradient(135deg,
        #fff 0%,
        #00f0ff 15%,
        #fff 30%,
        #ffd700 45%,
        #00f0ff 60%,
        #fff 75%,
        #ffd700 90%,
        #fff 100%);
    background-size: 500% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmerFast 4s ease-in-out infinite;
    filter: drop-shadow(0 0 50px rgba(0, 240, 255, 0.6));
    letter-spacing: -0.02em;
    position: relative;
    z-index: 10;
}}

@keyframes shimmerFast {{
    0%, 100% {{ background-position: 100% 50%; }}
    50% {{ background-position: 0% 50%; }}
}}

@keyframes shimmer {{
    0%, 100% {{ background-position: 100% 50%; }}
    50% {{ background-position: 0% 50%; }}
}}

/* Bullets */
.bullet-list {{
    list-style: none;
    font-size: 36px;
    line-height: 1.7;
    padding: 20px 0;
}}

.bullet-item {{
    position: relative;
    padding-left: 50px;
    margin-bottom: 24px;
    opacity: 0;
    transform: translateX(-20px);
    animation: slideIn 0.5s ease forwards;
}}

.bullet-item::before {{
    content: "•";
    position: absolute;
    left: 0;
    color: #4a9eff;
    font-weight: bold;
    font-size: 48px;
    line-height: 1;
}}

/* Bullets with Icons - TRANSCENDENT */
.bullet-list-icon {{
    list-style: none;
    font-size: 38px;  /* EVEN LARGER text */
    margin-top: 20px;
}}

.bullet-item-icon {{
    display: flex;
    align-items: center;
    margin-bottom: 18px;
    opacity: 0;
    transform: translateX(-40px) scale(0.95);
    animation: bulletSlideIn 500ms cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
    padding: 28px 40px;
    background: linear-gradient(135deg,
        rgba(0, 240, 255, 0.12) 0%,
        rgba(74, 158, 255, 0.06) 50%,
        rgba(255, 215, 0, 0.04) 100%);
    border-radius: 24px;
    border-left: 6px solid transparent;
    border-image: linear-gradient(180deg, #00f0ff, #ffd700) 1;
    transition: all 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
    box-shadow:
        0 10px 40px rgba(0,0,0,0.3),
        0 0 30px rgba(0, 240, 255, 0.15),
        inset 0 1px 0 rgba(255,255,255,0.1);
    font-weight: 500;
    position: relative;
    overflow: hidden;
}}

/* Animated border glow */
.bullet-item-icon::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 6px;
    height: 100%;
    background: linear-gradient(180deg, #00f0ff, #ffd700, #00f0ff);
    background-size: 100% 200%;
    animation: borderGlow 3s ease-in-out infinite;
}}

@keyframes borderGlow {{
    0%, 100% {{ background-position: 0 0; opacity: 0.8; }}
    50% {{ background-position: 0 100%; opacity: 1; }}
}}

/* Staggered animations */
.bullet-item-icon:nth-child(1) {{ animation-delay: 100ms; }}
.bullet-item-icon:nth-child(2) {{ animation-delay: 200ms; }}
.bullet-item-icon:nth-child(3) {{ animation-delay: 300ms; }}
.bullet-item-icon:nth-child(4) {{ animation-delay: 400ms; }}
.bullet-item-icon:nth-child(5) {{ animation-delay: 500ms; }}

@keyframes bulletSlideIn {{
    to {{
        opacity: 1;
        transform: translateX(0) scale(1);
    }}
}}

.bullet-item-icon:hover {{
    background: linear-gradient(135deg,
        rgba(0, 240, 255, 0.2) 0%,
        rgba(74, 158, 255, 0.1) 50%,
        rgba(255, 215, 0, 0.08) 100%);
    transform: translateX(16px) scale(1.02);
    box-shadow:
        0 16px 50px rgba(0,0,0,0.4),
        0 0 50px rgba(0, 240, 255, 0.25),
        inset 0 1px 0 rgba(255,255,255,0.15);
}}

.bullet-icon {{
    width: 60px;  /* MAXIMUM SIZE */
    height: 60px;
    min-width: 60px;
    margin-right: 32px;
    padding: 12px;
    background: linear-gradient(135deg,
        rgba(0, 240, 255, 0.35) 0%,
        rgba(74, 158, 255, 0.25) 100%);
    border-radius: 16px;
    filter: drop-shadow(0 0 20px rgba(0, 240, 255, 0.7));
    animation: iconPulse 3s ease-in-out infinite;
}}

@keyframes iconPulse {{
    0%, 100% {{ transform: scale(1); filter: drop-shadow(0 0 20px rgba(0, 240, 255, 0.7)); }}
    50% {{ transform: scale(1.05); filter: drop-shadow(0 0 30px rgba(0, 240, 255, 0.9)); }}
}}

/* Hero Full - FILLS AVAILABLE SPACE */
/* Hero Full - TRANSCENDENT */
.hero-full {{
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 500px;
    background-size: 115%;  /* Start slightly zoomed for Ken Burns range */
    background-position: center;
    border-radius: 28px;
    overflow: hidden;
    box-shadow:
        0 30px 80px rgba(0, 0, 0, 0.6),
        0 0 100px rgba(0, 240, 255, 0.2),
        inset 0 0 0 1px rgba(255,255,255,0.1);
    /* DRAMATIC Ken Burns on background */
    animation: heroKenBurns 15s ease-in-out infinite alternate;
}}

/* DRAMATIC hero background Ken Burns */
@keyframes heroKenBurns {{
    0% {{
        background-size: 115%;
        background-position: 45% 45%;
    }}
    33% {{
        background-size: 120%;
        background-position: 55% 40%;
    }}
    66% {{
        background-size: 125%;
        background-position: 50% 55%;
    }}
    100% {{
        background-size: 130%;
        background-position: 45% 50%;
    }}
}}

/* Original subtle zoom */
@keyframes heroZoom {{
    0% {{ background-size: 100% auto; background-position: center; }}
    100% {{ background-size: 110% auto; background-position: center top; }}
}}

.hero-overlay {{
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    padding: 80px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    background: linear-gradient(
        to bottom,
        transparent 30%,
        rgba(0,0,0,0.4) 60%,
        rgba(0,0,0,0.9) 100%
    );
}}

/* Animated vignette */
.hero-overlay::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.4) 100%);
    animation: vignettePulse 8s ease-in-out infinite;
    pointer-events: none;
}}

@keyframes vignettePulse {{
    0%, 100% {{ opacity: 0.6; }}
    50% {{ opacity: 0.8; }}
}}

.hero-title {{
    font-size: 108px;  /* MASSIVE for impact */
    font-weight: 700;
    margin-bottom: 28px;
    text-shadow:
        0 4px 20px rgba(0,0,0,0.8),
        0 8px 40px rgba(0,0,0,0.5),
        0 0 80px rgba(0, 240, 255, 0.5);
    letter-spacing: -0.03em;
    position: relative;
    z-index: 10;
    animation: heroTitleGlow 4s ease-in-out infinite;
}}

@keyframes heroTitleGlow {{
    0%, 100% {{ text-shadow: 0 4px 20px rgba(0,0,0,0.8), 0 0 60px rgba(0, 240, 255, 0.4); }}
    50% {{ text-shadow: 0 4px 20px rgba(0,0,0,0.8), 0 0 100px rgba(0, 240, 255, 0.6); }}
}}

.hero-subtitle {{
    font-size: 44px;  /* BIGGER */
    font-weight: 400;
    color: rgba(255, 255, 255, 0.98);
    text-shadow:
        0 2px 10px rgba(0,0,0,0.8),
        0 0 40px rgba(255, 255, 255, 0.2);
    letter-spacing: 0.02em;
    position: relative;
    z-index: 10;
}}

/* Hero Split - FILLS AVAILABLE SPACE */
.hero-split {{
    display: flex;
    width: 100%;
    height: 100%;  /* Fill parent */
    gap: 60px;
    align-items: center;  /* Vertically center */
}}

.hero-image-container {{
    flex: 1.2;  /* Image takes more space */
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    padding: 16px;
    overflow: hidden;
    border-radius: 28px;
}}

/* Animated border glow around image */
.hero-image-container::before {{
    content: "";
    position: absolute;
    top: -2px;
    left: -2px;
    right: -2px;
    bottom: -2px;
    background: linear-gradient(45deg,
        #00f0ff 0%,
        transparent 40%,
        transparent 60%,
        #ffd700 100%);
    border-radius: 30px;
    animation: borderRotate 6s linear infinite;
    z-index: 0;
    opacity: 0.6;
}}

@keyframes borderRotate {{
    0% {{ transform: rotate(0deg); }}
    100% {{ transform: rotate(360deg); }}
}}

.hero-image {{
    width: 100%;
    height: 100%;
    border-radius: 24px;
    box-shadow:
        0 30px 80px rgba(0, 0, 0, 0.7),
        0 0 80px rgba(0, 240, 255, 0.3),
        inset 0 0 0 1px rgba(255,255,255,0.15);
    object-fit: cover;
    /* DRAMATIC Ken Burns - visible motion over slide duration */
    animation: kenBurnsDramatic 12s ease-in-out infinite alternate;
    position: relative;
    z-index: 1;
}}

/* DRAMATIC Ken Burns - noticeable zoom and pan */
@keyframes kenBurnsDramatic {{
    0% {{
        transform: scale(1.0) translate(0%, 0%);
    }}
    25% {{
        transform: scale(1.08) translate(-2%, 1%);
    }}
    50% {{
        transform: scale(1.12) translate(1%, -1%);
    }}
    75% {{
        transform: scale(1.06) translate(-1%, 2%);
    }}
    100% {{
        transform: scale(1.15) translate(2%, -2%);
    }}
}}

/* Original subtle Ken Burns for reference */
@keyframes kenBurns {{
    0% {{ transform: scale(1) translateX(0); }}
    100% {{ transform: scale(1.08) translateX(-2%); }}
}}

.hero-text-container {{
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;  /* Vertically center text */
    padding: 20px;
}}

.hero-text-container .hero-title {{
    font-size: 72px;  /* BOLD - readable at distance */
    line-height: 1.1;
    margin-bottom: 24px;
    background: linear-gradient(135deg,
        #fff 0%,
        #00f0ff 30%,
        #fff 60%,
        #ffd700 100%);
    background-size: 200% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 0 30px rgba(0, 240, 255, 0.4));
}}

.hero-text-container .hero-subtitle {{
    font-size: 32px;  /* LARGER - easily readable */
    margin-bottom: 40px;
    color: rgba(255,255,255,0.95);  /* HIGH CONTRAST */
    font-weight: 400;
    line-height: 1.4;
}}

.hero-points {{
    list-style: none;
    margin-top: 20px;
    font-size: 34px;  /* OPTIMAL SIZE */
    line-height: 1.4;
}}

.hero-points li {{
    padding: 20px 28px 20px 52px;
    position: relative;
    margin-bottom: 14px;
    border-left: 5px solid transparent;
    background: linear-gradient(90deg,
        rgba(0, 240, 255, 0.15) 0%,
        rgba(74, 158, 255, 0.08) 50%,
        rgba(255, 255, 255, 0.02) 100%);
    border-radius: 0 16px 16px 0;
    font-weight: 500;
    box-shadow:
        0 6px 24px rgba(0,0,0,0.2),
        0 0 20px rgba(0, 240, 255, 0.1);
    position: relative;
    overflow: hidden;
    opacity: 0;
    transform: translateX(-20px);
    animation: pointSlideIn 400ms ease forwards;
}}

/* Animated left border */
.hero-points li::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 5px;
    background: linear-gradient(180deg, #00f0ff, #ffd700);
    animation: pointBorderGlow 2s ease-in-out infinite;
}}

@keyframes pointBorderGlow {{
    0%, 100% {{ opacity: 0.8; }}
    50% {{ opacity: 1; box-shadow: 0 0 15px rgba(0, 240, 255, 0.5); }}
}}

/* Arrow indicator */
.hero-points li::after {{
    content: "→";
    position: absolute;
    left: 16px;
    top: 50%;
    transform: translateY(-50%);
    color: #00f0ff;
    font-weight: 700;
    font-size: 24px;
    text-shadow: 0 0 10px rgba(0, 240, 255, 0.5);
}}

/* Staggered entry */
.hero-points li:nth-child(1) {{ animation-delay: 150ms; }}
.hero-points li:nth-child(2) {{ animation-delay: 300ms; }}
.hero-points li:nth-child(3) {{ animation-delay: 450ms; }}
.hero-points li:nth-child(4) {{ animation-delay: 600ms; }}

@keyframes pointSlideIn {{
    to {{
        opacity: 1;
        transform: translateX(0);
    }}
}}

.hero-points li::before {{
    content: "→";
    position: absolute;
    left: 12px;
    color: #4a9eff;
    font-weight: bold;
}}

/* Quote */
.quote-block {{
    max-width: 1400px;
    margin: 0 auto;
    text-align: center;
    padding: 60px 40px;
}}

.quote-text {{
    font-size: 64px;
    font-weight: 300;
    font-style: italic;
    line-height: 1.4;
    color: rgba(255, 255, 255, 0.95);
    position: relative;
}}

.quote-text::before {{
    content: '"';
    position: absolute;
    top: -40px;
    left: -40px;
    font-size: 200px;
    color: rgba(74, 158, 255, 0.2);
    font-family: Georgia, serif;
    line-height: 1;
}}

.quote-author {{
    display: block;
    margin-top: 48px;
    font-size: 32px;
    color: rgba(255, 255, 255, 0.7);
    font-style: normal;
}}

/* Stats */
.stats-block {{
    text-align: center;
    padding: 60px 40px;
}}

.stat-value {{
    font-size: 220px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 32px;
    background: linear-gradient(135deg,
        #fff 0%,
        #00f0ff 50%,
        #ffd700 100%);
    background-size: 200% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 4s ease-in-out infinite;
    filter: drop-shadow(0 0 40px rgba(0, 240, 255, 0.4));
}}

.stat-label {{
    font-size: 48px;
    font-weight: 400;
    color: rgba(255, 255, 255, 0.9);
}}

/* Columns */
.columns {{
    display: flex;
    gap: 40px;
    margin-top: 40px;
    padding: 20px;
}}

.columns-2 .column {{ flex: 1; }}
.columns-3 .column {{ flex: 1; }}

.column {{
    text-align: center;
    padding: 48px 32px;
    background: rgba(255, 255, 255, 0.06);
    border-radius: 20px;
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
}}

.column-icon {{
    width: 64px;
    height: 64px;
    margin-bottom: 28px;
}}

.column-title {{
    font-size: 36px;
    font-weight: 600;
    margin-bottom: 20px;
}}

.column-content {{
    font-size: 24px;
    color: rgba(255, 255, 255, 0.85);
    line-height: 1.6;
}}

/* Code */
.code-block {{
    background: rgba(0, 0, 0, 0.4);
    border-radius: 12px;
    padding: 32px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 20px;
    line-height: 1.6;
    overflow-x: auto;
}}

/* Animations */
@keyframes slideIn {{
    to {{
        opacity: 1;
        transform: translateX(0);
    }}
}}

@keyframes fadeIn {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
}}

.bullet-item:nth-child(1) {{ animation-delay: 0.1s; }}
.bullet-item:nth-child(2) {{ animation-delay: 0.2s; }}
.bullet-item:nth-child(3) {{ animation-delay: 0.3s; }}
.bullet-item:nth-child(4) {{ animation-delay: 0.4s; }}
.bullet-item:nth-child(5) {{ animation-delay: 0.5s; }}

/* Fibonacci stagger delays (89, 144, 233, 377, 610ms) */
.bullet-item-icon:nth-child(1) {{ animation-delay: 89ms; }}
.bullet-item-icon:nth-child(2) {{ animation-delay: 233ms; }}
.bullet-item-icon:nth-child(3) {{ animation-delay: 377ms; }}
.bullet-item-icon:nth-child(4) {{ animation-delay: 610ms; }}
.bullet-item-icon:nth-child(5) {{ animation-delay: 987ms; }}

/* === MICRODELIGHT ANIMATIONS === */

/* GLOBAL: Every element gets entrance animation */
.slide-content > * {{
    opacity: 0;
    animation: elementEntrance 610ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
}}

.slide-content > *:nth-child(1) {{ animation-delay: 0ms; }}
.slide-content > *:nth-child(2) {{ animation-delay: 144ms; }}
.slide-content > *:nth-child(3) {{ animation-delay: 233ms; }}
.slide-content > *:nth-child(4) {{ animation-delay: 377ms; }}
.slide-content > *:nth-child(5) {{ animation-delay: 610ms; }}

@keyframes elementEntrance {{
    from {{
        opacity: 0;
        transform: translateY(30px) scale(0.95);
        filter: blur(4px);
    }}
    to {{
        opacity: 1;
        transform: translateY(0) scale(1);
        filter: blur(0);
    }}
}}

/* SVG Icon Animations - ALWAYS animate icons */
.bullet-icon, .column-icon {{
    animation: iconPulse 2584ms ease-in-out infinite, iconGlow 4000ms ease-in-out infinite;
}}

@keyframes iconPulse {{
    0%, 100% {{ transform: scale(1); }}
    50% {{ transform: scale(1.08); }}
}}

@keyframes iconGlow {{
    0%, 100% {{ filter: drop-shadow(0 0 8px rgba(74, 158, 255, 0.4)); }}
    50% {{ filter: drop-shadow(0 0 16px rgba(74, 158, 255, 0.7)); }}
}}

/* Hero Image Effects */
.hero-image {{
    animation: heroFloat 6180ms ease-in-out infinite;
    transition: transform 377ms cubic-bezier(0.34, 1.56, 0.64, 1);
}}

@keyframes heroFloat {{
    0%, 100% {{ transform: translateY(0) rotate(0deg); }}
    50% {{ transform: translateY(-8px) rotate(0.5deg); }}
}}

.hero-image-container::after {{
    content: '';
    position: absolute;
    inset: -20px;
    background: radial-gradient(ellipse at center,
        rgba(74, 158, 255, 0.15) 0%,
        transparent 70%);
    animation: imageGlow 4000ms ease-in-out infinite;
    pointer-events: none;
    z-index: -1;
}}

@keyframes imageGlow {{
    0%, 100% {{ opacity: 0.5; transform: scale(0.9); }}
    50% {{ opacity: 1; transform: scale(1.1); }}
}}

/* Title Effects - Floating particles */
.title::before, .section-title::before {{
    content: '✨';
    position: absolute;
    font-size: 24px;
    opacity: 0;
    animation: sparkle 3000ms ease-in-out infinite;
    pointer-events: none;
}}

@keyframes sparkle {{
    0%, 100% {{
        opacity: 0;
        transform: translate(-50px, 20px) scale(0.5) rotate(0deg);
    }}
    50% {{
        opacity: 0.7;
        transform: translate(0, -10px) scale(1) rotate(180deg);
    }}
}}

/* Stats Value Animation */
.stat-value {{
    animation: statPop 987ms cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
    opacity: 0;
}}

@keyframes statPop {{
    0% {{
        opacity: 0;
        transform: scale(0.5);
        filter: blur(10px);
    }}
    60% {{
        transform: scale(1.1);
    }}
    100% {{
        opacity: 1;
        transform: scale(1);
        filter: blur(0);
    }}
}}

/* Quote Animation */
.quote-text {{
    animation: quoteReveal 987ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
    opacity: 0;
    background: linear-gradient(90deg,
        rgba(255,255,255,0.9) 0%,
        rgba(255,255,255,0.6) 100%);
    background-size: 200% 100%;
    -webkit-background-clip: text;
}}

@keyframes quoteReveal {{
    from {{
        opacity: 0;
        transform: translateY(40px);
        letter-spacing: 0.2em;
    }}
    to {{
        opacity: 1;
        transform: translateY(0);
        letter-spacing: normal;
    }}
}}

/* Column Card Effects */
.column {{
    animation: cardSlideUp 610ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
    opacity: 0;
    transition: all 233ms cubic-bezier(0.34, 1.56, 0.64, 1);
    position: relative;
    overflow: hidden;
}}

.column::before {{
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg,
        transparent,
        rgba(255,255,255,0.1),
        transparent);
    animation: cardShine 4000ms ease-in-out infinite;
}}

@keyframes cardShine {{
    0% {{ left: -100%; }}
    50%, 100% {{ left: 100%; }}
}}

@keyframes cardSlideUp {{
    from {{
        opacity: 0;
        transform: translateY(60px) rotateX(10deg);
    }}
    to {{
        opacity: 1;
        transform: translateY(0) rotateX(0);
    }}
}}

.columns-2 .column:nth-child(1) {{ animation-delay: 144ms; }}
.columns-2 .column:nth-child(2) {{ animation-delay: 377ms; }}
.columns-3 .column:nth-child(1) {{ animation-delay: 144ms; }}
.columns-3 .column:nth-child(2) {{ animation-delay: 377ms; }}
.columns-3 .column:nth-child(3) {{ animation-delay: 610ms; }}

/* === VISUAL CRAFT (from ~/projects/art/) === */

/* Breathing Background Layers */
.breath-layer {{
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
}}

.breath-1 {{
    background: radial-gradient(ellipse 100% 80% at 20% 30%,
        rgba(0, 240, 255, 0.06) 0%, transparent 60%);
    animation: breathe 2584ms ease-in-out infinite;
}}

.breath-2 {{
    background: radial-gradient(ellipse 80% 100% at 80% 70%,
        rgba(255, 215, 0, 0.04) 0%, transparent 50%);
    animation: breathe 3876ms ease-in-out infinite reverse;
}}

.breath-3 {{
    background: radial-gradient(ellipse 60% 60% at 50% 50%,
        rgba(168, 85, 247, 0.03) 0%, transparent 40%);
    animation: breathe 5168ms ease-in-out infinite;
    animation-delay: -987ms;
}}

@keyframes breathe {{
    0%, 100% {{ opacity: 0.5; transform: scale(1); }}
    50% {{ opacity: 1; transform: scale(1.08); }}
}}

/* Floating Particles Background */
.particle-layer {{
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
    z-index: 0;
}}

.particle {{
    position: absolute;
    width: 4px;
    height: 4px;
    background: rgba(74, 158, 255, 0.5);
    border-radius: 50%;
    animation: float 8000ms ease-in-out infinite;
}}

@keyframes float {{
    0%, 100% {{
        transform: translateY(0) translateX(0);
        opacity: 0;
    }}
    10% {{ opacity: 0.8; }}
    90% {{ opacity: 0.8; }}
    50% {{
        transform: translateY(-200px) translateX(50px);
    }}
}}

/* Accent Glow */
.accent-glow {{
    text-shadow: 0 0 30px rgba(0, 240, 255, 0.4);
}}

/* Card Elevation */
.card-elevate {{
    transition:
        transform 233ms cubic-bezier(0.34, 1.56, 0.64, 1),
        box-shadow 233ms cubic-bezier(0.16, 1, 0.3, 1);
}}

.card-elevate:hover {{
    transform: translateY(-6px);
    box-shadow:
        0 10px 20px rgba(0, 0, 0, 0.2),
        0 4px 8px rgba(0, 0, 0, 0.15);
}}

/* Continuous Shimmer for all major text */
.title, .section-title, .title-only, .hero-title {{
    position: relative;
}}

/* Line Drawing Animation for icons */
.bullet-icon path, .column-icon path {{
    stroke-dasharray: 100;
    stroke-dashoffset: 100;
    animation: drawLine 1000ms ease-out forwards;
}}

@keyframes drawLine {{
    to {{
        stroke-dashoffset: 0;
    }}
}}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }}
    .breath-1, .breath-2, .breath-3 {{
        animation: none;
        opacity: 0.6;
    }}
}}

/* === BROADCAST LOWER THIRD — KINETIC TYPOGRAPHY === */

/* Container spans full width at bottom */
#subtitle-container {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 9999;
    pointer-events: none;
    height: 180px;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    padding-bottom: 30px;
}}

/* Lower third bar - broadcast style */
#subtitle-container::before {{
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 160px;
    background: linear-gradient(to top,
        rgba(0, 0, 0, 0.95) 0%,
        rgba(0, 0, 0, 0.85) 40%,
        rgba(0, 0, 0, 0.5) 70%,
        transparent 100%
    );
    pointer-events: none;
}}

/* Accent line - animated gradient */
#subtitle-container::after {{
    content: '';
    position: absolute;
    bottom: 140px;
    left: 10%;
    right: 10%;
    height: 3px;
    background: linear-gradient(90deg,
        transparent 0%,
        rgba(0, 240, 255, 0.3) 10%,
        rgba(0, 240, 255, 0.8) 30%,
        rgba(255, 215, 0, 0.8) 50%,
        rgba(0, 240, 255, 0.8) 70%,
        rgba(0, 240, 255, 0.3) 90%,
        transparent 100%
    );
    background-size: 200% 100%;
    animation: lowerThirdShimmer 4s linear infinite;
    border-radius: 2px;
    filter: blur(1px);
}}

@keyframes lowerThirdShimmer {{
    0% {{ background-position: 200% 0; }}
    100% {{ background-position: -200% 0; }}
}}

/* Text container */
#subtitle-text {{
    position: relative;
    z-index: 2;
    text-align: center;
    max-width: 85%;
    padding: 0 60px;
}}

#subtitle-text:empty {{
    display: none;
}}

/* Individual words */
#subtitle-text .word {{
    display: inline-block;
    font-family: 'IBM Plex Sans', -apple-system, sans-serif;
    font-size: 52px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.7);
    letter-spacing: 0.02em;
    margin: 0 6px;
    vertical-align: baseline;
    transition: all 180ms cubic-bezier(0.4, 0, 0.2, 1);
    text-shadow:
        0 2px 4px rgba(0, 0, 0, 0.9),
        0 4px 20px rgba(0, 0, 0, 0.6);
}}

/* CURRENT word - THE STAR */
#subtitle-text .word.current {{
    color: #ffffff;
    font-weight: 700;
    font-size: 58px;
    transform: translateY(-4px);
    text-shadow:
        0 2px 4px rgba(0, 0, 0, 0.9),
        0 4px 20px rgba(0, 0, 0, 0.8),
        0 0 30px rgba(0, 240, 255, 0.5),
        0 0 60px rgba(0, 240, 255, 0.3);
    animation: wordReveal 250ms cubic-bezier(0.34, 1.56, 0.64, 1);
}}

/* Past words fade elegantly */
#subtitle-text .word.past {{
    color: rgba(255, 255, 255, 0.5);
    font-weight: 400;
}}

/* Upcoming words - dim preview */
#subtitle-text .word.upcoming {{
    color: rgba(255, 255, 255, 0.2);
    font-weight: 300;
    font-size: 48px;
}}

/* Word reveal animation */
@keyframes wordReveal {{
    0% {{
        opacity: 0.3;
        transform: translateY(8px) scale(0.92);
        filter: blur(2px);
    }}
    50% {{
        transform: translateY(-6px) scale(1.05);
    }}
    100% {{
        opacity: 1;
        transform: translateY(-4px) scale(1);
        filter: blur(0);
    }}
}}

/* Accent underline for current word */
#subtitle-text .word.current::after {{
    content: '';
    position: absolute;
    bottom: -6px;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg,
        transparent,
        rgba(0, 240, 255, 0.8) 20%,
        rgba(255, 215, 0, 0.8) 50%,
        rgba(0, 240, 255, 0.8) 80%,
        transparent
    );
    border-radius: 2px;
    animation: underlineGrow 250ms ease-out;
}}

@keyframes underlineGrow {{
    0% {{ transform: scaleX(0); opacity: 0; }}
    100% {{ transform: scaleX(1); opacity: 1; }}
}}

/* Side accents */
#subtitle-text::before,
#subtitle-text::after {{
    content: '';
    position: absolute;
    top: 50%;
    width: 80px;
    height: 2px;
    background: linear-gradient(90deg,
        transparent,
        rgba(0, 240, 255, 0.6)
    );
    transform: translateY(-50%);
}}

#subtitle-text::before {{
    left: -100px;
    background: linear-gradient(90deg,
        transparent,
        rgba(0, 240, 255, 0.6)
    );
}}

#subtitle-text::after {{
    right: -100px;
    background: linear-gradient(90deg,
        rgba(0, 240, 255, 0.6),
        transparent
    );
}}
</style>
"""


def generate_slide_deck_html(
    designs: list[SlideDesign],
    resolution: tuple[int, int] = (1920, 1080),
) -> str:
    """Generate full HTML slide deck.

    Args:
        designs: List of SlideDesign specifications
        resolution: Output resolution

    Returns:
        Complete HTML document
    """
    slides_html = "\n".join(generate_slide_html(design, i) for i, design in enumerate(designs))

    # Generate particle positions
    particle_html = ""
    for i in range(15):  # 15 floating particles
        x = (i * 137) % 100  # Golden ratio distribution
        y = (i * 89) % 100
        delay = i * 533  # Fibonacci-ish stagger
        particle_html += (
            f'<div class="particle" style="left:{x}%;top:{y}%;animation-delay:{delay}ms;"></div>\n'
        )

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Kagami Presentation</title>
    {get_slide_css(resolution)}
</head>
<body>
    <!-- Breathing Background Layers (Visual Craft) -->
    <div class="breath-layer breath-1"></div>
    <div class="breath-layer breath-2"></div>
    <div class="breath-layer breath-3"></div>

    <!-- Floating Particles (Microdelight) -->
    <div class="particle-layer">
        {particle_html}
    </div>

    <div id="slides-container">
        {slides_html}
    </div>

    <!-- KINETIC SUBTITLE CONTAINER -->
    <div id="subtitle-container">
        <div id="subtitle-text"></div>
    </div>

    <script>
        // Slide timing controller
        const slides = document.querySelectorAll('.slide');
        let currentSlide = 0;
        window.currentTimeMs = 0;
        window.slideTimings = []; // Set from Python
        window.wordTimings = []; // Set from Python - word-by-word timing

        // Direct slide navigation (for fast screenshot mode)
        window.showSlide = function(index) {{
            slides.forEach(s => s.classList.remove('active'));
            if (slides[index]) {{
                slides[index].classList.add('active');
                currentSlide = index;

                // Restart animations on slide change
                const content = slides[index].querySelector('.slide-content');
                if (content) {{
                    content.style.animation = 'none';
                    void content.offsetHeight; // Trigger reflow
                    content.style.animation = '';
                }}
            }}
        }};

        window.updateSlide = function() {{
            // Find which slide should be active based on time
            for (let i = 0; i < window.slideTimings.length; i++) {{
                const timing = window.slideTimings[i];
                if (window.currentTimeMs >= timing.start_ms &&
                    window.currentTimeMs < timing.end_ms) {{
                    if (currentSlide !== i) {{
                        window.showSlide(i);
                    }}
                    break;
                }}
            }}
        }};

        // === BROADCAST LOWER THIRD — KINETIC TYPOGRAPHY ===
        const subtitleContainer = document.getElementById('subtitle-text');
        let lastCurrentIdx = -1;

        window.updateSubtitles = function() {{
            // Find current word index
            let currentIdx = -1;
            for (let i = 0; i < window.wordTimings.length; i++) {{
                const word = window.wordTimings[i];
                if (window.currentTimeMs >= word.start_ms && window.currentTimeMs < word.end_ms) {{
                    currentIdx = i;
                    break;
                }}
            }}

            // No current word? Check if we're in a gap
            if (currentIdx === -1) {{
                // Find next word
                for (let i = 0; i < window.wordTimings.length; i++) {{
                    if (window.wordTimings[i].start_ms > window.currentTimeMs) {{
                        // We're in a gap before word i
                        // Keep showing previous words if recent
                        const prevIdx = i - 1;
                        if (prevIdx >= 0) {{
                            const timeSinceEnd = window.currentTimeMs - window.wordTimings[prevIdx].end_ms;
                            if (timeSinceEnd < 800) {{
                                currentIdx = prevIdx;  // Keep previous word highlighted briefly
                            }}
                        }}
                        break;
                    }}
                }}
            }}

            // Build phrase context (show surrounding words)
            const CONTEXT_BEFORE = 4;  // Words before current
            const CONTEXT_AFTER = 2;   // Words after current (preview)
            const startIdx = Math.max(0, currentIdx - CONTEXT_BEFORE);
            const endIdx = Math.min(window.wordTimings.length - 1, currentIdx + CONTEXT_AFTER);

            // Build HTML
            let html = '';
            for (let i = startIdx; i <= endIdx; i++) {{
                const word = window.wordTimings[i];
                if (!word) continue;

                let cls = 'word';
                if (i === currentIdx) {{
                    cls += ' current';
                }} else if (i < currentIdx) {{
                    cls += ' past';
                }} else {{
                    cls += ' upcoming';
                }}

                // Calculate opacity based on distance from current
                let opacity = 1;
                if (i < currentIdx) {{
                    // Past words fade based on distance
                    const distance = currentIdx - i;
                    opacity = Math.max(0.3, 1 - (distance * 0.2));
                }} else if (i > currentIdx) {{
                    // Upcoming words are very dim
                    opacity = 0.25;
                }}

                html += `<span class="${{cls}}" style="opacity:${{opacity.toFixed(2)}}">${{word.text}}</span> `;
            }}

            subtitleContainer.innerHTML = html.trim();
            lastCurrentIdx = currentIdx;
        }};

        // === REAL-TIME PLAYBACK MODE ===
        let playbackStartTime = null;
        let animationFrame = null;

        window.startPlayback = function() {{
            playbackStartTime = performance.now();
            function tick() {{
                window.currentTimeMs = performance.now() - playbackStartTime;
                window.updateSlide();
                window.updateSubtitles();
                animationFrame = requestAnimationFrame(tick);
            }}
            tick();
        }};

        window.stopPlayback = function() {{
            if (animationFrame) {{
                cancelAnimationFrame(animationFrame);
                animationFrame = null;
            }}
        }};

        window.seekTo = function(timeMs) {{
            window.currentTimeMs = timeMs;
            window.updateSlide();
            window.updateSubtitles();
        }};

        // Show first slide
        if (slides[0]) slides[0].classList.add('active');
    </script>
</body>
</html>
"""


__all__ = [
    "ICONS",
    "GradientPreset",
    "SlideDesign",
    "SlideLayout",
    "generate_slide_deck_html",
    "generate_slide_html",
    "get_slide_css",
]
