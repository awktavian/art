from __future__ import annotations

"""Unified Spatial Scene Graph - Single Source of Truth for Spatial Entities.

Consolidates:
- Genesis physics entities
- Vision-based scene graphs
- Manual spatial annotations
- Spatial reasoner data
- Rooms multiplayer state

Design Principles:
1. Multi-source ingestion (physics, vision, manual)
2. Unified entity representation
3. Cached relation computation
4. Temporal tracking
5. Feeds all downstream systems (JEPA, rooms, spatial reasoner)
"""
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from kagami_observability.metrics import (
    RELATIONSHIP_GRAPH_EDGES_TOTAL,
    RELATIONSHIP_GRAPH_NODES_TOTAL,
)

logger = logging.getLogger(__name__)


@dataclass
class SpatialEntity:
    """Unified spatial entity representation.

    Combines data from multiple sources:
    - Genesis: position, orientation, velocity, angular_velocity
    - Vision: labels, bounding box, confidence
    - Manual: custom properties
    """

    entity_id: str
    entity_type: str

    # Transforms (always present)
    position: tuple[float, float, float]
    orientation: tuple[float, float, float, float] = (
        0.0,
        0.0,
        0.0,
        1.0,
    )  # quaternion

    # Dynamics (optional)
    velocity: tuple[float, float, float] | None = None
    angular_velocity: tuple[float, float, float] | None = None

    # Geometry (optional)
    size: tuple[float, float, float] | None = None  # bbox (width, height, depth)

    # Semantics (optional)
    labels: list[str] = field(default_factory=list[Any])
    properties: dict[str, Any] = field(default_factory=dict[str, Any])

    # Metadata
    source: str = "unknown"  # "genesis", "vision", "manual"
    confidence: float = 1.0
    last_updated: float = field(default_factory=time.time)


@dataclass
class SpatialRelation:
    """Unified spatial relation representation.

    Supports both:
    - Geometric relations (above, below, near, far)
    - Contact-based relations (touching, holding)
    """

    subject_id: str
    predicate: str  # "touching", "above", "near", "holding", etc.
    object_id: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])  # distance, impulse, direction

    def __hash__(self) -> int:
        return hash((self.subject_id, self.predicate, self.object_id))


