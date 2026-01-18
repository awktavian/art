"""LLM-Powered Slide Generator — Hierarchical content design.

Uses LLM to individually design each slide with:
1. HIGH-LEVEL: Presentation structure planning (informed by speaker identity)
2. PER-SLIDE: Individual slide content and visual design
3. VISUAL: Hero image prompts for AI generation

Speaker Integration:
- Loads character from assets/characters/*/metadata.json
- Uses personality traits for presentation style
- Uses speech profile for tone/tempo
- Adapts visual style to match character
- Supports all characters: tim, andy, kelli_finglass, etc.

Hierarchical call pattern:
    1. load_speaker(name) → Character
    2. plan_presentation(script, speaker) → PresentationPlan
    3. for each slide: design_slide(slide, plan, speaker) → SlideContent
    4. for visuals: generate_image_prompt(slide, speaker) → str

Context Management:
- Each LLM call gets minimal, focused context
- Speaker personality informs but doesn't dominate
- Presentation theme passed as compact summary
- No cross-slide content leakage
- Structured output for reliable parsing

Usage:
    from kagami_studio.production.llm_slide_generator import (
        LLMSlideGenerator,
        generate_presentation,
    )

    # Any character from assets/characters/
    designs = await generate_presentation(
        script=[{"title": "Welcome", "spoken": "..."}],
        theme="professional",
        speaker="tim",  # or "andy", "kelli_finglass", etc.
    )

    # List available speakers
    from kagami_studio.characters import list_characters
    print(list_characters())  # ['tim', 'andy', 'bella', 'kelli_finglass', ...]
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from kagami_studio.production.slide_design import (
    GradientPreset,
    SlideDesign,
    SlideLayout,
)

if TYPE_CHECKING:
    from kagami_studio.characters import Character

logger = logging.getLogger(__name__)


# === SPEAKER CONTEXT BUILDER ===


@dataclass
class SpeakerContext:
    """Compact speaker context for LLM prompts.

    Built from Character metadata, provides only what LLM needs.
    """

    identity_id: str
    name: str
    speaking_style: str = ""
    wpm: int = 150
    traits: list[str] = field(default_factory=list)
    catch_phrases: list[str] = field(default_factory=list)
    professional_focus: list[str] = field(default_factory=list)
    visual_style_hint: str = ""
    mood_default: str = "professional"

    @classmethod
    def from_character(cls, char: Character) -> SpeakerContext:
        """Build context from Character object."""
        # Determine default mood from personality traits
        traits_lower = [t.lower() for t in (char.personality.traits or [])]
        mood = "professional"
        if any("warm" in t or "friendly" in t for t in traits_lower):
            mood = "warm"
        if any("energetic" in t or "excited" in t for t in traits_lower):
            mood = "exciting"
        if any("calm" in t or "measured" in t for t in traits_lower):
            mood = "calm"

        # Determine visual style from character metadata
        visual_hint = ""
        if char.role.value == "household":
            visual_hint = "modern home, warm lighting"
        elif char.role.value == "external":
            visual_hint = "professional, corporate"
        elif char.metadata.get("professional"):
            visual_hint = "tech industry, innovation"

        # Extract professional focus
        professional = char.metadata.get("professional", {})
        focus = professional.get("focus", [])

        return cls(
            identity_id=char.identity_id,
            name=char.name,
            speaking_style=char.personality.speaking_style,
            wpm=char.personality.wpm,
            traits=char.personality.traits[:5],  # Max 5 traits
            catch_phrases=char.personality.catch_phrases[:3],
            professional_focus=focus[:3] if focus else [],
            visual_style_hint=visual_hint,
            mood_default=mood,
        )

    @classmethod
    def default(cls, name: str = "presenter") -> SpeakerContext:
        """Create default context for unknown speaker."""
        return cls(
            identity_id=name.lower().replace(" ", "_"),
            name=name.title(),
            speaking_style="clear, professional",
            wpm=150,
            traits=["professional", "knowledgeable"],
            mood_default="professional",
        )

    def to_prompt_block(self) -> str:
        """Format as compact LLM prompt block."""
        lines = [f"SPEAKER: {self.name}"]

        if self.speaking_style:
            lines.append(f"Style: {self.speaking_style}")
        if self.traits:
            lines.append(f"Traits: {', '.join(self.traits[:3])}")
        if self.professional_focus:
            lines.append(f"Focus: {', '.join(self.professional_focus)}")
        if self.catch_phrases:
            lines.append(f"Phrases: {', '.join(self.catch_phrases)}")

        return "\n".join(lines)


def load_speaker_context(speaker: str | Character | None) -> SpeakerContext:
    """Load speaker context from name or Character object.

    Args:
        speaker: Speaker name (identity_id), Character object, or None

    Returns:
        SpeakerContext with personality/style info
    """
    if speaker is None:
        return SpeakerContext.default()

    # Already a Character object
    if hasattr(speaker, "identity_id"):
        return SpeakerContext.from_character(speaker)  # type: ignore

    # Load by name
    try:
        from kagami_studio.characters import load_character

        char = load_character(str(speaker))
        if char:
            logger.debug(f"Loaded speaker context: {char.name} ({char.identity_id})")
            return SpeakerContext.from_character(char)
    except Exception as e:
        logger.debug(f"Could not load character '{speaker}': {e}")

    # Fallback to default
    return SpeakerContext.default(str(speaker))


# === PYDANTIC MODELS FOR STRUCTURED LLM OUTPUT ===


class VisualStyle(str, Enum):
    """Visual style for hero images."""

    MINIMALIST = "minimalist"
    ABSTRACT = "abstract"
    PHOTOREALISTIC = "photorealistic"
    ILLUSTRATION = "illustration"
    GEOMETRIC = "geometric"
    CINEMATIC = "cinematic"


class SlideLayoutChoice(str, Enum):
    """LLM-friendly layout choices."""

    HERO_FULL = "hero_full"  # Full background image + text overlay
    HERO_LEFT = "hero_left"  # Image left, text right
    HERO_RIGHT = "hero_right"  # Text left, image right
    TITLE_ONLY = "title_only"  # Big centered title
    TITLE_SUBTITLE = "title_subtitle"  # Title + subtitle
    BULLETS_ICON = "bullets_icon"  # Title + bullets with icons
    STATS = "stats"  # Big number + label
    QUOTE = "quote"  # Quote + attribution
    TWO_COLUMN = "two_column"  # Two columns
    THREE_COLUMN = "three_column"  # Three columns


class PresentationPlan(BaseModel):
    """High-level presentation structure from LLM."""

    theme_description: str = Field(description="2-3 sentence description of visual theme")
    mood: str = Field(description="Overall mood: warm, professional, exciting, calm")
    color_palette: str = Field(description="Color palette description")
    gradient_choice: str = Field(
        description="One of: dark_blue, midnight, ocean, sunset, forest, warm"
    )
    accent_color: str = Field(description="Hex color without # for accents, e.g. 4a9eff")
    visual_style: VisualStyle = Field(description="Visual style for imagery")
    narrative_arc: str = Field(description="Brief narrative arc description")


class SlideContentDesign(BaseModel):
    """Individual slide design from LLM."""

    layout: SlideLayoutChoice = Field(description="Best layout for this content")
    title_refined: str = Field(description="Refined/improved title (max 8 words)")
    subtitle: str = Field(default="", description="Optional subtitle (max 15 words)")
    points: list[str] = Field(
        default_factory=list, description="Bullet points if applicable (max 4)"
    )
    icons: list[str] = Field(
        default_factory=list,
        description="Icon names for bullets: check, brain, home, shield, lightbulb, zap, heart, users, lock, globe, star, arrow-right",
    )
    stat_value: str = Field(default="", description="For STATS layout: the big number")
    stat_label: str = Field(default="", description="For STATS layout: what it represents")
    quote_text: str = Field(default="", description="For QUOTE layout: the quote")
    quote_author: str = Field(default="", description="For QUOTE layout: attribution")
    hero_image_prompt: str = Field(
        default="",
        description="Detailed prompt for AI image generation (describe scene, style, mood)",
    )
    visual_metaphor: str = Field(
        default="",
        description="What visual metaphor represents this slide's concept?",
    )
    transition_hint: str = Field(
        default="",
        description="How does this slide connect to the next?",
    )


class ColumnContent(BaseModel):
    """Content for a single column."""

    title: str = Field(description="Column title")
    content: str = Field(description="Column content/description")
    icon: str = Field(default="check", description="Icon name for column")


class SlideColumnsDesign(BaseModel):
    """Multi-column slide design."""

    columns: list[ColumnContent] = Field(description="2-3 columns of content")


# === SLIDE GENERATOR CLASS ===


@dataclass
class LLMSlideGenerator:
    """Hierarchical LLM-powered slide generator.

    Fully integrated with Character system for any speaker.

    Attributes:
        llm_service: LLM service instance
        initialized: Whether service is ready
        default_theme: Default gradient theme
        speaker_context: Loaded speaker context
    """

    llm_service: Any = None
    initialized: bool = False
    default_theme: GradientPreset = GradientPreset.DARK_BLUE
    speaker_context: SpeakerContext | None = None

    async def initialize(self) -> None:
        """Initialize LLM service."""
        if self.initialized:
            return

        from kagami.core.services.llm import get_llm_service

        self.llm_service = get_llm_service()
        await self.llm_service.initialize()
        self.initialized = True
        logger.info("✓ LLM Slide Generator initialized")

    def set_speaker(self, speaker: str | Character | None) -> SpeakerContext:
        """Set and load speaker context.

        Args:
            speaker: Speaker name, Character object, or None

        Returns:
            Loaded SpeakerContext
        """
        self.speaker_context = load_speaker_context(speaker)
        logger.info(
            f"✓ Speaker set: {self.speaker_context.name} ({self.speaker_context.identity_id})"
        )
        return self.speaker_context

    async def plan_presentation(
        self,
        script: list[dict[str, Any]],
        speaker: str | Character | None = None,
        style_hints: str = "",
    ) -> PresentationPlan:
        """Generate high-level presentation plan.

        LEVEL 1 of hierarchy — sets theme for all slides.
        Integrates speaker personality for cohesive style.

        Args:
            script: List of slide dictionaries
            speaker: Speaker name, Character object, or None
            style_hints: Optional style guidance

        Returns:
            PresentationPlan with theme/mood/colors
        """
        # Load speaker context
        ctx = load_speaker_context(speaker)
        self.speaker_context = ctx

        # Build compact context
        slide_titles = [s.get("title", "Untitled") for s in script]
        slide_summary = "\n".join(f"- {t}" for t in slide_titles[:10])

        # Build speaker block
        speaker_block = ctx.to_prompt_block()

        # Combine style hints with speaker visual hint
        combined_style = style_hints
        if ctx.visual_style_hint:
            combined_style = (
                f"{style_hints}, {ctx.visual_style_hint}" if style_hints else ctx.visual_style_hint
            )

        prompt = f"""You are a world-class presentation designer creating a Gamma-style visual presentation.

