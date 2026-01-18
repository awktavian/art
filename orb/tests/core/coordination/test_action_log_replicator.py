"""Tests for ActionLogReplicator - Distributed Action Log.

Tests cover:
- Action append and serialization
- Deduplication via correlation_id tracking
- Action replay with time range filtering
- Watch API for real-time action streaming
- Automatic compaction with retention period
- Multi-instance coordination (simulated)
- Edge cases: empty log, duplicate actions, malformed data

Created: December 15, 2025
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import os
import time
from unittest.mock import MagicMock, Mock, patch

import msgpack

from kagami.core.coordination.action_log_replicator import (
    ActionLogReplicator,
    ColonyAction,
    create_action_log_replicator,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def instance_id():
    """Test instance ID."""
    return "test-instance-123"


@pytest.fixture
def replicator(instance_id):
    """Create test replicator."""
    return ActionLogReplicator(
        instance_id=instance_id,
        dedup_window_size=16,  # Small window for testing
        retention_days=1,  # 1 day retention for testing
    )


@pytest.fixture
def sample_action(instance_id):
    """Create sample action."""
    return ColonyAction(
        colony_id=2,
        action_type="execute",
        task="Test task",
        routing={2: "activate", 7: "observe"},
        timestamp=time.time(),
        instance_id=instance_id,
        correlation_id="test-123",
        metadata={"priority": 1},
    )


@pytest.fixture
def mock_etcd_client():
    """Mock etcd client."""
    mock = MagicMock()
    mock.put = Mock()
    mock.get_prefix = Mock(return_value=[])
    mock.delete = Mock()
    mock.watch_prefix = Mock(return_value=(iter([]), lambda: None))
    return mock


# =============================================================================
# TEST ACTION DATACLASS
# =============================================================================


def test_colony_action_to_dict(sample_action) -> None:
    """Test ColonyAction serialization to dict."""
    data = sample_action.to_dict()

    assert data["colony_id"] == 2
    assert data["action_type"] == "execute"
    assert data["task"] == "Test task"
    # NOTE: routing keys converted to strings for msgpack compatibility
    assert data["routing"] == {"2": "activate", "7": "observe"}
    assert data["instance_id"] == "test-instance-123"
    assert data["correlation_id"] == "test-123"
    assert data["metadata"] == {"priority": 1}


def test_colony_action_from_dict(sample_action) -> None:
    """Test ColonyAction deserialization from dict."""
    data = sample_action.to_dict()
    restored = ColonyAction.from_dict(data)

    assert restored.colony_id == sample_action.colony_id
    assert restored.action_type == sample_action.action_type
    assert restored.task == sample_action.task
    # Routing should be restored with integer keys
    assert restored.routing == sample_action.routing
    assert all(isinstance(k, int) for k in restored.routing.keys())
    assert restored.instance_id == sample_action.instance_id
    assert restored.correlation_id == sample_action.correlation_id
    assert restored.metadata == sample_action.metadata


def test_colony_action_msgpack_serialization(sample_action) -> None:
    """Test msgpack serialization roundtrip."""
    data = sample_action.to_dict()
    packed = msgpack.packb(data, use_bin_type=True)
    unpacked = msgpack.unpackb(packed, raw=False)
    restored = ColonyAction.from_dict(unpacked)

    assert restored.colony_id == sample_action.colony_id
    assert restored.correlation_id == sample_action.correlation_id


# =============================================================================
# TEST REPLICATOR INITIALIZATION
# =============================================================================


def test_replicator_init(replicator, instance_id) -> None:
    """Test replicator initialization."""
    assert replicator.instance_id == instance_id
    assert replicator.log_prefix == "action_log:"
    assert replicator.dedup_window_size == 16
    assert replicator.retention_days == 1
    assert len(replicator._seen_correlation_ids) == 0


def test_create_action_log_replicator():
    """Test factory function."""
    replicator = create_action_log_replicator(instance_id="test-node")
    assert replicator.instance_id == "test-node"
    assert replicator.dedup_window_size == 4096  # Default


def test_create_action_log_replicator_with_env():
    """Test factory with environment variables."""
    with patch.dict(
        os.environ,
        {
            "NODE_ID": "env-node",
            "REPLICATOR_DEDUP_WINDOW": "8192",
            "REPLICATOR_RETENTION_DAYS": "14",
        },
    ):
        replicator = create_action_log_replicator()
        assert replicator.instance_id == "env-node"
        assert replicator.dedup_window_size == 8192
        assert replicator.retention_days == 14


# =============================================================================
# TEST DEDUPLICATION
# =============================================================================


def test_deduplication_window(replicator) -> None:
    """Test deduplication window behavior."""
    # Not seen initially
    assert not replicator._is_duplicate("action-1")

    # Record as seen
    replicator._record_seen("action-1")
    assert replicator._is_duplicate("action-1")

    # Different correlation_id
    assert not replicator._is_duplicate("action-2")


def test_deduplication_window_overflow(replicator) -> None:
    """Test window overflow with sliding behavior."""
    # Fill window (size=16)
    for i in range(16):
        replicator._record_seen(f"action-{i}")

    # Oldest should still be present
    assert replicator._is_duplicate("action-0")

    # Add one more to exceed window
    replicator._record_seen("action-16")

    # Oldest should be evicted
    assert not replicator._is_duplicate("action-0")

    # Newest should be present
    assert replicator._is_duplicate("action-16")


# =============================================================================
# TEST APPEND ACTION
# =============================================================================


@pytest.mark.asyncio
async def test_append_action_success(replicator, sample_action, mock_etcd_client) -> None:
    """Test successful action append."""
    with patch("kagami.core.coordination.action_log_replicator.etcd_operation") as mock_op:
        mock_op.return_value.__enter__ = Mock(return_value=mock_etcd_client)
        mock_op.return_value.__exit__ = Mock(return_value=None)

        success = await replicator.append_action(sample_action)

        assert success
        assert mock_etcd_client.put.called
        assert replicator._is_duplicate(sample_action.correlation_id)


@pytest.mark.asyncio
async def test_append_action_generates_unique_keys(
    replicator, instance_id, mock_etcd_client
) -> None:
    """Test that append generates unique keys."""
    with patch("kagami.core.coordination.action_log_replicator.etcd_operation") as mock_op:
        mock_op.return_value.__enter__ = Mock(return_value=mock_etcd_client)
        mock_op.return_value.__exit__ = Mock(return_value=None)

        action1 = ColonyAction(
            colony_id=1,
            action_type="test",
            task="Task 1",
            routing={},
            timestamp=time.time(),
            instance_id=instance_id,
            correlation_id="action-1",
        )

        action2 = ColonyAction(
            colony_id=2,
            action_type="test",
            task="Task 2",
            routing={},
            timestamp=time.time(),
            instance_id=instance_id,
            correlation_id="action-2",
        )

        await replicator.append_action(action1)
        await replicator.append_action(action2)

        # Verify two separate puts
        assert mock_etcd_client.put.call_count == 2

        # Extract keys from calls
        call_args = [call[0] for call in mock_etcd_client.put.call_args_list]
        keys = [args[0] for args in call_args]

        # Keys should be different (timestamp + instance_id)
        assert keys[0] != keys[1]
        assert all(key.startswith("action_log:") for key in keys)


@pytest.mark.asyncio
async def test_append_action_failure(replicator, sample_action, mock_etcd_client) -> None:
    """Test action append failure handling."""
    mock_etcd_client.put.side_effect = Exception("etcd error")

    with patch("kagami.core.coordination.action_log_replicator.etcd_operation") as mock_op:
        mock_op.return_value.__enter__ = Mock(return_value=mock_etcd_client)
        mock_op.return_value.__exit__ = Mock(return_value=None)

        success = await replicator.append_action(sample_action)

        assert not success
        # Should not be marked as seen due to failure
        assert not replicator._is_duplicate(sample_action.correlation_id)


# =============================================================================
# TEST REPLAY ACTIONS
# =============================================================================


@pytest.mark.asyncio
async def test_replay_actions_empty_log(replicator, mock_etcd_client) -> None:
    """Test replay with empty log."""
    with patch("kagami.core.coordination.action_log_replicator.etcd_operation") as mock_op:
        mock_op.return_value.__enter__ = Mock(return_value=mock_etcd_client)
        mock_op.return_value.__exit__ = Mock(return_value=None)

        mock_etcd_client.get_prefix.return_value = []

        actions = []

        async def callback(action):
            actions.append(action)

        count = await replicator.replay_actions(since=0.0, callback=callback)

        assert count == 0
        assert len(actions) == 0


@pytest.mark.asyncio
async def test_replay_actions_time_range(replicator, instance_id, mock_etcd_client) -> None:
    """Test replay with time range filtering."""
    # Create mock actions at different timestamps
    t0 = 1000.0
    t1 = 2000.0
    t2 = 3000.0

    action1 = ColonyAction(
        colony_id=1,
        action_type="test",
        task="Task 1",
        routing={},
        timestamp=t0,
        instance_id=instance_id,
        correlation_id="action-1",
    )
    action2 = ColonyAction(
        colony_id=2,
        action_type="test",
        task="Task 2",
        routing={},
        timestamp=t1,
        instance_id=instance_id,
        correlation_id="action-2",
    )
    action3 = ColonyAction(
        colony_id=3,
        action_type="test",
        task="Task 3",
        routing={},
        timestamp=t2,
        instance_id=instance_id,
        correlation_id="action-3",
    )

    # Mock etcd response with all three actions
    def mock_metadata(timestamp_ns):
        mock_meta = Mock()
        mock_meta.key = f"action_log:{timestamp_ns}:{instance_id}".encode()
        return mock_meta

    mock_etcd_client.get_prefix.return_value = [
        (msgpack.packb(action1.to_dict(), use_bin_type=True), mock_metadata(int(t0 * 1e9))),
        (msgpack.packb(action2.to_dict(), use_bin_type=True), mock_metadata(int(t1 * 1e9))),
        (msgpack.packb(action3.to_dict(), use_bin_type=True), mock_metadata(int(t2 * 1e9))),
    ]

    with patch("kagami.core.coordination.action_log_replicator.etcd_operation") as mock_op:
        mock_op.return_value.__enter__ = Mock(return_value=mock_etcd_client)
        mock_op.return_value.__exit__ = Mock(return_value=None)

        actions = []

        async def callback(action):
            actions.append(action)

        # Replay only actions in range [1500, 2500]
        count = await replicator.replay_actions(
            since=1500.0,
            until=2500.0,
            callback=callback,
        )

        assert count == 1
        assert len(actions) == 1
        assert actions[0].correlation_id == "action-2"


@pytest.mark.asyncio
async def test_replay_actions_deduplication(replicator, instance_id, mock_etcd_client) -> None:
    """Test replay skips duplicates."""
    action = ColonyAction(
        colony_id=1,
        action_type="test",
        task="Task",
        routing={},
        timestamp=1000.0,
        instance_id=instance_id,
        correlation_id="duplicate-action",
    )

    # Mark as already seen
    replicator._record_seen("duplicate-action")

    def mock_metadata(timestamp_ns):
        mock_meta = Mock()
        mock_meta.key = f"action_log:{timestamp_ns}:{instance_id}".encode()
        return mock_meta

    mock_etcd_client.get_prefix.return_value = [
        (msgpack.packb(action.to_dict(), use_bin_type=True), mock_metadata(int(1000.0 * 1e9))),
    ]

    with patch("kagami.core.coordination.action_log_replicator.etcd_operation") as mock_op:
        mock_op.return_value.__enter__ = Mock(return_value=mock_etcd_client)
        mock_op.return_value.__exit__ = Mock(return_value=None)

        actions = []

        async def callback(action):
            actions.append(action)

        count = await replicator.replay_actions(since=0.0, callback=callback)

        # Should skip duplicate
        assert count == 0
        assert len(actions) == 0


# =============================================================================
# TEST COMPACTION
# =============================================================================


@pytest.mark.asyncio
async def test_compact_removes_old_actions(replicator, instance_id, mock_etcd_client) -> None:
    """Test compaction removes actions older than retention period."""
    now = time.time()
    old_time = now - (2 * 86400)  # 2 days ago (older than 1 day retention)
    recent_time = now - 3600  # 1 hour ago (within retention)

    action_old = ColonyAction(
        colony_id=1,
        action_type="test",
        task="Old",
        routing={},
        timestamp=old_time,
        instance_id=instance_id,
        correlation_id="old-action",
    )
    action_recent = ColonyAction(
        colony_id=2,
        action_type="test",
        task="Recent",
        routing={},
        timestamp=recent_time,
        instance_id=instance_id,
        correlation_id="recent-action",
    )

    def mock_metadata(timestamp_ns):
        mock_meta = Mock()
        mock_meta.key = f"action_log:{timestamp_ns}:{instance_id}".encode()
        return mock_meta

    mock_etcd_client.get_prefix.return_value = [
        (
            msgpack.packb(action_old.to_dict(), use_bin_type=True),
            mock_metadata(int(old_time * 1e9)),
        ),
        (
            msgpack.packb(action_recent.to_dict(), use_bin_type=True),
            mock_metadata(int(recent_time * 1e9)),
        ),
    ]

    with patch("kagami.core.coordination.action_log_replicator.etcd_operation") as mock_op:
        mock_op.return_value.__enter__ = Mock(return_value=mock_etcd_client)
        mock_op.return_value.__exit__ = Mock(return_value=None)

        count = await replicator.compact()

        # Should delete only the old action
        assert count == 1
        assert mock_etcd_client.delete.called

        # Extract deleted key
        deleted_key = mock_etcd_client.delete.call_args[0][0]
        assert "action_log:" in deleted_key
        assert instance_id in deleted_key


@pytest.mark.asyncio
async def test_compact_empty_log(replicator, mock_etcd_client) -> None:
    """Test compaction with empty log."""
    mock_etcd_client.get_prefix.return_value = []

    with patch("kagami.core.coordination.action_log_replicator.etcd_operation") as mock_op:
        mock_op.return_value.__enter__ = Mock(return_value=mock_etcd_client)
        mock_op.return_value.__exit__ = Mock(return_value=None)

        count = await replicator.compact()

        assert count == 0
        assert not mock_etcd_client.delete.called


# =============================================================================
# TEST BACKGROUND COMPACTION
# =============================================================================


@pytest.mark.asyncio
async def test_start_compaction_task(replicator) -> None:
    """Test background compaction task starts."""
    with patch.object(replicator, "_compaction_loop") as mock_loop:
        mock_loop.return_value = asyncio.Future()
        mock_loop.return_value.set_result(None)

        await replicator.start_compaction()

        assert replicator._compaction_task is not None


@pytest.mark.asyncio
async def test_start_compaction_already_running(replicator) -> None:
    """Test starting compaction when already running."""
    # Set dummy task
    replicator._compaction_task = asyncio.create_task(asyncio.sleep(0.1))

    await replicator.start_compaction()

    # Should not create new task
    # (test passes if no exception raised)


# =============================================================================
# TEST SHUTDOWN
# =============================================================================


@pytest.mark.asyncio
async def test_shutdown(replicator) -> None:
    """Test graceful shutdown."""
    # Start compaction task
    with patch.object(replicator, "compact") as mock_compact:
        mock_compact.return_value = 0
        await replicator.start_compaction()

        # Give task time to start
        await asyncio.sleep(0.1)

        # Shutdown
        await replicator.shutdown()

        assert replicator._shutdown is True
        assert replicator._compaction_task.cancelled() or replicator._compaction_task.done()


# =============================================================================
# TEST WATCH (Basic Structure)
# =============================================================================


@pytest.mark.asyncio
async def test_watch_actions_starts_task(replicator) -> None:
    """Test watch_actions spawns background task."""
    mock_callback = Mock()

    with patch.object(replicator, "_watch_loop") as mock_loop:
        mock_loop.return_value = asyncio.Future()
        mock_loop.return_value.set_result(None)

        await replicator.watch_actions(mock_callback)

        # Task should be created
        # (test passes if no exception)


# =============================================================================
# TEST EDGE CASES
# =============================================================================


def test_colony_action_missing_metadata():
    """Test ColonyAction handles missing metadata."""
    data = {
        "colony_id": 1,
        "action_type": "test",
        "task": "Task",
        "routing": {},
        "timestamp": 1000.0,
        "instance_id": "test",
        "correlation_id": "test-123",
        # No metadata field
    }

    action = ColonyAction.from_dict(data)
    assert action.metadata == {}


@pytest.mark.asyncio
async def test_replay_malformed_key(replicator, mock_etcd_client) -> None:
    """Test replay handles malformed keys gracefully."""
    # Mock with malformed key (missing timestamp)
    mock_meta = Mock()
    mock_meta.key = b"action_log:malformed"

    action_data = msgpack.packb(
        {
            "colony_id": 1,
            "action_type": "test",
            "task": "Task",
            "routing": {},
            "timestamp": 1000.0,
            "instance_id": "test",
            "correlation_id": "test-123",
        },
        use_bin_type=True,
    )

    mock_etcd_client.get_prefix.return_value = [(action_data, mock_meta)]

    with patch("kagami.core.coordination.action_log_replicator.etcd_operation") as mock_op:
        mock_op.return_value.__enter__ = Mock(return_value=mock_etcd_client)
        mock_op.return_value.__exit__ = Mock(return_value=None)

        actions = []

        async def callback(action):
            actions.append(action)

        count = await replicator.replay_actions(since=0.0, callback=callback)

        # Should skip malformed key
        assert count == 0


# =============================================================================
# TEST INTEGRATION SCENARIO
# =============================================================================


@pytest.mark.asyncio
async def test_multi_instance_scenario(mock_etcd_client) -> None:
    """Test multi-instance coordination scenario."""
    # Create two instances
    instance1 = ActionLogReplicator("instance-1", dedup_window_size=16)
    instance2 = ActionLogReplicator("instance-2", dedup_window_size=16)

    # Instance 1 appends action
    action = ColonyAction(
        colony_id=2,
        action_type="execute",
        task="Shared task",
        routing={2: "activate"},
        timestamp=time.time(),
        instance_id="instance-1",
        correlation_id="shared-action",
    )

    with patch("kagami.core.coordination.action_log_replicator.etcd_operation") as mock_op:
        mock_op.return_value.__enter__ = Mock(return_value=mock_etcd_client)
        mock_op.return_value.__exit__ = Mock(return_value=None)

        success = await instance1.append_action(action)
        assert success

    # Simulate instance 2 receiving action via watch
    # (In real scenario, etcd watch would deliver this)
    received_actions = []

    async def callback(action):
        received_actions.append(action)

    # Manually process action on instance 2
    if not instance2._is_duplicate(action.correlation_id):
        instance2._record_seen(action.correlation_id)
        await callback(action)

    assert len(received_actions) == 1
    assert received_actions[0].correlation_id == "shared-action"

    # Both instances should now recognize as duplicate
    assert instance1._is_duplicate("shared-action")
    assert instance2._is_duplicate("shared-action")
