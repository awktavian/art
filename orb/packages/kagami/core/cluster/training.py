"""Distributed Training via Unified Cluster Manager.

All distributed training coordination goes through UnifiedClusterManager:
- Leader election for training coordinator
- Gradient aggregation via Redis
- Checkpoint synchronization via distributed storage
- Model weight broadcasting via etcd

This module provides the training-specific cluster functionality while
using the unified infrastructure for all underlying operations.

Usage:
    from kagami.core.cluster.training import get_training_cluster

    cluster = await get_training_cluster()

    # Federated aggregation
    await cluster.submit_gradients(model_id, gradients)
    aggregated = await cluster.aggregate_gradients(model_id)

    # Checkpoint management
    await cluster.save_checkpoint(model_id, state_dict)
    state_dict = await cluster.load_checkpoint(model_id)

    # Distributed training coordination
    async with cluster.training_lock(model_id):
        # Exclusive access for training operations
        pass
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# TRAINING CLUSTER TYPES
# =============================================================================


class TrainingRole(str, Enum):
    """Role in distributed training."""

    COORDINATOR = "coordinator"  # Aggregates gradients, manages checkpoints
    WORKER = "worker"  # Computes gradients, receives updates
    OBSERVER = "observer"  # Read-only monitoring


class AggregationAlgorithm(str, Enum):
    """Federated aggregation algorithms."""

    FEDAVG = "fedavg"  # Simple averaging
    FEDPROX = "fedprox"  # Proximal regularization
    FEDADAM = "fedadam"  # Adaptive learning rates
    E8_AWARE = "e8_aware"  # Project to E8 lattice


@dataclass
class TrainingWorker:
    """Information about a training worker."""

    worker_id: str
    hostname: str
    role: TrainingRole = TrainingRole.WORKER
    model_ids: list[str] = field(default_factory=list)
    gpu_available: bool = False
    last_heartbeat: float = 0.0
    gradients_submitted: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "role": self.role.value,
            "model_ids": self.model_ids,
            "gpu_available": self.gpu_available,
            "last_heartbeat": self.last_heartbeat,
            "gradients_submitted": self.gradients_submitted,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingWorker:
        """Deserialize from dictionary."""
        return cls(
            worker_id=data["worker_id"],
            hostname=data["hostname"],
            role=TrainingRole(data.get("role", "worker")),
            model_ids=data.get("model_ids", []),
            gpu_available=data.get("gpu_available", False),
            last_heartbeat=data.get("last_heartbeat", 0.0),
            gradients_submitted=data.get("gradients_submitted", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class GradientUpdate:
    """Gradient update from a worker."""

    worker_id: str
    model_id: str
    gradients: dict[str, np.ndarray]
    num_samples: int
    timestamp: float = 0.0
    dp_epsilon: float | None = None  # Differential privacy epsilon
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# E8 LATTICE PROJECTION FOR FEDERATED AGGREGATION
# =============================================================================


def _generate_e8_roots() -> np.ndarray:
    """Generate all 240 E8 lattice roots."""
    from itertools import combinations, product

    roots = []

    # Type 1: Two ±1s, rest zeros
    for positions in combinations(range(8), 2):
        for signs in product([1.0, -1.0], repeat=2):
            root = np.zeros(8)
            root[positions[0]] = signs[0]
            root[positions[1]] = signs[1]
            roots.append(root)

    # Type 2: All ±½ with even number of negatives
    for signs in product([1, -1], repeat=8):
        if sum(1 for s in signs if s == -1) % 2 == 0:
            root = np.array([s * 0.5 for s in signs], dtype=np.float64)
            roots.append(root)

    return np.stack(roots)


_E8_ROOTS: np.ndarray | None = None


def project_to_e8(weights: np.ndarray, temperature: float = 0.1) -> np.ndarray:
    """Project weights to nearest E8 lattice point."""
    global _E8_ROOTS
    if _E8_ROOTS is None:
        _E8_ROOTS = _generate_e8_roots()

    if weights.shape[-1] != 8:
        return weights

    original_shape = weights.shape
    flat = weights.reshape(-1, 8)

    # Compute distances to all roots
    distances = np.sum((flat[:, None, :] - _E8_ROOTS[None, :, :]) ** 2, axis=-1)

    if temperature <= 0:
        indices = np.argmin(distances, axis=-1)
        projected = _E8_ROOTS[indices]
    else:
        weights_soft = np.exp(-distances / temperature)
        weights_soft = weights_soft / weights_soft.sum(axis=-1, keepdims=True)
        projected = weights_soft @ _E8_ROOTS

    return projected.reshape(original_shape)


# =============================================================================
# TRAINING CLUSTER
# =============================================================================


class TrainingCluster:
    """Distributed training cluster using UnifiedClusterManager.

    Provides:
    - Federated gradient aggregation (FedAvg, FedProx, E8-aware)
    - Distributed checkpoint management
    - Training coordination (locks, leader election)
    - Worker discovery and health monitoring

    All underlying operations use UnifiedClusterManager for:
    - etcd: Coordination, leader election, locks
    - Redis: Gradient queues, caching, pub/sub
    - Database: Checkpoint metadata persistence
    """

    def __init__(self):
        self._cluster = None
        self._worker: TrainingWorker | None = None
        self._is_coordinator = False
        self._started = False

        # Background tasks
        self._heartbeat_task: asyncio.Task | None = None
        self._aggregation_task: asyncio.Task | None = None

        # Aggregation settings
        self.aggregation_algorithm = AggregationAlgorithm.FEDAVG
        self.aggregation_interval = 60.0  # seconds
        self.e8_projection_temperature = 0.1
        self.min_workers_for_aggregation = 2

    async def start(self) -> None:
        """Start the training cluster."""
        if self._started:
            return

        # Get unified cluster manager
        from kagami.core.cluster import get_cluster_manager

        self._cluster = await get_cluster_manager()
        await self._cluster.wait_healthy(timeout=30.0)

        # Register as training worker
        self._worker = TrainingWorker(
            worker_id=self._cluster.node_id,
            hostname=self._cluster.config.node_id.split("-")[0],
            gpu_available=self._check_gpu(),
            last_heartbeat=time.time(),
        )

        # Attempt to become coordinator
        await self._elect_coordinator()

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        if self._is_coordinator:
            self._aggregation_task = asyncio.create_task(self._aggregation_loop())

        self._started = True
        role = "COORDINATOR" if self._is_coordinator else "WORKER"
        logger.info(f"✅ Training cluster started ({role})")

    async def stop(self) -> None:
        """Stop the training cluster."""
        if not self._started:
            return

        # Cancel background tasks in parallel
        tasks_to_cancel = [t for t in [self._heartbeat_task, self._aggregation_task] if t]
        for task in tasks_to_cancel:
            task.cancel()
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        # Unregister worker
        await self._unregister_worker()

        self._started = False
        logger.info("✅ Training cluster stopped")

    def _check_gpu(self) -> bool:
        """Check if GPU is available."""
        try:
            import torch

            return torch.cuda.is_available() or (
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            )
        except ImportError:
            return False

    async def _elect_coordinator(self) -> None:
        """Attempt to become training coordinator."""
        if not self._cluster or not self._cluster.etcd.healthy:
            self._is_coordinator = False
            return

        success, _ = await self._cluster.etcd.acquire_leader(
            "training-coordinator",
            ttl=60,
        )

        self._is_coordinator = success
        if self._worker:
            self._worker.role = TrainingRole.COORDINATOR if success else TrainingRole.WORKER

        if success:
            logger.info("🎖️ This node is training coordinator")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat."""
        while True:
            try:
                await self._register_worker()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Training heartbeat error: {e}")
                await asyncio.sleep(5)

    async def _register_worker(self) -> None:
        """Register this worker in cluster."""
        if not self._worker or not self._cluster:
            return

        self._worker.last_heartbeat = time.time()

        if self._cluster.redis.healthy:
            key = f"kagami:training:worker:{self._worker.worker_id}"
            await self._cluster.redis.client.setex(
                key,
                120,  # 2 minute TTL
                json.dumps(self._worker.to_dict()),
            )

    async def _unregister_worker(self) -> None:
        """Unregister this worker."""
        if not self._worker or not self._cluster:
            return

        if self._cluster.redis.healthy:
            key = f"kagami:training:worker:{self._worker.worker_id}"
            await self._cluster.redis.client.delete(key)

    async def _aggregation_loop(self) -> None:
        """Coordinator: periodically aggregate gradients."""
        while True:
            try:
                await asyncio.sleep(self.aggregation_interval)
                await self._run_aggregation_round()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Aggregation error: {e}")

    async def _run_aggregation_round(self) -> None:
        """Run one round of gradient aggregation."""
        if not self._cluster or not self._cluster.redis.healthy:
            return

        # Get all model IDs with pending gradients
        pattern = "kagami:training:gradients:*"
        cursor = 0
        model_ids = set()

        while True:
            cursor, keys = await self._cluster.redis.client.scan(cursor, match=pattern, count=100)
            for key in keys:
                # Extract model_id from key
                parts = key.decode().split(":")
                if len(parts) >= 4:
                    model_ids.add(parts[3])
            if cursor == 0:
                break

        # Aggregate each model
        for model_id in model_ids:
            try:
                aggregated = await self.aggregate_gradients(model_id)
                if aggregated:
                    logger.info(f"Aggregated gradients for model {model_id}")
            except Exception as e:
                logger.error(f"Failed to aggregate {model_id}: {e}")

    # =========================================================================
    # PUBLIC API: Gradient Aggregation
    # =========================================================================

    async def submit_gradients(
        self,
        model_id: str,
        gradients: dict[str, np.ndarray],
        num_samples: int,
        dp_epsilon: float | None = None,
    ) -> bool:
        """Submit gradients for federated aggregation.

        Args:
            model_id: Model identifier
            gradients: Dict mapping layer names to gradient arrays
            num_samples: Number of samples used to compute gradients
            dp_epsilon: Differential privacy epsilon (None = no DP)

        Returns:
            True if submitted successfully
        """
        if not self._cluster or not self._cluster.redis.healthy:
            logger.warning("Training cluster not ready for gradient submission")
            return False

        if not self._worker:
            return False

        update = GradientUpdate(
            worker_id=self._worker.worker_id,
            model_id=model_id,
            gradients=gradients,
            num_samples=num_samples,
            timestamp=time.time(),
            dp_epsilon=dp_epsilon,
        )

        # Serialize gradients
        serialized = {
            "worker_id": update.worker_id,
            "model_id": update.model_id,
            "num_samples": update.num_samples,
            "timestamp": update.timestamp,
            "dp_epsilon": update.dp_epsilon,
            "gradients": {k: v.tolist() for k, v in gradients.items()},
        }

        # Store in Redis with expiry
        key = f"kagami:training:gradients:{model_id}:{self._worker.worker_id}"
        await self._cluster.redis.client.setex(
            key,
            300,  # 5 minute TTL
            json.dumps(serialized),
        )

        self._worker.gradients_submitted += 1
        logger.debug(f"Submitted gradients for {model_id}")
        return True

    async def aggregate_gradients(
        self,
        model_id: str,
        algorithm: AggregationAlgorithm | None = None,
    ) -> dict[str, np.ndarray] | None:
        """Aggregate gradients from all workers.

        Args:
            model_id: Model to aggregate
            algorithm: Aggregation algorithm (defaults to self.aggregation_algorithm)

        Returns:
            Aggregated gradients, or None if not enough workers
        """
        if not self._cluster or not self._cluster.redis.healthy:
            return None

        algorithm = algorithm or self.aggregation_algorithm

        # Collect all gradient updates for this model
        pattern = f"kagami:training:gradients:{model_id}:*"
        cursor = 0
        updates: list[GradientUpdate] = []

        while True:
            cursor, keys = await self._cluster.redis.client.scan(cursor, match=pattern, count=100)

            for key in keys:
                data = await self._cluster.redis.client.get(key)
                if data:
                    try:
                        parsed = json.loads(data)
                        update = GradientUpdate(
                            worker_id=parsed["worker_id"],
                            model_id=parsed["model_id"],
                            gradients={k: np.array(v) for k, v in parsed["gradients"].items()},
                            num_samples=parsed["num_samples"],
                            timestamp=parsed["timestamp"],
                            dp_epsilon=parsed.get("dp_epsilon"),
                        )
                        updates.append(update)
                    except Exception as e:
                        logger.debug(f"Failed to parse gradient update: {e}")

            if cursor == 0:
                break

        if len(updates) < self.min_workers_for_aggregation:
            logger.debug(
                f"Not enough workers for aggregation: {len(updates)} < {self.min_workers_for_aggregation}"
            )
            return None

        # Aggregate based on algorithm
        if algorithm == AggregationAlgorithm.FEDAVG:
            aggregated = self._fedavg(updates)
        elif algorithm == AggregationAlgorithm.E8_AWARE:
            aggregated = self._fedavg_e8(updates)
        else:
            aggregated = self._fedavg(updates)

        # Clear processed gradients in parallel
        keys_to_delete = await self._cluster.redis.client.keys(pattern)
        if keys_to_delete:
            await asyncio.gather(
                *[self._cluster.redis.client.delete(key) for key in keys_to_delete],
                return_exceptions=True,
            )

        # Broadcast aggregated weights
        await self._broadcast_weights(model_id, aggregated)

        return aggregated

    def _fedavg(self, updates: list[GradientUpdate]) -> dict[str, np.ndarray]:
        """FedAvg: weighted averaging by sample count."""
        total_samples = sum(u.num_samples for u in updates)
        if total_samples == 0:
            return {}

        aggregated: dict[str, np.ndarray] = {}

        # Get all layer names
        all_layers = set()
        for u in updates:
            all_layers.update(u.gradients.keys())

        for layer in all_layers:
            weighted_sum = None
            for u in updates:
                if layer in u.gradients:
                    weight = u.num_samples / total_samples
                    if weighted_sum is None:
                        weighted_sum = u.gradients[layer] * weight
                    else:
                        weighted_sum += u.gradients[layer] * weight

            if weighted_sum is not None:
                aggregated[layer] = weighted_sum

        return aggregated

    def _fedavg_e8(self, updates: list[GradientUpdate]) -> dict[str, np.ndarray]:
        """E8-aware FedAvg: project to E8 lattice after averaging."""
        aggregated = self._fedavg(updates)

        # Project E8-related layers to lattice
        e8_prefixes = ("e8_", "quantizer.", "bottleneck.")
        for layer, grads in aggregated.items():
            if any(layer.startswith(p) for p in e8_prefixes):
                aggregated[layer] = project_to_e8(grads, self.e8_projection_temperature)

        return aggregated

    async def _broadcast_weights(self, model_id: str, weights: dict[str, np.ndarray]) -> None:
        """Broadcast aggregated weights to all workers."""
        if not self._cluster:
            return

        # Store in Redis for workers to pull
        serialized = {k: v.tolist() for k, v in weights.items()}
        key = f"kagami:training:weights:{model_id}"

        if self._cluster.redis.healthy:
            await self._cluster.redis.client.set(key, json.dumps(serialized))

        # Publish notification
        await self._cluster.publish(
            "training.weights_updated",
            {"model_id": model_id, "timestamp": time.time()},
        )

    async def get_aggregated_weights(self, model_id: str) -> dict[str, np.ndarray] | None:
        """Get latest aggregated weights for a model."""
        if not self._cluster or not self._cluster.redis.healthy:
            return None

        key = f"kagami:training:weights:{model_id}"
        data = await self._cluster.redis.client.get(key)

        if data:
            parsed = json.loads(data)
            return {k: np.array(v) for k, v in parsed.items()}

        return None

    # =========================================================================
    # PUBLIC API: Checkpoint Management
    # =========================================================================

    async def save_checkpoint(
        self,
        model_id: str,
        state_dict: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Save training checkpoint to distributed storage.

        Args:
            model_id: Model identifier
            state_dict: PyTorch state dict or similar
            metadata: Additional metadata

        Returns:
            Checkpoint ID, or None on failure
        """
        if not self._cluster:
            return None

        checkpoint_id = f"{model_id}-{int(time.time())}"

        try:
            from kagami.core.persistence.distributed_storage import get_distributed_storage

            storage = await get_distributed_storage()

            # Save state dict
            await storage.save(
                f"checkpoints/{model_id}/{checkpoint_id}",
                state_dict,
                metadata={
                    "model_id": model_id,
                    "checkpoint_id": checkpoint_id,
                    "timestamp": time.time(),
                    "worker_id": self._worker.worker_id if self._worker else "unknown",
                    **(metadata or {}),
                },
            )

            # Update latest pointer in Redis
            if self._cluster.redis.healthy:
                await self._cluster.redis.client.set(
                    f"kagami:training:checkpoint:latest:{model_id}",
                    checkpoint_id,
                )

            logger.info(f"Saved checkpoint {checkpoint_id}")
            return checkpoint_id

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return None

    async def load_checkpoint(
        self, model_id: str, checkpoint_id: str | None = None
    ) -> dict[str, Any] | None:
        """Load training checkpoint from distributed storage.

        Args:
            model_id: Model identifier
            checkpoint_id: Specific checkpoint, or None for latest

        Returns:
            State dict, or None if not found
        """
        if not self._cluster:
            return None

        try:
            # Get latest if not specified
            if checkpoint_id is None and self._cluster.redis.healthy:
                checkpoint_id = await self._cluster.redis.client.get(
                    f"kagami:training:checkpoint:latest:{model_id}"
                )
                if checkpoint_id:
                    checkpoint_id = checkpoint_id.decode()

            if not checkpoint_id:
                logger.warning(f"No checkpoint found for {model_id}")
                return None

            from kagami.core.persistence.distributed_storage import get_distributed_storage

            storage = await get_distributed_storage()
            state_dict = await storage.load(f"checkpoints/{model_id}/{checkpoint_id}")

            logger.info(f"Loaded checkpoint {checkpoint_id}")
            return state_dict

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    # =========================================================================
    # PUBLIC API: Training Coordination
    # =========================================================================

    async def training_lock(self, model_id: str, ttl: int = 300) -> Any:
        """Acquire distributed lock for training operations.

        Usage:
            async with await cluster.training_lock("my_model"):
                # Exclusive access
                pass
        """
        from kagami.core.consensus.distributed_lock import distributed_lock

        return distributed_lock(f"training:{model_id}", ttl=ttl)

    async def get_workers(self) -> list[TrainingWorker]:
        """Get all active training workers."""
        if not self._cluster or not self._cluster.redis.healthy:
            return []

        workers = []
        pattern = "kagami:training:worker:*"
        cursor = 0

        while True:
            cursor, keys = await self._cluster.redis.client.scan(cursor, match=pattern, count=100)

            for key in keys:
                data = await self._cluster.redis.client.get(key)
                if data:
                    try:
                        worker = TrainingWorker.from_dict(json.loads(data))
                        # Check freshness
                        if time.time() - worker.last_heartbeat < 120:
                            workers.append(worker)
                    except Exception:
                        pass

            if cursor == 0:
                break

        return workers

    @property
    def is_coordinator(self) -> bool:
        """Check if this node is training coordinator."""
        return self._is_coordinator

    @property
    def worker_id(self) -> str:
        """Get this worker's ID."""
        return self._worker.worker_id if self._worker else ""


# =============================================================================
# MODULE-LEVEL SINGLETON
# =============================================================================

_training_cluster: TrainingCluster | None = None


async def get_training_cluster() -> TrainingCluster:
    """Get or create the training cluster singleton."""
    global _training_cluster

    if _training_cluster is None:
        _training_cluster = TrainingCluster()
        await _training_cluster.start()

    return _training_cluster


async def shutdown_training_cluster() -> None:
    """Shutdown the training cluster."""
    global _training_cluster

    if _training_cluster:
        await _training_cluster.stop()
        _training_cluster = None


__all__ = [
    "AggregationAlgorithm",
    "GradientUpdate",
    "TrainingCluster",
    "TrainingRole",
    "TrainingWorker",
    "get_training_cluster",
    "project_to_e8",
    "shutdown_training_cluster",
]
