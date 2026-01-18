"""HTML slide renderer with Fibonacci animations and crafted micro-interactions.

Pure HTML/CSS generation for presentation slides.

Features:
- Ambient effects (radial gradients, particles, glow)
- Ken Burns animation on images with dramatic motion
- Fibonacci timing (89, 144, 233, 377, 610, 987ms)
- Layout-specific styles for all SlideLayoutType values
- Self-contained HTML with embedded assets
- Micro-animations on every element
- Typography polish with proper kerning

Usage:
    from kagami_studio.production.html_renderer import render_presentation_html

    html = render_presentation_html(
        presentation=presentation,
        image_paths={0: Path("hero_0.png"), 2: Path("hero_2.png")},
        slide_timings=[{"index": 0, "start_ms": 0, "end_ms": 5000}, ...],
        audio_path=Path("narration.mp3"),
    )

    Path("slides.html").write_text(html)

Design principles:
- Every pixel intentional
- Every motion purposeful
- Every moment delightful
- Fibonacci timing feels natural

Created: 2026-01-09
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from kagami_studio.production.layouts import SlideLayoutType
from kagami_studio.production.models import Presentation, SlideContent

logger = logging.getLogger(__name__)

# Fibonacci timing constants (milliseconds)
FIBONACCI_MS = [89, 144, 233, 377, 610, 987, 1597, 2584]


def hex_to_rgb(hex_color: str) -> str:
    """Convert hex color to RGB values for CSS rgba()."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"{r}, {g}, {b}"


