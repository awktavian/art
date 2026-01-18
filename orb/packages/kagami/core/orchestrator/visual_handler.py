"""Visual Intent Handler - Screenshot analysis, UI debugging.

Created: November 2, 2025
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def handle_visual_intent(intent: dict[str, Any]) -> dict[str, Any]:
    """Handle visual/image analysis intents.

    Args:
        intent: Intent dict[str, Any]

    Returns:
        Analysis result
    """
    params = intent.get("args", {}) or intent.get("params", {})
    image_path = params.get("image") or params.get("screenshot")

    if not image_path:
        return {"status": "error", "error": "No image provided"}

    try:
        from PIL import Image

        from kagami.core.multimodal.vision import get_unified_vision_module

        img = Image.open(image_path).convert("RGB")
        vision = get_unified_vision_module()
        scene = await vision.analyze(img)

        analysis = {
            "caption": scene.caption,
            "detailed_caption": scene.detailed_caption,
            "ocr_text": scene.ocr_text,
            "confidence": scene.confidence,
            "processing_time_ms": scene.processing_time_ms,
            "metadata": scene.metadata,
            "objects": [
                {
                    "id": o.id,
                    "label": o.label,
                    "confidence": o.confidence,
                    "bbox": o.bbox,
                    "area": o.area,
                }
                for o in scene.objects
            ],
            "relations": [
                {
                    "subject_id": r.subject_id,
                    "object_id": r.object_id,
                    "predicate": r.predicate,
                    "confidence": r.confidence,
                }
                for r in scene.relations
            ],
        }

        return {"status": "success", "analysis": analysis, "image": image_path}
    except Exception as e:
        logger.error(f"Visual analysis failed: {e}")
        return {"status": "error", "error": str(e)}


__all__ = ["handle_visual_intent"]
