"""Spatial reasoning and 3D understanding.

Provides:
- 3D spatial reasoning for object relationships
- Unified scene graph for entity tracking
- Vision adapter for perception integration
"""

from kagami.core.spatial.spatial_reasoning_3d import (
    Object3D,
    Position3D,
    Spatial3DReasoner,
    SpatialRelation,
)
from kagami.core.spatial.unified_scene_graph import (
    SpatialEntity,
    UnifiedSceneGraph,
)

__all__ = [
    # 3D reasoning
    "Object3D",
    "Position3D",
    "Spatial3DReasoner",
    # Scene graph
    "SpatialEntity",
    "SpatialRelation",
    "UnifiedSceneGraph",
]
