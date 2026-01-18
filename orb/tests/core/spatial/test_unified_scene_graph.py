"""Tests for unified spatial scene graph."""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.core.spatial.unified_scene_graph import (
    SpatialEntity,
    SpatialRelation,
    UnifiedSceneGraph,
    get_scene_graph,
)


@pytest.fixture
def scene_graph():
    """Create fresh scene graph for each test."""
    return UnifiedSceneGraph()


@pytest.mark.asyncio
async def test_add_entity(scene_graph: Any) -> None:
    """Test adding entity to scene graph."""
    entity = SpatialEntity(
        entity_id="test_entity",
        entity_type="character",
        position=(1.0, 2.0, 3.0),
        orientation=(0.0, 0.0, 0.0, 1.0),
        source="manual",
    )

    await scene_graph.add_entity(entity)

    assert len(scene_graph.get_all_entities()) == 1
    retrieved = scene_graph.get_entity("test_entity")
    assert retrieved is not None
    assert retrieved.position == (1.0, 2.0, 3.0)


@pytest.mark.asyncio
async def test_genesis_ingestion(scene_graph: Any) -> None:
    """Test Genesis frame ingestion."""
    frame = {
        "timestamp": 0.0,
        "entities": [
            {
                "id": 1,
                "name": "character",
                "position": [0.0, 0.0, 1.0],
                "orientation": [0.0, 0.0, 0.0, 1.0],
                "velocity": [1.0, 0.0, 0.0],
                "angular_velocity": [0.0, 0.0, 0.5],
            }
        ],
    }

    await scene_graph.ingest_from_genesis(frame)

    entities = scene_graph.get_all_entities()
    assert len(entities) == 1

    entity = entities[0]
    assert entity.source == "genesis"
    assert entity.velocity == (1.0, 0.0, 0.0)
    assert entity.angular_velocity == (0.0, 0.0, 0.5)


@pytest.mark.asyncio
async def test_relation_computation(scene_graph: Any) -> None:
    """Test automatic relation computation."""
    # Add two nearby entities
    e1 = SpatialEntity(
        entity_id="e1",
        entity_type="object",
        position=(0.0, 0.0, 0.0),
        source="manual",
    )
    e2 = SpatialEntity(
        entity_id="e2",
        entity_type="object",
        position=(1.0, 0.0, 0.0),  # 1m away on x-axis
        source="manual",
    )

    await scene_graph.add_entity(e1)
    await scene_graph.add_entity(e2)

    # Compute relations
    await scene_graph._compute_all_relations()

    relation = await scene_graph.query_relation("e1", "e2")
    assert relation is not None
    assert relation.predicate == "near"  # Within 2m threshold
    assert relation.confidence > 0.0


@pytest.mark.asyncio
async def test_vertical_relation(scene_graph: Any) -> None:
    """Test vertical (above/below) relation detection."""
    e1 = SpatialEntity(
        entity_id="e1",
        entity_type="object",
        position=(0.0, 0.0, 0.0),
        source="manual",
    )
    e2 = SpatialEntity(
        entity_id="e2",
        entity_type="object",
        position=(0.0, 0.0, 2.0),  # 2m above on z-axis
        source="manual",
    )

    await scene_graph.add_entity(e1)
    await scene_graph.add_entity(e2)
    await scene_graph._compute_all_relations()

    relation = await scene_graph.query_relation("e1", "e2")
    assert relation is not None
    assert relation.predicate == "above"


@pytest.mark.asyncio
async def test_query_nearby(scene_graph: Any) -> None:
    """Test proximity query."""
    # Add entities at various distances
    await scene_graph.add_entity(
        SpatialEntity(
            entity_id="close",
            entity_type="object",
            position=(1.0, 0.0, 0.0),
            source="manual",
        )
    )
    await scene_graph.add_entity(
        SpatialEntity(
            entity_id="far",
            entity_type="object",
            position=(10.0, 0.0, 0.0),
            source="manual",
        )
    )

    # Query within 5m radius
    nearby = await scene_graph.query_nearby((0.0, 0.0, 0.0), radius=5.0)

    # Should find "close" but not "far"
    assert len(nearby) == 1
    assert nearby[0].entity_id == "close"


