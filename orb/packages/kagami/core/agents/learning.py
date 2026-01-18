"""Agent Learning — Redis persistence and stigmergy patterns.

This module provides:
- Learning event processing
- Engagement tracking
- Adaptation triggers
- Stigmergic knowledge sharing
- A/B testing framework

Stigmergy Pattern:
    Agents leave "pheromone trails" (patterns) that other agents can learn from.
    High-engagement patterns are strengthened, low-engagement patterns decay.

Colony: Crystal (e7) — Verification and Learning
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.agents.schema import AgentState

logger = logging.getLogger(__name__)


# =============================================================================
# Redis Keys
# =============================================================================


def agent_key(agent_id: str) -> str:
    """Get Redis key for agent state."""
    return f"agent:{agent_id}:state"


def engagement_key(agent_id: str) -> str:
    """Get Redis key for engagement data."""
    return f"agent:{agent_id}:engagement"


def secrets_key(agent_id: str) -> str:
    """Get Redis key for found secrets."""
    return f"agent:{agent_id}:secrets"


def patterns_key(agent_id: str) -> str:
    """Get Redis key for stigmergic patterns."""
    return f"agent:{agent_id}:patterns"


def global_patterns_key() -> str:
    """Get Redis key for global stigmergic patterns."""
    return "agents:global:patterns"


def ab_test_key(agent_id: str, test_id: str) -> str:
    """Get Redis key for A/B test data."""
    return f"agent:{agent_id}:ab:{test_id}"


# =============================================================================
# Redis Client (Lazy Import)
# =============================================================================


_redis_client = None


async def get_redis() -> Any:
    """Get Redis client instance."""
    global _redis_client

    if _redis_client is None:
        try:
            import redis.asyncio as redis

            from kagami.core.config import get_settings

            settings = get_settings()
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379")

            _redis_client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        except ImportError:
            logger.warning("Redis not available, using in-memory fallback")
            _redis_client = InMemoryRedis()

    return _redis_client


class InMemoryRedis:
    """In-memory Redis fallback for development."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._ttls: dict[str, float] = {}

    async def get(self, key: str) -> str | None:
        self._check_ttl(key)
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._data[key] = value
        if ex:
            self._ttls[key] = time.time() + ex

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._ttls.pop(key, None)

    async def incr(self, key: str) -> int:
        self._check_ttl(key)
        val = int(self._data.get(key, 0)) + 1
        self._data[key] = str(val)
        return val

    async def incrbyfloat(self, key: str, amount: float) -> float:
        self._check_ttl(key)
        val = float(self._data.get(key, 0)) + amount
        self._data[key] = str(val)
        return val

    async def hget(self, key: str, field: str) -> str | None:
        self._check_ttl(key)
        data = self._data.get(key, {})
        return data.get(field) if isinstance(data, dict) else None

    async def hset(self, key: str, field: str, value: str) -> None:
        self._check_ttl(key)
        if key not in self._data or not isinstance(self._data[key], dict):
            self._data[key] = {}
        self._data[key][field] = value

    async def hgetall(self, key: str) -> dict[str, str]:
        self._check_ttl(key)
        data = self._data.get(key, {})
        return data if isinstance(data, dict) else {}

    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        self._check_ttl(key)
        if key not in self._data or not isinstance(self._data[key], dict):
            self._data[key] = {}
        val = int(self._data[key].get(field, 0)) + amount
        self._data[key][field] = str(val)
        return val

    async def sadd(self, key: str, *values: str) -> int:
        self._check_ttl(key)
        if key not in self._data:
            self._data[key] = set()
        if not isinstance(self._data[key], set):
            self._data[key] = set()
        before = len(self._data[key])
        self._data[key].update(values)
        return len(self._data[key]) - before

    async def smembers(self, key: str) -> set[str]:
        self._check_ttl(key)
        data = self._data.get(key, set())
        return data if isinstance(data, set) else set()

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        if key not in self._data:
            self._data[key] = {}
        for member, score in mapping.items():
            self._data[key][member] = score
        return len(mapping)

    async def zincrby(self, key: str, amount: float, member: str) -> float:
        if key not in self._data:
            self._data[key] = {}
        score = self._data[key].get(member, 0) + amount
        self._data[key][member] = score
        return score

    async def zrange(self, key: str, start: int, end: int, withscores: bool = False) -> list:
        data = self._data.get(key, {})
        if not isinstance(data, dict):
            return []
        items = sorted(data.items(), key=lambda x: x[1])
        if end == -1:
            items = items[start:]
        else:
            items = items[start : end + 1]
        if withscores:
            return [(k, v) for k, v in items]
        return [k for k, v in items]

    async def zrevrange(self, key: str, start: int, end: int, withscores: bool = False) -> list:
        data = self._data.get(key, {})
        if not isinstance(data, dict):
            return []
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)
        if end == -1:
            items = items[start:]
        else:
            items = items[start : end + 1]
        if withscores:
            return [(k, v) for k, v in items]
        return [k for k, v in items]

    async def expire(self, key: str, seconds: int) -> None:
        if key in self._data:
            self._ttls[key] = time.time() + seconds

    def _check_ttl(self, key: str) -> None:
        if key in self._ttls and time.time() > self._ttls[key]:
            self._data.pop(key, None)
            self._ttls.pop(key, None)


