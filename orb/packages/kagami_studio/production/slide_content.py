"""Slide Content Generator — Transform scripts into visual presentations.

TWO MODES:
1. LLM Mode (default): Each slide individually designed by LLM
2. Heuristic Mode: Fast rule-based layout selection (fallback)

LLM Hierarchical Design:
1. PLAN: Overall presentation theme (1 LLM call)
2. DESIGN: Each slide individually (N LLM calls)
3. VISUALS: Hero image prompts (M LLM calls)

Design Philosophy (Gamma/NotebookLM inspired):
- Visual storytelling > bullet points
- One idea per slide, maximum impact
- Hero images that reinforce the message
- Consistent theming throughout
- Dark mode with accent colors

Usage:
    from kagami_studio.production.slide_content import (
        enhance_script_to_designs,
        generate_hero_image,
    )

    # LLM-powered design (recommended)
    designs = await enhance_script_to_designs(
        slides=[
            {"title": "Welcome Home", "spoken": "You walk through..."},
            {"title": "The Problem", "points": ["Fragmented", "No learning"]},
        ],
        theme="dark_blue",
        generate_images=True,
        use_llm=True,  # Default: uses LLM for each slide
    )

    # Fast heuristic mode (no LLM calls)
    designs = await enhance_script_to_designs(
        slides=script,
        use_llm=False,
    )
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from kagami_studio.production.slide_design import (
    GradientPreset,
    SlideDesign,
    SlideLayout,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/tmp/kagami_slides/images")


# Content-to-layout mapping based on slide characteristics
LAYOUT_RULES = {
    # Opening/closing slides
    "intro": SlideLayout.TITLE_SUBTITLE,
    "welcome": SlideLayout.HERO_FULL,
    "conclusion": SlideLayout.TITLE_ONLY,
    "closing": SlideLayout.TITLE_ONLY,
    # Content with statistics/numbers
    "stat": SlideLayout.STATS,
    "number": SlideLayout.STATS,
    "percent": SlideLayout.STATS,
    # Questions/quotes
    "quote": SlideLayout.QUOTE,
    "question": SlideLayout.TITLE_SUBTITLE,
    # Problem/solution
    "problem": SlideLayout.BULLETS_ICON,
    "solution": SlideLayout.HERO_RIGHT,
    "challenge": SlideLayout.BULLETS_ICON,
    # Features/benefits
    "feature": SlideLayout.THREE_COLUMN,
    "benefit": SlideLayout.BULLETS_ICON,
    # Comparisons
    "vs": SlideLayout.COMPARISON,
    "compare": SlideLayout.TWO_COLUMN,
}

# Keywords to icon mapping for automatic iconography
KEYWORD_ICONS = {
    # Technology
    "ai": "brain",
    "artificial intelligence": "brain",
    "machine learning": "brain",
    "smart": "lightbulb",
    "intelligent": "lightbulb",
    "automation": "zap",
    "automated": "zap",
    # Home/lifestyle
    "home": "home",
    "house": "home",
    "light": "lightbulb",
    "lighting": "lightbulb",
    "music": "star",
    "temperature": "zap",
    "climate": "globe",
    # Security/privacy
    "privacy": "lock",
    "secure": "shield",
    "security": "shield",
    "protect": "shield",
    "safe": "shield",
    # People/community
    "team": "users",
    "people": "users",
    "community": "users",
    "family": "heart",
    "love": "heart",
    # Success/achievement
    "success": "star",
    "win": "star",
    "achieve": "check",
    "complete": "check",
    "done": "check",
    # Learning/growth
    "learn": "brain",
    "adapt": "zap",
    "grow": "arrow-right",
    "improve": "arrow-right",
    # General actions
    "start": "arrow-right",
    "begin": "arrow-right",
    "next": "arrow-right",
    "connect": "globe",
    "integrate": "globe",
}

# Mood to gradient mapping
MOOD_GRADIENTS = {
    "warm": GradientPreset.WARM,
    "friendly": GradientPreset.WARM,
    "excited": GradientPreset.SUNSET,
    "serious": GradientPreset.MIDNIGHT,
    "dramatic": GradientPreset.MIDNIGHT,
    "professional": GradientPreset.DARK_BLUE,
    "neutral": GradientPreset.DARK_BLUE,
    "calm": GradientPreset.OCEAN,
    "natural": GradientPreset.FOREST,
    "tech": GradientPreset.MIDNIGHT,
}


async def enhance_script_to_designs(
    slides: list[dict[str, Any]],
    theme: GradientPreset | str = GradientPreset.DARK_BLUE,
    accent_color: str = "4a9eff",
    generate_images: bool = False,
    image_style: str = "modern minimalist",
    use_llm: bool = True,
    speaker: str = "tim",
    reuse_images: bool = True,
) -> list[SlideDesign]:
    """Transform basic script slides into rich visual designs.

    Args:
        slides: List of slide dictionaries with:
            - title: Slide title
            - spoken: Narration text
            - points: Bullet points
            - mood: Emotional tone
            - shot: Shot type (used for layout hints)
        theme: Gradient theme preset or name
        accent_color: Hex color for accents
        generate_images: Whether to generate AI images for heroes
        image_style: Style prompt for image generation
        use_llm: If True, use LLM for individual slide design (recommended)
        speaker: Speaker identity for LLM context
        reuse_images: If True, reuse existing images instead of regenerating

    Returns:
        List of SlideDesign objects ready for rendering
    """
    # === LLM MODE (DEFAULT) ===
    if use_llm:
        try:
            from kagami_studio.production.llm_slide_generator import generate_presentation

            logger.info("🎨 Using LLM for hierarchical slide design...")
            theme_str = theme.value if isinstance(theme, GradientPreset) else str(theme)

            designs = await generate_presentation(
                script=slides,
                theme=f"{theme_str}, {image_style}",
                speaker=speaker,
                generate_images=generate_images,
            )

            # Generate actual images if requested
            if generate_images:
                for i, design in enumerate(designs):
                    if design.hero_prompt and design.layout in [
                        SlideLayout.HERO_FULL,
                        SlideLayout.HERO_LEFT,
                        SlideLayout.HERO_RIGHT,
                    ]:
                        image_path = OUTPUT_DIR / f"hero_{i:03d}.png"

                        # Reuse existing image if valid
                        if (
                            reuse_images
                            and image_path.exists()
                            and image_path.stat().st_size > 100000
                        ):
                            logger.info(f"  ♻️  Reusing existing image: {image_path.name}")
                            design.hero_image = str(image_path)
                        else:
                            # Generate new image
                            result = await generate_hero_image(
                                prompt=design.hero_prompt,
                                output_path=image_path,
                            )
                            if result:
                                design.hero_image = str(result)

            logger.info(f"✓ LLM designed {len(designs)} slides")
            return designs

        except Exception as e:
            logger.warning(f"LLM slide generation failed, falling back to heuristics: {e}")
            # Fall through to heuristic mode

    # === HEURISTIC MODE (FALLBACK) ===
    logger.info("📐 Using heuristic slide design (fast mode)...")

    # Resolve theme
    if isinstance(theme, str):
        try:
            theme = GradientPreset(theme)
        except ValueError:
            theme = GradientPreset.DARK_BLUE

    designs = []

    for i, slide in enumerate(slides):
        title = slide.get("title", "")
        spoken = slide.get("spoken", "")
        points = slide.get("points", [])
        mood = slide.get("mood", "neutral")

        # Determine best layout
        layout = _select_layout(slide, i, len(slides))

        # Downgrade hero layouts when not generating images
        # (hero layouts without images look broken)
        if not generate_images and layout in [
            SlideLayout.HERO_FULL,
            SlideLayout.HERO_LEFT,
            SlideLayout.HERO_RIGHT,
        ]:
            if points:
                layout = SlideLayout.BULLETS_ICON
            else:
                layout = SlideLayout.TITLE_SUBTITLE

        # Determine gradient based on mood
        gradient = MOOD_GRADIENTS.get(mood, theme)

        # Generate icons for bullet points
        icons = _generate_icons_for_points(points)

        # Create design
        design = SlideDesign(
            layout=layout,
            title=title,
            subtitle=spoken[:100] + "..."
            if len(spoken) > 100
            and layout
            in [
                SlideLayout.TITLE_SUBTITLE,
                SlideLayout.HERO_FULL,
                SlideLayout.HERO_LEFT,
                SlideLayout.HERO_RIGHT,
            ]
            else "",
            points=points,
            icons=icons,
            gradient=gradient,
            accent_color=accent_color,
        )

        # Generate hero image if requested and layout needs it
        if generate_images and layout in [
            SlideLayout.HERO_FULL,
            SlideLayout.HERO_LEFT,
            SlideLayout.HERO_RIGHT,
        ]:
            image_prompt = _generate_image_prompt(title, spoken, mood, image_style)
            design.hero_prompt = image_prompt

            # Actually generate the image
            image_path = await generate_hero_image(
                prompt=image_prompt,
                output_path=OUTPUT_DIR / f"hero_{i:03d}.png",
            )
            if image_path:
                design.hero_image = str(image_path)

        # Handle special layouts
        if layout == SlideLayout.STATS:
            stat = _extract_statistic(title + " " + spoken)
            if stat:
                design.stat_value = stat["value"]
                design.stat_label = stat["label"]

        if layout == SlideLayout.QUOTE:
            design.quote_text = spoken
            design.quote_author = title or "Unknown"

        if layout in [SlideLayout.TWO_COLUMN, SlideLayout.THREE_COLUMN]:
            design.columns = _create_columns_from_points(points, layout)

        designs.append(design)

    return designs


def _select_layout(slide: dict, index: int, total: int) -> SlideLayout:
    """Select the best layout for a slide based on its content.

    Uses heuristics based on:
    - Position (first/last slides)
    - Title keywords
    - Content type (points, numbers, quotes)
    - Shot type hint
    """
    title = slide.get("title", "").lower()
    spoken = slide.get("spoken", "").lower()
    points = slide.get("points", [])
    shot = slide.get("shot", "")

    # First slide - dramatic intro
    if index == 0:
        if points:
            return SlideLayout.HERO_RIGHT
        return SlideLayout.HERO_FULL

    # Last slide - simple closing
    if index == total - 1:
        return SlideLayout.TITLE_ONLY

    # Check for keywords that suggest specific layouts
    combined = title + " " + spoken

    # Statistics
    if re.search(r"\d+%|\d+x|\d+\+", combined):
        return SlideLayout.STATS

    # Quotes
    if '"' in combined or combined.startswith("'"):
        return SlideLayout.QUOTE

    # Feature lists with 3 items
    if len(points) == 3:
        return SlideLayout.THREE_COLUMN

    # Feature lists with 2 items
    if len(points) == 2:
        return SlideLayout.TWO_COLUMN

    # Any points -> bullets with icons
    if points:
        return SlideLayout.BULLETS_ICON

    # Check layout rules by keyword
    for keyword, layout in LAYOUT_RULES.items():
        if keyword in title or keyword in spoken:
            return layout

    # Shot type hints
    if shot in ["establishing", "front_wide", "hero_full"]:
        return SlideLayout.HERO_FULL
    if shot in ["dialogue", "front_medium"]:
        return SlideLayout.TITLE_SUBTITLE
    if shot in ["reverse", "audience"]:
        return SlideLayout.TITLE_ONLY

    # Default - title with subtitle
    return SlideLayout.TITLE_SUBTITLE


def _generate_icons_for_points(points: list[str]) -> list[str]:
    """Generate appropriate icons for bullet points."""
    icons = []

    for point in points:
        point_lower = point.lower()
        icon = "check"  # Default

        # Check for keyword matches
        for keyword, icon_name in KEYWORD_ICONS.items():
            if keyword in point_lower:
                icon = icon_name
                break

        icons.append(icon)

    return icons


def _generate_image_prompt(
    title: str,
    spoken: str,
    mood: str,
    style: str,
) -> str:
    """Generate a prompt for hero image generation.

    Creates visual metaphors for abstract concepts.
    """
    # Base style
    base = f"{style} digital illustration, dark background, subtle gradient lighting"

    # Extract key concepts
    combined = title + " " + spoken
    combined_lower = combined.lower()

    # Map concepts to visual metaphors
    visual_concepts = []

    if any(w in combined_lower for w in ["home", "house", "living"]):
        visual_concepts.append("modern smart home interior with warm ambient lighting")

    if any(w in combined_lower for w in ["ai", "intelligence", "smart", "brain"]):
        visual_concepts.append("abstract neural network, glowing connections")

    if any(w in combined_lower for w in ["light", "lighting"]):
        visual_concepts.append("elegant pendant lights, warm glow")

    if any(w in combined_lower for w in ["music", "audio", "sound"]):
        visual_concepts.append("sound waves, audio visualization")

    if any(w in combined_lower for w in ["privacy", "secure", "protect"]):
        visual_concepts.append("shield icon, lock symbol, protective barrier")

    if any(w in combined_lower for w in ["problem", "challenge", "broken"]):
        visual_concepts.append("fragmented pieces, disconnected elements")

    if any(w in combined_lower for w in ["solution", "unified", "connect"]):
        visual_concepts.append("connected nodes, unified system, harmony")

    # Mood modifiers
    mood_styles = {
        "warm": "warm orange and amber tones, cozy atmosphere",
        "serious": "cool blue tones, sharp contrast",
        "excited": "vibrant colors, dynamic composition",
        "calm": "soft gradients, serene atmosphere",
        "professional": "clean lines, corporate aesthetic",
    }
    mood_style = mood_styles.get(mood, "balanced composition")

    # Combine into prompt
    if visual_concepts:
        concept_str = ", ".join(visual_concepts[:2])  # Max 2 concepts
        return f"{base}, {concept_str}, {mood_style}"
    else:
        # Generic abstract based on title
        return f"{base}, abstract representation of '{title}', {mood_style}"


async def generate_hero_image(
    prompt: str,
    output_path: Path | str,
    width: int = 1920,
    height: int = 1080,
) -> Path | None:
    """Generate hero image using AI image generation.

    Uses Flux (via Replicate) or falls back to placeholder.

    Args:
        prompt: Image generation prompt
        output_path: Where to save the image
        width: Image width
        height: Image height

    Returns:
        Path to generated image, or None if failed
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from kagami_studio.generation.image import generate_image

        result = await generate_image(
            prompt=prompt,
            width=width,
            height=height,
            output_path=output_path,
        )

        if result and result.exists():
            logger.info(f"Generated hero image: {output_path}")
            return result

    except ImportError:
        logger.debug("Image generation module not available")
    except Exception as e:
        logger.warning(f"Image generation failed: {e}")

    # Fallback: Create gradient placeholder
    return await _create_placeholder_image(output_path, width, height, prompt)


