"""Consensus Performance Optimizations for KagamiOS.

TARGET LATENCY:
===============
- p50: <50ms consensus latency
- p99: <100ms consensus latency

OPTIMIZATION STRATEGIES:
========================
1. **Batched Consensus**: Batch multiple tasks into single consensus round
2. **Fano Affinity Grouping**: Group tasks by Fano line affinity
3. **Consensus Caching**: Cache consensus results for deterministic tasks
4. **Predictive Consensus**: Use world model to predict outcomes
5. **Parallel Proposal Collection**: Collect proposals with concurrency limits

ARCHITECTURE:
=============
┌────────────────────────────────────────────────────────────────┐
│                   CONSENSUS OPTIMIZATION LAYER                  │
│                                                                 │
│  BatchedConsensus ──────► Batching + timeout logic             │
│          ↓                                                      │
│  ConsensusCache ────────► LRU cache with TTL                   │
│          ↓                                                      │
│  PredictiveConsensus ───► World model prediction               │
│          ↓                                                      │
│  KagamiConsensus ───────► Byzantine consensus (fallback)       │
└────────────────────────────────────────────────────────────────┘

METRICS:
========
- consensus_cache_hits_total
- consensus_cache_misses_total
- consensus_predictions_total{used=true|false}
- consensus_batch_size (histogram)
- consensus_latency_seconds (histogram)
- consensus_optimization_speedup_ratio (histogram)

Created: December 15, 2025
"""

from __future__ import annotations

# Standard library imports
import asyncio
import hashlib
import logging
import time
from collections import (
    defaultdict,
    deque,
)
from collections.abc import (
    Awaitable,
    Callable,
)
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    TYPE_CHECKING,
    Any,
)

# Third-party imports
import numpy as np

# Local imports - use types module to avoid circular dependency
from kagami.core.coordination.types import (
    ColonyID,
    CoordinationProposal,
)
from kagami.core.services.llm import (
    TaskType,
    get_llm_service,
)

if TYPE_CHECKING:
    from kagami.core.coordination.kagami_consensus import (
        ConsensusState,
        KagamiConsensus,
    )

logger = logging.getLogger(__name__)

# Try to import metrics (optional)
try:
    from kagami_observability.metrics import Counter, Histogram

    METRICS_AVAILABLE = True
except ImportError:
    logger.warning("Metrics not available - consensus optimization telemetry disabled")
    METRICS_AVAILABLE = False

# =============================================================================
# METRICS
# =============================================================================

if METRICS_AVAILABLE:
    # Cache metrics
    CONSENSUS_CACHE_HITS = Counter(
        "consensus_cache_hits_total",
        "Total consensus cache hits",
    )
    CONSENSUS_CACHE_MISSES = Counter(
        "consensus_cache_misses_total",
        "Total consensus cache misses",
    )
    CONSENSUS_CACHE_EVICTIONS = Counter(
        "consensus_cache_evictions_total",
        "Total consensus cache evictions",
    )

    # Prediction metrics
    CONSENSUS_PREDICTIONS_TOTAL = Counter(
        "consensus_predictions_total",
        "Total consensus predictions",
        ["used"],  # used=true|false
    )
    CONSENSUS_PREDICTION_CONFIDENCE = Histogram(
        "consensus_prediction_confidence",
        "Prediction confidence scores",
    )

    # Batch metrics
    CONSENSUS_BATCH_SIZE = Histogram(
        "consensus_batch_size",
        "Number of tasks in consensus batch",
    )
    CONSENSUS_BATCH_TIMEOUT = Counter(
        "consensus_batch_timeout_total",
        "Batches triggered by timeout (vs size)",
    )

    # Latency metrics (separate per optimization type)
    CONSENSUS_LATENCY_CACHED = Histogram(
        "consensus_latency_cached_seconds",
        "Consensus latency (cached)",
    )
    CONSENSUS_LATENCY_PREDICTED = Histogram(
        "consensus_latency_predicted_seconds",
        "Consensus latency (predicted)",
    )
    CONSENSUS_LATENCY_BATCHED = Histogram(
        "consensus_latency_batched_seconds",
        "Consensus latency (batched)",
    )
    CONSENSUS_LATENCY_FULL = Histogram(
        "consensus_latency_full_seconds",
        "Consensus latency (full)",
    )
    CONSENSUS_OPTIMIZATION_SPEEDUP = Histogram(
        "consensus_optimization_speedup_ratio",
        "Speedup ratio: optimized_time / full_consensus_time",
    )