# =============================================================================
# Learning Event Processing
# =============================================================================


async def process_learning_event(
    agent: AgentState,
    event_type: str,
    data: dict[str, Any],
) -> list[str]:
    """Process a learning event for an agent.

    Args:
        agent: AgentState instance.
        event_type: Type of learning event.
        data: Event data.

    Returns:
        List of triggered adaptation names.
    """
    redis = await get_redis()
    triggered: list[str] = []

    # Track engagement
    await track_engagement(agent.agent_id, event_type, data)

    # Check for secret discovery
    if event_type == "secret_found":
        secret_id = data.get("secret_id")
        if secret_id:
            agent.secrets_found.add(secret_id)
            await redis.sadd(secrets_key(agent.agent_id), secret_id)

    # Update local agent state
    agent.engagement[event_type] = agent.engagement.get(event_type, 0) + 1

    # Check adaptation thresholds
    triggered = await check_adaptations(agent)

    # Emit stigmergic patterns if enabled
    if agent.schema.i_learn.stigmergy.get("emit_patterns", True):
        await emit_stigmergy_pattern(agent, event_type, data)

    return triggered


async def track_engagement(agent_id: str, event_type: str, data: dict[str, Any]) -> None:
    """Track engagement metrics in Redis.

    Args:
        agent_id: Agent identifier.
        event_type: Type of engagement event.
        data: Event data.
    """
    redis = await get_redis()
    key = engagement_key(agent_id)

    # Increment event count
    await redis.hincrby(key, f"count:{event_type}", 1)

    # Track specific metrics
    if event_type == "scroll":
        depth = data.get("depth", 0)
        await redis.hset(
            key,
            "max_scroll_depth",
            str(max(depth, float(await redis.hget(key, "max_scroll_depth") or 0))),
        )

    elif event_type == "time_on_section":
        section = data.get("section", "unknown")
        duration = data.get("duration", 0)
        await redis.hincrby(key, f"time:{section}", int(duration))

    elif event_type == "interaction":
        element = data.get("element", "unknown")
        await redis.hincrby(key, f"clicks:{element}", 1)

    # Update last activity timestamp
    await redis.hset(key, "last_activity", str(time.time()))


async def check_adaptations(agent: AgentState) -> list[str]:
    """Check if any adaptation thresholds are triggered.

    Args:
        agent: AgentState instance.

    Returns:
        List of triggered adaptation names.
    """
    redis = await get_redis()
    triggered: list[str] = []
    engagement = await redis.hgetall(engagement_key(agent.agent_id))

    for adaptation in agent.schema.i_learn.adaptations:
        condition = adaptation.condition
        action = adaptation.action

        # Simple condition evaluation
        try:
            # Parse condition like "visits >= 3"
            parts = condition.split()
            if len(parts) == 3:
                metric, operator, threshold = parts
                value = float(engagement.get(f"count:{metric}", 0))
                threshold = float(threshold)

                result = False
                if operator == ">=":
                    result = value >= threshold
                elif operator == ">":
                    result = value > threshold
                elif operator == "<=":
                    result = value <= threshold
                elif operator == "<":
                    result = value < threshold
                elif operator == "==":
                    result = value == threshold

                if result:
                    triggered.append(action)
                    logger.info(f"Adaptation triggered for {agent.agent_id}: {action}")

        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")

    return triggered


# =============================================================================
# Stigmergy Patterns
# =============================================================================


@dataclass
class StigmergyPattern:
    """A stigmergic pattern that can be shared across agents.

    Attributes:
        pattern_id: Unique pattern identifier.
        source_agent: Agent that emitted the pattern.
        pattern_type: Type of pattern (engagement, interaction, discovery).
        data: Pattern data.
        strength: Pattern strength (decays over time).
        timestamp: When the pattern was emitted.
    """

    pattern_id: str
    source_agent: str
    pattern_type: str
    data: dict[str, Any]
    strength: float = 1.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "source_agent": self.source_agent,
            "pattern_type": self.pattern_type,
            "data": self.data,
            "strength": self.strength,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StigmergyPattern:
        """Deserialize from dictionary."""
        return cls(**data)