SLIDES ({len(script)} total):
{slide_summary}

{speaker_block}

STYLE HINTS: {combined_style or "Modern, professional, visually striking"}
DEFAULT MOOD: {ctx.mood_default}

Design a cohesive visual theme for this presentation that reflects the speaker's personality and style.
Consider:
- What visual style matches both the content AND the speaker?
- What color palette creates the right mood for this speaker?
- How does the narrative arc reflect the speaker's communication style?

Respond with a JSON object matching this schema:
{{
    "theme_description": "2-3 sentence visual theme description",
    "mood": "warm|professional|exciting|calm",
    "color_palette": "description of colors",
    "gradient_choice": "dark_blue|midnight|ocean|sunset|forest|warm",
    "accent_color": "hex color without # (e.g. 4a9eff)",
    "visual_style": "minimalist|abstract|photorealistic|illustration|geometric|cinematic",
    "narrative_arc": "brief narrative arc description"
}}"""

        try:
            result = await self.llm_service.generate_structured(
                prompt=prompt,
                response_model=PresentationPlan,
                max_tokens=500,
                temperature=0.7,
                hints={"provider": "anthropic"},  # Force cloud LLM
            )
            logger.info(f"✓ Presentation plan: {result.mood} / {result.gradient_choice}")
            return result
        except Exception as e:
            logger.warning(f"Cloud LLM failed, using intelligent defaults: {e}")
            # Intelligent fallback based on content analysis
            return self._fallback_presentation_plan(script, ctx)

    async def design_slide(
        self,
        slide: dict[str, Any],
        slide_index: int,
        total_slides: int,
        plan: PresentationPlan,
        previous_layout: SlideLayoutChoice | None = None,
        speaker_context: SpeakerContext | None = None,
    ) -> SlideContentDesign:
        """Design individual slide content.

        LEVEL 2 of hierarchy — designs each slide independently.
        Uses speaker context for personality-aligned content.

        Args:
            slide: Single slide dictionary
            slide_index: Position in presentation (0-based)
            total_slides: Total number of slides
            plan: Overall presentation plan
            previous_layout: Layout of previous slide (for variety)
            speaker_context: Speaker personality context

        Returns:
            SlideContentDesign with all content
        """
        title = slide.get("title", "")
        spoken = slide.get("spoken", "")
        points = slide.get("points", [])
        slide.get("mood", plan.mood)

        # Use stored context or provided
        ctx = speaker_context or self.speaker_context or SpeakerContext.default()

        # Position context
        position = (
            "opening"
            if slide_index == 0
            else "closing"
            if slide_index == total_slides - 1
            else "middle"
        )

        # Speaker style hint for slide design
        speaker_style_hint = ""
        if ctx.speaking_style:
            speaker_style_hint = f"Speaker style: {ctx.speaking_style}"
        if ctx.catch_phrases and slide_index == 0:
            speaker_style_hint += f"\nSignature phrases to consider: {', '.join(ctx.catch_phrases)}"

        # Enhanced prompt with microdelight emphasis
        prompt = f"""Design a VISUALLY STUNNING presentation slide. You are a world-class visual designer.

