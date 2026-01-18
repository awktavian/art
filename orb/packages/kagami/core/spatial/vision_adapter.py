from __future__ import annotations

"""Vision Scene Graph Adapter for Unified Scene Graph.

Adapts vision-based scene graphs (from DETR/transformers) to the unified
spatial scene graph format.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def ingest_vision_scene_graph(scene_graph_result: Any) -> dict[str, Any]:
    """Ingest vision-based scene graph into unified scene graph.

    Args:
        scene_graph_result: SceneGraphResult from scene_graph_generator

    Returns:
        Ingestion stats
    """
    try:
        from kagami.core.spatial.unified_scene_graph import get_scene_graph

        scene_graph = get_scene_graph()

        # Ingest using built-in vision ingestion
        await scene_graph.ingest_from_vision(scene_graph_result)

        stats = {
            "objects_ingested": len(getattr(scene_graph_result, "objects", [])),
            "relations_ingested": len(getattr(scene_graph_result, "relations", [])),
            "confidence": getattr(scene_graph_result, "confidence", 0.0),
        }

        logger.debug(
            f"Vision adapter: ingested {stats['objects_ingested']} objects, "
            f"{stats['relations_ingested']} relations"
        )

        return stats

    except Exception as e:
        logger.error(f"Vision scene graph ingestion failed: {e}")
        return {"error": str(e)}


async def adapt_ar_scene_analysis(
    analysis: dict[str, Any], *, room_id: str | None = None
) -> dict[str, Any]:
    """Adapt AR scene analysis to unified scene graph.

    Args:
        analysis: Scene analysis from KagamiARSystem

    Returns:
        Adaptation stats
    """
    try:
        from kagami.core.spatial.unified_scene_graph import (
            SpatialEntity,
            get_scene_graph,
        )

        scene_graph = get_scene_graph(room_id)

        entities_added = 0

        # Extract objects from scene graph if present
        scene_graph_data = analysis.get("scene_graph")
        if scene_graph_data and hasattr(scene_graph_data, "objects"):
            await ingest_vision_scene_graph(scene_graph_data)
            entities_added = len(scene_graph_data.objects)

        # Extract tracked objects if present
        tracked_objects = analysis.get("tracked_objects", {})
        for obj_id, obj_data in tracked_objects.items():
            try:
                # Convert tracked object to spatial entity
                position = tuple(obj_data.get("position", [0.0, 0.0, 0.0]))[:3]

                entity = SpatialEntity(
                    entity_id=f"ar_tracked_{obj_id}",
                    entity_type="ar_tracked_object",
                    position=position,
                    source="vision",
                    confidence=float(obj_data.get("confidence", 0.5)),
                    labels=[obj_data.get("label", "unknown")],
                    properties={
                        "tracking_id": obj_id,
                        "first_seen": obj_data.get("first_seen"),
                        "last_seen": obj_data.get("last_seen"),
                    },
                )

                await scene_graph.add_entity(entity)
                entities_added += 1

            except Exception as obj_err:
                logger.debug(f"Failed to adapt tracked object {obj_id}: {obj_err}")

        logger.debug(f"AR adapter: added {entities_added} entities to scene graph")

        return {
            "entities_added": entities_added,
            "success": True,
        }

    except Exception as e:
        logger.error(f"AR scene analysis adaptation failed: {e}")
        return {"error": str(e), "success": False}


__all__ = [
    "adapt_ar_scene_analysis",
    "ingest_vision_scene_graph",
]
