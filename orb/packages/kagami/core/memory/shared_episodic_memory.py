"""Shared Episodic Memory - Collective knowledge across all agents.

All agents contribute to and query a shared memory pool:
- Agent insights become collective knowledge
- Patterns recognized by one agent inform all others
- Collaborative learning accelerates
- Hive intelligence emerges
- NOW WITH automatic cleanup to prevent unbounded growth

This enables: "Has anyone seen this pattern before?" → Instant recall

Storage: Weaviate-backed for persistence (Redis removed December 2025).
In-memory fallback if Weaviate unavailable.

Created: October 2025
Updated: December 7, 2025 - Removed Redis, Weaviate-only storage
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin

logger = logging.getLogger(__name__)


@dataclass
class SharedEpisode:
    """A memory contributed by an agent to collective knowledge."""

    episode_id: str
    contributing_agent: str
    category: str  # "visual_pattern", "performance_insight", "mathematical_discovery"
    content: str  # The actual insight or observation
    data: dict[str, Any]  # Supporting data
    valence: float  # -1.0 to 1.0 (emotional weight)
    importance: float  # 0.0-1.0 (how significant)
    timestamp: float
    access_count: int = 0  # How many times queried
    confirmed_by: list[str] = field(default_factory=list[Any])  # Other agents who validated this
    # Optional semantic vector for "semantic glasses" filtering
    embedding: list[float] | None = None


class SharedEpisodicMemory(SingletonCleanupMixin):
    """Collective memory pool for all agents WITH automatic cleanup.

    Any agent can:
    1. Store insights (contribute to hive knowledge)
    2. Query insights (ask "has anyone seen X?")
    3. Confirm insights (validate what others found)
    4. Build on insights (add to existing knowledge)

    Result: Hive learns collectively, not individually.

    Storage: Weaviate-backed. Falls back to in-memory if unavailable.
    """

    def __init__(self, capacity: int = 1000, episode_ttl_days: int = 30) -> None:
        self.capacity = capacity
        self._episodes: list[SharedEpisode] = []
        self._index_by_category: dict[str, list[str]] = {}
        self._index_by_agent: dict[str, list[str]] = {}
        self._lock = asyncio.Lock()
        self._episode_ttl_seconds = episode_ttl_days * 86400

        # Weaviate persistence (lazy-loaded)
        self._weaviate_store: Any | None = None
        self._weaviate_available: bool | None = None  # None = not checked yet

        # Configure cleanup
        self._cleanup_interval = 3600.0  # 1 hour
        self._register_cleanup_on_exit()

    async def _get_weaviate_store(self) -> Any:
        """Lazy-load Weaviate store for persistence."""
        if self._weaviate_available is False:
            return None

        if self._weaviate_store is not None:
            return self._weaviate_store

        try:
            # Dynamic import to avoid core ↔ integrations import cycles.
            import importlib

            mod = importlib.import_module("kagami_integrations.elysia.weaviate_e8_adapter")
            get_weaviate_adapter = getattr(mod, "get_weaviate_adapter", None)
            if get_weaviate_adapter is None:
                raise ImportError("get_weaviate_adapter not found")

            adapter = get_weaviate_adapter()
            connected = await adapter.connect()

            if connected:
                self._weaviate_store = adapter
                self._weaviate_available = True
                logger.debug("Weaviate connected for episodic memory")
                return adapter
            else:
                self._weaviate_available = False
                logger.debug("Weaviate not available - using in-memory only")
                return None

        except ImportError:
            self._weaviate_available = False
            logger.debug("Weaviate integration not available - using in-memory only")
            return None
        except Exception as e:
            self._weaviate_available = False
            logger.debug(f"Weaviate connection failed: {e} - using in-memory only")
            return None

    async def store(
        self,
        agent_name: str,
        category: str,
        content: str,
        data: dict[str, Any],
        valence: float = 0.0,
        importance: float = 0.5,
        embedding: list[float] | None = None,
    ) -> str:
        """Store insight in shared memory.

        Args:
            agent_name: Agent contributing this insight
            category: Type of insight
            content: The insight text
            data: Supporting data
            valence: Emotional weight (-1.0 to 1.0)
            importance: Significance (0.0-1.0)
            embedding: Optional semantic vector

        Returns:
            episode_id for reference
        """
        async with self._lock:
            episode_id = f"{agent_name}_{int(time.time() * 1000)}"

            episode = SharedEpisode(
                episode_id=episode_id,
                contributing_agent=agent_name,
                category=category,
                content=content,
                data=data,
                valence=valence,
                importance=importance,
                timestamp=time.time(),
                embedding=embedding,
            )

            # Add to main storage
            self._episodes.append(episode)

            # Maintain capacity (evict least important)
            if len(self._episodes) > self.capacity:
                # Sort by importance * (1 - age_factor)
                now = time.time()
                scored = [
                    (
                        ep,
                        ep.importance * (1.0 / (1.0 + (now - ep.timestamp) / 86400)),  # Age decay
                    )
                    for ep in self._episodes
                ]
                scored.sort(key=lambda x: x[1])
                self._episodes = [ep for ep, _ in scored[-self.capacity :]]

            # Update indices
            if category not in self._index_by_category:
                self._index_by_category[category] = []
            self._index_by_category[category].append(episode_id)

            if agent_name not in self._index_by_agent:
                self._index_by_agent[agent_name] = []
            self._index_by_agent[agent_name].append(episode_id)

            # Persist to Weaviate if available
            store = await self._get_weaviate_store()
            if store:
                try:
                    await store.store(
                        content=content,
                        metadata={
                            "kind": "episode",
                            "episode_id": episode_id,
                            "agent": agent_name,
                            "category": category,
                            "colony": category.split("_")[0] if "_" in category else "nexus",
                            "source_id": episode_id,
                            "timestamp": episode.timestamp,
                            "metadata_json": json.dumps(
                                {"data": data, "valence": valence, "importance": importance},
                                default=str,
                            ),
                        },
                    )
                except Exception as e:
                    logger.debug(f"Weaviate persistence failed: {e}")

            # Emit metric

            logger.info(f"💾 {agent_name} stored: {content[:60]}... (importance={importance:.2f})")

            return episode_id

    def get_all_episodes(self) -> list[SharedEpisode]:
        """Return a snapshot list[Any] of all episodes (for semantic filtering)."""
        return list(self._episodes)

    async def query(
        self,
        asking_agent: str,
        query_text: str,
        category: str | None = None,
        top_k: int = 5,
    ) -> list[SharedEpisode]:
        """Query shared memory for relevant insights.

        Args:
            asking_agent: Agent querying
            query_text: What to search for
            category: Optional category filter
            top_k: How many results

        Returns:
            List of relevant episodes
        """
        async with self._lock:
            # Filter by category if specified
            candidates = self._episodes
            if category and category in self._index_by_category:
                episode_ids = self._index_by_category[category]
                candidates = [ep for ep in self._episodes if ep.episode_id in episode_ids]

            # Simple relevance scoring (would use semantic search in production)
            scored = []
            query_words = set(query_text.lower().split())

            for episode in candidates:
                content_words = set(episode.content.lower().split())
                overlap = len(query_words & content_words)

                # Score: word overlap + importance + recency
                age_hours = (time.time() - episode.timestamp) / 3600
                recency_factor = 1.0 / (1.0 + age_hours / 24)

                score = (overlap / max(len(query_words), 1)) * episode.importance * recency_factor

                if score > 0.1:  # Minimum relevance threshold
                    scored.append((episode, score))

            # Sort by score
            scored.sort(key=lambda x: x[1], reverse=True)

            results = [ep for ep, _ in scored[:top_k]]

            # Track access
            for ep in results:
                ep.access_count += 1

            if results:
                logger.info(
                    f'🔍 {asking_agent} queried: "{query_text[:40]}..." → {len(results)} results'
                )

            return results

    async def confirm(self, episode_id: str, confirming_agent: str) -> bool:
        """Confirm/validate an insight from another agent.

        Confirmation AMPLIFIES importance (stigmergy reinforcement):
        - 1st confirmation: +10% importance
        - 2nd confirmation: +15% importance
        - 3rd+ confirmation: +20% importance

        Args:
            episode_id: Episode to confirm
            confirming_agent: Agent doing the confirmation

        Returns:
            True if confirmed
        """
        async with self._lock:
            for episode in self._episodes:
                if episode.episode_id == episode_id:
                    if confirming_agent not in episode.confirmed_by:
                        episode.confirmed_by.append(confirming_agent)

                        # Amplification based on confirmation count (stigmergy)
                        n_confirmations = len(episode.confirmed_by)
                        if n_confirmations == 1:
                            amplification = 1.1  # +10%
                        elif n_confirmations == 2:
                            amplification = 1.15  # +15%
                        else:
                            amplification = 1.2  # +20%

                        episode.importance = min(1.0, episode.importance * amplification)

                        logger.info(
                            f"✓ {confirming_agent} confirmed {episode.contributing_agent}'s insight "
                            f"(confirmations={n_confirmations}, importance={episode.importance:.2f})"
                        )
                    return True

            return False

    async def evaporate_old_memories(self, decay_rate: float = 0.95) -> int:
        """Evaporate (decay) importance of old memories (pheromone-style).

        Implements negative feedback for exploration-exploitation balance.
        Old memories fade unless reinforced by access or confirmation.

        Args:
            decay_rate: Importance decay per hour (0.95 = 5% decay/hour)

        Returns:
            Number of memories evaporated (removed)
        """
        async with self._lock:
            now = time.time()
            evaporated = 0

            for episode in self._episodes[:]:  # Copy to allow removal
                # Age in hours
                age_hours = (now - episode.timestamp) / 3600

                # Decay importance (exponential)
                decayed_importance = episode.importance * (decay_rate**age_hours)

                # Remove if too weak
                if decayed_importance < 0.1:
                    self._episodes.remove(episode)
                    evaporated += 1
                else:
                    episode.importance = decayed_importance

            if evaporated > 0:
                logger.info(f"🍂 Evaporated {evaporated} old hive memories (importance < 0.1)")

            return evaporated

    def _cleanup_internal_state(self) -> dict[str, int]:
        """Clean up old episodes (implements SingletonCleanupMixin)."""
        removed = 0
        current_time = time.time()

        # Remove episodes older than TTL
        original_count = len(self._episodes)
        self._episodes = [
            ep
            for ep in self._episodes
            if (current_time - ep.timestamp) <= self._episode_ttl_seconds
        ]
        removed = original_count - len(self._episodes)

        # Rebuild indices
        self._index_by_category.clear()
        self._index_by_agent.clear()

        for ep in self._episodes:
            if ep.category not in self._index_by_category:
                self._index_by_category[ep.category] = []
            self._index_by_category[ep.category].append(ep.episode_id)

            if ep.contributing_agent not in self._index_by_agent:
                self._index_by_agent[ep.contributing_agent] = []
            self._index_by_agent[ep.contributing_agent].append(ep.episode_id)

        return {
            "episodes_removed": removed,
            "episodes_remaining": len(self._episodes),
            "categories": len(self._index_by_category),
            "agents": len(self._index_by_agent),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        if not self._episodes:
            return {
                "total_episodes": 0,
                "categories": [],
                "contributing_agents": [],
                "avg_importance": 0.0,
            }

        categories = list(self._index_by_category.keys())
        agents = list(self._index_by_agent.keys())
        avg_importance = sum(ep.importance for ep in self._episodes) / len(self._episodes)

        # Confirmation statistics
        confirmed_episodes = [ep for ep in self._episodes if ep.confirmed_by]
        avg_confirmations = (
            sum(len(ep.confirmed_by) for ep in confirmed_episodes) / len(confirmed_episodes)
            if confirmed_episodes
            else 0.0
        )

        return {
            "total_episodes": len(self._episodes),
            "capacity": self.capacity,
            "utilization": len(self._episodes) / self.capacity,
            "categories": categories,
            "contributing_agents": agents,
            "avg_importance": avg_importance,
            "confirmed_episodes": len(confirmed_episodes),
            "avg_confirmations": avg_confirmations,
            "most_accessed": sorted(self._episodes, key=lambda ep: ep.access_count, reverse=True)[
                :3
            ],
            "storage_backend": "weaviate" if self._weaviate_available else "in_memory",
        }


# Singleton
_shared_memory: SharedEpisodicMemory | None = None


def get_shared_memory() -> SharedEpisodicMemory:
    """Get or create shared episodic memory."""
    global _shared_memory
    if _shared_memory is None:
        _shared_memory = SharedEpisodicMemory(capacity=1000)
    return _shared_memory


# Alias for backwards compatibility (used in continuous_mind.py)
get_shared_episodic_memory = get_shared_memory


__all__ = [
    "SharedEpisode",
    "SharedEpisodicMemory",
    "get_shared_episodic_memory",  # Backwards compatibility
    "get_shared_memory",
]
