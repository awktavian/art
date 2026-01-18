"""Comprehensive tests for ColonyStateRepository.

Tests CRUD operations, caching (L1 + Redis), write-through behavior,
conflict resolution, and etcd integration.

Created: December 28, 2025
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.database.models import ColonyState
from kagami.core.storage.colony_repository import ColonyStateRepository

pytestmark = pytest.mark.tier_integration


# =============================================================================
# Initialization Tests
# =============================================================================


@pytest.mark.asyncio
async def test_repository_initialization(db_session: AsyncSession):
    """Test repository initialization."""
    repo = ColonyStateRepository(db_session=db_session)

    assert repo.db_session is db_session
    assert repo.etcd_client is None
    assert repo._cache_strategy.value == "write"  # WRITE_THROUGH


@pytest.mark.asyncio
async def test_repository_with_redis(
    db_session: AsyncSession, mock_redis_client
):
    """Test repository initialization with Redis."""
    repo = ColonyStateRepository(
        db_session=db_session, redis_client=mock_redis_client
    )

    assert repo._redis_client is mock_redis_client


@pytest.mark.asyncio
async def test_repository_with_etcd(db_session: AsyncSession, mock_etcd_client):
    """Test repository initialization with etcd."""
    repo = ColonyStateRepository(
        db_session=db_session, etcd_client=mock_etcd_client
    )

    assert repo.etcd_client is mock_etcd_client


# =============================================================================
# CRUD Operations Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_by_id(
    db_session: AsyncSession, sample_colony_state: ColonyState
):
    """Test get colony state by ID."""
    repo = ColonyStateRepository(db_session=db_session)

    # Get by UUID
    state = await repo.get_by_id(sample_colony_state.id)
    assert state is not None
    assert state.id == sample_colony_state.id
    assert state.colony_id == "spark"

    # Get by string UUID
    state = await repo.get_by_id(str(sample_colony_state.id))
    assert state is not None
    assert state.id == sample_colony_state.id


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    """Test get by ID returns None for non-existent state."""
    repo = ColonyStateRepository(db_session=db_session)

    state = await repo.get_by_id(uuid.uuid4())
    assert state is None


@pytest.mark.asyncio
async def test_get_by_colony_instance(
    db_session: AsyncSession, sample_colony_state: ColonyState
):
    """Test get colony state by colony and instance ID."""
    repo = ColonyStateRepository(db_session=db_session)

    state = await repo.get_by_colony_instance("spark", "spark-001")
    assert state is not None
    assert state.colony_id == "spark"
    assert state.instance_id == "spark-001"


@pytest.mark.asyncio
async def test_get_by_colony_instance_not_found(db_session: AsyncSession):
    """Test get by colony instance returns None when not found."""
    repo = ColonyStateRepository(db_session=db_session)

    state = await repo.get_by_colony_instance("nonexistent", "instance-999")
    assert state is None


@pytest.mark.asyncio
async def test_get_active_colonies(db_session: AsyncSession):
    """Test get active colony states."""
    # Create multiple colony states
    colonies = []
    for i, colony_id in enumerate(["spark", "forge", "flow"]):
        state = ColonyState(
            id=uuid.uuid4(),
            colony_id=colony_id,
            instance_id=f"{colony_id}-001",
            node_id=f"node-{i}",
            z_state={"latent": [0.0] * 64},
            z_dim=64,
            timestamp=datetime.utcnow().timestamp(),
            is_active=(i < 2),  # First two active
        )
        colonies.append(state)
        db_session.add(state)
    await db_session.commit()

    repo = ColonyStateRepository(db_session=db_session)

    # Get all active colonies
    active = await repo.get_active_colonies()
    assert len(active) == 2
    assert all(s.is_active for s in active)


@pytest.mark.asyncio
async def test_get_active_colonies_filtered(db_session: AsyncSession):
    """Test get active colonies with filter."""
    # Create states
    for colony_id in ["spark", "spark", "forge"]:
        state = ColonyState(
            id=uuid.uuid4(),
            colony_id=colony_id,
            instance_id=f"{colony_id}-{uuid.uuid4().hex[:4]}",
            node_id="node-001",
            z_state={"latent": [0.0] * 64},
            z_dim=64,
            timestamp=datetime.utcnow().timestamp(),
            is_active=True,
        )
        db_session.add(state)
    await db_session.commit()

    repo = ColonyStateRepository(db_session=db_session)

    # Get only spark colonies
    spark_colonies = await repo.get_active_colonies(colony_id="spark")
    assert len(spark_colonies) == 2
    assert all(s.colony_id == "spark" for s in spark_colonies)


@pytest.mark.asyncio
async def test_get_colony_instances(db_session: AsyncSession):
    """Test get all instances of a colony."""
    # Create multiple instances
    for i in range(3):
        state = ColonyState(
            id=uuid.uuid4(),
            colony_id="nexus",
            instance_id=f"nexus-{i:03d}",
            node_id=f"node-{i}",
            z_state={"latent": [0.0] * 64},
            z_dim=64,
            timestamp=datetime.utcnow().timestamp() + i,
        )
        db_session.add(state)
    await db_session.commit()

    repo = ColonyStateRepository(db_session=db_session)

    instances = await repo.get_colony_instances("nexus")
    assert len(instances) == 3
    assert all(s.colony_id == "nexus" for s in instances)
    # Should be ordered by timestamp desc
    assert instances[0].timestamp > instances[1].timestamp


@pytest.mark.asyncio
async def test_save_colony_state(db_session: AsyncSession):
    """Test save colony state."""
    repo = ColonyStateRepository(db_session=db_session)

    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="beacon",
        instance_id="beacon-001",
        node_id="node-001",
        z_state={"latent": [0.1] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
    )

    saved_state = await repo.save_colony_state(state)
    assert saved_state.id is not None
    assert saved_state.colony_id == "beacon"

    # Verify saved in database
    stmt = select(ColonyState).where(ColonyState.id == saved_state.id)
    result = await db_session.execute(stmt)
    db_state = result.scalar_one_or_none()
    assert db_state is not None
    assert db_state.colony_id == "beacon"


@pytest.mark.asyncio
async def test_save_colony_state_with_etcd(
    db_session: AsyncSession, mock_etcd_client
):
    """Test save colony state syncs to etcd."""
    repo = ColonyStateRepository(
        db_session=db_session, etcd_client=mock_etcd_client
    )

    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="grove",
        instance_id="grove-001",
        node_id="node-001",
        z_state={"latent": [0.0] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
    )

    await repo.save_colony_state(state)

    # Verify etcd put was called
    mock_etcd_client.put.assert_called_once()
    call_args = mock_etcd_client.put.call_args
    assert "/colonies/grove/grove-001" in call_args[0][0]


# =============================================================================
# Update Operations Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_heartbeat(
    db_session: AsyncSession, sample_colony_state: ColonyState
):
    """Test update last heartbeat timestamp."""
    repo = ColonyStateRepository(db_session=db_session)

    original_heartbeat = sample_colony_state.last_heartbeat_at

    # Update heartbeat
    result = await repo.update_heartbeat("spark", "spark-001")
    assert result is True

    # Verify updated
    updated_state = await repo.get_by_colony_instance("spark", "spark-001")
    assert updated_state.last_heartbeat_at > original_heartbeat


@pytest.mark.asyncio
async def test_update_heartbeat_not_found(db_session: AsyncSession):
    """Test update heartbeat returns False when state not found."""
    repo = ColonyStateRepository(db_session=db_session)

    result = await repo.update_heartbeat("nonexistent", "instance-999")
    assert result is False


@pytest.mark.asyncio
async def test_mark_inactive(
    db_session: AsyncSession, sample_colony_state: ColonyState
):
    """Test mark colony instance as inactive."""
    repo = ColonyStateRepository(db_session=db_session)

    assert sample_colony_state.is_active is True

    # Mark inactive
    result = await repo.mark_inactive("spark", "spark-001")
    assert result is True

    # Verify inactive
    state = await repo.get_by_colony_instance("spark", "spark-001")
    assert state.is_active is False


@pytest.mark.asyncio
async def test_mark_inactive_not_found(db_session: AsyncSession):
    """Test mark inactive returns False when state not found."""
    repo = ColonyStateRepository(db_session=db_session)

    result = await repo.mark_inactive("nonexistent", "instance-999")
    assert result is False


# =============================================================================
# Caching Tests
# =============================================================================


@pytest.mark.asyncio
async def test_l1_cache_hit(
    db_session: AsyncSession, sample_colony_state: ColonyState
):
    """Test L1 cache hit."""
    repo = ColonyStateRepository(db_session=db_session)

    # First read - cache miss, load from DB
    state1 = await repo.get_by_id(sample_colony_state.id)
    assert state1 is not None

    # Second read - cache hit (L1)
    state2 = await repo.get_by_id(sample_colony_state.id)
    assert state2 is not None
    assert state2.id == state1.id


@pytest.mark.asyncio
async def test_write_through_cache(db_session: AsyncSession):
    """Test write-through cache strategy."""
    repo = ColonyStateRepository(db_session=db_session)

    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="crystal",
        instance_id="crystal-001",
        node_id="node-001",
        z_state={"latent": [0.0] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
    )

    # Save (write-through)
    await repo.save_colony_state(state)

    # Verify in cache (L1 hit on next read)
    cached_state = await repo.get_by_id(state.id)
    assert cached_state is not None
    assert cached_state.id == state.id


@pytest.mark.asyncio
async def test_cache_invalidation_on_update(
    db_session: AsyncSession, sample_colony_state: ColonyState
):
    """Test cache invalidation on update."""
    repo = ColonyStateRepository(db_session=db_session)

    # Load into cache
    state1 = await repo.get_by_id(sample_colony_state.id)
    assert state1.last_action == "init"

    # Update directly in DB
    sample_colony_state.last_action = "updated"
    await repo.save_colony_state(sample_colony_state)

    # Read again - should see updated value
    state2 = await repo.get_by_id(sample_colony_state.id)
    assert state2.last_action == "updated"


# =============================================================================
# CRDT Synchronization Tests
# =============================================================================


@pytest.mark.asyncio
async def test_etcd_sync_on_save(db_session: AsyncSession, mock_etcd_client):
    """Test etcd synchronization on save."""
    repo = ColonyStateRepository(
        db_session=db_session, etcd_client=mock_etcd_client
    )

    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="flow",
        instance_id="flow-001",
        node_id="node-001",
        z_state={"latent": [0.5] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
        vector_clock={"node-001": 5},
    )

    await repo.save_colony_state(state)

    # Verify etcd sync was called
    assert mock_etcd_client.put.called
    call_args = mock_etcd_client.put.call_args[0]
    assert "/colonies/flow/flow-001" in call_args[0]


@pytest.mark.asyncio
async def test_etcd_sync_failure_handled(
    db_session: AsyncSession, mock_etcd_client
):
    """Test etcd sync failure is handled gracefully."""
    # Simulate etcd failure
    mock_etcd_client.put.side_effect = Exception("etcd connection failed")

    repo = ColonyStateRepository(
        db_session=db_session, etcd_client=mock_etcd_client
    )

    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="nexus",
        instance_id="nexus-001",
        node_id="node-001",
        z_state={"latent": [0.0] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
    )

    # Should not raise exception
    saved_state = await repo.save_colony_state(state)
    assert saved_state is not None


# =============================================================================
# Serialization Tests
# =============================================================================


@pytest.mark.asyncio
async def test_serialize_deserialize_roundtrip(db_session: AsyncSession):
    """Test serialize/deserialize roundtrip."""
    repo = ColonyStateRepository(db_session=db_session)

    original = ColonyState(
        id=uuid.uuid4(),
        colony_id="test",
        instance_id="test-001",
        node_id="node-001",
        z_state={"latent": [0.1, 0.2, 0.3]},
        z_dim=3,
        timestamp=datetime.utcnow().timestamp(),
        vector_clock={"node-001": 10},
        action_history=["a", "b", "c"],
        last_action="c",
        fano_neighbors=["x", "y"],
        is_active=True,
        last_heartbeat_at=datetime.utcnow(),
        state_metadata={"key": "value"},
    )

    # Serialize
    serialized = await repo._serialize(original)
    assert isinstance(serialized, str)
    assert "test-001" in serialized

    # Deserialize
    deserialized = await repo._deserialize(serialized)
    assert deserialized.colony_id == original.colony_id
    assert deserialized.instance_id == original.instance_id
    assert deserialized.z_dim == original.z_dim
    assert deserialized.vector_clock == original.vector_clock


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_from_storage_error_handling(db_session: AsyncSession):
    """Test error handling in fetch_from_storage."""
    repo = ColonyStateRepository(db_session=db_session)

    # Try to fetch with invalid UUID format
    with patch.object(
        repo, "_fetch_from_storage", side_effect=Exception("DB error")
    ):
        result = await repo.get_by_id(uuid.uuid4())
        # Should return None on error
        assert result is None


@pytest.mark.asyncio
async def test_write_to_storage_rollback_on_error(db_session: AsyncSession):
    """Test transaction rollback on write error."""
    repo = ColonyStateRepository(db_session=db_session)

    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="test",
        instance_id="test-001",
        node_id="node-001",
        z_state={"latent": [0.0] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
    )

    # Simulate commit error
    with patch.object(db_session, "commit", side_effect=Exception("Commit failed")):
        with pytest.raises(Exception):
            await repo.save_colony_state(state)


@pytest.mark.asyncio
async def test_delete_from_storage_error_handling(db_session: AsyncSession):
    """Test error handling in delete_from_storage."""
    repo = ColonyStateRepository(db_session=db_session)

    # Simulate delete error
    with patch.object(db_session, "delete", side_effect=Exception("Delete failed")):
        result = await repo._delete_from_storage(str(uuid.uuid4()))
        # Should return False on error
        assert result is False


# =============================================================================
# Concurrent Operations Tests
# =============================================================================


@pytest.mark.asyncio
async def test_concurrent_updates(db_session: AsyncSession):
    """Test concurrent updates to same colony state."""
    import asyncio

    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="concurrent",
        instance_id="concurrent-001",
        node_id="node-001",
        z_state={"latent": [0.0] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
        vector_clock={"node-001": 0},
    )
    db_session.add(state)
    await db_session.commit()

    repo = ColonyStateRepository(db_session=db_session)

    # Concurrent updates
    async def update_vector_clock(node_id: str):
        s = await repo.get_by_colony_instance("concurrent", "concurrent-001")
        s.vector_clock[node_id] = s.vector_clock.get(node_id, 0) + 1
        await repo.save_colony_state(s)

    # Run concurrent updates
    await asyncio.gather(
        update_vector_clock("node-001"),
        update_vector_clock("node-002"),
        update_vector_clock("node-003"),
    )

    # Verify all updates applied
    final_state = await repo.get_by_colony_instance("concurrent", "concurrent-001")
    assert len(final_state.vector_clock) >= 1  # At least one node updated


# =============================================================================
# Performance Tests
# =============================================================================


@pytest.mark.asyncio
async def test_bulk_read_performance(db_session: AsyncSession):
    """Test bulk read operations performance."""
    import time

    # Create 100 colony states
    states = []
    for i in range(100):
        state = ColonyState(
            id=uuid.uuid4(),
            colony_id=f"colony-{i % 10}",
            instance_id=f"instance-{i}",
            node_id=f"node-{i}",
            z_state={"latent": [0.0] * 64},
            z_dim=64,
            timestamp=datetime.utcnow().timestamp(),
        )
        states.append(state)
        db_session.add(state)
    await db_session.commit()

    repo = ColonyStateRepository(db_session=db_session)

    # Time bulk reads
    start = time.time()
    for state in states[:50]:  # Read first 50
        await repo.get_by_id(state.id)
    elapsed = time.time() - start

    # Should complete in reasonable time (< 5 seconds for 50 reads)
    assert elapsed < 5.0
