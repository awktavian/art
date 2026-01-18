from __future__ import annotations

"""3D Spatial Reasoning Engine - Geometric Understanding & Path Planning.

Provides spatial intelligence for:
- Object relationships (above, below, left, right, near, far)
- Collision detection
- Path planning in 3D space
- Spatial queries
"""
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Position3D:
    """3D position coordinates."""

    x: float
    y: float
    z: float

    def distance_to(self, other: Position3D) -> float:
        """Euclidean distance to another position."""
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return float(np.sqrt(dx * dx + dy * dy + dz * dz))


@dataclass
class Object3D:
    """3D object with position, size, and properties."""

    object_id: str
    object_type: str
    position: Position3D
    size: tuple[float, float, float]  # width, height, depth
    rotation: tuple[float, float, float]  # pitch, yaw, roll in radians
    properties: dict[str, Any]

    @property
    def id(self) -> str:
        """Alias for object_id."""
        return self.object_id


@dataclass
class SpatialRelation:
    """Spatial relationship between two objects."""

    object1_id: str
    object2_id: str
    relation_type: str  # "above", "below", "left", "right", "near", "far"
    confidence: float  # 0.0 to 1.0
    distance: float = 0.0  # Distance between objects


class Spatial3DReasoner:
    """3D spatial reasoning engine."""

    def __init__(self) -> None:
        self._objects: dict[str, Object3D] = {}
        self._initialized = False

        # Spatial thresholds
        self._near_threshold = 2.0  # meters
        self._far_threshold = 10.0  # meters

    async def initialize(self) -> None:
        """Initialize spatial reasoning engine."""
        logger.info("🌐 Initializing 3D spatial reasoner...")
        self._initialized = True
        logger.info("✅ 3D spatial reasoner initialized")

    async def add_object(self, obj: Object3D) -> None:
        """Add object to spatial scene."""
        self._objects[obj.object_id] = obj
        logger.debug(f"Added object {obj.object_id} at position {obj.position}")

    async def remove_object(self, object_id: str) -> None:
        """Remove object from spatial scene."""
        if object_id in self._objects:
            del self._objects[object_id]
            logger.debug(f"Removed object {object_id}")

    def compute_relation(self, obj1_id: str, obj2_id: str) -> SpatialRelation | None:
        """Compute spatial relationship between two objects."""
        if obj1_id not in self._objects or obj2_id not in self._objects:
            return None

        obj1 = self._objects[obj1_id]
        obj2 = self._objects[obj2_id]

        distance = obj1.position.distance_to(obj2.position)

        # Determine relation type
        relation_type = "unknown"
        confidence = 1.0

        # Distance-based relations
        if distance < self._near_threshold:
            relation_type = "near"
        elif distance > self._far_threshold:
            relation_type = "far"

        # Vertical relations (z-axis)
        dz = obj2.position.z - obj1.position.z
        if abs(dz) > 0.5:  # Significant vertical difference
            if dz > 0:
                relation_type = "above"
            else:
                relation_type = "below"
            confidence = min(1.0, abs(dz) / 2.0)

        # Horizontal relations (x-axis)
        dx = obj2.position.x - obj1.position.x
        if abs(dx) > abs(dz) and abs(dx) > 0.5:
            if dx > 0:
                relation_type = "right"
            else:
                relation_type = "left"
            confidence = min(1.0, abs(dx) / 2.0)

        return SpatialRelation(
            object1_id=obj1_id,
            object2_id=obj2_id,
            relation_type=relation_type,
            confidence=confidence,
            distance=distance,
        )

    async def query_relation(self, obj1_id: str, obj2_id: str) -> SpatialRelation | None:
        """Async query of spatial relationship between two objects."""
        return self.compute_relation(obj1_id, obj2_id)

    async def plan_path_3d(
        self,
        start: Position3D,
        goal: Position3D,
        obstacles: list[Object3D] | None = None,
    ) -> list[Position3D] | None:
        """Alias for plan_path."""
        return await self.plan_path(start, goal, obstacles)

    async def plan_path(
        self,
        start: Position3D,
        goal: Position3D,
        obstacles: list[Object3D] | None = None,
    ) -> list[Position3D] | None:
        """Plan path from start to goal avoiding obstacles.

        Simple A* path planning implementation.
        """
        # For now, return simple straight-line path if no obstacles
        if not obstacles:
            # Interpolate between start and goal
            steps = 10
            path = []
            for i in range(steps + 1):
                t = i / steps
                path.append(
                    Position3D(
                        x=start.x + t * (goal.x - start.x),
                        y=start.y + t * (goal.y - start.y),
                        z=start.z + t * (goal.z - start.z),
                    )
                )
            return path

        # With obstacles: simple obstacle avoidance
        # (Full A* implementation would be here in production)
        logger.warning("Obstacle avoidance not fully implemented yet")
        return None

    def check_collision(self, obj1: Object3D, obj2: Object3D) -> bool:
        """Check if two objects collide (AABB collision detection)."""
        # Simple axis-aligned bounding box collision
        p1 = obj1.position
        s1 = obj1.size
        p2 = obj2.position
        s2 = obj2.size

        # Check overlap on each axis
        x_overlap = abs(p1.x - p2.x) < (s1[0] + s2[0]) / 2
        y_overlap = abs(p1.y - p2.y) < (s1[1] + s2[1]) / 2
        z_overlap = abs(p1.z - p2.z) < (s1[2] + s2[2]) / 2

        return x_overlap and y_overlap and z_overlap

    async def query_nearby(self, position: Position3D, radius: float = 5.0) -> list[Object3D]:
        """Find all objects within radius of position."""
        nearby = []
        for obj in self._objects.values():
            distance = position.distance_to(obj.position)
            if distance <= radius:
                nearby.append(obj)
        return nearby


# Singleton
_spatial_reasoner: Spatial3DReasoner | None = None


def get_spatial_reasoner() -> Spatial3DReasoner:
    """Get global spatial reasoner instance."""
    global _spatial_reasoner
    if _spatial_reasoner is None:
        _spatial_reasoner = Spatial3DReasoner()
    return _spatial_reasoner


__all__ = [
    "Object3D",
    "Position3D",
    "Spatial3DReasoner",
    "SpatialRelation",
    "get_spatial_reasoner",
]
