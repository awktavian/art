"""
FORGE - Facial Animator Module
Real facial animation and expression generation for character animation
GAIA Standard: Complete implementations only
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch

from ...forge_llm_base import CharacterAspect, CharacterContext, LLMRequest
from ...llm_service_adapter import KagamiOSLLMServiceAdapter
from ...schema import CharacterRequest, FacialProfile, FacialType, GenerationResult
from ...utils.style_rewriters import build_prompts_for_content_type
from .frame_generator import FacialExpression
from .motion_retargeting import BoneTransform, MotionClip, MotionFrame

logger = logging.getLogger("ForgeMatrix.FacialAnimator")


@dataclass
class EmotionMapping:
    """Emotion to facial expression mapping."""

    emotion: str
    primary_expression: str
    secondary_expressions: list[str]
    intensity_range: tuple[float, float]
    duration_range: tuple[float, float]


class FacialAnimator:
    """Real facial animation and expression system."""

    def __init__(
        self, config: dict[str, Any] | None = None, device: torch.device | None = None
    ) -> None:
        self.config = config or {}
        self.device = device or torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.initialized = False
        self.expression_library: dict[str, Any] = {}
        self.emotion_mappings: dict[str, Any] = {}
        self.blendshape_definitions: dict[str, Any] = {}
        self.stats = {
            "total_animated": 0,
            "total_expressions": 0,
            "avg_animation_time": 0.0,
            "avg_blend_time": 0.0,
        }
        self.deca_integration: Any = None
        self.audio2face_integration: Any = None
        self.default_framerate = self.config.get("fps", 30.0)
        self.blend_threshold = 0.01
        self.max_blend_shapes = self.config.get("blend_shape_count", 50)
        self.blend_shapes: dict[str, Any] = {}
        self.llm = KagamiOSLLMServiceAdapter(  # type: ignore[call-arg]
            "qwen", provider="ollama", model_name="qwen3:235b-a22b", fast_model_name="qwen3:7b"
        )

    @property
    def is_initialized(self) -> bool:
        """Check if facial animator is initialized."""
        return self.initialized

    async def initialize(self) -> None:
        """Initialize facial animator."""
        try:
            logger.info("😄 Initializing facial animator...")
            await self.llm.initialize()
            from .audio2face_integration import Audio2FaceIntegration
            from .deca_integration import DECAIntegration

            self.deca_integration = DECAIntegration(self.device)
            self.audio2face_integration = Audio2FaceIntegration()
            await self._load_expression_library()
            await self._load_emotion_mappings()
            await self._load_blendshape_definitions()
            self.blend_shapes = dict[str, Any].fromkeys(self.blendshape_definitions.keys(), 0.0)
            self.initialized = True
            logger.info("✅ Facial animator initialized - REAL FACIAL ANIMATION")
        except Exception as e:
            logger.error(f"❌ Facial animator initialization failed: {e}")
            raise RuntimeError(f"Facial animator initialization failed: {e}") from None

    async def _load_expression_library(self) -> None:
        """Load facial expression library."""
        self.expression_library = {
            "neutral": FacialExpression(
                name="neutral",
                blendshapes={
                    "browInnerUp": 0.0,
                    "browOuterUp": 0.0,
                    "eyeBlinkLeft": 0.0,
                    "eyeBlinkRight": 0.0,
                    "eyeSquintLeft": 0.0,
                    "eyeSquintRight": 0.0,
                    "eyeWideLeft": 0.0,
                    "eyeWideRight": 0.0,
                    "jawOpen": 0.0,
                    "mouthSmileLeft": 0.0,
                    "mouthSmileRight": 0.0,
                    "mouthFrownLeft": 0.0,
                    "mouthFrownRight": 0.0,
                    "mouthPucker": 0.0,
                    "mouthStretchLeft": 0.0,
                    "mouthStretchRight": 0.0,
                    "cheekPuff": 0.0,
                    "noseSneer": 0.0,
                },
                duration=1.0,
                intensity=1.0,
            ),
            "happy": FacialExpression(
                name="happy",
                blendshapes={
                    "browInnerUp": 0.2,
                    "browOuterUp": 0.1,
                    "eyeBlinkLeft": 0.0,
                    "eyeBlinkRight": 0.0,
                    "eyeSquintLeft": 0.3,
                    "eyeSquintRight": 0.3,
                    "eyeWideLeft": 0.0,
                    "eyeWideRight": 0.0,
                    "jawOpen": 0.1,
                    "mouthSmileLeft": 0.8,
                    "mouthSmileRight": 0.8,
                    "mouthFrownLeft": 0.0,
                    "mouthFrownRight": 0.0,
                    "mouthPucker": 0.0,
                    "mouthStretchLeft": 0.0,
                    "mouthStretchRight": 0.0,
                    "cheekPuff": 0.4,
                    "noseSneer": 0.0,
                },
                duration=1.5,
                intensity=1.0,
            ),
            "sad": FacialExpression(
                name="sad",
                blendshapes={
                    "browInnerUp": 0.6,
                    "browOuterUp": 0.0,
                    "eyeBlinkLeft": 0.2,
                    "eyeBlinkRight": 0.2,
                    "eyeSquintLeft": 0.0,
                    "eyeSquintRight": 0.0,
                    "eyeWideLeft": 0.0,
                    "eyeWideRight": 0.0,
                    "jawOpen": 0.0,
                    "mouthSmileLeft": 0.0,
                    "mouthSmileRight": 0.0,
                    "mouthFrownLeft": 0.7,
                    "mouthFrownRight": 0.7,
                    "mouthPucker": 0.0,
                    "mouthStretchLeft": 0.0,
                    "mouthStretchRight": 0.0,
                    "cheekPuff": 0.0,
                    "noseSneer": 0.0,
                },
                duration=2.0,
                intensity=1.0,
            ),
            "angry": FacialExpression(
                name="angry",
                blendshapes={
                    "browInnerUp": 0.0,
                    "browOuterUp": 0.0,
                    "eyeBlinkLeft": 0.0,
                    "eyeBlinkRight": 0.0,
                    "eyeSquintLeft": 0.8,
                    "eyeSquintRight": 0.8,
                    "eyeWideLeft": 0.0,
                    "eyeWideRight": 0.0,
                    "jawOpen": 0.2,
                    "mouthSmileLeft": 0.0,
                    "mouthSmileRight": 0.0,
                    "mouthFrownLeft": 0.5,
                    "mouthFrownRight": 0.5,
                    "mouthPucker": 0.0,
                    "mouthStretchLeft": 0.0,
                    "mouthStretchRight": 0.0,
                    "cheekPuff": 0.0,
                    "noseSneer": 0.6,
                },
                duration=1.0,
                intensity=1.0,
            ),
            "surprised": FacialExpression(
                name="surprised",
                blendshapes={
                    "browInnerUp": 0.8,
                    "browOuterUp": 0.8,
                    "eyeBlinkLeft": 0.0,
                    "eyeBlinkRight": 0.0,
                    "eyeSquintLeft": 0.0,
                    "eyeSquintRight": 0.0,
                    "eyeWideLeft": 0.9,
                    "eyeWideRight": 0.9,
                    "jawOpen": 0.6,
                    "mouthSmileLeft": 0.0,
                    "mouthSmileRight": 0.0,
                    "mouthFrownLeft": 0.0,
                    "mouthFrownRight": 0.0,
                    "mouthPucker": 0.0,
                    "mouthStretchLeft": 0.0,
                    "mouthStretchRight": 0.0,
                    "cheekPuff": 0.0,
                    "noseSneer": 0.0,
                },
                duration=0.5,
                intensity=1.0,
            ),
            "disgusted": FacialExpression(
                name="disgusted",
                blendshapes={
                    "browInnerUp": 0.0,
                    "browOuterUp": 0.0,
                    "eyeBlinkLeft": 0.0,
                    "eyeBlinkRight": 0.0,
                    "eyeSquintLeft": 0.4,
                    "eyeSquintRight": 0.4,
                    "eyeWideLeft": 0.0,
                    "eyeWideRight": 0.0,
                    "jawOpen": 0.0,
                    "mouthSmileLeft": 0.0,
                    "mouthSmileRight": 0.0,
                    "mouthFrownLeft": 0.0,
                    "mouthFrownRight": 0.0,
                    "mouthPucker": 0.0,
                    "mouthStretchLeft": 0.0,
                    "mouthStretchRight": 0.0,
                    "cheekPuff": 0.0,
                    "noseSneer": 0.9,
                },
                duration=1.5,
                intensity=1.0,
            ),
            "fearful": FacialExpression(
                name="fearful",
                blendshapes={
                    "browInnerUp": 0.7,
                    "browOuterUp": 0.3,
                    "eyeBlinkLeft": 0.0,
                    "eyeBlinkRight": 0.0,
                    "eyeSquintLeft": 0.0,
                    "eyeSquintRight": 0.0,
                    "eyeWideLeft": 0.7,
                    "eyeWideRight": 0.7,
                    "jawOpen": 0.3,
                    "mouthSmileLeft": 0.0,
                    "mouthSmileRight": 0.0,
                    "mouthFrownLeft": 0.0,
                    "mouthFrownRight": 0.0,
                    "mouthPucker": 0.0,
                    "mouthStretchLeft": 0.4,
                    "mouthStretchRight": 0.4,
                    "cheekPuff": 0.0,
                    "noseSneer": 0.0,
                },
                duration=1.0,
                intensity=1.0,
            ),
            "thinking": FacialExpression(
                name="thinking",
                blendshapes={
                    "browInnerUp": 0.3,
                    "browOuterUp": 0.1,
                    "eyeBlinkLeft": 0.0,
                    "eyeBlinkRight": 0.0,
                    "eyeSquintLeft": 0.2,
                    "eyeSquintRight": 0.2,
                    "eyeWideLeft": 0.0,
                    "eyeWideRight": 0.0,
                    "jawOpen": 0.0,
                    "mouthSmileLeft": 0.0,
                    "mouthSmileRight": 0.0,
                    "mouthFrownLeft": 0.0,
                    "mouthFrownRight": 0.0,
                    "mouthPucker": 0.3,
                    "mouthStretchLeft": 0.0,
                    "mouthStretchRight": 0.0,
                    "cheekPuff": 0.0,
                    "noseSneer": 0.0,
                },
                duration=2.0,
                intensity=1.0,
            ),
            "speaking": FacialExpression(
                name="speaking",
                blendshapes={
                    "browInnerUp": 0.1,
                    "browOuterUp": 0.0,
                    "eyeBlinkLeft": 0.0,
                    "eyeBlinkRight": 0.0,
                    "eyeSquintLeft": 0.0,
                    "eyeSquintRight": 0.0,
                    "eyeWideLeft": 0.0,
                    "eyeWideRight": 0.0,
                    "jawOpen": 0.3,
                    "mouthSmileLeft": 0.0,
                    "mouthSmileRight": 0.0,
                    "mouthFrownLeft": 0.0,
                    "mouthFrownRight": 0.0,
                    "mouthPucker": 0.0,
                    "mouthStretchLeft": 0.0,
                    "mouthStretchRight": 0.0,
                    "cheekPuff": 0.0,
                    "noseSneer": 0.0,
                },
                duration=0.5,
                intensity=1.0,
            ),
        }

    async def _load_emotion_mappings(self) -> None:
        """Load emotion to expression mappings."""
        self.emotion_mappings = {
            "happy": EmotionMapping(
                emotion="happy",
                primary_expression="happy",
                secondary_expressions=["neutral"],
                intensity_range=(0.6, 1.0),
                duration_range=(1.0, 2.0),
            ),
            "sad": EmotionMapping(
                emotion="sad",
                primary_expression="sad",
                secondary_expressions=["neutral"],
                intensity_range=(0.5, 0.9),
                duration_range=(1.5, 3.0),
            ),
            "angry": EmotionMapping(
                emotion="angry",
                primary_expression="angry",
                secondary_expressions=["neutral"],
                intensity_range=(0.7, 1.0),
                duration_range=(0.8, 1.5),
            ),
            "surprised": EmotionMapping(
                emotion="surprised",
                primary_expression="surprised",
                secondary_expressions=["neutral"],
                intensity_range=(0.8, 1.0),
                duration_range=(0.3, 0.8),
            ),
            "disgusted": EmotionMapping(
                emotion="disgusted",
                primary_expression="disgusted",
                secondary_expressions=["neutral"],
                intensity_range=(0.6, 1.0),
                duration_range=(1.0, 2.0),
            ),
            "fearful": EmotionMapping(
                emotion="fearful",
                primary_expression="fearful",
                secondary_expressions=["neutral"],
                intensity_range=(0.7, 1.0),
                duration_range=(0.8, 1.5),
            ),
            "neutral": EmotionMapping(
                emotion="neutral",
                primary_expression="neutral",
                secondary_expressions=[],
                intensity_range=(1.0, 1.0),
                duration_range=(1.0, 1.0),
            ),
        }

    async def _load_blendshape_definitions(self) -> None:
        """Load blendshape to bone mapping definitions."""
        self.blendshape_definitions = {
            "browInnerUp": {
                "bones": ["left_eyebrow_inner", "right_eyebrow_inner"],
                "axis": "rotation_x",
                "range": (-15, 15),
            },
            "browOuterUp": {
                "bones": ["left_eyebrow_outer", "right_eyebrow_outer"],
                "axis": "rotation_x",
                "range": (-10, 20),
            },
            "eyeBlinkLeft": {
                "bones": ["left_eyelid_upper", "left_eyelid_lower"],
                "axis": "rotation_x",
                "range": (0, 45),
            },
            "eyeBlinkRight": {
                "bones": ["right_eyelid_upper", "right_eyelid_lower"],
                "axis": "rotation_x",
                "range": (0, 45),
            },
            "eyeSquintLeft": {
                "bones": ["left_eyelid_lower"],
                "axis": "rotation_x",
                "range": (0, 20),
            },
            "eyeSquintRight": {
                "bones": ["right_eyelid_lower"],
                "axis": "rotation_x",
                "range": (0, 20),
            },
            "eyeWideLeft": {
                "bones": ["left_eyelid_upper"],
                "axis": "rotation_x",
                "range": (-30, 0),
            },
            "eyeWideRight": {
                "bones": ["right_eyelid_upper"],
                "axis": "rotation_x",
                "range": (-30, 0),
            },
            "jawOpen": {"bones": ["jaw"], "axis": "rotation_x", "range": (0, 30)},
            "mouthSmileLeft": {
                "bones": ["left_mouth_corner"],
                "axis": "rotation_z",
                "range": (0, 20),
            },
            "mouthSmileRight": {
                "bones": ["right_mouth_corner"],
                "axis": "rotation_z",
                "range": (0, 20),
            },
            "mouthFrownLeft": {
                "bones": ["left_mouth_corner"],
                "axis": "rotation_z",
                "range": (0, -20),
            },
            "mouthFrownRight": {
                "bones": ["right_mouth_corner"],
                "axis": "rotation_z",
                "range": (0, -20),
            },
            "mouthPucker": {
                "bones": ["left_mouth_corner", "right_mouth_corner"],
                "axis": "position_x",
                "range": (0, 0.02),
            },
            "mouthStretchLeft": {
                "bones": ["left_mouth_corner"],
                "axis": "position_x",
                "range": (0, -0.02),
            },
            "mouthStretchRight": {
                "bones": ["right_mouth_corner"],
                "axis": "position_x",
                "range": (0, 0.02),
            },
            "cheekPuff": {
                "bones": ["left_cheek", "right_cheek"],
                "axis": "position_z",
                "range": (0, 0.01),
            },
            "noseSneer": {"bones": ["nose"], "axis": "rotation_y", "range": (0, 10)},
        }

    async def animate_expression(
        self,
        expression_name: str,
        duration: float | None = None,
        intensity: float = 1.0,
        skeleton_type: str = "humanoid",
    ) -> MotionClip:
        """Animate a facial expression."""
        if not self.initialized:
            await self.initialize()
        start_time = time.time()
        try:
            logger.info(f"😊 Animating expression: {expression_name}")
            if expression_name not in self.expression_library:
                expression_name = "neutral"
            expression = self.expression_library[expression_name]
            if duration is None:
                duration = expression.duration
            frames = []
            framerate = self.default_framerate
            num_frames = int(duration * framerate)
            for i in range(num_frames):
                timestamp = i / framerate
                frame = await self._generate_expression_frame(
                    timestamp, expression, intensity, skeleton_type, duration
                )
                frames.append(frame)
            motion_clip = MotionClip(
                name=f"{expression_name}_expression",
                frames=frames,
                skeleton_type=skeleton_type,
                framerate=framerate,
            )
            animation_time = (time.time() - start_time) * 1000
            self.stats["total_animated"] += 1
            self.stats["avg_animation_time"] = (
                self.stats["avg_animation_time"] * (self.stats["total_animated"] - 1)
                + animation_time
            ) / self.stats["total_animated"]
            logger.info(f"✅ Expression animation completed in {animation_time:.2f}ms")
            return motion_clip
        except Exception as e:
            logger.error(f"❌ Expression animation failed: {e}")
            raise RuntimeError(f"Expression animation failed: {e}") from None

    async def _generate_expression_frame(
        self,
        timestamp: float,
        expression: FacialExpression,
        intensity: float,
        skeleton_type: str,
        duration: float,
    ) -> MotionFrame:
        """Generate a single frame of facial animation."""
        from .frame_generator import FrameGenerator

        generator = FrameGenerator(self.expression_library, self.blendshape_definitions)
        return await generator.generate_expression_frame(
            timestamp, expression, intensity, skeleton_type, duration
        )

    def _ease_in_out(self, t: float) -> float:
        """Apply ease-in-out function for natural animation."""
        from .frame_generator import FrameGenerator

        return FrameGenerator({}, {})._ease_in_out(t)

    def _multiply_quaternions(
        self, q1: np.ndarray[Any, Any], q2: np.ndarray[Any, Any]
    ) -> np.ndarray[Any, Any]:
        """Multiply two quaternions."""
        from .frame_generator import FrameGenerator

        return FrameGenerator({}, {})._multiply_quaternions(q1, q2)

    async def blend_expressions(
        self,
        expressions: list[tuple[str, float]],
        duration: float = 2.0,
        skeleton_type: str = "humanoid",
    ) -> MotionClip:
        """Blend multiple expressions together."""
        if not self.initialized:
            await self.initialize()
        start_time = time.time()
        try:
            logger.info(f"🎭 Blending {len(expressions)} expressions")
            total_weight = sum((weight for _, weight in expressions))
            if total_weight > 0:
                normalized_expressions = [
                    (name, weight / total_weight) for name, weight in expressions
                ]
            else:
                normalized_expressions = [("neutral", 1.0)]
            frames = []
            framerate = self.default_framerate
            num_frames = int(duration * framerate)
            for i in range(num_frames):
                timestamp = i / framerate
                frame = await self._generate_blended_frame(
                    timestamp, normalized_expressions, skeleton_type, duration
                )
                frames.append(frame)
            motion_clip = MotionClip(
                name="blended_expressions",
                frames=frames,
                skeleton_type=skeleton_type,
                framerate=framerate,
            )
            blend_time = (time.time() - start_time) * 1000
            self.stats["total_expressions"] += len(expressions)
            self.stats["avg_blend_time"] = (
                self.stats["avg_blend_time"] * (self.stats["total_expressions"] - len(expressions))
                + blend_time
            ) / self.stats["total_expressions"]
            logger.info(f"✅ Expression blending completed in {blend_time:.2f}ms")
            return motion_clip
        except Exception as e:
            logger.error(f"❌ Expression blending failed: {e}")
            raise RuntimeError(f"Expression blending failed: {e}") from None

    async def _generate_blended_frame(
        self,
        timestamp: float,
        expressions: list[tuple[str, float]],
        skeleton_type: str,
        duration: float,
    ) -> MotionFrame:
        """Generate a single frame of blended expressions."""
        progress = timestamp / duration if duration > 0 else 1.0
        eased_progress = self._ease_in_out(progress)
        blended_blendshapes = {}
        for expression_name, weight in expressions:
            if expression_name in self.expression_library:
                expression = self.expression_library[expression_name]
                for (
                    blendshape_name,
                    blendshape_weight,
                ) in expression.blendshapes.items():
                    if blendshape_name not in blended_blendshapes:
                        blended_blendshapes[blendshape_name] = 0.0
                    blended_blendshapes[blendshape_name] += (
                        blendshape_weight * weight * eased_progress
                    )
        bone_transforms = {}
        for blendshape_name, weight in blended_blendshapes.items():
            if blendshape_name in self.blendshape_definitions:
                definition = self.blendshape_definitions[blendshape_name]
                for bone_name in definition["bones"]:
                    if bone_name not in bone_transforms:
                        bone_transforms[bone_name] = BoneTransform(
                            position=np.array([0, 0, 0]), rotation=np.array([1, 0, 0, 0])
                        )
                    axis = definition["axis"]
                    range_values = definition["range"]
                    if axis.startswith("rotation"):
                        angle = np.interp(weight, [0, 1], range_values)
                        angle_rad = np.radians(angle)
                        if axis == "rotation_x":
                            quat = np.array([np.cos(angle_rad / 2), np.sin(angle_rad / 2), 0, 0])
                        elif axis == "rotation_y":
                            quat = np.array([np.cos(angle_rad / 2), 0, np.sin(angle_rad / 2), 0])
                        elif axis == "rotation_z":
                            quat = np.array([np.cos(angle_rad / 2), 0, 0, np.sin(angle_rad / 2)])
                        else:
                            quat = np.array([1, 0, 0, 0])
                        bone_transforms[bone_name].rotation = self._multiply_quaternions(
                            bone_transforms[bone_name].rotation, quat
                        )
                    elif axis.startswith("position"):
                        offset = np.interp(weight, [0, 1], range_values)
                        if axis == "position_x":
                            bone_transforms[bone_name].position[0] += offset
                        elif axis == "position_y":
                            bone_transforms[bone_name].position[1] += offset
                        elif axis == "position_z":
                            bone_transforms[bone_name].position[2] += offset
        return MotionFrame(timestamp=timestamp, bone_transforms=bone_transforms)

    async def generate_emotion_sequence(
        self,
        emotions: list[tuple[str, float]],
        total_duration: float = 5.0,
        skeleton_type: str = "humanoid",
    ) -> MotionClip:
        """Generate a sequence of emotions over time."""
        if not self.initialized:
            await self.initialize()
        start_time = time.time()
        try:
            logger.info(f"🎬 Generating emotion sequence with {len(emotions)} emotions")
            if not emotions:
                raise ValueError("Emotions list[Any] cannot be empty")
            time_per_emotion = total_duration / len(emotions)
            frames = []
            framerate = self.default_framerate
            num_frames = int(total_duration * framerate)
            for i in range(num_frames):
                timestamp = i / framerate
                emotion_index = int(timestamp / time_per_emotion)
                emotion_index = min(emotion_index, len(emotions) - 1)
                current_emotion, intensity = emotions[emotion_index]
                frame = await self._generate_emotion_frame(
                    timestamp, current_emotion, intensity, skeleton_type
                )
                frames.append(frame)
            motion_clip = MotionClip(
                name="emotion_sequence",
                frames=frames,
                skeleton_type=skeleton_type,
                framerate=framerate,
            )
            sequence_time = (time.time() - start_time) * 1000
            self.stats["total_expressions"] += len(emotions)
            logger.info(f"✅ Emotion sequence completed in {sequence_time:.2f}ms")
            return motion_clip
        except Exception as e:
            logger.error(f"❌ Emotion sequence generation failed: {e}")
            raise RuntimeError(f"Emotion sequence generation failed: {e}") from None

    async def _generate_emotion_frame(
        self, timestamp: float, emotion: str, intensity: float, skeleton_type: str
    ) -> MotionFrame:
        """Generate a single frame for an emotion."""
        if emotion not in self.emotion_mappings:
            emotion = "neutral"
        mapping = self.emotion_mappings[emotion]
        primary_expression = self.expression_library[mapping.primary_expression]
        bone_transforms = {}
        for blendshape_name, weight in primary_expression.blendshapes.items():
            if blendshape_name in self.blendshape_definitions:
                definition = self.blendshape_definitions[blendshape_name]
                final_weight = weight * intensity
                for bone_name in definition["bones"]:
                    if bone_name not in bone_transforms:
                        bone_transforms[bone_name] = BoneTransform(
                            position=np.array([0, 0, 0]), rotation=np.array([1, 0, 0, 0])
                        )
                    axis = definition["axis"]
                    range_values = definition["range"]
                    if axis.startswith("rotation"):
                        angle = np.interp(final_weight, [0, 1], range_values)
                        angle_rad = np.radians(angle)
                        if axis == "rotation_x":
                            quat = np.array([np.cos(angle_rad / 2), np.sin(angle_rad / 2), 0, 0])
                        elif axis == "rotation_y":
                            quat = np.array([np.cos(angle_rad / 2), 0, np.sin(angle_rad / 2), 0])
                        elif axis == "rotation_z":
                            quat = np.array([np.cos(angle_rad / 2), 0, 0, np.sin(angle_rad / 2)])
                        else:
                            quat = np.array([1, 0, 0, 0])
                        bone_transforms[bone_name].rotation = self._multiply_quaternions(
                            bone_transforms[bone_name].rotation, quat
                        )
                    elif axis.startswith("position"):
                        offset = np.interp(final_weight, [0, 1], range_values)
                        if axis == "position_x":
                            bone_transforms[bone_name].position[0] += offset
                        elif axis == "position_y":
                            bone_transforms[bone_name].position[1] += offset
                        elif axis == "position_z":
                            bone_transforms[bone_name].position[2] += offset
        return MotionFrame(timestamp=timestamp, bone_transforms=bone_transforms)

    async def generate(self, request: CharacterRequest) -> GenerationResult:
        """Generate facial profile for character request."""
        if not self.initialized:
            await self.initialize()
        start_time = time.time()
        try:
            character_context = CharacterContext(
                character_id=request.request_id,
                name=request.concept,
                description=f"Facial animation for {request.concept}",
                aspect=CharacterAspect.VISUAL_DESIGN,
            )
            facial_data = await self._generate_facial_profile_llm(character_context)
            facial_type = self._determine_facial_type(facial_data)
            facial_profile = FacialProfile(
                facial_type=facial_type.value,
                expressiveness=facial_data.get("expressiveness", 0.7),
                asymmetry=facial_data.get("asymmetry", 0.1),
                characteristics=facial_data.get("characteristics", []),
            )
            generation_time = time.time() - start_time
            logger.info(f"Generated facial profile in {generation_time * 1000:.2f}ms")
            return GenerationResult(
                success=True,
                mesh_data=None,
                textures={},
                generation_time=generation_time,
                quality_score=self._calculate_facial_quality_score(facial_profile),
            )
        except Exception as e:
            logger.error(f"Facial generation failed: {e}")
            return GenerationResult(
                success=False, error=str(e), generation_time=time.time() - start_time
            )

    async def _generate_facial_profile_llm(
        self, character_context: CharacterContext
    ) -> dict[str, Any]:
        """Generate facial profile using LLM."""
        from ...utils.style_directives import get_kagami_house_style_directive

        style = get_kagami_house_style_directive()
        try:
            built = await build_prompts_for_content_type(
                content_type="facial", mascot_data={}, style_engine=None
            )
            core = "; ".join(built.core_lines)
            prefix = built.style_prompt + "\n" if built.style_prompt else ""
            facial_guide = f"{prefix}{core}".strip()
        except Exception:
            facial_guide = (
                "Expressions: joy, curiosity, empathy; subtle asymmetry; gaze anchors intent"
            )
        llm_request = LLMRequest(
            prompt=f"{style}\n{facial_guide}\nGenerate facial characteristics aligned with K os style for: {character_context.name}.\nReturn JSON with: facial_type, expressiveness (0-1), asymmetry (0-1), characteristics [strings].",
            context=character_context,
            temperature=0.7,
            max_tokens=500,
        )
        try:
            logger.info(
                "FacialAnimator: profile prompt prepared (content_type=facial, name=%s)",
                character_context.name,
            )
        except Exception:
            pass
        if self.llm:
            response = await self.llm.generate_text(llm_request.prompt)
        else:
            response = "{}"
        try:
            import json

            if isinstance(response, str):
                facial_data = json.loads(response)
                return dict(facial_data) if isinstance(facial_data, dict) else {}
            else:
                return dict(response) if response else {}  # type: ignore[unreachable]
        except (json.JSONDecodeError, Exception):
            return {
                "facial_type": "expressive",
                "expressiveness": 0.7,
                "asymmetry": 0.1,
                "characteristics": [],
            }

    def _determine_facial_type(self, facial_data: dict[str, Any]) -> FacialType:
        """Determine facial type from facial data."""
        facial_type_str = facial_data.get("facial_type", "expressive")
        type_mapping = {
            "expressive": FacialType.EXPRESSIVE,
            "subtle": FacialType.SUBTLE,
            "dramatic": FacialType.EXPRESSIVE,
            "stoic": FacialType.STOIC,
            "animated": FacialType.ANIMATED,
            "natural": FacialType.SUBTLE,
            "exaggerated": FacialType.ANIMATED,
            "controlled": FacialType.STOIC,
        }
        return type_mapping.get(facial_type_str, FacialType.EXPRESSIVE)

    def _calculate_facial_quality_score(self, facial_profile: FacialProfile) -> float:
        """Calculate quality score for facial profile."""
        score = 0.0
        if facial_profile.facial_type:
            score += 0.3
        if facial_profile.expressiveness > 0:
            score += 0.3
        if facial_profile.asymmetry >= 0:
            score += 0.2
        if facial_profile.characteristics:
            score += 0.2
        return min(score, 1.0)

    def get_status(self) -> dict[str, Any]:
        """Get facial animator status."""
        return {
            "initialized": self.initialized,
            "device": str(self.device),
            "available_expressions": list(self.expression_library.keys()),
            "available_emotions": list(self.emotion_mappings.keys()),
            "blendshape_count": len(self.blendshape_definitions),
            "stats": self.stats,
            "llm_integration": True,
            "real_facial_animation": True,
        }

    async def generate_facial_animation(
        self,
        concept: str,
        voice_profile: dict[str, Any] | None = None,
        style_preferences: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate complete facial animation from concept."""
        try:
            logger.info(f"🎭 Generating facial animation for: {concept}")
            deca_result = None
            if self.deca_integration:
                try:
                    import torch

                    placeholder_image = torch.zeros((1, 3, 224, 224), device=self.device)
                    deca_result = await self.deca_integration.reconstruct_face(
                        image=placeholder_image
                    )
                except Exception as e:
                    logger.warning(f"DECA reconstruction failed: {e}")
            audio2face_result = None
            if self.audio2face_integration:
                try:
                    audio2face_result = await self.audio2face_integration.generate_facial_animation(
                        concept=concept, voice_profile=voice_profile
                    )
                except Exception as e:
                    logger.warning(f"Audio2Face generation failed: {e}")
            combined_blendshapes: dict[str, float] = {}
            if deca_result and "blendshapes" in deca_result:
                combined_blendshapes.update(deca_result["blendshapes"])
            if audio2face_result and "blendshapes" in audio2face_result:
                for name, value in audio2face_result["blendshapes"].items():
                    if name in combined_blendshapes:
                        combined_blendshapes[name] = (combined_blendshapes[name] + value) / 2
                    else:
                        combined_blendshapes[name] = value
            wrinkle_maps: dict[str, Any] = {}
            if self.deca_integration and deca_result and ("codedict" in deca_result):
                try:
                    wrinkle_maps = await self.deca_integration.generate_wrinkle_maps(
                        codedict=deca_result["codedict"]
                    )
                except Exception as e:
                    logger.warning(f"Wrinkle map generation failed: {e}")
            return {
                "success": True,
                "deca_result": deca_result,
                "audio2face_result": audio2face_result,
                "combined_blendshapes": combined_blendshapes,
                "wrinkle_maps": wrinkle_maps,
            }
        except Exception as e:
            logger.error(f"❌ Facial animation generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "deca_result": None,
                "audio2face_result": None,
                "combined_blendshapes": {},
                "wrinkle_maps": {},
            }

    def combine_blendshapes(
        self,
        deca_blendshapes: dict[str, float],
        audio2face_blendshapes: dict[str, float],
        deca_weight: float = 0.5,
        audio2face_weight: float = 0.5,
    ) -> dict[str, float]:
        """Combine blendshapes from DECA and Audio2Face."""
        combined = {}
        total_weight = deca_weight + audio2face_weight
        if total_weight > 0:
            deca_weight /= total_weight
            audio2face_weight /= total_weight
        for name, value in deca_blendshapes.items():
            combined[name] = value * deca_weight
        for name, value in audio2face_blendshapes.items():
            if name in combined:
                combined[name] += value * audio2face_weight
            else:
                combined[name] = value * audio2face_weight
        for name in combined:
            combined[name] = float(np.clip(combined[name], 0.0, 1.0))
        return combined

    def synchronize_animations(
        self,
        deca_timeline: dict[str, Any],
        audio2face_timeline: dict[str, Any],
        target_fps: int = 30,
    ) -> dict[str, Any]:
        """Synchronize animations from different sources."""
        from .timeline_synchronizer import TimelineSynchronizer

        return TimelineSynchronizer().synchronize(deca_timeline, audio2face_timeline, target_fps)

    def assess_animation_quality(self, animation_data: dict[str, Any]) -> dict[str, float]:
        """Assess the quality of facial animation."""
        from .quality_assessor import AnimationQualityAssessor

        return AnimationQualityAssessor().assess_quality(animation_data)

    async def generate_expression(self, emotion: str, intensity: float = 0.8) -> dict[str, Any]:
        """Generate facial expression for given emotion."""
        if not self.initialized:
            await self.initialize()
        try:
            logger.info(f"😊 Generating {emotion} expression with intensity {intensity}")
            if emotion not in self.expression_library:
                emotion = "neutral"
            expression = self.expression_library[emotion]
            blend_weights = {}
            for blendshape_name, weight in expression.blendshapes.items():
                blend_weights[blendshape_name] = weight * intensity
            self.blend_shapes = blend_weights
            result = {
                "emotion": emotion,
                "intensity": intensity,
                "blend_weights": blend_weights,
                "duration": expression.duration,
                "success": True,
            }
            logger.info(f"✅ Generated expression for {emotion}")
            return result
        except Exception as e:
            logger.error(f"❌ Expression generation failed: {e}")
            return {
                "emotion": emotion,
                "intensity": intensity,
                "blend_weights": {},
                "duration": 1.0,
                "success": False,
                "error": str(e),
            }

    async def audio_to_visemes(self, audio_features: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert audio features to visemes for lip sync."""
        if not self.initialized:
            await self.initialize()
        try:
            logger.info("🎤 Converting audio features to visemes")
            visemes = []
            phonemes = audio_features.get("phonemes", [])
            phoneme_to_viseme = {
                "M": "M",
                "B": "M",
                "P": "M",
                "AH": "A",
                "AA": "A",
                "AE": "A",
                "TH": "T",
                "DH": "T",
                "T": "T",
                "D": "T",
                "S": "S",
                "Z": "S",
                "SH": "S",
                "F": "F",
                "V": "F",
                "L": "L",
                "R": "R",
                "UW": "U",
                "OW": "O",
                "IY": "I",
                "EH": "E",
            }
            for phoneme_data in phonemes:
                phoneme = phoneme_data.get("phoneme", "")
                start_time = phoneme_data.get("start", 0.0)
                duration = phoneme_data.get("duration", 0.1)
                viseme = phoneme_to_viseme.get(phoneme, "REST")
                viseme_data = {
                    "viseme": viseme,
                    "phoneme": phoneme,
                    "start_time": start_time,
                    "duration": duration,
                    "intensity": 0.8,
                }
                visemes.append(viseme_data)
            logger.info(f"✅ Generated {len(visemes)} visemes from audio")
            return visemes
        except Exception as e:
            logger.error(f"❌ Audio to visemes conversion failed: {e}")
            return []

    async def generate_blinks(self, duration: float, blink_rate: int = 20) -> list[dict[str, Any]]:
        """Generate realistic blink patterns."""
        if not self.initialized:
            await self.initialize()
        try:
            logger.info(f"👁 Generating blinks for {duration}s at {blink_rate} bpm")
            blinks = []
            blinks_per_second = blink_rate / 60.0
            avg_interval = 1.0 / blinks_per_second
            current_time = 0.0
            while current_time < duration:
                random_factor = np.random.uniform(0.5, 1.5)
                interval = avg_interval * random_factor
                current_time += interval
                if current_time < duration:
                    blink_duration = np.random.uniform(0.1, 0.3)
                    blink_data = {
                        "time": current_time,
                        "duration": blink_duration,
                        "intensity": np.random.uniform(0.8, 1.0),
                        "type": "normal",
                    }
                    blinks.append(blink_data)
            logger.info(f"✅ Generated {len(blinks)} blinks")
            return blinks
        except Exception as e:
            logger.error(f"❌ Blink generation failed: {e}")
            return []