# =============================================================================
# FANO AFFINITY GROUPING
# =============================================================================

# Keyword-based Fano affinity heuristics (using colony indices to avoid circular import)
FANO_AFFINITY_KEYWORDS: dict[str, list[int]] = {
    # Creative → implementation → debugging (Spark × Forge = Flow)
    "creative_flow": [0, 1, 2],  # SPARK, FORGE, FLOW
    # Planning → implementation → verification (Beacon × Forge = Crystal)
    "plan_build": [4, 1, 6],  # BEACON, FORGE, CRYSTAL
    # Research → integration → verification (Spark × Grove = Crystal)
    "research_verify": [0, 5, 6],  # SPARK, GROVE, CRYSTAL
    # Integration → debugging → verification (Nexus × Flow = Crystal)
    "integrate_debug": [3, 2, 6],  # NEXUS, FLOW, CRYSTAL
    # Planning → debugging → research (Beacon × Flow = Grove)
    "plan_debug": [4, 2, 5],  # BEACON, FLOW, GROVE
}


def detect_task_affinity(task: str) -> str:
    """Detect Fano affinity group from task keywords.

    Priority order: most specific first.

    Args:
        task: Task description

    Returns:
        Affinity group name (default: "creative_flow")
    """
    task_lower = task.lower()

    # Plan-debug: diagnose, analyze architecture (most specific)
    if any(kw in task_lower for kw in ["diagnose", "analyze", "trace"]):
        return "plan_debug"

    # Plan-build: architecture, design with implementation
    # Check for both plan AND implementation keywords
    has_plan = any(kw in task_lower for kw in ["plan", "design", "architect", "architecture"])
    has_implement = any(kw in task_lower for kw in ["implement", "build"])
    if has_plan and has_implement:
        return "plan_build"

    # Research-verify: research, explore, validate
    if any(kw in task_lower for kw in ["research", "explore", "investigate", "validate", "prove"]):
        return "research_verify"

    # Integrate-debug: connect, integrate, fix, debug
    if any(kw in task_lower for kw in ["integrate", "connect", "combine", "debug", "fix"]):
        return "integrate_debug"

    # Creative flow: brainstorm, ideate, implement (default for generic build tasks)
    if any(
        kw in task_lower
        for kw in ["brainstorm", "ideate", "creative", "imagine", "build", "implement"]
    ):
        return "creative_flow"

    # Default: creative flow (most common)
    return "creative_flow"


def group_by_fano_affinity(
    tasks: list[str],
    batch_size: int,
) -> list[list[str]]:
    """Group tasks by Fano line affinity for efficient batching.

    Tasks on same Fano line likely benefit from shared consensus.

    Args:
        tasks: List of task descriptions
        batch_size: Maximum batch size

    Returns:
        List of batches (each batch = list[Any] of tasks)
    """
    # Group by affinity
    affinity_groups: dict[str, list[str]] = defaultdict(list[Any])

    for task in tasks:
        affinity = detect_task_affinity(task)
        affinity_groups[affinity].append(task)

    # Create batches respecting batch_size
    batches: list[list[str]] = []

    for _affinity, group_tasks in affinity_groups.items():
        # Split large groups into multiple batches
        for i in range(0, len(group_tasks), batch_size):
            batch = group_tasks[i : i + batch_size]
            batches.append(batch)

    return batches


# =============================================================================
# CONSENSUS CACHE
# =============================================================================


@dataclass
class CacheEntry:
    """Cached consensus result with metadata."""

    state: ConsensusState
    timestamp: float
    access_count: int = 0
    last_access: float = field(default_factory=time.time)


