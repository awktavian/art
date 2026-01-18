"""鏡 Topic Generator — Create scripts from a single topic.

THE Single System: Topic → Script → Video

This module bridges the gap between "I want a video about X" and
the structured script format that produce_video() expects.

Enhanced with:
- TED-style layout selection (6-word max titles)
- Smart layout assignment per slide type
- Integration with unified models and layouts

Usage:
    from kagami_studio.production.topic_generator import generate_script_from_topic

    script = await generate_script_from_topic(
        topic="The Science of Farts",
        duration=60,
        tone="educational_funny",
    )

    result = await produce_video(script)

Created: January 2026
Updated: January 2026 - Added TED-style layouts
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

# Import from unified models
from kagami_studio.production.models import (
    Presentation,
    PresentationTone,
    SlideContent,
)

logger = logging.getLogger(__name__)


@dataclass
class TopicPlan:
    """High-level plan for a topic-based presentation."""

    topic: str
    title: str
    hook: str  # Opening hook to grab attention
    key_points: list[str]  # Main points to cover
    conclusion: str  # Closing thought
    tone: PresentationTone
    target_duration: int  # seconds
    slide_count: int


class SlideOutline(BaseModel):
    """LLM output format for a single slide."""

    title: str = Field(description="Slide title (2-6 words)")
    spoken: str = Field(description="What the narrator says (1-3 sentences)")
    layout: str = Field(default="hero_split", description="Layout type")
    image_prompt: str | None = Field(default=None, description="AI image prompt")
    stat_value: str | None = Field(default=None, description="For stat_focus layout")
    stat_label: str | None = Field(default=None, description="For stat_focus layout")
    icon_items: list[dict] | None = Field(default=None, description="For icon_grid")
    recap_points: list[str] | None = Field(default=None, description="For recap layout")


class PresentationOutline(BaseModel):
    """LLM output format for full presentation plan."""

    title: str = Field(description="Presentation title")
    hook: str = Field(description="Opening hook to grab attention")
    slides: list[SlideOutline] = Field(description="Individual slide outlines")
    conclusion: str = Field(description="Final thought or call to action")


async def generate_script_from_topic(
    topic: str,
    duration: int = 60,
    tone: str | PresentationTone = "educational_funny",
    speaker: str = "tim",
    num_slides: int | None = None,
) -> list[dict[str, Any]]:
    """Generate a complete script from a topic.

    This is THE entry point for topic-based video generation.

    Args:
        topic: The topic to create a video about. Can be simple ("cats")
               or detailed ("The science of why cats purr and what it means")
        duration: Target duration in seconds (default: 60)
        tone: Presentation tone (default: educational_funny)
        speaker: Speaker identity for voice/style (default: tim)
        num_slides: Override slide count (default: auto based on duration)

    Returns:
        Script list ready for produce_video()

    Example:
        script = await generate_script_from_topic(
            topic="Why we yawn",
            duration=45,
            tone="educational_funny",
        )
        result = await produce_video(script)
    """
    import httpx
    import os

    # Convert tone to enum
    if isinstance(tone, str):
        try:
            tone = PresentationTone(tone)
        except ValueError:
            tone = PresentationTone.EDUCATIONAL_FUNNY

    # Calculate slide count from duration (~8-12 seconds per slide for TED-style)
    if num_slides is None:
        num_slides = max(5, min(12, duration // 10))

    # Get tone-specific instructions
    tone_instructions = _get_tone_instructions(tone)

    # Build prompt with layout guidance
    prompt = f"""Create a {num_slides}-slide TED-style presentation about: {topic}

