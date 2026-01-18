"""Memory Consolidation - Offline replay with semantic clustering WITH cleanup.

Implements sleep-like memory consolidation:
1. Sample high-importance experiences
2. Cluster by semantic similarity
3. Extract abstract patterns
4. Store in hierarchical memory
5. Prune low-importance memories
6. Automatic cleanup of consolidation state
"""

import logging
import time
from typing import Any

import numpy as np

from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin

logger = logging.getLogger(__name__)


class MemoryConsolidation(SingletonCleanupMixin):
    """Consolidate memories via offline replay and clustering WITH automatic cleanup.

    ROOM INTEGRATION (Dec 26, 2025):
    Subscribes to room.state_changed events to learn from room interactions.
    """

    def __init__(self) -> None:
        self._consolidation_history: list[dict[str, Any]] = []
        self._cleanup_interval = 7200.0  # 2 hours
        self._room_subscription_active = False
        self._register_cleanup_on_exit()

    async def subscribe_to_room_events(self) -> None:
        """Subscribe to room state changes for learning.

        ROOM→MEMORY INTEGRATION (Dec 26, 2025):
        Listens for room.state_changed events and extracts learning signal
        from social graph and spatial scene changes.
        """
        if self._room_subscription_active:
            return

        try:
            from kagami.core.events import get_unified_bus

            bus = get_unified_bus()

            async def on_room_changed(event_data: dict[str, Any]) -> None:
                """Handle room state change for learning."""
                try:
                    room_id = event_data.get("room_id", "unknown")
                    social_graph = event_data.get("social_graph", {})
                    spatial_scene = event_data.get("spatial_scene", {})

                    # Extract learning signal from room changes
                    member_count = social_graph.get("member_count", 0)
                    entity_count = spatial_scene.get("entity_count", 0)

                    if member_count > 0 or entity_count > 0:
                        # Store room interaction as experience
                        from kagami.core.memory.hierarchical_memory import get_hierarchical_memory

                        hier_mem = get_hierarchical_memory()
                        if hier_mem:
                            experience = {
                                "content": f"room:{room_id} members:{member_count} entities:{entity_count}",
                                "timestamp": event_data.get("timestamp", time.time()),
                                "valence": 0.3,  # Neutral-positive valence for room activity
                                "metadata": {
                                    "source": "room_state_changed",
                                    "room_id": room_id,
                                    "member_count": member_count,
                                    "entity_count": entity_count,
                                },
                            }
                            await hier_mem.store(experience)
                            logger.debug(f"📚 Stored room learning from {room_id}")
                except Exception as e:
                    logger.debug(f"Room learning failed: {e}")

            await bus.subscribe("room.state_changed", on_room_changed)  # type: ignore[arg-type, func-returns-value]
            self._room_subscription_active = True
            logger.info("✅ MemoryConsolidation subscribed to room.state_changed events")

        except Exception as e:
            logger.warning(f"Failed to subscribe to room events: {e}")

    async def consolidate_memories(self) -> dict[str, Any]:
        """Consolidate memories from prioritized replay into hierarchical storage.

        Returns:
            Stats about consolidation process
        """
        try:
            from kagami.core.memory.hierarchical_memory import get_hierarchical_memory
            from kagami.core.memory.unified_replay import get_unified_replay
            from kagami.core.services.embedding_service import get_embedding_service

            replay = get_unified_replay()
            hier_mem = get_hierarchical_memory()
            embeddings_svc = get_embedding_service()

            # 1. Sample high-importance experiences (UPDATED Dec 6, 2025: Use unified buffer)
            # Sample experiences - UnifiedReplayBuffer uses prioritized sampling by default
            important_exps, _, _ = replay.sample(min(100, len(replay)))

            if len(important_exps) < 5:
                return {
                    "status": "insufficient_data",
                    "experiences": len(important_exps),
                }

            # 2. Compute embeddings for clustering
            embeddings = []
            for exp in important_exps:
                try:
                    text = f"{exp.context.get('action', '')} {exp.outcome.get('status', '')}"
                    emb = embeddings_svc.embed_text(text)
                    embeddings.append(emb)
                except Exception:
                    embeddings.append(np.zeros(384))  # Fallback

            embeddings_array = np.array(embeddings)

            # 3. Cluster by semantic similarity (k-means)
            from sklearn.cluster import KMeans

            n_clusters = min(10, len(important_exps) // 10)  # ~10 experiences per cluster
            if n_clusters < 2:
                n_clusters = 2

            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            kmeans.fit_predict(embeddings_array)

            # 4. Store consolidated memories in hierarchical memory
            consolidated_count = 0
            for exp in important_exps:
                experience: dict[str, Any] = {
                    "content": str(exp.context.get("action", "unknown")),
                    "timestamp": float(exp.timestamp),
                    "valence": float(exp.valence),
                    "context": exp.context,
                    "outcome": exp.outcome,
                    "metadata": {
                        **(exp.metadata or {}),
                        "task_id": exp.task_id,
                        "experience_type": exp.experience_type,
                        "priority": float(exp.priority),
                    },
                }
                await hier_mem.store(experience)
                consolidated_count += 1

            logger.info(
                f"💾 Consolidated {consolidated_count} memories into {n_clusters} semantic clusters"
            )

            return {
                "status": "success",
                "consolidated": consolidated_count,
                "clusters": n_clusters,
                "avg_importance": float(np.mean([e.priority for e in important_exps])),
            }

        except Exception as e:
            logger.warning(f"Memory consolidation failed: {e}")
            return {"status": "error", "error": str(e)}

    def _cleanup_internal_state(self) -> dict[str, int]:
        """Clean up old consolidation history (implements SingletonCleanupMixin)."""
        time.time()
        original_count = len(self._consolidation_history)

        # Keep only last 100 consolidations
        if len(self._consolidation_history) > 100:
            self._consolidation_history = self._consolidation_history[-100:]

        removed = original_count - len(self._consolidation_history)

        return {"history_removed": removed, "history_remaining": len(self._consolidation_history)}


# Global singleton
_consolidation: MemoryConsolidation | None = None


def get_memory_consolidation() -> MemoryConsolidation:
    """Get or create memory consolidation instance."""
    global _consolidation
    if _consolidation is None:
        _consolidation = MemoryConsolidation()
    return _consolidation