def generate_css(colors: dict[str, str]) -> str:
    """Generate crafted CSS with Fibonacci timing and micro-animations.

    Every pixel intentional. Every motion purposeful. Every moment delightful.

    Args:
        colors: Dict with primary, secondary, background, text color values

    Returns:
        Complete CSS string with:
        - Fibonacci-timed animations
        - Ambient effects (particles, gradients, glow)
        - Ken Burns on images
        - Micro-interactions on all elements
        - Typography polish
    """
    primary = colors.get("primary", "#00f0ff")
    secondary = colors.get("secondary", "#ffd700")
    background = colors.get("background", "#0d1117")
    text = colors.get("text", "#ffffff")

    primary_rgb = hex_to_rgb(primary)
    secondary_rgb = hex_to_rgb(secondary)
    bg_rgb = hex_to_rgb(background)

    return f"""
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap');

/* === DESIGN TOKENS === */
:root {{
    --primary: {primary};
    --secondary: {secondary};
    --bg: {background};
    --text: {text};
    --primary-rgb: {primary_rgb};
    --secondary-rgb: {secondary_rgb};
    --bg-rgb: {bg_rgb};

    /* Fibonacci Timing */
    --t-instant: 89ms;
    --t-fast: 144ms;
    --t-normal: 233ms;
    --t-medium: 377ms;
    --t-slow: 610ms;
    --t-slower: 987ms;
    --t-slowest: 1597ms;
    --t-glacial: 2584ms;

    /* Easing */
    --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
    --ease-out-back: cubic-bezier(0.34, 1.56, 0.64, 1);
    --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
}}

/* === RESET === */
*, *::before, *::after {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    width: 1920px;
    height: 1080px;
    overflow: hidden;
    font-family: 'IBM Plex Sans', -apple-system, sans-serif;
    color: var(--text);
    background: var(--bg);
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}}

#slides-container {{
    position: relative;
    width: 100%;
    height: 100%;
}}

/* === SLIDE BASE === */
.slide {{
    position: absolute;
    inset: 0;
    display: none;
    opacity: 0;
    padding: 64px 80px;
    overflow: hidden;
}}

.slide.active {{
    display: flex;
    animation: slideIn var(--t-slow) var(--ease-out-expo) forwards;
}}

@keyframes slideIn {{
    from {{
        opacity: 0;
        transform: scale(0.98) translateY(20px);
    }}
    to {{
        opacity: 1;
        transform: scale(1) translateY(0);
    }}
}}

/* === AMBIENT BACKGROUND === */
.slide::before {{
    content: "";
    position: absolute;
    inset: 0;
    background:
        radial-gradient(ellipse 80% 60% at 15% 85%, rgba(var(--primary-rgb), 0.12) 0%, transparent 50%),
        radial-gradient(ellipse 70% 50% at 85% 15%, rgba(var(--secondary-rgb), 0.08) 0%, transparent 50%),
        radial-gradient(circle at 50% 50%, rgba(var(--primary-rgb), 0.03) 0%, transparent 70%);
    animation: ambientPulse var(--t-glacial) ease-in-out infinite;
    pointer-events: none;
    z-index: 0;
}}

.slide::after {{
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(
        135deg,
        transparent 40%,
        rgba(var(--primary-rgb), 0.02) 50%,
        transparent 60%
    );
    background-size: 200% 200%;
    animation: shimmerAmbient 8s ease-in-out infinite;
    pointer-events: none;
    z-index: 0;
}}

@keyframes ambientPulse {{
    0%, 100% {{ opacity: 0.7; transform: scale(1); }}
    50% {{ opacity: 1; transform: scale(1.02); }}
}}

@keyframes shimmerAmbient {{
    0% {{ background-position: 200% 200%; }}
    100% {{ background-position: -200% -200%; }}
}}

.slide > * {{
    position: relative;
    z-index: 1;
}}

/* === LAYOUT: HERO_FULL === */
.layout-hero_full {{
    position: relative;
    width: 100%;
    height: 100%;
}}

.hero-bg {{
    position: absolute;
    inset: 0;
    background-size: cover;
    background-position: center;
    animation: kenBurnsDramatic 20s ease-in-out infinite alternate;
}}

.hero-bg::after {{
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(
        to bottom,
        rgba(var(--bg-rgb), 0.1) 0%,
        rgba(var(--bg-rgb), 0.3) 40%,
        rgba(var(--bg-rgb), 0.85) 100%
    );
}}

.hero-overlay {{
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 80px;
}}

.hero-title {{
    font-size: 120px;
    font-weight: 800;
    line-height: 1.05;
    letter-spacing: -0.03em;
    text-shadow:
        0 4px 40px rgba(0, 0, 0, 0.8),
        0 0 80px rgba(var(--primary-rgb), 0.3);
    animation: heroTitleEnter var(--t-slower) var(--ease-out-expo) both;
    max-width: 80%;
}}

@keyframes kenBurnsDramatic {{
    0% {{
        transform: scale(1) translate(0, 0);
        filter: brightness(1);
    }}
    100% {{
        transform: scale(1.15) translate(-2%, 1%);
        filter: brightness(1.05);
    }}
}}

@keyframes heroTitleEnter {{
    from {{
        opacity: 0;
        transform: translateY(60px);
        filter: blur(8px);
    }}
    to {{
        opacity: 1;
        transform: translateY(0);
        filter: blur(0);
    }}
}}

/* === LAYOUT: HERO_SPLIT === */
.layout-hero_split {{
    display: flex;
    gap: 64px;
    align-items: center;
    height: 100%;
    padding: 48px;
}}

.split-image {{
    flex: 1.3;
    height: 85%;
    border-radius: 32px;
    overflow: hidden;
    box-shadow:
        0 40px 100px rgba(0, 0, 0, 0.5),
        0 0 0 1px rgba(255, 255, 255, 0.05);
    animation: splitImageEnter var(--t-slow) var(--ease-out-expo) both;
}}

.split-image img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    animation: imageFloat 8s ease-in-out infinite;
    filter: brightness(1.02) contrast(1.02);
}}

.split-text {{
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 24px;
    animation: splitTextEnter var(--t-slower) var(--ease-out-expo) var(--t-fast) both;
}}

.split-title {{
    font-size: 80px;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, var(--text) 0%, var(--primary) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}

.split-subtitle {{
    font-size: 36px;
    font-weight: 400;
    line-height: 1.5;
    color: rgba(255, 255, 255, 0.75);
    max-width: 90%;
}}

@keyframes splitImageEnter {{
    from {{ opacity: 0; transform: translateX(-40px) scale(0.95); }}
    to {{ opacity: 1; transform: translateX(0) scale(1); }}
}}

@keyframes splitTextEnter {{
    from {{ opacity: 0; transform: translateX(40px); }}
    to {{ opacity: 1; transform: translateX(0); }}
}}

@keyframes imageFloat {{
    0%, 100% {{ transform: translateY(0) scale(1); filter: brightness(1.02); }}
    50% {{ transform: translateY(-12px) scale(1.02); filter: brightness(1.05); }}
}}

/* === LAYOUT: STAT_FOCUS === */
.layout-stat_focus {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    height: 100%;
    gap: 32px;
}}

.stat-value {{
    font-size: 320px;
    font-weight: 800;
    line-height: 0.9;
    letter-spacing: -0.05em;
    background: linear-gradient(
        135deg,
        var(--primary) 0%,
        var(--secondary) 50%,
        var(--primary) 100%
    );
    background-size: 200% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation:
        statEnter var(--t-slower) var(--ease-out-back) both,
        statGradient 4s ease-in-out infinite,
        statPulse 2s ease-in-out infinite;
    filter: drop-shadow(0 0 80px rgba(var(--primary-rgb), 0.4));
}}

.stat-label {{
    font-size: 56px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.85);
    animation: statLabelEnter var(--t-slow) var(--ease-out-expo) var(--t-normal) both;
}}

@keyframes statEnter {{
    from {{ opacity: 0; transform: scale(0.5); filter: blur(20px); }}
    to {{ opacity: 1; transform: scale(1); filter: blur(0); }}
}}

@keyframes statGradient {{
    0%, 100% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
}}

@keyframes statPulse {{
    0%, 100% {{ transform: scale(1); }}
    50% {{ transform: scale(1.02); }}
}}

@keyframes statLabelEnter {{
    from {{ opacity: 0; transform: translateY(20px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

/* === LAYOUT: QUOTE === */
.layout-quote {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 80px 120px;
    height: 100%;
}}

.quote-text {{
    font-size: 72px;
    font-weight: 300;
    font-style: italic;
    line-height: 1.35;
    position: relative;
    padding-left: 64px;
    animation: quoteEnter var(--t-slower) var(--ease-out-expo) both;
}}

.quote-text::before {{
    content: '"';
    position: absolute;
    top: -60px;
    left: -40px;
    font-size: 280px;
    font-family: Georgia, 'Times New Roman', serif;
    color: rgba(var(--primary-rgb), 0.15);
    line-height: 1;
    animation: quoteMark var(--t-glacial) ease-in-out infinite;
}}

.quote-author {{
    font-size: 36px;
    font-weight: 400;
    color: rgba(255, 255, 255, 0.6);
    margin-top: 48px;
    padding-left: 64px;
    animation: quoteAuthorEnter var(--t-slow) var(--ease-out-expo) var(--t-normal) both;
}}

@keyframes quoteEnter {{
    from {{ opacity: 0; transform: translateX(-30px); }}
    to {{ opacity: 1; transform: translateX(0); }}
}}

@keyframes quoteMark {{
    0%, 100% {{ opacity: 0.15; transform: scale(1); }}
    50% {{ opacity: 0.25; transform: scale(1.05); }}
}}

@keyframes quoteAuthorEnter {{
    from {{ opacity: 0; transform: translateX(-20px); }}
    to {{ opacity: 1; transform: translateX(0); }}
}}

/* === LAYOUT: MINIMAL_TEXT === */
.layout-minimal_text {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    height: 100%;
    padding: 80px;
}}

.minimal-title {{
    font-size: 108px;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
    background: linear-gradient(
        135deg,
        var(--text) 0%,
        var(--primary) 40%,
        var(--secondary) 70%,
        var(--text) 100%
    );
    background-size: 300% 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation:
        minimalEnter var(--t-slower) var(--ease-out-expo) both,
        minimalShimmer 6s ease-in-out infinite;
    max-width: 85%;
}}

@keyframes minimalEnter {{
    from {{ opacity: 0; transform: translateY(40px) scale(0.95); filter: blur(10px); }}
    to {{ opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }}
}}

@keyframes minimalShimmer {{
    0% {{ background-position: 100% 50%; }}
    100% {{ background-position: -100% 50%; }}
}}

/* === LAYOUT: ICON_GRID === */
.layout-icon_grid {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    height: 100%;
    padding: 64px;
    gap: 64px;
}}

.grid-title {{
    font-size: 72px;
    font-weight: 700;
    text-align: center;
    animation: gridTitleEnter var(--t-slow) var(--ease-out-expo) both;
}}

.icon-grid {{
    display: flex;
    justify-content: center;
    gap: 48px;
    flex-wrap: wrap;
}}

.icon-item {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24px;
    padding: 40px;
    background: linear-gradient(
        135deg,
        rgba(255, 255, 255, 0.08) 0%,
        rgba(255, 255, 255, 0.03) 100%
    );
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    min-width: 220px;
    backdrop-filter: blur(10px);
    animation: iconItemEnter var(--t-medium) var(--ease-out-back) both;
}}

.icon-item:nth-child(1) {{ animation-delay: 89ms; }}
.icon-item:nth-child(2) {{ animation-delay: 144ms; }}
.icon-item:nth-child(3) {{ animation-delay: 233ms; }}
.icon-item:nth-child(4) {{ animation-delay: 377ms; }}

.icon-item .icon {{
    font-size: 72px;
    animation: iconBounce var(--t-glacial) ease-in-out infinite;
}}

.icon-item:nth-child(1) .icon {{ animation-delay: 0s; }}
.icon-item:nth-child(2) .icon {{ animation-delay: 0.5s; }}
.icon-item:nth-child(3) .icon {{ animation-delay: 1s; }}
.icon-item:nth-child(4) .icon {{ animation-delay: 1.5s; }}

.icon-item .label {{
    font-size: 28px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.9);
}}

@keyframes gridTitleEnter {{
    from {{ opacity: 0; transform: translateY(-20px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

@keyframes iconItemEnter {{
    from {{ opacity: 0; transform: translateY(30px) scale(0.9); }}
    to {{ opacity: 1; transform: translateY(0) scale(1); }}
}}

@keyframes iconBounce {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-8px); }}
}}

/* === LAYOUT: RECAP === */
.layout-recap {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    height: 100%;
    padding: 64px 120px;
}}

.recap-title {{
    font-size: 72px;
    font-weight: 700;
    margin-bottom: 64px;
    animation: recapTitleEnter var(--t-slow) var(--ease-out-expo) both;
}}

.recap-list {{
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 32px;
}}

.recap-item {{
    font-size: 44px;
    font-weight: 400;
    padding-left: 64px;
    position: relative;
    animation: recapItemEnter var(--t-medium) var(--ease-out-expo) both;
}}

.recap-item::before {{
    content: attr(data-num);
    position: absolute;
    left: 0;
    font-weight: 700;
    color: var(--primary);
    font-variant-numeric: tabular-nums;
}}

.recap-item::after {{
    content: "";
    position: absolute;
    left: 0;
    bottom: -8px;
    width: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--primary), transparent);
    animation: recapLine var(--t-slow) var(--ease-out-expo) forwards;
}}

.recap-item:nth-child(1) {{ animation-delay: 89ms; }}
.recap-item:nth-child(2) {{ animation-delay: 144ms; }}
.recap-item:nth-child(3) {{ animation-delay: 233ms; }}
.recap-item:nth-child(4) {{ animation-delay: 377ms; }}
.recap-item:nth-child(5) {{ animation-delay: 610ms; }}

.recap-item:nth-child(1)::after {{ animation-delay: 89ms; }}
.recap-item:nth-child(2)::after {{ animation-delay: 144ms; }}
.recap-item:nth-child(3)::after {{ animation-delay: 233ms; }}
.recap-item:nth-child(4)::after {{ animation-delay: 377ms; }}
.recap-item:nth-child(5)::after {{ animation-delay: 610ms; }}

@keyframes recapTitleEnter {{
    from {{ opacity: 0; transform: translateX(-30px); }}
    to {{ opacity: 1; transform: translateX(0); }}
}}

@keyframes recapItemEnter {{
    from {{ opacity: 0; transform: translateX(-40px); }}
    to {{ opacity: 1; transform: translateX(0); }}
}}

@keyframes recapLine {{
    to {{ width: 60%; }}
}}

/* === SUBTITLES === */
#subtitles {{
    position: fixed;
    bottom: 60px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 40px;
    font-weight: 500;
    color: white;
    text-shadow:
        0 2px 4px rgba(0, 0, 0, 0.9),
        0 4px 20px rgba(0, 0, 0, 0.5);
    text-align: center;
    max-width: 80%;
    z-index: 1000;
}}
"""


