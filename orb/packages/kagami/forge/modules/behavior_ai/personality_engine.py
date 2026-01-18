#!/usr/bin/env python3
"""Personality and behavioral AI generation for character creation.

This module generates comprehensive personality profiles for characters using
LLM-powered analysis. It creates detailed behavioral patterns, decision-making
processes, and psychological traits that drive character actions.

Key Features:
    - Big Five personality trait generation
    - Decision-making pattern analysis
    - Social interaction style modeling
    - Emotional characteristic profiling
    - Behavioral pattern prediction
    - Communication style definition

Personality Archetypes:
    - Analytical: Logical, systematic thinkers
    - Expressive: Outgoing, enthusiastic communicators
    - Driving: Decisive, action-oriented leaders
    - Amiable: Supportive, harmony-seeking collaborators
    - Creative: Innovative, imaginative visionaries
    - Guardian: Traditional, protective caretakers

Dependencies:
    - Qwen LLM for personality generation
    - Shared context for character consistency
"""

import json
import logging
import time
from typing import Any

from ...core_integration import (
    CharacterAspect,
    CharacterContext,
    LLMRequest,
    LLMResponse,
)
from ...llm_service_adapter import KagamiOSLLMServiceAdapter
from ...schema import (
    BehaviorResult,
    CharacterRequest,
    EmotionalProfile,
    EmotionalState,
    PersonalityProfile,
)
from ..export.base import ForgeComponent

# Initialize logger early
logger = logging.getLogger("ForgeMatrix.PersonalityEngine")

from enum import Enum


class PersonalityTrait(Enum):
    """Big Five personality trait dimensions."""

    OPENNESS = "openness"
    CONSCIENTIOUSNESS = "conscientiousness"
    EXTRAVERSION = "extraversion"
    AGREEABLENESS = "agreeableness"
    NEUROTICISM = "neuroticism"


