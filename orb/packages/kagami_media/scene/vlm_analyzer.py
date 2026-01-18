"""VLM-Enhanced Scene Analysis.

Uses Vision-Language Models (GPT-4 Vision, Jina-VLM) to extract:
- Detailed lighting conditions (direction, color temperature, intensity)
- Material properties visible in scene
- Environmental context
- Specular/reflection characteristics
- Fire/flame analysis
- Depth of field characteristics

This module provides the intelligent "art direction" layer that
analyzes real photos and generates conditioning data for matching
synthetic images.

Colony: Grove (e₆) × Crystal (e₇) — Research meets verification

Usage:
    from kagami_media.scene import VLMSceneAnalyzer

    analyzer = VLMSceneAnalyzer()
    await analyzer.initialize()

    # Analyze a reference image
    analysis = await analyzer.analyze_image("photo.jpg")

    # Generate conditioning prompt for matching image generation
    prompt = analyzer.build_conditioning_prompt(analysis, style="pixar")
"""

from __future__ import annotations

import base64
import json
import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class LightingType(Enum):
    """Types of lighting in a scene."""

    NATURAL_DAYLIGHT = "natural_daylight"
    WARM_TUNGSTEN = "warm_tungsten"
    COOL_FLUORESCENT = "cool_fluorescent"
    MIXED = "mixed"
    FIRELIGHT = "firelight"
    NEON = "neon"
    CANDLELIGHT = "candlelight"
    GOLDEN_HOUR = "golden_hour"
    OVERCAST = "overcast"
    STUDIO = "studio"


class ConditioningStrength(Enum):
    """How strongly to match the reference scene.

    Use these presets or pass a float 0.0-1.0 directly.
    """

    # Exact match - every lighting detail must match precisely
    EXACT = 1.0

    # Strong match (DEFAULT) - lighting direction, color temp, fire all match
    STRONG = 0.85

    # Balanced - overall mood matches, some artistic freedom
    BALANCED = 0.6

    # Loose - general atmosphere, creative interpretation allowed
    LOOSE = 0.4

    # Artistic - inspired by, not constrained by
    ARTISTIC = 0.2


class MaterialCategory(Enum):
    """Material categories for acoustic/visual properties."""

    WOOD = "wood"
    METAL = "metal"
    GLASS = "glass"
    FABRIC = "fabric"
    SKIN = "skin"
    FIRE = "fire"
    WATER = "water"
    STONE = "stone"
    BRICK = "brick"
    PLASTIC = "plastic"
    LEATHER = "leather"
    FOLIAGE = "foliage"


@dataclass
class LightSource:
    """A light source in the scene."""

    name: str
    direction: str  # "left", "right", "above", "below", "front", "behind"
    color_temp_kelvin: int  # Color temperature
    intensity: float  # 0-1 relative intensity
    type: LightingType
    is_practical: bool = False  # Is this an in-scene light (candle, fire, neon)?
    position_description: str = ""  # Natural language position

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "direction": self.direction,
            "color_temp_kelvin": self.color_temp_kelvin,
            "intensity": self.intensity,
            "type": self.type.value,
            "is_practical": self.is_practical,
            "position_description": self.position_description,
        }


@dataclass
class MaterialInfo:
    """Material detected in scene with visual properties."""

    category: MaterialCategory
    description: str
    location: str  # Where in the frame
    has_specular: bool = False
    roughness: float = 0.5  # 0=mirror, 1=matte

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "description": self.description,
            "location": self.location,
            "has_specular": self.has_specular,
            "roughness": self.roughness,
        }


@dataclass
class FireAnalysis:
    """Analysis of fire/flame in scene."""

    present: bool = False
    color_primary: str = "orange"  # "orange", "yellow", "blue", "white"
    color_secondary: str = "yellow"
    intensity: float = 0.0  # 0-1
    position: str = ""  # "foreground", "background", "left", "right"
    type: str = ""  # "campfire", "candle", "fireplace", "bonfire"
    casting_light: bool = False  # Is it a significant light source?

    def to_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "color_primary": self.color_primary,
            "color_secondary": self.color_secondary,
            "intensity": self.intensity,
            "position": self.position,
            "type": self.type,
            "casting_light": self.casting_light,
        }