def render_slide_html(slide: SlideContent, index: int, img_b64: str | None) -> str:
    """Render a single slide to HTML based on its layout.

    Args:
        slide: Slide content data
        index: Slide index (0-based)
        img_b64: Base64-encoded image data (if applicable)

    Returns:
        HTML string for the slide
    """
    active = "active" if index == 0 else ""
    layout = slide.layout

    if layout == SlideLayoutType.HERO_FULL.value or layout == "hero_full":
        bg_style = f"background-image: url(data:image/png;base64,{img_b64});" if img_b64 else ""
        return f'''
<div class="slide {active}" id="slide-{index}">
    <div class="layout-hero_full">
        <div class="hero-bg" style="{bg_style}"></div>
        <div class="hero-overlay">
            <h1 class="hero-title">{slide.title}</h1>
        </div>
    </div>
</div>'''

    elif layout in (SlideLayoutType.HERO_SPLIT.value, "hero_split", "hero_left", "hero_right"):
        img_html = f'<img src="data:image/png;base64,{img_b64}" alt="">' if img_b64 else ""
        subtitle = slide.display_text or ""
        return f"""
<div class="slide {active}" id="slide-{index}">
    <div class="layout-hero_split">
        <div class="split-image">{img_html}</div>
        <div class="split-text">
            <h2 class="split-title">{slide.title}</h2>
            <p class="split-subtitle">{subtitle}</p>
        </div>
    </div>
</div>"""

    elif layout in (SlideLayoutType.STAT_FOCUS.value, "stat_focus"):
        return f"""
<div class="slide {active}" id="slide-{index}">
    <div class="layout-stat_focus">
        <div class="stat-value">{slide.stat_value or "?"}</div>
        <div class="stat-label">{slide.stat_label or slide.title}</div>
    </div>
</div>"""

    elif layout in (SlideLayoutType.QUOTE.value, "quote"):
        return f"""
<div class="slide {active}" id="slide-{index}">
    <div class="layout-quote">
        <blockquote class="quote-text">{slide.quote_text or slide.title}</blockquote>
        <cite class="quote-author">— {slide.quote_author or ""}</cite>
    </div>
</div>"""

    elif layout in (SlideLayoutType.MINIMAL_TEXT.value, "minimal_text", "title_only"):
        text = slide.display_text or slide.title
        return f"""
<div class="slide {active}" id="slide-{index}">
    <div class="layout-minimal_text">
        <h1 class="minimal-title">{text}</h1>
    </div>
</div>"""

    elif layout in (SlideLayoutType.ICON_GRID.value, "icon_grid"):
        items_html = ""
        if slide.icon_items:
            for item in slide.icon_items:
                items_html += f"""
        <div class="icon-item">
            <span class="icon">{item.get("icon", "•")}</span>
            <span class="label">{item.get("label", "")}</span>
        </div>"""
        return f"""
<div class="slide {active}" id="slide-{index}">
    <div class="layout-icon_grid">
        <h2 class="grid-title">{slide.title}</h2>
        <div class="icon-grid">{items_html}</div>
    </div>
</div>"""

    elif layout in (SlideLayoutType.RECAP.value, "recap"):
        items_html = ""
        if slide.recap_points:
            for i, point in enumerate(slide.recap_points, 1):
                items_html += f'<li class="recap-item" data-num="{i}.">{point}</li>'
        return f"""
<div class="slide {active}" id="slide-{index}">
    <div class="layout-recap">
        <h2 class="recap-title">{slide.title}</h2>
        <ul class="recap-list">{items_html}</ul>
    </div>
</div>"""

    # Default fallback: minimal text
    return f"""
<div class="slide {active}" id="slide-{index}">
    <div class="layout-minimal_text">
        <h1 class="minimal-title">{slide.title}</h1>
    </div>
</div>"""


