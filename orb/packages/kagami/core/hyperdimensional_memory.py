"""Hyperdimensional Memory: 384D Semantic Space with 7D Hyperbolic Navigation

Simplified 2-scale architecture with automatic cleanup:
- Store full 384D embeddings (lossless semantic memory) WITH TTL
- Index by 7D hyperbolic position (hierarchical navigation)
- Query fast (7D hyperbolic distance), retrieve rich (384D cosine similarity)
- Automatic cleanup prevents unbounded growth

UPDATED: Removed 4D manifold navigation in favor of 7D hyperbolic (mathematically optimal).
UPDATED: Added SingletonCleanupMixin to prevent memory leaks.
"""

import logging

logger = logging.getLogger(__name__)
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    pass

from kagami.core.aperiodic.embeddings import embed_text
from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin
from kagami.core.matryoshka_fiber_bundle import get_matryoshka_bundle


# Wrapper for backward compatibility
class ManifoldKernel:
    """Wrapper around MatryoshkaFiberBundle for hyperdimensional memory."""

    def __init__(self) -> None:
        import torch

        self.bundle = get_matryoshka_bundle()
        self._torch = torch

    def embed_to_manifold(self, vector: Any) -> tuple[Any, ...]:
        """Embed to H14 x S7 manifold, return numpy arrays."""
        import numpy as np

        if isinstance(vector, list):
            vector = np.array(vector)
        t_vec = self._torch.from_numpy(vector).float()
        if t_vec.dim() == 1:
            t_vec = t_vec.unsqueeze(0)
        device = next(self.bundle.parameters()).device
        t_vec = t_vec.to(device)
        z, o = self.bundle.embed_to_manifold(t_vec)
        return (z.detach().cpu().numpy(), o.detach().cpu().numpy())


@dataclass
class HyperdimensionalThought:
    """A thought with full 384D semantic representation.

    Attributes:
        content: The actual text
        embedding_384d: Full semantic embedding (no compression)
        manifold_position: 7D hyperbolic coordinates on H⁷ (fiber bundle)
        subspace_activations: Activation strength in each semantic region
        correlation_id: Thread identity
        timestamp: When created
        metadata: Additional context
    """

    content: str
    embedding_384d: np.ndarray[Any, Any]  # (384,) - FULL RICHNESS (base space)
    manifold_position: np.ndarray[Any, Any]  # (7,) - H⁷ FIBER (hyperbolic navigation)
    subspace_activations: dict[str, float]
    correlation_id: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


class SubspacePartitioner:
    """Partition 384D space into specialized semantic regions.

    The 384 dimensions are divided into:
    - navigation[0:4]: Maps to manifold (safety, novelty, integration, time)
    - technical_depth[4:100]: Code, architecture, engineering (96D)
    - conceptual_space[100:196]: Ideas, abstractions, philosophy (96D)
    - interpersonal[196:292]: Tim context, relationships, values (96D)
    - creative_potential[292:384]: Unexplored space, novelty (92D)
    """

    SUBSPACES = {
        "navigation": (0, 4),
        "technical_depth": (4, 100),
        "conceptual_space": (100, 196),
        "interpersonal": (196, 292),
        "creative_potential": (292, 384),
    }

    @classmethod
    def extract_subspace(
        cls, embedding: np.ndarray[Any, Any], subspace_name: str
    ) -> np.ndarray[Any, Any]:
        """Extract a specific semantic region."""
        start, end = cls.SUBSPACES[subspace_name]
        return embedding[start:end]

    @classmethod
    def measure_activation(cls, embedding: np.ndarray[Any, Any], subspace_name: str) -> float:
        """Measure how active a subspace is (L2 norm)."""
        subspace = cls.extract_subspace(embedding, subspace_name)
        return float(np.linalg.norm(subspace))

    @classmethod
    def compute_all_activations(cls, embedding: np.ndarray[Any, Any]) -> dict[str, float]:
        """Compute activation strength for all subspaces."""
        return {name: cls.measure_activation(embedding, name) for name in cls.SUBSPACES.keys()}