class UnifiedSceneGraph:
    """Single authoritative spatial scene graph.

    Features:
    - Multi-source entity ingestion
    - Automatic relation computation
    - Temporal tracking (entity history)
    - Export to JEPA, rooms, spatial reasoner
    """

    def __init__(self, max_history: int = 100) -> None:
        self._entities: dict[str, SpatialEntity] = {}
        self._relations: set[SpatialRelation] = set()
        self._relation_index: dict[str, list[SpatialRelation]] = defaultdict(list[Any])

        # Temporal tracking
        self._entity_history: dict[str, deque[SpatialEntity]] = defaultdict(
            lambda: deque(maxlen=max_history)
        )

        # Configuration
        self._near_threshold = 2.0  # meters
        self._far_threshold = 10.0  # meters
        self._auto_compute_relations = True

        # Performance tracking
        self._last_update = 0.0
        self._update_count = 0

        # WebSocket push for CORTEX 3D UI
        self._enable_websocket_push = True
        self._agui_sessions: list[Any] = []

        logger.info("🌐 Initialized unified spatial scene graph (WebSocket push enabled)")

    # ========== WebSocket Push ==========

    def register_agui_session(self, session: Any) -> None:
        """Register AGUI session for real-time scene graph pushes."""
        if session not in self._agui_sessions:
            self._agui_sessions.append(session)
            logger.debug("Registered AGUI session for scene graph pushes")

    def unregister_agui_session(self, session: Any) -> None:
        """Unregister AGUI session."""
        if session in self._agui_sessions:
            self._agui_sessions.remove(session)
            logger.debug("Unregistered AGUI session")

    async def _push_to_frontend(self) -> None:
        """Push scene graph update to all registered frontend sessions."""
        if not self._enable_websocket_push or not self._agui_sessions:
            return

        try:
            from kagami.core.interfaces.agui_events import emit_scene_graph_update

            entities = list(self._entities.values())
            relations = list(self._relations)

            # Push to all sessions
            for session in self._agui_sessions:
                try:
                    await emit_scene_graph_update(session, entities, relations)
                except Exception as e:
                    logger.debug(f"Failed to push to session: {e}")
        except Exception as e:
            logger.debug(f"Scene graph WebSocket push failed: {e}")

    # ========== Data Ingestion ==========

    async def ingest_from_genesis(self, frame: dict[str, Any]) -> None:
        """Ingest Genesis physics frame.

        Expected format:
        {
            "timestamp": float,
            "entities": [
                {
                    "id": entity.uid,
                    "name": "character_123",
                    "position": [x, y, z],
                    "orientation": [qx, qy, qz, qw],
                    "velocity": [vx, vy, vz],
                    "angular_velocity": [wx, wy, wz]
                }
            ]
        }
        """
        try:
            entities = frame.get("entities", [])

            for ent_data in entities:
                entity_id = str(ent_data.get("id", ent_data.get("name", "")))
                if not entity_id:
                    continue

                # Convert lists to tuples
                position = tuple(ent_data.get("position", [0.0, 0.0, 0.0]))[:3]
                orientation = tuple(ent_data.get("orientation", [0.0, 0.0, 0.0, 1.0]))[:4]

                velocity = ent_data.get("velocity")
                if velocity:
                    velocity = tuple(velocity)[:3]

                angular_velocity = ent_data.get("angular_velocity")
                if angular_velocity:
                    angular_velocity = tuple(angular_velocity)[:3]

                entity = SpatialEntity(
                    entity_id=entity_id,
                    entity_type="physics_entity",
                    position=position,
                    orientation=orientation,
                    velocity=velocity,
                    angular_velocity=angular_velocity,
                    source="genesis",
                    confidence=1.0,
                    labels=[ent_data.get("name", "")],
                    properties={
                        "genesis_uid": ent_data.get("id"),
                        "timestamp": frame.get("timestamp", time.time()),
                    },
                )

                await self.add_entity(entity)

            # Update relations if auto-compute enabled
            if self._auto_compute_relations:
                await self._compute_all_relations()

            logger.debug(
                f"Ingested {len(entities)} entities from Genesis (frame {frame.get('timestamp', 0):.2f}s)"
            )

        except Exception as e:
            logger.error(f"Failed to ingest Genesis frame: {e}")

    async def ingest_from_vision(self, scene_graph: Any) -> None:
        """Ingest vision-based scene graph.

        Expected: SceneGraphResult from scene_graph_generator
        """
        try:
            if not hasattr(scene_graph, "objects"):
                logger.warning("Scene graph missing objects attribute")
                return

            for obj in scene_graph.objects:
                entity_id = f"vision_{obj.object_id}"

                # Extract position from bounding box center
                bbox = obj.bounding_box
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                # Assume z=0 for 2D vision (upgrade to depth estimation later)
                position = (float(center_x), float(center_y), 0.0)

                # Estimate size from bbox
                width = float(bbox[2] - bbox[0])
                height = float(bbox[3] - bbox[1])
                size = (width, height, 1.0)  # Assume unit depth

                entity = SpatialEntity(
                    entity_id=entity_id,
                    entity_type="vision_object",
                    position=position,
                    size=size,
                    source="vision",
                    confidence=float(obj.confidence),
                    labels=[obj.label],
                    properties={
                        "bounding_box": bbox,
                        "area": obj.area,
                    },
                )

                await self.add_entity(entity)

            # Ingest vision relations
            if hasattr(scene_graph, "relations"):
                for rel in scene_graph.relations:
                    relation = SpatialRelation(
                        subject_id=f"vision_{rel.subject_id}",
                        predicate=rel.predicate,
                        object_id=f"vision_{rel.object_id}",
                        confidence=float(rel.confidence),
                    )
                    await self.add_relation(relation)

            logger.debug(f"Ingested {len(scene_graph.objects)} objects from vision")

        except Exception as e:
            logger.error(f"Failed to ingest vision scene graph: {e}")

    async def ingest_from_manual(self, entity: SpatialEntity) -> None:
        """Ingest manually created entity."""
        entity.source = "manual"
        await self.add_entity(entity)

    # ========== Entity Management ==========

    async def add_entity(self, entity: SpatialEntity) -> None:
        """Add or update entity in scene graph."""
        entity.last_updated = time.time()

        # Store current state
        self._entities[entity.entity_id] = entity

        # Track history
        self._entity_history[entity.entity_id].append(entity)

        # Update metrics
        self._update_count += 1
        self._last_update = time.time()

        try:
            RELATIONSHIP_GRAPH_NODES_TOTAL.set(float(len(self._entities)))
        except Exception:
            pass

    async def remove_entity(self, entity_id: str) -> None:
        """Remove entity from scene graph."""
        if entity_id in self._entities:
            del self._entities[entity_id]

            # Remove relations involving this entity
            self._relations = {
                r for r in self._relations if r.subject_id != entity_id and r.object_id != entity_id
            }
            self._rebuild_relation_index()

            try:
                RELATIONSHIP_GRAPH_NODES_TOTAL.set(float(len(self._entities)))
            except Exception:
                pass

    async def add_relation(self, relation: SpatialRelation) -> None:
        """Add relation to scene graph."""
        self._relations.add(relation)
        self._relation_index[relation.subject_id].append(relation)
        self._relation_index[relation.object_id].append(relation)

        try:
            RELATIONSHIP_GRAPH_EDGES_TOTAL.set(float(len(self._relations)))
        except Exception:
            pass

    def _rebuild_relation_index(self) -> None:
        """Rebuild relation index after bulk changes."""
        self._relation_index.clear()
        for rel in self._relations:
            self._relation_index[rel.subject_id].append(rel)
            self._relation_index[rel.object_id].append(rel)

    # ========== Relation Computation ==========

    async def _compute_all_relations(self) -> None:
        """Compute geometric relations between all entities.

        Only computes relations for entities that have changed.
        """
        entities = list(self._entities.values())

        # Clear old geometric relations (keep vision/manual relations)
        self._relations = {r for r in self._relations if r.metadata.get("source") != "computed"}

        # Compute pairwise relations
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1 :]:
                relation = self._compute_relation(e1, e2)
                if relation:
                    relation.metadata["source"] = "computed"
                    await self.add_relation(relation)

        try:
            RELATIONSHIP_GRAPH_EDGES_TOTAL.set(float(len(self._relations)))
        except Exception:
            pass

    def _compute_relation(self, e1: SpatialEntity, e2: SpatialEntity) -> SpatialRelation | None:
        """Compute spatial relation between two entities.

        Prioritizes:
        1. Contact-based (if velocity indicates collision)
        2. Geometric (above/below/near/far)
        """
        # Compute distance
        p1 = np.array(e1.position)
        p2 = np.array(e2.position)
        distance = float(np.linalg.norm(p2 - p1))

        # Contact detection (if both have velocity)
        if e1.velocity and e2.velocity and distance < 0.5:
            # Simple heuristic: approaching velocities = touching
            v1 = np.array(e1.velocity)
            v2 = np.array(e2.velocity)
            relative_vel = np.linalg.norm(v2 - v1)
            if relative_vel > 0.1:
                return SpatialRelation(
                    subject_id=e1.entity_id,
                    predicate="touching",
                    object_id=e2.entity_id,
                    confidence=0.8,
                    metadata={"distance": distance, "relative_velocity": relative_vel},
                )

        # Distance-based relations
        if distance < self._near_threshold:
            predicate = "near"
            confidence = 1.0 - (distance / self._near_threshold) * 0.5
        elif distance > self._far_threshold:
            predicate = "far"
            confidence = min(1.0, distance / self._far_threshold - 0.5)
        else:
            # Mid-range, check vertical/horizontal
            dx, dy, dz = p2 - p1

            # Vertical relations (z-axis)
            if abs(dz) > 0.5 and abs(dz) > abs(dx) and abs(dz) > abs(dy):
                predicate = "above" if dz > 0 else "below"
                confidence = min(1.0, abs(dz) / 2.0)
            # Horizontal relations (x-axis)
            elif abs(dx) > 0.5:
                predicate = "right" if dx > 0 else "left"
                confidence = min(1.0, abs(dx) / 2.0)
            else:
                return None  # No strong relation

        return SpatialRelation(
            subject_id=e1.entity_id,
            predicate=predicate,
            object_id=e2.entity_id,
            confidence=confidence,
            metadata={"distance": distance},
        )

    # ========== Queries ==========

    def get_entity(self, entity_id: str) -> SpatialEntity | None:
        """Get entity by ID."""
        return self._entities.get(entity_id)

    def get_all_entities(self) -> list[SpatialEntity]:
        """Get all entities."""
        return list(self._entities.values())

    def get_all_relations(self) -> list[SpatialRelation]:
        """Get all relations."""
        return list(self._relations)

    def get_entity_history(self, entity_id: str, limit: int = 10) -> list[SpatialEntity]:
        """Get entity history (past states)."""
        history = self._entity_history.get(entity_id, deque())
        return list(history)[-limit:]

    async def query_relation(self, subject_id: str, object_id: str) -> SpatialRelation | None:
        """Query specific relation between two entities."""
        for rel in self._relation_index.get(subject_id, []):
            if rel.object_id == object_id:
                return rel
        return None

    async def query_relations(
        self, entity_id: str, predicate: str | None = None
    ) -> list[SpatialRelation]:
        """Query all relations involving entity (optionally filtered by predicate)."""
        relations = self._relation_index.get(entity_id, [])
        if predicate:
            relations = [r for r in relations if r.predicate == predicate]
        return relations

    async def query_nearby(
        self, position: tuple[float, float, float], radius: float = 5.0
    ) -> list[SpatialEntity]:
        """Find all entities within radius of position."""
        pos = np.array(position)
        nearby = []

        for entity in self._entities.values():
            ent_pos = np.array(entity.position)
            distance = np.linalg.norm(ent_pos - pos)
            if distance <= radius:
                nearby.append(entity)

        return nearby

    # ========== Export ==========

    async def to_jepa_observation(self) -> dict[str, Any]:
        """Export scene graph as JEPA observation.

        Converts spatial entities to observation dict[str, Any] for JEPA encoding.
        """
        observation = {
            "type": "scene_graph",
            "status": "success",
            "entities": [],
            "features": {},
        }

        for entity in self._entities.values():
            observation["entities"].append(  # type: ignore  # Dynamic attr
                {
                    "id": entity.entity_id,
                    "type": entity.entity_type,
                    "position": list(entity.position),
                    "orientation": list(entity.orientation),
                    "velocity": list(entity.velocity) if entity.velocity else None,
                    "labels": entity.labels,
                }
            )

        # Add aggregate features
        observation["features"] = {
            "entity_count": len(self._entities),
            "relation_count": len(self._relations),
            "avg_distance": self._compute_avg_distance(),
        }

        return observation

    async def to_rooms_snapshot(self, room_id: str) -> dict[str, Any]:
        """Export scene graph for rooms state service.

        Format matches update_physics_entities() expectations.
        """
        entities = []
        for entity in self._entities.values():
            entities.append(
                {
                    "id": entity.entity_id,
                    "name": entity.entity_id,
                    "position": list(entity.position),
                    "orientation": list(entity.orientation),
                    "velocity": list(entity.velocity) if entity.velocity else [0, 0, 0],
                }
            )

        return {"room_id": room_id, "entities": entities, "timestamp": time.time()}

    async def to_spatial_reasoner(self) -> None:
        """Populate spatial reasoner with current entities."""
        try:
            from kagami.core.spatial.spatial_reasoning_3d import (
                Object3D,
                Position3D,
                get_spatial_reasoner,
            )

            reasoner = get_spatial_reasoner()

            for entity in self._entities.values():
                # Only add entities with valid geometry
                if entity.position and entity.size:
                    obj3d = Object3D(
                        object_id=entity.entity_id,
                        object_type=entity.entity_type,
                        position=Position3D(*entity.position),
                        size=entity.size,
                        rotation=entity.properties.get("rotation", (0.0, 0.0, 0.0)),
                        properties=entity.properties,
                    )
                    await reasoner.add_object(obj3d)

            logger.debug(f"Synced {len(self._entities)} entities to spatial reasoner")

        except Exception as e:
            logger.debug(f"Spatial reasoner sync failed: {e}")

    # ========== Utilities ==========

    def _compute_avg_distance(self) -> float:
        """Compute average distance between all entity pairs."""
        entities = list(self._entities.values())
        if len(entities) < 2:
            return 0.0

        total_distance = 0.0
        count = 0

        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1 :]:
                p1 = np.array(e1.position)
                p2 = np.array(e2.position)
                total_distance += float(np.linalg.norm(p2 - p1))
                count += 1

        return total_distance / count if count > 0 else 0.0

    def get_stats(self) -> dict[str, Any]:
        """Get scene graph statistics."""
        return {
            "entity_count": len(self._entities),
            "relation_count": len(self._relations),
            "update_count": self._update_count,
            "last_update": self._last_update,
            "sources": {
                source: sum(1 for e in self._entities.values() if e.source == source)
                for source in ["genesis", "vision", "manual"]
            },
        }


# Singleton
_scene_graphs: dict[str, UnifiedSceneGraph] = {}


def get_scene_graph(room_id: str | None = None) -> UnifiedSceneGraph:
    """Get or create unified scene graph for a room.

    Args:
        room_id: Optional room identifier; defaults to 'global'.
    """
    key = (room_id or "global").strip() or "global"
    if key not in _scene_graphs:
        _scene_graphs[key] = UnifiedSceneGraph()
    return _scene_graphs[key]


__all__ = [
    "SpatialEntity",
    "SpatialRelation",
    "UnifiedSceneGraph",
    "get_scene_graph",
]