SLIDE {slide_index + 1}/{total_slides} ({position})
Title: {title}
Narration: {spoken[:200]}
Existing points: {points[:3] if points else "none"}
Previous layout: {previous_layout.value if previous_layout else "none"}

THEME: {plan.theme_description}
VISUAL STYLE: {plan.visual_style.value}
SPEAKER: {ctx.name}
{speaker_style_hint}

=== DESIGN PRINCIPLES (MANDATORY) ===
1. VISUAL IMPACT: Every slide must have a strong visual hook
2. MICRODELIGHT: Add subtle touches that reward attention
3. ICON SELECTION: Choose icons that perfectly match concepts (not generic)
4. IMAGE PROMPTS: Be extremely detailed - include lighting, mood, composition, style

=== LAYOUT SELECTION ===
- hero_full/hero_left/hero_right: Use for emotional impact, storytelling moments
- title_only: Use SPARINGLY for chapter breaks, dramatic pauses
- bullets_icon: Use for lists with MEANINGFUL icons (not just checkmarks)
- stats: Use when you have a compelling number
- quote: Use for memorable statements
- two_column/three_column: Use for comparisons, features

=== ICON GUIDELINES ===
Match icons semantically:
- brain/lightbulb: ideas, thinking, understanding
- zap/flame: energy, power, speed, danger
- heart: emotion, care, health
- shield/lock: protection, security, safety
- users: people, community, team
- globe/home: location, world, domestic
- star/trophy: achievement, excellence
- check/check-circle: completion, validation
- arrow-right: progression, next steps
- sparkles: magic, enhancement, new
- beaker/microscope/dna: science, research
- clock/timer: time, urgency
- cpu/settings: technology, configuration