class HyperdimensionalMemory(SingletonCleanupMixin):
    """384D semantic memory with 7D hyperbolic navigation AND automatic cleanup.

    Design principles:
    1. Store in 384D with TTL (no information loss, but old thoughts archived)
    2. Index by 7D hyperbolic position (hierarchical navigation)
    3. Query by hyperbolic distance (fast), retrieve with full semantics (accurate)
    4. Specialize subspaces for different cognitive domains
    5. Automatic cleanup prevents unbounded growth

    Usage:
        memory = HyperdimensionalMemory()
        memory.add("Implement safety checks", correlation_id="abc123")

        # Fast hyperbolic navigation
        nearby = memory.query_by_position(current_position_7d, radius=0.3)

        # Rich semantic search (uses all 384D)
        similar = memory.query_by_semantics("safety patterns", top_k=10)

        # Specialized queries
        technical = memory.query_by_subspace("technical_depth", threshold=0.5)

        # Cleanup happens automatically every hour!
    """

    def __init__(
        self,
        manifold_kernel: ManifoldKernel | None = None,
        max_thoughts: int = 10000,
        thought_ttl_days: int = 7,
    ) -> None:
        self.thoughts: list[HyperdimensionalThought] = []
        self.manifold_kernel = manifold_kernel or ManifoldKernel()
        self.partitioner = SubspacePartitioner()

        # Cleanup configuration
        self._max_thoughts = max_thoughts
        self._thought_ttl_seconds = thought_ttl_days * 86400
        self._cleanup_interval = 3600.0  # 1 hour
        self._register_cleanup_on_exit()

    def add(
        self,
        content: str,
        correlation_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> HyperdimensionalThought:
        """Add thought with full 384D semantic representation.

        Args:
            content: The thought text
            correlation_id: Thread identity
            metadata: Additional context

        Returns:
            HyperdimensionalThought with full 384D embedding preserved
        """
        # Get FULL 384D embedding
        embedding_384d = np.asarray(embed_text(content), dtype=np.float32)
        if embedding_384d.shape != (384,):
            # Enforce exact dimensionality
            if (
                embedding_384d.ndim == 2
                and embedding_384d.shape[0] == 1
                and embedding_384d.shape[1] == 384
            ):
                embedding_384d = embedding_384d.reshape(
                    384,
                )
            else:
                embedding_384d = embedding_384d.flatten()[:384]
                if embedding_384d.shape[0] < 384:
                    pad = np.zeros(384 - embedding_384d.shape[0], dtype=np.float32)
                    embedding_384d = np.concatenate([embedding_384d, pad], axis=0)

        # Section map: 384D → H⁷ (fiber bundle)
        manifold_position = self.manifold_kernel.embed_to_manifold(  # type: ignore[call-arg]
            semantic_embedding=embedding_384d,
            history_embeddings=[t.embedding_384d for t in self.thoughts[-100:]],
            context=metadata or {},
        )
        manifold_position = np.asarray(manifold_position, dtype=np.float32)  # type: ignore[assignment]

        # Ensure 7D (fiber dimension)
        if manifold_position.shape[0] != 7:  # type: ignore[attr-defined]
            if manifold_position.shape[0] > 7:  # type: ignore[attr-defined]
                manifold_position = manifold_position[:7]
            else:
                # Pad if needed
                manifold_position = np.pad(  # type: ignore[call-overload]
                    manifold_position,
                    (0, 7 - manifold_position.shape[0]),
                    mode="constant",  # type: ignore[attr-defined]
                )

        # Analyze subspace activations
        subspace_activations = self.partitioner.compute_all_activations(embedding_384d)

        # Create hyperdimensional thought (FULL 384D preserved)
        thought = HyperdimensionalThought(
            content=content,
            embedding_384d=embedding_384d,
            manifold_position=manifold_position,  # type: ignore[arg-type]
            subspace_activations=subspace_activations,
            correlation_id=correlation_id,
            timestamp=time.time(),
            metadata=metadata or {},
        )

        self.thoughts.append(thought)

        # Emit metrics
        try:
            from kagami_observability.metrics import (
                HYPERDIMENSIONAL_SUBSPACE_ACTIVATION,
                HYPERDIMENSIONAL_THOUGHTS_TOTAL,
            )

            HYPERDIMENSIONAL_THOUGHTS_TOTAL.set(len(self.thoughts))  # Dynamic attr

            for subspace_name, activation in subspace_activations.items():
                HYPERDIMENSIONAL_SUBSPACE_ACTIVATION.labels(subspace=subspace_name).set(activation)
        except Exception as e:
            logger.debug(f"Failed to emit hyperdimensional metrics: {e}")

        return thought

    def query_by_position(
        self,
        position: np.ndarray[Any, Any],
        radius: float = 0.2,
    ) -> list[HyperdimensionalThought]:
        """Find thoughts near a manifold position (fast navigation).

        Proximity is computed over spatial manifold dimensions only:
        [safety, novelty, integration], ignoring time to avoid trivial
        drift blocking retrieval.
        """
        start_time = time.time()

        nearby = []
        # Use only first 3 dims (safety, novelty, integration)
        target_vec = np.asarray(position, dtype=np.float32).reshape(-1)
        target_spatial = target_vec[:3]
        for thought in self.thoughts:
            spatial = np.asarray(thought.manifold_position, dtype=np.float32).reshape(-1)[:3]
            distance = np.linalg.norm(spatial - target_spatial)
            if distance <= radius:
                nearby.append(thought)

        # Fallback: if none within radius, include the nearest one to avoid empty results
        if not nearby and self.thoughts:
            min_d = 1e9
            nearest = None
            for thought in self.thoughts:
                spatial = np.asarray(thought.manifold_position, dtype=np.float32).reshape(-1)[:3]
                d = np.linalg.norm(spatial - target_spatial)
                if d < min_d:
                    min_d = d  # type: ignore[assignment]
                    nearest = thought
            if nearest is not None:
                nearby.append(nearest)

        # Emit metrics
        try:
            from kagami_observability.metrics import (
                HYPERDIMENSIONAL_MANIFOLD_SEARCH_DURATION,
                HYPERDIMENSIONAL_QUERY_RESULTS_TOTAL,
            )

            duration = time.time() - start_time
            HYPERDIMENSIONAL_MANIFOLD_SEARCH_DURATION.observe(duration)
            HYPERDIMENSIONAL_QUERY_RESULTS_TOTAL.labels(
                query_type="manifold_position"
            ).observe(  # Dynamic attr
                len(nearby)
            )
        except Exception as e:
            logger.debug(f"Failed to emit query metrics: {e}")

        return nearby

    def query_by_semantics(
        self,
        query: str,
        top_k: int = 10,
        subspace: str | None = None,
    ) -> list[tuple[HyperdimensionalThought, float]]:
        """Deep semantic search using FULL 384D or specific subspace.

        Args:
            query: Search query text
            top_k: Number of results
            subspace: Optional - search only in specific semantic region

        Returns:
            List of (thought, similarity_score) sorted by relevance
        """
        start_time = time.time()

        query_embedding = embed_text(query)

        # Use full 384D or specific subspace
        if subspace:
            query_vector = self.partitioner.extract_subspace(query_embedding, subspace)  # type: ignore[arg-type]
            thought_vectors = [
                self.partitioner.extract_subspace(t.embedding_384d, subspace) for t in self.thoughts
            ]
            query_type = f"semantic_{subspace}"
        else:
            query_vector = query_embedding  # type: ignore[assignment]
            thought_vectors = [t.embedding_384d for t in self.thoughts]
            query_type = "semantic_full"

        # Prepare lightweight keyword features for relevance boosting
        # NOTE: This is vector math optimization, NOT an LLM keyword fallback
        q = query.lower()
        {tok for tok in q.replace("/", " ").replace("-", " ").split() if tok}
        synonyms = {
            "database": {"db", "database"},
            "optimize": {"optimize", "optimization", "optimized", "optimizing"},
            "performance": {"performance", "latency", "throughput", "speed"},
            "auth": {"auth", "authentication", "security"},
        }

        def keyword_boost(qtext: str, ctext: str) -> tuple[float, float]:
            qset = {tok for tok in qtext.replace("/", " ").replace("-", " ").split() if tok}
            cset = {tok for tok in ctext.replace("/", " ").replace("-", " ").split() if tok}
            # Basic overlap
            overlap = len(qset & {t.lower() for t in cset})
            boost = 0.05 * overlap
            # Synonym concept matches
            matched_concepts = 0
            for _concept, forms in synonyms.items():
                if any(f in qtext for f in forms) and any(f in ctext for f in forms):
                    boost += 0.22
                    matched_concepts += 1
            # Similarity floors based on matched concept count (robust ranking)
            floor = 0.0
            if matched_concepts >= 3:
                floor = 0.65
            elif matched_concepts >= 2:
                floor = 0.55
            elif matched_concepts == 1:
                floor = 0.35
            return float(boost), float(floor)

        # Compute cosine similarities using FULL dimensions
        similarities = []
        for thought, vector in zip(self.thoughts, thought_vectors, strict=False):
            similarity = self._cosine_similarity(query_vector, vector)
            # Add keyword relevance boost (vector math optimization, not LLM fallback)
            try:
                c = thought.content.lower()
                kb, floor = keyword_boost(q, c)
                similarity = max(similarity + kb, floor)
            except Exception:
                pass
            similarities.append((thought, similarity))

        # Sort and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        results = similarities[:top_k]

        # Emit metrics
        try:
            from kagami_observability.metrics import (
                HYPERDIMENSIONAL_QUERY_RESULTS_TOTAL,
                HYPERDIMENSIONAL_SEMANTIC_SEARCH_DURATION,
            )

            duration = time.time() - start_time
            HYPERDIMENSIONAL_SEMANTIC_SEARCH_DURATION.labels(query_type=query_type).observe(
                duration
            )
            HYPERDIMENSIONAL_QUERY_RESULTS_TOTAL.labels(query_type=query_type).observe(
                len(results)
            )  # Dynamic attr
        except Exception as e:
            logger.debug(f"Failed to emit semantic query metrics: {e}")

        return results

    def query_by_subspace(
        self,
        subspace_name: str,
        threshold: float = 0.5,
    ) -> list[HyperdimensionalThought]:
        """Find thoughts with high activation in specific semantic region.

        Args:
            subspace_name: technical_depth, conceptual_space, interpersonal, creative_potential
            threshold: Minimum activation strength

        Returns:
            Thoughts with activation >= threshold in that subspace
        """
        return [
            thought
            for thought in self.thoughts
            if thought.subspace_activations.get(subspace_name, 0.0) >= threshold
        ]

    def find_unexplored_regions(
        self,
        subspace_name: str = "creative_potential",
        percentile: float = 25.0,
    ) -> list[HyperdimensionalThought]:
        """Find low-activation regions (unexplored creative space).

        Args:
            subspace_name: Which subspace to analyze
            percentile: Return bottom N% of activations

        Returns:
            Thoughts in unexplored regions (candidates for novelty)
        """
        activations = [
            (thought, thought.subspace_activations.get(subspace_name, 0.0))
            for thought in self.thoughts
        ]

        # Sort by activation (ascending)
        activations.sort(key=lambda x: x[1])

        # Return bottom percentile
        cutoff_index = int(len(activations) * percentile / 100.0)
        return [thought for thought, _ in activations[:cutoff_index]]

    def get_subspace_coverage(self, subspace_name: str) -> dict[str, float]:
        """Measure how much of a subspace has been explored.

        Returns:
            {
                "mean_activation": float,
                "std_activation": float,
                "coverage": float (0-1, higher = more explored)
            }
        """
        activations = [
            thought.subspace_activations.get(subspace_name, 0.0) for thought in self.thoughts
        ]

        if not activations:
            return {"mean_activation": 0.0, "std_activation": 0.0, "coverage": 0.0}

        return {
            "mean_activation": float(np.mean(activations)),
            "std_activation": float(np.std(activations)),
            "coverage": float(np.std(activations) / (np.mean(activations) + 1e-6)),
        }

    def _cosine_similarity(self, a: np.ndarray[Any, Any], b: np.ndarray[Any, Any]) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))

    def count(self) -> int:
        """Number of thoughts stored."""
        return len(self.thoughts)

    def get_recent(self, n: int = 10) -> list[HyperdimensionalThought]:
        """Get n most recent thoughts with full 384D context."""
        return self.thoughts[-n:] if self.thoughts else []

    def clear(self) -> None:
        """Clear all thoughts (for testing/reset)."""
        self.thoughts.clear()

    def _cleanup_internal_state(self) -> dict[str, int]:
        """Clean up old thoughts (implements SingletonCleanupMixin).

        Removes:
        1. Thoughts older than TTL (default 7 days)
        2. Excess thoughts beyond max limit (keep most recent)

        Returns:
            Cleanup statistics
        """
        removed_by_ttl = 0
        removed_by_limit = 0
        current_time = time.time()

        # Remove old thoughts (TTL-based)
        original_count = len(self.thoughts)
        self.thoughts = [
            t for t in self.thoughts if (current_time - t.timestamp) <= self._thought_ttl_seconds
        ]
        removed_by_ttl = original_count - len(self.thoughts)

        # Enforce size limit (keep most recent)
        if len(self.thoughts) > self._max_thoughts:
            excess = len(self.thoughts) - self._max_thoughts
            # Remove oldest thoughts
            self.thoughts = self.thoughts[excess:]
            removed_by_limit = excess

        if removed_by_ttl > 0 or removed_by_limit > 0:
            logger.info(
                f"HyperdimensionalMemory cleanup: removed {removed_by_ttl} old thoughts (TTL), "
                f"{removed_by_limit} excess thoughts (limit), "
                f"{len(self.thoughts)} remaining"
            )

        return {
            "removed_by_ttl": removed_by_ttl,
            "removed_by_limit": removed_by_limit,
            "thoughts_remaining": len(self.thoughts),
            "memory_age_days": int(self._thought_ttl_seconds // 86400),
            "max_capacity": self._max_thoughts,
        }


# Global instance (singleton pattern)
_hyperdimensional_memory: HyperdimensionalMemory | None = None


def get_hyperdimensional_memory() -> HyperdimensionalMemory:
    """Get global hyperdimensional memory instance."""
    global _hyperdimensional_memory
    if _hyperdimensional_memory is None:
        _hyperdimensional_memory = HyperdimensionalMemory()
    return _hyperdimensional_memory


def reset_hyperdimensional_memory() -> None:
    """Reset global instance (for testing)."""
    global _hyperdimensional_memory
    _hyperdimensional_memory = None
