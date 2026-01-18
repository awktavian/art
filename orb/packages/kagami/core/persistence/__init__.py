from typing import Any

"""State Persistence Layer for Kagami.

CREATED: December 28, 2025
PURPOSE: Comprehensive state persistence for colonies, world model, receipts, and memory.

This module provides a unified API for saving and loading system state across
multiple storage backends (filesystem, Redis, PostgreSQL, S3/GCS).

Key Components:
- StateManager: Main API for checkpoint save/load/list[Any]
- ColonyStateStore: Persist all 7 colony states with E8 embeddings
- WorldModelStore: RSSM parameters, trajectory cache, version migration
- ReceiptStore: Persistent execution history (receipt commits)
- MemoryStore: Stigmergy patterns and collective memory
- Serializers: JSON, PyTorch tensors (safetensors), compression, encryption

Features:
- Incremental checkpointing (save only changed state)
- Auto-save with configurable intervals
- Crash recovery and partial state recovery
- State verification and corruption detection
- Multi-backend support with transparent failover
- Async/await support throughout
- Encryption at rest (AES-256-GCM)
- Compression (zstd for speed, gzip for compatibility)

Safety Invariant:
    h(state) >= 0    All persisted states must be valid and safe.

Architecture:
    StateManager
        ├── ColonyStateStore (7 colonies × E8 embeddings)
        ├── WorldModelStore (RSSM, trajectories)
        ├── ReceiptStore (execution commits)
        └── MemoryStore (stigmergy patterns)
            ├── FilesystemBackend (JSON/pickle, fast local)
            ├── RedisBackend (cache layer, sub-second)
            ├── PostgreSQLBackend (durable, ACID)
            └── CloudBackend (S3/GCS, archive)

Usage:
    from kagami.core.persistence import StateManager, get_state_manager

    # Get singleton instance
    manager = get_state_manager()

    # Save complete system state
    checkpoint_id = await manager.save_state(
        name="training_epoch_42",
        include=["colonies", "world_model", "receipts", "memory"]
    )

    # Load state
    state = await manager.load_state(checkpoint_id)

    # List all checkpoints
    checkpoints = await manager.list_checkpoints(limit=10)

    # Auto-save configuration
    await manager.configure_autosave(
        enabled=True,
        interval_seconds=300,
        keep_last_n=5
    )

References:
- PyTorch state_dict: https://pytorch.org/tutorials/beginner/saving_loading_models.html
- safetensors: https://github.com/huggingface/safetensors
- Git internals: https://git-scm.com/book/en/v2/Git-Internals-Git-Objects
"""

from kagami.core.persistence.backends.cloud import CloudBackend
from kagami.core.persistence.backends.filesystem import FilesystemBackend
from kagami.core.persistence.backends.postgres import PostgreSQLBackend
from kagami.core.persistence.backends.protocol import (
    BackendType,
    StorageBackend,
    StorageConfig,
)
from kagami.core.persistence.backends.redis_backend import RedisBackend
from kagami.core.persistence.colony_state_store import (
    ColonyStateSnapshot,
    ColonyStateStore,
)
from kagami.core.persistence.consciousness_state import (
    ConsciousnessStatePersistence,
    PersistentConsciousnessState,
    get_consciousness_persistence,
    initialize_consciousness_persistence,
    reset_consciousness_persistence,
)
from kagami.core.persistence.memory_store import (
    MemoryStore,
    StigmergySnapshot,
)
from kagami.core.persistence.receipt_store import (
    PersistentReceiptStore,
    ReceiptSnapshot,
)
from kagami.core.persistence.serializers import (
    CompressionType,
    JSONSerializer,
    StateSerializer,
    TensorSerializer,
    compress_data,
    decompress_data,
    decrypt_data,
    encrypt_data,
)
from kagami.core.persistence.state_manager import (
    AutoSaveConfig,
    Checkpoint,
    CheckpointMetadata,
    StateManager,
    configure_persistence,
    get_state_manager,
)
from kagami.core.persistence.world_model_store import (
    WorldModelCheckpoint,
    WorldModelStore,
)

__all__ = [
    "AutoSaveConfig",
    "BackendType",
    "Checkpoint",
    "CheckpointMetadata",
    "CloudBackend",
    "ColonyStateSnapshot",
    # Store components
    "ColonyStateStore",
    "CompressionType",
    # Consciousness State (Dec 30, 2025 - etcd distributed sync)
    "ConsciousnessStatePersistence",
    # Backend implementations
    "FilesystemBackend",
    "JSONSerializer",
    "MemoryStore",
    "PersistentConsciousnessState",
    "PersistentReceiptStore",
    "PostgreSQLBackend",
    "ReceiptSnapshot",
    "RedisBackend",
    # Main API
    "StateManager",
    # Serialization
    "StateSerializer",
    "StigmergySnapshot",
    # Backend protocol
    "StorageBackend",
    "StorageConfig",
    "TensorSerializer",
    "WorldModelCheckpoint",
    "WorldModelStore",
    "compress_data",
    "configure_persistence",
    "decompress_data",
    "decrypt_data",
    "encrypt_data",
    "get_consciousness_persistence",
    "get_state_manager",
    "initialize_consciousness_persistence",
    "reset_consciousness_persistence",
]

__version__ = "1.0.0"
__description__ = "Comprehensive state persistence layer for Kagami"
