# Kagami State Persistence

**Comprehensive state persistence layer for Kagami AI platform**

Created: December 28, 2025

---

## Overview

The persistence layer provides a unified API for saving and loading system state across multiple storage backends. It handles:

- **Colony States**: All 7 colonies with E8 embeddings and RSSM state
- **World Model**: RSSM parameters, trajectory cache, training checkpoints
- **Receipts**: Execution history (audit trail, stigmergic traces)
- **Memory**: Stigmergy patterns and collective memory

### Safety Invariant

```
h(state) >= 0    All persisted states must be valid and safe.
```

---

## Architecture

```
StateManager (Unified API)
    ├── ColonyStateStore      → 7 colonies × E8 embeddings
    ├── WorldModelStore       → RSSM parameters + trajectories
    ├── ReceiptStore          → Execution commits (audit trail)
    └── MemoryStore           → Stigmergy patterns
            │
            ├── Serializers (JSON, PyTorch, compression, encryption)
            │
            └── Storage Backends
                ├── FilesystemBackend   (JSON/pickle, fast local)
                ├── RedisBackend        (cache layer, sub-second)
                ├── PostgreSQLBackend   (durable, ACID)
                └── CloudBackend        (S3/GCS, infinite scale)
```

---

## Quick Start

### Basic Usage

```python
from kagami.core.persistence import configure_persistence, get_state_manager
from kagami.core.persistence import BackendType

# 1. Configure persistence (once at startup)
configure_persistence(
    backend_type=BackendType.FILESYSTEM,
    data_dir="/path/to/kagami/state"
)

# 2. Get manager instance
manager = get_state_manager()

# 3. Save state
checkpoint_id = await manager.save_state(
    name="training_epoch_42",
    colony_state=colony_snapshot,
    world_model=model_checkpoint,
    receipts=recent_receipts,
    metadata={"epoch": 42, "loss": 0.123}
)

# 4. Load state
checkpoint = await manager.load_state(checkpoint_id)

# 5. List checkpoints
checkpoints = await manager.list_checkpoints(limit=10)

# 6. Delete old checkpoint
await manager.delete_checkpoint(old_checkpoint_id)
```

### Auto-Save

```python
# Configure automatic checkpointing
await manager.configure_autosave(
    enabled=True,
    interval_seconds=300,  # Every 5 minutes
    keep_last_n=5,         # Keep 5 most recent
    components=["colonies", "world_model", "receipts", "memory"]
)
```

---

## Storage Backends

### Filesystem Backend (Local)

**Best for**: Development, testing, single-machine deployments

```python
configure_persistence(
    backend_type=BackendType.FILESYSTEM,
    data_dir="/path/to/state"
)
```

**Features**:
- Simple directory-based storage
- Automatic versioning with timestamps
- Metadata stored as JSON sidecar files
- No external dependencies
- Fast for local access

**Storage Layout**:
```
data_dir/
    checkpoints/
        epoch_42_1234567890/
            metadata.json
    colonies/
        epoch_42_1234567890/
            data.bin
            metadata.json
    world_model/
        epoch_42_1234567890/
            data.bin
            metadata.json
```

### Redis Backend (Cache)

**Best for**: Fast temporary state, recent checkpoints cache

```python
configure_persistence(
    backend_type=BackendType.REDIS,
    host="localhost",
    port=6379,
    db=0,
    ttl_seconds=3600  # 1 hour
)
```

**Features**:
- Sub-second access times
- Automatic TTL-based expiration
- Pub/sub for state change notifications
- Perfect for recent state caching

**Requirements**: `pip install redis`

### PostgreSQL Backend (Durable)

**Best for**: Production, ACID guarantees, distributed systems

```python
configure_persistence(
    backend_type=BackendType.POSTGRESQL
    # Uses existing kagami.core.database connection
)
```

**Features**:
- ACID transactions
- Full SQL query capabilities
- Reuses existing CockroachDB/PostgreSQL connection
- Binary data stored efficiently

### Cloud Backend (Archive)

**Best for**: Long-term archival, infinite scale, multi-region

```python
configure_persistence(
    backend_type=BackendType.CLOUD,
    provider="s3",           # or "gcs", "minio"
    bucket="kagami-state",
    region="us-east-1",
    access_key="...",
    secret_key="..."
)
```

**Features**:
- Infinite scalability
- Automatic versioning (S3 native)
- Lifecycle policies for cost optimization
- Multi-region replication