def render_presentation_html(
    presentation: Presentation,
    image_paths: dict[int, Path],
    slide_timings: list[dict[str, Any]],
    audio_path: Path,
    word_timings: list[dict[str, Any]] | None = None,
) -> str:
    """Generate complete self-contained HTML with embedded assets.

    Args:
        presentation: The presentation data
        image_paths: Dict mapping slide index to image path
        slide_timings: List of timing dicts with start_ms/end_ms
        audio_path: Path to audio file
        word_timings: Optional word-level timings for subtitles

    Returns:
        Complete HTML string with embedded images and audio
    """
    colors = presentation.get_colors()
    css = generate_css(colors)

    # Generate slides HTML
    slides_html = ""
    for i, slide in enumerate(presentation.slides):
        img_path = image_paths.get(i)
        img_b64 = ""
        if img_path and img_path.exists():
            img_b64 = base64.b64encode(img_path.read_bytes()).decode()

        slides_html += render_slide_html(slide, i, img_b64 if img_b64 else None)

    # Embed audio
    audio_b64 = ""
    if audio_path and audio_path.exists():
        audio_b64 = base64.b64encode(audio_path.read_bytes()).decode()

    # Prepare word timings for JS
    word_timings_json = json.dumps(word_timings or [])

    # Build complete HTML with crafted JS
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{presentation.title}</title>
    <style>{css}</style>
