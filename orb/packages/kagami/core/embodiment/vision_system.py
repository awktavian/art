"""Vision System - Visual Perception and Understanding.

This module is a thin, stable interface for "vision" inside the embodied
subsystem. It uses the SOTA unified vision stack (`UnifiedVisionModule`) and
does NOT fabricate "fallback" features or detections. If SOTA vision is disabled
or unavailable, callers must handle the error explicitly.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DetectedObject:
    """An object detected in an image."""

    label: str
    confidence: float
    bounding_box: tuple[int, int, int, int]  # x1, y1, x2, y2
    attributes: dict[str, Any]


@dataclass
class VisionPerception:
    """Complete visual perception of a scene."""

    features: Any  # Visual features (embedding)
    objects: list[DetectedObject]
    scene_description: str
    relationships: list[dict[str, Any]]  # Spatial relationships
    timestamp: datetime
    confidence: float


class VisionSystem:
    """Visual perception and understanding system.

    Pipeline:
    1. Load image
    2. Extract visual features (DINOv2)
    3. Detect objects (Florence-2)
    4. Understand scene (Florence-2 captioning)
    5. Extract spatial relationships
    """

    def __init__(self) -> None:
        """Initialize vision system."""
        self.scene_memory: list[VisionPerception] = []
        self._sota_vision: Any = None  # UnifiedVisionModule (lazy)

        logger.info("👁️ Vision system initialized")

    def _should_use_sota(self) -> bool:
        """Whether to use the SOTA unified vision stack.

        Default: enabled in full mode, disabled in test mode.
        """
        from kagami.core.boot_mode import is_test_mode

        if is_test_mode():
            return False
        return os.getenv("KAGAMI_VISION_USE_SOTA", "1").lower() not in {"0", "false", "no", "off"}

    def _get_sota_vision(self) -> Any | None:
        """Lazy-load UnifiedVisionModule (best-effort)."""
        if self._sota_vision is not None:
            return self._sota_vision
        from kagami.core.multimodal.vision import get_unified_vision_module

        self._sota_vision = get_unified_vision_module()
        return self._sota_vision

    def _to_pil(self, image: np.ndarray) -> Any:
        """Convert numpy image to PIL.Image (RGB)."""
        from PIL import Image as PILImage

        if image.dtype != np.uint8:
            # Best-effort conversion; clamp to [0,255]
            arr = np.clip(image, 0, 255).astype(np.uint8)
        else:
            arr = image
        return PILImage.fromarray(arr).convert("RGB")

    async def perceive(self, image_input: str | bytes | np.ndarray) -> VisionPerception:
        """Process visual input and understand the scene.

        Args:
            image_input: Image (path, bytes, or numpy array)

        Returns:
            Complete visual perception
        """
        logger.info("👁️ Perceiving visual input...")

        try:
            # Load image
            image = self._load_image(image_input)

            # Extract visual features
            features = await self._extract_features(image)

            # Detect objects
            objects = await self._detect_objects(image)

            # Describe scene using LLM
            scene_description = await self._describe_scene(image, objects)

            # Extract spatial relationships
            relationships = self._extract_spatial_relationships(objects)

            # Calculate overall confidence
            if objects:
                avg_confidence = sum(obj.confidence for obj in objects) / len(objects)
            else:
                avg_confidence = 0.5

            perception = VisionPerception(
                features=features,
                objects=objects,
                scene_description=scene_description,
                relationships=relationships,
                timestamp=datetime.now(),
                confidence=avg_confidence,
            )

            # Store in scene memory (last 100 perceptions)
            self.scene_memory.append(perception)
            if len(self.scene_memory) > 100:
                self.scene_memory = self.scene_memory[-100:]

            logger.info(
                f"👁️ Perceived: {len(objects)} objects, "
                f"confidence={avg_confidence:.2f}, "
                f"description: {scene_description[:50]}..."
            )

            return perception

        except Exception as e:
            logger.error(f"Vision perception failed: {e}", exc_info=True)
            raise

    async def act_on_vision(self, perception: VisionPerception, intent: str) -> dict[str, Any]:
        """Decide what action to take based on visual perception.

        Args:
            perception: Visual perception
            intent: What we're trying to accomplish

        Returns:
            Action to take
        """
        logger.info(f"👁️ Deciding action based on vision for intent: {intent}")

        try:
            # Use LLM to decide action based on what we see
            from kagami.core.services.llm.service import KagamiOSLLMService

            llm = KagamiOSLLMService()

            # Create prompt with visual context
            objects_str = ", ".join(
                [f"{obj.label} ({obj.confidence:.1%})" for obj in perception.objects]
            )
            relationships_str = "; ".join(
                [
                    f"{r.get('object1')} {r.get('relation')} {r.get('object2')}"
                    for r in perception.relationships[:5]
                ]
            )

            prompt = f"""I can see the following:

Scene: {perception.scene_description}

Objects detected:
{objects_str}

Spatial relationships:
{relationships_str}

My intent: {intent}

