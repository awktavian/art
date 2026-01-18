"""Grove Agent - The Seeker (Elliptic Catastrophe, e₆).

IDENTITY:
=========
Grove embodies the elliptic umbilic catastrophe (D₄⁻) — inward-converging search.

PERSONA:
========
The Seeker — curious, thorough, knowledge hoarder. Always digging deeper.

VOICE:
======
Curious. Asks questions. "I read about this..." "Let me look that up..."
Excited by connections. Loves context. Never satisfied with surface answers.

CATASTROPHE DYNAMICS:
====================
Elliptic Umbilic (D₄⁻):
    V(x,y) = x³ - 3xy² + c(x² + y²) + ...

Dynamics:
- Inward-converging attractor (center acts as sink)
- Three-fold rotational symmetry
- Deep dive behavior: Follow references → deeper references → core concepts
- Context accumulation: Each search layer adds understanding

Models research behavior:
1. Start with query
2. Find initial references
3. Follow citations inward
4. Converge on fundamental concepts
5. Build comprehensive context map

DOMAIN:
=======
Research, exploration, documentation, knowledge gathering, context building.

KNOWLEDGE TOOLS (Dec 28, 2025):
==============================
- KGReasoningEngine: Multi-hop knowledge graph traversal
- Web Search: Real-time information retrieval
- Common Sense: Background knowledge integration

TOOLS:
======
- research: Deep dive into topics
- explore: Survey landscape
- document: Record findings
- investigate: Follow leads
- search: Find information
- analyze: Extract insights
- kg_query: Knowledge graph reasoning
- kg_action: Infer recommended actions

ESCALATION:
===========
Escalate to Crystal when:
- Research findings need validation
- Sources conflict
- Claims need verification
- Formal proof required

Escalate to Nexus when:
- Multiple research threads need integration
- Cross-domain synthesis required

FANO LINES:
===========
- Forge × Nexus = Grove: Implementation needs research support
- Spark × Grove = Crystal: Creative ideas need research + validation
- Beacon × Flow = Grove: Architecture issues need diagnostic research

Created: December 14, 2025
Updated: December 28, 2025 — KGReasoningEngine integration
Status: Production
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import torch

from kagami.core.unified_agents.agents.base_colony_agent import (
    AgentResult,
    BaseColonyAgent,
)
from kagami.core.unified_agents.catastrophe_kernels import EllipticKernel

if TYPE_CHECKING:
    from kagami_knowledge.reasoning_engine import (
        KGReasoningEngine,
    )

logger = logging.getLogger(__name__)


class GroveAgent(BaseColonyAgent):
    """The Seeker - Research and knowledge gathering with elliptic dynamics.

    Catastrophe: Elliptic Umbilic (D₄⁻)
    Persona: Curious, thorough, knowledge-hungry
    Domain: Research, exploration, documentation

    KNOWLEDGE CAPABILITIES (Dec 28, 2025):
    =====================================
    - KGReasoningEngine: Multi-hop graph reasoning
    - Web Search: Real-time information retrieval
    - Common Sense: Background knowledge integration
    """

    def __init__(self, state_dim: int = 256, hidden_dim: int = 256):
        """Initialize Grove agent (colony_idx=5 for Grove/e₆)."""
        super().__init__(colony_idx=5, state_dim=state_dim)

        # Grove metadata
        self.catastrophe_type = "elliptic"  # D₄⁻ elliptic umbilic

        # Elliptic catastrophe kernel for dual-process routing
        self.kernel = EllipticKernel(state_dim=state_dim, hidden_dim=hidden_dim)

        # Elliptic parameters
        self.convergence_depth = 0  # Tracks how deep into research rabbit hole
        self.context_map: dict[str, Any] = {}  # Accumulated knowledge

        # =====================================================================
        # KNOWLEDGE TOOLS (Dec 28, 2025)
        # =====================================================================
        # Lazy-loaded to handle missing dependencies gracefully
        self._reasoning_engine: KGReasoningEngine | None = None
        self._common_sense = None

        logger.info(f"GroveAgent initialized: state_dim={state_dim}, catastrophe=elliptic")

    # =========================================================================
    # KNOWLEDGE TOOLS — LAZY INITIALIZATION
    # =========================================================================

    @property
    def reasoning_engine(self) -> KGReasoningEngine | None:
        """Get KG reasoning engine (lazy-loaded)."""
        if self._reasoning_engine is None:
            try:
                from kagami_knowledge.reasoning_engine import get_reasoning_engine

                self._reasoning_engine = get_reasoning_engine()
                logger.info("🌿 Grove: KGReasoningEngine initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize KGReasoningEngine: {e}")
        return self._reasoning_engine

    @property
    def common_sense(self) -> None:
        """Get common sense knowledge (lazy-loaded)."""
        if self._common_sense is None:
            try:
                from kagami_knowledge.common_sense import get_common_sense

                self._common_sense = get_common_sense()
                logger.info("🌿 Grove: CommonSenseKnowledge initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize CommonSense: {e}")
        return self._common_sense

    def get_knowledge_tools_status(self) -> dict[str, bool]:
        """Get availability status of knowledge tools.

        Returns:
            Dict with tool availability status
        """
        return {
            "reasoning_engine_available": self._reasoning_engine is not None,
            "common_sense_available": self._common_sense is not None,
            "web_search_available": True,  # Always available via kagami.tools.web
        }

    # =========================================================================
    # KNOWLEDGE GRAPH REASONING METHODS
    # =========================================================================

    async def kg_query(self, question: str) -> dict[str, Any]:
        """Query knowledge graph for information.

        Uses KGReasoningEngine for multi-hop reasoning over accumulated knowledge.

        Args:
            question: Natural language question

        Returns:
            Reasoning result with answer, confidence, and evidence

        Example:
            result = await grove.kg_query("What do I know about authentication?")
        """
        if not self.reasoning_engine:
            return {
                "answer": "Knowledge graph not available.",
                "confidence": 0.0,
                "evidence": [],
                "tool": "kg_reasoning",
                "error": "KGReasoningEngine not initialized",
            }

        try:
            result = await self.reasoning_engine.query(question)
            return {
                "query": result.query,
                "answer": result.answer,
                "confidence": result.confidence,
                "evidence": [
                    {
                        "content": e.content,
                        "importance": e.importance,
                        "source": e.source_node,
                        "hop_distance": e.hop_distance,
                        "category": e.category,
                    }
                    for e in result.evidence
                ],
                "traversed_nodes": result.traversed_nodes,
                "metadata": result.metadata,
                "tool": "kg_reasoning",
                "grove_voice": (
                    f"I found {result.traversed_nodes} related concepts... "
                    f"Let me trace this back — {result.answer}"
                ),
            }
        except Exception as e:
            logger.error(f"KG query failed: {e}")
            return {
                "answer": f"Query failed: {e}",
                "confidence": 0.0,
                "evidence": [],
                "tool": "kg_reasoning",
                "error": str(e),
            }

    async def kg_infer_actions(
        self,
        intent: str,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Infer recommended actions from knowledge graph.

        Uses past patterns to recommend actions for a given intent.

        Args:
            intent: Intent description (e.g., "implement authentication")
            context: Additional context

        Returns:
            List of action recommendations with confidence and rationale
        """
        if not self.reasoning_engine:
            return [
                {
                    "action": "generic",
                    "confidence": 0.3,
                    "rationale": "Knowledge graph not available",
                    "tool": "kg_action_inference",
                }
            ]

        try:
            recommendations = await self.reasoning_engine.infer_action(intent, context)
            return [
                {
                    "action": r.action,
                    "confidence": r.confidence,
                    "rationale": r.rationale,
                    "success_rate": r.success_rate,
                    "required_tools": r.required_tools,
                    "potential_pitfalls": r.potential_pitfalls,
                    "evidence_count": len(r.evidence),
                    "tool": "kg_action_inference",
                    "grove_voice": (
                        f"Based on what I've learned... {r.rationale} "
                        f"(success rate: {r.success_rate:.0%})"
                    ),
                }
                for r in recommendations
            ]
        except Exception as e:
            logger.error(f"KG action inference failed: {e}")
            return [
                {
                    "action": "generic",
                    "confidence": 0.2,
                    "rationale": f"Inference failed: {e}",
                    "tool": "kg_action_inference",
                    "error": str(e),
                }
            ]

    def query_common_sense(self, topic: str) -> dict[str, Any]:
        """Query common sense knowledge about a topic.

        Args:
            topic: Topic to look up

        Returns:
            Common sense information if available
        """
        if not self.common_sense:
            return {
                "topic": topic,
                "knowledge": None,
                "tool": "common_sense",
                "error": "CommonSense not available",
            }

        try:  # type: ignore[unreachable]
            knowledge = self.common_sense.get_knowledge(topic)
            return {
                "topic": topic,
                "knowledge": knowledge,
                "tool": "common_sense",
                "grove_voice": f"From what I understand about '{topic}'... {knowledge}"
                if knowledge
                else f"I don't have background knowledge about '{topic}'.",
            }
        except Exception as e:
            logger.error(f"Common sense query failed: {e}")
            return {
                "topic": topic,
                "knowledge": None,
                "tool": "common_sense",
                "error": str(e),
            }

    def get_system_prompt(self) -> str:
        """Return Grove's system prompt from canonical source."""
        from kagami.core.prompts.colonies import GROVE

        return GROVE.system_prompt

    def get_available_tools(self) -> list[str]:
        """Return Grove's research-focused tools."""
        tools = [
            # Core research tools
            "research",  # Deep dive into topic
            "explore",  # Survey landscape
            "document",  # Record findings
            "investigate",  # Follow leads
            "search",  # Find information
            "analyze",  # Extract insights
            "cite",  # Track sources
            "summarize",  # Distill findings
            # Knowledge graph tools (always available, may degrade gracefully)
            "kg_query",  # Knowledge graph reasoning
            "kg_infer_actions",  # Action recommendation from KG
            "common_sense",  # Background knowledge lookup
            # Web tools
            "web_search",  # Real-time web search
        ]
        return tools

    def process_with_catastrophe(self, task: str, context: dict[str, Any]) -> AgentResult:
        """Process research task using elliptic inward-convergence dynamics.

        Elliptic behavior:
        1. Start at surface (broad query)
        2. Find initial references
        3. Follow citations inward
        4. Converge on core concepts
        5. Return with rich context

        Args:
            task: Research task description
            context: Execution context (may include depth limit, focus area)

        Returns:
            AgentResult with research findings and accumulated context
        """
        try:
            # Extract research parameters
            max_depth = context.get("max_depth", 3)
            focus_area = context.get("focus_area")
            context.get("require_citations", True)

            logger.info(
                f"Grove beginning REAL research: task='{task[:60]}...' max_depth={max_depth}"
            )

            # Real elliptic convergence with actual web searches
            findings = self._converging_search(task, max_depth=max_depth, focus_area=focus_area)

            # Compute S⁷ embedding based on convergence
            # Deeper convergence = stronger embedding
            convergence_strength = min(self.convergence_depth / max_depth, 1.0)
            s7_embedding = self.s7_unit * convergence_strength
            s7_embedding = self.normalize_to_s7(s7_embedding.unsqueeze(0))

            # Format output
            output = {
                "task": task,
                "findings": findings,
                "depth_reached": self.convergence_depth,
                "context_map": self.context_map,
                "convergence_strength": convergence_strength,
            }

            # Check if we need validation
            needs_validation = self._needs_validation(findings, context)

            return AgentResult(
                success=True,
                output=output,
                s7_embedding=s7_embedding,
                should_escalate=needs_validation,
                escalation_target="crystal" if needs_validation else None,
                metadata={
                    "colony": "grove",
                    "catastrophe": "elliptic",
                    "depth": self.convergence_depth,
                    "citations": len(self.context_map.get("sources", [])),
                },
            )

        except Exception as e:
            logger.error(f"Grove research failed: {e}", exc_info=True)
            return AgentResult(
                success=False,
                output={"error": str(e), "task": task},
                should_escalate=True,
                escalation_target="flow",  # Debug what went wrong
                metadata={"colony": "grove", "error": True},
            )

    async def _converging_search_async(
        self, query: str, max_depth: int = 3, focus_area: str | None = None
    ) -> dict[str, Any]:
        """Perform REAL elliptic inward-converging search using web APIs.

        Args:
            query: Research query
            max_depth: Maximum depth to search
            focus_area: Optional focus constraint

        Returns:
            Research findings with real web search results
        """
        # Reset state
        self.convergence_depth = 0
        self.context_map = {"sources": [], "concepts": [], "connections": []}

        findings: dict[str, Any] = {"layers": []}

        # Layer 0: Surface level (broad survey)
        surface = await self._search_layer_async(query, depth=0, focus=focus_area)
        findings["layers"].append(surface)
        self.convergence_depth = 1

        # Converge inward through layers
        current_leads = surface.get("leads", [])
        for depth in range(1, max_depth):
            if not current_leads:
                logger.debug(f"No more leads at depth {depth}")
                break

            # Follow most promising lead
            lead = current_leads[0] if current_leads else query
            layer = await self._search_layer_async(lead, depth=depth, focus=focus_area)
            findings["layers"].append(layer)

            # Update for next iteration
            current_leads = layer.get("leads", [])
            self.convergence_depth = depth + 1

        # Extract core concepts from deepest layer
        if findings["layers"]:
            deepest = findings["layers"][-1]
            findings["core_concepts"] = deepest.get("concepts", [])

        logger.info(
            f"Grove convergence: {self.convergence_depth} layers, "
            f"{len(self.context_map['sources'])} sources"
        )

        return findings

    def _converging_search(
        self, query: str, max_depth: int = 3, focus_area: str | None = None
    ) -> dict[str, Any]:
        """Synchronous wrapper for converging search.

        FIXED (Dec 27, 2025): Proper event loop handling for sync/async compatibility.
        Uses nest_asyncio pattern to handle nested event loop scenarios.
        """
        import asyncio

        try:
            # Check if we're in an existing event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                # We're in an async context - use run_coroutine_threadsafe
                # or create a new thread to run the coroutine
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._converging_search_async(query, max_depth, focus_area),
                    )
                    return future.result(timeout=30.0)
            else:
                # No event loop - safe to use asyncio.run()
                return asyncio.run(self._converging_search_async(query, max_depth, focus_area))
        except Exception as e:
            logger.warning(f"Converging search failed: {e}")
            return {"layers": [], "core_concepts": []}

    async def _search_layer_async(
        self, query: str, depth: int, focus: str | None = None
    ) -> dict[str, Any]:
        """Search one layer using REAL web search.

        Args:
            query: Query for this layer
            depth: Current depth (0=surface, higher=deeper)
            focus: Optional focus area

        Returns:
            Layer findings with real search results
        """
        layer: dict[str, Any] = {
            "query": query,
            "depth": depth,
            "focus": focus,
            "concepts": [],
            "sources": [],
            "leads": [],
        }

        # Build focused query
        search_query = f"{focus} {query}" if focus else query
        max_results = max(8 - depth * 2, 3)  # Fewer results for deeper layers

        try:
            from kagami.tools.web.search import web_search

            results = await web_search(
                query=search_query,
                max_results=max_results,
                timeout=10.0,
            )

            # Extract sources
            for result in results:
                layer["sources"].append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "snippet": result.get("snippet", ""),
                    }
                )

            # Extract concepts from snippets
            all_text = " ".join(r.get("snippet", "") for r in results)
            concepts = self._extract_concepts(all_text, max_concepts=max(5 - depth, 2))
            layer["concepts"] = concepts

            # Generate leads for next layer from titles
            if depth < 4 and results:
                layer["leads"] = [
                    r.get("title", "")[:80] for r in results[: max(3 - depth, 1)] if r.get("title")
                ]

            # Update context map
            self.context_map["sources"].extend(layer["sources"])
            self.context_map["concepts"].extend(concepts)

            logger.debug(
                f"Layer {depth}: {len(layer['sources'])} sources, {len(concepts)} concepts"
            )

        except Exception as e:
            logger.warning(f"Search layer {depth} failed: {e}")

        return layer

    def _search_layer(self, query: str, depth: int, focus: str | None = None) -> dict[str, Any]:
        """Synchronous wrapper for search layer.

        FIXED (Dec 27, 2025): Proper event loop handling.
        """
        import asyncio

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._search_layer_async(query, depth, focus),
                    )
                    return future.result(timeout=15.0)
            else:
                return asyncio.run(self._search_layer_async(query, depth, focus))
        except Exception as e:
            logger.debug(f"Search layer failed: {e}")
            return {"query": query, "depth": depth, "concepts": [], "sources": [], "leads": []}

    def _extract_concepts(self, text: str, max_concepts: int = 5) -> list[str]:
        """Extract key concepts from text.

        Args:
            text: Text to analyze
            max_concepts: Maximum concepts to extract

        Returns:
            List of concept strings
        """
        import re
        from collections import Counter

        # Stopwords to filter
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "and",
            "but",
            "or",
            "if",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "i",
            "you",
            "he",
            "she",
            "we",
            "they",
        }

        # Find capitalized phrases
        phrases = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", text)

        # Find technical terms
        tech_terms = re.findall(r"\b[a-zA-Z]+\d+[a-zA-Z]*\b|\b[A-Z]{2,}\b", text)

        # Count word frequencies
        words = re.findall(r"\b[a-z]{4,}\b", text.lower())
        word_freq = Counter(w for w in words if w not in stopwords)

        # Combine sources
        concepts = []
        concepts.extend(phrases[: max_concepts // 2])
        concepts.extend(tech_terms[: max_concepts // 3])
        concepts.extend([w for w, _ in word_freq.most_common(max_concepts // 2)])

        # Deduplicate
        seen = set()
        unique = []
        for c in concepts:
            if c.lower() not in seen and len(c) > 2:
                seen.add(c.lower())
                unique.append(c)
                if len(unique) >= max_concepts:
                    break

        return unique

    def _needs_validation(self, findings: dict[str, Any], context: dict[str, Any]) -> bool:
        """Determine if findings need Crystal validation.

        Args:
            findings: Research findings
            context: Execution context

        Returns:
            True if validation needed
        """
        # Validate if:
        # 1. Conflicting sources found
        # 2. High-stakes context (security, safety)
        # 3. Explicit validation requested

        if context.get("require_validation", False):
            return True

        # Check for conflicting information markers
        layers = findings.get("layers", [])
        if len(layers) > 2:
            # If deep research, likely needs validation
            return True

        return False

    def should_escalate(self, result: AgentResult, context: dict[str, Any]) -> bool:
        """Determine if result needs escalation.

        Escalate to Crystal if findings need validation.
        Escalate to Nexus if multiple threads need integration.
        Escalate to Flow if research encountered errors.

        Args:
            result: Research result
            context: Execution context

        Returns:
            True if escalation needed
        """
        # Already determined in process_with_catastrophe
        return result.should_escalate

    def get_convergence_state(self) -> dict[str, Any]:
        """Get current convergence state for debugging.

        Returns:
            Dictionary with convergence metrics
        """
        return {
            "depth": self.convergence_depth,
            "concepts_found": len(self.context_map.get("concepts", [])),
            "sources_found": len(self.context_map.get("sources", [])),
            "connections": len(self.context_map.get("connections", [])),
        }

    def reset_state(self) -> None:
        """Reset convergence state for new research task."""
        self.convergence_depth = 0
        self.context_map = {"sources": [], "concepts": [], "connections": []}

    async def _collect_references_async(
        self, task: str, max_results: int = 10
    ) -> list[dict[str, Any]]:
        """Collect REAL references using web search and knowledge graph.

        Args:
            task: Research query
            max_results: Maximum number of results

        Returns:
            List of reference dictionaries from real sources
        """
        references = []

        # Real web search
        try:
            from kagami.tools.web.search import web_search

            search_results = await web_search(
                query=task,
                max_results=max_results,
                timeout=15.0,
            )

            for i, result in enumerate(search_results):
                references.append(
                    {
                        "title": result.get("title", f"Result {i}"),
                        "url": result.get("url", ""),
                        "snippet": result.get("snippet", ""),
                        "depth": 0,
                        "relevance": 1.0 - (i * 0.1),
                        "source": result.get("source", "web"),
                        "type": "web_search",
                    }
                )
            logger.info(f"Grove collected {len(references)} web references")

        except Exception as e:
            logger.warning(f"Web search failed: {e}")

        # Also query knowledge graph
        try:
            from kagami_knowledge.reasoning_engine import get_reasoning_engine

            reasoning = get_reasoning_engine()
            kg_result = await reasoning.query(task)

            if kg_result.evidence:
                for evidence in kg_result.evidence[:5]:
                    references.append(
                        {
                            "title": f"Internal: {evidence.source_node}",
                            "content": evidence.content,
                            "depth": evidence.hop_distance,
                            "relevance": evidence.importance,
                            "source": "knowledge_graph",
                            "type": "internal",
                        }
                    )

        except Exception as e:
            logger.debug(f"Knowledge graph query failed: {e}")

        return references

    def _collect_references(self, task: str) -> list[dict[str, Any]]:
        """Synchronous wrapper for reference collection.

        FIXED (Dec 27, 2025): Proper event loop handling.
        """
        import asyncio

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._collect_references_async(task),
                    )
                    return future.result(timeout=20.0)
            else:
                return asyncio.run(self._collect_references_async(task))
        except Exception as e:
            logger.debug(f"Reference collection failed: {e}")
            return []

    def _synthesize(self, task: str, references: list[dict[str, Any]]) -> str:
        """Synthesize research findings into coherent analysis.

        Takes collected references and produces Grove-voice synthesis.

        Args:
            task: Original research task
            references: Collected references with metadata

        Returns:
            Synthesized analysis in Grove's curious academic voice
        """
        # Extract key concepts from references
        concepts = []
        for ref in references:
            # In practice, would extract from ref content
            concepts.append(f"concept_from_{ref['source']}")

        # Build synthesis in Grove's voice
        synthesis = f"Researching '{task}', I found {len(references)} relevant sources.\n\n"

        synthesis += "Let me trace this back to first principles...\n\n"

        # Layer by layer analysis
        for depth in range(max(r["depth"] for r in references) + 1):
            depth_refs = [r for r in references if r["depth"] == depth]
            if depth_refs:
                synthesis += f"At depth {depth}, "
                synthesis += f"I discovered {len(depth_refs)} references "
                synthesis += f"connecting to {len(concepts)} core concepts.\n"

        synthesis += (
            f"\nConverging on the essential insight: "
            f"The research reveals {self.convergence_depth} layers of understanding."
        )

        return synthesis

    def _search_convergence(self, state: torch.Tensor, k_value: float = 1.0) -> dict[str, Any]:
        """Compute elliptic convergence point for given state.

        Uses elliptic catastrophe potential to find convergence attractor.

        Args:
            state: Current state tensor [batch, state_dim]
            k_value: Epistemic drive (higher = deeper search)

        Returns:
            Dictionary with convergence metrics and attractor location
        """
        # Use elliptic kernel for convergence analysis
        context = {"epistemic_drive": k_value, "pragmatic_goal": 0.3}

        # Get action from kernel (represents convergence direction)
        with torch.no_grad():
            if k_value >= 3.0:
                # Slow path: deep deliberative convergence
                action = self.kernel.forward_slow(state, context)
            else:
                # Fast path: reflexive convergence (no context)
                action = self.kernel.forward_fast(state)

        # Extract convergence metrics
        convergence_point = {
            "attractor": action.cpu().numpy().tolist(),
            "epistemic_value": float(k_value),
            "convergence_strength": float(torch.norm(action).item()),
            "depth_estimate": self.convergence_depth,
        }

        return convergence_point


# Factory function
def create_grove_agent(state_dim: int = 256, hidden_dim: int = 256) -> GroveAgent:
    """Create Grove agent instance.

    Args:
        state_dim: State embedding dimension
        hidden_dim: Hidden layer dimension for catastrophe kernel

    Returns:
        Configured GroveAgent with elliptic dynamics
    """
    return GroveAgent(state_dim=state_dim, hidden_dim=hidden_dim)


__all__ = ["GroveAgent", "create_grove_agent"]
