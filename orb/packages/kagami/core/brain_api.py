from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from kagami.core.async_utils import safe_create_task

logger = logging.getLogger(__name__)


@dataclass
class BrainQuery:
    """A single query to the brain from an agent."""

    agent_id: str
    query_embedding: torch.Tensor
    context: dict[str, Any] = field(default_factory=dict[str, Any])
    priority: float = 1.0
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""


@dataclass
class BrainResponse:
    """Response from brain to agent."""

    agent_id: str
    activations: dict[int, torch.Tensor]
    final_output: torch.Tensor
    processing_time: float
    batch_size: int
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


class BrainAPI:
    """Unified API for fractal agents to query Matryoshka brain.

    Features:
    - Automatic batching (collects queries, processes together)
    - Async interface (agents don't block)
    - Thread-safe (multiple agents can query concurrently)
    - 7-layer activations (full brain state)
    - Metrics and monitoring

    Usage:
        brain = get_brain_api()
        response = await brain.query(agent_id, embedding, context)
        # response.activations contains all 7 layers
        # response.final_output is 2048D reasoning result
    """

    def __init__(
        self,
        max_batch_size: int = 8,
        batch_timeout_ms: float = 10.0,
        enable_parallel_layers: bool = True,
    ) -> None:
        """Initialize brain API.

        Args:
            max_batch_size: Maximum queries to batch together (default 8)
            batch_timeout_ms: Max time to wait for batch to fill (default 10ms)
            enable_parallel_layers: Enable 7-way parallel execution (default True)
        """
        self.max_batch_size = max_batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.enable_parallel_layers = enable_parallel_layers
        self._query_queue: deque[tuple[BrainQuery, asyncio.Future]] = deque()
        self._processing_lock = asyncio.Lock()
        self._batch_processor_task: asyncio.Task | None = None
        self._brain: Any | None = None
        self._total_queries = 0
        self._total_batches = 0
        self._total_processing_time = 0.0
        self._batch_sizes: list[int] = []
        self._running = False

    async def start(self) -> None:
        """Start the brain API and background batch processor."""
        if self._running:
            return
        self._running = True

        # Use async brain loading for better lazy loading support
        self._brain = await self._load_brain_async()

        # Brain must be available - no degraded mode
        if self._brain is None:
            raise RuntimeError(
                "BrainAPI requires world model. "
                "Ensure world model is initialized before starting BrainAPI."
            )

        self._batch_processor_task = safe_create_task(
            self._batch_processor(), name="_batch_processor"
        )
        logger.info(
            f"🧠 BrainAPI started: batch_size={self.max_batch_size}, timeout={self.batch_timeout_ms}ms, parallel={self.enable_parallel_layers}"
        )

    async def stop(self) -> None:
        """Stop the brain API and wait for pending queries."""
        self._running = False
        if self._batch_processor_task:
            await self._batch_processor_task
        logger.info("🧠 BrainAPI stopped")

    async def _load_brain_async(self) -> Any:
        """Load world model brain instance with async initialization.

        FIXED (Dec 29, 2025): Use get_model_async() to avoid blocking event loop.
        The previous implementation used the sync .model property which could
        deadlock when called from async context.
        """
        from kagami.core.world_model import get_world_model_service

        try:
            service = get_world_model_service()
            # Use async method to avoid blocking event loop
            brain = await service.get_model_async()

            if brain is not None:
                # KagamiWorldModel handles parallelism internally via hourglass architecture
                num_layers = len(brain.config.layer_dimensions)
                logger.info(
                    f"✅ Loaded KagamiWorldModel: {num_layers} encoder + {num_layers} decoder layers "
                    f"(hourglass architecture, E8+S⁷+H¹⁴)"
                )
                return brain

            # Model initialization returned None - fail fast
            raise RuntimeError(
                "World model not available. Ensure model is loaded before initializing BrainAPI."
            )

        except Exception as e:
            raise RuntimeError(
                f"World model initialization failed: {e}. Cannot operate BrainAPI without brain."
            ) from e

    def _load_brain(self) -> Any:
        """Load world model brain instance (KagamiWorldModel by default).

        Note: This is the sync version used during initialization.
        Prefer _load_brain_async for async contexts.
        """
        try:
            from kagami.core.world_model import get_world_model_service

            brain = get_world_model_service().model
            if brain is None:
                raise RuntimeError(
                    "World model not ready during sync load. "
                    "Use async initialization via start() instead."
                )
            # KagamiWorldModel handles parallelism internally via hourglass architecture
            num_layers = len(brain.config.layer_dimensions)
            logger.info(
                f"✅ Loaded KagamiWorldModel: {num_layers} encoder + {num_layers} decoder layers "
                f"(hourglass architecture, E8+S⁷+H¹⁴)"
            )
            return brain
        except Exception as e:
            raise RuntimeError(f"Failed to load brain: {e}") from e

    def encode(self, text: str) -> torch.Tensor:
        """Encode text into a deterministic 32D embedding.

        This is intentionally lightweight so Brain-guided utilities can run
        without requiring external embedding services.
        """
        digest = hashlib.blake2b(text.encode("utf-8"), digest_size=64).digest()
        vals = [
            (int.from_bytes(digest[i * 2 : (i + 1) * 2], "little") / 32767.5) - 1.0
            for i in range(32)
        ]
        emb = torch.tensor(vals, dtype=torch.float32)
        return F.normalize(emb, dim=0)

    async def query(
        self,
        agent_id: str,
        query_embedding: torch.Tensor | np.ndarray[Any, Any],
        context: dict[str, Any] | None = None,
        priority: float = 1.0,
        correlation_id: str = "",
        model_override: Any | None = None,
    ) -> BrainResponse:
        """Query the brain (async, batched automatically).

        Args:
            agent_id: ID of requesting agent
            query_embedding: Semantic embedding to process (will be adapted to 32D)
            context: Optional context for query
            priority: Query priority (higher processed first)
            correlation_id: Correlation ID for tracing
            model_override: Optional specific model to use (bypasses batching)

        Returns:
            BrainResponse with 7-layer activations and final output
        """
        if not self._running:
            await self.start()

        # Brain must be available - no degraded mode
        if self._brain is None and model_override is None:
            raise RuntimeError(
                f"BrainAPI query failed: brain not available for agent {agent_id}. "
                "Initialize brain before querying."
            )

        if isinstance(query_embedding, np.ndarray[Any, Any]):
            query_embedding = torch.from_numpy(query_embedding).float()

        # Handle model override (bypass batching for MAML adapted models)
        if model_override is not None:
            return await self._process_single_query(
                BrainQuery(
                    agent_id=agent_id,
                    query_embedding=query_embedding,
                    context=context or {},
                    priority=priority,
                    correlation_id=correlation_id,
                ),
                model_override,
            )

        query = BrainQuery(
            agent_id=agent_id,
            query_embedding=query_embedding,
            context=context or {},
            priority=priority,
            correlation_id=correlation_id,
        )
        future: asyncio.Future[BrainResponse] = asyncio.Future()
        self._query_queue.append((query, future))
        self._total_queries += 1
        return await future

    async def _process_single_query(self, query: BrainQuery, model: Any) -> BrainResponse:
        """Process a single query using a specific model (bypass batching)."""
        start_time = time.perf_counter()
        try:
            embedding = query.query_embedding.unsqueeze(0)  # [1, D]
            if embedding.dim() == 2:
                embedding = embedding.unsqueeze(1)  # [1, 1, D]

            output, brain_info = model.forward(embedding, return_all_layers=True)

            activations = {}
            final_output = None

            if isinstance(output, dict):
                # OptimizedWorldModel format
                for layer_idx, dim in enumerate(model.dimensions):
                    key = f"layer_{layer_idx}"
                    if key in output:
                        activations[dim] = output[key][0]
                        final_output = output[key][0]
            elif "layer_states" in brain_info:
                # Legacy format
                for layer_idx, layer_state in enumerate(brain_info["layer_states"]):
                    dim = model.dimensions[layer_idx]
                    activations[dim] = layer_state[0]
                final_output = output[0] if output.dim() > 1 else output

            # Fallback
            if final_output is None:
                final_output = (
                    list(activations.values())[-1]
                    if activations
                    else torch.zeros(model.dimensions[-1])
                )

            return BrainResponse(
                agent_id=query.agent_id,
                activations=activations,
                final_output=final_output,
                processing_time=time.perf_counter() - start_time,
                batch_size=1,
                metadata={
                    "brain_info": brain_info,
                    "correlation_id": query.correlation_id,
                    "mode": "override",
                },
            )
        except Exception as e:
            logger.error(f"Single query processing failed: {e}", exc_info=True)
            raise

    async def _batch_processor(self) -> None:
        """Background task that processes queries in batches with adaptive timeout.

        OPTIMIZATION: Adaptive timeout based on queue size:
        - Queue empty: 10ms (default)
        - Queue < 3: 1ms (low latency for single agents)
        - Queue >= max_batch_size: 0ms (process immediately)
        - Otherwise: scale linearly between 1-10ms
        """
        while self._running:
            try:
                queue_size = len(self._query_queue)
                if queue_size == 0:
                    adaptive_timeout = self.batch_timeout_ms
                elif queue_size >= self.max_batch_size:
                    adaptive_timeout = 0.0
                elif queue_size < 3:
                    adaptive_timeout = 1.0
                else:
                    fill_ratio = queue_size / self.max_batch_size
                    adaptive_timeout = 1.0 + (self.batch_timeout_ms - 1.0) * fill_ratio
                if adaptive_timeout > 0:
                    await asyncio.sleep(adaptive_timeout / 1000.0)
                if not self._query_queue:
                    continue
                batch: list[tuple[BrainQuery, asyncio.Future]] = []
                async with self._processing_lock:
                    while len(batch) < self.max_batch_size and self._query_queue:
                        batch.append(self._query_queue.popleft())
                if not batch:
                    continue
                await self._process_batch(batch)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch processor error: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _process_batch(self, batch: list[tuple[BrainQuery, asyncio.Future]]) -> None:
        """Process a batch of queries through the brain.

        Args:
            batch: List of (query, future) tuples
        """
        start_time = time.perf_counter()
        try:
            queries = [q for q, _ in batch]
            [f for _, f in batch]
            embeddings = torch.stack([q.query_embedding for q in queries])
            if embeddings.dim() == 2:
                embeddings = embeddings.unsqueeze(1)
            output, brain_info = self._brain.forward(embeddings, return_all_layers=True)  # type: ignore[union-attr]
            for i, (query, future) in enumerate(batch):
                if future.done():
                    continue
                activations = {}
                final_output = None

                if isinstance(output, dict):
                    # OptimizedWorldModel format
                    for layer_idx, dim in enumerate(self._brain.dimensions):  # type: ignore[union-attr]
                        key = f"layer_{layer_idx}"
                        if key in output:
                            activations[dim] = output[key][i]
                            final_output = output[key][i]  # Update to last layer
                elif "layer_states" in brain_info:
                    # Legacy format
                    for layer_idx, layer_state in enumerate(brain_info["layer_states"]):
                        dim = self._brain.dimensions[layer_idx]  # type: ignore[union-attr]
                        activations[dim] = layer_state[i]
                    final_output = output[i] if output.dim() > 1 else output

                # Fallback for final output
                if final_output is None:
                    # Should not happen if brain works, but safe fallback
                    final_output = (
                        list(activations.values())[-1]
                        if activations
                        else torch.zeros(self._brain.dimensions[-1])  # type: ignore[union-attr]
                    )

                response = BrainResponse(
                    agent_id=query.agent_id,
                    activations=activations,
                    final_output=final_output,
                    processing_time=time.perf_counter() - start_time,
                    batch_size=len(batch),
                    metadata={"brain_info": brain_info, "correlation_id": query.correlation_id},
                )
                try:
                    if query.correlation_id:
                        from kagami.core.debugging.unified_debugging_system import (
                            get_unified_debugging_system,
                        )

                        debug_sys = get_unified_debugging_system()
                        debug_sys.capture_brain_activations(
                            correlation_id=query.correlation_id, activations=activations
                        )
                except Exception:
                    pass
                future.set_result(response)
            self._total_batches += 1
            self._batch_sizes.append(len(batch))
            processing_time = time.perf_counter() - start_time
            self._total_processing_time += processing_time
            try:
                from kagami_observability.metrics import (
                    BRAIN_BATCH_SIZE,
                    BRAIN_PROCESSING_TIME_SECONDS,
                )

                BRAIN_BATCH_SIZE.observe(len(batch))
                BRAIN_PROCESSING_TIME_SECONDS.observe(processing_time)
            except Exception:
                pass
            logger.debug(
                f"🧠 Processed batch: {len(batch)} queries, {processing_time * 1000:.1f}ms, avg {processing_time / len(batch) * 1000:.1f}ms/query"
            )
        except Exception as e:
            for _, future in batch:
                if not future.done():
                    future.set_exception(e)
            logger.error(f"Batch processing failed: {e}", exc_info=True)

    def get_stats(self) -> dict[str, Any]:
        """Get brain API statistics.

        Returns:
            Statistics dict[str, Any] with query counts, batch sizes, timing info
        """
        avg_batch_size = np.mean(self._batch_sizes) if self._batch_sizes else 0.0
        avg_processing_time = (
            self._total_processing_time / self._total_batches if self._total_batches > 0 else 0.0
        )
        return {
            "total_queries": self._total_queries,
            "total_batches": self._total_batches,
            "avg_batch_size": avg_batch_size,
            "avg_processing_time_ms": avg_processing_time * 1000,
            "queue_size": len(self._query_queue),
            "throughput_queries_per_sec": (
                self._total_queries / self._total_processing_time
                if self._total_processing_time > 0
                else 0.0
            ),
        }


_brain_api: BrainAPI | None = None


def get_brain_api(
    max_batch_size: int = 8, batch_timeout_ms: float = 10.0, enable_parallel_layers: bool = True
) -> BrainAPI:
    """Get singleton BrainAPI instance.

    Args:
        max_batch_size: Maximum queries per batch
        batch_timeout_ms: Batch timeout in milliseconds
        enable_parallel_layers: Enable parallel layer execution

    Returns:
        Singleton BrainAPI instance
    """
    global _brain_api
    if _brain_api is None:
        _brain_api = BrainAPI(
            max_batch_size=max_batch_size,
            batch_timeout_ms=batch_timeout_ms,
            enable_parallel_layers=enable_parallel_layers,
        )
    return _brain_api
