"""Character visual design system powered by LLM reasoning.

This module generates comprehensive visual character profiles using
intelligent reasoning and multimodal analysis. It creates detailed
physical descriptions, style specifications, and technical implementation
guidance for 3D character creation.

Key Features:
    - Multimodal reference image analysis
    - Comprehensive visual profile generation
    - Technical specification creation
    - Implementation guidance for 3D artists
    - Style and aesthetic development
    - Visual storytelling integration

Design Process:
    1. Analyze reference images (if provided)
    2. Generate detailed visual profile
    3. Create technical specifications
    4. Provide implementation guidance

Outputs:
    - Physical characteristics and proportions
    - Style and aesthetic choices
    - Color palettes and materials
    - Technical requirements for 3D modeling
    - Step-by-step implementation guide
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

from ...forge_llm_base import CharacterAspect, CharacterContext, LLMRequest
from ...llm_service_adapter import KagamiOSLLMServiceAdapter
from ...schema import (
    BoundingBox,
    CharacterRequest,
    GenerationResult,
    Mesh,
    StylePreferences,
    Vector3,
)


@dataclass
class StyleConfig:
    """Configuration for character style preferences."""

    color_palette: str = "vibrant"
    character_proportions: str = "balanced"
    detail_level: str = "high"
    cuteness_level: str = "cute"
    emoji_compatible: bool = True
    outfit_style: str = "casual"
    size_emphasis: str = "normal"
    eye_style: str = "expressive"
    expression: str = "friendly"


logger = logging.getLogger(__name__)


class CharacterVisualProfiler:
    """LLM-powered visual character design with adaptive reasoning.

    This is the primary visual design implementation for character creation,
    using LLM-powered generation with SOTA Gaussian Splatting 3D generation.
    Formerly named IntelligentVisualDesigner - renamed to avoid confusion.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.design_history: list[dict[str, Any]] = []
        self.style_preferences: dict[str, Any] = {}
        from kagami.forge.utils.cache import MemoryCache

        self.visual_analysis_cache = MemoryCache(
            name="visual_analysis", max_size=100, default_ttl=3600
        )
        self._initialized = False
        self.style_config = StyleConfig()
        config = config or {}
        config.get("llm", {})
        self.llm = KagamiOSLLMServiceAdapter()

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the visual designer."""
        if not self._initialized:
            await self.llm.initialize()
            self._initialized = True
            logger.info("IntelligentVisualDesigner initialized")

    async def create_kagami_style_prompt(
        self,
        character_concept: str,
        character_traits: list[str] | None = None,
        outfit_style: str = "casual",
        style_config: StyleConfig | None = None,
    ) -> str:
        """Create a K os house-style cute character prompt"""
        if character_traits is None:
            character_traits = []
        if style_config is None:
            style_config = StyleConfig(
                cuteness_level="ultra_cute",
                emoji_compatible=True,
                outfit_style=outfit_style,
                size_emphasis="chibi",
                eye_style="large_sparkly",
                expression="joyful",
            )
        if hasattr(self, "pixar_enhancer") and self.pixar_enhancer is not None:
            enhanced_prompt = str(
                self.pixar_enhancer.enhance_prompt_for_pixar_style(
                    base_prompt=character_concept,
                    character_traits=character_traits,
                    outfit_preference=outfit_style,
                    style_config=style_config,
                )
            )
        else:
            prompt = f"Transform this concept into a K os house‑style brief for 3D character creation.\nEmbed: proportion targets (Head45/Body35/Limbs20), eye design (round pupils, triple highlights),\ncosmic gradient color philosophy, velvet‑matte materials with SSS, and lighting (key/fill/rim).\nReflect animation principles in stills: anticipation, arcs, overlap, implied squash/stretch, appeal.\nReturn a compact brief with sections: Concept, Proportions, Eyes, Palette, Materials, Lighting, Pose, Expression, Background, No‑Nos.\n\nConcept: {character_concept}\nTraits: {', '.join(character_traits)}\nOutfit: {outfit_style}\nStyleConfig: {style_config}"
            enhanced_prompt = str(await self.llm.generate_text(prompt))
        return enhanced_prompt

    def get_kagami_negative_prompt(self) -> str:
        """Get negative prompt optimized for K os house style generation"""
        if hasattr(self, "pixar_enhancer") and self.pixar_enhancer is not None:
            return str(self.pixar_enhancer.create_pixar_negative_prompt())
        else:
            return "low quality, blurry, ugly, distorted, bad anatomy"

    async def generate(self, request: CharacterRequest) -> GenerationResult:
        """Generate visual design for character request."""
        if not self._initialized:
            await self.initialize()
        start_time = time.time()
        try:
            character_context = CharacterContext(
                character_id=request.request_id,
                name=getattr(request, "concept", "character"),
                description=f"Character with {request.style.primary_style.value} style",
                aspect=CharacterAspect.VISUAL_DESIGN,
                metadata=(getattr(request, "metadata", {}) or {}).get("visual_features", {}),
            )
        except Exception:
            character_context = CharacterContext(character_id="temp", name="character")
        visual_profile = await self._generate_visual_design(character_context, request.style)

        # SOTA: Gaussian Splatting mesh generation (best-effort).
        try:
            import trimesh

            from kagami.forge.modules.generation import get_3d_generator

            gen = await get_3d_generator()
            negative = self.get_kagami_negative_prompt()

            # Scale iterations by quality level (preview/draft/final).
            q = getattr(getattr(request, "quality_level", None), "value", None) or str(
                getattr(request, "quality_level", "preview")
            )
            q = str(q).lower()
            iters = 500 if q in ("low", "preview") else 1500 if q in ("medium", "draft") else 3000

            gen_res = await gen.generate(
                prompt=request.concept,
                negative_prompt=negative,
                num_iterations=iters,
            )
            if not getattr(gen_res, "success", False) or not getattr(gen_res, "mesh_path", None):
                raise RuntimeError(getattr(gen_res, "error", None) or "Gaussian generation failed")

            # Load exported OBJ into Forge Mesh dataclass
            tm = trimesh.load(str(gen_res.mesh_path), force="mesh")
            if isinstance(tm, trimesh.Scene):
                # Concatenate scene geometry into a single mesh.
                tm = trimesh.util.concatenate(tuple(tm.geometry.values()))

            verts = np.asarray(getattr(tm, "vertices", np.zeros((0, 3))), dtype=np.float32)
            faces = np.asarray(getattr(tm, "faces", np.zeros((0, 3))), dtype=np.int64)
            if verts.size == 0 or faces.size == 0:
                raise RuntimeError("Generated mesh empty")

            bmin = verts.min(axis=0)
            bmax = verts.max(axis=0)
            bounds = BoundingBox(
                min_point=Vector3(float(bmin[0]), float(bmin[1]), float(bmin[2])),
                max_point=Vector3(float(bmax[0]), float(bmax[1]), float(bmax[2])),
            )

            mesh = Mesh(
                name=f"{request.request_id}_mesh",
                vertices=verts,
                faces=faces,
                bounds=bounds,
                metadata={
                    "generator": "gaussian_splatting",
                    "mesh_path": str(gen_res.mesh_path),
                    "cloud_path": str(getattr(gen_res, "output_path", "") or ""),
                    "num_gaussians": int(getattr(gen_res, "num_gaussians", 0) or 0),
                    "final_loss": float(getattr(gen_res, "final_loss", 0.0) or 0.0),
                },
            )
        except Exception as e:
            # Fail fast - no fallback meshes
            logger.error(f"Gaussian mesh generation failed: {e}")
            return GenerationResult(success=False, error=str(e))
        generation_time = time.time() - start_time
        return GenerationResult(
            success=True,
            mesh_data=mesh,
            textures=visual_profile.get("textures", {}),
            generation_time=generation_time,
            quality_score=self._calculate_quality_score(visual_profile),
        )

    async def _analyze_reference_images(
        self, images: list[str | bytes | Image.Image]
    ) -> dict[str, Any]:
        """Analyze reference images using LLM reasoning"""
        try:
            analysis_prompt = "Analyze these reference images for character design elements.\n\nFor each image, identify and describe:\n1. Visual style and artistic approach\n2. Character design principles being used\n3. Color palette and lighting mood\n4. Distinctive design elements and features\n5. Cultural or thematic influences\n6. Technical rendering style (realistic, stylized, etc.)\n7. Emotional tone and personality conveyed\n8. Design patterns that could be adapted\n\nProvide specific, actionable insights that can guide character design decisions."
            llm_request = LLMRequest(
                prompt=analysis_prompt,
                context=CharacterContext(
                    character_id="image_analysis",
                    name="reference_analysis",
                    description="Analysis of reference images",
                    aspect=CharacterAspect.VISUAL_DESIGN,
                ),
                temperature=0.6,
                max_tokens=800,
            )
            response = await self.llm.generate_text(llm_request.prompt)
            analysis_data = {
                "visual_insights": response,
                "reasoning": "",
                "design_patterns": self._extract_design_patterns(response),
                "style_indicators": self._extract_style_indicators(response),
            }
            cache_key = self._generate_image_cache_key(images)
            self.visual_analysis_cache[cache_key] = analysis_data
            return analysis_data
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return {"error": str(e)}

    def _prepare_design_context(
        self,
        character_context: CharacterContext,
        style_requirements: StylePreferences | None,
        visual_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """Prepare comprehensive context for visual design generation"""
        context = {
            "character_base": {
                "character_id": character_context.character_id,
                "concept": getattr(
                    character_context, "concept", getattr(character_context, "name", "character")
                ),
                "style": getattr(
                    character_context,
                    "description",
                    getattr(character_context, "concept", getattr(character_context, "name", "")),
                ),
            },
            "design_requirements": (
                {
                    "primary_style": (
                        style_requirements.primary_style.value
                        if style_requirements
                        else "realistic"
                    ),
                    "secondary_styles": (
                        [s.value for s in style_requirements.secondary_styles]
                        if style_requirements
                        else []
                    ),
                    "color_palette": style_requirements.color_palette if style_requirements else [],
                    "detail_level": (
                        style_requirements.detail_level if style_requirements else "medium"
                    ),
                }
                if style_requirements
                else {}
            ),
            "visual_references": visual_analysis,
            "design_history": self._summarize_design_history(),
            "style_preferences": self.style_preferences,
            "technical_constraints": self._get_technical_constraints(),
            "creative_parameters": self._get_creative_parameters(),
        }
        return context

    async def _generate_visual_design(
        self,
        character_context: CharacterContext,
        style_requirements: StylePreferences | None = None,
    ) -> dict[str, Any]:
        """Generate comprehensive visual design using LLM reasoning"""
        ctx_name = getattr(character_context, "name", None) or getattr(
            character_context, "concept", "character"
        )
        llm_request = LLMRequest(
            prompt=f"Create a comprehensive visual character design for: {ctx_name}",
            context=character_context,
            temperature=0.7,
            max_tokens=1000,
        )
        response = await self.llm.generate_text(llm_request.prompt)
        visual_design = await self._parse_visual_design(response)
        return visual_design

    async def _parse_visual_design(self, response: str) -> dict[str, Any]:
        """Parse and structure visual design response"""
        try:
            content = response
            sections = await self._intelligent_section_parsing(content)
            design_elements = {
                "physical_characteristics": sections.get("physical_characteristics", {}),
                "style_aesthetic": sections.get("style_and_aesthetic", {}),
                "visual_storytelling": sections.get("visual_storytelling", {}),
                "technical_considerations": sections.get("technical_considerations", {}),
                "color_palette": await self._extract_color_palette(content),
                "key_features": await self._extract_key_features(content),
                "design_priorities": await self._extract_design_priorities(content),
            }
            return {
                "design_elements": design_elements,
                "raw_content": content,
                "reasoning": sections.get("reasoning", ""),
                "structured_sections": sections,
                "textures": {},
            }
        except Exception as e:
            logger.warning(f"Failed to parse visual design: {e}")
            return {"raw_content": response, "reasoning": "", "parse_error": str(e)}

    async def _intelligent_section_parsing(self, content: str) -> dict[str, Any]:
        """Parse content into sections using an LLM call instead of regex heuristics."""
        try:
            prompt = f"Structure the following character visual design content into sections. Return strict JSON with keys: physical_characteristics, style_and_aesthetic, visual_storytelling, technical_considerations, reasoning.\n\nContent:\n{content[:4000]}"
            structured = await self.llm.generate_text(prompt)
            import json as _json

            result = _json.loads(structured) if isinstance(structured, str) else structured
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    async def _extract_color_palette(self, content: str) -> list[str]:
        """Ask LLM to extract color palette names; no regex heuristics."""
        try:
            prompt = f"List the distinct color names present in the following design content as a JSON array.\n\nContent:\n{content[:4000]}"
            response = await self.llm.generate_text(prompt)
            import json as _json

            data = _json.loads(response) if isinstance(response, str) else response
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def _extract_key_features(self, content: str) -> list[str]:
        """LLM-extracted list[Any] of key distinctive features."""
        try:
            prompt = f"Extract up to 10 distinctive features from the following text as a JSON array.\n\nContent:\n{content[:4000]}"
            response = await self.llm.generate_text(prompt)
            import json as _json

            data = _json.loads(response) if isinstance(response, str) else response
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def _extract_design_priorities(self, content: str) -> list[str]:
        """LLM-extracted design priorities to remove regex heuristics."""
        try:
            prompt = f"Extract up to 8 design priorities from the following content as a JSON array.\n\nContent:\n{content[:4000]}"
            response = await self.llm.generate_text(prompt)
            import json as _json

            data = _json.loads(response) if isinstance(response, str) else response
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def _generate_technical_specifications(
        self, visual_profile: dict[str, Any], character_context: CharacterContext
    ) -> dict[str, Any]:
        """Generate technical specifications for implementation"""
        llm_request = LLMRequest(
            prompt=f"Based on this visual character design, generate detailed technical specifications for 3D implementation.\n\nVisual Design:\n{json.dumps(visual_profile, indent=2)}\n\nCreate technical specifications including:\n- 3D modeling requirements\n- Material and shader specifications\n- Animation considerations\n- Asset pipeline requirements\n\nBe specific and actionable for a 3D art team.",
            context=character_context,
            temperature=0.5,
            max_tokens=800,
        )
        response = await self.llm.generate_text(llm_request.prompt)
        return await self._parse_technical_specs(response)

    async def _generate_implementation_guidance(
        self, visual_profile: dict[str, Any], technical_specs: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate step-by-step implementation guidance"""
        llm_request = LLMRequest(
            prompt=f"Create a comprehensive implementation guide for bringing this character design to life.\n\nVisual Profile:\n{json.dumps(visual_profile, indent=2)}\n\nTechnical Specifications:\n{json.dumps(technical_specs, indent=2)}\n\nGenerate an implementation guide including:\n- Pre-production phase requirements\n- Production pipeline workflow\n- Quality assurance checks\n- Integration requirements\n\nProvide actionable steps with clear deliverables and quality metrics.",
            context=CharacterContext(
                character_id="implementation",
                name="guide_generation",
                description="Implementation guide generation",
                aspect=CharacterAspect.VISUAL_DESIGN,
            ),
            temperature=0.6,
            max_tokens=1200,
        )
        response = await self.llm.generate_text(llm_request.prompt)
        return self._parse_implementation_guide(response)

    async def _parse_technical_specs(self, response: str) -> dict[str, Any]:
        """Parse technical specifications response"""
        return {
            "specifications": response,
            "reasoning": "",
            "sections": await self._intelligent_section_parsing(response),
        }

    def _parse_implementation_guide(self, response: str) -> dict[str, Any]:
        """Parse implementation guidance response"""
        return {
            "guidance": response,
            "reasoning": "",
            "workflow_steps": self._extract_workflow_steps(response),
            "deliverables": self._extract_deliverables(response),
        }

    def _extract_workflow_steps(self, content: str) -> list[dict[str, Any]]:
        """Extract workflow steps from implementation guide"""
        import re

        step_pattern = "(\\d+\\.?\\s*[^.\\n]+)"
        steps = re.findall(step_pattern, content)
        workflow_steps = []
        for step in steps:
            workflow_steps.append(
                {
                    "step": step.strip(),
                    "phase": self._determine_phase(step),
                    "estimated_effort": self._estimate_effort(self._determine_phase(step), step),
                }
            )
        return workflow_steps

    def _estimate_effort(self, phase: str, step: str) -> str:
        """Heuristic effort estimator for a workflow step.

        Returns a compact effort bucket string to avoid overpromising while
        providing useful guidance. Buckets are expressed in person-hours.
        """
        base = {
            "pre_production": 2.0,
            "production": 6.0,
            "quality_assurance": 3.0,
            "integration": 4.0,
            "general": 3.0,
        }.get(phase, 3.0)
        text = (step or "").lower()
        if any(k in text for k in ["rig", "retarget", "simulate", "optimize"]):
            base *= 1.8
        if any(k in text for k in ["concept", "style", "review", "align"]):
            base *= 0.9
        if any(k in text for k in ["test", "validate", "fix", "qa"]):
            base *= 1.1
        length_factor = min(1.5, max(0.8, len(step) / 60.0)) if step else 1.0
        hours = max(1.0, base * length_factor)
        if hours <= 2:
            return "~2h"
        if hours <= 4:
            return "~4h"
        if hours <= 8:
            return "~1d"
        if hours <= 16:
            return "~2d"
        return ">2d"

    def _determine_phase(self, step: str) -> str:
        """Determine which phase a workflow step belongs to"""
        step_lower = step.lower()
        if any(word in step_lower for word in ["concept", "design", "plan"]):
            return "pre_production"
        elif any(word in step_lower for word in ["model", "texture", "rig"]):
            return "production"
        elif any(word in step_lower for word in ["test", "validate", "check"]):
            return "quality_assurance"
        elif any(word in step_lower for word in ["integrate", "optimize", "deploy"]):
            return "integration"
        else:
            return "general"

    def _extract_deliverables(self, content: str) -> list[str]:
        """Extract deliverables from implementation guide"""
        deliverable_indicators = ["deliverable", "output", "result", "asset", "file", "document"]
        import re

        deliverables = []
        for indicator in deliverable_indicators:
            pattern = f"{indicator}[^.]*"
            matches = re.findall(pattern, content, re.IGNORECASE)
            deliverables.extend(matches)
        return list(set(deliverables))

    def _get_technical_constraints(self) -> dict[str, Any]:
        """Get technical constraints for design"""
        return {
            "target_platform": "cross_platform",
            "performance_requirements": {
                "polygon_budget": "medium",
                "texture_memory": "optimized",
                "animation_complexity": "realistic",
            },
            "engine_compatibility": ["unreal", "unity", "custom"],
            "output_formats": ["fbx", "gltf", "usd"],
        }

    def _get_creative_parameters(self) -> dict[str, Any]:
        """Get creative parameters for design"""
        return {
            "style_flexibility": "high",
            "innovation_level": "moderate",
            "cultural_sensitivity": "high",
            "target_audience": "general",
            "artistic_direction": "realistic_stylized",
        }

    def _extract_design_patterns(self, content: str) -> list[str]:
        """Extract design patterns from visual analysis"""
        patterns = []
        pattern_keywords = [
            "symmetrical",
            "asymmetrical",
            "geometric",
            "organic",
            "minimalist",
            "detailed",
            "angular",
            "curved",
            "contrast",
            "harmony",
            "balance",
            "emphasis",
        ]
        content_lower = content.lower()
        for keyword in pattern_keywords:
            if keyword in content_lower:
                patterns.append(keyword)
        return patterns

    def _extract_style_indicators(self, content: str) -> list[str]:
        """Extract style indicators from visual analysis"""
        style_keywords = [
            "realistic",
            "stylized",
            "cartoon",
            "anime",
            "semi_realistic",
            "photorealistic",
            "abstract",
            "impressionistic",
            "modern",
            "classic",
            "futuristic",
            "retro",
            "fantasy",
            "sci_fi",
        ]
        content_lower = content.lower()
        indicators = [kw for kw in style_keywords if kw in content_lower]
        return indicators

    def _generate_image_cache_key(self, images: list[Any]) -> str:
        """Generate cache key for image analysis"""
        import hashlib

        key_data = f"{len(images)}_{type(images[0]).__name__}"
        return hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()

    def _update_design_history(self, result: dict[str, Any]) -> None:
        """Update design generation history"""
        self.design_history.append(
            {
                "timestamp": time.time(),
                "result_summary": {
                    "has_visual_profile": "visual_profile" in result,
                    "has_technical_specs": "technical_specifications" in result,
                    "processing_time": result.get("generation_metadata", {}).get(
                        "processing_time_ms", 0
                    ),
                },
                "quality_metrics": self._assess_design_quality(result),
            }
        )
        if len(self.design_history) > 50:
            self.design_history = self.design_history[-25:]

    def _assess_design_quality(self, result: dict[str, Any]) -> dict[str, str]:
        """Assess the quality of generated design"""
        profile = result.get("visual_profile", {})
        content_length = len(str(profile))
        quality = "high" if content_length > 1000 else "medium" if content_length > 500 else "low"
        return {
            "content_quality": quality,
            "has_technical_specs": "yes" if "technical_specifications" in result else "no",
            "has_implementation_guide": "yes" if "implementation_guidance" in result else "no",
        }

    def _summarize_design_history(self) -> dict[str, Any]:
        """Summarize design generation history"""
        if not self.design_history:
            return {}
        recent_history = self.design_history[-5:]
        return {
            "recent_designs": len(recent_history),
            "average_processing_time": sum(
                h["result_summary"]["processing_time"] for h in recent_history
            )
            / len(recent_history),
            "quality_trend": [h["quality_metrics"]["content_quality"] for h in recent_history],
        }

    def _calculate_quality_score(self, visual_profile: dict[str, Any]) -> float:
        """Calculate quality score for visual design."""
        score = 0.0
        if visual_profile.get("design_elements"):
            score += 0.3
        content = str(visual_profile.get("raw_content", ""))
        if len(content) > 500:
            score += 0.3
        elif len(content) > 200:
            score += 0.2
        if visual_profile.get("structured_sections"):
            score += 0.2
        if visual_profile.get("reasoning"):
            score += 0.2
        return min(score, 1.0)
