"""Shot Planner — LLM-Powered Cinematography for Any Speaker.

Plans multi-shot video production with visual consistency:
1. Analyzes script narrative arc
2. Plans shot sequence (coverage, pacing, variety)
3. Generates character-consistent visual prompts
4. Maintains style coherence across all shots

Speaker Integration:
- Loads character from assets/characters/*/metadata.json
- Uses character physical description for visual prompts
- Adapts shot styles to speaker personality
- Maintains visual consistency via seed prompts

Usage:
    from kagami_studio.production.shot_planner import (
        ShotPlanner,
        plan_production,
        ProductionPlan,
    )

    # Quick path
    plan = await plan_production(
        script=[{"title": "Welcome", "spoken": "..."}],
        speaker="tim",
    )

    # Access planned shots
    for shot in plan.shots:
        print(f"{shot.type}: {shot.visual_seed[:50]}...")

    # Generate with planned shots
    from kagami_studio.production import produce_video
    result = await produce_video(
        script=script,
        speaker="tim",
        shot_plan=plan,  # Use planned shots
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from kagami_studio.composition.shot import CameraAngle, Shot, ShotType
from kagami_studio.production.llm_slide_generator import (
    SpeakerContext,
    load_speaker_context,
)

if TYPE_CHECKING:
    from kagami_studio.characters import Character

logger = logging.getLogger(__name__)


# === VISUAL CONSISTENCY SYSTEM ===


@dataclass
class VisualSeed:
    """Visual consistency seed for a character.

    Generated once, used across all shots to maintain
    character appearance consistency.
    """

    character_id: str
    character_name: str

    # Physical description (from metadata)
    physical_description: str = ""

    # Generated style prompts
    appearance_prompt: str = ""  # Detailed appearance for image generation
    environment_style: str = ""  # Typical environment/setting
    lighting_style: str = ""  # Preferred lighting
    color_palette: str = ""  # Associated colors

    # Motion/expression baseline
    default_expression: str = ""
    default_posture: str = ""

    @classmethod
    def from_character(cls, char: Character) -> VisualSeed:
        """Build visual seed from Character metadata."""
        # Extract physical description
        phys = char.metadata.get("physical_description", {})
        if isinstance(phys, dict):
            parts = []
            if phys.get("hair"):
                parts.append(f"hair: {phys['hair']}")
            if phys.get("eyes"):
                parts.append(f"eyes: {phys['eyes']}")
            if phys.get("build"):
                parts.append(f"build: {phys['build']}")
            if phys.get("distinguishing_features"):
                features = phys["distinguishing_features"]
                if isinstance(features, list):
                    parts.append(f"features: {', '.join(features)}")
            physical_description = "; ".join(parts)
        else:
            physical_description = str(phys) if phys else ""

        # Extract visual description if available
        vis = char.metadata.get("visual_description", {})
        if isinstance(vis, dict):
            appearance_parts = []
            if vis.get("hair"):
                appearance_parts.append(f"{vis['hair']} hair")
            if vis.get("build"):
                appearance_parts.append(f"{vis['build']} build")
            if vis.get("style"):
                appearance_parts.append(f"{vis['style']} style")
            if vis.get("key_features"):
                appearance_parts.append(vis["key_features"])
            appearance_prompt = ", ".join(appearance_parts)
        else:
            appearance_prompt = physical_description

        # Determine environment from role/metadata
        role = char.role.value
        if role == "household":
            environment_style = "modern home, warm lighting, comfortable"
        elif role == "external":
            # Check for specific context
            if "dcc" in (char.metadata_path.parent.name if char.metadata_path else ""):
                environment_style = "professional stadium, bright lights, performance venue"
            else:
                environment_style = "professional setting, neutral background"
        else:
            environment_style = "clean, neutral background"

        # Lighting based on typical use
        lighting_style = "soft, natural lighting"
        if char.metadata.get("interview_position"):
            lighting_style = "professional interview lighting, key light from side"

        # Color palette from metadata or defaults
        color_palette = "neutral, professional"
        if vis.get("interview_attire"):
            color_palette = f"{vis['interview_attire']}, professional"

        return cls(
            character_id=char.identity_id,
            character_name=char.name,
            physical_description=physical_description,
            appearance_prompt=appearance_prompt,
            environment_style=environment_style,
            lighting_style=lighting_style,
            color_palette=color_palette,
            default_expression="natural, confident",
            default_posture="relaxed but attentive",
        )

    def to_prompt_block(self) -> str:
        """Format as prompt block for LLM."""
        lines = [f"CHARACTER: {self.character_name}"]
        if self.appearance_prompt:
            lines.append(f"Appearance: {self.appearance_prompt}")
        if self.environment_style:
            lines.append(f"Environment: {self.environment_style}")
        if self.lighting_style:
            lines.append(f"Lighting: {self.lighting_style}")
        return "\n".join(lines)


def load_visual_seed(speaker: str | Character | None) -> VisualSeed:
    """Load visual consistency seed for a speaker.

    Args:
        speaker: Speaker name, Character object, or None

    Returns:
        VisualSeed with character visual info
    """
    if speaker is None:
        return VisualSeed(
            character_id="presenter",
            character_name="Presenter",
            appearance_prompt="professional presenter",
            environment_style="modern presentation stage",
            lighting_style="professional stage lighting",
        )

    # Already a Character object
    if hasattr(speaker, "identity_id"):
        return VisualSeed.from_character(speaker)  # type: ignore

    # Load by name
    try:
        from kagami_studio.characters import load_character

        char = load_character(str(speaker))
        if char:
            logger.debug(f"Loaded visual seed: {char.name}")
            return VisualSeed.from_character(char)
    except Exception as e:
        logger.debug(f"Could not load character '{speaker}': {e}")

    # Default
    return VisualSeed(
        character_id=str(speaker).lower().replace(" ", "_"),
        character_name=str(speaker).title(),
    )


# === PYDANTIC MODELS FOR LLM OUTPUT ===


class ShotPlan(BaseModel):
    """Single shot in production plan."""

    shot_type: str = Field(description="Shot type from ShotType enum")
    camera_angle: str = Field(default="medium", description="Camera framing")
    duration_s: float = Field(default=5.0, description="Shot duration")
    motion: str = Field(default="natural", description="Emotional motion")
    visual_prompt: str = Field(
        default="",
        description="Detailed visual description for this shot",
    )
    transition_to_next: str = Field(
        default="cut",
        description="Transition type (cut, dissolve, wipe)",
    )
    purpose: str = Field(
        default="",
        description="Why this shot exists in the sequence",
    )
    slide_index: int | None = Field(
        default=None,
        description="Associated slide index if any",
    )


class CoverageStrategy(str, Enum):
    """Shot coverage strategy."""

    TED_TALK = "ted_talk"  # Multi-camera TED style
    INTERVIEW = "interview"  # Two-person interview
    MONOLOGUE = "monologue"  # Single speaker, varied angles
    DOCUMENTARY = "documentary"  # B-roll heavy
    PRESENTATION = "presentation"  # Slides + speaker


class ProductionPlanModel(BaseModel):
    """Complete production plan from LLM."""

    coverage_strategy: str = Field(
        default="ted_talk",
        description="Overall coverage approach",
    )
    mood: str = Field(default="professional", description="Overall mood")
    pacing: str = Field(
        default="moderate",
        description="Editing pace (slow, moderate, fast)",
    )
    visual_style: str = Field(
        default="clean, modern",
        description="Visual style description",
    )
    shots: list[ShotPlan] = Field(default_factory=list)


# === PRODUCTION PLAN DATACLASS ===


@dataclass
class PlannedShot:
    """A planned shot ready for rendering.

    Combines shot definition with visual consistency info.
    """

    # Core shot info
    type: ShotType
    camera: CameraAngle
    duration_s: float
    motion: str

    # Content
    text: str | None = None
    action_prompt: str | None = None

    # Visual consistency
    visual_seed: str = ""  # Detailed visual prompt for this shot
    character_id: str | None = None

    # Metadata
    purpose: str = ""
    transition: str = "cut"
    slide_index: int | None = None

    def to_shot(self) -> Shot:
        """Convert to Shot object for rendering."""
        return Shot(
            type=self.type,
            text=self.text,
            action_prompt=self.action_prompt or self.visual_seed,
            character=self.character_id,
            camera=self.camera,
            duration_s=self.duration_s,
            motion=self.motion,
        )


@dataclass
class ProductionPlan:
    """Complete production plan with visual consistency.

    Attributes:
        speaker_context: Speaker personality/style
        visual_seed: Character visual consistency info
        shots: Planned shots in sequence
        coverage_strategy: Overall coverage approach
        mood: Production mood
        pacing: Editing pace
        visual_style: Overall visual style
    """

    speaker_context: SpeakerContext
    visual_seed: VisualSeed
    shots: list[PlannedShot] = field(default_factory=list)
    coverage_strategy: CoverageStrategy = CoverageStrategy.TED_TALK
    mood: str = "professional"
    pacing: str = "moderate"
    visual_style: str = "clean, modern"

    @property
    def total_duration_s(self) -> float:
        """Total planned duration."""
        return sum(s.duration_s for s in self.shots)

    @property
    def shot_count(self) -> int:
        """Number of planned shots."""
        return len(self.shots)

    def get_dialogue_shots(self) -> list[PlannedShot]:
        """Get all dialogue/monologue shots."""
        return [s for s in self.shots if s.type in (ShotType.DIALOGUE, ShotType.MONOLOGUE)]

    def get_broll_shots(self) -> list[PlannedShot]:
        """Get all B-roll shots."""
        return [
            s
            for s in self.shots
            if s.type
            in (
                ShotType.ACTION,
                ShotType.ESTABLISHING,
                ShotType.CUTAWAY,
                ShotType.AUDIENCE,
            )
        ]


# === SHOT PLANNER ===


@dataclass
class ShotPlanner:
    """LLM-powered shot planner with visual consistency.

    Plans cinematography for any speaker with:
    - Character-aware visual prompts
    - Consistent appearance across shots
    - Narrative-driven shot selection
    - Professional coverage patterns
    """

    llm_service: Any = None
    initialized: bool = False

    async def initialize(self) -> None:
        """Initialize LLM service."""
        if self.initialized:
            return

        from kagami.core.services.llm import get_llm_service

        self.llm_service = get_llm_service()
        await self.llm_service.initialize()
        self.initialized = True
        logger.info("✓ Shot Planner initialized")

    async def plan(
        self,
        script: list[dict[str, Any]],
        speaker: str | Character | None = None,
        coverage: CoverageStrategy = CoverageStrategy.TED_TALK,
        include_broll: bool = True,
    ) -> ProductionPlan:
        """Plan complete shot sequence for script.

        Args:
            script: List of slide/scene dictionaries
            speaker: Speaker identity (name or Character)
            coverage: Coverage strategy to use
            include_broll: Whether to include B-roll shots

        Returns:
            ProductionPlan with all shots
        """
        if not self.initialized:
            await self.initialize()

        # Load speaker context and visual seed
        speaker_ctx = load_speaker_context(speaker)
        visual_seed = load_visual_seed(speaker)

        logger.info(
            f"🎬 Planning production: {len(script)} scenes, "
            f"speaker={visual_seed.character_name}, coverage={coverage.value}"
        )

        # Build script summary for LLM
        script_summary = self._build_script_summary(script)

        # Generate shot plan
        plan_model = await self._generate_shot_plan(
            script_summary=script_summary,
            speaker_ctx=speaker_ctx,
            visual_seed=visual_seed,
            coverage=coverage,
            include_broll=include_broll,
            script_length=len(script),
        )

        # Convert to PlannedShots with visual consistency
        planned_shots = self._convert_to_planned_shots(
            plan_model=plan_model,
            script=script,
            visual_seed=visual_seed,
        )

        plan = ProductionPlan(
            speaker_context=speaker_ctx,
            visual_seed=visual_seed,
            shots=planned_shots,
            coverage_strategy=CoverageStrategy(plan_model.coverage_strategy),
            mood=plan_model.mood,
            pacing=plan_model.pacing,
            visual_style=plan_model.visual_style,
        )

        logger.info(
            f"✓ Planned {plan.shot_count} shots, {plan.total_duration_s:.1f}s total duration"
        )

        return plan

    def _build_script_summary(self, script: list[dict[str, Any]]) -> str:
        """Build compact script summary for LLM."""
        lines = []
        for i, scene in enumerate(script):
            title = scene.get("title", f"Scene {i + 1}")
            spoken = scene.get("spoken", "")[:100]
            duration = scene.get("duration", 5.0)
            mood = scene.get("mood", "neutral")
            lines.append(f"{i + 1}. [{duration}s] {title}: {spoken}... (mood: {mood})")
        return "\n".join(lines)

    async def _generate_shot_plan(
        self,
        script_summary: str,
        speaker_ctx: SpeakerContext,
        visual_seed: VisualSeed,
        coverage: CoverageStrategy,
        include_broll: bool,
        script_length: int,
    ) -> ProductionPlanModel:
        """Generate shot plan via LLM."""
        # Build prompt
        prompt = f"""You are a professional cinematographer planning shots for a video production.

