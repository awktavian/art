#!/usr/bin/env python3
"""
FORGE - Emotional Processor Module
Advanced emotional state processing and management.
GAIA Standard: No fallbacks, complete implementations only.
"""

import logging
import time
from typing import Any

try:  # pragma: no cover - optional heavy dependency
    import numpy as _np

    _NUMPY_IMPORT_ERROR: Exception | None = None
except Exception as _numpy_err:  # pragma: no cover
    _np: Any = None  # type: ignore[no-redef]
    _NUMPY_IMPORT_ERROR = _numpy_err

if _np is None:

    def _variance(values: list[float]) -> float:  # type: ignore  # Defensive/fallback code
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        return sum((val - mean) ** 2 for val in values) / len(values)

else:  # pragma: no cover - standard path

    def _variance(values: list[float]) -> float:
        return float(_np.var(values))


from ...forge_llm_base import (
    CharacterContext,
    LLMRequest,
)
from ...llm_service_adapter import KagamiOSLLMServiceAdapter
from ...schema import (
    CharacterRequest,
    EmotionalProfile,
    EmotionalState,
    PersonalityProfile,
)

logger = logging.getLogger("ForgeMatrix.EmotionalProcessor")


class EmotionalProcessor:
    """Professional emotional state processing and management."""

    def __init__(self) -> None:
        self.initialized = False
        # Use bounded cache with LRU eviction to prevent memory leaks
        from kagami.forge.utils.cache import MemoryCache

        self.emotion_cache = MemoryCache(name="emotions", max_size=200, default_ttl=1800)
        self.emotion_history: list[dict[str, Any]] = []
        self.stats = {
            "total_processed": 0,
            "avg_intensity": 0.0,
            "stability_score": 0.0,
        }

        # Initialize LLM for emotional analysis (respect fast test echo mode)
        self.llm = KagamiOSLLMServiceAdapter(  # type: ignore[call-arg]
            "qwen",
            provider="ollama",
            model_name="qwen3:235b-a22b",
            fast_model_name="qwen3:7b",
        )

        # Structured output client disabled (feature not available)
        self.structured_client = None

    async def initialize(self) -> None:
        """Initialize emotional processing system."""
        # Initialize LLM
        await self.llm.initialize()

        # Initialize structured client
        if self.structured_client:
            await self.structured_client.initialize()  # type: ignore  # Defensive/fallback code

        self.initialized = True
        logger.info("✅ Emotional processor system initialized with structured outputs")

    async def generate(
        self, request: CharacterRequest, personality_profile: PersonalityProfile
    ) -> EmotionalProfile:
        """Generate emotional profile from character request and personality."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # Create character context
            character_context = CharacterContext(
                character_id=request.request_id,
                name=getattr(request, "name", "Character"),
                description=request.concept,
            )

            # Generate emotional profile using LLM
            emotional_data = await self._generate_emotional_profile_llm(character_context)

            # Enhance with algorithmic emotional patterns
            enhanced_data = await self._enhance_with_big_five_emotions(
                emotional_data, personality_profile.big_five
            )

            # Create EmotionalProfile object
            emotional_profile = EmotionalProfile(
                base_mood=self._determine_base_mood(enhanced_data),
                emotional_range=enhanced_data.get("emotional_range", {}).get(
                    "emotional_breadth", 0.7
                ),
                mood_stability=enhanced_data.get("emotional_stability", 0.5),
                triggers=enhanced_data.get("trigger_patterns", {}),
                emotional_intelligence=enhanced_data.get("emotional_intelligence", 0.6),
                empathy_level=enhanced_data.get("empathy_level", 0.7),
            )

            self.stats["total_processed"] += 1
            generation_time = time.time() - start_time

            logger.info(f"Generated emotional profile in {generation_time * 1000:.2f}ms")

            return emotional_profile

        except Exception as e:
            logger.error(f"Emotional processing failed: {e}")
            raise

    async def _generate_emotional_profile_llm(
        self, character_context: CharacterContext
    ) -> dict[str, Any]:
        """Generate emotional profile using LLM with structured output.

        GAIA Standard: No fallbacks - requires valid LLM JSON response.
        """
        import json

        llm_request = LLMRequest(
            prompt=f"Generate emotional profile for character: {character_context.description}",
            context=character_context,
            temperature=0.7,
        )

        response_text = await self.llm.generate_text(
            llm_request.prompt,
            temperature=llm_request.temperature,
            max_tokens=llm_request.max_tokens,
        )

        # Parse response - require valid JSON from LLM
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
                f"Emotional profile generation failed: LLM returned invalid JSON. "
                f"Response: {response_text[:100]}... Error: {e}"
            ) from e

    async def _enhance_with_big_five_emotions(
        self, llm_data: dict[str, Any], big_five: dict[str, float]
    ) -> dict[str, Any]:
        """Enhance LLM data with Big Five algorithmic emotional patterns."""
        enhanced = llm_data.copy()

        # Add algorithmic enhancements
        enhanced["current_emotions"] = await self._generate_base_emotions(big_five)
        enhanced["emotional_intensity"] = await self._calculate_emotional_intensity(
            enhanced["current_emotions"], big_five
        )
        enhanced["emotional_range"] = await self._calculate_emotional_range(big_five)
        enhanced["trigger_patterns"] = await self._generate_trigger_patterns(big_five)
        enhanced["regulation_strategies"] = await self._generate_regulation_strategies(big_five)
        enhanced["expression_style"] = await self._generate_expression_style(big_five)
        enhanced["recovery_patterns"] = await self._generate_recovery_patterns(big_five)

        return enhanced

    def _determine_base_mood(self, emotional_data: dict[str, Any]) -> EmotionalState:
        """Determine base mood from emotional data."""
        current_emotions = emotional_data.get("current_emotions", {})

        if not current_emotions:
            return EmotionalState.NEUTRAL

        # Find dominant emotion
        dominant_emotion = max(current_emotions.items(), key=lambda x: x[1])
        emotion_name, _intensity = dominant_emotion

        # Map to EmotionalState enum
        emotion_mapping = {
            "joy": EmotionalState.HAPPY,
            "sadness": EmotionalState.SAD,
            "anger": EmotionalState.ANGRY,
            "fear": EmotionalState.FEARFUL,
            "surprise": EmotionalState.SURPRISED,
            "excitement": EmotionalState.EXCITED,
            "calm": EmotionalState.CALM,
        }

        return emotion_mapping.get(emotion_name, EmotionalState.NEUTRAL)

    async def process_emotional_state(
        self, personality_profile: dict[str, Any], context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Process and generate emotional state from personality profile."""
        if not self.initialized:
            await self.initialize()

        try:
            big_five = personality_profile.get("big_five", {})
            emotional_patterns = personality_profile.get("emotional_patterns", {})

            # Generate base emotional state
            base_emotions = await self._generate_base_emotions(big_five)

            # Apply contextual modifications
            if context:
                base_emotions = await self._apply_context_modifiers(base_emotions, context)

            # Generate emotional dynamics
            emotional_state = {
                "current_emotions": base_emotions,
                "emotional_intensity": await self._calculate_emotional_intensity(
                    base_emotions, big_five
                ),
                "emotional_stability": emotional_patterns.get("emotional_stability", 0.5),
                "emotional_range": await self._calculate_emotional_range(big_five),
                "trigger_patterns": await self._generate_trigger_patterns(big_five),
                "regulation_strategies": await self._generate_regulation_strategies(big_five),
                "expression_style": await self._generate_expression_style(big_five),
                "recovery_patterns": await self._generate_recovery_patterns(big_five),
            }

            self.stats["total_processed"] += 1
            return emotional_state

        except Exception as e:
            logger.error(f"Emotional processing failed: {e}")
            raise

    async def _generate_base_emotions(self, big_five: dict[str, float]) -> dict[str, float]:
        """Generate base emotional state from personality."""
        # Map personality traits to emotional tendencies
        neuroticism = big_five.get("neuroticism", 0.5)
        extraversion = big_five.get("extraversion", 0.5)
        agreeableness = big_five.get("agreeableness", 0.5)
        conscientiousness = big_five.get("conscientiousness", 0.5)
        openness = big_five.get("openness", 0.5)

        emotions = {
            "joy": max(0.1, extraversion + agreeableness * 0.3 - neuroticism * 0.2),
            "sadness": max(0.1, neuroticism * 0.6 + (1.0 - extraversion) * 0.3),
            "anger": max(0.1, neuroticism * 0.4 + (1.0 - agreeableness) * 0.5),
            "fear": max(0.1, neuroticism * 0.7 + (1.0 - conscientiousness) * 0.2),
            "surprise": max(0.1, openness + extraversion * 0.2),
            "trust": max(0.1, agreeableness + conscientiousness * 0.3),
            "anticipation": max(0.1, conscientiousness + extraversion * 0.2),
            "disgust": max(0.1, (1.0 - agreeableness) * 0.3 + neuroticism * 0.2),
        }

        # Normalize emotions
        total = sum(emotions.values())
        if total > 0:
            emotions = {k: v / total for k, v in emotions.items()}

        return emotions

    async def _apply_context_modifiers(
        self, base_emotions: dict[str, float], context: dict[str, Any]
    ) -> dict[str, float]:
        """Apply contextual modifiers to emotions."""
        modified_emotions = base_emotions.copy()

        # Social context
        if context.get("social_situation"):
            social_type = context["social_situation"]
            if social_type == "conflict":
                modified_emotions["anger"] *= 1.5
                modified_emotions["fear"] *= 1.2
            elif social_type == "celebration":
                modified_emotions["joy"] *= 1.4
                modified_emotions["surprise"] *= 1.2
            elif social_type == "loss":
                modified_emotions["sadness"] *= 1.6
                modified_emotions["fear"] *= 1.1

        # Stress level
        stress_level = context.get("stress_level", 0.5)
        if stress_level > 0.6:
            modified_emotions["fear"] *= 1.0 + stress_level * 0.3
            modified_emotions["anger"] *= 1.0 + stress_level * 0.2
            modified_emotions["joy"] *= 1.0 - stress_level * 0.3

        # Renormalize
        total = sum(modified_emotions.values())
        if total > 0:
            modified_emotions = {k: v / total for k, v in modified_emotions.items()}

        return modified_emotions

    async def _calculate_emotional_intensity(
        self, emotions: dict[str, float], big_five: dict[str, float]
    ) -> float:
        """Calculate overall emotional intensity."""
        neuroticism = big_five.get("neuroticism", 0.5)
        extraversion = big_five.get("extraversion", 0.5)

        # Base intensity from neuroticism and extraversion
        base_intensity = neuroticism * 0.6 + extraversion * 0.4

        # Modify by emotion variance
        emotion_variance = _variance(list(emotions.values()))
        intensity_modifier = emotion_variance * 2.0

        intensity = base_intensity + intensity_modifier
        return min(0.9, max(0.1, float(intensity)))

    async def _calculate_emotional_range(self, big_five: dict[str, float]) -> dict[str, float]:
        """Calculate emotional range and flexibility."""
        openness = big_five.get("openness", 0.5)
        neuroticism = big_five.get("neuroticism", 0.5)

        return {
            "emotional_breadth": min(0.9, openness + 0.2),
            "emotional_depth": min(0.9, neuroticism * 0.6 + openness * 0.4),
            "emotional_flexibility": min(0.9, openness + (1.0 - neuroticism) * 0.3),
            "emotional_complexity": min(0.9, openness * 0.7 + neuroticism * 0.3),
        }

    async def _generate_trigger_patterns(self, big_five: dict[str, float]) -> dict[str, Any]:
        """Generate emotional trigger patterns."""
        neuroticism = big_five.get("neuroticism", 0.5)
        agreeableness = big_five.get("agreeableness", 0.5)
        conscientiousness = big_five.get("conscientiousness", 0.5)

        triggers = {
            "criticism": {
                "intensity": min(0.9, neuroticism + 0.2),
                "primary_emotion": "anger" if agreeableness < 0.5 else "sadness",
                "duration": "moderate",
            },
            "failure": {
                "intensity": min(0.9, neuroticism + conscientiousness * 0.3),
                "primary_emotion": "sadness",
                "duration": "long" if conscientiousness > 0.6 else "moderate",
            },
            "rejection": {
                "intensity": min(0.9, neuroticism + (1.0 - agreeableness) * 0.2),
                "primary_emotion": "sadness",
                "duration": "long",
            },
            "success": {
                "intensity": min(0.9, conscientiousness + 0.3),
                "primary_emotion": "joy",
                "duration": "moderate",
            },
            "uncertainty": {
                "intensity": min(0.9, neuroticism + (1.0 - big_five.get("openness", 0.5)) * 0.3),
                "primary_emotion": "fear",
                "duration": "persistent",
            },
        }

        return triggers

    async def _generate_regulation_strategies(self, big_five: dict[str, float]) -> list[str]:
        """Generate emotional regulation strategies."""
        strategies = []

        conscientiousness = big_five.get("conscientiousness", 0.5)
        extraversion = big_five.get("extraversion", 0.5)
        openness = big_five.get("openness", 0.5)
        agreeableness = big_five.get("agreeableness", 0.5)

        if conscientiousness > 0.6:
            strategies.extend(["planning", "problem_solving", "goal_setting"])
        if extraversion > 0.6:
            strategies.extend(["social_support", "expression", "activity"])
        if openness > 0.6:
            strategies.extend(["reframing", "creative_expression", "mindfulness"])
        if agreeableness > 0.6:
            strategies.extend(["seeking_harmony", "empathy", "cooperation"])

        # Add some baseline strategies
        strategies.extend(["deep_breathing", "distraction", "self_talk"])

        return list(set(strategies))[:6]  # Return unique strategies, max 6

    async def _generate_expression_style(self, big_five: dict[str, float]) -> dict[str, Any]:
        """Generate emotional expression style."""
        extraversion = big_five.get("extraversion", 0.5)
        agreeableness = big_five.get("agreeableness", 0.5)
        neuroticism = big_five.get("neuroticism", 0.5)

        return {
            "expressiveness": min(0.9, extraversion + neuroticism * 0.3),
            "emotional_openness": min(0.9, extraversion + agreeableness * 0.2),
            "emotional_control": max(
                0.1, (1.0 - neuroticism) + big_five.get("conscientiousness", 0.5) * 0.3
            ),
            "vulnerability_comfort": min(0.9, agreeableness + extraversion * 0.2),
            "emotional_authenticity": min(0.9, agreeableness + (1.0 - neuroticism) * 0.2),
        }

    async def _generate_recovery_patterns(self, big_five: dict[str, float]) -> dict[str, Any]:
        """Generate emotional recovery patterns."""
        neuroticism = big_five.get("neuroticism", 0.5)
        extraversion = big_five.get("extraversion", 0.5)
        conscientiousness = big_five.get("conscientiousness", 0.5)

        return {
            "recovery_speed": max(0.1, (1.0 - neuroticism) + extraversion * 0.3),
            "resilience": max(0.1, conscientiousness + (1.0 - neuroticism) * 0.4),
            "bounce_back_tendency": min(0.9, extraversion + conscientiousness * 0.2),
            "emotional_memory": min(0.9, neuroticism + 0.2),
            "growth_from_adversity": min(
                0.9, big_five.get("openness", 0.5) + conscientiousness * 0.3
            ),
        }

    def get_status(self) -> dict[str, Any]:
        """Get emotional processor status."""
        return {
            "initialized": self.initialized,
            "cache_size": len(self.emotion_cache),  # type: ignore[arg-type]
            "history_length": len(self.emotion_history),
            "stats": self.stats,
        }