DURATION: {duration} seconds (~{duration // num_slides}s per slide)
TONE: {tone.value}
{tone_instructions}

TED RULES (CRITICAL):
1. Maximum 6 words per slide title
2. ONE idea per slide
3. Start with attention-grabbing HOOK
4. End with memorable TAKEAWAY

LAYOUT OPTIONS - Choose the BEST for each slide:
- hero_full: Full-bleed image + title overlay (hooks, emotional impact)
- hero_split: 60/40 image + text split (explanatory content)
- stat_focus: Giant number + label (surprising statistics)
- minimal_text: Bold text only (key points, transitions)
- icon_grid: 2-4 icons with labels (related concepts)
- recap: Numbered points (summaries)

IMAGE PROMPTS (for hero layouts):
- Describe warm, friendly, modern illustrations
- Use metaphors and abstract concepts
- NEVER: medical imagery, anatomy, x-rays, scary/creepy content
- Think "magazine cover" not "textbook"

Return JSON:
{{
    "title": "Presentation Title",
    "hook": "Opening hook sentence",
    "slides": [
        {{
            "title": "Short Title",
            "spoken": "Narrator text (1-3 sentences)",
            "layout": "hero_full|hero_split|stat_focus|minimal_text|icon_grid|recap",
            "image_prompt": "For hero layouts: detailed warm friendly image description",
            "stat_value": "For stat_focus: e.g. '14x'",
            "stat_label": "For stat_focus: e.g. 'times per day'",
            "icon_items": [{{"icon": "emoji", "label": "text"}}],
            "recap_points": ["Point 1", "Point 2"]
        }}
    ],
    "conclusion": "Final memorable thought"
}}"""

    logger.info(f"Generating script for: {topic} ({num_slides} slides, {duration}s)")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a TED-style presentation designer. Return valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.8,
                "max_tokens": 3000,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        response = data["choices"][0]["message"]["content"]

    # Parse response
    try:
        json_str = response.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]

        outline = json.loads(json_str.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        outline = _create_fallback_outline(topic, num_slides)

    # Convert to script format
    script = _outline_to_script(outline, speaker)

    logger.info(f"Generated script: {len(script)} slides")

    return script


async def generate_presentation(
    topic: str,
    duration: int = 90,
    tone: str | PresentationTone = "educational_funny",
    speaker: str = "tim",
    num_slides: int | None = None,
) -> Presentation:
    """Generate a complete Presentation object from a topic.

    Higher-level than generate_script_from_topic - returns a full
    Presentation model with SlideContent objects.

    Args:
        topic: The topic to create a video about
        duration: Target duration in seconds
        tone: Presentation tone
        speaker: Speaker identity
        num_slides: Override slide count

    Returns:
        Presentation object ready for rendering
    """
    script = await generate_script_from_topic(
        topic=topic,
        duration=duration,
        tone=tone,
        speaker=speaker,
        num_slides=num_slides,
    )

    # Convert tone
    if isinstance(tone, str):
        try:
            tone_enum = PresentationTone(tone)
        except ValueError:
            tone_enum = PresentationTone.EDUCATIONAL_FUNNY
    else:
        tone_enum = tone

    # Build SlideContent objects
    slides = []
    for s in script:
        slide = SlideContent(
            title=s.get("title", ""),
            spoken_text=s.get("spoken", ""),
            layout=s.get("layout", "hero_split"),
            image_prompt=s.get("image_prompt"),
            stat_value=s.get("stat_value"),
            stat_label=s.get("stat_label"),
            icon_items=s.get("icon_items"),
            recap_points=s.get("recap_points"),
        )
        slides.append(slide)

    return Presentation(
        title=topic,
        topic=topic,
        tone=tone_enum,
        slides=slides,
        target_duration_seconds=duration,
        speaker=speaker,
    )


def _get_tone_instructions(tone: PresentationTone) -> str:
    """Get tone-specific instructions for the LLM."""

    instructions = {
        PresentationTone.EDUCATIONAL: """
Be clear and informative. Use simple language to explain complex concepts.
Include interesting facts and statistics. Maintain a professional but accessible tone.""",
        PresentationTone.EDUCATIONAL_FUNNY: """
Be informative AND entertaining. Include humor, fun facts, and playful observations.
Make learning feel like discovery, not lecture. Use wit without being crude.
Think 'fascinating TED talk' meets 'funny friend explaining things.'""",
        PresentationTone.ENTERTAINING: """
Prioritize engagement and fun. Use humor, surprises, and unexpected connections.
Keep it light and breezy. Make the audience smile.""",
        PresentationTone.PROFESSIONAL: """
Maintain a polished, corporate tone. Be concise and focused.
Use data and evidence. Keep it business-appropriate.""",
        PresentationTone.INSPIRATIONAL: """
Build emotional connection. Use powerful language and vivid imagery.
Include calls to action. Make the audience feel motivated.""",
        PresentationTone.STORYTELLING: """
Use narrative structure with a clear arc. Include characters and conflict.
Build tension and release. Make it feel like a story, not a lecture.""",
    }

    return instructions.get(tone, instructions[PresentationTone.EDUCATIONAL_FUNNY])


def _create_fallback_outline(topic: str, num_slides: int) -> dict:
    """Create a basic outline if LLM fails."""

    slides = [
        {
            "title": f"What is {topic}?",
            "spoken": f"Let's explore {topic} together.",
            "visual_hint": "Warm, inviting introduction image",
        },
    ]

    for i in range(num_slides - 2):
        slides.append(
            {
                "title": f"Key Point {i + 1}",
                "spoken": f"Here's something interesting about {topic}.",
                "visual_hint": "Engaging visual related to the topic",
            }
        )

    slides.append(
        {
            "title": "Wrapping Up",
            "spoken": f"And that's {topic}! Now you know more than most people.",
            "visual_hint": "Satisfying conclusion visual",
        }
    )

    return {
        "title": f"All About {topic}",
        "hook": f"Ever wondered about {topic}?",
        "slides": slides,
        "conclusion": f"Thanks for learning about {topic}!",
    }


def _outline_to_script(outline: dict, speaker: str) -> list[dict[str, Any]]:
    """Convert outline to produce_video() script format with layouts."""

    script = []

    # Title slide with hook - always hero_full
    script.append(
        {
            "title": outline.get("title", "Untitled"),
            "spoken": outline.get("hook", ""),
            "layout": "hero_full",
            "image_prompt": f"Bold, attention-grabbing visual representing {outline.get('title', '')}. "
            f"Modern illustration style, warm colors, professional quality.",
            "mood": "energetic",
        }
    )

    # Content slides with layout info
    for slide in outline.get("slides", []):
        slide_data = {
            "title": slide.get("title", ""),
            "spoken": slide.get("spoken", ""),
            "layout": slide.get("layout", "hero_split"),
            "mood": "engaging",
        }

        # Add layout-specific fields
        if slide.get("image_prompt"):
            slide_data["image_prompt"] = slide["image_prompt"]
        elif slide.get("visual_hint"):
            slide_data["image_prompt"] = slide["visual_hint"]

        if slide.get("stat_value"):
            slide_data["stat_value"] = slide["stat_value"]
        if slide.get("stat_label"):
            slide_data["stat_label"] = slide["stat_label"]
        if slide.get("icon_items"):
            slide_data["icon_items"] = slide["icon_items"]
        if slide.get("recap_points"):
            slide_data["recap_points"] = slide["recap_points"]

        script.append(slide_data)

    # Conclusion slide
    if outline.get("conclusion"):
        script.append(
            {
                "title": "Thanks for Watching!",
                "spoken": outline["conclusion"],
                "layout": "hero_full",
                "image_prompt": "Warm, satisfying sunset or peaceful scene. Modern illustration, soft colors.",
                "mood": "warm",
            }
        )

    return script


async def quick_video(
    topic: str,
    duration: int = 60,
    tone: str = "educational_funny",
    speaker: str = "tim",
    output_dir: str | None = None,
    deploy_name: str | None = None,
) -> dict[str, Any]:
    """One-liner video generation from topic.

    THE simplest way to create a video:

        result = await quick_video("Why cats purr")

    Args:
        topic: What the video is about
        duration: Target duration in seconds
        tone: Presentation tone
        speaker: Speaker identity
        output_dir: Custom output directory (default: auto)
        deploy_name: If set, deploy to ~/projects/art/{name}/

    Returns:
        Dict with video_path, script, and other metadata
    """
    from kagami_studio.production import produce_video

    # Generate script
    script = await generate_script_from_topic(
        topic=topic,
        duration=duration,
        tone=tone,
        speaker=speaker,
    )

    # Produce video
    result = await produce_video(
        script=script,
        speaker=speaker,
        output_dir=output_dir,
        generate_images=True,
        burn_ass_subtitles=True,
        reuse_images=False,
    )

    if not result.success:
        raise RuntimeError(f"Video production failed: {result.error}")

    # Deploy if requested
    if deploy_name:
        import shutil
        import subprocess
        from pathlib import Path

        art_dir = Path.home() / "projects" / "art" / deploy_name
        art_dir.mkdir(parents=True, exist_ok=True)

        # Copy assets
        final_video = art_dir / f"{deploy_name}_hd.mp4"
        shutil.copy(result.video_path, final_video)

        # Copy slides
        slides_html = result.video_path.parent / "slides.html"
        if slides_html.exists():
            shutil.copy(slides_html, art_dir / "slides.html")

        # Copy images
        images_dir = result.video_path.parent / "images"
        if images_dir.exists():
            dest_images = art_dir / "images"
            if dest_images.exists():
                shutil.rmtree(dest_images)
            shutil.copytree(images_dir, dest_images)

        # Mobile transcode
        mobile_video = art_dir / f"{deploy_name}_mobile.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(final_video),
                "-c:v",
                "libx265",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-vf",
                "scale=1280:720",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                str(mobile_video),
            ],
            capture_output=True,
        )

        result.video_path = final_video

    return {
        "success": True,
        "video_path": str(result.video_path),
        "duration_s": result.duration_s,
        "script": script,
        "slides_count": len(script),
    }


# Convenience exports
__all__ = [
    "PresentationOutline",
    "PresentationTone",
    "SlideOutline",
    "TopicPlan",
    "generate_presentation",
    "generate_script_from_topic",
    "quick_video",
]
