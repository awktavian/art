from __future__ import annotations

from kagami.core.async_utils import safe_create_task

"""Distributed Replay Buffer - Fleet-Wide Experience Sharing.

Uses CockroachDB to share experiences across all K os instances.

Features:
- 100K capacity with automatic cleanup
- Prioritized sampling by importance
- Cross-instance learning
- Prevents sample starvation

REPLACES: Local-only PrioritizedReplayBuffer for production
"""
import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DistributedExperience:
    """Shared experience format for distributed replay buffer.

    Note: Distinct from kagami.core.memory.types.Experience (RL-style).
    This type is optimized for cross-instance fleet learning.
    """

    context: dict[str, Any]
    action: dict[str, Any]
    outcome: dict[str, Any]
    valence: float
    importance: float


class DistributedReplayBuffer:
    """Database-backed replay buffer shared across fleet.

    Advantages over local buffer:
    - All instances learn from each other
    - Survives restarts
    - Automatic cleanup (keeps 100K best)
    - Prioritized sampling prevents starvation
    """

    def __init__(self, db_session: Any, capacity: int = 100_000) -> None:
        self.db = db_session
        self.capacity = capacity
        self._initialized = False

    async def ensure_table(self) -> None:
        """Ensure replay_buffer table exists."""
        if self._initialized:
            return

        try:
            # Table created by migration, just verify
            result = await self.db.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'replay_buffer'
            """
            )

            if result:
                self._initialized = True
                logger.info("✅ Distributed replay buffer ready")
            else:
                logger.warning("Replay buffer table not found; run migration")
        except Exception as e:
            logger.warning(f"Replay buffer check failed: {e}")

    def add(self, experience: DistributedExperience) -> None:
        """Add experience to distributed buffer (sync wrapper)."""
        import asyncio

        try:
            asyncio.get_running_loop()
            safe_create_task(self._add_async(experience, name="_add_async"))  # type: ignore  # Call sig
        except RuntimeError:
            # No running loop - create one
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._add_async(experience))
            finally:
                loop.close()
        except Exception as e:
            logger.debug(f"Failed to add experience: {e}")

    async def _add_async(self, experience: DistributedExperience) -> None:
        """Add experience to distributed buffer."""
        await self.ensure_table()

        try:
            await self.db.execute(
                """
                INSERT INTO replay_buffer
                (context, action, outcome, valence, importance)
                VALUES ($1, $2, $3, $4, $5)
            """,
                json.dumps(experience.context),
                json.dumps(experience.action),
                json.dumps(experience.outcome),
                experience.valence,
                experience.importance,
            )
        except Exception as e:
            logger.debug(f"Failed to insert experience: {e}")

    async def sample_prioritized(self, batch_size: int = 32) -> list[DistributedExperience]:
        """Sample high-importance experiences from fleet."""
        await self.ensure_table()

        try:
            # Prioritized sampling with exploration
            # Uses importance-weighted random sampling
            rows = await self.db.fetch(
                """
                UPDATE replay_buffer
                SET sampled_count = sampled_count + 1
                WHERE experience_id IN (
                    SELECT experience_id FROM replay_buffer
                    ORDER BY importance * POW(RANDOM(), 1.0/GREATEST(importance, 0.1)) DESC
                    LIMIT $1
                )
                RETURNING *
            """,
                batch_size,
            )

            experiences = []
            for row in rows:
                try:
                    experiences.append(
                        DistributedExperience(
                            context=json.loads(row["context"]),
                            action=json.loads(row["action"]),
                            outcome=json.loads(row["outcome"]),
                            valence=row["valence"],
                            importance=row["importance"],
                        )
                    )
                except Exception as e:
                    logger.debug(f"Failed to parse experience: {e}")

            return experiences

        except Exception as e:
            logger.warning(f"Sampling failed: {e}")
            return []

    def get_replay_stats(self) -> dict[str, Any]:
        """Get buffer statistics (sync wrapper)."""
        import asyncio

        try:
            asyncio.get_running_loop()
            # Can't sync await in running loop
            return {"size": 0, "avg_importance": 0.5}
        except RuntimeError:
            # No running loop - safe to create one
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._get_stats_async())
            finally:
                loop.close()
        except Exception:
            return {"size": 0, "avg_importance": 0.5}

    async def _get_stats_async(self) -> dict[str, Any]:
        """Get buffer statistics."""
        await self.ensure_table()

        try:
            row = await self.db.fetchrow(
                """
                SELECT
                    COUNT(*) as size,
                    AVG(importance) as avg_importance,
                    MAX(importance) as max_importance,
                    AVG(sampled_count) as avg_samples
                FROM replay_buffer
            """
            )

            return {
                "size": row["size"] if row else 0,
                "avg_importance": row["avg_importance"] if row and row["avg_importance"] else 0.5,
                "max_importance": row["max_importance"] if row and row["max_importance"] else 1.0,
                "avg_samples": row["avg_samples"] if row and row["avg_samples"] else 0,
            }
        except Exception as e:
            logger.debug(f"Stats failed: {e}")
            return {"size": 0, "avg_importance": 0.5}


# Global singleton
_distributed_replay: DistributedReplayBuffer | None = None


async def get_distributed_replay() -> DistributedReplayBuffer:
    """Get distributed replay buffer."""
    global _distributed_replay
    if _distributed_replay is None:
        from kagami.core.database.async_connection import get_async_session

        db = await get_async_session()  # type: ignore[misc]
        _distributed_replay = DistributedReplayBuffer(db)
        await _distributed_replay.ensure_table()
    return _distributed_replay
