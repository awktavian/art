"""Unified Cluster Management for Kagami.

All clustering coordinated through UnifiedClusterManager:
- etcd: Consensus, leader election, distributed locks
- Redis: Caching, job queues, pub/sub, sessions
- CockroachDB: Distributed SQL persistence

Sub-systems powered by unified cluster:
- Training: Federated learning, gradient aggregation, checkpoints
- Rendering: Distributed VFX rendering across cluster
- Coordination: State sync, receipts, homeostasis
- Service Registry: Byzantine-aware service discovery

Usage:
    from kagami.core.cluster import get_cluster_manager

    cluster = await get_cluster_manager()
    await cluster.wait_healthy()

    # Access services
    redis = cluster.redis
    database = cluster.database

    # Cluster operations
    await cluster.acquire_lock("resource")

Service Registry Usage:
    from kagami.core.cluster import get_service_registry, ServiceType

    registry = await get_service_registry()
    await registry.register(
        service_type=ServiceType.HUB,
        node_id="hub-kitchen",
        address="192.168.1.50",
        port=8080,
    )
    hubs = await registry.discover(ServiceType.HUB)

Training Usage:
    from kagami.core.cluster import get_training_cluster

    training = await get_training_cluster()
    await training.submit_gradients(model_id, gradients)
    aggregated = await training.aggregate_gradients(model_id)
"""

# Failover (Jan 4, 2026)
from kagami.core.cluster.failover import (
    FailoverConfig,
    FailoverEvent,
    FailoverManager,
    FailoverState,
    HealthCheckResult,
    LocationHealth,
    NodeHealth,
    get_failover_manager,
    shutdown_failover_manager,
)

# Graceful Shutdown (Jan 4, 2026 — 125%)
from kagami.core.cluster.graceful_shutdown import (
    GracefulShutdownCoordinator,
    ShutdownConfig,
    ShutdownPhase,
    ShutdownReason,
    ShutdownState,
    get_shutdown_coordinator,
)

# Secure Bootstrap (Jan 4, 2026)
from kagami.core.cluster.secure_bootstrap import (
    BootstrapRequest,
    BootstrapResult,
    BootstrapState,
    SecureBootstrapCoordinator,
    get_bootstrap_coordinator,
    shutdown_bootstrap_coordinator,
)
from kagami.core.cluster.service_registry import (
    ServiceEvent,
    ServiceEventData,
    ServiceInstance,
    ServiceRegistry,
    ServiceType,
    get_service_registry,
    get_service_registry_sync,
)
from kagami.core.cluster.service_registry import (
    ServiceHealth as ServiceRegistryHealth,
)
from kagami.core.cluster.training import (
    AggregationAlgorithm,
    GradientUpdate,
    TrainingCluster,
    TrainingRole,
    TrainingWorker,
    get_training_cluster,
    project_to_e8,
    shutdown_training_cluster,
)
from kagami.core.cluster.unified_cluster import (
    ClusterConfig,
    ClusterNode,
    ClusterRole,
    DatabaseService,
    EtcdService,
    RedisService,
    ServiceHealth,
    UnifiedClusterManager,
    get_cluster_manager,
    shutdown_cluster,
)

__all__ = [
    # Unified Cluster
    "AggregationAlgorithm",
    "BootstrapRequest",
    "BootstrapResult",
    # Secure Bootstrap (Jan 4, 2026)
    "BootstrapState",
    "ClusterConfig",
    "ClusterNode",
    "ClusterRole",
    "DatabaseService",
    "EtcdService",
    "FailoverConfig",
    "FailoverEvent",
    "FailoverManager",
    # Failover (Jan 4, 2026)
    "FailoverState",
    # Graceful Shutdown (Jan 4, 2026 — 125%)
    "GracefulShutdownCoordinator",
    "GradientUpdate",
    "HealthCheckResult",
    "LocationHealth",
    "NodeHealth",
    "RedisService",
    "SecureBootstrapCoordinator",
    "ServiceEvent",
    "ServiceEventData",
    "ServiceHealth",
    "ServiceInstance",
    "ServiceRegistry",
    "ServiceRegistryHealth",
    # Service Registry
    "ServiceType",
    "ShutdownConfig",
    "ShutdownPhase",
    "ShutdownReason",
    "ShutdownState",
    "TrainingCluster",
    "TrainingRole",
    "TrainingWorker",
    "UnifiedClusterManager",
    "get_bootstrap_coordinator",
    "get_cluster_manager",
    "get_failover_manager",
    "get_service_registry",
    "get_service_registry_sync",
    "get_shutdown_coordinator",
    "get_training_cluster",
    "project_to_e8",
    "shutdown_bootstrap_coordinator",
    "shutdown_cluster",
    "shutdown_failover_manager",
    "shutdown_training_cluster",
]