**Requirements**: `pip install boto3` (for S3/MinIO)

---

## State Components

### Colony State

Persists all 7 colony states with E8 embeddings:

```python
from kagami.core.persistence import ColonyStateSnapshot
import torch

# Create snapshot
snapshot = ColonyStateSnapshot(
    hidden_states={
        0: torch.randn(4, 128),  # Spark
        1: torch.randn(4, 128),  # Forge
        # ... 5 more colonies
    },
    stochastic_states={
        0: torch.randn(4, 64),
        # ...
    },
    e8_embeddings={
        0: torch.randn(8),  # 8D octonion
        # ...
    },
    timestep=42,
    active_colonies=[0, 1, 2, 3, 4, 5, 6],
    metadata={"context": "training"}
)

# Save
version = await manager.colony_store.save_snapshot("my_snapshot", snapshot)

# Load
loaded = await manager.colony_store.load_snapshot("my_snapshot")
```

### World Model

Persists RSSM parameters and trajectory cache:

```python
from kagami.core.persistence import WorldModelCheckpoint

# Create checkpoint
checkpoint = WorldModelCheckpoint(
    model_state_dict=model.state_dict(),
    trajectory_cache={
        "traj_0": torch.randn(10, 8),  # E8 quantized
    },
    epoch=10,
    step=1000,
    loss=0.123,
    metrics={"accuracy": 0.95},
    model_version="1.0.0",
    config={"hidden_dim": 128}
)

# Save
version = await manager.world_model_store.save_checkpoint("epoch_10", checkpoint)

# Load
loaded = await manager.world_model_store.load_checkpoint("epoch_10")
```

### Receipts

Persists execution history (audit trail):

```python
receipts = [
    {
        "correlation_id": "task_123",
        "action": "generate_character",
        "timestamp": 1234567890.0,
        "status": "success",
        "colony": "forge",
    },
    # More receipts...
]

version = await manager.receipt_store.save_receipts(
    "batch_2025_12_28",
    receipts,
    metadata={"batch_size": len(receipts)}
)
```

### Memory (Stigmergy)

Persists collective memory patterns:

```python
patterns = {
    "action1": {
        "success_count": 10,
        "failure_count": 2,
        "avg_latency": 0.5,
    },
    # More patterns...
}

version = await manager.memory_store.save_stigmergy(
    "stigmergy_snapshot",
    patterns,
    density=0.5,
    cooperation_metric=0.8,
    metadata={"agent_count": 7}
)
```

---

## Serialization

### Supported Formats

- **JSON**: Metadata, configuration, simple types
- **PyTorch**: Model parameters (safetensors or torch.save)
- **Pickle**: Complex Python objects (with safety checks)
- **NumPy**: Arrays and scientific data

### Compression

```python
from kagami.core.persistence import CompressionType

# Available options:
CompressionType.NONE    # No compression
CompressionType.GZIP    # Universal (slower)
CompressionType.ZSTD    # Fast, high ratio (default)
CompressionType.LZ4     # Ultra-fast
```

### Encryption

```python
from kagami.core.persistence.serializers import (
    generate_encryption_key,
    EncryptionType
)

# Generate key
key = generate_encryption_key()

# Configure with encryption
config = StorageConfig(
    backend_type=BackendType.FILESYSTEM,
    params={"data_dir": "/path"},
    encryption_enabled=True,
    encryption_key=key
)
```

---

## Advanced Features

### Incremental Checkpointing

Save only changed state:

```python
# Save partial state
checkpoint_id = await manager.save_state(
    "partial_update",
    include=["colonies"],  # Only save colonies
    colony_state=new_colony_state
)
```

### Versioning

All backends support versioning:

```python
# Save multiple versions
v1 = await backend.save(key, data1)
v2 = await backend.save(key, data2)
v3 = await backend.save(key, data3)

# List versions
versions = await backend.list_versions(key)

# Load specific version
data, meta = await backend.load(key, version=v1)

# Load latest
data, meta = await backend.load(key)
```

### Crash Recovery

```python
# List all checkpoints
checkpoints = await manager.list_checkpoints()

# Load most recent valid checkpoint
for checkpoint_meta in checkpoints:
    try:
        checkpoint = await manager.load_state(checkpoint_meta.checkpoint_id)
        print(f"Recovered from {checkpoint_meta.name}")
        break
    except Exception as e:
        print(f"Failed to load {checkpoint_meta.checkpoint_id}: {e}")
        continue
```

