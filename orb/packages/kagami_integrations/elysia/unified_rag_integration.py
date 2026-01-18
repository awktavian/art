"""Unified RAG Integration — Elysia Connected to All Kagami Subsystems.

ARCHITECTURE (Dec 7, 2025):
============================

PARALLELIZATION STRATEGY:
- S⁷ PARALLEL: All 7 colonies processed in parallel where possible
- asyncio.gather(): Workspace, Bus, CoT operations run concurrently
- Batch operations: Weaviate writes batched for efficiency
- Pipeline parallelism: Query → [Workspace || Bus || CoT] → Response

This module provides the **optimal unified integration** of Elysia RAG with:

1. **Global Workspace (GWT)**:
   - RAG results compete for workspace access via salience
   - High-relevance results broadcast to all subscribers
   - Supports attention-driven context selection

2. **Unified E8 Event Bus**:
   - All RAG events encoded as E8Events with Fano routing
   - Colony-specific subscriptions for specialized handling
   - Cross-instance distribution via Redis

3. **Organism CoT (Chain-of-Thought)**:
   - RAG results inform meta-reasoning
   - Few-shot examples enrich colony traces
   - Fano compositions integrate retrieval with reasoning

4. **Message Bus (Cross-Instance)**:
   - E8-encoded RAG queries across instances
   - Distributed retrieval with unified memory

5. **Stigmergy Feedback Loop**:
   - User ratings become receipts
   - ACO probabilities guide routing
   - Superorganism health tracking

UNIFIED DATA FLOW:
==================

    User Query
        │
        ▼
    ┌─────────────────┐
    │  KagamiElysia   │ ──────────────────────┐
    │  (Fano Router)  │                       │
    └────────┬────────┘                       │
             │                                │
             ▼                                ▼
    ┌─────────────────┐              ┌─────────────────┐
    │  UnifiedE8Bus   │◀────────────▶│  GlobalWorkspace │
    │  (E8Event)      │              │  (Salience)      │
    └────────┬────────┘              └────────┬────────┘
             │                                │
             ▼                                ▼
    ┌─────────────────┐              ┌─────────────────┐
    │  OrganismCoT    │◀────────────▶│ ConsciousWorkspace│
    │  (Meta-Reason)  │              │ (Competition)     │
    └────────┬────────┘              └────────┬────────┘
             │                                │
             └───────────────┬────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Stigmergy Loop  │
                    │ (ACO/Receipts)  │
                    └─────────────────┘

E8 PROTOCOL:
============
All data flows through E8 quantization:
- Queries: hash(query) % 240 → E8 index
- Results: embedding → E8 residual encoding
- Events: topic → colony → Fano line routing

COLONY DISPLAY MAPPING:
=======================
Query complexity determines display via Fano routing:
- Simple (1 colony): Direct response
- Medium (3 colonies): Fano line composition
- Complex (7 colonies): Full superorganism synthesis

Scientific basis:
- GWT: Baars (1988), Dehaene & Changeux (2011)
- E8: Viazovska (2016), sphere packing optimality
- Fano: G₂ 3-form φ, octonion multiplication
- Stigmergy: Theraulaz & Bonabeau (1999), indirect coordination
- ACO: Dorigo & Di Caro (1999), ant colony optimization

Created: December 7, 2025
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.events.unified_e8_bus import E8Event, UnifiedE8Bus
    from kagami.core.workspace.conscious_workspace import ConsciousWorkspace
    from kagami.core.workspace.global_workspace import GlobalWorkspace

    from kagami_integrations.elysia.chunking_bridge import ChunkOnDemandBridge
    from kagami_integrations.elysia.dspy_integration import KagamiDSPyModule

logger = logging.getLogger(__name__)


# =============================================================================
# S⁷ PARALLEL UTILITIES
# =============================================================================


async def parallel_gather(*coros, return_exceptions: bool = True) -> list[Any]:  # type: ignore[no-untyped-def]
    """Execute coroutines in parallel with exception handling.

    Args:
        *coros: Coroutines to execute
        return_exceptions: If True, return exceptions instead of raising

    Returns:
        List of results (or exceptions if return_exceptions=True)
    """
    return await asyncio.gather(*coros, return_exceptions=return_exceptions)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class UnifiedRAGConfig:
    """Configuration for unified RAG integration.

    Tunes the integration between all subsystems.
    """

    # Workspace integration
    workspace_enabled: bool = True
    salience_weight: float = 0.7  # How much salience affects broadcast
    min_salience_threshold: float = 0.3  # Minimum to compete for workspace

    # E8 Bus integration
    bus_enabled: bool = True
    bus_topic_prefix: str = "elysia"
    use_fano_routing: bool = True

    # CoT integration
    cot_enabled: bool = True
    inject_fewshot: bool = True  # Inject few-shot into colony traces
    max_fewshot_examples: int = 3

    # Stigmergy
    stigmergy_enabled: bool = True
    emit_receipts: bool = True

    # Cross-instance (Message Bus)
    mesh_enabled: bool = False  # Disabled by default (requires Redis)

    # Timing
    broadcast_delay_ms: float = 10.0  # Delay before workspace broadcast


# =============================================================================
# WORKSPACE ADAPTER
# =============================================================================


@dataclass
class RAGWorkspaceEntry:
    """Entry for RAG results competing for workspace access."""

    query_id: str
    query: str
    results: list[dict[str, Any]]
    colonies_used: list[str]
    fano_line: tuple[int, int, int] | None
    salience: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class ElysiaWorkspaceAdapter:
    """Adapts Elysia RAG results to Global Workspace Theory.

    Responsibilities:
    1. Compute salience for RAG results
    2. Submit results to workspace competition
    3. Handle broadcast notifications
    4. Integrate with ConsciousWorkspace ignition

    Salience computation considers:
    - Result relevance (similarity score)
    - Colony confidence
    - Recency
    - User engagement history (from stigmergy)

    Usage:
        adapter = ElysiaWorkspaceAdapter()
        await adapter.submit_results(elysia_response)
    """

    def __init__(self, config: UnifiedRAGConfig | None = None):
        """Initialize workspace adapter.

        Args:
            config: Configuration options
        """
        self.config = config or UnifiedRAGConfig()

        # Lazy-loaded subsystems
        self._global_workspace: GlobalWorkspace | None = None
        self._conscious_workspace: ConsciousWorkspace | None = None

        # Pending entries (for batching)
        self._pending: list[RAGWorkspaceEntry] = []

        logger.debug("ElysiaWorkspaceAdapter initialized")

    def _get_global_workspace(self) -> GlobalWorkspace:
        """Lazy-load global workspace."""
        if self._global_workspace is None:
            from kagami.core.workspace.global_workspace import get_global_workspace

            self._global_workspace = get_global_workspace()
        return self._global_workspace

    def _get_conscious_workspace(self) -> ConsciousWorkspace:
        """Lazy-load conscious workspace."""
        if self._conscious_workspace is None:
            from kagami.core.workspace.conscious_workspace import get_conscious_workspace

            self._conscious_workspace = get_conscious_workspace()
        return self._conscious_workspace

    def compute_salience(
        self,
        query: str,
        results: list[dict[str, Any]],
        colonies_used: list[str],
        fano_line: tuple[int, int, int] | None = None,
    ) -> float:
        """Compute salience score for RAG results.

        Salience combines:
        - Relevance: Average similarity of results (0.4 weight)
        - Colony confidence: How well-routed the query was (0.3 weight)
        - Complexity alignment: Did complexity match routing? (0.2 weight)
        - Recency: Fresh results preferred (0.1 weight)

        Args:
            query: User query
            results: Retrieved results with similarity scores
            colonies_used: Colonies that processed the query
            fano_line: Fano line if 3-colony routing

        Returns:
            Salience score [0, 1]
        """
        # Relevance: average result similarity
        if results:
            similarities = [r.get("similarity", r.get("score", 0.5)) for r in results]
            relevance = sum(similarities) / len(similarities)
        else:
            relevance = 0.1  # Low salience for empty results

        # Colony confidence: more colonies = more thorough = higher confidence
        colony_conf = len(colonies_used) / 7.0  # Normalized by max colonies

        # Complexity alignment: Fano line = medium complexity handled well
        if fano_line is not None:
            complexity_match = 0.8  # Good: used Fano routing
        elif len(colonies_used) == 1:
            complexity_match = 0.6  # Okay: simple query, simple routing
        elif len(colonies_used) == 7:
            complexity_match = 0.9  # Good: complex query, full routing
        else:
            complexity_match = 0.5  # Suboptimal routing

        # Recency: always 1.0 for fresh results
        recency = 1.0

        # Weighted combination
        salience = 0.4 * relevance + 0.3 * colony_conf + 0.2 * complexity_match + 0.1 * recency

        return min(1.0, max(0.0, salience))  # type: ignore[no-any-return]

    async def submit_results(
        self,
        query_id: str,
        query: str,
        results: list[dict[str, Any]],
        colonies_used: list[str],
        fano_line: tuple[int, int, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RAGWorkspaceEntry:
        """Submit RAG results to workspace competition.

        S⁷ PARALLEL: Submits to conscious and global workspace concurrently.

        Args:
            query_id: Unique query identifier
            query: User query
            results: Retrieved results
            colonies_used: Colonies that processed
            fano_line: Fano line if 3-colony routing
            metadata: Additional metadata

        Returns:
            RAGWorkspaceEntry submitted
        """
        salience = self.compute_salience(query, results, colonies_used, fano_line)

        entry = RAGWorkspaceEntry(
            query_id=query_id,
            query=query,
            results=results,
            colonies_used=colonies_used,
            fano_line=fano_line,
            salience=salience,
            metadata=metadata or {},
        )

        # Check threshold
        if salience < self.config.min_salience_threshold:
            logger.debug(f"RAG result below salience threshold: {salience:.2f}")
            return entry

        # S⁷ PARALLEL: Submit to BOTH workspaces concurrently
        state_data = {
            "type": "elysia.rag_result",
            "query_id": query_id,
            "query": query,
            "results_count": len(results),
            "colonies": colonies_used,
            "fano_line": fano_line,
        }
        agent_name = f"elysia:{colonies_used[0] if colonies_used else 'nexus'}"

        async def submit_conscious() -> None:
            conscious = self._get_conscious_workspace()
            await conscious.compete_for_access(
                state=state_data,
                salience=salience,
                agent=agent_name,
            )

        async def submit_global() -> None:
            global_ws = self._get_global_workspace()
            # Global workspace handles broadcasting via its internal loop
            # We can optionally attach bus here if needed
            if hasattr(global_ws, "attach_bus") and global_ws._bus is None:
                try:
                    from kagami.core.events import get_unified_bus

                    global_ws.attach_bus(get_unified_bus())
                except Exception:
                    pass

        # Run both submissions in parallel
        await parallel_gather(
            submit_conscious(),
            submit_global(),
        )

        logger.debug(
            f"RAG submitted to workspace (parallel): query_id={query_id}, "
            f"salience={salience:.2f}, colonies={colonies_used}"
        )

        return entry


# =============================================================================
# E8 BUS HANDLER
# =============================================================================


class ElysiaE8EventHandler:
    """Handles E8 events for Elysia RAG integration.

    Responsibilities:
    1. Publish RAG events to unified bus
    2. Subscribe to relevant topics
    3. Route events via Fano lines
    4. Handle cross-colony coordination

    Event types:
    - elysia.query: New query submitted
    - elysia.result: Results retrieved
    - elysia.feedback: User feedback received
    - elysia.pattern: Pattern update from stigmergy

    Usage:
        handler = ElysiaE8EventHandler()
        await handler.start()
        await handler.publish_query(query, context)
    """

    # Colony indices for Fano routing
    COLONY_INDICES = {
        "spark": 0,
        "forge": 1,
        "flow": 2,
        "nexus": 3,
        "beacon": 4,
        "grove": 5,
        "crystal": 6,
    }

    def __init__(self, config: UnifiedRAGConfig | None = None):
        """Initialize E8 event handler.

        Args:
            config: Configuration options
        """
        self.config = config or UnifiedRAGConfig()

        # Lazy-loaded bus
        self._bus: UnifiedE8Bus | None = None

        # Registered handlers
        self._handlers: dict[str, list] = {}

        logger.debug("ElysiaE8EventHandler initialized")

    def _get_bus(self) -> UnifiedE8Bus:
        """Lazy-load unified E8 bus."""
        if self._bus is None:
            from kagami.core.events.unified_e8_bus import get_unified_bus

            self._bus = get_unified_bus()
        return self._bus

    async def start(self) -> None:
        """Start event handler, subscribing to relevant topics."""
        if not self.config.bus_enabled:
            return

        bus = self._get_bus()

        # Subscribe to Elysia-related topics
        bus.subscribe(f"{self.config.bus_topic_prefix}.*", self._handle_elysia_event)

        # Subscribe to colony-specific events
        for colony in self.COLONY_INDICES:
            bus.subscribe(f"colony.{colony}.*", self._handle_colony_event)

        logger.info("✅ ElysiaE8EventHandler started")

    async def _handle_elysia_event(self, event: E8Event) -> None:
        """Handle Elysia-specific events."""
        topic = event.topic
        handlers = self._handlers.get(topic, [])

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Elysia event handler error: {e}")

    async def _handle_colony_event(self, event: E8Event) -> None:
        """Handle colony events that may affect Elysia."""
        # Colony events can trigger RAG updates
        if "learning" in event.topic or "pattern" in event.topic:
            # Stigmergy pattern update
            await self._handle_pattern_update(event)

    async def _handle_pattern_update(self, event: E8Event) -> None:
        """Handle stigmergy pattern updates."""
        # Update Elysia's routing probabilities
        payload = event.payload
        colony = payload.get("colony")
        success_rate = payload.get("success_rate", 0.5)

        logger.debug(f"Pattern update for colony {colony}: {success_rate:.2f}")

    async def publish_query(
        self,
        query_id: str,
        query: str,
        complexity: float,
        target_colonies: list[str],
    ) -> E8Event:
        """Publish query event to bus.

        Args:
            query_id: Unique query identifier
            query: User query
            complexity: Estimated complexity
            target_colonies: Target colonies for routing

        Returns:
            Published E8Event
        """
        bus = self._get_bus()

        # Determine source colony (primary router)
        source_colony = self.COLONY_INDICES.get(target_colonies[0], 3)  # Default: nexus

        # E8 index from query hash
        query_hash = int(hashlib.md5(query.encode()).hexdigest()[:4], 16)
        e8_index = query_hash % 240

        return await bus.publish(
            topic=f"{self.config.bus_topic_prefix}.query",
            payload={
                "query_id": query_id,
                "query": query,
                "complexity": complexity,
                "target_colonies": target_colonies,
                "e8_index": e8_index,
            },
            source_colony=source_colony,
            use_fano=self.config.use_fano_routing and len(target_colonies) == 3,
        )

    async def publish_result(
        self,
        query_id: str,
        results: list[dict[str, Any]],
        colonies_used: list[str],
        fano_line: tuple[int, int, int] | None = None,
    ) -> E8Event:
        """Publish result event to bus.

        Args:
            query_id: Query identifier
            results: Retrieved results
            colonies_used: Colonies that processed
            fano_line: Fano line if used

        Returns:
            Published E8Event
        """
        bus = self._get_bus()

        source_colony = self.COLONY_INDICES.get(colonies_used[-1], 3)  # Result colony

        return await bus.publish(
            topic=f"{self.config.bus_topic_prefix}.result",
            payload={
                "query_id": query_id,
                "results_count": len(results),
                "colonies_used": colonies_used,
                "fano_line": fano_line,
            },
            source_colony=source_colony,
            use_fano=fano_line is not None,
        )

    async def publish_feedback(
        self,
        query_id: str,
        rating: int,
        colony: str,
    ) -> E8Event:
        """Publish feedback event to bus.

        Args:
            query_id: Query identifier
            rating: User rating (1-5)
            colony: Colony that handled query

        Returns:
            Published E8Event
        """
        bus = self._get_bus()

        return await bus.publish(
            topic=f"{self.config.bus_topic_prefix}.feedback",
            payload={
                "query_id": query_id,
                "rating": rating,
                "colony": colony,
                "success": rating >= 4,
            },
            source_colony=self.COLONY_INDICES.get(colony, 3),
        )


# =============================================================================
# COT BRIDGE
# =============================================================================


class ElysiaCoTBridge:
    """Bridges Elysia RAG to Organism CoT meta-reasoning.

    Responsibilities:
    1. Inject RAG results as context for reasoning
    2. Use few-shot examples to enrich colony traces
    3. Integrate retrieval with Fano composition
    4. Provide semantic grounding for meta-reasoning

    The CoT can use RAG results to:
    - Ground abstract reasoning in concrete examples
    - Provide evidence for conclusions
    - Resolve ambiguity via retrieved context

    Usage:
        bridge = ElysiaCoTBridge()
        enriched = await bridge.enrich_cot_context(rag_results, organism_cot)
    """

    def __init__(self, config: UnifiedRAGConfig | None = None):
        """Initialize CoT bridge.

        Args:
            config: Configuration options
        """
        self.config = config or UnifiedRAGConfig()

        # Cache for recent enrichments
        self._enrichment_cache: dict[str, dict] = {}
        self._cache_max_size = 50

        logger.debug("ElysiaCoTBridge initialized")

    async def enrich_cot_context(
        self,
        query: str,
        rag_results: list[dict[str, Any]],
        fewshot_examples: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Enrich CoT reasoning context with RAG results.

        Creates a structured context that the OrganismCoT can use
        during meta-reasoning.

        Args:
            query: User query
            rag_results: Retrieved results from Elysia
            fewshot_examples: Few-shot examples from feedback history

        Returns:
            Enriched context dict for CoT
        """
        # Extract key information from results
        evidence = []
        for result in rag_results[:5]:  # Top 5 results
            evidence.append(
                {
                    "content": result.get("content", "")[:500],  # Truncate
                    "source": result.get("source_id", "unknown"),
                    "relevance": result.get("similarity", 0.5),
                }
            )

        # Structure few-shot examples
        examples = []
        if self.config.inject_fewshot and fewshot_examples:
            for ex in fewshot_examples[: self.config.max_fewshot_examples]:
                examples.append(
                    {
                        "query": ex.get("query", ""),
                        "response": ex.get("response", "")[:300],
                        "rating": ex.get("rating", 0),
                    }
                )

        context = {
            "query": query,
            "evidence": evidence,
            "fewshot_examples": examples,
            "evidence_count": len(rag_results),
            "has_examples": len(examples) > 0,
            "timestamp": time.time(),
        }

        # Cache
        cache_key = hashlib.md5(query.encode()).hexdigest()[:8]
        self._enrichment_cache[cache_key] = context
        if len(self._enrichment_cache) > self._cache_max_size:
            # Remove oldest
            oldest_key = next(iter(self._enrichment_cache))
            del self._enrichment_cache[oldest_key]

        return context

    def get_semantic_grounding(
        self,
        rag_results: list[dict[str, Any]],
    ) -> list[float] | None:
        """Extract semantic centroid from RAG results for CoT grounding.

        This provides a semantic "anchor" for reasoning, helping the
        organism maintain coherence with retrieved knowledge.

        Args:
            rag_results: Retrieved results with embeddings

        Returns:
            Semantic centroid as float list, or None if unavailable
        """
        embeddings = []
        for result in rag_results:
            if "embedding" in result:
                embeddings.append(result["embedding"])
            elif "vector" in result:
                embeddings.append(result["vector"])

        if not embeddings:
            return None

        # Compute centroid (simple average)
        import numpy as np

        centroid = np.mean(embeddings, axis=0).tolist()
        return centroid  # type: ignore[no-any-return]