@dataclass
class VLMSceneAnalysis:
    """Complete VLM-extracted scene analysis."""

    # Source
    source_path: str | None = None

    # Lighting
    primary_light: LightSource | None = None
    secondary_lights: list[LightSource] = field(default_factory=list)
    ambient_color: tuple[float, float, float] = (0.1, 0.1, 0.12)
    overall_warmth: float = 0.5  # 0=cool, 1=warm

    # Materials
    materials: list[MaterialInfo] = field(default_factory=list)

    # Fire/flame
    fire: FireAnalysis = field(default_factory=FireAnalysis)

    # Specular/reflections
    has_specular_highlights: bool = False
    specular_surfaces: list[str] = field(default_factory=list)
    has_bokeh: bool = False

    # Depth of field
    depth_of_field: str = "medium"  # "shallow", "medium", "deep"
    focus_distance: str = "medium"  # "close", "medium", "far"

    # Environment
    environment_type: str = "unknown"  # "indoor", "outdoor"
    location_type: str = "unknown"  # "home", "office", "restaurant", etc.
    environment_description: str = ""

    # Mood/atmosphere
    mood: str = ""
    time_of_day: str = "unknown"

    # Color grading
    contrast: float = 0.5  # 0=flat, 1=high
    saturation: float = 0.5  # 0=desaturated, 1=vivid

    # Raw VLM response (for debugging)
    raw_vlm_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "primary_light": self.primary_light.to_dict() if self.primary_light else None,
            "secondary_lights": [l.to_dict() for l in self.secondary_lights],
            "ambient_color": self.ambient_color,
            "overall_warmth": self.overall_warmth,
            "materials": [m.to_dict() for m in self.materials],
            "fire": self.fire.to_dict(),
            "has_specular_highlights": self.has_specular_highlights,
            "specular_surfaces": self.specular_surfaces,
            "has_bokeh": self.has_bokeh,
            "depth_of_field": self.depth_of_field,
            "focus_distance": self.focus_distance,
            "environment_type": self.environment_type,
            "location_type": self.location_type,
            "environment_description": self.environment_description,
            "mood": self.mood,
            "time_of_day": self.time_of_day,
            "contrast": self.contrast,
            "saturation": self.saturation,
        }


# =============================================================================
# VLM SCENE ANALYZER
# =============================================================================


# Scene analysis prompt for VLM
SCENE_ANALYSIS_PROMPT = """Analyze this image for cinematography and lighting reproduction.

Return a JSON object with EXACTLY this structure:
{
    "lighting": {
        "primary": {
            "direction": "left|right|above|below|front|behind",
            "type": "natural_daylight|warm_tungsten|cool_fluorescent|firelight|candlelight|neon|golden_hour|overcast|studio|mixed",
            "color_temp_kelvin": 2000-10000,
            "intensity": 0.0-1.0,
            "is_practical": true/false,
            "position_description": "natural language description"
        },
        "secondary": [
            {
                "direction": "...",
                "type": "...",
                "color_temp_kelvin": ...,
                "intensity": ...,
                "is_practical": true/false,
                "position_description": "..."
            }
        ],
        "ambient_warmth": 0.0-1.0
    },
    "fire": {
        "present": true/false,
        "color_primary": "orange|yellow|blue|white",
        "color_secondary": "...",
        "intensity": 0.0-1.0,
        "position": "foreground|background|left|right|center",
        "type": "campfire|candle|fireplace|bonfire|none",
        "casting_light": true/false
    },
    "materials": [
        {
            "category": "wood|metal|glass|fabric|skin|fire|water|stone|brick|plastic|leather|foliage",
            "description": "what it is",
            "location": "where in frame",
            "has_specular": true/false,
            "roughness": 0.0-1.0
        }
    ],
    "specular": {
        "has_highlights": true/false,
        "surfaces": ["list of surfaces with specular highlights"]
    },
    "depth_of_field": "shallow|medium|deep",
    "has_bokeh": true/false,
    "environment": {
        "type": "indoor|outdoor",
        "location": "home|office|restaurant|cafe|park|street|studio|other",
        "description": "detailed description of environment"
    },
    "mood": "warm|cold|neutral|dramatic|intimate|energetic",
    "time_of_day": "morning|afternoon|evening|night|unknown",
    "color_grading": {
        "contrast": 0.0-1.0,
        "saturation": 0.0-1.0
    }
}

Be precise about lighting direction and color temperature.
Focus on what would be needed to REPRODUCE this lighting in a generated image."""