### State Verification

```python
# Checksums are automatically verified on load
try:
    data, meta = await backend.load(key)
    # Checksum verified ✓
except ValueError as e:
    print(f"Checksum mismatch: {e}")
```

---

## Performance

### Benchmarks (Approximate)

| Backend | Write Latency | Read Latency | Throughput |
|---------|--------------|--------------|------------|
| Filesystem | 5-50ms | 1-10ms | 100-500 MB/s |
| Redis | 1-5ms | <1ms | 1-5 GB/s |
| PostgreSQL | 10-100ms | 5-50ms | 50-200 MB/s |
| Cloud (S3) | 100-500ms | 50-200ms | 100-500 MB/s |

*Note: Actual performance depends on data size, compression, network, etc.*

### Optimization Tips

1. **Use compression**: ZSTD provides 3-5× compression with minimal overhead
2. **Enable versioning selectively**: Only for important checkpoints
3. **Prune old versions**: Set `max_versions` appropriately
4. **Use Redis for hot data**: Cache recent checkpoints in Redis
5. **Archive to cloud**: Move old checkpoints to S3 for cost savings

---

## Error Handling

```python
from kagami.core.persistence.backends.protocol import (
    StorageError,
    KeyNotFoundError,
    VersionNotFoundError,
    StorageFullError,
    StorageConnectionError
)

try:
    checkpoint = await manager.load_state(checkpoint_id)
except KeyNotFoundError:
    print("Checkpoint not found")
except VersionNotFoundError:
    print("Version not found")
except StorageConnectionError:
    print("Cannot connect to storage backend")
except StorageError as e:
    print(f"Storage error: {e}")
```

---

## Testing

Run the test suite:

```bash
# All persistence tests
pytest tests/core/persistence/

# Specific test
pytest tests/core/persistence/test_state_manager.py::test_end_to_end_persistence_workflow

# With coverage
pytest tests/core/persistence/ --cov=kagami.core.persistence --cov-report=html
```

---

## Migration Guide

### From Manual torch.save

```python
# OLD
torch.save(model.state_dict(), "checkpoint.pt")

# NEW
from kagami.core.persistence import configure_persistence, get_state_manager

configure_persistence(backend_type=BackendType.FILESYSTEM, data_dir="./checkpoints")
manager = get_state_manager()

checkpoint = WorldModelCheckpoint(model_state_dict=model.state_dict(), ...)
await manager.world_model_store.save_checkpoint("my_model", checkpoint)
```

### From Pickle Files

```python
# OLD
import pickle
with open("state.pkl", "wb") as f:
    pickle.dump(state, f)

# NEW
from kagami.core.persistence import configure_persistence, get_state_manager

configure_persistence(backend_type=BackendType.FILESYSTEM, data_dir="./state")
manager = get_state_manager()

await manager.save_state("my_state", colony_state=state, ...)
```

---

## File Inventory

```
kagami/core/persistence/
├── __init__.py                  # Public API exports
├── README.md                    # This file
├── serializers.py               # Serialization (JSON, tensors, compression)
├── state_manager.py             # Main StateManager API
├── colony_state_store.py        # Colony state persistence
├── world_model_store.py         # World model checkpoints
├── receipt_store.py             # Receipt history persistence
├── memory_store.py              # Stigmergy/memory persistence
└── backends/
    ├── __init__.py
    ├── protocol.py              # StorageBackend protocol
    ├── filesystem.py            # Filesystem backend
    ├── redis_backend.py         # Redis backend
    ├── postgres.py              # PostgreSQL backend
    └── cloud.py                 # S3/GCS backend

tests/core/persistence/
├── __init__.py
└── test_state_manager.py        # Comprehensive tests
```

**Total Code**: ~2,100 lines of production-quality Python

---

## API Reference

See docstrings in source files for detailed API documentation:

```python
# View docstring
from kagami.core.persistence import StateManager
help(StateManager.save_state)
```

---

## References

- PyTorch Saving & Loading: https://pytorch.org/tutorials/beginner/saving_loading_models.html
- safetensors: https://github.com/huggingface/safetensors
- Git Internals: https://git-scm.com/book/en/v2/Git-Internals-Git-Objects
- Redis Persistence: https://redis.io/topics/persistence
- S3 Versioning: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html

---

## License

Part of the Kagami AI platform. See LICENSE file in repository root.
