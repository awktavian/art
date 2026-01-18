"""Comprehensive tests for Kagami state persistence.

CREATED: December 28, 2025
PURPOSE: Test all persistence components end-to-end.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
import torch

from kagami.core.persistence import (
    StateManager,
    configure_persistence,
    BackendType,
    ColonyStateSnapshot,
    WorldModelCheckpoint,
    CompressionType,
)
from kagami.core.persistence.backends.filesystem import FilesystemBackend
from kagami.core.persistence.backends.protocol import StorageConfig


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Create temporary storage directory."""
    storage_dir = tmp_path / "kagami_state"
    storage_dir.mkdir()
    return storage_dir


@pytest.fixture
def filesystem_backend(temp_storage_dir):
    """Create filesystem backend for testing."""
    config = StorageConfig(
        backend_type=BackendType.FILESYSTEM,
        params={"data_dir": str(temp_storage_dir)},
        compression_enabled=True,
        enable_versioning=True,
        max_versions=5,
    )
    return FilesystemBackend(config)


@pytest.fixture
def state_manager(filesystem_backend):
    """Create state manager for testing."""
    return StateManager(filesystem_backend, compression=CompressionType.ZSTD)


@pytest.fixture
def sample_colony_state():
    """Create sample colony state."""
    hidden_states = {}
    stochastic_states = {}
    e8_embeddings = {}

    for colony_id in range(7):
        hidden_states[colony_id] = torch.randn(4, 128)  # batch=4, hidden=128
        stochastic_states[colony_id] = torch.randn(4, 64)  # batch=4, stoch=64
        e8_embeddings[colony_id] = torch.randn(8)  # 8D octonion

    return ColonyStateSnapshot(
        hidden_states=hidden_states,
        stochastic_states=stochastic_states,
        e8_embeddings=e8_embeddings,
        timestep=42,
        active_colonies=[0, 1, 2, 3, 4, 5, 6],
        metadata={"test": "data"},
    )


@pytest.fixture
def sample_world_model():
    """Create sample world model checkpoint."""
    # Create dummy model state
    model_state = {
        "encoder.weight": torch.randn(256, 128),
        "encoder.bias": torch.randn(256),
        "decoder.weight": torch.randn(128, 256),
        "decoder.bias": torch.randn(128),
    }

    # Create trajectory cache
    trajectory_cache = {
        "traj_0": torch.randn(10, 8),  # 10 timesteps, 8D E8
        "traj_1": torch.randn(10, 8),
    }

    return WorldModelCheckpoint(
        model_state_dict=model_state,
        trajectory_cache=trajectory_cache,
        epoch=10,
        step=1000,
        loss=0.123,
        metrics={"accuracy": 0.95, "loss": 0.123},
        model_version="1.0.0",
        config={"hidden_dim": 128},
        metadata={"training": "complete"},
    )


# =============================================================================
# SERIALIZER TESTS
# =============================================================================


def test_json_serializer():
    """Test JSON serialization."""
    from kagami.core.persistence.serializers import JSONSerializer

    serializer = JSONSerializer()
    data = {"test": "value", "number": 42, "list": [1, 2, 3]}

    # Serialize
    serialized = serializer.serialize(data)
    assert isinstance(serialized, bytes)

    # Deserialize
    deserialized = serializer.deserialize(serialized)
    assert deserialized == data


def test_tensor_serializer():
    """Test tensor serialization."""
    from kagami.core.persistence.serializers import TensorSerializer

    serializer = TensorSerializer(use_safetensors=False)  # Use torch.save
    tensors = {
        "weight": torch.randn(100, 50),
        "bias": torch.randn(100),
    }

    # Serialize
    serialized = serializer.serialize(tensors)
    assert isinstance(serialized, bytes)

    # Deserialize
    deserialized = serializer.deserialize(serialized)
    assert "weight" in deserialized
    assert "bias" in deserialized
    assert torch.allclose(deserialized["weight"], tensors["weight"])
    assert torch.allclose(deserialized["bias"], tensors["bias"])


def test_compression():
    """Test compression and decompression."""
    from kagami.core.persistence.serializers import (
        compress_data,
        decompress_data,
        CompressionType,
    )

    data = b"Hello, World!" * 1000  # Repeated data compresses well

    # Test GZIP
    compressed = compress_data(data, CompressionType.GZIP)
    assert len(compressed) < len(data)
    decompressed = decompress_data(compressed, CompressionType.GZIP)
    assert decompressed == data


def test_checksum():
    """Test checksum computation and verification."""
    from kagami.core.persistence.serializers import compute_checksum, verify_checksum

    data = b"test data"
    checksum = compute_checksum(data)
    assert isinstance(checksum, str)
    assert len(checksum) == 64  # SHA256 hex

    # Verify
    assert verify_checksum(data, checksum)
    assert not verify_checksum(b"wrong data", checksum)