=== IMAGE PROMPT GUIDELINES ===
For hero_image_prompt, be EXTREMELY specific:
- Describe the scene, subject, action
- Specify lighting (golden hour, dramatic shadows, soft diffused)
- Include style (photorealistic, 3D render, illustration, cinematic)
- Mention mood (warm, cold, energetic, calm, mysterious)
- Add composition notes (close-up, wide shot, centered, rule of thirds)
- Include color palette alignment with the theme

=== CRITICAL: AVOID CREEPY/MEDICAL IMAGERY ===
NEVER include in hero_image_prompt:
- Exposed skulls, bones, or teeth (NO X-RAY VIEWS)
- Anatomical cross-sections showing internal organs
- Medical/clinical imagery that feels like a textbook
- Body horror elements (exposed veins, nerves visible through skin)
- Creepy uncanny valley faces
- Anything that would make viewers uncomfortable

ALWAYS prefer:
- WARM, FRIENDLY, APPROACHABLE imagery
- Stylized illustrations over photorealistic anatomy
- Abstract representations of scientific concepts
- Beautiful metaphorical imagery (e.g., "warm glow" not "dilating blood vessels")
- People enjoying experiences (eating ice cream) not suffering
- Modern, clean aesthetic - think Pixar, not medical journal

For scientific/medical topics:
- Use METAPHORS instead of literal anatomy
- Show the EXPERIENCE not the mechanism
- Make it DELIGHTFUL not clinical
- Focus on EMOTION not biology

For {position} slides:
- Opening: DRAMATIC visual hook, establish tone, captivate immediately
- Middle: Support the narrative, build visual rhythm, vary layouts
- Closing: Memorable image, emotional resonance, leave impression

Return JSON:
{{
    "layout": "hero_full|hero_left|hero_right|title_only|title_subtitle|bullets_icon|stats|quote|two_column|three_column",
    "title_refined": "improved title (max 8 words, punchy)",
    "subtitle": "optional subtitle (max 15 words)",
    "points": ["point1 (concise)", "point2", "max 4 points"],
    "icons": ["semantically perfect icon for each point"],
    "stat_value": "for stats: make it dramatic (e.g., '47%' or '3x')",
    "stat_label": "for stats: what it represents",
    "quote_text": "for quote: memorable, punchy",
    "quote_author": "for quote: attribution",
    "hero_image_prompt": "DETAILED: Subject, action, lighting, style, mood, composition, colors",
    "visual_metaphor": "the core visual concept that makes this memorable",
    "transition_hint": "how this connects to next slide"
}}"""

        try:
            result = await self.llm_service.generate_structured(
                prompt=prompt,
                response_model=SlideContentDesign,
                max_tokens=600,
                temperature=0.8,
                hints={"provider": "anthropic"},  # Force cloud LLM
            )
            logger.debug(
                f"  Slide {slide_index + 1}: {result.layout.value} - {result.title_refined[:30]}"
            )
            return result
        except Exception as e:
            logger.warning(f"Slide design failed, using heuristic: {e}")
            # Intelligent fallback based on content analysis
            return self._fallback_slide_design(
                slide, slide_index, total_slides, plan, previous_layout
            )

    async def design_columns(
        self,
        slide: dict[str, Any],
        plan: PresentationPlan,
        num_columns: int = 3,
    ) -> list[ColumnContent]:
        """Design multi-column content.

        LEVEL 2b — specialized for column layouts.
        """
        title = slide.get("title", "")
        spoken = slide.get("spoken", "")
        points = slide.get("points", [])

        prompt = f"""Create {num_columns} columns for a presentation slide.

SLIDE CONTEXT:
Title: {title}
Narration: {spoken[:150]}
Points: {points[:4] if points else "none"}