@pytest.mark.asyncio
async def test_jepa_export(scene_graph: Any) -> None:
    """Test JEPA observation export."""
    entity = SpatialEntity(
        entity_id="test",
        entity_type="character",
        position=(1.0, 2.0, 3.0),
        velocity=(0.5, 0.0, 0.0),
        source="genesis",
        labels=["player"],
    )
    await scene_graph.add_entity(entity)

    obs = await scene_graph.to_jepa_observation()

    assert obs["type"] == "scene_graph"
    assert obs["status"] == "success"
    assert len(obs["entities"]) == 1
    assert obs["features"]["entity_count"] == 1

    entity_data = obs["entities"][0]
    assert entity_data["id"] == "test"
    assert entity_data["position"] == [1.0, 2.0, 3.0]
    assert entity_data["velocity"] == [0.5, 0.0, 0.0]


@pytest.mark.asyncio
async def test_rooms_export(scene_graph: Any) -> None:
    """Test rooms snapshot export."""
    entity = SpatialEntity(
        entity_id="entity_1",
        entity_type="physics_entity",
        position=(1.0, 2.0, 3.0),
        orientation=(0.0, 0.0, 0.0, 1.0),
        velocity=(0.1, 0.2, 0.3),
        source="genesis",
    )
    await scene_graph.add_entity(entity)

    snapshot = await scene_graph.to_rooms_snapshot("test_room")

    assert snapshot["room_id"] == "test_room"
    assert len(snapshot["entities"]) == 1

    entity_data = snapshot["entities"][0]
    assert entity_data["id"] == "entity_1"
    assert entity_data["position"] == [1.0, 2.0, 3.0]
    assert entity_data["velocity"] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_entity_history(scene_graph: Any) -> None:
    """Test entity history tracking."""
    entity_id = "tracked"

    # Add entity multiple times with different positions
    for i in range(5):
        entity = SpatialEntity(
            entity_id=entity_id,
            entity_type="object",
            position=(float(i), 0.0, 0.0),
            source="manual",
        )
        await scene_graph.add_entity(entity)

    history = scene_graph.get_entity_history(entity_id, limit=5)

    assert len(history) == 5
    # Verify positions changed over time
    assert history[0].position[0] == 0.0
    assert history[-1].position[0] == 4.0


@pytest.mark.asyncio
async def test_remove_entity(scene_graph: Any) -> None:
    """Test entity removal."""
    entity = SpatialEntity(
        entity_id="to_remove",
        entity_type="object",
        position=(0.0, 0.0, 0.0),
        source="manual",
    )
    await scene_graph.add_entity(entity)

    assert scene_graph.get_entity("to_remove") is not None

    await scene_graph.remove_entity("to_remove")

    assert scene_graph.get_entity("to_remove") is None
    assert len(scene_graph.get_all_entities()) == 0


@pytest.mark.asyncio
async def test_add_relation(scene_graph: Any) -> None:
    """Test manual relation addition."""
    relation = SpatialRelation(
        subject_id="e1",
        predicate="holding",
        object_id="e2",
        confidence=0.95,
        metadata={"hand": "right"},
    )

    await scene_graph.add_relation(relation)

    retrieved = await scene_graph.query_relation("e1", "e2")
    assert retrieved is not None
    assert retrieved.predicate == "holding"
    assert retrieved.metadata["hand"] == "right"


@pytest.mark.asyncio
async def test_stats(scene_graph: Any) -> None:
    """Test stats reporting."""
    # Add entities from different sources
    await scene_graph.add_entity(
        SpatialEntity(
            entity_id="genesis_1",
            entity_type="character",
            position=(0.0, 0.0, 0.0),
            source="genesis",
        )
    )
    await scene_graph.add_entity(
        SpatialEntity(
            entity_id="vision_1",
            entity_type="object",
            position=(1.0, 0.0, 0.0),
            source="vision",
        )
    )

    stats = scene_graph.get_stats()

    assert stats["entity_count"] == 2
    assert stats["sources"]["genesis"] == 1
    assert stats["sources"]["vision"] == 1


@pytest.mark.asyncio
async def test_singleton():
    """Test singleton pattern."""
    sg1 = get_scene_graph()
    sg2 = get_scene_graph()

    assert sg1 is sg2  # Same instance