Based on what I see, what action should I take?
Respond with JSON: {{"action": "...", "target": "...", "parameters": {{...}}, "reasoning": "..."}}"""

            response = await llm.generate(
                prompt=prompt,
                app_name="vision_system",
                temperature=0.2,  # Low for consistent actions
                max_tokens=200,
            )

            # Parse response
            import json as _json

            action: dict[str, Any]
            try:
                parsed = _json.loads(str(response))
                if isinstance(parsed, dict):
                    action = parsed
                else:
                    action = {
                        "action": "observe",
                        "target": "scene",
                        "parameters": {},
                        "reasoning": str(response),
                    }
            except Exception:
                # Fallback if not valid JSON
                action = {
                    "action": "observe",
                    "target": "scene",
                    "parameters": {},
                    "reasoning": str(response),
                }

            logger.info(f"👁️ Vision-guided action: {action.get('action')} on {action.get('target')}")

            return action

        except Exception as e:
            logger.error(f"Failed to decide action from vision: {e}", exc_info=True)
            return {"action": "error", "error": str(e)}

    def _load_image(self, image_input: str | bytes | np.ndarray) -> np.ndarray:
        """Load image from various formats.

        Args:
            image_input: Image data

        Returns:
            Image as numpy array
        """
        import io

        import PIL.Image

        if isinstance(image_input, str):
            # File path
            img = PIL.Image.open(image_input)
            return np.array(img)
        elif isinstance(image_input, bytes):
            # Bytes
            img = PIL.Image.open(io.BytesIO(image_input))
            return np.array(img)
        elif isinstance(image_input, np.ndarray):
            # Already numpy
            return image_input
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

    async def _extract_features(self, image: np.ndarray) -> Any:
        """Extract visual features using vision model.

        Args:
            image: Image as numpy array

        Returns:
            Feature embedding
        """
        if not self._should_use_sota():
            raise RuntimeError(
                "SOTA vision disabled (set[Any] KAGAMI_VISION_USE_SOTA=1 and avoid test mode)."
            )

        vision = self._get_sota_vision()
        if vision is None:
            raise RuntimeError("SOTA vision unavailable (failed to construct UnifiedVisionModule).")

        pil = self._to_pil(image)
        return await vision.encode(pil)

    async def _detect_objects(self, image: np.ndarray) -> list[DetectedObject]:
        """Detect objects in image.

        Args:
            image: Image as numpy array

        Returns:
            List of detected objects
        """
        if not self._should_use_sota():
            raise RuntimeError(
                "SOTA vision disabled (set[Any] KAGAMI_VISION_USE_SOTA=1 and avoid test mode)."
            )

        vision = self._get_sota_vision()
        if vision is None:
            raise RuntimeError("SOTA vision unavailable (failed to construct UnifiedVisionModule).")

        pil = self._to_pil(image)
        sota_objects = await vision.detect(pil)

        detected_objects: list[DetectedObject] = []
        for obj in sota_objects:
            # Florence-2 bbox is normalized [x1,y1,x2,y2]
            try:
                x1, y1, x2, y2 = obj.bbox
                detected_objects.append(
                    DetectedObject(
                        label=str(obj.label),
                        confidence=float(getattr(obj, "confidence", 0.9)),
                        bounding_box=(
                            int(x1 * image.shape[1]),
                            int(y1 * image.shape[0]),
                            int(x2 * image.shape[1]),
                            int(y2 * image.shape[0]),
                        ),
                        attributes={},
                    )
                )
            except Exception:
                continue

        return detected_objects

    async def _describe_scene(self, image: np.ndarray, objects: list[DetectedObject]) -> str:
        """Generate natural language description of scene.

        Args:
            image: Image
            objects: Detected objects

        Returns:
            Scene description
        """
        if not self._should_use_sota():
            raise RuntimeError(
                "SOTA vision disabled (set[Any] KAGAMI_VISION_USE_SOTA=1 and avoid test mode)."
            )

        vision = self._get_sota_vision()
        if vision is None:
            raise RuntimeError("SOTA vision unavailable (failed to construct UnifiedVisionModule).")

        pil = self._to_pil(image)
        caption = await vision.caption(pil, detailed=True)
        return caption.strip() if isinstance(caption, str) else str(caption)

    def _extract_spatial_relationships(self, objects: list[DetectedObject]) -> list[dict[str, Any]]:
        """Extract spatial relationships between objects.

        Args:
            objects: Detected objects

        Returns:
            List of relationships
        """
        relationships = []

        for i, obj1 in enumerate(objects):
            for obj2 in objects[i + 1 :]:
                # Compute spatial relationship
                x1_center = (obj1.bounding_box[0] + obj1.bounding_box[2]) / 2
                y1_center = (obj1.bounding_box[1] + obj1.bounding_box[3]) / 2
                x2_center = (obj2.bounding_box[0] + obj2.bounding_box[2]) / 2
                y2_center = (obj2.bounding_box[1] + obj2.bounding_box[3]) / 2

                # Determine relation
                if x1_center < x2_center:
                    relation = "left of"
                elif x1_center > x2_center:
                    relation = "right of"
                elif y1_center < y2_center:
                    relation = "above"
                else:
                    relation = "below"

                relationships.append(
                    {
                        "object1": obj1.label,
                        "relation": relation,
                        "object2": obj2.label,
                    }
                )

        return relationships


__all__ = ["DetectedObject", "VisionPerception", "VisionSystem"]
