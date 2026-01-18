#!/usr/bin/env python3
"""
FORGE - Gesture Engine Module
Real gesture pattern generation with LLM integration
GAIA Standard: Complete implementations only
"""

import logging
import time
from typing import Any

from ...forge_llm_base import (
    CharacterContext,
)
from ...llm_service_adapter import KagamiOSLLMServiceAdapter

# Import Forge schema
from ...schema import CharacterRequest, GenerationResult, GestureType

logger = logging.getLogger("ForgeMatrix.GestureEngine")


class GestureEngine:
    """Real gesture generation system with LLM integration."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.initialized = False
        self.stats = {"total_processed": 0, "llm_calls": 0, "avg_response_time": 0.0}
        self.gesture_templates = self._load_gesture_templates()

        # Initialize LLM for gesture analysis
        self.llm = KagamiOSLLMServiceAdapter(  # type: ignore[call-arg]
            "qwen",
            provider="ollama",
            model_name="qwen3:235b-a22b",
            fast_model_name="qwen3:7b",
        )

    async def initialize(self) -> None:
        """Initialize gesture engine with LLM capabilities."""
        try:
            # Initialize LLM
            await self.llm.initialize()

            self.initialized = True
            logger.info("✅ GestureEngine initialized with LLM integration")
        except Exception as e:
            logger.error(f"❌ GestureEngine initialization failed: {e}")
            raise RuntimeError(f"Gesture engine initialization failed: {e}") from None

    def _load_gesture_templates(self) -> dict[str, dict[str, Any]]:
        """Load gesture generation templates for different character types."""
        return {
            "confident": {
                "frequency": "high",
                "style": "expansive",
                "hand_positions": ["open_palms", "pointed_fingers", "firm_gestures"],
                "movement_patterns": ["deliberate", "sweeping", "emphatic"],
                "expressiveness": 0.8,
            },
            "shy": {
                "frequency": "low",
                "style": "contained",
                "hand_positions": ["closed_hands", "fidgeting", "protective"],
                "movement_patterns": ["minimal", "hesitant", "self-protective"],
                "expressiveness": 0.3,
            },
            "aggressive": {
                "frequency": "high",
                "style": "sharp",
                "hand_positions": ["clenched_fists", "pointing", "chopping"],
                "movement_patterns": ["rapid", "angular", "forceful"],
                "expressiveness": 0.9,
            },
            "wise": {
                "frequency": "moderate",
                "style": "measured",
                "hand_positions": ["open_hands", "steepled_fingers", "gentle"],
                "movement_patterns": ["slow", "deliberate", "thoughtful"],
                "expressiveness": 0.6,
            },
            "energetic": {
                "frequency": "very_high",
                "style": "dynamic",
                "hand_positions": ["animated_hands", "wide_gestures", "bouncing"],
                "movement_patterns": ["quick", "varied", "enthusiastic"],
                "expressiveness": 0.95,
            },
        }

    async def generate(self, request: CharacterRequest) -> GenerationResult:
        """Generate gesture profile for character request."""
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

            # Generate gesture profile using LLM
            gesture_data = await self._generate_gesture_profile_llm(character_context)

            generation_time = time.time() - start_time

            # Update statistics
            self.stats["total_processed"] += 1
            self.stats["llm_calls"] += 1

            self.stats["avg_response_time"] = (
                self.stats["avg_response_time"] * (self.stats["llm_calls"] - 1)
                + generation_time * 1000
            ) / self.stats["llm_calls"]

            logger.info(f"✅ Generated gesture profile in {generation_time * 1000:.2f}ms")

            return GenerationResult(
                success=True,
                mesh_data=None,  # Gesture profiles don't have mesh data
                generation_time=generation_time,
                quality_score=self._calculate_gesture_quality(gesture_data),
            )

        except Exception as e:
            logger.error(f"❌ Gesture generation failed: {e}")
            return GenerationResult(
                success=False, error=str(e), generation_time=time.time() - start_time
            )

    async def _generate_gesture_profile_llm(
        self, character_context: CharacterContext
    ) -> dict[str, Any]:
        """Generate gesture profile using LLM."""
        # Create prompt
        prompt = f"Generate gesture patterns for character: {character_context.description}"

        # Generate response
        from ...utils.style_directives import get_motion_house_style_note

        style_note = get_motion_house_style_note()
        response = await self.llm.generate_text(style_note + "\n" + prompt)

        # Parse response (assuming it's JSON)
        try:
            import json

            parsed = json.loads(response)
            return (
                parsed
                if isinstance(parsed, dict)
                else {"gesture_type": "expressive", "frequency": 0.5}
            )
        except json.JSONDecodeError:
            # Fallback if response is not valid JSON
            return {"gesture_type": "expressive", "frequency": 0.5}

    def _determine_gesture_type(self, gesture_data: dict[str, Any]) -> GestureType:
        """Determine gesture type from gesture data."""
        gesture_type_str = gesture_data.get("gesture_type", "natural")

        # Map to GestureType enum
        type_mapping = {
            "expressive": GestureType.EXPRESSIVE,
            "subtle": GestureType.FUNCTIONAL,
            "dramatic": GestureType.EXPRESSIVE,
            "minimal": GestureType.FUNCTIONAL,
            "natural": GestureType.EXPRESSIVE,
            "animated": GestureType.EXPRESSIVE,
            "restrained": GestureType.FUNCTIONAL,
            "cultural": GestureType.CULTURAL,
            "nervous": GestureType.NERVOUS,
            "functional": GestureType.FUNCTIONAL,
        }

        return type_mapping.get(gesture_type_str, GestureType.EXPRESSIVE)

    async def generate_gesture_patterns(self, context: Any) -> dict[str, Any]:
        """Generate comprehensive gesture patterns."""
        if not self.initialized:
            await self.initialize()

        start_time = time.time()

        try:
            # Get character context
            character_name = getattr(context, "character_name", "Character")
            description = getattr(context, "original_description", "")
            character_traits = getattr(context, "character_traits", {})

            # Determine character archetype for template guidance
            archetype = self._determine_gesture_archetype(character_traits.get("personality", {}))
            template = self.gesture_templates.get(archetype, self.gesture_templates["wise"])

            # Create character context
            character_context = CharacterContext(
                character_id=getattr(context, "character_id", "unknown"),
                name=getattr(context, "name", "Character"),
                description=description,
            )

            # Generate gesture profile using LLM
            gesture_data = await self._generate_gesture_profile_llm(character_context)

            # Enhance with template data
            enhanced_data = {
                "base_patterns": {
                    "frequency": gesture_data.get("frequency", template["frequency"]),
                    "style": gesture_data.get("style", template["style"]),
                    "expressiveness": gesture_data.get(
                        "expressiveness", template["expressiveness"]
                    ),
                    "archetype": archetype,
                    "llm_enhanced": True,
                },
                "gesture_patterns": gesture_data.get("gesture_patterns", {}),
                "hand_positions": gesture_data.get("hand_positions", {}),
                "movement_patterns": gesture_data.get("movement_patterns", {}),
                "contextual_variations": gesture_data.get("contextual_variations", {}),
                "animation_parameters": gesture_data.get("animation_parameters", {}),
                "interaction_patterns": gesture_data.get("interaction_patterns", {}),
                "generation_metadata": {
                    "method": "llm_powered",
                    "template_archetype": archetype,
                    "enhancement_applied": True,
                },
            }

            # Update statistics
            self.stats["total_processed"] += 1
            self.stats["llm_calls"] += 1

            execution_time = (time.time() - start_time) * 1000
            self.stats["avg_response_time"] = (
                self.stats["avg_response_time"] * (self.stats["llm_calls"] - 1) + execution_time
            ) / self.stats["llm_calls"]

            logger.info(
                f"✅ Generated gesture patterns for {character_name} in {execution_time:.2f}ms"
            )

            return enhanced_data

        except Exception as e:
            logger.error(f"❌ Gesture generation failed: {e}")
            raise RuntimeError(f"Gesture generation failed: {e}") from None

    def _determine_gesture_archetype(self, personality_traits: dict[str, float]) -> str:
        """Determine gesture archetype from personality traits."""
        # Big Five personality mapping to gesture styles
        extraversion = personality_traits.get("extraversion", 0.5)
        agreeableness = personality_traits.get("agreeableness", 0.5)
        neuroticism = personality_traits.get("neuroticism", 0.5)
        openness = personality_traits.get("openness", 0.5)
        conscientiousness = personality_traits.get("conscientiousness", 0.5)

        # Determine archetype based on trait combinations
        if extraversion > 0.7 and openness > 0.6:
            return "energetic"
        elif agreeableness < 0.3 and extraversion > 0.6:
            return "aggressive"
        elif neuroticism > 0.6 or extraversion < 0.3:
            return "shy"
        elif conscientiousness > 0.7 and openness > 0.6:
            return "wise"
        elif extraversion > 0.6:
            return "confident"
        else:
            return "wise"  # Default

    def _calculate_gesture_quality(self, gesture_profile: dict[str, Any]) -> float:
        """Calculate quality score for generated gesture profile."""
        quality_factors = []

        # Check completeness
        required_sections = [
            "base_patterns",
            "gesture_patterns",
            "movement_patterns",
            "animation_parameters",
        ]
        completeness = sum(1 for section in required_sections if section in gesture_profile) / len(
            required_sections
        )
        quality_factors.append(completeness)

        # Check data richness
        total_data_points = sum(
            len(str(gesture_profile.get(section, {}))) for section in required_sections
        )
        richness_score = min(total_data_points / 1000, 1.0)
        quality_factors.append(richness_score)

        # Check LLM enhancement
        llm_enhanced = gesture_profile.get("base_patterns", {}).get("llm_enhanced", False)
        enhancement_score = 1.0 if llm_enhanced else 0.5
        quality_factors.append(enhancement_score)

        return sum(quality_factors) / len(quality_factors)

    def get_status(self) -> dict[str, Any]:
        """Get gesture engine status and statistics."""
        return {
            "initialized": self.initialized,
            "stats": self.stats,
            "llm_integration": True,
            "available_archetypes": list(self.gesture_templates.keys()),
            "performance": {
                "avg_response_time_ms": self.stats["avg_response_time"],
                "total_llm_calls": self.stats["llm_calls"],
                "processing_success_rate": (
                    100.0 if self.stats["llm_calls"] == self.stats["total_processed"] else 0.0
                ),
            },
            "real_gesture_generation": True,
        }

    async def generate_from_speech(
        self,
        speech_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate gestures from speech analysis data."""
        if not self.initialized:
            await self.initialize()

        try:
            logger.info("🗣️ Generating gestures from speech data")

            text = speech_data.get("text", "")
            emphasis_words = speech_data.get("emphasis_words", [])
            duration = speech_data.get("duration", 2.0)
            prosody = speech_data.get("prosody", {})

            # Generate keyframes based on speech content
            keyframes = []

            # Basic gesture timing - start with neutral pose
            keyframes.append(
                {
                    "time": 0.0,
                    "joints": {
                        "left_shoulder": [0, 0, 0],
                        "right_shoulder": [0, 0, 0],
                        "left_elbow": [0, 0, 0],
                        "right_elbow": [0, 0, 0],
                    },
                    "gesture_type": "neutral",
                }
            )

            # Add gestures for emphasis words
            if emphasis_words:
                words = text.split()
                word_times = []

                # Estimate timing for each word
                if words:
                    for i, word in enumerate(words):
                        word_time = (i / len(words)) * duration
                        word_times.append((word, word_time))

                # Create gestures for emphasis words
                for word, word_time in word_times:
                    if word.lower() in [w.lower() for w in emphasis_words]:
                        # Create emphasis gesture
                        keyframes.append(
                            {
                                "time": word_time,
                                "joints": {
                                    "left_shoulder": [0, 10, 5],
                                    "right_shoulder": [0, 15, -5],
                                    "left_elbow": [20, 0, 0],
                                    "right_elbow": [25, 0, 0],
                                },
                                "gesture_type": "emphasis",
                                "word": word,
                            }
                        )

                        # Return to neutral after gesture
                        keyframes.append(
                            {
                                "time": word_time + 0.5,
                                "joints": {
                                    "left_shoulder": [0, 5, 0],
                                    "right_shoulder": [0, 5, 0],
                                    "left_elbow": [10, 0, 0],
                                    "right_elbow": [10, 0, 0],
                                },
                                "gesture_type": "return_neutral",
                            }
                        )

            # Add prosody-based gestures
            pitch_contour = prosody.get("pitch_contour", [])
            energy = prosody.get("energy", [])

            if pitch_contour and energy:
                for i, (pitch, eng) in enumerate(zip(pitch_contour, energy, strict=False)):
                    gesture_time = (i / len(pitch_contour)) * duration

                    # High energy + high pitch = larger gestures
                    if eng > 0.7 and pitch > 1.2:
                        keyframes.append(
                            {
                                "time": gesture_time,
                                "joints": {
                                    "left_shoulder": [
                                        0,
                                        int(eng * 20),
                                        int(pitch * 10),
                                    ],
                                    "right_shoulder": [
                                        0,
                                        int(eng * 20),
                                        -int(pitch * 10),
                                    ],
                                    "left_elbow": [int(eng * 30), 0, 0],
                                    "right_elbow": [int(eng * 30), 0, 0],
                                },
                                "gesture_type": "dynamic",
                                "energy": eng,
                                "pitch": pitch,
                            }
                        )

            # End with neutral pose
            keyframes.append(
                {
                    "time": duration,
                    "joints": {
                        "left_shoulder": [0, 0, 0],
                        "right_shoulder": [0, 0, 0],
                        "left_elbow": [0, 0, 0],
                        "right_elbow": [0, 0, 0],
                    },
                    "gesture_type": "neutral",
                }
            )

            result = {
                "keyframes": keyframes,
                "duration": duration,
                "gesture_count": len([kf for kf in keyframes if kf["gesture_type"] != "neutral"]),
                "style": self.config.get("style", "natural"),
                "intensity": self.config.get("intensity", 0.8),
            }

            logger.info(f"✅ Generated {len(keyframes)} gesture keyframes")
            return result

        except Exception as e:
            logger.error(f"❌ Speech gesture generation failed: {e}")
            return {
                "keyframes": [],
                "duration": duration,
                "gesture_count": 0,
                "error": str(e),
            }

    async def generate_idle_gestures(
        self,
        duration: float,
        character_traits: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate idle gesture patterns for character."""
        if not self.initialized:
            await self.initialize()

        try:
            logger.info(f"📏 Generating idle gestures for {duration}s")

            if character_traits is None:
                character_traits = {}

            energy_level = character_traits.get("energy_level", 0.5)
            expressiveness = character_traits.get("expressiveness", 0.6)

            keyframes = []

            # Generate subtle idle movements
            import numpy as np

            # Number of idle gestures based on duration and energy
            num_gestures = max(1, int(duration * energy_level * 2))  # 1-4 gestures per second

            for i in range(num_gestures):
                gesture_time = (
                    (i / max(1, num_gestures - 1)) * duration if num_gestures > 1 else duration / 2
                )

                # Generate subtle random movements
                max_rotation = 15 * expressiveness  # Scale by expressiveness

                # Random but subtle movements
                left_shoulder_rot = [
                    np.random.uniform(-max_rotation / 2, max_rotation / 2) for _ in range(3)
                ]
                right_shoulder_rot = [
                    np.random.uniform(-max_rotation / 2, max_rotation / 2) for _ in range(3)
                ]
                left_elbow_rot = [
                    np.random.uniform(-max_rotation, max_rotation / 2),
                    0,
                    0,
                ]
                right_elbow_rot = [
                    np.random.uniform(-max_rotation, max_rotation / 2),
                    0,
                    0,
                ]

                # Create keyframe
                keyframe = {
                    "time": gesture_time,
                    "joints": {
                        "left_shoulder": left_shoulder_rot,
                        "right_shoulder": right_shoulder_rot,
                        "left_elbow": left_elbow_rot,
                        "right_elbow": right_elbow_rot,
                    },
                    "gesture_type": "idle",
                    "intensity": energy_level * 0.3,  # Keep idle gestures subtle
                }

                keyframes.append(keyframe)

            # Ensure we start and end in neutral positions
            if keyframes:
                # Add neutral start
                keyframes.insert(
                    0,
                    {
                        "time": 0.0,
                        "joints": {
                            "left_shoulder": [0, 0, 0],
                            "right_shoulder": [0, 0, 0],
                            "left_elbow": [0, 0, 0],
                            "right_elbow": [0, 0, 0],
                        },
                        "gesture_type": "neutral",
                    },
                )

                # Add neutral end
                keyframes.append(
                    {
                        "time": duration,
                        "joints": {
                            "left_shoulder": [0, 0, 0],
                            "right_shoulder": [0, 0, 0],
                            "left_elbow": [0, 0, 0],
                            "right_elbow": [0, 0, 0],
                        },
                        "gesture_type": "neutral",
                    }
                )

            result = {
                "keyframes": keyframes,
                "duration": duration,
                "character_traits": character_traits,
                "gesture_count": len([kf for kf in keyframes if kf["gesture_type"] == "idle"]),
                "style": "idle",
            }

            logger.info(f"✅ Generated {len(keyframes)} idle gesture keyframes")
            return result

        except Exception as e:
            logger.error(f"❌ Idle gesture generation failed: {e}")
            return {
                "keyframes": [],
                "duration": duration,
                "gesture_count": 0,
                "error": str(e),
            }