THEME: {plan.mood} / {plan.visual_style.value}

Each column should have:
- A concise title (2-4 words)
- Brief content (1-2 sentences)
- An icon from: [check, brain, home, shield, lightbulb, zap, heart, users, lock, globe, star, arrow-right]

Make columns complementary but distinct.

Return JSON array:
[
    {{"title": "...", "content": "...", "icon": "..."}},
    ...
]"""

        try:
            # Generate as list
            response = await self.llm_service.generate(
                prompt=prompt,
                app_name="slide_generator",
                max_tokens=400,
                temperature=0.7,
                routing_hints={"provider": "anthropic"},  # Force cloud LLM
            )

            # Parse JSON from response
            data = json.loads(response)
            columns = [ColumnContent(**c) for c in data[:num_columns]]
            return columns
        except Exception as e:
            logger.warning(f"Column design failed, using heuristic: {e}")
            # Intelligent fallback based on content
            return self._fallback_columns(points, num_columns)

    async def generate_image_prompt(
        self,
        slide: SlideContentDesign,
        plan: PresentationPlan,
        speaker_context: SpeakerContext | None = None,
    ) -> str:
        """Generate detailed image prompt for AI generation.

        LEVEL 3 — creates detailed visual descriptions.
        Incorporates speaker visual style hints.
        """
        ctx = speaker_context or self.speaker_context or SpeakerContext.default()

        if slide.hero_image_prompt:
            # Already have a prompt from design phase
            base_prompt = slide.hero_image_prompt
        else:
            base_prompt = slide.visual_metaphor or slide.title_refined

        # Enhance with style
        style_map = {
            VisualStyle.MINIMALIST: "clean, minimal, white space, subtle, elegant",
            VisualStyle.ABSTRACT: "abstract shapes, flowing forms, artistic",
            VisualStyle.PHOTOREALISTIC: "photorealistic, professional photography, high detail",
            VisualStyle.ILLUSTRATION: "digital illustration, stylized, artistic rendering",
            VisualStyle.GEOMETRIC: "geometric shapes, patterns, mathematical beauty",
            VisualStyle.CINEMATIC: "cinematic lighting, dramatic, film still quality",
        }
        style_desc = style_map.get(plan.visual_style, "modern, professional")

        # Add speaker visual context
        speaker_visual_hint = ""
        if ctx.visual_style_hint:
            speaker_visual_hint = f"ENVIRONMENT HINT: {ctx.visual_style_hint}"
        if ctx.professional_focus:
            speaker_visual_hint += f"\nDOMAIN: {', '.join(ctx.professional_focus)}"

        prompt = f"""Create a STUNNING, REFINED image generation prompt. You are a master visual artist.

SLIDE: {slide.title_refined}
VISUAL METAPHOR: {slide.visual_metaphor}
BASE IDEA: {base_prompt}

STYLE: {plan.visual_style.value} ({style_desc})
COLORS: {plan.color_palette}
MOOD: {plan.mood}
SPEAKER: {ctx.name}
{speaker_visual_hint}

=== IMAGE EXCELLENCE REQUIREMENTS ===
Create a Flux/DALL-E/Midjourney prompt that is:

1. VISUALLY STUNNING - Award-winning composition, beautiful lighting
2. EMOTIONALLY RESONANT - Captures the mood perfectly
3. PROFESSIONALLY POLISHED - No amateur look, refined details
4. CONTEXTUALLY PERFECT - Matches the slide's message
5. WARM AND APPROACHABLE - Makes viewers feel good, not uncomfortable

=== CRITICAL: NEVER INCLUDE ===
- Exposed skulls, bones, or teeth
- X-ray or anatomical views showing internal structures
- Medical/clinical imagery
- Body horror elements (visible veins, nerves through skin)
- Anything creepy or unsettling

=== INSTEAD, USE ===
- Beautiful metaphorical imagery
- Stylized illustrations (Pixar-like, not medical textbook)
- Abstract representations of concepts
- Warm, friendly faces enjoying experiences
- Modern, clean aesthetic

=== MANDATORY ELEMENTS ===
Include ALL of these in your prompt:
- SUBJECT: What's the main focus? (be specific)
- ACTION/STATE: What's happening?
- LIGHTING: Specific lighting (golden hour, dramatic rim light, soft diffused, etc.)
- COMPOSITION: Camera angle, framing (close-up, wide shot, aerial, etc.)
- STYLE: Artistic style (cinematic, editorial, 3D render, etc.)
- MOOD: Emotional atmosphere
- COLORS: Color palette that matches theme
- QUALITY: "professional quality, highly detailed, 8k, sharp focus"
- BACKGROUND: Dark edges suitable for text overlay

=== MICRODELIGHT TOUCHES ===
Add subtle visual interest:
- Atmospheric elements (subtle particles, light rays, mist)
- Depth cues (bokeh background, layered elements)
- Texture details that reward close viewing
- Dynamic elements that suggest motion or life