</head>
<body>
    <div id="slides-container">
        {slides_html}
    </div>

    <audio id="sync-audio" preload="auto" style="display:none;">
        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
    </audio>

    <div id="subtitles"></div>

    <script>
        const slides = document.querySelectorAll('.slide');
        const audio = document.getElementById('sync-audio');
        const subtitles = document.getElementById('subtitles');
        let currentSlide = 0;
        let lastSubtitleIdx = -1;

        const slideTimings = {json.dumps(slide_timings)};
        const wordTimings = {word_timings_json};

        function showSlide(index) {{
            slides.forEach(s => s.classList.remove('active'));
            if (slides[index]) {{
                slides[index].classList.add('active');
                currentSlide = index;
            }}
        }}

        function updateSubtitles(timeMs) {{
            if (!wordTimings.length) return;

            // Build subtitle from words in a window around current time
            const windowMs = 3000; // Show 3s of words
            const wordsInWindow = [];

            for (let i = 0; i < wordTimings.length; i++) {{
                const w = wordTimings[i];
                // Show words that started in the last 3s and haven't ended yet
                if (w.start_ms <= timeMs && w.end_ms >= timeMs - windowMs) {{
                    wordsInWindow.push({{
                        text: w.text,
                        active: timeMs >= w.start_ms && timeMs <= w.end_ms + 200
                    }});
                }}
            }}

            // Keep only last ~8 words for readability
            const recentWords = wordsInWindow.slice(-10);

            if (recentWords.length > 0) {{
                subtitles.innerHTML = recentWords
                    .map(w => w.active
                        ? `<span style="color: #00f0ff; text-shadow: 0 0 20px rgba(0,240,255,0.5);">${{w.text}}</span>`
                        : `<span style="opacity: 0.7;">${{w.text}}</span>`)
                    .join(' ');
                subtitles.style.opacity = '1';
            }} else {{
                subtitles.style.opacity = '0';
            }}
        }}

        function updateSlide() {{
            const timeMs = audio.currentTime * 1000;

            // Update slide
            for (let i = 0; i < slideTimings.length; i++) {{
                const t = slideTimings[i];
                if (timeMs >= t.start_ms && timeMs < t.end_ms) {{
                    if (currentSlide !== i) showSlide(i);
                    break;
                }}
            }}

            // Update subtitles
            updateSubtitles(timeMs);
        }}

        audio.addEventListener('timeupdate', updateSlide);

        document.addEventListener('keydown', (e) => {{
            if (e.code === 'Space') {{
                e.preventDefault();
                audio.paused ? audio.play() : audio.pause();
            }}
            if (e.code === 'ArrowRight') showSlide(Math.min(currentSlide + 1, slides.length - 1));
            if (e.code === 'ArrowLeft') showSlide(Math.max(currentSlide - 1, 0));
        }});

        showSlide(0);
    </script>
</body>
</html>"""


__all__ = [
    "FIBONACCI_MS",
    "generate_css",
    "hex_to_rgb",
    "render_presentation_html",
    "render_slide_html",
]