async def _create_placeholder_image(
    output_path: Path,
    width: int,
    height: int,
    prompt: str,
) -> Path | None:
    """Create a gradient placeholder image with FFmpeg."""
    import subprocess

    # Extract colors from prompt for gradient
    colors = ["0d1117", "1a1a2e", "2d1b3d"]

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"gradients=s={width}x{height}:c0=0x{colors[0]}:c1=0x{colors[1]}:x0=0:y0=0:x1={width}:y1={height}:duration=1",
            "-frames:v",
            "1",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and output_path.exists():
            return output_path

    except Exception as e:
        logger.debug(f"Placeholder generation failed: {e}")

    return None


def _extract_statistic(text: str) -> dict | None:
    """Extract statistics from text for STATS layout."""
    # Look for patterns like "100%", "10x", "50+"
    patterns = [
        (r"(\d+%)", ""),  # 100%
        (r"(\d+x)", "times"),  # 10x
        (r"(\d+\+)", "+"),  # 50+
        (r"(\d+)\s*(million|billion|thousand)", ""),  # 10 million
    ]

    for pattern, _suffix in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1)
            # Try to get context around the number
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end]

            return {
                "value": value,
                "label": context.strip(),
            }

    return None


def _create_columns_from_points(
    points: list[str],
    layout: SlideLayout,
) -> list[dict]:
    """Convert bullet points to column data."""
    count = 3 if layout == SlideLayout.THREE_COLUMN else 2
    columns = []

    for _i, point in enumerate(points[:count]):
        # Try to split point into title and content
        parts = point.split(":", 1) if ":" in point else [point, ""]

        # Generate icon based on content
        icon = "check"
        point_lower = point.lower()
        for keyword, icon_name in KEYWORD_ICONS.items():
            if keyword in point_lower:
                icon = icon_name
                break

        columns.append(
            {
                "title": parts[0].strip(),
                "content": parts[1].strip() if len(parts) > 1 else "",
                "icon": icon,
            }
        )

    return columns


__all__ = [
    "enhance_script_to_designs",
    "generate_hero_image",
]