class PersonalityEngine(ForgeComponent):
    """Generates comprehensive personality profiles for characters.

    Uses LLM analysis to create detailed psychological profiles including
    personality traits, behavioral patterns, and decision-making processes.
    Personality generation is based on character descriptions and guided
    by psychological archetypes.

    Attributes:
        initialized: Whether the engine is ready for generation
        stats: Performance statistics for tracking
        personality_templates: Predefined archetype templates
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        # Initialize ForgeComponent base class
        super().__init__("PersonalityEngine")

        self.initialized = False
        self.stats = {"total_processed": 0, "llm_calls": 0, "avg_response_time": 0.0}
        self.personality_templates = self._load_personality_templates()

        # Use provided config or default
        config = config or {}
        llm_config = config.get("llm", {})

        # Initialize LLM for personality generation
        llm_params = {
            "provider": llm_config.get("provider"),
            "model_name": llm_config.get("model_name"),
            "fast_model_name": llm_config.get("fast_model_name"),
            "auto_model_selection": llm_config.get("auto_model_selection", True),
            "complexity_threshold": llm_config.get("complexity_threshold", 0.6),
            # Pass along nested config for factory to resolve sensible defaults
            "config": llm_config,
        }

        logger.info(
            f"PersonalityEngine: Initializing LLM with model={llm_params['model_name']}, fast_model={llm_params['fast_model_name']}"
        )

        self.llm = KagamiOSLLMServiceAdapter(
            model_type=llm_config.get("provider", "qwen"),
            **llm_params,
        )

        # Colony integration for world model coherence
        self._colony_bridge = None
        try:
            from ...colony_integration import get_forge_colony_bridge

            self._colony_bridge = get_forge_colony_bridge()
            logger.info("✅ Colony bridge connected for personality coherence")
        except ImportError:
            logger.debug("Colony integration not available")

    async def initialize(self, config: dict[str, Any] | None = None) -> None:  # type: ignore  # Override
        """Initialize personality engine with LLM and world model integration."""
        try:
            # Initialize LLM
            await self.llm.initialize()

            self.initialized = True
            logger.info("✅ PersonalityEngine initialized with LLM integration")
        except Exception as e:
            logger.error(f"❌ PersonalityEngine initialization failed: {e}")
            raise RuntimeError(f"PersonalityEngine failed to initialize: {e}") from None

    def _load_personality_templates(self) -> dict[str, dict[str, Any]]:
        """Load personality templates for different behavioral archetypes."""
        return {
            "analytical": {
                "big_five": {
                    "openness": 0.8,
                    "conscientiousness": 0.9,
                    "extraversion": 0.3,
                    "agreeableness": 0.6,
                    "neuroticism": 0.2,
                },
                "decision_making": "logical_systematic",
                "social_style": "reserved_thoughtful",
                "emotional_range": "controlled_measured",
                "communication": "precise_factual",
                "stress_response": "methodical_planning",
            },
            "expressive": {
                "big_five": {
                    "openness": 0.7,
                    "conscientiousness": 0.5,
                    "extraversion": 0.9,
                    "agreeableness": 0.8,
                    "neuroticism": 0.4,
                },
                "decision_making": "intuitive_emotional",
                "social_style": "outgoing_animated",
                "emotional_range": "dynamic_expressive",
                "communication": "enthusiastic_storytelling",
                "stress_response": "social_seeking",
            },
            "driving": {
                "big_five": {
                    "openness": 0.6,
                    "conscientiousness": 0.8,
                    "extraversion": 0.8,
                    "agreeableness": 0.3,
                    "neuroticism": 0.3,
                },
                "decision_making": "quick_decisive",
                "social_style": "assertive_direct",
                "emotional_range": "intense_focused",
                "communication": "commanding_brief",
                "stress_response": "action_oriented",
            },
            "amiable": {
                "big_five": {
                    "openness": 0.5,
                    "conscientiousness": 0.7,
                    "extraversion": 0.4,
                    "agreeableness": 0.9,
                    "neuroticism": 0.4,
                },
                "decision_making": "consensus_seeking",
                "social_style": "supportive_patient",
                "emotional_range": "stable_gentle",
                "communication": "empathetic_encouraging",
                "stress_response": "harmony_seeking",
            },
            "creative": {
                "big_five": {
                    "openness": 0.9,
                    "conscientiousness": 0.4,
                    "extraversion": 0.6,
                    "agreeableness": 0.7,
                    "neuroticism": 0.5,
                },
                "decision_making": "innovative_flexible",
                "social_style": "inspiring_imaginative",
                "emotional_range": "passionate_variable",
                "communication": "metaphorical_visionary",
                "stress_response": "creative_outlet",
            },
            "guardian": {
                "big_five": {
                    "openness": 0.4,
                    "conscientiousness": 0.9,
                    "extraversion": 0.5,
                    "agreeableness": 0.8,
                    "neuroticism": 0.3,
                },
                "decision_making": "traditional_careful",
                "social_style": "protective_loyal",
                "emotional_range": "steady_reliable",
                "communication": "practical_supportive",
                "stress_response": "duty_focused",
            },
        }

    async def generate(self, request: CharacterRequest) -> BehaviorResult:
        """Generate personality profile for character request."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # Create character context
            character_context = CharacterContext(  # type: ignore[call-arg]
                character_id=request.request_id,
                concept=request.concept,
                personality_traits=(
                    request.personality_brief.split(", ") if request.personality_brief else []
                ),
            )

            # Determine personality archetype
            archetype = self._determine_personality_archetype(request.concept, {})
            template = self.personality_templates.get(
                archetype, self.personality_templates["amiable"]
            )

            # Generate personality profile
            personality_data = await self._generate_personality_profile(
                character_context, archetype, template
            )

            # Create PersonalityProfile object
            personality_profile = PersonalityProfile(
                traits=personality_data.get("traits", []),
                big_five=personality_data.get("big_five_personality", {}),
                values=personality_data.get("values", []),
                fears=personality_data.get("fears", []),
                desires=personality_data.get("desires", []),
                quirks=personality_data.get("quirks", []),
            )

            # Create EmotionalProfile object
            emotional_data = personality_data.get("emotional_characteristics", {})
            emotional_profile = EmotionalProfile(
                base_mood=EmotionalState.NEUTRAL,
                emotional_range=emotional_data.get("emotional_range", 0.7),
                mood_stability=emotional_data.get("emotional_stability", 0.5),
                empathy_level=emotional_data.get("empathy_level", 0.7),
            )

            # Calculate quality score
            quality_score = self._calculate_personality_quality(personality_data)

            generation_time = time.time() - start_time

            # Update statistics
            self.stats["total_processed"] += 1
            self.stats["llm_calls"] += 1
            self.stats["avg_response_time"] = (
                self.stats["avg_response_time"] * (self.stats["llm_calls"] - 1)
                + generation_time * 1000
            ) / self.stats["llm_calls"]

            logger.info(
                f"✅ Generated personality profile for {request.request_id} in {generation_time * 1000:.2f}ms"
            )

            return BehaviorResult(
                success=True,
                personality=personality_profile,
                emotional_profile=emotional_profile,
                decision_tree=personality_data.get("decision_making_patterns", {}),
                behavior_scripts=personality_data.get("behavior_scripts", {}),
                generation_time=generation_time,
                consistency_score=quality_score,
            )

        except Exception as e:
            logger.error(f"❌ Personality generation failed: {e}")
            return BehaviorResult(
                success=False, error=str(e), generation_time=time.time() - start_time
            )

    async def _generate_personality_profile(
        self,
        character_context: CharacterContext,
        archetype: str,
        template: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate personality profile using LLM with world model integration."""
        return await self._generate_personality_llm(character_context, archetype, template)

    async def _generate_personality_llm(
        self,
        character_context: CharacterContext,
        archetype: str,
        template: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate personality using LLM with world model integration.

        REFACTORED (Dec 4, 2025): Removed legacy naming, integrated colony tracking.
        """
        from ...utils.style_directives import get_kagami_creative_tone

        _tone = get_kagami_creative_tone()
        llm_request = LLMRequest(
            aspect=CharacterAspect.PERSONALITY,
            prompt=f"{_tone}\nGenerate comprehensive personality profile for: {getattr(character_context, 'concept', 'Unknown')}",
            context=character_context,
            template=None,
            require_json=True,
        )

        # Generate response
        if hasattr(self.llm, "reason"):
            response = await self.llm.reason(llm_request)
        elif hasattr(self.llm, "generate_text"):
            response_text = await self.llm.generate_text(
                llm_request.prompt, temperature=0.7, max_tokens=2048
            )
            from ...core_integration import LLMResponse as CoreLLMResponse

            response = CoreLLMResponse(
                content=response_text, model_name=self.llm.model_name, confidence=0.9
            )
        else:
            raise AttributeError(
                f"LLM {type(self.llm)} has neither 'reason' nor 'generate_text' method"
            )

        # Process response
        return self._process_personality_response(response, template, archetype)

    def _process_personality_response(
        self, response: LLMResponse, template: dict[str, Any], archetype: str
    ) -> dict[str, Any]:
        """Process LLM response and enhance with template data."""

        # Parse LLM response
        if isinstance(response.content, dict):  # type: ignore[unreachable]
            personality_data = response.content  # type: ignore[unreachable]
        else:
            # Try to parse as JSON if it's a string
            try:
                personality_data = json.loads(str(response.content))
            except json.JSONDecodeError:
                # Use template data instead
                personality_data = {}

        # Enhance with template data and ensure completeness
        enhanced_data = {
            "big_five_personality": personality_data.get(
                "big_five_personality", template.get("big_five", {})
            ),
            "decision_making_patterns": personality_data.get(
                "decision_making_patterns",
                {"style": template.get("decision_making", "balanced")},
            ),
            "social_interaction_styles": personality_data.get(
                "social_interaction_styles",
                {"style": template.get("social_style", "balanced")},
            ),
            "emotional_characteristics": personality_data.get(
                "emotional_characteristics",
                {"range": template.get("emotional_range", "moderate")},
            ),
            "behavioral_patterns": personality_data.get("behavioral_patterns", {}),
            "motivational_drivers": personality_data.get("motivational_drivers", {}),
            "communication_patterns": personality_data.get(
                "communication_patterns",
                {"style": template.get("communication", "balanced")},
            ),
            "cognitive_preferences": personality_data.get("cognitive_preferences", {}),
            # Schema-compatible fields
            "traits": self._extract_traits(personality_data, template),
            "values": self._extract_values(personality_data),
            "fears": self._extract_fears(personality_data),
            "desires": self._extract_desires(personality_data),
            "quirks": self._extract_quirks(personality_data),
            "behavior_scripts": self._generate_behavior_scripts(personality_data, archetype),
            "archetype_analysis": {
                "determined_archetype": archetype,
                "template_influences": template,
                "llm_enhanced": True,
            },
            "generation_metadata": {
                "method": "llm_powered",
                "template_archetype": archetype,
                "enhancement_applied": True,
                "behavioral_modeling_ready": True,
                "ai_implementation_ready": True,
            },
        }

        return enhanced_data

    def _determine_personality_archetype(self, description: str, traits: dict[str, Any]) -> str:
        """Determine personality archetype from description and traits."""

        description_lower = description.lower()

        # Direct archetype indicators in description
        if any(
            word in description_lower
            for word in [
                "analytical",
                "logical",
                "systematic",
                "methodical",
                "rational",
            ]
        ):
            return "analytical"
        elif any(
            word in description_lower
            for word in ["expressive", "outgoing", "enthusiastic", "animated", "social"]
        ):
            return "expressive"
        elif any(
            word in description_lower
            for word in ["driving", "decisive", "assertive", "commanding", "direct"]
        ):
            return "driving"
        elif any(
            word in description_lower
            for word in ["amiable", "gentle", "supportive", "patient", "caring"]
        ):
            return "amiable"
        elif any(
            word in description_lower
            for word in [
                "creative",
                "imaginative",
                "artistic",
                "innovative",
                "visionary",
            ]
        ):
            return "creative"
        elif any(
            word in description_lower
            for word in ["guardian", "protective", "loyal", "traditional", "reliable"]
        ):
            return "guardian"

        # Personality-based determination from existing traits
        personality = traits.get("personality", {})
        if personality:
            openness = personality.get("openness", 0.5)
            conscientiousness = personality.get("conscientiousness", 0.5)
            extraversion = personality.get("extraversion", 0.5)
            agreeableness = personality.get("agreeableness", 0.5)
            personality.get("neuroticism", 0.5)

            # Analytical: High conscientiousness + low extraversion + high openness
            if conscientiousness > 0.7 and extraversion < 0.4 and openness > 0.6:
                return "analytical"
            # Expressive: High extraversion + high agreeableness + high openness
            elif extraversion > 0.7 and agreeableness > 0.6 and openness > 0.6:
                return "expressive"
            # Driving: High extraversion + low agreeableness + high conscientiousness
            elif extraversion > 0.7 and agreeableness < 0.4 and conscientiousness > 0.6:
                return "driving"
            # Creative: High openness + low conscientiousness + moderate extraversion
            elif openness > 0.8 and conscientiousness < 0.5:
                return "creative"
            # Guardian: High conscientiousness + high agreeableness + low openness
            elif conscientiousness > 0.8 and agreeableness > 0.7 and openness < 0.5:
                return "guardian"
            # Amiable: High agreeableness + low extraversion + moderate conscientiousness
            elif agreeableness > 0.7 and extraversion < 0.5:
                return "amiable"

        # Default to amiable if no strong indicators
        return "amiable"

    def _calculate_personality_quality(self, personality_profile: dict[str, Any]) -> float:
        """Calculate quality score for generated personality profile."""
        quality_factors = []

        # Check completeness
        required_sections = [
            "big_five_personality",
            "decision_making_patterns",
            "social_interaction_styles",
            "emotional_characteristics",
        ]
        completeness = sum(
            1 for section in required_sections if section in personality_profile
        ) / len(required_sections)
        quality_factors.append(completeness)

        # Check Big Five validity (should be between 0.0 and 1.0)
        big_five = personality_profile.get("big_five_personality", {})
        big_five_validity = 0.0
        if big_five:
            valid_traits = 0
            for _trait, value in big_five.items():
                if isinstance(value, (int, float)) and 0.0 <= value <= 1.0:
                    valid_traits += 1
            big_five_validity = valid_traits / 5.0  # 5 Big Five traits
        quality_factors.append(big_five_validity)

        # Check detail richness
        total_details = sum(
            len(str(personality_profile.get(section, {}))) for section in required_sections
        )
        detail_score = min(total_details / 2500, 1.0)  # Expect rich behavioral details
        quality_factors.append(detail_score)

        # Check Qwen enhancement
        qwen_enhanced = personality_profile.get("archetype_analysis", {}).get(
            "qwen_enhanced", False
        )
        enhancement_score = 1.0 if qwen_enhanced else 0.5
        quality_factors.append(enhancement_score)

        # Check AI implementation readiness
        ai_ready = personality_profile.get("generation_metadata", {}).get(
            "ai_implementation_ready", False
        )
        ai_score = 1.0 if ai_ready else 0.7
        quality_factors.append(ai_score)

        return sum(quality_factors) / len(quality_factors)

    def _extract_traits(
        self, personality_data: dict[str, Any], template: dict[str, Any]
    ) -> list[str]:
        """Extract personality traits from data."""
        traits = []

        # Extract from big five
        big_five = personality_data.get("big_five_personality", {})
        for trait, value in big_five.items():
            if isinstance(value, (int, float)) and value > 0.7:
                traits.append(f"high_{trait}")
            elif isinstance(value, (int, float)) and value < 0.3:
                traits.append(f"low_{trait}")

        # Add archetype-based traits
        archetype_traits = {
            "analytical": ["logical", "systematic", "detail-oriented"],
            "expressive": ["enthusiastic", "social", "animated"],
            "driving": ["decisive", "assertive", "goal-oriented"],
            "amiable": ["supportive", "patient", "cooperative"],
            "creative": ["imaginative", "innovative", "artistic"],
            "guardian": ["protective", "loyal", "traditional"],
        }

        archetype = template.get("archetype", "amiable")
        traits.extend(archetype_traits.get(archetype, []))

        return traits[:10]  # Limit to 10 traits

    def _extract_values(self, personality_data: dict[str, Any]) -> list[str]:
        """Extract core values from personality data."""
        values = []
        motivational = personality_data.get("motivational_drivers", {})

        if "achievement" in str(motivational).lower():
            values.append("achievement")
        if "harmony" in str(motivational).lower():
            values.append("harmony")
        if "independence" in str(motivational).lower():
            values.append("independence")
        if "security" in str(motivational).lower():
            values.append("security")
        if "growth" in str(motivational).lower():
            values.append("growth")

        return values or ["balance", "integrity", "respect"]

    def _extract_fears(self, personality_data: dict[str, Any]) -> list[str]:
        """Extract fears from personality data."""
        fears = []
        emotional = personality_data.get("emotional_characteristics", {})

        if "anxiety" in str(emotional).lower():
            fears.append("failure")
        if "social" in str(emotional).lower():
            fears.append("rejection")
        if "control" in str(emotional).lower():
            fears.append("loss of control")

        return fears or ["uncertainty", "conflict"]

    def _extract_desires(self, personality_data: dict[str, Any]) -> list[str]:
        """Extract desires from personality data."""
        desires = []
        motivational = personality_data.get("motivational_drivers", {})

        if "recognition" in str(motivational).lower():
            desires.append("recognition")
        if "connection" in str(motivational).lower():
            desires.append("meaningful relationships")
        if "mastery" in str(motivational).lower():
            desires.append("expertise")

        return desires or ["fulfillment", "growth", "connection"]

    def _extract_quirks(self, personality_data: dict[str, Any]) -> list[str]:
        """Extract quirks from personality data."""
        quirks = []
        behavioral = personality_data.get("behavioral_patterns", {})

        if "perfectionism" in str(behavioral).lower():
            quirks.append("perfectionist tendencies")
        if "routine" in str(behavioral).lower():
            quirks.append("loves routine")
        if "spontaneous" in str(behavioral).lower():
            quirks.append("spontaneous decisions")

        return quirks or ["thoughtful pauses", "expressive gestures"]

    def _generate_behavior_scripts(
        self, personality_data: dict[str, Any], archetype: str
    ) -> dict[str, str]:
        """Generate behavior scripts for different situations."""
        scripts = {
            "greeting": f"Greets others in a {archetype} manner",
            "conflict": f"Handles conflict with {archetype} approach",
            "decision": f"Makes decisions using {archetype} style",
            "stress": f"Responds to stress with {archetype} patterns",
        }

        return scripts

    def get_status(self) -> dict[str, Any]:
        """Get personality engine status and statistics."""
        return {
            "initialized": self.initialized,
            "stats": self.stats,
            "llm_integration": self.llm is not None,
            "llm_only_mode": True,
            "llm_only_systems": "ENABLED",
            "personality_archetypes": list(self.personality_templates.keys()),
            "performance": {
                "avg_response_time_ms": self.stats["avg_response_time"],
                "total_llm_calls": self.stats["llm_calls"],
                "processing_success_rate": (
                    100.0 if self.stats["llm_calls"] == self.stats["total_processed"] else 0.0
                ),
            },
        }

    def _check_health(self) -> bool:
        """Check component health status."""
        try:
            # Check if engine is initialized
            if not self.initialized:
                return False

            # Check if LLM is available (required for this engine)
            if self.llm is None:
                return False  # type: ignore  # Defensive/fallback code

            # Check if we have personality templates
            if not self.personality_templates:
                return False

            return True
        except Exception:
            return False

    def _get_status_specific(self) -> dict[str, Any]:
        """Get personality engine specific status information."""
        return {
            "initialized": self.initialized,
            "llm_available": self.llm is not None,
            "llm_only_mode": True,
            "personality_archetypes_count": len(self.personality_templates),
            "personality_archetypes": list(self.personality_templates.keys()),
            "total_processed": self.stats["total_processed"],
            "llm_calls": self.stats["llm_calls"],
            "avg_response_time_ms": self.stats["avg_response_time"],
            "success_rate": (
                100.0 if self.stats["llm_calls"] == self.stats["total_processed"] else 0.0
            ),
        }

    def _do_initialize(self, config: dict[str, Any]) -> None:
        """Initialize the personality engine with the given configuration.

        This is the required abstract method implementation from ForgeComponent.
        """
        # The actual initialization is already done in __init__ and initialize()
        # This method satisfies the abstract base class requirement

    def _validate_config_specific(self, config: dict[str, Any]) -> bool:
        """Validate the configuration specific to this component.

        This is the required abstract method implementation from ForgeComponent.
        """
        # Check if LLM configuration is provided
        if "llm" not in config:
            return False

        # Check if LLM configuration is valid
        llm_config = config["llm"]
        if not isinstance(llm_config, dict):
            return False

        # Basic validation passed
        return True