class VLMSceneAnalyzer:
    """VLM-enhanced scene analyzer.

    Uses GPT-4 Vision or Jina-VLM to extract detailed scene information
    for conditioning image generation.
    """

    def __init__(
        self,
        backend: str = "openai",  # "openai" or "jina"
        model: str = "gpt-4o",
    ):
        """Initialize the VLM scene analyzer.

        Args:
            backend: "openai" for GPT-4 Vision, "jina" for local Jina-VLM
            model: Model name (for OpenAI backend)
        """
        self.backend = backend
        self.model = model
        self._jina_vlm = None
        self._openai_key: str | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the analyzer."""
        if self._initialized:
            return

        if self.backend == "openai":
            # Try keychain first, then .env
            try:
                result = subprocess.run(
                    [
                        "security",
                        "find-generic-password",
                        "-s",
                        "kagami",
                        "-a",
                        "openai_api_key",
                        "-w",
                    ],
                    capture_output=True,
                    text=True,
                )
                self._openai_key = result.stdout.strip()
            except Exception:
                pass

            if not self._openai_key:
                # Try .env
                env_path = Path("/Users/schizodactyl/projects/kagami/.env")
                if env_path.exists():
                    with open(env_path) as f:
                        for line in f:
                            if line.startswith("OPENAI_API_KEY="):
                                self._openai_key = line.strip().split("=", 1)[1]
                                break

            if not self._openai_key:
                raise ValueError("OpenAI API key not found in keychain or .env")

            logger.info("✅ VLMSceneAnalyzer initialized (OpenAI backend)")

        elif self.backend == "jina":
            from kagami.core.multimodal.vision import JinaVLM

            self._jina_vlm = JinaVLM()
            await self._jina_vlm.initialize()
            logger.info("✅ VLMSceneAnalyzer initialized (Jina-VLM backend)")

        self._initialized = True

    async def analyze_image(
        self,
        image: str | Path | Image.Image | np.ndarray,
    ) -> VLMSceneAnalysis:
        """Analyze an image and extract scene conditioning data.

        Args:
            image: Path to image, PIL Image, or numpy array

        Returns:
            VLMSceneAnalysis with extracted data
        """
        if not self._initialized:
            await self.initialize()

        # Convert to base64 if needed
        if isinstance(image, (str, Path)):
            image_path = Path(image)
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode()
            source_path = str(image_path)
        elif isinstance(image, Image.Image):
            import io

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            image_b64 = base64.b64encode(buffer.getvalue()).decode()
            source_path = None
        elif isinstance(image, np.ndarray):
            import io

            from PIL import Image as PILImage

            pil_img = PILImage.fromarray(image)
            buffer = io.BytesIO()
            pil_img.save(buffer, format="PNG")
            image_b64 = base64.b64encode(buffer.getvalue()).decode()
            source_path = None
        else:
            raise TypeError(f"Unsupported image type: {type(image)}")

        # Call VLM
        if self.backend == "openai":
            raw_response = await self._analyze_openai(image_b64)
        else:
            raw_response = await self._analyze_jina(image_b64)

        # Parse response
        analysis = self._parse_vlm_response(raw_response)
        analysis.source_path = source_path
        analysis.raw_vlm_response = raw_response

        return analysis

    async def _analyze_openai(self, image_b64: str) -> str:
        """Analyze using OpenAI GPT-4 Vision."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": SCENE_ANALYSIS_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_b64}",
                                        "detail": "high",
                                    },
                                },
                            ],
                        }
                    ],
                    "max_tokens": 2000,
                },
            )

            if response.status_code != 200:
                raise RuntimeError(f"OpenAI API error: {response.text}")

            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def _analyze_jina(self, image_b64: str) -> str:
        """Analyze using local Jina-VLM."""
        import io

        from PIL import Image as PILImage

        # Decode image
        image_bytes = base64.b64decode(image_b64)
        image = PILImage.open(io.BytesIO(image_bytes))

        # Use Jina-VLM
        return self._jina_vlm.answer(image, SCENE_ANALYSIS_PROMPT)

    def _parse_vlm_response(self, response: str) -> VLMSceneAnalysis:
        """Parse VLM JSON response into structured data."""
        # Extract JSON from response (may have markdown code blocks)
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]

        try:
            data = json.loads(json_str.strip())
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse VLM response as JSON: {response[:200]}")
            return VLMSceneAnalysis()

        analysis = VLMSceneAnalysis()

        # Parse lighting
        if "lighting" in data:
            lighting = data["lighting"]

            # Primary light
            if "primary" in lighting:
                p = lighting["primary"]
                analysis.primary_light = LightSource(
                    name="primary",
                    direction=p.get("direction", "front"),
                    color_temp_kelvin=int(p.get("color_temp_kelvin", 5500)),
                    intensity=float(p.get("intensity", 0.7)),
                    type=LightingType(p.get("type", "natural_daylight")),
                    is_practical=p.get("is_practical", False),
                    position_description=p.get("position_description", ""),
                )

            # Secondary lights
            for i, s in enumerate(lighting.get("secondary", [])):
                analysis.secondary_lights.append(
                    LightSource(
                        name=f"secondary_{i}",
                        direction=s.get("direction", "ambient"),
                        color_temp_kelvin=int(s.get("color_temp_kelvin", 5500)),
                        intensity=float(s.get("intensity", 0.3)),
                        type=LightingType(s.get("type", "natural_daylight")),
                        is_practical=s.get("is_practical", False),
                        position_description=s.get("position_description", ""),
                    )
                )

            analysis.overall_warmth = float(lighting.get("ambient_warmth", 0.5))

        # Parse fire
        if "fire" in data:
            f = data["fire"]
            analysis.fire = FireAnalysis(
                present=f.get("present", False),
                color_primary=f.get("color_primary", "orange"),
                color_secondary=f.get("color_secondary", "yellow"),
                intensity=float(f.get("intensity", 0.0)),
                position=f.get("position", ""),
                type=f.get("type", ""),
                casting_light=f.get("casting_light", False),
            )

        # Parse materials
        for m in data.get("materials", []):
            try:
                analysis.materials.append(
                    MaterialInfo(
                        category=MaterialCategory(m.get("category", "plastic")),
                        description=m.get("description", ""),
                        location=m.get("location", ""),
                        has_specular=m.get("has_specular", False),
                        roughness=float(m.get("roughness", 0.5)),
                    )
                )
            except ValueError:
                pass  # Skip invalid material categories

        # Parse specular
        if "specular" in data:
            spec = data["specular"]
            analysis.has_specular_highlights = spec.get("has_highlights", False)
            analysis.specular_surfaces = spec.get("surfaces", [])

        # Parse other fields
        analysis.depth_of_field = data.get("depth_of_field", "medium")
        analysis.has_bokeh = data.get("has_bokeh", False)

        if "environment" in data:
            env = data["environment"]
            analysis.environment_type = env.get("type", "unknown")
            analysis.location_type = env.get("location", "unknown")
            analysis.environment_description = env.get("description", "")

        analysis.mood = data.get("mood", "neutral")
        analysis.time_of_day = data.get("time_of_day", "unknown")

        if "color_grading" in data:
            cg = data["color_grading"]
            analysis.contrast = float(cg.get("contrast", 0.5))
            analysis.saturation = float(cg.get("saturation", 0.5))

        return analysis

    def build_conditioning_prompt(
        self,
        analysis: VLMSceneAnalysis,
        character_description: str,
        style: str = "photorealistic",
        strength: float | ConditioningStrength = ConditioningStrength.STRONG,
    ) -> str:
        """Build an image generation prompt conditioned on the scene analysis.

        Args:
            analysis: VLMSceneAnalysis from analyze_image()
            character_description: Description of the character to generate
            style: Visual style ("pixar", "photorealistic", "ghibli", etc.)
            strength: How strongly to match reference (0.0-1.0 or ConditioningStrength)
                - EXACT (1.0): Every lighting detail must match precisely
                - STRONG (0.85): Default, lighting direction/color/fire all match
                - BALANCED (0.6): Overall mood matches, some artistic freedom
                - LOOSE (0.4): General atmosphere, creative interpretation
                - ARTISTIC (0.2): Inspired by, not constrained by

        Returns:
            Complete prompt for image generation
        """
        # Normalize strength to float
        if isinstance(strength, ConditioningStrength):
            strength_value = strength.value
        else:
            strength_value = float(strength)

        # Style prefix
        style_prefix = self._get_style_prefix(style, strength_value)

        # Build sections based on strength
        if strength_value >= 0.8:
            # EXACT/STRONG: Full technical precision
            prompt = self._build_exact_prompt(analysis, character_description, style_prefix)
        elif strength_value >= 0.5:
            # BALANCED: Good detail, some flexibility
            prompt = self._build_balanced_prompt(analysis, character_description, style_prefix)
        else:
            # LOOSE/ARTISTIC: Mood-based
            prompt = self._build_artistic_prompt(analysis, character_description, style_prefix)

        return prompt.strip()

    def _build_exact_prompt(
        self,
        analysis: VLMSceneAnalysis,
        character_description: str,
        style_prefix: str,
    ) -> str:
        """Build highly precise prompt for exact scene matching."""
        # Precise lighting with exact values
        lighting_block = self._describe_lighting_exact(analysis)

        # Fire with exact colors
        fire_block = ""
        if analysis.fire.present:
            fire_block = self._describe_fire_exact(analysis.fire)

        # Material reflections
        material_block = self._describe_materials_exact(analysis)

        # Technical precision
        tech_block = self._describe_technical_exact(analysis)

        return f"""{style_prefix}

═══════════════════════════════════════════════════════════════════════════════
CHARACTER (preserve these features exactly):
═══════════════════════════════════════════════════════════════════════════════
{character_description}

═══════════════════════════════════════════════════════════════════════════════
LIGHTING (CRITICAL — match EXACTLY as specified):
═══════════════════════════════════════════════════════════════════════════════
{lighting_block}
{fire_block}

═══════════════════════════════════════════════════════════════════════════════
ENVIRONMENT & ATMOSPHERE:
═══════════════════════════════════════════════════════════════════════════════
Setting: {analysis.environment_description or f"{analysis.environment_type} {analysis.location_type}"}
Mood: {analysis.mood}
Time: {analysis.time_of_day}

{material_block}

═══════════════════════════════════════════════════════════════════════════════
TECHNICAL REQUIREMENTS (must match):
═══════════════════════════════════════════════════════════════════════════════
{tech_block}

CRITICAL: The lighting on the character's face and body MUST match the exact
direction and color temperature specified above. This is non-negotiable."""

    def _build_balanced_prompt(
        self,
        analysis: VLMSceneAnalysis,
        character_description: str,
        style_prefix: str,
    ) -> str:
        """Build balanced prompt with good detail but some flexibility."""
        lighting_desc = self._describe_lighting(analysis)
        fire_desc = self._describe_fire(analysis.fire) if analysis.fire.present else ""

        warmth = self._warmth_to_words(analysis.overall_warmth)

        return f"""{style_prefix}

CHARACTER:
{character_description}

LIGHTING:
{lighting_desc}
{fire_desc}

ENVIRONMENT:
{analysis.environment_description}
Mood: {analysis.mood}

TECHNICAL:
- Overall warmth: {warmth}
- Depth of field: {analysis.depth_of_field}
- High quality cinematic render
- Lighting direction should generally match the description above"""

    def _build_artistic_prompt(
        self,
        analysis: VLMSceneAnalysis,
        character_description: str,
        style_prefix: str,
    ) -> str:
        """Build loose, mood-based prompt for artistic interpretation."""
        warmth = self._warmth_to_words(analysis.overall_warmth)

        return f"""{style_prefix}

CHARACTER:
{character_description}

ATMOSPHERE:
- {analysis.mood} mood
- {warmth} color palette
- {analysis.environment_type} setting
{"- Warm firelight glow" if analysis.fire.present else ""}

High quality render with cinematic feel."""

    def _describe_lighting_exact(self, analysis: VLMSceneAnalysis) -> str:
        """Generate precise lighting description with exact values."""
        if not analysis.primary_light:
            return "Soft ambient lighting from all directions."

        p = analysis.primary_light
        lines = []

        # Primary light with exact specs
        lines.append("PRIMARY LIGHT:")
        lines.append(f"  • Direction: {p.direction.upper()}")
        lines.append(
            f"  • Color Temperature: {p.color_temp_kelvin}K ({self._kelvin_to_words(p.color_temp_kelvin)})"
        )
        lines.append(f"  • Intensity: {int(p.intensity * 100)}%")
        lines.append(f"  • Type: {p.type.value.replace('_', ' ').title()}")
        if p.position_description:
            lines.append(f"  • Position: {p.position_description}")

        # Secondary lights
        for i, s in enumerate(analysis.secondary_lights[:3]):
            lines.append(f"\nSECONDARY LIGHT {i + 1}:")
            lines.append(f"  • Direction: {s.direction}")
            lines.append(f"  • Color Temperature: {s.color_temp_kelvin}K")
            lines.append(f"  • Intensity: {int(s.intensity * 100)}%")

        # Ambient
        lines.append("\nAMBIENT:")
        lines.append(f"  • Overall warmth: {int(analysis.overall_warmth * 100)}% warm")

        return "\n".join(lines)

    def _describe_fire_exact(self, fire: FireAnalysis) -> str:
        """Generate precise fire description."""
        lines = ["\nFIRE/FLAME LIGHTING:"]
        lines.append(f"  • Type: {fire.type}")
        lines.append(f"  • Position in frame: {fire.position}")
        lines.append(f"  • Primary flame color: {fire.color_primary}")
        lines.append(f"  • Secondary flame color: {fire.color_secondary}")
        lines.append(f"  • Intensity: {int(fire.intensity * 100)}%")

        if fire.casting_light:
            lines.append(
                f"  • CRITICAL: Fire is casting warm {fire.color_primary} light on subject"
            )
            lines.append("    - Creates warm highlights on skin facing the fire")
            lines.append("    - Creates orange-yellow rim lighting on hair/clothing")
            lines.append("    - Subsurface scattering in skin shows warm glow")

        return "\n".join(lines)

    def _describe_materials_exact(self, analysis: VLMSceneAnalysis) -> str:
        """Generate material/reflection details."""
        if not analysis.materials and not analysis.has_specular_highlights:
            return ""

        lines = ["MATERIAL PROPERTIES:"]

        if analysis.has_specular_highlights:
            surfaces = ", ".join(analysis.specular_surfaces[:5])
            lines.append(f"  • Specular highlights visible on: {surfaces}")

        for m in analysis.materials[:4]:
            roughness_desc = (
                "glossy" if m.roughness < 0.3 else "satin" if m.roughness < 0.6 else "matte"
            )
            lines.append(f"  • {m.category.value.title()}: {m.description} ({roughness_desc})")

        if analysis.has_bokeh:
            lines.append("  • Background bokeh light points visible")

        return "\n".join(lines)

    def _describe_technical_exact(self, analysis: VLMSceneAnalysis) -> str:
        """Generate technical specifications."""
        lines = []

        # Color grading
        contrast = (
            "high" if analysis.contrast > 0.6 else "medium" if analysis.contrast > 0.4 else "low"
        )
        saturation = (
            "vivid"
            if analysis.saturation > 0.6
            else "natural"
            if analysis.saturation > 0.4
            else "muted"
        )
        lines.append(f"• Contrast: {contrast}")
        lines.append(f"• Saturation: {saturation}")

        # DOF
        dof_desc = {
            "shallow": "Shallow DOF — background softly blurred, subject tack sharp",
            "medium": "Medium DOF — slight background softness",
            "deep": "Deep DOF — most of scene in focus",
        }.get(analysis.depth_of_field, "")
        lines.append(f"• {dof_desc}")

        # Quality
        lines.append("• Render at highest quality")
        lines.append("• Cinematic color grading")

        return "\n".join(lines)

    def _describe_lighting(self, analysis: VLMSceneAnalysis) -> str:
        """Generate natural language lighting description."""
        if not analysis.primary_light:
            return "Natural ambient lighting."

        p = analysis.primary_light
        temp_desc = self._kelvin_to_words(p.color_temp_kelvin)
        intensity_desc = (
            "soft" if p.intensity < 0.4 else "moderate" if p.intensity < 0.7 else "strong"
        )

        desc = f"Primary: {intensity_desc} {temp_desc} light from {p.direction}"
        if p.position_description:
            desc += f" ({p.position_description})"
        desc += ".\n"

        for s in analysis.secondary_lights[:2]:
            s_temp = self._kelvin_to_words(s.color_temp_kelvin)
            s_intensity = (
                "soft" if s.intensity < 0.4 else "moderate" if s.intensity < 0.7 else "strong"
            )
            desc += f"Secondary: {s_intensity} {s_temp} light from {s.direction}.\n"

        return desc

    def _describe_fire(self, fire: FireAnalysis) -> str:
        """Generate fire lighting description."""
        if not fire.present:
            return ""

        intensity = (
            "subtle" if fire.intensity < 0.4 else "moderate" if fire.intensity < 0.7 else "strong"
        )
        color = f"{fire.color_primary}-{fire.color_secondary}"

        desc = f"{intensity.title()} {color} {fire.type} fire in {fire.position}. "
        if fire.casting_light:
            desc += "Fire is casting warm light on the subject, creating orange highlights on skin and warm rim lighting. "

        return desc

    def _warmth_to_words(self, warmth: float) -> str:
        """Convert warmth value to natural description."""
        if warmth > 0.8:
            return "very warm golden"
        elif warmth > 0.6:
            return "warm"
        elif warmth > 0.4:
            return "neutral"
        elif warmth > 0.2:
            return "cool"
        else:
            return "very cool blue"

    def _get_style_prefix(self, style: str, strength: float = 0.85) -> str:
        """Get style-specific prompt prefix with strength-appropriate instructions."""

        # Base style descriptions
        base_styles = {
            "pixar": """🎬 PIXAR/DISNEY 3D ANIMATED CHARACTER

STYLE REQUIREMENTS:
• Big expressive eyes with that signature Pixar sparkle and catchlights
• Smooth, stylized 3D rendered skin with subtle subsurface scattering
• Slightly exaggerated but charming facial proportions
• High quality 3D render matching the visual fidelity of recent Pixar films
• Clean, appealing character design with clear silhouette""",
            "photorealistic": """📷 PHOTOREALISTIC CINEMATIC PORTRAIT

STYLE REQUIREMENTS:
• Hyper-detailed skin texture with pores, fine lines, and natural imperfections
• Accurate eye reflections showing environment
• Natural subsurface scattering in skin (especially ears, nose, fingers)
• Cinema-quality lighting with proper falloff
• Shot on high-end cinema camera, shallow depth of field""",
            "ghibli": """🎨 STUDIO GHIBLI ANIME STYLE

STYLE REQUIREMENTS:
• Soft, hand-painted aesthetic with visible brushwork feeling
• Large expressive eyes with emotion
• Gentle pastel color palette with watercolor-like gradients
• Dreamlike, atmospheric quality with soft edges
• Character feels warm and approachable""",
            "comic": """💥 STYLIZED COMIC BOOK ART

STYLE REQUIREMENTS:
• Bold ink lines and dramatic shadows
• Simplified but highly expressive features
• Strong color blocks with halftone shading
• Dynamic visual hierarchy and composition
• Clear graphic novel aesthetic""",
            "anime": """🌸 MODERN ANIME STYLE

STYLE REQUIREMENTS:
• Clean line art with smooth coloring
• Large detailed eyes with highlight reflections
• Stylized but proportionate features
• Vibrant colors with cel-shading
• High quality digital anime illustration""",
        }

        base = base_styles.get(style, base_styles["photorealistic"])

        # Add strength-specific instructions
        if strength >= 0.8:
            base += """

⚠️ CRITICAL INSTRUCTIONS:
• The character's features described below MUST be preserved exactly
• The lighting MUST match the exact specifications provided
• Do NOT add creative interpretations that deviate from the description
• Every detail matters — this is a precise reconstruction"""
        elif strength >= 0.5:
            base += """

📋 GUIDELINES:
• Preserve the key character features described
• Match the general lighting direction and mood
• Some artistic interpretation is acceptable"""

        return base

    def _describe_lighting(self, analysis: VLMSceneAnalysis) -> str:
        """Generate natural language lighting description."""
        if not analysis.primary_light:
            return "Natural ambient lighting."

        p = analysis.primary_light
        temp_desc = self._kelvin_to_words(p.color_temp_kelvin)
        intensity_desc = (
            "soft" if p.intensity < 0.4 else "moderate" if p.intensity < 0.7 else "strong"
        )

        desc = f"Primary: {intensity_desc} {temp_desc} light from {p.direction}"
        if p.position_description:
            desc += f" ({p.position_description})"
        desc += ".\n"

        for s in analysis.secondary_lights[:2]:
            s_temp = self._kelvin_to_words(s.color_temp_kelvin)
            s_intensity = (
                "soft" if s.intensity < 0.4 else "moderate" if s.intensity < 0.7 else "strong"
            )
            desc += f"Secondary: {s_intensity} {s_temp} light from {s.direction}.\n"

        return desc

    def _describe_fire(self, fire: FireAnalysis) -> str:
        """Generate fire lighting description."""
        if not fire.present:
            return ""

        intensity = (
            "subtle" if fire.intensity < 0.4 else "moderate" if fire.intensity < 0.7 else "strong"
        )
        color = f"{fire.color_primary}-{fire.color_secondary}"

        desc = f"{intensity.title()} {color} {fire.type} fire in {fire.position}. "
        if fire.casting_light:
            desc += "Fire is casting warm light on the subject, creating orange highlights on skin and warm rim lighting. "

        return desc

    @staticmethod
    def _kelvin_to_words(kelvin: int) -> str:
        """Convert color temperature to natural description."""
        if kelvin < 2000:
            return "very warm candlelight orange"
        elif kelvin < 2500:
            return "warm golden firelight"
        elif kelvin < 3500:
            return "warm tungsten yellow-orange"
        elif kelvin < 5000:
            return "neutral warm"
        elif kelvin < 6500:
            return "neutral daylight"
        else:
            return "cool blue"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


