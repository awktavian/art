"""Learning Pipeline — Unified Cross-Service Learning with Notion Persistence.

This module creates a unified learning feedback loop that:
1. Records service actions across all colonies
2. Learns which service-colony combinations succeed
3. Persists patterns to Notion knowledge base
4. Feeds learnings back to routing decisions

Architecture:
    ┌────────────────────────────────────────────────────────────────────────┐
    │                       LEARNING PIPELINE                                 │
    │                                                                        │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                        OBSERVATION                                │  │
    │  │                                                                   │  │
    │  │  Colony Actions ──► Service Calls ──► Results                     │  │
    │  │       │                   │                │                      │  │
    │  │       └───────────────────┴────────────────┘                      │  │
    │  │                           │                                       │  │
    │  │                     Record Receipt                                │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    │                              ↓                                          │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                        LEARNING                                   │  │
    │  │                                                                   │  │
    │  │  Extract Patterns ──► Update Stigmergy ──► Calculate Utilities    │  │
    │  │       │                     │                     │               │  │
    │  │       └─────────────────────┴─────────────────────┘               │  │
    │  │                             │                                     │  │
    │  │                       Pattern Cache                               │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    │                              ↓                                          │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                        PERSISTENCE                                │  │
    │  │                                                                   │  │
    │  │  Pattern Cache ──► Notion KB ──► Pattern Database                 │  │
    │  │       │                │                │                         │  │
    │  │       └────────────────┴────────────────┘                         │  │
    │  │                        │                                          │  │
    │  │                  Searchable KB                                    │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    │                              ↓                                          │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                        FEEDBACK                                   │  │
    │  │                                                                   │  │
    │  │  Query KB ──► Enhance Routing ──► Better Decisions                │  │
    │  │       │              │                    │                       │  │
    │  │       └──────────────┴────────────────────┘                       │  │
    │  │                           │                                       │  │
    │  │                      Next Action                                  │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────────────────────┘

Usage:
    from kagami.core.orchestration.learning_pipeline import get_learning_pipeline

    pipeline = await get_learning_pipeline()

    # Record an action
    await pipeline.record_action(
        colony="forge",
        service="github",
        action="GITHUB_CREATE_A_REFERENCE",
        success=True,
        duration_ms=150,
    )

    # Persist to Notion (called periodically)
    await pipeline.persist_patterns()

    # Get routing suggestions
    suggestions = pipeline.get_routing_suggestions("create branch")
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.orchestration.notion_kb import NotionKnowledgeBase
    from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Persistence configuration
DEFAULT_PERSIST_INTERVAL = 300.0  # 5 minutes
DEFAULT_MIN_PATTERN_COUNT = 3  # Minimum executions before persisting
DEFAULT_MIN_SUCCESS_RATE = 0.3  # Minimum success rate to persist


@dataclass
class ActionRecord:
    """Record of a service action."""

    colony: str
    service: str
    action: str
    success: bool
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    context: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class LearningMetrics:
    """Metrics for the learning pipeline."""

    total_actions_recorded: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    patterns_persisted: int = 0
    last_persist_time: float = 0.0
    active_colonies: set[str] = field(default_factory=set)
    active_services: set[str] = field(default_factory=set)


@dataclass
class RoutingSuggestion:
    """A routing suggestion based on learned patterns."""

    colony: str
    service: str
    confidence: float
    success_rate: float
    reason: str
    alternative_colonies: list[str] = field(default_factory=list)


# =============================================================================
# LEARNING PIPELINE
# =============================================================================


class LearningPipeline:
    """Unified cross-service learning pipeline.

    This class orchestrates the learning feedback loop:

    1. Observation: Record all service actions across colonies
    2. Learning: Extract patterns and update stigmergy
    3. Persistence: Store patterns in Notion knowledge base
    4. Feedback: Provide routing suggestions based on learnings
    """

    def __init__(
        self,
        persist_interval: float = DEFAULT_PERSIST_INTERVAL,
        min_pattern_count: int = DEFAULT_MIN_PATTERN_COUNT,
        min_success_rate: float = DEFAULT_MIN_SUCCESS_RATE,
    ) -> None:
        """Initialize learning pipeline.

        Args:
            persist_interval: Seconds between persistence operations
            min_pattern_count: Minimum executions before persisting
            min_success_rate: Minimum success rate to persist
        """
        self.persist_interval = persist_interval
        self.min_pattern_count = min_pattern_count
        self.min_success_rate = min_success_rate

        self._stigmergy: StigmergyLearner | None = None
        self._notion_kb: NotionKnowledgeBase | None = None
        self._initialized = False

        # Action buffer for batch processing
        self._action_buffer: list[ActionRecord] = []
        self._buffer_lock = asyncio.Lock()

        # Metrics
        self.metrics = LearningMetrics()

        # Background persistence task
        self._persist_task: asyncio.Task[None] | None = None

    async def initialize(self) -> bool:
        """Initialize the learning pipeline.

        Returns:
            True if successfully initialized
        """
        if self._initialized:
            return True

        try:
            # Initialize stigmergy learner
            from kagami.core.unified_agents.memory.stigmergy import StigmergyLearner

            self._stigmergy = StigmergyLearner(
                enable_persistence=True,
                enable_game_model=True,
                adaptive_mode=True,
            )
            await self._stigmergy.load_patterns()

            # Initialize Notion KB
            from kagami.core.orchestration.notion_kb import get_notion_kb

            self._notion_kb = get_notion_kb()
            await self._notion_kb.initialize()

            self._initialized = True
            logger.info("✅ LearningPipeline initialized")

            # Start background persistence task
            self._persist_task = asyncio.create_task(self._persist_loop())

            return True

        except Exception as e:
            logger.error(f"Failed to initialize LearningPipeline: {e}")
            return False

    async def shutdown(self) -> None:
        """Shutdown the learning pipeline."""
        # Cancel persistence task
        if self._persist_task is not None:
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass

        # Final persistence
        await self.persist_patterns()

        logger.info("LearningPipeline shutdown complete")

    # =========================================================================
    # OBSERVATION PHASE
    # =========================================================================

    async def record_action(
        self,
        colony: str,
        service: str,
        action: str,
        success: bool,
        duration_ms: float = 0.0,
        context: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record a service action.

        Args:
            colony: Colony that executed the action
            service: Service used
            action: Action executed
            success: Whether it succeeded
            duration_ms: Execution duration in milliseconds
            context: Optional context
            error_message: Error message if failed
        """
        record = ActionRecord(
            colony=colony,
            service=service,
            action=action,
            success=success,
            duration_ms=duration_ms,
            context=context or {},
            error_message=error_message,
        )

        async with self._buffer_lock:
            self._action_buffer.append(record)

        # Update metrics
        self.metrics.total_actions_recorded += 1
        if success:
            self.metrics.successful_actions += 1
        else:
            self.metrics.failed_actions += 1
        self.metrics.active_colonies.add(colony)
        self.metrics.active_services.add(service)

        # Record to stigmergy
        if self._stigmergy is not None:
            self._stigmergy.record_service_action(
                colony=colony,
                service=service,
                action=action,
                success=success,
                duration_ms=duration_ms,
                context=context,
            )

        logger.debug(
            f"Recorded action: {colony}→{service}:{action} "
            f"(success={success}, total={self.metrics.total_actions_recorded})"
        )

    # =========================================================================
    # LEARNING PHASE
    # =========================================================================

    def get_learned_patterns(
        self,
        min_count: int | None = None,
        min_success_rate: float | None = None,
    ) -> list[dict[str, Any]]:
        """Get learned patterns from stigmergy.

        Args:
            min_count: Minimum execution count
            min_success_rate: Minimum success rate

        Returns:
            List of pattern dictionaries
        """
        if self._stigmergy is None:
            return []

        return self._stigmergy.get_cross_service_patterns(
            min_count=min_count or self.min_pattern_count,
            min_success_rate=min_success_rate or self.min_success_rate,
        )

    def get_colony_affinities(self, colony: str) -> dict[str, float]:
        """Get service affinities for a colony.

        Args:
            colony: Colony name

        Returns:
            Dict mapping service names to affinity scores
        """
        if self._stigmergy is None:
            return {}

        return self._stigmergy.get_colony_service_affinity(colony)

    def get_best_colony(self, service: str) -> str | None:
        """Get best colony for a service.

        Args:
            service: Service name

        Returns:
            Best colony name or None
        """
        if self._stigmergy is None:
            return None

        return self._stigmergy.get_best_colony_for_service(service)

    # =========================================================================
    # PERSISTENCE PHASE
    # =========================================================================

    async def persist_patterns(self) -> int:
        """Persist learned patterns to Notion KB.

        Returns:
            Number of patterns persisted
        """
        if self._notion_kb is None or not self._notion_kb._initialized:
            return 0

        patterns = self.get_learned_patterns()
        persisted = 0

        for pattern in patterns:
            try:
                from kagami.core.orchestration.notion_kb import PatternCategory

                # Determine category from service
                service = pattern.get("service", "")
                category_map = {
                    "github": PatternCategory.INTEGRATION,
                    "linear": PatternCategory.INTEGRATION,
                    "slack": PatternCategory.INTEGRATION,
                    "notion": PatternCategory.INTEGRATION,
                }
                category = category_map.get(service, PatternCategory.OTHER)

                await self._notion_kb.store_pattern(
                    name=f"{pattern['colony']}→{pattern['service']}:{pattern['action']}",
                    category=category,
                    description=(
                        f"Colony {pattern['colony']} uses {pattern['service']} "
                        f"action {pattern['action']} with {pattern['success_rate'] * 100:.0f}% success rate"
                    ),
                    success_rate=pattern.get("success_rate", 0.0),
                    usage_count=pattern.get("total_count", 0),
                    colonies_involved=[pattern.get("colony", "")],
                    services_involved=[pattern.get("service", "")],
                )
                persisted += 1

            except Exception as e:
                logger.warning(f"Failed to persist pattern: {e}")

        self.metrics.patterns_persisted += persisted
        self.metrics.last_persist_time = time.time()

        if persisted > 0:
            logger.info(f"✅ Persisted {persisted} patterns to Notion KB")

        return persisted

    async def _persist_loop(self) -> None:
        """Background loop for periodic persistence."""
        while True:
            try:
                await asyncio.sleep(self.persist_interval)
                await self.persist_patterns()

                # Also save stigmergy patterns
                if self._stigmergy is not None:
                    await self._stigmergy.save_patterns()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Persist loop error: {e}")

    # =========================================================================
    # FEEDBACK PHASE
    # =========================================================================

    def get_routing_suggestions(
        self,
        task_description: str,
        services_needed: list[str] | None = None,
    ) -> list[RoutingSuggestion]:
        """Get routing suggestions based on learned patterns.

        Args:
            task_description: Description of the task
            services_needed: Optional list of required services

        Returns:
            List of routing suggestions
        """
        suggestions = []

        if self._stigmergy is None:
            return suggestions

        # Get best colonies for each service
        services = services_needed or ["github", "linear", "notion", "slack"]

        for service in services:
            best_colony = self.get_best_colony(service)
            if best_colony is None:
                continue

            # Get affinity data
            affinities = self.get_colony_affinities(best_colony)
            success_rate = affinities.get(service, 0.5)

            # Calculate confidence based on pattern count
            patterns = self.get_learned_patterns()
            service_patterns = [p for p in patterns if p.get("service") == service]
            confidence = min(1.0, len(service_patterns) * 0.1)

            # Find alternatives
            alternatives = []
            for pattern in service_patterns:
                if pattern.get("colony") != best_colony:
                    alternatives.append(pattern.get("colony", ""))

            suggestions.append(
                RoutingSuggestion(
                    colony=best_colony,
                    service=service,
                    confidence=confidence,
                    success_rate=success_rate,
                    reason=f"Learned from {len(service_patterns)} patterns",
                    alternative_colonies=list(set(alternatives))[:3],
                )
            )

        # Sort by confidence
        suggestions.sort(key=lambda s: s.confidence, reverse=True)

        return suggestions

    def enhance_routing_context(
        self,
        colony: str,
        action: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Enhance routing context with learned patterns.

        Args:
            colony: Target colony
            action: Action being routed
            context: Current routing context

        Returns:
            Enhanced context with learned hints
        """
        enhanced = dict(context)

        if self._stigmergy is None:
            return enhanced

        # Get colony affinities
        affinities = self.get_colony_affinities(colony)
        enhanced["service_affinities"] = affinities

        # Get relevant patterns
        patterns = self.get_learned_patterns()
        colony_patterns = [p for p in patterns if p.get("colony") == colony]
        enhanced["learned_patterns"] = colony_patterns[:5]  # Top 5

        # Add success prediction
        if colony_patterns:
            avg_success = sum(p.get("success_rate", 0.5) for p in colony_patterns) / len(
                colony_patterns
            )
            enhanced["predicted_success_rate"] = avg_success

        enhanced["_learning_enhanced"] = True

        return enhanced

    # =========================================================================
    # STATUS
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get pipeline status summary."""
        return {
            "initialized": self._initialized,
            "total_actions": self.metrics.total_actions_recorded,
            "success_rate": (
                self.metrics.successful_actions / self.metrics.total_actions_recorded
                if self.metrics.total_actions_recorded > 0
                else 0.0
            ),
            "patterns_persisted": self.metrics.patterns_persisted,
            "last_persist": self.metrics.last_persist_time,
            "active_colonies": list(self.metrics.active_colonies),
            "active_services": list(self.metrics.active_services),
            "buffer_size": len(self._action_buffer),
            "persist_task_running": (
                self._persist_task is not None and not self._persist_task.done()
            ),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_learning_pipeline: LearningPipeline | None = None


def get_learning_pipeline() -> LearningPipeline:
    """Get the global learning pipeline instance."""
    global _learning_pipeline
    if _learning_pipeline is None:
        _learning_pipeline = LearningPipeline()
    return _learning_pipeline


async def initialize_learning_pipeline() -> LearningPipeline:
    """Initialize and return the global learning pipeline."""
    pipeline = get_learning_pipeline()
    await pipeline.initialize()
    return pipeline


__all__ = [
    "ActionRecord",
    "LearningMetrics",
    "LearningPipeline",
    "RoutingSuggestion",
    "get_learning_pipeline",
    "initialize_learning_pipeline",
]
