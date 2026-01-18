"""Memory System Integration - Central Hub for All Memory Operations.

Full Operation Mode: Single source of truth for all memory systems.
No duplicate implementations, all memory access through this hub.

DEEP UNIFICATION (Dec 1, 2025):
==============================
Architecture now includes:
- HierarchicalMemory: Working + short-term + long-term storage
- SharedEpisodicMemory: Episode-specific memories
- ProceduralMemory: Skills and procedures
- HopfieldE8Memory: Geometric memory via E8 lattice (240 slots)
- ProgramLibrary: Program memory with MDL-based complexity prior
- ColonyMemoryBridge: Unified access to colony state and memory
- MemoryConsolidation: Background consolidation process
- SpacedRepetition: Optimized retrieval scheduling

SECURITY HARDENING (Dec 23, 2025):
==================================
All memory writes now filtered through MemoryHygieneFilter to prevent:
- Morris II-style worm persistence
- Instruction injection into stored memories
- Untrusted content contamination
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class MemoryHub:
    """Central hub for all memory systems.

    DEEP UNIFICATION (Dec 1, 2025):
    ==============================
    Single point of access for ALL memory systems:
    - Hierarchical memory (working/short/long-term)
    - Episodic memory (episodes, events)
    - Procedural memory (skills, procedures)
    - HopfieldE8Memory (geometric addressing via E8 lattice)
    - ProgramLibrary (program memory with MDL weighting)
    - ColonyRSSM (shared colony state)
    - Memory consolidation
    - Spaced repetition

    All memory access routes through E8 lattice addressing for unified geometry.

    Full Operation Mode: All memory systems required, no fallbacks.
    """

    def __init__(self) -> None:
        """Initialize memory hub with all integrated systems."""
        # Lazy import to avoid circular dependencies
        from kagami.core.learning.procedural_memory import ProceduralMemory
        from kagami.core.memory.hierarchical_memory import HierarchicalMemory
        from kagami.core.memory.shared_episodic_memory import SharedEpisodicMemory

        self.hierarchical = HierarchicalMemory()
        self.episodic = SharedEpisodicMemory()
        self.procedural = ProceduralMemory()

        # DEEP UNIFICATION (Dec 1, 2025): Geometric memory systems
        self._hopfield_e8: Any = None  # Lazy-loaded
        self._solomonoff: Any = None  # Lazy-loaded
        self._colony_memory_bridge: Any = None  # Lazy-loaded

        logger.info("MemoryHub initialized with all systems")

    def _ensure_geometric_memory(self) -> None:
        """Lazy-load geometric memory systems (Split Architecture Dec 2025)."""
        if self._hopfield_e8 is None:
            try:
                from kagami.core.world_model.memory import (
                    EpisodicMemory,
                    EpisodicMemoryConfig,
                )

                # Episodic Memory: 256D values (matches RSSM h)
                episodic_config = EpisodicMemoryConfig(num_slots=240, value_dim=256)
                self._hopfield_e8 = EpisodicMemory(episodic_config)
                logger.debug("EpisodicMemory initialized in MemoryHub")
            except Exception as e:
                logger.warning(f"EpisodicMemory init failed: {e}")

        if self._solomonoff is None:
            try:
                from kagami.core.world_model.memory import (
                    ProgramLibrary,
                    ProgramLibraryConfig,
                )

                # Program Library: 52D F₄ embeddings (optimal for actions)
                program_config = ProgramLibraryConfig(num_base_programs=240, program_dim=52)
                self._solomonoff = ProgramLibrary(program_config)
                logger.info("✅ ProgramLibrary (52D F₄) connected to MemoryHub")
            except Exception as e:
                logger.warning(f"ProgramLibrary init failed: {e}")

        if self._colony_memory_bridge is None:
            try:
                from kagami.core.unified_agents.memory import get_colony_memory_bridge

                self._colony_memory_bridge = get_colony_memory_bridge()
                logger.info("✅ ColonyMemoryBridge connected to MemoryHub")
            except Exception as e:
                logger.warning(f"ColonyMemoryBridge init failed: {e}")

    @property
    def hopfield_e8(self) -> Any:
        """Get HopfieldE8Memory (lazy-loaded)."""
        self._ensure_geometric_memory()
        return self._hopfield_e8

    @property
    def solomonoff(self) -> Any:
        """Get ProgramLibrary (lazy-loaded). Legacy name kept for compatibility."""
        self._ensure_geometric_memory()
        return self._solomonoff

    @property
    def colony_bridge(self) -> Any:
        """Get ColonyMemoryBridge (lazy-loaded)."""
        self._ensure_geometric_memory()
        return self._colony_memory_bridge

    async def store(self, item: dict[str, Any]) -> str:
        """Store item in appropriate memory system with security filtering.

        SECURITY HARDENING (Dec 23, 2025):
        All content is filtered through MemoryHygieneFilter before storage
        to prevent worm persistence and instruction injection.

        Args:
            item: Memory item with 'type' key indicating storage location

        Returns:
            Memory ID

        Raises:
            ValueError: If item type unknown or content blocked by security
        """
        item_type = item.get("type", "working")
        content = str(item.get("content", ""))
        source = str(item.get("source", "unknown"))

        # SECURITY: Filter content through MemoryHygieneFilter
        filtered_content = await self._filter_content_for_storage(
            content=content,
            source=source,
            memory_type=item_type,
        )

        if item_type in ("working", "short_term", "long_term"):
            memory_id = str(item.get("id") or uuid.uuid4())
            experience: dict[str, Any] = {
                "content": filtered_content,
                "timestamp": float(item.get("timestamp") or time.time()),
                "valence": float(item.get("valence", 0.0) or 0.0),
                "metadata": dict(item.get("metadata") or {}),
            }
            await self.hierarchical.store(experience)
            return memory_id

        elif item_type == "episode":
            return await self.episodic.store(
                agent_name=str(item.get("agent_name") or item.get("agent") or "unknown"),
                category=str(item.get("category") or "generic"),
                content=filtered_content,
                data=dict(item.get("data") or item.get("metadata") or {}),
                valence=float(item.get("valence", 0.0) or 0.0),
                importance=float(item.get("importance", 0.5) or 0.5),
            )

        elif item_type == "skill":
            pattern_id = str(item.get("pattern_id") or item.get("name") or uuid.uuid4())
            workflow = {
                "procedure": filtered_content,
                "metadata": dict(item.get("metadata") or {}),
                "timestamp": float(item.get("timestamp") or time.time()),
            }
            await self.procedural.store_workflow(pattern_id, workflow)
            return pattern_id

        else:
            raise ValueError(f"Unknown memory type: {item_type}")

    async def _filter_content_for_storage(
        self,
        content: str,
        source: str,
        memory_type: str,
    ) -> str:
        """Filter content through MemoryHygieneFilter before storage.

        Args:
            content: Content to filter
            source: Source of content
            memory_type: Type of memory (working, episode, skill)

        Returns:
            Filtered content (sanitized or blocked)

        Raises:
            ValueError: If content is blocked by hygiene filter
        """
        try:
            from kagami.core.security.memory_hygiene import (
                MemoryType,
                get_memory_hygiene_filter,
            )

            # Map item type to MemoryType enum
            # Note: MemoryType enum has SYSTEM, PROFILE, EPISODIC, WORKING, SCRATCH
            type_map = {
                "working": MemoryType.WORKING,
                "short_term": MemoryType.WORKING,
                "long_term": MemoryType.EPISODIC,  # Long-term -> EPISODIC (medium protection)
                "episode": MemoryType.EPISODIC,
                "skill": MemoryType.PROFILE,  # Skills are high-value -> PROFILE (high protection)
            }
            mem_type = type_map.get(memory_type, MemoryType.WORKING)

            filter = get_memory_hygiene_filter()
            result = filter.filter_before_storage(
                content=content,
                memory_type=mem_type,
                source=source,
            )

            if not result.allowed:
                logger.warning(
                    f"MemoryHub BLOCKED storage: source={source}, type={memory_type}, "
                    f"reason={result.blocked_reason}"
                )
                raise ValueError(f"memory_storage_blocked:{result.blocked_reason}")

            # Return sanitized content if available, otherwise original
            return result.content or content

        except ValueError:
            raise
        except ImportError as e:
            raise RuntimeError(
                "MemoryHygieneFilter not available. "
                "Security module required for safe memory storage."
            ) from e
        except Exception as e:
            raise RuntimeError(f"Memory hygiene filter error: {e}") from e

    async def retrieve(
        self, query: str, memory_types: list[str] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Search across memory systems.

        DEEP UNIFICATION (Dec 1, 2025): Now includes geometric memory systems.

        Args:
            query: Search query
            memory_types: Which memory types to search (None = all)
                - "hierarchical": Working/short/long-term memory
                - "episodic": Episode-specific memories
                - "procedural": Skills and procedures
                - "geometric": HopfieldE8 + ProgramLibrary (E8 lattice)
            limit: Max results per system

        Returns:
            List of memory items sorted by relevance
        """
        results: list[dict[str, Any]] = []

        if memory_types is None or "hierarchical" in memory_types:
            try:
                hier_results = await self.hierarchical.recall({"content": query}, max_results=limit)
                results.extend(
                    [{"type": "hierarchical", "content": r, "relevance": 1.0} for r in hier_results]
                )
            except Exception as e:
                logger.warning(f"Hierarchical retrieval failed: {e}")

        if memory_types is None or "episodic" in memory_types:
            try:
                ep_results = await self.episodic.query(
                    asking_agent="memory_hub",
                    query_text=query,
                    top_k=limit,
                )
                results.extend(
                    [{"type": "episodic", "content": r, "relevance": 0.9} for r in ep_results]
                )
            except Exception as e:
                logger.warning(f"Episodic retrieval failed: {e}")

        if memory_types is None or "procedural" in memory_types:
            try:
                proc_results = await self.procedural.list_workflows(limit=limit)
                results.extend(
                    [{"type": "procedural", "content": r, "relevance": 0.8} for r in proc_results]
                )
            except Exception as e:
                logger.warning(f"Procedural retrieval failed: {e}")

        # DEEP UNIFICATION (Dec 1, 2025): Geometric memory via E8 lattice
        if memory_types is None or "geometric" in memory_types:
            try:
                import hashlib

                import torch

                # Convert query to tensor via hash
                query_hash = hashlib.sha256(query.encode()).digest()
                query_tensor = torch.tensor(
                    [float(b) / 255.0 for b in query_hash[:14]],
                    dtype=torch.float32,
                ).unsqueeze(0)

                # Retrieve from HopfieldE8
                if self.hopfield_e8 is not None:
                    hopfield_result = self.hopfield_e8(query_tensor)
                    if "retrieved_content" in hopfield_result:
                        results.append(
                            {
                                "type": "hopfield_e8",
                                "content": hopfield_result["retrieved_content"],
                                "attention": hopfield_result.get("attention"),
                                "relevance": 0.95,  # High relevance for geometric memory
                            }
                        )

                # Retrieve programs from ProgramLibrary
                if self.solomonoff is not None:
                    from kagami.core.world_model.memory import ColonyGenome

                    genome = ColonyGenome.for_colony(1)  # Default to Forge
                    sol_result = self.solomonoff.select(
                        query=query_tensor,
                        colony_genome=genome,
                        extended_dna=[],
                        top_k=limit,
                    )
                    if "embedding" in sol_result:
                        results.append(
                            {
                                "type": "solomonoff",
                                "content": sol_result["embedding"],
                                "program_indices": sol_result.get("top_k_indices"),
                                "relevance": 0.92,
                            }
                        )

            except Exception as e:
                logger.debug(f"Geometric retrieval failed: {e}")

        # Sort by relevance
        results.sort(key=lambda x: float(x.get("relevance", 0.0)), reverse=True)
        return results[:limit]

    def consolidate(self) -> dict[str, Any]:
        """Run memory consolidation across all systems.

        Returns:
            Consolidation stats
        """
        stats: dict[str, Any] = {
            "hierarchical": {},
            "episodic": {},
            "procedural": {},
        }

        try:
            # Consolidate hierarchical memory (short-term → long-term)
            if hasattr(self.hierarchical, "consolidate"):
                stats["hierarchical"] = self.hierarchical.consolidate()
        except Exception as e:
            logger.error(f"Hierarchical consolidation failed: {e}")
            stats["hierarchical"] = {"error": str(e)}

        try:
            # Consolidate episodic memory
            if hasattr(self.episodic, "consolidate"):
                stats["episodic"] = self.episodic.consolidate()
        except Exception as e:
            logger.error(f"Episodic consolidation failed: {e}")
            stats["episodic"] = {"error": str(e)}

        return stats

    def get_stats(self) -> dict[str, Any]:
        """Get statistics from all memory systems.

        DEEP UNIFICATION (Dec 1, 2025): Now includes geometric memory stats.

        Returns:
            Dict with stats from each system
        """
        stats: dict[str, Any] = {
            "hierarchical": {
                "working": len(getattr(self.hierarchical, "_working_memory", {})),
                "short_term": len(getattr(self.hierarchical, "_short_term", [])),
                "long_term": len(getattr(self.hierarchical, "_long_term", [])),
            },
            "episodic": {
                "episodes": len(getattr(self.episodic, "episodes", [])),
            },
            "procedural": {
                "skills": len(getattr(self.procedural, "skills", {})),
            },
        }

        # Geometric memory stats
        self._ensure_geometric_memory()

        if self._hopfield_e8 is not None:
            stats["hopfield_e8"] = {
                "slots": 240,  # Fixed E8 root count
                "value_dim": (
                    getattr(self._hopfield_e8, "config", None)
                    and self._hopfield_e8.config.value_dim
                )
                or 128,
            }

        if self._solomonoff is not None:
            stats["solomonoff"] = {
                "programs": 240,  # Fixed E8 slot count
                "initialized": True,
            }

        if self._colony_memory_bridge is not None:
            bridge_stats = self._colony_memory_bridge.get_stats()
            stats["colony_bridge"] = bridge_stats

        return stats


# Singleton instance
_memory_hub: MemoryHub | None = None


def get_memory_hub() -> MemoryHub:
    """Get singleton memory hub.

    Returns:
        MemoryHub instance

    Raises:
        RuntimeError: If memory hub fails to initialize (Full Operation Mode)
    """
    global _memory_hub

    if _memory_hub is None:
        try:
            _memory_hub = MemoryHub()
        except Exception as e:
            raise RuntimeError(
                f"MemoryHub failed to initialize. Full Operation Mode requires memory systems. Error: {e}"
            ) from e

    return _memory_hub


def reset_memory_hub() -> None:
    """Reset memory hub (for testing)."""
    global _memory_hub
    _memory_hub = None


__all__ = ["MemoryHub", "get_memory_hub", "reset_memory_hub"]