# =============================================================================
# BACKEND TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_filesystem_backend_save_load(filesystem_backend):
    """Test filesystem backend save and load."""
    key = "test/data"
    data = b"Hello, World!"
    metadata = {"test": "metadata"}

    # Save
    version = await filesystem_backend.save(key, data, metadata)
    assert version.startswith("v")

    # Load
    loaded_data, loaded_meta = await filesystem_backend.load(key)
    assert loaded_data == data
    assert "checksum" in loaded_meta
    assert loaded_meta["test"] == "metadata"


@pytest.mark.asyncio
async def test_filesystem_backend_versioning(filesystem_backend):
    """Test filesystem backend versioning."""
    key = "test/versioned"

    # Save multiple versions
    version1 = await filesystem_backend.save(key, b"version 1")
    await asyncio.sleep(0.001)  # Ensure different timestamps
    version2 = await filesystem_backend.save(key, b"version 2")
    await asyncio.sleep(0.001)
    version3 = await filesystem_backend.save(key, b"version 3")

    # List versions
    versions = await filesystem_backend.list_versions(key)
    assert len(versions) >= 3

    # Load specific version
    data1, _ = await filesystem_backend.load(key, version1)
    assert data1 == b"version 1"

    data2, _ = await filesystem_backend.load(key, version2)
    assert data2 == b"version 2"

    # Load latest
    latest, _ = await filesystem_backend.load(key)
    assert latest == b"version 3"


@pytest.mark.asyncio
async def test_filesystem_backend_delete(filesystem_backend):
    """Test filesystem backend delete."""
    key = "test/delete"
    await filesystem_backend.save(key, b"data")

    # Verify exists
    assert await filesystem_backend.exists(key)

    # Delete
    deleted = await filesystem_backend.delete(key)
    assert deleted

    # Verify doesn't exist
    assert not await filesystem_backend.exists(key)


@pytest.mark.asyncio
async def test_filesystem_backend_list_keys(filesystem_backend):
    """Test listing keys."""
    # Save multiple keys
    await filesystem_backend.save("test/key1", b"data1")
    await filesystem_backend.save("test/key2", b"data2")
    await filesystem_backend.save("other/key3", b"data3")

    # List all
    keys = await filesystem_backend.list_keys()
    assert len(keys) >= 3

    # List with prefix
    test_keys = await filesystem_backend.list_keys(prefix="test")
    assert len(test_keys) >= 2


# =============================================================================
# COLONY STATE STORE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_colony_state_store_save_load(state_manager, sample_colony_state):
    """Test colony state store save and load."""
    snapshot_id = "test_colony_snapshot"

    # Save
    version = await state_manager.colony_store.save_snapshot(
        snapshot_id, sample_colony_state
    )
    assert version.startswith("v")

    # Load
    loaded = await state_manager.colony_store.load_snapshot(snapshot_id)

    # Verify
    assert loaded.timestep == sample_colony_state.timestep
    assert loaded.active_colonies == sample_colony_state.active_colonies
    assert len(loaded.hidden_states) == 7
    assert len(loaded.stochastic_states) == 7
    assert len(loaded.e8_embeddings) == 7

    # Check tensors match
    for colony_id in range(7):
        assert torch.allclose(
            loaded.hidden_states[colony_id],
            sample_colony_state.hidden_states[colony_id],
        )
        assert torch.allclose(
            loaded.e8_embeddings[colony_id],
            sample_colony_state.e8_embeddings[colony_id],
        )


@pytest.mark.asyncio
async def test_colony_state_store_list(state_manager, sample_colony_state):
    """Test listing colony snapshots."""
    # Save multiple snapshots
    await state_manager.colony_store.save_snapshot("snapshot1", sample_colony_state)
    await state_manager.colony_store.save_snapshot("snapshot2", sample_colony_state)

    # List
    snapshots = await state_manager.colony_store.list_snapshots()
    assert len(snapshots) >= 2


# =============================================================================
# WORLD MODEL STORE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_world_model_store_save_load(state_manager, sample_world_model):
    """Test world model store save and load."""
    checkpoint_id = "test_world_model"

    # Save
    version = await state_manager.world_model_store.save_checkpoint(
        checkpoint_id, sample_world_model
    )
    assert version.startswith("v")

    # Load
    loaded = await state_manager.world_model_store.load_checkpoint(checkpoint_id)

    # Verify
    assert loaded.epoch == sample_world_model.epoch
    assert loaded.step == sample_world_model.step
    assert loaded.loss == sample_world_model.loss
    assert loaded.model_version == sample_world_model.model_version

    # Check model state dict
    assert len(loaded.model_state_dict) == len(sample_world_model.model_state_dict)

    # Check trajectory cache
    assert len(loaded.trajectory_cache) == len(sample_world_model.trajectory_cache)