async def emit_stigmergy_pattern(
    agent: AgentState,
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Emit a stigmergic pattern for other agents to learn from.

    Args:
        agent: Agent emitting the pattern.
        event_type: Type of event that triggered the pattern.
        data: Event data.
    """
    redis = await get_redis()

    pattern = StigmergyPattern(
        pattern_id=f"{agent.agent_id}:{event_type}:{int(time.time() * 1000)}",
        source_agent=agent.agent_id,
        pattern_type=event_type,
        data=data,
    )

    # Store in agent's pattern list
    await redis.zadd(patterns_key(agent.agent_id), {pattern.pattern_id: pattern.strength})

    # Store pattern data
    await redis.set(
        f"pattern:{pattern.pattern_id}",
        json.dumps(pattern.to_dict()),
        ex=86400 * 7,  # 7 day TTL
    )

    # Add to global patterns if notable
    if should_share_pattern(event_type, data):
        await redis.zadd(global_patterns_key(), {pattern.pattern_id: pattern.strength})
        logger.debug(f"Emitted stigmergy pattern: {pattern.pattern_id}")


def should_share_pattern(event_type: str, data: dict[str, Any]) -> bool:
    """Determine if a pattern should be shared globally.

    Args:
        event_type: Type of event.
        data: Event data.

    Returns:
        True if pattern should be shared.
    """
    # Share notable events
    notable_events = {"secret_found", "high_engagement", "conversion", "share"}
    return event_type in notable_events


async def receive_stigmergy_patterns(agent: AgentState, limit: int = 10) -> list[StigmergyPattern]:
    """Receive stigmergic patterns from other agents.

    Args:
        agent: Agent receiving patterns.
        limit: Maximum number of patterns to receive.

    Returns:
        List of patterns to learn from.
    """
    if not agent.schema.i_learn.stigmergy.get("receive_patterns", True):
        return []

    redis = await get_redis()
    patterns = []

    # Get top patterns from global pool
    pattern_ids = await redis.zrevrange(global_patterns_key(), 0, limit - 1)

    for pattern_id in pattern_ids:
        # Don't receive own patterns
        if pattern_id.startswith(f"{agent.agent_id}:"):
            continue

        pattern_data = await redis.get(f"pattern:{pattern_id}")
        if pattern_data:
            patterns.append(StigmergyPattern.from_dict(json.loads(pattern_data)))

    return patterns


async def apply_stigmergy_learning(agent: AgentState, patterns: list[StigmergyPattern]) -> None:
    """Apply learning from stigmergic patterns.

    Args:
        agent: Agent to apply learning to.
        patterns: Patterns to learn from.
    """
    for pattern in patterns:
        # Log the learning event
        logger.info(f"Agent {agent.agent_id} learning from pattern {pattern.pattern_id}")

        # Apply pattern-specific learning
        if pattern.pattern_type == "secret_found":
            # Increase hint visibility
            pass
        elif pattern.pattern_type == "high_engagement":
            # Boost similar content
            pass


async def decay_stigmergy_patterns(decay_rate: float = 0.95) -> None:
    """Decay all stigmergy patterns (run periodically).

    Args:
        decay_rate: Decay multiplier (0.95 = 5% decay).
    """
    redis = await get_redis()

    # Get all pattern IDs
    pattern_ids = await redis.zrange(global_patterns_key(), 0, -1, withscores=True)

    for pattern_id, strength in pattern_ids:
        new_strength = strength * decay_rate

        if new_strength < 0.01:
            # Remove weak patterns
            await redis.delete(f"pattern:{pattern_id}")
            await redis.zrem(global_patterns_key(), pattern_id)
        else:
            await redis.zadd(global_patterns_key(), {pattern_id: new_strength})


# =============================================================================
# A/B Testing
# =============================================================================


@dataclass
class ABTest:
    """A/B test configuration.

    Attributes:
        test_id: Unique test identifier.
        variants: List of variant names.
        weights: Weights for each variant (must sum to 1).
        metrics: Metrics to track.
        start_time: Test start timestamp.
        end_time: Test end timestamp (None = ongoing).
    """

    test_id: str
    variants: list[str]
    weights: list[float] | None = None
    metrics: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None

    def get_variant(self, user_id: str) -> str:
        """Get consistent variant for a user.

        Args:
            user_id: User identifier.

        Returns:
            Assigned variant name.
        """
        import hashlib

        # Deterministic assignment based on user_id and test_id
        hash_input = f"{user_id}:{self.test_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)

        weights = self.weights or [1.0 / len(self.variants)] * len(self.variants)
        cumulative = 0
        threshold = (hash_value % 1000) / 1000

        for variant, weight in zip(self.variants, weights, strict=False):
            cumulative += weight
            if threshold < cumulative:
                return variant

        return self.variants[-1]


async def create_ab_test(agent_id: str, test: ABTest) -> None:
    """Create an A/B test for an agent.

    Args:
        agent_id: Agent identifier.
        test: A/B test configuration.
    """
    redis = await get_redis()
    key = ab_test_key(agent_id, test.test_id)

    await redis.set(
        key,
        json.dumps(
            {
                "test_id": test.test_id,
                "variants": test.variants,
                "weights": test.weights,
                "metrics": test.metrics,
                "start_time": test.start_time,
                "end_time": test.end_time,
            }
        ),
    )

    logger.info(f"Created A/B test {test.test_id} for agent {agent_id}")


async def track_ab_event(
    agent_id: str,
    test_id: str,
    variant: str,
    metric: str,
    value: float = 1.0,
) -> None:
    """Track an event for an A/B test.

    Args:
        agent_id: Agent identifier.
        test_id: Test identifier.
        variant: Variant that was shown.
        metric: Metric name.
        value: Metric value.
    """
    redis = await get_redis()
    key = f"{ab_test_key(agent_id, test_id)}:results"

    await redis.hincrby(key, f"{variant}:count", 1)
    await redis.incrbyfloat(key, f"{variant}:{metric}", value)


async def get_ab_results(agent_id: str, test_id: str) -> dict[str, Any]:
    """Get results for an A/B test.

    Args:
        agent_id: Agent identifier.
        test_id: Test identifier.

    Returns:
        Test results with variant statistics.
    """
    redis = await get_redis()

    # Get test config
    config_key = ab_test_key(agent_id, test_id)
    config_data = await redis.get(config_key)
    if not config_data:
        return {"error": "Test not found"}

    config = json.loads(config_data)

    # Get results
    results_key = f"{config_key}:results"
    results = await redis.hgetall(results_key)

    # Parse results by variant
    variant_results = {}
    for variant in config["variants"]:
        variant_results[variant] = {
            "count": int(results.get(f"{variant}:count", 0)),
        }
        for metric in config["metrics"]:
            variant_results[variant][metric] = float(results.get(f"{variant}:{metric}", 0))

    return {
        "test_id": test_id,
        "config": config,
        "results": variant_results,
    }


# =============================================================================
# State Persistence
# =============================================================================


async def save_agent_state(agent: AgentState) -> None:
    """Persist agent state to Redis.

    Args:
        agent: AgentState to save.
    """
    redis = await get_redis()

    await redis.set(
        agent_key(agent.agent_id),
        json.dumps(
            {
                "memory": agent.memory,
                "secrets_found": list(agent.secrets_found),
                "engagement": agent.engagement,
                "last_interaction": agent.last_interaction,
            }
        ),
    )


async def load_agent_state(agent: AgentState) -> None:
    """Load agent state from Redis.

    Args:
        agent: AgentState to populate.
    """
    redis = await get_redis()

    data = await redis.get(agent_key(agent.agent_id))
    if data:
        state = json.loads(data)
        agent.memory = state.get("memory", {})
        agent.secrets_found = set(state.get("secrets_found", []))
        agent.engagement = state.get("engagement", {})
        agent.last_interaction = state.get("last_interaction", 0)


async def clear_agent_state(agent_id: str) -> None:
    """Clear all persisted state for an agent.

    Args:
        agent_id: Agent identifier.
    """
    redis = await get_redis()

    await redis.delete(agent_key(agent_id))
    await redis.delete(engagement_key(agent_id))
    await redis.delete(secrets_key(agent_id))
    await redis.delete(patterns_key(agent_id))


# =============================================================================
# Background Tasks
# =============================================================================


async def start_learning_background_tasks() -> asyncio.Task:
    """Start background tasks for learning system.

    Returns:
        Background task handle.
    """

    async def background_loop() -> None:
        while True:
            try:
                # Decay stigmergy patterns every hour
                await decay_stigmergy_patterns()
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Learning background task error: {e}")
                await asyncio.sleep(60)

    return asyncio.create_task(background_loop())


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    # A/B Testing
    "ABTest",
    # Stigmergy
    "StigmergyPattern",
    "apply_stigmergy_learning",
    "check_adaptations",
    "clear_agent_state",
    "create_ab_test",
    "decay_stigmergy_patterns",
    "emit_stigmergy_pattern",
    "get_ab_results",
    # Redis
    "get_redis",
    "load_agent_state",
    # Event Processing
    "process_learning_event",
    "receive_stigmergy_patterns",
    # State Persistence
    "save_agent_state",
    # Background Tasks
    "start_learning_background_tasks",
    "track_ab_event",
    "track_engagement",
]