SCRIPT ({script_length} scenes):
{script_summary}

SPEAKER:
{speaker_ctx.to_prompt_block()}

VISUAL REFERENCE:
{visual_seed.to_prompt_block()}

COVERAGE STRATEGY: {coverage.value}
INCLUDE B-ROLL: {include_broll}

Plan a professional shot sequence following these principles:
1. TED Talk multi-camera coverage (wide, medium, close)
2. Roger Deakins: wider lenses for context, movement only when narrative requires
3. Vary shot types to maintain visual interest
4. Match shot selection to content mood
5. Include establishing and cutaway shots for pacing (if B-roll enabled)
6. Consider speaker's personality and style

AVAILABLE SHOT TYPES:
- dialogue: Speaker talking (needs face, lip sync)
- monologue: Extended speaking
- front_wide: Full stage view
- front_medium: Waist up
- front_closeup: Face only
- audience: View of audience
- reverse: Back of speaker toward audience
- establishing: Scene-setting wide
- cutaway: B-roll detail
- slides: Full-screen presentation

CAMERA ANGLES:
- extreme_wide, wide, medium_wide, medium, medium_close, close, extreme_close
- front, three_quarter_front, profile, over_shoulder
- high_angle, low_angle

For each shot, provide:
1. Shot type and camera angle
2. Duration in seconds
3. Motion/emotion (warm, excited, serious, neutral)
4. Visual prompt describing what we see (include speaker appearance for consistency)
5. Purpose (why this shot here)
6. Transition to next