# =============================================================================
# STATE MANAGER TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_state_manager_save_load_complete(
    state_manager, sample_colony_state, sample_world_model
):
    """Test complete state save and load."""
    checkpoint_name = "complete_checkpoint"

    # Sample receipts and stigmergy
    receipts = [
        {"action": "test", "timestamp": 123.456, "status": "success"},
        {"action": "test2", "timestamp": 123.789, "status": "success"},
    ]
    stigmergy_patterns = {
        "pattern1": {"success": 10, "failure": 2},
        "pattern2": {"success": 5, "failure": 1},
    }

    # Save complete state
    checkpoint_id = await state_manager.save_state(
        name=checkpoint_name,
        colony_state=sample_colony_state,
        world_model=sample_world_model,
        receipts=receipts,
        stigmergy_patterns=stigmergy_patterns,
        stigmergy_density=0.5,
        stigmergy_cooperation=0.8,
        metadata={"test": "complete"},
    )

    assert checkpoint_name in checkpoint_id

    # Load complete state
    checkpoint = await state_manager.load_state(checkpoint_id)

    # Verify
    assert checkpoint.checkpoint_id == checkpoint_id
    assert checkpoint.colony_state is not None
    assert checkpoint.world_model is not None
    assert checkpoint.receipts is not None
    assert checkpoint.stigmergy is not None

    # Check colony state
    assert checkpoint.colony_state.timestep == sample_colony_state.timestep

    # Check world model
    assert checkpoint.world_model.epoch == sample_world_model.epoch

    # Check receipts
    assert checkpoint.receipts.count == len(receipts)

    # Check stigmergy
    assert checkpoint.stigmergy.density == 0.5
    assert checkpoint.stigmergy.cooperation_metric == 0.8


@pytest.mark.asyncio
async def test_state_manager_list_checkpoints(
    state_manager, sample_colony_state
):
    """Test listing checkpoints."""
    # Save multiple checkpoints
    await state_manager.save_state(
        "checkpoint1",
        colony_state=sample_colony_state,
    )
    await state_manager.save_state(
        "checkpoint2",
        colony_state=sample_colony_state,
    )

    # List
    checkpoints = await state_manager.list_checkpoints(limit=10)
    assert len(checkpoints) >= 2

    # Check metadata
    for checkpoint_meta in checkpoints:
        assert checkpoint_meta.checkpoint_id
        assert checkpoint_meta.name
        assert checkpoint_meta.timestamp > 0
        assert "colonies" in checkpoint_meta.components


@pytest.mark.asyncio
async def test_state_manager_delete_checkpoint(
    state_manager, sample_colony_state
):
    """Test deleting checkpoint."""
    checkpoint_id = await state_manager.save_state(
        "to_delete",
        colony_state=sample_colony_state,
    )

    # Delete
    deleted = await state_manager.delete_checkpoint(checkpoint_id)
    assert deleted

    # Verify deleted (should raise KeyError)
    with pytest.raises(Exception):
        await state_manager.load_state(checkpoint_id)


@pytest.mark.asyncio
async def test_state_manager_partial_save_load(
    state_manager, sample_colony_state, sample_world_model
):
    """Test saving and loading partial state."""
    # Save only colonies
    checkpoint_id = await state_manager.save_state(
        "partial_colonies",
        include=["colonies"],
        colony_state=sample_colony_state,
    )

    # Load
    checkpoint = await state_manager.load_state(checkpoint_id)
    assert checkpoint.colony_state is not None
    assert checkpoint.world_model is None

    # Save only world model
    checkpoint_id2 = await state_manager.save_state(
        "partial_world_model",
        include=["world_model"],
        world_model=sample_world_model,
    )

    # Load
    checkpoint2 = await state_manager.load_state(checkpoint_id2)
    assert checkpoint2.colony_state is None
    assert checkpoint2.world_model is not None


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_configure_persistence_singleton(temp_storage_dir):
    """Test configure_persistence singleton."""
    # Configure
    manager = configure_persistence(
        backend_type=BackendType.FILESYSTEM,
        data_dir=str(temp_storage_dir),
    )

    assert manager is not None

    # Get singleton
    from kagami.core.persistence import get_state_manager

    manager2 = get_state_manager()
    assert manager2 is manager  # Same instance


@pytest.mark.asyncio
async def test_end_to_end_persistence_workflow(temp_storage_dir):
    """Test complete end-to-end persistence workflow."""
    # 1. Configure persistence
    manager = configure_persistence(
        backend_type=BackendType.FILESYSTEM,
        data_dir=str(temp_storage_dir / "e2e"),
    )

    # 2. Create sample state
    colony_state = ColonyStateSnapshot(
        hidden_states={0: torch.randn(4, 128)},
        stochastic_states={0: torch.randn(4, 64)},
        e8_embeddings={0: torch.randn(8)},
    )

    # 3. Save checkpoint
    checkpoint_id = await manager.save_state(
        "e2e_checkpoint",
        colony_state=colony_state,
    )

    # 4. List checkpoints
    checkpoints = await manager.list_checkpoints()
    assert len(checkpoints) >= 1

    # 5. Load checkpoint
    loaded = await manager.load_state(checkpoint_id)
    assert loaded.colony_state is not None

    # 6. Delete checkpoint
    deleted = await manager.delete_checkpoint(checkpoint_id)
    assert deleted

    # 7. Close manager
    await manager.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
