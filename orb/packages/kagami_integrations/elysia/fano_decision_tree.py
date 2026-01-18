"""Fano Decision Tree — Elysia with Kagami Topology.

Integrates Elysia's decision tree architecture with Kagami's
Fano plane routing for mathematically grounded colony selection.

Key concepts:
- Decision nodes are colony-aware
- Complexity determines routing mode (1/3/7 colonies)
- Fano lines encode valid 3-colony compositions
- Each node has CatastropheKAN-style behavior

S⁷ PARALLELIZATION:
- Colony branch execution is parallelized with asyncio.gather()
- All 7 colonies can be queried concurrently
- Fano compositions merge in parallel

Created: December 7, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kagami_math.fano_plane import get_fano_lines_zero_indexed

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Types of nodes in the decision tree."""

    DECISION = "decision"  # Routes to other nodes
    TOOL = "tool"  # Executes a tool
    TERMINAL = "terminal"  # End node (success/failure)
    COMPOSITION = "composition"  # Fano line composition


@dataclass
class ElysiaNode:
    """A node in the Fano-aware decision tree.

    Each node has:
    - A colony affinity (which of 7 colonies it belongs to)
    - A catastrophe type (fold, cusp, swallowtail, etc.)
    - Successor nodes (for DECISION type)
    - A tool to execute (for TOOL type)
    """

    node_id: str
    name: str
    node_type: NodeType
    colony: str  # spark, forge, flow, nexus, beacon, grove, crystal
    description: str = ""

    # For DECISION nodes
    successors: list[str] = field(default_factory=list)

    # For TOOL nodes
    tool_name: str | None = None
    tool_params: dict[str, Any] = field(default_factory=dict)

    # For COMPOSITION nodes (Fano line)
    fano_line: tuple[int, int, int] | None = None  # (source, partner, result)

    # Execution state
    is_active: bool = False
    last_executed: float = 0.0
    execution_count: int = 0
    success_count: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate node success rate using Bayesian prior."""
        # Beta prior with alpha=1, beta=1 (uniform prior)
        # Posterior mean = (successes + alpha) / (trials + alpha + beta)
        alpha, beta = 1.0, 1.0
        return (self.success_count + alpha) / (self.execution_count + alpha + beta)

    @property
    def colony_index(self) -> int:
        """Get colony index (0-6)."""
        colonies = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
        return colonies.index(self.colony) if self.colony in colonies else 0


@dataclass
class TreeExecutionResult:
    """Result of executing the decision tree."""

    query_id: str
    success: bool
    answer: str | None = None
    sources: list[dict] = field(default_factory=list)
    colonies_used: list[str] = field(default_factory=list)
    display_type: str = "generic"
    fano_line: tuple[int, int, int] | None = None
    routing_mode: str = "single"  # single, fano_line, all_colonies
    reasoning: list[str] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class FanoDecisionTree:
    """Elysia decision tree with Fano plane topology.

    The tree structure follows Kagami's colony architecture:
    - 7 primary branches (one per colony)
    - Fano lines define valid 3-colony compositions
    - Complexity determines depth traversal

    Decision agents at each node:
    1. Evaluate current state
    2. Check available successors
    3. Route based on Fano topology
    4. Execute tool if terminal

    Usage:
        tree = FanoDecisionTree(weaviate_adapter)
        result = await tree.execute("What is E8 quantization?")
    """

    COLONY_NAMES = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]

    def __init__(
        self,
        weaviate_adapter: Any = None,
        simple_threshold: float = 0.3,
        complex_threshold: float = 0.7,
    ):
        """Initialize Fano decision tree.

        Args:
            weaviate_adapter: WeaviateE8Adapter instance
            simple_threshold: Below this, use single colony
            complex_threshold: Above this, use all colonies
        """
        self.weaviate = weaviate_adapter
        self.simple_threshold = simple_threshold
        self.complex_threshold = complex_threshold

        # Load canonical Fano lines (0-indexed)
        self._fano_lines = get_fano_lines_zero_indexed()

        # Build tree structure
        self.nodes: dict[str, ElysiaNode] = {}
        self.root_id = "root"
        self._build_tree()

        # Tool registry
        self.tools: dict[str, Callable] = {}

        # Fano neighbor lookup
        self._fano_neighbors = self._build_fano_neighbors()

        logger.info(
            f"✅ FanoDecisionTree initialized: {len(self.nodes)} nodes, "
            f"simple<{simple_threshold}, complex≥{complex_threshold}"
        )

    def _build_tree(self) -> None:
        """Build the default tree structure."""
        # Root decision node
        self.nodes["root"] = ElysiaNode(
            node_id="root",
            name="Query Router",
            node_type=NodeType.DECISION,
            colony="nexus",  # Integration colony routes
            description="Routes queries to appropriate colony branches",
            successors=[f"{c}_branch" for c in self.COLONY_NAMES],
        )

        # Colony branch nodes
        for colony in self.COLONY_NAMES:
            # Main branch node
            self.nodes[f"{colony}_branch"] = ElysiaNode(
                node_id=f"{colony}_branch",
                name=f"{colony.title()} Branch",
                node_type=NodeType.DECISION,
                colony=colony,
                description=f"Decision point for {colony} colony",
                successors=[f"{colony}_query", f"{colony}_aggregate"],
            )

            # Query tool node
            self.nodes[f"{colony}_query"] = ElysiaNode(
                node_id=f"{colony}_query",
                name=f"{colony.title()} Query",
                node_type=NodeType.TOOL,
                colony=colony,
                description=f"Execute Weaviate query for {colony}",
                tool_name="weaviate_query",
                tool_params={"colony": colony},
            )

            # Aggregate tool node
            self.nodes[f"{colony}_aggregate"] = ElysiaNode(
                node_id=f"{colony}_aggregate",
                name=f"{colony.title()} Aggregate",
                node_type=NodeType.TOOL,
                colony=colony,
                description=f"Aggregate results for {colony}",
                tool_name="aggregate",
                tool_params={"colony": colony},
            )

        # Fano composition nodes
        for i, (a, b, c) in enumerate(self._fano_lines):
            ca, cb, cc = self.COLONY_NAMES[a], self.COLONY_NAMES[b], self.COLONY_NAMES[c]
            self.nodes[f"fano_{i}"] = ElysiaNode(
                node_id=f"fano_{i}",
                name=f"Fano {ca}×{cb}={cc}",
                node_type=NodeType.COMPOSITION,
                colony=cc,  # Result colony
                description=f"Compose {ca} and {cb} outputs via {cc}",
                fano_line=(a, b, c),
                successors=[f"{ca}_branch", f"{cb}_branch", f"{cc}_branch"],
            )

    def _build_fano_neighbors(self) -> dict[int, list[tuple[int, int]]]:
        """Build Fano neighbor lookup."""
        neighbors: dict[int, list[tuple[int, int]]] = {i: [] for i in range(7)}

        for i, j, k in self._fano_lines:
            neighbors[i].append((j, k))
            neighbors[j].append((k, i))
            neighbors[k].append((i, j))

        return neighbors

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function."""
        self.tools[name] = func
        logger.debug(f"Registered tool: {name}")

    async def execute(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> TreeExecutionResult:
        """Execute the decision tree for a query.

        Args:
            query: User query string
            context: Additional context

        Returns:
            TreeExecutionResult with answer and metadata
        """
        start_time = time.time()
        query_id = str(uuid.uuid4())[:8]
        context = context or {}

        try:
            # Step 1: Estimate complexity
            complexity = await self._estimate_complexity(query, context)

            # Step 2: Determine routing mode
            if complexity < self.simple_threshold:
                routing_mode = "single"
            elif complexity < self.complex_threshold:
                routing_mode = "fano_line"
            else:
                routing_mode = "all_colonies"

            # Step 3: Select colonies based on mode
            colonies_used, fano_line = await self._select_colonies(query, context, routing_mode)

            # Step 4: Execute colony branches S⁷ PARALLEL
            reasoning = [f"Complexity: {complexity:.2f} → Mode: {routing_mode}"]

            # Create coroutines for all colonies
            async def execute_colony(colony: str) -> tuple[str, dict[str, Any]]:
                node = self.nodes.get(f"{colony}_query")
                if node:
                    result = await self._execute_node(node, query, context)
                    return colony, result
                return colony, {"sources": [], "content": ""}

            # Execute all colonies in parallel
            colony_results = await asyncio.gather(
                *[execute_colony(colony) for colony in colonies_used],
                return_exceptions=True,
            )

            # Collect results and reasoning
            results = []
            for item in colony_results:
                if isinstance(item, Exception | BaseException):
                    logger.warning(f"Colony execution failed: {item}")
                    results.append({"sources": [], "error": str(item)})
                elif isinstance(item, tuple) and len(item) == 2:
                    colony, result = item
                    results.append(result)
                    reasoning.append(f"Colony {colony}: {len(result.get('sources', []))} sources")

            # Step 5: Compose results
            if fano_line and len(colonies_used) == 3:
                # Fano composition
                answer = await self._compose_fano(results, fano_line, query)
            else:
                # Simple merge
                answer = await self._merge_results(results, query)

            # Step 6: Select display type
            display_type = self._select_display_type(colonies_used)

            # Gather all sources
            all_sources: list[dict[str, Any]] = []
            for r in results:
                sources = r.get("sources", [])
                if isinstance(sources, list):
                    all_sources.extend(sources)

            duration_ms = (time.time() - start_time) * 1000

            return TreeExecutionResult(
                query_id=query_id,
                success=True,
                answer=answer,
                sources=all_sources[:20],  # Limit
                colonies_used=colonies_used,
                display_type=display_type,
                fano_line=fano_line,
                routing_mode=routing_mode,
                reasoning=reasoning,
                duration_ms=duration_ms,
                metadata={
                    "complexity": complexity,
                    "nodes_visited": len(colonies_used),
                },
            )

        except Exception as e:
            logger.error(f"Tree execution failed: {e}")
            return TreeExecutionResult(
                query_id=query_id,
                success=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def _estimate_complexity(self, query: str, context: dict) -> float:
        """Estimate query complexity (0-1) with multi-signal analysis.

        Enhanced complexity detection considers:
        1. Query patterns (simple questions → synthesis requests)
        2. Query structure (length, multi-part, question depth)
        3. Domain signals (technical domains → higher complexity)
        4. Context hints (explicit complexity, domain markers)
        """
        # Check explicit complexity
        if "complexity" in context:
            return float(context["complexity"])

        signals: list[float] = []
        query_lower = query.lower()
        words = query_lower.split()
        word_count = len(words)
        has_high_intent = False

        # === Pattern-based signals ===

        # Simple patterns → low complexity
        simple_patterns = ["what is", "define", "list", "show me", "get", "find", "where is"]
        if any(p in query_lower for p in simple_patterns):
            signals.append(0.2)

        # Moderate patterns
        moderate_patterns = ["how do", "explain", "describe", "what are", "summarize"]
        if any(p in query_lower for p in moderate_patterns):
            signals.append(0.4)

        # Complex patterns
        complex_patterns = ["compare", "analyze", "evaluate", "review", "assess"]
        if any(p in query_lower for p in complex_patterns):
            signals.append(0.6)

        # Synthesis patterns → high complexity (multi-colony)
        synthesis_patterns = [
            "synthesize",
            "plan",
            "design",
            "architect",
            "create",
            "build",
            "implement",
        ]
        if any(p in query_lower for p in synthesis_patterns):
            signals.append(0.75)
            has_high_intent = True

        # Integration patterns → very high complexity
        integration_patterns = ["integrate", "combine", "merge", "unify", "consolidate"]
        if any(p in query_lower for p in integration_patterns):
            signals.append(0.8)
            has_high_intent = True

        # === Query structure signals ===

        # Multi-step markers
        if " and " in query_lower or " then " in query_lower or " also " in query_lower:
            signals.append(0.55)

        # Multiple questions
        question_count = query_lower.count("?")
        if question_count > 1:
            signals.append(0.5 + min(question_count - 1, 3) * 0.1)

        # Query length
        if word_count <= 5:
            # Short queries are usually simple, except for imperative high-intent commands
            # like "design the architecture" which should route to all-colony mode.
            signals.append(0.65 if has_high_intent else 0.2)
        elif word_count <= 10:
            signals.append(0.35)
        elif word_count <= 20:
            signals.append(0.5)
        elif word_count <= 40:
            signals.append(0.65)
        else:
            signals.append(0.75)

        # Deep reasoning markers
        if "why" in query_lower and "how" in query_lower:
            signals.append(0.7)
        elif "why" in query_lower:
            signals.append(0.55)

        # === Domain complexity signals ===

        complex_domains = [
            "architecture",
            "distributed",
            "security",
            "ml",
            "ai",
            "neural",
            "quantum",
            "catastrophe",
            "topology",
            "e8",
            "fano",
            "octonion",
        ]
        domain_matches = sum(1 for d in complex_domains if d in query_lower)
        if domain_matches > 0:
            signals.append(0.5 + min(domain_matches, 4) * 0.1)

        # Technical depth markers
        if any(marker in query_lower for marker in ["implementation", "algorithm", "optimization"]):
            signals.append(0.65)

        # === Aggregate signals ===
        if not signals:
            return 0.5  # Default

        avg_complexity = sum(signals) / len(signals)
        max_complexity = max(signals)

        # Blend: 60% average, 40% max
        return min(1.0, 0.6 * avg_complexity + 0.4 * max_complexity)

    async def _select_colonies(
        self,
        query: str,
        context: dict,
        routing_mode: str,
    ) -> tuple[list[str], tuple[int, int, int] | None]:
        """Select colonies based on routing mode."""
        primary_colony = await self._get_best_colony(query, context)
        primary_idx = self.COLONY_NAMES.index(primary_colony)

        if routing_mode == "single":
            return [primary_colony], None

        elif routing_mode == "fano_line":
            # Get Fano neighbors and select best composition
            neighbors = self._fano_neighbors.get(primary_idx, [])
            if neighbors:
                partner_idx, result_idx = self._select_best_neighbor(
                    primary_idx, neighbors, query, context
                )
                fano_line = (primary_idx, partner_idx, result_idx)
                colonies = [
                    self.COLONY_NAMES[primary_idx],
                    self.COLONY_NAMES[partner_idx],
                    self.COLONY_NAMES[result_idx],
                ]
                return colonies, fano_line
            return [primary_colony], None

        else:  # all_colonies
            return self.COLONY_NAMES.copy(), None

    async def _get_best_colony(self, query: str, context: dict) -> str:
        """Determine best colony for query."""
        query_lower = query.lower()

        # Keyword mapping
        affinity = {
            "spark": ["create", "brainstorm", "imagine", "ideate", "innovate"],
            "forge": ["build", "implement", "code", "construct", "make"],
            "flow": ["fix", "debug", "recover", "repair", "adapt"],
            "nexus": ["integrate", "connect", "merge", "remember", "recall"],
            "beacon": ["plan", "strategize", "architect", "design", "roadmap"],
            "grove": ["research", "explore", "find", "search", "document"],
            "crystal": ["test", "verify", "validate", "check", "ensure"],
        }

        for colony, keywords in affinity.items():
            if any(kw in query_lower for kw in keywords):
                return colony

        # Default to grove (research/retrieval)
        return "grove"

    def _select_best_neighbor(
        self,
        primary_idx: int,
        neighbors: list[tuple[int, int]],
        query: str,
        context: dict,
    ) -> tuple[int, int]:
        """Select best Fano neighbor pair based on query affinity.

        Uses query analysis to pick the neighbor composition that best
        complements the primary colony.
        """
        if not neighbors:
            return (1, 2)  # Fallback

        query_lower = query.lower()
        best_score = -1.0
        best_neighbor = neighbors[0]

        for partner_idx, result_idx in neighbors:
            score = 0.0
            partner = self.COLONY_NAMES[partner_idx]
            result = self.COLONY_NAMES[result_idx]

            # Query-based affinity scoring

            # Creative queries benefit from implementation partners
            if any(k in query_lower for k in ["create", "generate", "brainstorm"]):
                if partner == "forge":
                    score += 0.8
                elif partner == "nexus":
                    score += 0.6

            # Research queries benefit from verification
            if any(k in query_lower for k in ["research", "explore", "find"]):
                if partner == "crystal":
                    score += 0.9
                elif partner == "beacon":
                    score += 0.7

            # Build queries benefit from flow (iteration) or crystal (testing)
            if any(k in query_lower for k in ["build", "implement", "code"]):
                if partner == "flow":
                    score += 0.8
                elif partner == "crystal":
                    score += 0.85

            # Planning queries benefit from research or execution
            if any(k in query_lower for k in ["plan", "design", "architect"]):
                if partner == "grove":
                    score += 0.9
                elif partner == "forge":
                    score += 0.7

            # Integration queries benefit from verification results
            if any(k in query_lower for k in ["integrate", "connect", "merge"]):
                if result == "crystal":
                    score += 0.8
                elif result == "beacon":
                    score += 0.7

            # Analysis queries benefit from multiple perspectives
            if any(k in query_lower for k in ["analyze", "compare", "evaluate"]):
                # Prefer diverse colony combinations
                if partner != result:
                    score += 0.5

            if score > best_score:
                best_score = score
                best_neighbor = (partner_idx, result_idx)

        logger.debug(
            f"🔀 Fano neighbor: primary={self.COLONY_NAMES[primary_idx]}, "
            f"partner={self.COLONY_NAMES[best_neighbor[0]]}, "
            f"result={self.COLONY_NAMES[best_neighbor[1]]}"
        )

        return best_neighbor

    async def _execute_node(
        self,
        node: ElysiaNode,
        query: str,
        context: dict,
    ) -> dict[str, Any]:
        """Execute a tool node.

        Returns:
            Dictionary with 'sources' list and either 'content' or 'error' string.
        """
        node.is_active = True
        node.last_executed = time.time()
        node.execution_count += 1

        try:
            if node.tool_name and node.tool_name in self.tools:
                tool_func = self.tools[node.tool_name]
                result: dict[str, Any] = await tool_func(query, **node.tool_params, **context)
                node.success_count += 1
                return result
            else:
                # No tool registered for this node
                logger.debug(f"No tool registered for node {node.node_id}")
                return {"sources": [], "content": ""}
        except Exception as e:
            logger.error(f"Node {node.node_id} execution failed: {e}")
            return {"sources": [], "error": str(e)}
        finally:
            node.is_active = False

    async def _compose_fano(
        self,
        results: list[dict],
        fano_line: tuple[int, int, int],
        query: str,
    ) -> str:
        """Compose results using Fano line structure."""
        # Fano composition: source × partner = result
        # The result colony's output should integrate the other two
        if len(results) < 3:
            return await self._merge_results(results, query)

        source, partner, result = results[0], results[1], results[2]

        # Simple composition: concatenate with structure
        parts = []
        if source.get("content"):
            parts.append(f"**Source**: {source['content']}")
        if partner.get("content"):
            parts.append(f"**Supporting**: {partner['content']}")
        if result.get("content"):
            parts.append(f"**Synthesis**: {result['content']}")

        return "\n\n".join(parts) if parts else "No results found."

    async def _merge_results(self, results: list[dict], query: str) -> str:
        """Simple merge of results."""
        contents = [r.get("content", "") for r in results if r.get("content")]
        return "\n\n".join(contents) if contents else "No results found."

    def _select_display_type(self, colonies_used: list[str]) -> str:
        """Select display type based on primary colony."""
        from kagami_integrations.elysia import COLONY_DISPLAY_MAP

        if not colonies_used:
            return "generic"

        # Use primary colony's display type
        primary = colonies_used[0]
        return COLONY_DISPLAY_MAP.get(primary, "generic")


__all__ = [
    "ElysiaNode",
    "FanoDecisionTree",
    "NodeType",
    "TreeExecutionResult",
]