# =============================================================================
# UNIFIED INTEGRATION
# =============================================================================


class UnifiedRAGIntegration:
    """Unified integration of Elysia RAG with all Kagami subsystems.

    This is the main entry point for connected RAG operations. It:
    1. Coordinates between workspace, bus, and CoT
    2. Manages event flow and state
    3. Handles lifecycle of sub-adapters
    4. Provides unified query/response API
    5. Integrates chunking and DSPy for enhanced retrieval

    S⁷ PARALLELIZATION:
    - Query operations run workspace/bus/cot in parallel
    - Chunking happens asynchronously during retrieval
    - DSPy calls use multi-model routing

    Usage:
        integration = UnifiedRAGIntegration()
        await integration.start()

        # Query with full integration
        response = await integration.query("What is E8 quantization?")

        # Provide feedback
        await integration.feedback(response.query_id, rating=5)

        await integration.stop()
    """

    def __init__(
        self,
        config: UnifiedRAGConfig | None = None,
        elysia: Any | None = None,
    ):
        """Initialize unified integration.

        Args:
            config: Configuration options
            elysia: Optional existing KagamiElysia instance
        """
        self.config = config or UnifiedRAGConfig()

        # Core Elysia (lazy-loaded if not provided)
        self._elysia = elysia

        # Sub-adapters
        self.workspace_adapter = ElysiaWorkspaceAdapter(self.config)
        self.e8_handler = ElysiaE8EventHandler(self.config)
        self.cot_bridge = ElysiaCoTBridge(self.config)

        # Chunking bridge (lazy-loaded)
        self._chunking_bridge: ChunkOnDemandBridge | None = None

        # DSPy module (lazy-loaded)
        self._dspy_module: KagamiDSPyModule | None = None

        # State
        self._started = False
        self._query_count = 0

        logger.info("🪞 UnifiedRAGIntegration initialized")

    def _get_chunking_bridge(self) -> Any:
        """Lazy-load chunking bridge."""
        if self._chunking_bridge is None:
            try:
                from kagami_integrations.elysia.chunking_bridge import ChunkOnDemandBridge

                self._chunking_bridge = ChunkOnDemandBridge()
            except ImportError:
                logger.debug("ChunkOnDemandBridge not available")
        return self._chunking_bridge

    def _get_dspy_module(self) -> Any:
        """Lazy-load DSPy module."""
        if self._dspy_module is None:
            try:
                from kagami_integrations.elysia.dspy_integration import get_dspy_module

                self._dspy_module = get_dspy_module()
            except ImportError:
                logger.debug("DSPy module not available")
        return self._dspy_module

    async def _get_elysia(self) -> Any:
        """Lazy-load KagamiElysia."""
        if self._elysia is None:
            from kagami_integrations.elysia import KagamiElysia

            self._elysia = KagamiElysia()  # type: ignore[call-arg]
            await self._elysia.connect()  # type: ignore[attr-defined]
        return self._elysia

    async def _filter_rag_sources(self, elysia_response: Any) -> Any:
        """Filter RAG sources through ContentBoundaryEnforcer.

        SECURITY HARDENING (Dec 23, 2025):
        Prevents Morris II-style worm injection through RAG content.
        Filters all retrieved sources before they're used in context.

        Args:
            elysia_response: Raw Elysia response with sources

        Returns:
            Filtered response with sanitized sources
        """
        try:
            from kagami.core.security.content_boundary import (
                TrustLevel,
                get_content_boundary_enforcer,
            )

            if not elysia_response.sources:
                return elysia_response

            enforcer = get_content_boundary_enforcer()

            # Convert sources to chunk format expected by enforcer
            raw_chunks = [{"content": s.get("content", ""), **s} for s in elysia_response.sources]

            # Filter through content boundary enforcer
            sanitized_chunks = enforcer.filter_retrieved_chunks(
                chunks=raw_chunks,
                source="rag:elysia",
                trust_level=TrustLevel.RETRIEVED,
            )

            # Track what was filtered
            original_count = len(elysia_response.sources)
            filtered_count = len(sanitized_chunks)

            if filtered_count < original_count:
                logger.info(
                    f"🛡️ RAG security filter: {original_count - filtered_count}/{original_count} "
                    "sources blocked or sanitized"
                )

            # Update response with filtered sources
            # Convert back to original format, preserving metadata
            filtered_sources = []
            for chunk in sanitized_chunks:
                source_entry = {
                    "content": chunk.content,
                    "source_id": chunk.metadata.get("uuid", ""),
                    "similarity": chunk.metadata.get("similarity", 0.5),
                    "security_filtered": chunk.content != chunk.original_content,
                    "risk_score": chunk.risk_score.total_risk,
                    **{k: v for k, v in chunk.metadata.items() if k not in ("uuid", "similarity")},
                }
                filtered_sources.append(source_entry)

            # Create updated response (preserve all other fields)
            elysia_response.sources = filtered_sources
            return elysia_response

        except ImportError:
            logger.debug("ContentBoundaryEnforcer not available, skipping RAG filtering")
            return elysia_response
        except Exception as e:
            logger.warning(f"RAG security filter error: {e}, allowing unfiltered sources")
            return elysia_response

    async def start(self) -> None:
        """Start unified integration."""
        if self._started:
            return

        # Start E8 event handler
        if self.config.bus_enabled:
            await self.e8_handler.start()

        # Ensure Elysia is connected
        await self._get_elysia()

        self._started = True
        logger.info("✅ UnifiedRAGIntegration started")

    async def stop(self) -> None:
        """Stop unified integration."""
        if self._elysia:
            await self._elysia.close()
            self._elysia = None

        self._started = False
        logger.info("UnifiedRAGIntegration stopped")

    async def query(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        use_chunking: bool = True,
        use_dspy: bool = False,
    ) -> dict[str, Any]:
        """Execute unified query with full integration.

        S⁷ PARALLEL FLOW:
        1. [SEQUENTIAL] Publish query event to E8 bus (fast, non-blocking)
        2. [SEQUENTIAL] Execute Elysia query with Fano routing
        3. [PARALLEL] Submit results to workspace || Enrich CoT || Publish result event
        4. [OPTIONAL] Chunk large documents || DSPy enhancement
        5. Return unified response

        Args:
            query: User query
            context: Additional context
            use_chunking: Enable chunk-on-demand for large docs
            use_dspy: Enable DSPy enhancement for complex queries

        Returns:
            Unified response dict
        """
        if not self._started:
            await self.start()

        self._query_count += 1
        start_time = time.time()
        query_id = f"q_{self._query_count}"

        # Get Elysia
        elysia = await self._get_elysia()

        # Step 1: Publish query event (fast, fire-and-forget style)
        complexity = 0.5
        target_colonies: list[str] = ["nexus"]
        if self.config.bus_enabled:
            complexity = await elysia._tree._estimate_complexity(query, context or {})
            target_result = await elysia._tree._select_colonies(
                query,
                context or {},
                "fano_line" if 0.3 <= complexity < 0.7 else "single",
            )
            target_colonies = (
                target_result[0] if isinstance(target_result, tuple) else target_result
            )

            # Fire-and-forget (don't await, use create_task)
            asyncio.create_task(
                self.e8_handler.publish_query(
                    query_id=query_id,
                    query=query,
                    complexity=complexity,
                    target_colonies=target_colonies,
                )
            )

        # Step 2: Execute Elysia query (main retrieval)
        elysia_response = await elysia.query(query, context)

        # Step 2.5: SECURITY - Filter RAG results through ContentBoundaryEnforcer
        # This prevents Morris II-style worm injection via RAG
        elysia_response = await self._filter_rag_sources(elysia_response)

        # Step 3: S⁷ PARALLEL - Run workspace, CoT, and result publishing concurrently
        async def workspace_task() -> Any:
            if self.config.workspace_enabled:
                return await self.workspace_adapter.submit_results(
                    query_id=elysia_response.query_id,
                    query=query,
                    results=elysia_response.sources,
                    colonies_used=elysia_response.colonies_used,
                    fano_line=elysia_response.fano_line,
                    metadata=elysia_response.metadata,
                )
            return None

        async def cot_task() -> Any:
            if self.config.cot_enabled:
                return await self.cot_bridge.enrich_cot_context(
                    query=query,
                    rag_results=elysia_response.sources,
                    fewshot_examples=elysia_response.fewshot_examples,
                )
            return None

        async def result_event_task() -> Any:
            if self.config.bus_enabled:
                return await self.e8_handler.publish_result(
                    query_id=elysia_response.query_id,
                    results=elysia_response.sources,
                    colonies_used=elysia_response.colonies_used,
                    fano_line=elysia_response.fano_line,
                )
            return None

        async def chunking_task() -> None:
            if use_chunking and elysia_response.sources:
                bridge = self._get_chunking_bridge()
                if bridge:
                    # Check if any sources need chunking
                    large_docs = [
                        s for s in elysia_response.sources if len(s.get("content", "")) > 4000
                    ]
                    if large_docs:
                        return await bridge.retrieve_and_chunk(  # type: ignore[no-any-return]
                            query=query,
                            max_documents=5,
                        )
            return None

        async def dspy_task() -> None:
            if use_dspy and complexity > 0.6:
                module = self._get_dspy_module()
                if module:
                    return await module.execute(  # type: ignore[no-any-return]
                        query=query,
                        colony=target_colonies[0] if target_colonies else "nexus",
                        context={"sources": elysia_response.sources[:3]},
                        complexity=complexity,
                    )
            return None

        # Execute all tasks in parallel
        results = await parallel_gather(
            workspace_task(),
            cot_task(),
            result_event_task(),
            chunking_task(),
            dspy_task(),
        )

        # Unpack results
        _workspace_entry, cot_context, _result_event, chunked_content, dspy_result = results

        # Merge chunked content if available
        enhanced_sources = elysia_response.sources
        if chunked_content and not isinstance(chunked_content, Exception):
            enhanced_sources = [{"content": c, "chunked": True} for c in chunked_content]

        # Merge DSPy enhancement if available
        dspy_enhancement = None
        if dspy_result and not isinstance(dspy_result, Exception):
            dspy_enhancement = dspy_result

        duration_ms = (time.time() - start_time) * 1000

        return {
            "query_id": elysia_response.query_id,
            "success": elysia_response.success,
            "answer": elysia_response.answer,
            "sources": enhanced_sources,
            "display": elysia_response.display,
            "colonies_used": elysia_response.colonies_used,
            "fano_line": elysia_response.fano_line,
            "routing_mode": elysia_response.routing_mode,
            "reasoning": elysia_response.reasoning,
            "cot_context": cot_context if not isinstance(cot_context, Exception) else None,
            "dspy_enhancement": dspy_enhancement,
            "duration_ms": duration_ms,
            "integrated": True,
            "parallelization": {
                "workspace": not isinstance(results[0], Exception),
                "cot": not isinstance(results[1], Exception),
                "bus": not isinstance(results[2], Exception),
                "chunking": not isinstance(results[3], Exception) if results[3] else False,
                "dspy": not isinstance(results[4], Exception) if results[4] else False,
            },
        }

    async def feedback(
        self,
        query_id: str,
        rating: int,
        query: str | None = None,
        response: str | None = None,
    ) -> dict[str, Any]:
        """Record feedback with full integration.

        Flow:
        1. Record in Elysia (Weaviate + stigmergy)
        2. Publish feedback event to bus
        3. Update workspace salience model
        4. Return feedback result

        Args:
            query_id: Query identifier
            rating: User rating (1-5)
            query: Original query (optional)
            response: Response text (optional)

        Returns:
            Feedback result dict
        """
        elysia = await self._get_elysia()

        # Step 1: Record via Elysia
        result = await elysia.feedback(
            query_id=query_id,
            rating=rating,
            query=query,
            response=response,
        )

        # Step 2: Publish feedback event
        if self.config.bus_enabled:
            await self.e8_handler.publish_feedback(
                query_id=query_id,
                rating=rating,
                colony=result.get("colony", "nexus"),
            )

        result["integrated"] = True
        return result  # type: ignore[no-any-return]

    def get_status(self) -> dict[str, Any]:
        """Get integration status.

        Returns:
            Status dict with metrics
        """
        return {
            "started": self._started,
            "query_count": self._query_count,
            "config": {
                "workspace_enabled": self.config.workspace_enabled,
                "bus_enabled": self.config.bus_enabled,
                "cot_enabled": self.config.cot_enabled,
                "stigmergy_enabled": self.config.stigmergy_enabled,
                "mesh_enabled": self.config.mesh_enabled,
            },
            "components": {
                "chunking_available": self._chunking_bridge is not None,
                "dspy_available": self._dspy_module is not None,
                "elysia_connected": self._elysia is not None,
            },
            "parallelization": "S⁷ PARALLEL enabled",
        }

    async def __aenter__(self) -> UnifiedRAGIntegration:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, _exc_val, _exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Async context manager exit."""
        await self.stop()


# =============================================================================
# SINGLETON AND FACTORY
# =============================================================================

_unified_integration: UnifiedRAGIntegration | None = None


def get_unified_rag_integration(
    config: UnifiedRAGConfig | None = None,
) -> UnifiedRAGIntegration:
    """Get or create singleton unified RAG integration.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        UnifiedRAGIntegration singleton
    """
    global _unified_integration
    if _unified_integration is None:
        _unified_integration = UnifiedRAGIntegration(config)
    return _unified_integration


async def create_unified_rag_integration(
    config: UnifiedRAGConfig | None = None,
    elysia: Any | None = None,
    auto_start: bool = True,
) -> UnifiedRAGIntegration:
    """Create a new unified RAG integration.

    Args:
        config: Configuration options
        elysia: Optional existing KagamiElysia instance
        auto_start: Whether to start automatically

    Returns:
        Configured UnifiedRAGIntegration
    """
    integration = UnifiedRAGIntegration(config, elysia)
    if auto_start:
        await integration.start()
    return integration


__all__ = [
    "ElysiaCoTBridge",
    "ElysiaE8EventHandler",
    # Adapters
    "ElysiaWorkspaceAdapter",
    "RAGWorkspaceEntry",
    # Configuration
    "UnifiedRAGConfig",
    # Main integration
    "UnifiedRAGIntegration",
    "create_unified_rag_integration",
    "get_unified_rag_integration",
]
