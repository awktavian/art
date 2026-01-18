"""Consensus and distributed coordination via etcd.

Updated Dec 6, 2025:
- Geometrically correct consensus algorithms (Fréchet mean, weighted voting)
- Consensus quality metrics with entropy tracking
- E8-aware federated aggregation

Updated Dec 16, 2025:
- Added distributed_lock module (migration from deprecated swarm.distributed_locks)

Updated Jan 4, 2026:
- Added PBFT (Practical Byzantine Fault Tolerance) implementation
- Byzantine-tolerant consensus for critical state changes
- 3f+1 cluster configuration for f Byzantine nodes
- Critical PBFT coordinator for safety/security operations

See docs/INDEX.md for documentation.
"""

from __future__ import annotations

from typing import Any

from kagami.core.consensus.etcd_client import (
    acquire_leader,
    close_etcd_client,
    etcd_operation,
    get_etcd_client,
    get_state,
    publish_state,
    watch_key,
)

# Import exception classes from central hierarchy
from kagami.core.exceptions import (
    EtcdConnectionError,
    EtcdError,
    EtcdLeaderError,
    EtcdQuorumError,
)

# Alias for backward compatibility
EtcdClientError = EtcdError


def get_homeostasis_sync() -> Any:  # pragma: no cover
    """Get homeostasis sync singleton (lazy import)."""
    import importlib

    mod = importlib.import_module("kagami.core.consensus.homeostasis_sync")
    fn = getattr(mod, "get_homeostasis_sync", None)
    return fn() if callable(fn) else None


__all__ = [
    # Auto Recovery (Jan 4, 2026 — 125%)
    "AutoRecoveryManager",
    # Consensus types (Dec 6, 2025)
    "ConsensusQuality",
    # PBFT Byzantine consensus (Jan 4, 2026)
    "ConsensusRequest",
    "ConsensusResult",
    "ConsensusStrength",
    # Critical PBFT for safety/security operations (Jan 4, 2026)
    "CriticalOperation",
    "CriticalPBFTCoordinator",
    "CriticalPBFTResult",
    "CriticalityLevel",
    "DistributedLock",
    "EtcdClientError",  # Backward compatibility alias
    "EtcdConnectionError",
    # Errors
    "EtcdError",
    "EtcdLeaderError",
    "EtcdQuorumError",
    "FaultRecord",
    "FaultSeverity",
    "GlobalHomeostasisState",
    "HomeostasisAdjustments",
    "InstanceState",
    "LocalTransport",
    # Mesh-Homeostasis Bridge (Jan 4, 2026)
    "MeshBridgeConfig",
    "MeshHomeostasisBridge",
    "MessageType",
    "NodeRecoveryState",
    "PBFTConfig",
    "PBFTMessage",
    "PBFTNode",
    "PBFTPhase",
    "RecoveryAction",
    "RecoveryConfig",
    "RedisTransport",
    "acquire_leader",
    "close_etcd_client",
    # Distributed locking (Dec 16, 2025)
    "distributed_lock",
    "etcd_operation",
    "get_critical_pbft_coordinator",
    # etcd client
    "get_etcd_client",
    # Homeostasis sync
    "get_homeostasis_sync",
    "get_mesh_homeostasis_bridge",
    "get_pbft_node",
    "get_recovery_manager",
    "get_state",
    "is_critical_operation",
    "publish_state",
    "require_pbft_for_critical",
    "shutdown_mesh_homeostasis_bridge",
    "shutdown_pbft",
    "shutdown_recovery_manager",
    "watch_key",
]


def __getattr__(name: str) -> Any:  # pragma: no cover
    """Lazy-resolve homeostasis types and distributed lock to avoid import cycles."""
    if name in {
        "ConsensusQuality",
        "ConsensusStrength",
        "GlobalHomeostasisState",
        "HomeostasisAdjustments",
        "InstanceState",
    }:
        import importlib

        mod = importlib.import_module("kagami.core.consensus.homeostasis_sync")
        return getattr(mod, name)

    # Lazy import for distributed lock (Dec 16, 2025)
    if name in {"distributed_lock", "DistributedLock"}:
        import importlib

        mod = importlib.import_module("kagami.core.consensus.distributed_lock")
        return getattr(mod, name)

    # Lazy import for PBFT Byzantine consensus (Jan 4, 2026)
    if name in {
        "ConsensusRequest",
        "ConsensusResult",
        "LocalTransport",
        "MessageType",
        "PBFTConfig",
        "PBFTMessage",
        "PBFTNode",
        "PBFTPhase",
        "RedisTransport",
        "get_pbft_node",
        "shutdown_pbft",
    }:
        import importlib

        mod = importlib.import_module("kagami.core.consensus.critical_pbft")
        return getattr(mod, name)

    # Lazy import for Critical PBFT coordinator (Jan 4, 2026)
    if name in {
        "CriticalOperation",
        "CriticalityLevel",
        "CriticalPBFTCoordinator",
        "CriticalPBFTResult",
        "get_critical_pbft_coordinator",
        "is_critical_operation",
        "require_pbft_for_critical",
    }:
        import importlib

        mod = importlib.import_module("kagami.core.consensus.critical_pbft")
        return getattr(mod, name)

    # Lazy import for Mesh-Homeostasis Bridge (Jan 4, 2026)
    if name in {
        "MeshBridgeConfig",
        "MeshHomeostasisBridge",
        "get_mesh_homeostasis_bridge",
        "shutdown_mesh_homeostasis_bridge",
    }:
        import importlib

        mod = importlib.import_module("kagami.core.consensus.mesh_homeostasis_bridge")
        return getattr(mod, name)

    # Lazy import for Auto Recovery (Jan 4, 2026 — 125%)
    if name in {
        "AutoRecoveryManager",
        "FaultRecord",
        "FaultSeverity",
        "NodeRecoveryState",
        "RecoveryAction",
        "RecoveryConfig",
        "get_recovery_manager",
        "shutdown_recovery_manager",
    }:
        import importlib

        mod = importlib.import_module("kagami.core.consensus.auto_recovery")
        return getattr(mod, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