_shared_analyzer: VLMSceneAnalyzer | None = None


async def get_scene_analyzer(backend: str = "openai") -> VLMSceneAnalyzer:
    """Get shared VLM scene analyzer instance.

    Args:
        backend: "openai" or "jina"

    Returns:
        Initialized VLMSceneAnalyzer
    """
    global _shared_analyzer
    if _shared_analyzer is None or _shared_analyzer.backend != backend:
        _shared_analyzer = VLMSceneAnalyzer(backend=backend)
        await _shared_analyzer.initialize()
    return _shared_analyzer


async def analyze_scene_vlm(
    image: str | Path | Image.Image | np.ndarray,
    backend: str = "openai",
) -> VLMSceneAnalysis:
    """Convenience function to analyze a scene with VLM.

    Args:
        image: Image to analyze
        backend: "openai" or "jina"

    Returns:
        VLMSceneAnalysis
    """
    analyzer = await get_scene_analyzer(backend)
    return await analyzer.analyze_image(image)


__all__ = [
    # Enums
    "ConditioningStrength",
    # Data classes
    "FireAnalysis",
    "LightSource",
    "LightingType",
    "MaterialCategory",
    "MaterialInfo",
    "VLMSceneAnalysis",
    # Main class
    "VLMSceneAnalyzer",
    # Convenience functions
    "analyze_scene_vlm",
    "get_scene_analyzer",
]