Return JSON matching this schema:
{{
    "coverage_strategy": "{coverage.value}",
    "mood": "overall mood",
    "pacing": "slow|moderate|fast",
    "visual_style": "style description",
    "shots": [
        {{
            "shot_type": "dialogue",
            "camera_angle": "medium",
            "duration_s": 5.0,
            "motion": "warm",
            "visual_prompt": "detailed description",
            "transition_to_next": "cut",
            "purpose": "why this shot",
            "slide_index": null
        }}
    ]
}}"""

        try:
            result = await self.llm_service.generate_structured(
                prompt=prompt,
                response_model=ProductionPlanModel,
                app_name="shot_planner",
                max_tokens=4000,
                temperature=0.7,
            )
            return result
        except Exception as e:
            logger.warning(f"Structured generation failed, using fallback: {e}")
            return self._fallback_plan(script_length, coverage)

    def _fallback_plan(
        self,
        script_length: int,
        coverage: CoverageStrategy,
    ) -> ProductionPlanModel:
        """Generate fallback plan without LLM."""
        shots = []

        # Opening establishing
        shots.append(
            ShotPlan(
                shot_type="establishing",
                camera_angle="extreme_wide",
                duration_s=3.0,
                motion="neutral",
                visual_prompt="Wide establishing shot of presentation venue",
                purpose="Set the scene",
                transition_to_next="dissolve",
            )
        )

        # Main dialogue shots
        for i in range(script_length):
            # Vary angles
            if i % 3 == 0:
                angle = "medium"
            elif i % 3 == 1:
                angle = "medium_close"
            else:
                angle = "close"

            shots.append(
                ShotPlan(
                    shot_type="dialogue",
                    camera_angle=angle,
                    duration_s=5.0,
                    motion="natural",
                    visual_prompt="Speaker delivering content",
                    purpose=f"Main content {i + 1}",
                    slide_index=i,
                )
            )

        return ProductionPlanModel(
            coverage_strategy=coverage.value,
            mood="professional",
            pacing="moderate",
            visual_style="clean, modern",
            shots=shots,
        )

    def _convert_to_planned_shots(
        self,
        plan_model: ProductionPlanModel,
        script: list[dict[str, Any]],
        visual_seed: VisualSeed,
    ) -> list[PlannedShot]:
        """Convert LLM plan to PlannedShot objects with visual consistency."""
        planned = []

        for shot_plan in plan_model.shots:
            # Parse shot type
            try:
                shot_type = ShotType(shot_plan.shot_type)
            except ValueError:
                shot_type = ShotType.DIALOGUE

            # Parse camera angle
            try:
                camera = CameraAngle(shot_plan.camera_angle)
            except ValueError:
                camera = CameraAngle.MEDIUM

            # Get associated script content
            slide_idx = shot_plan.slide_index
            text = None
            if slide_idx is not None and 0 <= slide_idx < len(script):
                text = script[slide_idx].get("spoken")

            # Enhance visual prompt with character consistency
            visual_prompt = self._enhance_visual_prompt(
                base_prompt=shot_plan.visual_prompt,
                visual_seed=visual_seed,
                shot_type=shot_type,
            )

            planned.append(
                PlannedShot(
                    type=shot_type,
                    camera=camera,
                    duration_s=shot_plan.duration_s,
                    motion=shot_plan.motion,
                    text=text,
                    visual_seed=visual_prompt,
                    character_id=visual_seed.character_id,
                    purpose=shot_plan.purpose,
                    transition=shot_plan.transition_to_next,
                    slide_index=slide_idx,
                )
            )

        return planned

    def _enhance_visual_prompt(
        self,
        base_prompt: str,
        visual_seed: VisualSeed,
        shot_type: ShotType,
    ) -> str:
        """Enhance visual prompt with character consistency info."""
        parts = []

        # Add base prompt
        if base_prompt:
            parts.append(base_prompt)

        # Add character appearance for consistency
        if shot_type in (ShotType.DIALOGUE, ShotType.MONOLOGUE):
            if visual_seed.appearance_prompt:
                parts.append(f"Speaker: {visual_seed.appearance_prompt}")

        # Add environment for non-closeup shots
        if shot_type in (
            ShotType.ESTABLISHING,
            ShotType.FRONT_WIDE,
            ShotType.AUDIENCE,
        ):
            if visual_seed.environment_style:
                parts.append(f"Setting: {visual_seed.environment_style}")

        # Add lighting
        if visual_seed.lighting_style:
            parts.append(f"Lighting: {visual_seed.lighting_style}")

        return "; ".join(parts)


# === CONVENIENCE FUNCTIONS ===


async def plan_production(
    script: list[dict[str, Any]],
    speaker: str | Character | None = None,
    coverage: str | CoverageStrategy = "ted_talk",
    include_broll: bool = True,
) -> ProductionPlan:
    """Plan complete video production for script.

    Convenience function for quick shot planning.

    Args:
        script: List of scene/slide dictionaries
        speaker: Speaker identity (name or Character)
        coverage: Coverage strategy ("ted_talk", "interview", "monologue", etc.)
        include_broll: Whether to include B-roll shots

    Returns:
        ProductionPlan with all shots planned

    Example:
        plan = await plan_production(
            script=my_script,
            speaker="tim",
            coverage="ted_talk",
        )

        # Use with video production
        result = await produce_video(
            script=my_script,
            speaker="tim",
            shot_plan=plan,
        )
    """
    # Parse coverage
    if isinstance(coverage, str):
        coverage = CoverageStrategy(coverage)

    planner = ShotPlanner()
    await planner.initialize()

    return await planner.plan(
        script=script,
        speaker=speaker,
        coverage=coverage,
        include_broll=include_broll,
    )


def list_coverage_strategies() -> list[str]:
    """List available coverage strategies."""
    return [s.value for s in CoverageStrategy]


__all__ = [
    "CoverageStrategy",
    "PlannedShot",
    "ProductionPlan",
    "ShotPlanner",
    "VisualSeed",
    "list_coverage_strategies",
    "load_visual_seed",
    "plan_production",
]
