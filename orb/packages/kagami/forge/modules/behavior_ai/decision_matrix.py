#!/usr/bin/env python3
"""
FORGE - Decision Matrix Module
Advanced decision-making pattern analysis and generation.
GAIA Standard: No fallbacks, complete implementations only.
"""

import logging
import time
from typing import Any

from ...forge_llm_base import (
    CharacterContext,
    LLMRequest,
)
from ...llm_service_adapter import KagamiOSLLMServiceAdapter

# Import Forge schema
from ...schema import CharacterRequest, PersonalityProfile

logger = logging.getLogger("ForgeMatrix.DecisionMatrix")


class DecisionMatrix:
    """Professional decision-making pattern analysis and generation."""

    def __init__(self) -> None:
        self.initialized = False
        # Use bounded cache with LRU eviction to prevent memory leaks
        from kagami.forge.utils.cache import MemoryCache

        self.decision_cache = MemoryCache(name="decision_matrix", max_size=200, default_ttl=600)
        self.stats = {"total_decisions": 0, "pattern_matches": 0, "avg_complexity": 0.0}

        # Initialize LLM for decision analysis
        self.llm = KagamiOSLLMServiceAdapter(  # type: ignore[call-arg]
            "qwen",
            provider="ollama",
            model_name="qwen3:235b-a22b",
            fast_model_name="qwen3:7b",
        )

    async def initialize(self) -> None:
        """Initialize decision matrix system."""
        # Initialize LLM
        await self.llm.initialize()

        self.initialized = True
        logger.info("Decision matrix system initialized")

    async def generate(
        self, request: CharacterRequest, personality_profile: PersonalityProfile
    ) -> dict[str, Any]:
        """Generate decision-making patterns from personality profile."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # Create character context
            character_context = CharacterContext(
                character_id=request.request_id,
                name=request.concept,
                description=request.concept,
            )

            # Generate decision patterns using LLM
            patterns = await self._generate_decision_patterns_llm(
                character_context, personality_profile
            )

            # Enhance with algorithmic patterns
            enhanced_patterns = await self._enhance_with_big_five_patterns(
                patterns, personality_profile.big_five
            )

            self.stats["total_decisions"] += 1
            generation_time = time.time() - start_time

            logger.info(f"Generated decision patterns in {generation_time * 1000:.2f}ms")

            return enhanced_patterns

        except Exception as e:
            logger.error(f"Decision pattern generation failed: {e}")
            raise

    async def _generate_decision_patterns_llm(
        self,
        character_context: CharacterContext,
        personality_profile: PersonalityProfile,
    ) -> dict[str, Any]:
        """Generate decision patterns using LLM."""
        # Create LLM request
        llm_request = LLMRequest(
            prompt=f"Generate decision-making patterns for character: {character_context.name}",
            context=character_context,
            temperature=0.7,
            max_tokens=1000,
        )

        # Generate response
        response_text = await self.llm.generate_text(
            llm_request.prompt,
            temperature=llm_request.temperature,
            max_tokens=llm_request.max_tokens,
        )

        # Parse response - require valid JSON from LLM
        import json

        try:
            parsed_response = json.loads(response_text)
            if isinstance(parsed_response, dict):
                return parsed_response
            else:
                raise ValueError(
                    f"LLM returned non-dict[str, Any] JSON: {type(parsed_response).__name__}"
                )
        except json.JSONDecodeError as e:
            # GAIA Standard: No fallbacks - require valid LLM response
            logger.error(f"LLM returned non-JSON response: {response_text[:200]}...")
            raise RuntimeError(
                f"Decision pattern generation failed: LLM returned invalid JSON. "
                f"Response: {response_text[:100]}... Error: {e}"
            ) from e

    async def _enhance_with_big_five_patterns(
        self, llm_patterns: dict[str, Any], big_five: dict[str, float]
    ) -> dict[str, Any]:
        """Enhance LLM patterns with Big Five algorithmic patterns."""
        enhanced = llm_patterns.copy()

        # Add algorithmic enhancements
        enhanced["decision_style"] = await self._determine_decision_style(big_five)
        enhanced["risk_assessment"] = await self._generate_risk_patterns(big_five)
        enhanced["information_gathering"] = await self._generate_info_patterns(big_five)
        enhanced["time_pressure_response"] = await self._generate_time_pressure_patterns(big_five)
        enhanced["group_vs_individual"] = await self._generate_group_decision_patterns(big_five)
        enhanced["value_priorities"] = await self._generate_value_priorities(big_five)
        enhanced["decision_confidence"] = await self._generate_confidence_patterns(big_five)

        return enhanced

    async def generate_decision_patterns(
        self, personality_profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate decision-making patterns from personality profile."""
        if not self.initialized:
            await self.initialize()

        try:
            big_five = personality_profile.get("big_five", {})

            # Generate decision patterns
            patterns = {
                "decision_style": await self._determine_decision_style(big_five),
                "risk_assessment": await self._generate_risk_patterns(big_five),
                "information_gathering": await self._generate_info_patterns(big_five),
                "time_pressure_response": await self._generate_time_pressure_patterns(big_five),
                "group_vs_individual": await self._generate_group_decision_patterns(big_five),
                "value_priorities": await self._generate_value_priorities(big_five),
                "decision_confidence": await self._generate_confidence_patterns(big_five),
            }

            self.stats["total_decisions"] += 1
            return patterns

        except Exception as e:
            logger.error(f"Decision pattern generation failed: {e}")
            raise

    async def _determine_decision_style(self, big_five: dict[str, float]) -> dict[str, Any]:
        """Determine primary decision-making style."""
        conscientiousness = big_five.get("conscientiousness", 0.5)
        openness = big_five.get("openness", 0.5)
        neuroticism = big_five.get("neuroticism", 0.5)

        if conscientiousness > 0.6 and openness > 0.6:
            style = "systematic_creative"
        elif conscientiousness > 0.6:
            style = "analytical_systematic"
        elif openness > 0.6:
            style = "intuitive_creative"
        elif neuroticism > 0.6:
            style = "cautious_deliberative"
        else:
            style = "balanced_pragmatic"

        return {
            "primary_style": style,
            "analytical_weight": min(0.9, conscientiousness + 0.2),
            "intuitive_weight": min(0.9, openness + 0.2),
            "emotional_weight": min(0.9, neuroticism + 0.1),
        }

    async def _generate_risk_patterns(self, big_five: dict[str, float]) -> dict[str, Any]:
        """Generate risk assessment patterns."""
        openness = big_five.get("openness", 0.5)
        conscientiousness = big_five.get("conscientiousness", 0.5)
        neuroticism = big_five.get("neuroticism", 0.5)

        base_risk_tolerance = openness - (neuroticism * 0.7) + (conscientiousness * 0.3)
        risk_tolerance = max(0.1, min(0.9, base_risk_tolerance))

        return {
            "risk_tolerance": risk_tolerance,
            "risk_assessment_thoroughness": min(0.9, conscientiousness + neuroticism * 0.5),
            "risk_mitigation_preference": min(0.9, conscientiousness + neuroticism * 0.3),
            "uncertainty_comfort": max(0.1, openness - neuroticism * 0.5),
        }

    async def _generate_info_patterns(self, big_five: dict[str, float]) -> dict[str, Any]:
        """Generate information gathering patterns."""
        openness = big_five.get("openness", 0.5)
        conscientiousness = big_five.get("conscientiousness", 0.5)

        return {
            "information_depth": min(0.9, conscientiousness + openness * 0.4),
            "source_diversity": min(0.9, openness + 0.2),
            "verification_thoroughness": min(0.9, conscientiousness + 0.1),
            "information_speed": max(0.1, 1.0 - conscientiousness * 0.6),
        }

    async def _generate_time_pressure_patterns(self, big_five: dict[str, float]) -> dict[str, Any]:
        """Generate time pressure response patterns."""
        conscientiousness = big_five.get("conscientiousness", 0.5)
        neuroticism = big_five.get("neuroticism", 0.5)
        extraversion = big_five.get("extraversion", 0.5)

        return {
            "time_pressure_tolerance": max(0.1, extraversion - neuroticism * 0.5),
            "quality_vs_speed_preference": min(0.9, conscientiousness + 0.2),
            "stress_decision_quality": max(0.2, 1.0 - neuroticism * 0.8),
            "deadline_response_style": ("proactive" if conscientiousness > 0.6 else "reactive"),
        }

    async def _generate_group_decision_patterns(self, big_five: dict[str, float]) -> dict[str, Any]:
        """Generate group vs individual decision patterns."""
        extraversion = big_five.get("extraversion", 0.5)
        agreeableness = big_five.get("agreeableness", 0.5)

        return {
            "group_input_preference": min(0.9, extraversion + agreeableness * 0.5),
            "consensus_seeking": min(0.9, agreeableness + 0.2),
            "leadership_tendency": min(0.9, extraversion + (1.0 - agreeableness) * 0.3),
            "independent_decision_comfort": max(0.1, 1.0 - agreeableness * 0.7),
        }

    async def _generate_value_priorities(self, big_five: dict[str, float]) -> dict[str, Any]:
        """Generate value-based decision priorities."""
        values = {}

        # Map personality to values
        values["fairness"] = big_five.get("agreeableness", 0.5)
        values["efficiency"] = big_five.get("conscientiousness", 0.5)
        values["innovation"] = big_five.get("openness", 0.5)
        values["harmony"] = big_five.get("agreeableness", 0.5)
        values["achievement"] = big_five.get("conscientiousness", 0.5)
        values["security"] = max(0.1, 1.0 - big_five.get("openness", 0.5) * 0.5)

        # Normalize values
        total = sum(values.values())
        if total > 0:
            values = {k: v / total for k, v in values.items()}

        return values

    async def _generate_confidence_patterns(self, big_five: dict[str, float]) -> dict[str, Any]:
        """Generate decision confidence patterns."""
        conscientiousness = big_five.get("conscientiousness", 0.5)
        neuroticism = big_five.get("neuroticism", 0.5)
        extraversion = big_five.get("extraversion", 0.5)

        return {
            "decision_confidence": max(
                0.2, extraversion - neuroticism * 0.6 + conscientiousness * 0.3
            ),
            "second_guessing_tendency": min(0.8, neuroticism + (1.0 - conscientiousness) * 0.3),
            "commitment_strength": min(0.9, conscientiousness + extraversion * 0.2),
            "adaptation_willingness": min(0.9, big_five.get("openness", 0.5) + 0.2),
        }

    def get_status(self) -> dict[str, Any]:
        """Get decision matrix status."""
        return {
            "initialized": self.initialized,
            "cache_size": len(self.decision_cache),  # type: ignore[arg-type]
            "stats": self.stats,
        }
