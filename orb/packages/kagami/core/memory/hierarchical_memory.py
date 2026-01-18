from __future__ import annotations

"""Hierarchical Memory with Automatic Consolidation.

Multi-level memory system inspired by human memory (working → short-term → long-term).
Automatically consolidates and compresses memories as they age.

Key benefits:
- Better long-term memory (automatic consolidation)
- Faster retrieval (hierarchical search)
- Automatic abstraction (compress details → patterns)
- Bounded memory usage WITH automatic cleanup

Architecture:
    Level 0: Working Memory (20 recent, full detail)
    Level 1: Short-Term Memory (1000 episodes, compressed)
    Level 2: Long-Term Memory (patterns, prototypes) - NOW WITH TTL
    Level 3: Semantic Memory (abstract knowledge) - NOW WITH SIZE LIMITS

Consolidation:
    Working (20 full) → Short-Term (compress) → Long-Term (abstract) → Semantic (knowledge)

Reference: McClelland et al. (1995) "Complementary Learning Systems"
"""
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin

logger = logging.getLogger(__name__)


@dataclass
class CompressedEpisode:
    """Compressed representation of multiple similar experiences."""

    pattern: dict[str, Any]  # Common pattern extracted
    valence_avg: float  # Average valence
    valence_std: float  # Valence variance
    count: int  # Number of experiences
    examples: list[dict[str, Any]]  # Sample experiences (2-3)
    first_seen: float  # Timestamp
    last_seen: float  # Timestamp


@dataclass
class LongTermPattern:
    """Abstract pattern in long-term memory."""

    prototype: dict[str, Any]  # Prototypical example
    frequency: int  # How often this pattern occurs
    confidence: float  # Confidence in pattern (0-1)
    created_at: float  # When pattern was created