Return ONLY the refined image prompt (no explanations)."""

        try:
            result = await self.llm_service.generate(
                prompt=prompt,
                app_name="slide_generator",
                max_tokens=200,
                temperature=0.9,
                routing_hints={"provider": "anthropic"},  # Force cloud LLM
            )
            return result.strip()
        except Exception as e:
            logger.warning(f"Image prompt generation failed, using template: {e}")
            return f"{style_desc} visualization of {slide.title_refined}, {plan.mood} mood, dark background"

    # === INTELLIGENT FALLBACK METHODS ===

    def _fallback_presentation_plan(
        self,
        script: list[dict[str, Any]],
        ctx: SpeakerContext,
    ) -> PresentationPlan:
        """Generate intelligent fallback plan based on content analysis.

        Args:
            script: List of slide dictionaries
            ctx: Speaker context

        Returns:
            PresentationPlan with content-derived settings
        """
        # Analyze content to determine mood
        all_text = " ".join(s.get("title", "") + " " + s.get("spoken", "") for s in script).lower()

        # Mood detection heuristics
        mood = "professional"
        if any(w in all_text for w in ["exciting", "amazing", "incredible", "wow", "fun"]):
            mood = "exciting"
        elif any(w in all_text for w in ["calm", "peaceful", "relax", "mindful"]):
            mood = "calm"
        elif any(w in all_text for w in ["warm", "cozy", "friendly", "welcome"]):
            mood = "warm"

        # Gradient based on mood
        gradient_map = {
            "professional": "dark_blue",
            "exciting": "sunset",
            "warm": "warm",
            "calm": "ocean",
        }

        # Visual style based on content
        visual_style = VisualStyle.MINIMALIST
        if any(w in all_text for w in ["science", "research", "data", "study"]):
            visual_style = VisualStyle.GEOMETRIC
        elif any(w in all_text for w in ["story", "journey", "adventure"]):
            visual_style = VisualStyle.CINEMATIC

        return PresentationPlan(
            theme_description=f"{mood.title()} presentation with {visual_style.value} visuals",
            mood=mood,
            color_palette=f"{mood.title()} palette with accent highlights",
            gradient_choice=gradient_map.get(mood, "dark_blue"),
            accent_color="4a9eff"
            if mood == "professional"
            else "ff9f40"
            if mood == "exciting"
            else "00d4aa",
            visual_style=visual_style,
            narrative_arc="Build from introduction through key points to conclusion",
        )

    def _fallback_slide_design(
        self,
        slide: dict[str, Any],
        slide_index: int,
        total_slides: int,
        plan: PresentationPlan,
        previous_layout: SlideLayoutChoice | None = None,
    ) -> SlideContentDesign:
        """Generate intelligent fallback slide design based on content.

        Args:
            slide: Single slide dictionary
            slide_index: Position in presentation
            total_slides: Total number of slides
            plan: Presentation plan
            previous_layout: Previous slide's layout

        Returns:
            SlideContentDesign with heuristic-based settings
        """
        title = slide.get("title", "")
        spoken = slide.get("spoken", "")
        points = slide.get("points", [])

        # Smart layout selection based on position and content
        if slide_index == 0:
            # Opening slide
            layout = SlideLayoutChoice.HERO_FULL
        elif slide_index == total_slides - 1:
            # Closing slide
            layout = SlideLayoutChoice.TITLE_ONLY
        elif points and len(points) >= 3:
            # Multiple points = bullets
            layout = SlideLayoutChoice.BULLETS_ICON
        elif any(c.isdigit() for c in spoken[:50]):
            # Contains numbers = stats
            layout = SlideLayoutChoice.STATS
        elif len(spoken) > 200 and not points:
            # Long text with no points = quote style
            layout = SlideLayoutChoice.QUOTE
        elif previous_layout == SlideLayoutChoice.BULLETS_ICON:
            # Vary from previous
            layout = SlideLayoutChoice.HERO_LEFT
        else:
            layout = SlideLayoutChoice.TITLE_SUBTITLE

        # Extract potential stat from spoken text
        stat_value = ""
        stat_label = ""
        if layout == SlideLayoutChoice.STATS:
            import re

            numbers = re.findall(r"\d+[\d,\.]*\s*%?", spoken)
            if numbers:
                stat_value = numbers[0]
                stat_label = title if title else "Key Metric"

        # Smart icon selection
        icons = []
        icon_keywords = {
            "check": ["complete", "done", "success", "yes"],
            "brain": ["think", "mind", "brain", "learn", "smart"],
            "home": ["home", "house", "family"],
            "shield": ["safe", "secure", "protect"],
            "lightbulb": ["idea", "insight", "discover"],
            "zap": ["fast", "quick", "power", "energy"],
            "heart": ["love", "care", "health"],
            "users": ["team", "people", "community"],
            "globe": ["world", "global", "international"],
            "star": ["best", "top", "favorite"],
        }
        text_lower = (title + " " + spoken).lower()
        for icon, keywords in icon_keywords.items():
            if any(kw in text_lower for kw in keywords):
                icons.append(icon)
        # Default icons
        if not icons:
            icons = ["check"] * len(points) if points else ["lightbulb"]

        return SlideContentDesign(
            layout=layout,
            title_refined=title if title else "Untitled",
            subtitle=spoken[:150]
            if spoken and layout in [SlideLayoutChoice.TITLE_SUBTITLE, SlideLayoutChoice.HERO_FULL]
            else "",
            points=points[:5],
            icons=icons[: len(points)] if points else icons[:1],
            stat_value=stat_value,
            stat_label=stat_label,
            quote_text=spoken[:250] if layout == SlideLayoutChoice.QUOTE else "",
            quote_author="",
            hero_image_prompt=f"{plan.visual_style.value} image representing {title}"
            if layout
            in [
                SlideLayoutChoice.HERO_FULL,
                SlideLayoutChoice.HERO_LEFT,
                SlideLayoutChoice.HERO_RIGHT,
            ]
            else "",
            visual_metaphor=title,
            transition_hint="",
        )

    def _fallback_columns(
        self,
        points: list[str] | None,
        num_columns: int,
    ) -> list[ColumnContent]:
        """Generate fallback column content from points.

        Args:
            points: List of points from slide
            num_columns: Number of columns needed

        Returns:
            List of ColumnContent with sensible defaults
        """
        defaults = [
            ColumnContent(title="Overview", content="Key introduction point", icon="lightbulb"),
            ColumnContent(title="Details", content="Supporting information", icon="check"),
            ColumnContent(title="Summary", content="Concluding thoughts", icon="star"),
        ]

        if not points:
            return defaults[:num_columns]

        result = []
        for i, point in enumerate(points[:num_columns]):
            # Extract title from point (first few words or up to colon)
            if ":" in point:
                title = point.split(":")[0][:25]
                content = point.split(":", 1)[1][:100] if ":" in point else ""
            else:
                words = point.split()
                title = " ".join(words[:3])[:25]
                content = " ".join(words[3:])[:100]

            icon = ["lightbulb", "check", "star", "zap", "brain"][i % 5]
            result.append(ColumnContent(title=title, content=content, icon=icon))

        return result

    def content_to_design(
        self,
        content: SlideContentDesign,
        plan: PresentationPlan,
        columns: list[ColumnContent] | None = None,
    ) -> SlideDesign:
        """Convert LLM content to SlideDesign object.

        Args:
            content: LLM-generated content
            plan: Presentation plan
            columns: Column content if applicable

        Returns:
            SlideDesign ready for rendering
        """
        # Map layout choice to SlideLayout enum
        layout_map = {
            SlideLayoutChoice.HERO_FULL: SlideLayout.HERO_FULL,
            SlideLayoutChoice.HERO_LEFT: SlideLayout.HERO_LEFT,
            SlideLayoutChoice.HERO_RIGHT: SlideLayout.HERO_RIGHT,
            SlideLayoutChoice.TITLE_ONLY: SlideLayout.TITLE_ONLY,
            SlideLayoutChoice.TITLE_SUBTITLE: SlideLayout.TITLE_SUBTITLE,
            SlideLayoutChoice.BULLETS_ICON: SlideLayout.BULLETS_ICON,
            SlideLayoutChoice.STATS: SlideLayout.STATS,
            SlideLayoutChoice.QUOTE: SlideLayout.QUOTE,
            SlideLayoutChoice.TWO_COLUMN: SlideLayout.TWO_COLUMN,
            SlideLayoutChoice.THREE_COLUMN: SlideLayout.THREE_COLUMN,
        }

        # Map gradient choice
        gradient_map = {
            "dark_blue": GradientPreset.DARK_BLUE,
            "midnight": GradientPreset.MIDNIGHT,
            "ocean": GradientPreset.OCEAN,
            "sunset": GradientPreset.SUNSET,
            "forest": GradientPreset.FOREST,
            "warm": GradientPreset.WARM,
        }

        layout = layout_map.get(content.layout, SlideLayout.TITLE_SUBTITLE)
        gradient = gradient_map.get(plan.gradient_choice, GradientPreset.DARK_BLUE)

        # Build columns data
        columns_data = []
        if columns:
            columns_data = [
                {"title": c.title, "content": c.content, "icon": c.icon} for c in columns
            ]

        return SlideDesign(
            layout=layout,
            title=content.title_refined,
            subtitle=content.subtitle,
            points=content.points,
            icons=content.icons,
            gradient=gradient,
            accent_color=plan.accent_color,
            stat_value=content.stat_value,
            stat_label=content.stat_label,
            quote_text=content.quote_text,
            quote_author=content.quote_author,
            columns=columns_data,
            hero_prompt=content.hero_image_prompt,
        )


# === MAIN GENERATION FUNCTION ===


async def generate_presentation(
    script: list[dict[str, Any]],
    theme: str = "professional",
    speaker: str | Character | None = None,
    generate_images: bool = False,
    max_parallel: int = 4,
) -> list[SlideDesign]:
    """Generate LLM-designed presentation from script.

    Fully integrated with Character system for any speaker.

    Hierarchical generation:
    1. Load speaker context from Character metadata
    2. Plan overall presentation (1 LLM call, speaker-aware)
    3. Design each slide individually (N LLM calls, speaker-aware)
    4. Generate image prompts for hero slides (M LLM calls)

    Args:
        script: List of slide dictionaries
        theme: Style hints for presentation
        speaker: Speaker identity (name or Character object)
                 Examples: "tim", "andy", "kelli_finglass", Character object
                 None defaults to generic presenter
        generate_images: Whether to generate AI image prompts
        max_parallel: Max parallel slide design calls

    Returns:
        List of SlideDesign objects ready for rendering

    Example:
        # Using character name
        designs = await generate_presentation(script, speaker="tim")

        # Using Character object
        from kagami_studio.characters import load_character
        char = load_character("kelli_finglass")
        designs = await generate_presentation(script, speaker=char)

        # List available speakers
        from kagami_studio.characters import list_characters
        print(list_characters())
    """
    generator = LLMSlideGenerator()
    await generator.initialize()

    # Load speaker context
    speaker_ctx = load_speaker_context(speaker)
    generator.speaker_context = speaker_ctx

    logger.info(f"🎨 Generating presentation: {len(script)} slides")
    logger.info(f"   Speaker: {speaker_ctx.name} ({speaker_ctx.identity_id})")

    # LEVEL 1: Plan presentation (speaker-aware)
    logger.info("  [1/3] Planning presentation theme...")
    plan = await generator.plan_presentation(script, speaker, theme)

    # LEVEL 2: Design each slide (with batching, speaker-aware)
    logger.info("  [2/3] Designing individual slides...")
    designs: list[SlideContentDesign] = []
    previous_layout: SlideLayoutChoice | None = None

    # Process in batches for parallelism
    semaphore = asyncio.Semaphore(max_parallel)

    async def design_with_semaphore(
        slide: dict, idx: int, prev_layout: SlideLayoutChoice | None
    ) -> SlideContentDesign:
        async with semaphore:
            return await generator.design_slide(
                slide, idx, len(script), plan, prev_layout, speaker_ctx
            )

    # Design slides sequentially to maintain layout variety
    # (can't fully parallelize due to previous_layout dependency)
    for i, slide in enumerate(script):
        content = await design_with_semaphore(slide, i, previous_layout)
        designs.append(content)
        previous_layout = content.layout

    # LEVEL 2b: Design columns for multi-column layouts
    for i, content in enumerate(designs):
        if content.layout in [SlideLayoutChoice.TWO_COLUMN, SlideLayoutChoice.THREE_COLUMN]:
            num_cols = 2 if content.layout == SlideLayoutChoice.TWO_COLUMN else 3
            columns = await generator.design_columns(script[i], plan, num_cols)
            # Store columns in content (we'll use them in conversion)
            content._columns = columns  # type: ignore

    # LEVEL 3: Generate image prompts (parallel, speaker-aware)
    if generate_images:
        logger.info("  [3/3] Generating hero image prompts...")

        async def enhance_image_prompt(content: SlideContentDesign) -> None:
            if content.layout in [
                SlideLayoutChoice.HERO_FULL,
                SlideLayoutChoice.HERO_LEFT,
                SlideLayoutChoice.HERO_RIGHT,
            ]:
                async with semaphore:
                    content.hero_image_prompt = await generator.generate_image_prompt(
                        content, plan, speaker_ctx
                    )

        await asyncio.gather(*[enhance_image_prompt(c) for c in designs])
    else:
        logger.info("  [3/3] Skipping image prompts (generate_images=False)")

    # Convert to SlideDesign objects
    logger.info("  Converting to SlideDesign objects...")
    slide_designs = []
    for content in designs:
        columns = getattr(content, "_columns", None)
        design = generator.content_to_design(content, plan, columns)
        slide_designs.append(design)

    logger.info(f"✓ Generated {len(slide_designs)} LLM-designed slides for {speaker_ctx.name}")
    return slide_designs


def list_available_speakers() -> list[str]:
    """List all available speaker identities.

    Returns:
        List of identity_ids from assets/characters/
    """
    try:
        from kagami_studio.characters import list_characters

        return list_characters()
    except ImportError:
        return ["tim", "andy", "presenter"]


__all__ = [
    "ColumnContent",
    "LLMSlideGenerator",
    "PresentationPlan",
    "SlideContentDesign",
    "SlideLayoutChoice",
    "SpeakerContext",
    "VisualStyle",
    "generate_presentation",
    "list_available_speakers",
    "load_speaker_context",
]