class ConsensusCache:
    """LRU cache for consensus results with TTL.

    Caches deterministic consensus outcomes to avoid redundant computation.
    """

    def __init__(
        self,
        ttl: int = 300,  # 5 minutes
        max_size: int = 1000,
    ):
        """Initialize consensus cache.

        Args:
            ttl: Time-to-live in seconds
            max_size: Maximum cache entries (LRU eviction)
        """
        self.ttl = ttl
        self.max_size = max_size
        self.cache: dict[str, CacheEntry] = {}
        self.access_order: deque[str] = deque()  # LRU tracking

        logger.info(f"Initialized ConsensusCache (ttl={ttl}s, max_size={max_size})")

    def _compute_task_hash(self, task: str, context: dict[str, Any] | None = None) -> str:
        """Compute deterministic hash for task + context.

        Args:
            task: Task description
            context: Optional context dict[str, Any]

        Returns:
            SHA256 hash (hex)
        """
        # Create deterministic string representation
        cache_key = f"{task}|{sorted((context or {}).items())}"
        return hashlib.sha256(cache_key.encode()).hexdigest()

    def get(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> ConsensusState | None:
        """Get cached consensus if available and fresh.

        Args:
            task: Task description
            context: Optional context

        Returns:
            Cached ConsensusState or None
        """
        task_hash = self._compute_task_hash(task, context)

        if task_hash not in self.cache:
            if METRICS_AVAILABLE:
                CONSENSUS_CACHE_MISSES.inc()
            return None

        entry = self.cache[task_hash]

        # Check TTL
        age = time.time() - entry.timestamp
        if age > self.ttl:
            # Stale entry, evict
            del self.cache[task_hash]
            if task_hash in self.access_order:
                self.access_order.remove(task_hash)

            if METRICS_AVAILABLE:
                CONSENSUS_CACHE_MISSES.inc()
            return None

        # Cache hit
        entry.access_count += 1
        entry.last_access = time.time()

        # Update LRU order
        if task_hash in self.access_order:
            self.access_order.remove(task_hash)
        self.access_order.append(task_hash)

        if METRICS_AVAILABLE:
            CONSENSUS_CACHE_HITS.inc()

        logger.debug(f"Cache hit for task: {task[:50]}... (age={age:.2f}s)")
        return entry.state

    def put(
        self,
        task: str,
        state: ConsensusState,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Store consensus result in cache.

        Args:
            task: Task description
            state: Consensus state to cache
            context: Optional context
        """
        task_hash = self._compute_task_hash(task, context)

        # Evict if at capacity
        if len(self.cache) >= self.max_size and task_hash not in self.cache:
            self._evict_lru()

        # Store entry
        self.cache[task_hash] = CacheEntry(
            state=state,
            timestamp=time.time(),
        )

        # Update LRU order
        if task_hash in self.access_order:
            self.access_order.remove(task_hash)
        self.access_order.append(task_hash)

        logger.debug(f"Cached consensus for task: {task[:50]}...")

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self.access_order:
            return

        # Remove oldest
        oldest_hash = self.access_order.popleft()
        if oldest_hash in self.cache:
            del self.cache[oldest_hash]
            if METRICS_AVAILABLE:
                CONSENSUS_CACHE_EVICTIONS.inc()
            logger.debug("Evicted LRU cache entry")

    async def get_or_compute(
        self,
        task: str,
        compute_fn: Callable[[str], Awaitable[ConsensusState]],
        context: dict[str, Any] | None = None,
    ) -> ConsensusState:
        """Get cached consensus or compute new.

        Args:
            task: Task description
            compute_fn: Async function to compute consensus
            context: Optional context

        Returns:
            ConsensusState (cached or freshly computed)
        """
        # Try cache first
        cached = self.get(task, context)
        if cached is not None:
            return cached

        # Cache miss: compute
        start = time.time()
        state = await compute_fn(task)
        duration = time.time() - start

        if METRICS_AVAILABLE:
            CONSENSUS_LATENCY_FULL.observe(duration)

        # Store in cache if successful
        if state.converged:
            self.put(task, state, context)

        return state

    def clear(self) -> None:
        """Clear entire cache."""
        self.cache.clear()
        self.access_order.clear()
        logger.info("Cleared consensus cache")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache stats
        """
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl,
            "total_access": sum(e.access_count for e in self.cache.values()),
        }


# =============================================================================
# PREDICTIVE CONSENSUS
# =============================================================================


@dataclass
class PredictedConsensus:
    """Predicted consensus outcome from world model."""

    routing: dict[ColonyID, str]
    confidence: float
    predicted: bool = True


class PredictiveConsensus:
    """Use world model to predict consensus outcome.

    Skips full Byzantine consensus if world model confidence is high.
    """

    def __init__(
        self,
        consensus: KagamiConsensus,
        world_model: Any | None = None,
        confidence_threshold: float = 0.9,
    ):
        """Initialize predictive consensus.

        Args:
            consensus: "KagamiConsensus" instance (fallback)
            world_model: Optional KagamiWorldModel for prediction
            confidence_threshold: Minimum confidence to use prediction
        """
        self.consensus = consensus
        self.world_model = world_model
        self.confidence_threshold = confidence_threshold

        logger.info(
            f"Initialized PredictiveConsensus "
            f"(threshold={confidence_threshold}, model={'enabled' if world_model else 'disabled'})"
        )

    async def predict_or_compute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> ConsensusState:
        """Predict consensus or fall back to full computation.

        Args:
            task: Task description
            context: Optional context

        Returns:
            ConsensusState (predicted or computed)
        """
        start = time.time()

        # Attempt prediction if world model available
        if self.world_model is not None:
            try:
                predicted_routing, confidence = await self._predict_routing(task, context or {})

                if METRICS_AVAILABLE:
                    CONSENSUS_PREDICTION_CONFIDENCE.observe(confidence)

                if confidence >= self.confidence_threshold:
                    # High confidence: use prediction
                    duration = time.time() - start

                    if METRICS_AVAILABLE:
                        CONSENSUS_PREDICTIONS_TOTAL.inc(labels={"used": "true"})
                        CONSENSUS_LATENCY_PREDICTED.observe(duration)

                    logger.info(
                        f"Using predicted consensus (confidence={confidence:.3f}, "
                        f"latency={duration * 1000:.1f}ms)"
                    )

                    # Lazy import to avoid circular dependency
                    from kagami.core.coordination.kagami_consensus import ConsensusState

                    return ConsensusState(
                        proposals=[],  # No proposals needed
                        agreement_matrix=np.eye(7),
                        consensus_routing=predicted_routing,
                        cbf_constraint=0.5,  # Assume safe
                        converged=True,
                        iterations=0,
                        timestamp=time.time(),
                    )
                else:
                    if METRICS_AVAILABLE:
                        CONSENSUS_PREDICTIONS_TOTAL.inc(labels={"used": "false"})
                    logger.debug(
                        f"Low prediction confidence ({confidence:.3f}), running full consensus"
                    )

            except Exception as e:
                logger.warning(f"Prediction failed: {e}, falling back to full consensus")
                if METRICS_AVAILABLE:
                    CONSENSUS_PREDICTIONS_TOTAL.inc(labels={"used": "false"})

        # Fall back to full consensus
        proposals = await self.consensus.collect_proposals(
            task_description=task,
            context=context,
            world_model=self.world_model,
        )

        state = await self.consensus.byzantine_consensus(proposals)

        duration = time.time() - start
        if METRICS_AVAILABLE:
            CONSENSUS_LATENCY_FULL.observe(duration)

        return state

    async def _predict_routing(
        self,
        task: str,
        context: dict[str, Any],
    ) -> tuple[dict[ColonyID, str], float]:
        """Predict routing using world model and LLM.

        Args:
            task: Task description
            context: Additional context

        Returns:
            Tuple of (predicted_routing, confidence)

        Raises:
            RuntimeError: If LLM unavailable for routing prediction
        """
        # Use LLM for intelligent routing prediction - NO KEYWORD FALLBACK

        llm = get_llm_service()

        if not llm.is_initialized or not llm.are_models_ready:
            raise RuntimeError(
                "LLM models not ready for routing prediction. "
                "Real routing requires LLM - no keyword fallbacks."
            )

        prompt = f"""Analyze this task and determine which colonies should handle it.

Task: "{task}"
Context: {context}

Available colonies and their specializations:
- SPARK (1): Creativity, ideation, brainstorming
- FORGE (2): Implementation, building, code construction
- FLOW (3): Debugging, recovery, adaptation
- NEXUS (4): Integration, memory, binding systems
- BEACON (5): Planning, architecture, strategy
- GROVE (6): Research, documentation, exploration
- CRYSTAL (7): Testing, verification, security

Rules:
1. Select 1-3 colonies that best match the task
2. Consider Fano line synergies (e.g., SPARK+FORGE+FLOW collaborate well)
3. Higher confidence for clear matches, lower for ambiguous tasks

Respond in this exact format:
colonies: COLONY1, COLONY2
confidence: 0.XX
reasoning: one sentence why

Example:
Task: "Implement the E8 lattice encoder"
colonies: FORGE, CRYSTAL
confidence: 0.92
reasoning: Implementation task requiring building and verification

Now analyze the given task:"""

        response = await llm.generate(
            prompt=prompt,
            app_name="consensus_optimizer",
            task_type=TaskType.REASONING,
            max_tokens=100,
            temperature=0.3,
        )

        # Parse LLM response
        response_str = str(response)
        predicted_colonies: list[ColonyID] = []
        confidence = 0.7

        for line in response_str.strip().split("\n"):
            line_lower = line.lower().strip()
            if line_lower.startswith("colonies:"):
                colony_str = line.split(":", 1)[1].strip()
                for colony_name in colony_str.upper().replace(",", " ").split():
                    colony_name = colony_name.strip()
                    if hasattr(ColonyID, colony_name):
                        predicted_colonies.append(ColonyID[colony_name])
            elif line_lower.startswith("confidence:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass

        if not predicted_colonies:
            raise RuntimeError(
                f"LLM failed to predict colonies for task: '{task[:100]}...'\n"
                f"Response was: {response_str}\n"
                f"No keyword fallback - routing prediction requires LLM."
            )

        # Convert to routing dict[str, Any]
        routing = dict[str, Any].fromkeys(predicted_colonies, "activate")

        return routing, confidence


# =============================================================================
# BATCHED CONSENSUS
# =============================================================================


class BatchedConsensus:
    """Batch multiple tasks into single consensus round.

    Reduces consensus overhead by amortizing Byzantine protocol costs.
    """

    def __init__(
        self,
        consensus: KagamiConsensus,
        batch_size: int = 10,
        batch_timeout: float = 0.05,  # 50ms
        enable_affinity_grouping: bool = True,
    ):
        """Initialize batched consensus.

        Args:
            consensus: "KagamiConsensus" instance
            batch_size: Maximum tasks per batch
            batch_timeout: Timeout in seconds to trigger batch
            enable_affinity_grouping: Group by Fano affinity
        """
        self.consensus = consensus
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.enable_affinity_grouping = enable_affinity_grouping

        self.pending_tasks: list[tuple[str, dict[str, Any], asyncio.Future]] = []
        self.batch_lock = asyncio.Lock()
        self.batch_timer_task: asyncio.Task | None = None

        logger.info(
            f"Initialized BatchedConsensus "
            f"(size={batch_size}, timeout={batch_timeout * 1000:.0f}ms, "
            f"affinity={'enabled' if enable_affinity_grouping else 'disabled'})"
        )

    async def submit_task(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> ConsensusState:
        """Submit task for batched consensus.

        Args:
            task: Task description
            context: Optional context

        Returns:
            ConsensusState when batch processes
        """
        future: asyncio.Future[ConsensusState] = asyncio.Future()

        async with self.batch_lock:
            self.pending_tasks.append((task, context or {}, future))

            # Start batch timer if not running
            if self.batch_timer_task is None or self.batch_timer_task.done():
                self.batch_timer_task = asyncio.create_task(self._batch_timer())

            # If batch full, process immediately
            if len(self.pending_tasks) >= self.batch_size:
                await self._process_batch()

        # Wait for consensus result
        return await future

    async def _batch_timer(self) -> None:
        """Wait for timeout, then process batch."""
        await asyncio.sleep(self.batch_timeout)

        async with self.batch_lock:
            if self.pending_tasks:
                if METRICS_AVAILABLE:
                    CONSENSUS_BATCH_TIMEOUT.inc()
                await self._process_batch()

    async def _process_batch(self) -> None:
        """Process pending batch of tasks.

        Must be called while holding batch_lock.
        """
        if not self.pending_tasks:
            return

        batch = self.pending_tasks
        self.pending_tasks = []

        start = time.time()
        batch_size = len(batch)

        if METRICS_AVAILABLE:
            CONSENSUS_BATCH_SIZE.observe(batch_size)

        logger.info(f"Processing consensus batch of {batch_size} tasks")

        # Group by affinity if enabled
        if self.enable_affinity_grouping and batch_size > 1:
            task_strings = [task for task, _, _ in batch]
            affinity_batches = group_by_fano_affinity(task_strings, self.batch_size)
            logger.debug(f"Grouped into {len(affinity_batches)} affinity-based sub-batches")

        # Process all tasks in parallel
        results = await asyncio.gather(
            *[self._consensus_single(task, ctx) for task, ctx, _ in batch],
            return_exceptions=True,
        )

        # Resolve futures
        for (_, _, future), result in zip(batch, results, strict=False):
            if isinstance(result, Exception):
                future.set_exception(result)
            else:
                future.set_result(result)

        duration = time.time() - start
        latency_per_task = duration / batch_size

        logger.info(
            f"Batch processed in {duration * 1000:.1f}ms ({latency_per_task * 1000:.1f}ms per task)"
        )

        if METRICS_AVAILABLE:
            CONSENSUS_LATENCY_BATCHED.observe(latency_per_task)

    async def _consensus_single(
        self,
        task: str,
        context: dict[str, Any],
    ) -> ConsensusState:
        """Run consensus for single task.

        Args:
            task: Task description
            context: Context dict[str, Any]

        Returns:
            ConsensusState
        """
        proposals = await self.consensus.collect_proposals(
            task_description=task,
            context=context,
        )

        return await self.consensus.byzantine_consensus(proposals)


# =============================================================================
# PARALLEL PROPOSAL COLLECTION
# =============================================================================


async def parallel_proposal_collection(
    colonies: list[ColonyID],
    task: str,
    context: dict[str, Any],
    proposal_fn: Callable[[ColonyID, str, dict[str, Any]], Awaitable[CoordinationProposal]],
    max_concurrency: int = 7,
) -> list[CoordinationProposal]:
    """Collect proposals with concurrency limit.

    Args:
        colonies: List of colonies to query
        task: Task description
        context: Context dict[str, Any]
        proposal_fn: Async function to get proposal from colony
        max_concurrency: Maximum concurrent requests

    Returns:
        List of proposals
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def bounded_propose(colony: ColonyID) -> CoordinationProposal:
        async with semaphore:
            return await proposal_fn(colony, task, context)

    proposals = await asyncio.gather(*[bounded_propose(colony) for colony in colonies])

    return list(proposals)


# =============================================================================
# UNIFIED OPTIMIZER
# =============================================================================


class ConsensusOptimizer:
    """Unified consensus optimization layer.

    Combines caching, prediction, and batching for optimal performance.
    """

    def __init__(
        self,
        consensus: KagamiConsensus,
        world_model: Any | None = None,
        enable_cache: bool = True,
        enable_prediction: bool = True,
        enable_batching: bool = True,
        cache_ttl: int = 300,
        cache_max_size: int = 1000,
        prediction_threshold: float = 0.9,
        batch_size: int = 10,
        batch_timeout: float = 0.05,
    ):
        """Initialize consensus optimizer.

        Args:
            consensus: Base KagamiConsensus instance
            world_model: Optional world model for prediction
            enable_cache: Enable consensus caching
            enable_prediction: Enable predictive consensus
            enable_batching: Enable batched consensus
            cache_ttl: Cache TTL in seconds
            cache_max_size: Maximum cache entries
            prediction_threshold: Min confidence for prediction
            batch_size: Maximum batch size
            batch_timeout: Batch timeout in seconds
        """
        self.consensus = consensus

        # Caching layer
        self.cache: ConsensusCache | None = None
        if enable_cache:
            self.cache = ConsensusCache(ttl=cache_ttl, max_size=cache_max_size)

        # Prediction layer
        self.predictor: PredictiveConsensus | None = None
        if enable_prediction:
            self.predictor = PredictiveConsensus(
                consensus=consensus,
                world_model=world_model,
                confidence_threshold=prediction_threshold,
            )

        # Batching layer
        self.batcher: BatchedConsensus | None = None
        if enable_batching:
            self.batcher = BatchedConsensus(
                consensus=consensus,
                batch_size=batch_size,
                batch_timeout=batch_timeout,
            )

        logger.info(
            f"Initialized ConsensusOptimizer "
            f"(cache={enable_cache}, prediction={enable_prediction}, batching={enable_batching})"
        )

    async def run_consensus(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> ConsensusState:
        """Run optimized consensus.

        Tries layers in order: cache → prediction → batching → full.

        Args:
            task: Task description
            context: Optional context

        Returns:
            ConsensusState
        """
        start = time.time()

        # Layer 1: Cache
        if self.cache is not None:
            cached = self.cache.get(task, context)
            if cached is not None:
                duration = time.time() - start
                if METRICS_AVAILABLE:
                    CONSENSUS_LATENCY_CACHED.observe(duration)
                return cached

        # Layer 2: Prediction
        if self.predictor is not None:
            state = await self.predictor.predict_or_compute(task, context)

            # Cache if successful
            if self.cache is not None and state.converged:
                self.cache.put(task, state, context)

            return state

        # Layer 3: Batching
        if self.batcher is not None:
            state = await self.batcher.submit_task(task, context)

            # Cache if successful
            if self.cache is not None and state.converged:
                self.cache.put(task, state, context)

            return state

        # Layer 4: Full consensus (no optimizations)
        proposals = await self.consensus.collect_proposals(
            task_description=task,
            context=context,
        )
        state = await self.consensus.byzantine_consensus(proposals)

        duration = time.time() - start
        if METRICS_AVAILABLE:
            CONSENSUS_LATENCY_FULL.observe(duration)

        # Cache if successful
        if self.cache is not None and state.converged:
            self.cache.put(task, state, context)

        return state

    def get_stats(self) -> dict[str, Any]:
        """Get optimizer statistics.

        Returns:
            Dict with stats from all layers
        """
        stats: dict[str, Any] = {}

        if self.cache is not None:
            stats["cache"] = self.cache.get_stats()

        if self.predictor is not None:
            stats["predictor"] = {
                "threshold": self.predictor.confidence_threshold,
                "model_enabled": self.predictor.world_model is not None,
            }

        if self.batcher is not None:
            stats["batcher"] = {
                "batch_size": self.batcher.batch_size,
                "batch_timeout_ms": self.batcher.batch_timeout * 1000,
                "pending_tasks": len(self.batcher.pending_tasks),
            }

        return stats


# =============================================================================
# FACTORY
# =============================================================================


def create_consensus_optimizer(  # type: ignore[no-untyped-def]
    consensus: KagamiConsensus | None = None,
    world_model: Any | None = None,
    enable_cache: bool = True,
    enable_prediction: bool = True,
    enable_batching: bool = True,
    **kwargs,
) -> ConsensusOptimizer:
    """Factory for creating optimized consensus system.

    Args:
        consensus: Optional base consensus (created if None)
        world_model: Optional world model for prediction
        enable_cache: Enable caching layer
        enable_prediction: Enable prediction layer
        enable_batching: Enable batching layer
        **kwargs: Additional optimizer config

    Returns:
        ConsensusOptimizer instance
    """
    if consensus is None:
        from kagami.core.coordination.kagami_consensus import create_consensus_protocol

        consensus = create_consensus_protocol()

    return ConsensusOptimizer(
        consensus=consensus,
        world_model=world_model,
        enable_cache=enable_cache,
        enable_prediction=enable_prediction,
        enable_batching=enable_batching,
        **kwargs,
    )


__all__ = [
    "BatchedConsensus",
    "ConsensusCache",
    "ConsensusOptimizer",
    "PredictiveConsensus",
    "create_consensus_optimizer",
    "group_by_fano_affinity",
    "parallel_proposal_collection",
]