class HierarchicalMemory(SingletonCleanupMixin):
    """Multi-level memory with automatic consolidation AND cleanup.

    Usage:
        memory = HierarchicalMemory()

        # Store experience
        await memory.store(experience)

        # Recall relevant memories (hierarchical search)
        memories = await memory.recall(query, max_results=5)

        # Consolidation AND cleanup happen automatically!
    """

    def __init__(
        self,
        working_capacity: int = 20,
        short_term_capacity: int = 1000,
        consolidation_threshold: int = 20,
        long_term_ttl_days: int = 90,
        max_semantic_entries: int = 10000,
    ) -> None:
        """Initialize hierarchical memory.

        Args:
            working_capacity: Working memory size (recent, detailed)
            short_term_capacity: Short-term memory size (compressed)
            consolidation_threshold: Consolidate every N additions to working memory
            long_term_ttl_days: Remove long-term patterns after N days
            max_semantic_entries: Maximum semantic knowledge entries
        """
        # Level 0: Working memory (recent, detailed)
        self._working_memory: deque = deque(maxlen=working_capacity)

        # Level 1: Short-term memory (episodes, compressed)
        self._short_term: deque = deque(maxlen=short_term_capacity)

        # Level 2: Long-term memory (patterns, prototypes)
        self._long_term: dict[str, LongTermPattern] = {}

        # Level 3: Semantic memory (abstract knowledge)
        self._semantic: dict[str, Any] = {}

        # Configuration
        self._consolidation_threshold = consolidation_threshold
        self._working_capacity = working_capacity
        self._long_term_ttl_seconds = long_term_ttl_days * 86400
        self._max_semantic_entries = max_semantic_entries

        # Statistics
        self._total_stored = 0
        self._consolidations = 0
        self._last_consolidation = 0.0

        # Configure cleanup (every 1 hour)
        self._cleanup_interval = 3600.0
        self._register_cleanup_on_exit()

    async def store(self, experience: dict[str, Any]) -> None:
        """Store experience with automatic consolidation.

        Args:
            experience: Experience dict[str, Any] with context, outcome, valence
        """
        # Add to working memory
        self._working_memory.append(experience)
        self._total_stored += 1

        # Check if consolidation needed
        if len(self._working_memory) >= self._consolidation_threshold:
            await self._consolidate_working_to_short_term()

    async def _consolidate_working_to_short_term(self) -> None:
        """Consolidate working memory to short-term (compress).

        Clusters similar experiences and creates compressed representations.
        """
        if not self._working_memory:
            return

        # Cluster similar experiences
        clusters = await self._cluster_experiences(list(self._working_memory))

        # Compress each cluster
        for _cluster_id, experiences in clusters.items():
            if not experiences:
                continue

            # Extract common pattern
            pattern = self._extract_pattern(experiences)

            # Compute statistics
            valences = [e.get("valence", 0.0) for e in experiences]
            valence_avg = float(np.mean(valences))
            valence_std = float(np.std(valences))

            # Keep sample examples (2-3)
            examples = experiences[:3]

            # Create compressed episode
            compressed = CompressedEpisode(
                pattern=pattern,
                valence_avg=valence_avg,
                valence_std=valence_std,
                count=len(experiences),
                examples=examples,
                first_seen=min(e.get("timestamp", time.time()) for e in experiences),
                last_seen=max(e.get("timestamp", time.time()) for e in experiences),
            )

            # Add to short-term memory
            self._short_term.append(compressed)

        # Clear working memory (consolidated)
        self._working_memory.clear()
        self._consolidations += 1
        self._last_consolidation = time.time()

        logger.debug(f"💾 Consolidated working memory: {len(clusters)} clusters created")

        # Check if short-term needs consolidation to long-term
        if len(self._short_term) >= self._short_term.maxlen * 0.9:  # type: ignore  # Operator overload
            await self._consolidate_to_long_term()

    async def _consolidate_to_long_term(self) -> None:
        """Consolidate short-term to long-term (find frequent patterns).

        Finds patterns that occur frequently and stores them as prototypes.
        """
        # Find frequent patterns (appear 10+ times)
        pattern_counts: dict[str, list[CompressedEpisode]] = defaultdict(list[Any])

        for episode in self._short_term:
            # Create signature from pattern
            signature = self._pattern_signature(episode.pattern)
            pattern_counts[signature].append(episode)

        # Promote frequent patterns to long-term
        for signature, episodes in pattern_counts.items():
            if len(episodes) >= 10:  # Frequency threshold
                # Create prototype
                prototype = self._create_prototype(episodes)
                confidence = len(episodes) / len(self._short_term)

                # Store or update long-term pattern
                if signature in self._long_term:
                    # Update existing
                    self._long_term[signature].frequency += len(episodes)
                    self._long_term[signature].confidence = max(
                        self._long_term[signature].confidence, confidence
                    )
                else:
                    # Create new
                    self._long_term[signature] = LongTermPattern(
                        prototype=prototype,
                        frequency=len(episodes),
                        confidence=confidence,
                        created_at=time.time(),
                    )

        logger.debug(f"💾 Consolidated to long-term: {len(self._long_term)} patterns")

    async def recall(self, query: dict[str, Any], max_results: int = 5) -> list[dict[str, Any]]:
        """Hierarchical recall (working → short-term → long-term → semantic).

        Args:
            query: Query dict[str, Any] to match against
            max_results: Maximum memories to return

        Returns:
            List of relevant memories (most relevant first)
        """
        results = []

        # Level 0: Search working memory (fast, detailed)
        working_matches = self._search_working_memory(query)
        results.extend(working_matches[:max_results])

        # Level 1: Search short-term if needed
        if len(results) < max_results:
            short_term_matches = self._search_short_term(query)
            results.extend(short_term_matches[: max_results - len(results)])

        # Level 2: Search long-term if needed
        if len(results) < max_results:
            long_term_matches = self._search_long_term(query)
            results.extend(long_term_matches[: max_results - len(results)])

        # Level 3: Search semantic if needed
        if len(results) < max_results:
            semantic_matches = self._search_semantic(query)
            results.extend(semantic_matches[: max_results - len(results)])

        return results

    def _search_working_memory(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search working memory for matches."""
        matches = []
        for exp in self._working_memory:
            score = self._match_score(exp, query)
            if score > 0.3:  # Relevance threshold
                matches.append(
                    {"memory": exp, "score": score, "level": "working", "detail": "full"}
                )

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def _search_short_term(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search short-term memory for matches."""
        matches = []
        for episode in self._short_term:
            score = self._match_score(episode.pattern, query)
            if score > 0.3:
                matches.append(
                    {
                        "memory": episode.pattern,
                        "score": score,
                        "level": "short_term",
                        "detail": "compressed",
                        "count": episode.count,
                        "valence": episode.valence_avg,
                    }
                )

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    def _search_long_term(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search long-term memory for matches."""
        matches = []
        for _signature, pattern in self._long_term.items():
            score = self._match_score(pattern.prototype, query)
            if score > 0.3:
                matches.append(
                    {
                        "memory": pattern.prototype,
                        "score": score * pattern.confidence,  # Weight by confidence
                        "level": "long_term",
                        "detail": "prototype",
                        "frequency": pattern.frequency,
                    }
                )

        matches.sort(key=lambda x: x["score"], reverse=True)  # type: ignore
        return matches

    def _search_semantic(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search semantic memory for matches."""
        matches = []
        query_sig = self._pattern_signature(query)

        for key, knowledge in self._semantic.items():
            if query_sig in key or key in query_sig:
                matches.append(
                    {
                        "memory": knowledge,
                        "score": 0.5,  # Lower score for abstract knowledge
                        "level": "semantic",
                        "detail": "abstract",
                    }
                )

        return matches

    def _match_score(self, memory: dict[str, Any], query: dict[str, Any]) -> float:
        """Compute similarity score between memory and query.

        Args:
            memory: Stored memory
            query: Query dict[str, Any]

        Returns:
            Match score 0-1 (higher = better match)
        """
        # Simple matching: count overlapping keys/values
        common_keys = set(memory.keys()) & set(query.keys())
        if not common_keys:
            return 0.0

        matches = 0
        for key in common_keys:
            if memory.get(key) == query.get(key):
                matches += 1

        score = matches / len(common_keys)
        return float(score)

    async def _cluster_experiences(
        self, experiences: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Cluster similar experiences.

        Args:
            experiences: List of experiences

        Returns:
            Dict of cluster_id -> experiences
        """
        # Simple clustering by signature
        clusters = defaultdict(list[Any])

        for exp in experiences:
            signature = self._pattern_signature(exp.get("context", {}))
            clusters[signature].append(exp)

        return dict(clusters)

    def _extract_pattern(self, experiences: list[dict[str, Any]]) -> dict[str, Any]:
        """Extract common pattern from experiences.

        Args:
            experiences: List of similar experiences

        Returns:
            Pattern dict[str, Any] (common elements)
        """
        if not experiences:
            return {}

        # Start with first experience
        pattern = experiences[0].get("context", {}).copy()

        # Keep only common elements
        for exp in experiences[1:]:
            context = exp.get("context", {})
            # Remove keys that don't match
            pattern = {k: v for k, v in pattern.items() if k in context and context[k] == v}

        return cast(dict[str, Any], pattern)

    def _pattern_signature(self, pattern: dict[str, Any]) -> str:
        """Create signature from pattern.

        Args:
            pattern: Pattern dict[str, Any]

        Returns:
            String signature
        """
        # Sort keys for deterministic signature
        parts = [f"{k}:{v}" for k, v in sorted(pattern.items())]
        return "::".join(parts)

    def _create_prototype(self, episodes: list[CompressedEpisode]) -> dict[str, Any]:
        """Create prototypical example from episodes.

        Args:
            episodes: List of compressed episodes

        Returns:
            Prototype dict[str, Any]
        """
        if not episodes:
            return {}

        # Start with most common pattern
        pattern = episodes[0].pattern.copy()

        # Add statistics
        pattern["_frequency"] = sum(e.count for e in episodes)
        pattern["_avg_valence"] = float(np.mean([e.valence_avg for e in episodes]))
        pattern["_confidence"] = len(episodes) / 100.0  # Normalize

        return pattern

    def _cleanup_internal_state(self) -> dict[str, int]:
        """Clean up old memories (implements SingletonCleanupMixin).

        Removes:
        1. Long-term patterns older than TTL (default 90 days)
        2. Excess semantic knowledge (keep top N by frequency)

        Returns:
            Cleanup statistics
        """
        removed_long_term = 0
        removed_semantic = 0
        current_time = time.time()

        # Clean up long-term patterns (TTL-based)
        for signature in list(self._long_term.keys()):
            pattern = self._long_term[signature]
            age_seconds = current_time - pattern.created_at

            if age_seconds > self._long_term_ttl_seconds:
                del self._long_term[signature]
                removed_long_term += 1

        # Clean up semantic memory (size-based LRU)
        if len(self._semantic) > self._max_semantic_entries:
            # Remove oldest entries (simple: remove first N)
            excess = len(self._semantic) - self._max_semantic_entries
            keys_to_remove = list(self._semantic.keys())[:excess]

            for key in keys_to_remove:
                del self._semantic[key]
                removed_semantic += 1

        logger.debug(
            f"HierarchicalMemory cleanup: removed {removed_long_term} long-term patterns, "
            f"{removed_semantic} semantic entries"
        )

        return {
            "long_term_removed": removed_long_term,
            "semantic_removed": removed_semantic,
            "long_term_remaining": len(self._long_term),
            "semantic_remaining": len(self._semantic),
            "short_term_size": len(self._short_term),
            "working_memory_size": len(self._working_memory),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dict with memory sizes, consolidations, etc.
        """
        return {
            "working_memory_size": len(self._working_memory),
            "working_memory_capacity": self._working_capacity,
            "short_term_size": len(self._short_term),
            "short_term_capacity": self._short_term.maxlen,
            "long_term_patterns": len(self._long_term),
            "semantic_knowledge": len(self._semantic),
            "total_stored": self._total_stored,
            "consolidations": self._consolidations,
            "last_consolidation": self._last_consolidation,
            "compression_ratio": self._total_stored
            / max(1, len(self._working_memory) + len(self._short_term)),
        }


# Global singleton
_hierarchical_memory: HierarchicalMemory | None = None


def get_hierarchical_memory() -> HierarchicalMemory:
    """Get global hierarchical memory singleton.

    Returns:
        HierarchicalMemory instance
    """
    global _hierarchical_memory
    if _hierarchical_memory is None:
        _hierarchical_memory = HierarchicalMemory()
    return _hierarchical_memory
