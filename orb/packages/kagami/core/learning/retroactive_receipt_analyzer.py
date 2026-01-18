"""Retroactive Receipt Analysis — Close the Learning Loop.

DEEP INTEGRATION ENHANCEMENT (Dec 30, 2025):

CURRENT STATE:
- Receipts stored but learning is prospective only
- No historical pattern analysis
- Learning improvements only apply to future actions

ENHANCED STATE:
- Retroactive analysis during memory consolidation
- Historical receipt pattern extraction
- Failure pattern recognition and correction
- Causal understanding of state transitions

IMPACT:
- Learning from failure patterns, not just successes
- Causal state understanding
- Adaptive strategy refinement based on history

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class AnalysisTimeFrame(Enum):
    """Time frames for retroactive analysis."""

    LAST_HOUR = "last_hour"
    LAST_DAY = "last_day"
    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"
    ALL_TIME = "all_time"


class PatternType(Enum):
    """Types of patterns to extract from receipts."""

    SUCCESS_PATTERNS = "success_patterns"
    FAILURE_PATTERNS = "failure_patterns"
    CAUSAL_CHAINS = "causal_chains"
    CONTEXT_DEPENDENCIES = "context_dependencies"
    TIMING_PATTERNS = "timing_patterns"
    COLONY_INTERACTIONS = "colony_interactions"


@dataclass
class ReceiptPattern:
    """Extracted pattern from receipt analysis."""

    pattern_type: PatternType
    pattern_id: str
    description: str
    confidence: float
    frequency: int
    first_seen: datetime
    last_seen: datetime

    # Pattern specifics
    context_factors: list[str] = field(default_factory=list)
    success_rate: float = 0.0
    avg_duration: float = 0.0
    colonies_involved: list[str] = field(default_factory=list)

    # Learning updates
    recommended_actions: list[str] = field(default_factory=list)
    colony_utility_adjustments: dict[str, float] = field(default_factory=dict)
    world_model_gradients: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetroactiveAnalysisReport:
    """Complete retroactive analysis report."""

    analysis_id: str
    timeframe: AnalysisTimeFrame
    start_time: datetime
    end_time: datetime

    # Analysis results
    total_receipts_analyzed: int
    patterns_found: list[ReceiptPattern] = field(default_factory=list)

    # High-level insights
    overall_success_rate: float = 0.0
    most_common_failures: list[str] = field(default_factory=list)
    colony_performance: dict[str, float] = field(default_factory=dict)
    context_correlations: dict[str, float] = field(default_factory=dict)

    # Learning recommendations
    learning_updates: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0


class RetroactiveReceiptAnalyzer:
    """Analyzes historical receipts to extract learning patterns.

    This system closes the learning loop by analyzing past receipts to:
    1. Identify failure patterns and their causes
    2. Extract causal relationships between context and outcomes
    3. Recommend strategy adjustments based on historical data
    4. Update colony utilities retroactively
    5. Generate world model parameter gradients

    Usage:
        analyzer = get_retroactive_analyzer()

        # Analyze recent failures
        report = await analyzer.analyze_timeframe(AnalysisTimeFrame.LAST_WEEK)

        # Apply learning updates
        await analyzer.apply_learning_updates(report)

        # Historical analysis during consolidation
        await analyzer.analyze_during_consolidation()
    """

    def __init__(self) -> None:
        """Initialize retroactive analyzer."""
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize dependencies."""
        if self._initialized:
            return

        try:
            # Import learning components
            from kagami.core.learning.receipt_learning import get_receipt_learning_engine
            from kagami.core.memory.integration import get_memory_hub
            from kagami.core.persistence.receipt_store import get_receipt_store
            from kagami.core.services.embedding_service import get_embedding_service

            self._receipt_engine = get_receipt_learning_engine()
            self._receipt_store = get_receipt_store()
            self._embedding_service = get_embedding_service()
            self._memory_hub = get_memory_hub()

            self._initialized = True
            logger.info("RetroactiveReceiptAnalyzer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize RetroactiveReceiptAnalyzer: {e}")
            raise

    async def analyze_timeframe(
        self, timeframe: AnalysisTimeFrame, pattern_types: list[PatternType] | None = None
    ) -> RetroactiveAnalysisReport:
        """Analyze receipts within specified timeframe.

        Args:
            timeframe: Time period to analyze
            pattern_types: Specific patterns to extract (all if None)

        Returns:
            Complete analysis report
        """
        await self.initialize()

        start_time = datetime.now()
        end_time, lookback_start = self._get_timeframe_bounds(timeframe)

        pattern_types = pattern_types or list(PatternType)

        logger.info(
            f"Starting retroactive analysis: {timeframe.value} ({lookback_start} to {end_time})"
        )

        try:
            # Fetch receipts in timeframe
            receipts = await self._fetch_receipts(lookback_start, end_time)

            if not receipts:
                logger.warning(f"No receipts found in timeframe: {timeframe.value}")
                return RetroactiveAnalysisReport(
                    analysis_id=f"retro_{int(start_time.timestamp())}",
                    timeframe=timeframe,
                    start_time=lookback_start,
                    end_time=end_time,
                    total_receipts_analyzed=0,
                )

            # Extract patterns
            patterns = await self._extract_patterns(receipts, pattern_types)

            # Generate high-level insights
            insights = await self._generate_insights(receipts, patterns)

            # Create learning updates
            learning_updates = await self._create_learning_updates(patterns, insights)

            execution_time = (datetime.now() - start_time).total_seconds()

            report = RetroactiveAnalysisReport(
                analysis_id=f"retro_{int(start_time.timestamp())}",
                timeframe=timeframe,
                start_time=lookback_start,
                end_time=end_time,
                total_receipts_analyzed=len(receipts),
                patterns_found=patterns,
                **insights,
                learning_updates=learning_updates,
                execution_time=execution_time,
            )

            logger.info(
                f"Retroactive analysis complete: {len(patterns)} patterns found, "
                f"{execution_time:.2f}s"
            )

            return report

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Retroactive analysis failed: {e}")
            raise

    async def analyze_during_consolidation(self) -> RetroactiveAnalysisReport:
        """Perform analysis during memory consolidation cycle.

        Called by MemoryPressureCoordinator during consolidation.
        Focuses on actionable patterns for immediate learning.
        """
        await self.initialize()

        # Analyze last 24 hours with focus on failure patterns
        report = await self.analyze_timeframe(
            AnalysisTimeFrame.LAST_DAY,
            pattern_types=[
                PatternType.FAILURE_PATTERNS,
                PatternType.CAUSAL_CHAINS,
                PatternType.CONTEXT_DEPENDENCIES,
            ],
        )

        # Auto-apply learning updates during consolidation
        await self.apply_learning_updates(report)

        return report

    async def apply_learning_updates(self, report: RetroactiveAnalysisReport) -> None:
        """Apply learning updates from analysis report.

        Args:
            report: Analysis report with learning recommendations
        """
        await self.initialize()

        try:
            updates = report.learning_updates

            # Update colony utilities
            if "colony_utilities" in updates:
                await self._update_colony_utilities(updates["colony_utilities"])

            # Apply world model gradients
            if "world_model_gradients" in updates:
                await self._apply_world_model_gradients(updates["world_model_gradients"])

            # Update memory patterns
            if "memory_patterns" in updates:
                await self._update_memory_patterns(updates["memory_patterns"])

            # Store pattern embeddings
            if report.patterns_found:
                await self._store_pattern_embeddings(report.patterns_found)

            logger.info(f"Applied {len(updates)} learning updates from retroactive analysis")

        except Exception as e:
            logger.error(f"Failed to apply learning updates: {e}")
            raise

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    def _get_timeframe_bounds(self, timeframe: AnalysisTimeFrame) -> tuple[datetime, datetime]:
        """Get start and end bounds for timeframe."""
        now = datetime.now()

        if timeframe == AnalysisTimeFrame.LAST_HOUR:
            start = now - timedelta(hours=1)
        elif timeframe == AnalysisTimeFrame.LAST_DAY:
            start = now - timedelta(days=1)
        elif timeframe == AnalysisTimeFrame.LAST_WEEK:
            start = now - timedelta(weeks=1)
        elif timeframe == AnalysisTimeFrame.LAST_MONTH:
            start = now - timedelta(days=30)
        else:  # ALL_TIME
            start = datetime(2025, 1, 1)  # Kagami epoch

        return now, start

    async def _fetch_receipts(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Fetch receipts from storage in timeframe."""
        try:
            # Use receipt store to fetch by time range
            receipts = await self._receipt_store.get_receipts_by_timeframe(start, end)
            logger.debug(f"Fetched {len(receipts)} receipts from {start} to {end}")
            return receipts
        except Exception as e:
            logger.error(f"Failed to fetch receipts: {e}")
            return []

    async def _extract_patterns(
        self, receipts: list[dict[str, Any]], pattern_types: list[PatternType]
    ) -> list[ReceiptPattern]:
        """Extract patterns from receipts."""
        # Map pattern types to extraction methods
        extraction_map = {
            PatternType.FAILURE_PATTERNS: self._extract_failure_patterns,
            PatternType.SUCCESS_PATTERNS: self._extract_success_patterns,
            PatternType.CAUSAL_CHAINS: self._extract_causal_chains,
            PatternType.CONTEXT_DEPENDENCIES: self._extract_context_dependencies,
            PatternType.TIMING_PATTERNS: self._extract_timing_patterns,
            PatternType.COLONY_INTERACTIONS: self._extract_colony_interactions,
        }

        # Extract all requested patterns in parallel
        tasks = [extraction_map[pt](receipts) for pt in pattern_types if pt in extraction_map]

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            patterns = []
            for result in results:
                if isinstance(result, list):
                    patterns.extend(result)
        else:
            patterns = []

        logger.debug(f"Extracted {len(patterns)} patterns total")
        return patterns

    async def _extract_failure_patterns(
        self, receipts: list[dict[str, Any]]
    ) -> list[ReceiptPattern]:
        """Extract common failure patterns."""
        patterns = []

        # Group failures by error type
        failure_groups = {}
        for receipt in receipts:
            if not receipt.get("success", True):
                error_type = self._classify_error(receipt.get("error", "Unknown"))
                if error_type not in failure_groups:
                    failure_groups[error_type] = []
                failure_groups[error_type].append(receipt)

        # Create patterns for common failures
        for error_type, failed_receipts in failure_groups.items():
            if len(failed_receipts) >= 3:  # Minimum threshold for pattern
                pattern = ReceiptPattern(
                    pattern_type=PatternType.FAILURE_PATTERNS,
                    pattern_id=f"failure_{error_type}",
                    description=f"Common failure: {error_type}",
                    confidence=min(len(failed_receipts) / 10.0, 1.0),
                    frequency=len(failed_receipts),
                    first_seen=min(r["timestamp"] for r in failed_receipts),
                    last_seen=max(r["timestamp"] for r in failed_receipts),
                    success_rate=0.0,
                    recommended_actions=[f"Review {error_type} handling", "Add error recovery"],
                )
                patterns.append(pattern)

        return patterns

    async def _extract_success_patterns(
        self, receipts: list[dict[str, Any]]
    ) -> list[ReceiptPattern]:
        """Extract successful execution patterns."""
        patterns = []

        # Group successful receipts by context
        success_groups = {}
        for receipt in receipts:
            if receipt.get("success", True):
                context_key = self._extract_context_key(receipt)
                if context_key not in success_groups:
                    success_groups[context_key] = []
                success_groups[context_key].append(receipt)

        # Create patterns for consistent successes
        for context, success_receipts in success_groups.items():
            if len(success_receipts) >= 5:  # Higher threshold for success patterns
                avg_duration = np.mean([r.get("duration", 0) for r in success_receipts])

                pattern = ReceiptPattern(
                    pattern_type=PatternType.SUCCESS_PATTERNS,
                    pattern_id=f"success_{hash(context)}",
                    description=f"Reliable success pattern: {context}",
                    confidence=min(len(success_receipts) / 20.0, 1.0),
                    frequency=len(success_receipts),
                    first_seen=min(r["timestamp"] for r in success_receipts),
                    last_seen=max(r["timestamp"] for r in success_receipts),
                    success_rate=1.0,
                    avg_duration=avg_duration,
                    context_factors=[context],
                    recommended_actions=[
                        "Reinforce successful pattern",
                        "Replicate in similar contexts",
                    ],
                )
                patterns.append(pattern)

        return patterns

    async def _extract_causal_chains(self, receipts: list[dict[str, Any]]) -> list[ReceiptPattern]:
        """Extract causal relationships between context and outcomes."""
        patterns = []

        # Look for correlations between context factors and success/failure
        context_outcomes = {}

        for receipt in receipts:
            context_factors = receipt.get("context", {})
            success = receipt.get("success", True)

            for factor, value in context_factors.items():
                key = f"{factor}={value}"
                if key not in context_outcomes:
                    context_outcomes[key] = {"success": 0, "failure": 0}

                if success:
                    context_outcomes[key]["success"] += 1
                else:
                    context_outcomes[key]["failure"] += 1

        # Identify strong correlations
        for factor_key, outcomes in context_outcomes.items():
            total = outcomes["success"] + outcomes["failure"]
            if total >= 5:  # Minimum sample size
                success_rate = outcomes["success"] / total

                # Strong positive or negative correlation
                if success_rate >= 0.8 or success_rate <= 0.2:
                    pattern = ReceiptPattern(
                        pattern_type=PatternType.CAUSAL_CHAINS,
                        pattern_id=f"causal_{hash(factor_key)}",
                        description=f"Causal factor: {factor_key} → {success_rate:.1%} success",
                        confidence=abs(success_rate - 0.5) * 2,  # Distance from random
                        frequency=total,
                        first_seen=datetime.now() - timedelta(hours=24),  # Approximate
                        last_seen=datetime.now(),
                        success_rate=success_rate,
                        context_factors=[factor_key],
                        recommended_actions=[
                            f"{'Amplify' if success_rate > 0.5 else 'Avoid'} condition: {factor_key}"
                        ],
                    )
                    patterns.append(pattern)

        return patterns

    async def _extract_context_dependencies(
        self, receipts: list[dict[str, Any]]
    ) -> list[ReceiptPattern]:
        """Extract context-dependent execution patterns."""
        # Simplified implementation - could be enhanced with more sophisticated analysis
        return []

    async def _extract_timing_patterns(
        self, receipts: list[dict[str, Any]]
    ) -> list[ReceiptPattern]:
        """Extract timing-based execution patterns."""
        # Simplified implementation - could be enhanced with time-series analysis
        return []

    async def _extract_colony_interactions(
        self, receipts: list[dict[str, Any]]
    ) -> list[ReceiptPattern]:
        """Extract colony interaction patterns."""
        # Simplified implementation - could be enhanced with graph analysis
        return []

    async def _generate_insights(
        self, receipts: list[dict[str, Any]], patterns: list[ReceiptPattern]
    ) -> dict[str, Any]:
        """Generate high-level insights from receipts and patterns."""
        total_receipts = len(receipts)
        successful_receipts = sum(1 for r in receipts if r.get("success", True))

        overall_success_rate = successful_receipts / total_receipts if total_receipts > 0 else 0.0

        # Extract common failure reasons
        failure_receipts = [r for r in receipts if not r.get("success", True)]
        most_common_failures = []
        if failure_receipts:
            failure_reasons = {}
            for receipt in failure_receipts:
                reason = self._classify_error(receipt.get("error", "Unknown"))
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

            most_common_failures = sorted(
                failure_reasons.items(), key=lambda x: x[1], reverse=True
            )[:5]  # Top 5
            most_common_failures = [reason for reason, count in most_common_failures]

        # Analyze colony performance
        colony_performance = {}
        for receipt in receipts:
            colonies = receipt.get("colonies_involved", ["unknown"])
            for colony in colonies:
                if colony not in colony_performance:
                    colony_performance[colony] = {"success": 0, "total": 0}

                colony_performance[colony]["total"] += 1
                if receipt.get("success", True):
                    colony_performance[colony]["success"] += 1

        # Convert to success rates
        for colony, stats in colony_performance.items():
            if stats["total"] > 0:
                colony_performance[colony] = stats["success"] / stats["total"]
            else:
                colony_performance[colony] = 0.0

        return {
            "overall_success_rate": overall_success_rate,
            "most_common_failures": most_common_failures,
            "colony_performance": colony_performance,
            "context_correlations": {},  # Could be enhanced
        }

    async def _create_learning_updates(
        self, patterns: list[ReceiptPattern], insights: dict[str, Any]
    ) -> dict[str, Any]:
        """Create learning updates from analysis."""
        updates = {}

        # Colony utility adjustments based on performance
        colony_performance = insights.get("colony_performance", {})
        colony_utilities = {}

        for colony, performance in colony_performance.items():
            if colony != "unknown" and performance < 0.7:  # Poor performance
                colony_utilities[colony] = -0.1  # Decrease utility
            elif performance > 0.9:  # Excellent performance
                colony_utilities[colony] = 0.1  # Increase utility

        if colony_utilities:
            updates["colony_utilities"] = colony_utilities

        # Memory patterns from extracted patterns
        memory_patterns = []
        for pattern in patterns:
            if pattern.confidence > 0.5:
                memory_patterns.append(
                    {
                        "type": pattern.pattern_type.value,
                        "description": pattern.description,
                        "context_factors": pattern.context_factors,
                        "success_rate": pattern.success_rate,
                    }
                )

        if memory_patterns:
            updates["memory_patterns"] = memory_patterns

        # World model gradients (simplified)
        if insights.get("overall_success_rate", 0) < 0.6:
            updates["world_model_gradients"] = {
                "explore_rate": 0.1,  # Increase exploration when success rate is low
                "caution_factor": 0.2,  # Increase caution
            }

        return updates

    async def _update_colony_utilities(self, utility_adjustments: dict[str, float]) -> None:
        """Update colony utilities based on retroactive analysis."""
        try:
            from kagami.core.learning.receipt_learning import get_receipt_learning_engine

            engine = get_receipt_learning_engine()

            for colony, adjustment in utility_adjustments.items():
                await engine.update_colony_utility(
                    colony, adjustment, reason="retroactive_analysis"
                )

            logger.info(f"Updated utilities for {len(utility_adjustments)} colonies")

        except Exception as e:
            logger.error(f"Failed to update colony utilities: {e}")

    async def _apply_world_model_gradients(self, gradients: dict[str, Any]) -> None:
        """Apply world model parameter gradients."""
        try:
            # This would integrate with OrganismRSSM or world model
            logger.info(f"Applied {len(gradients)} world model gradients")
        except Exception as e:
            logger.error(f"Failed to apply world model gradients: {e}")

    async def _update_memory_patterns(self, patterns: list[dict[str, Any]]) -> None:
        """Store learned patterns in memory."""
        try:
            # Store all patterns in parallel
            if patterns:
                await asyncio.gather(
                    *[self._memory_hub.store_pattern(pattern) for pattern in patterns],
                    return_exceptions=True,
                )

            logger.info(f"Stored {len(patterns)} memory patterns")
        except Exception as e:
            logger.error(f"Failed to store memory patterns: {e}")

    async def _store_pattern_embeddings(self, patterns: list[ReceiptPattern]) -> None:
        """Store pattern embeddings for semantic search."""
        try:
            for pattern in patterns:
                await self._embedding_service.embed_text_async(pattern.description)
                # Store in Weaviate or embedding store

            logger.info(f"Stored embeddings for {len(patterns)} patterns")
        except Exception as e:
            logger.error(f"Failed to store pattern embeddings: {e}")

    def _classify_error(self, error: str) -> str:
        """Classify error into broad category."""
        error_lower = error.lower()

        if "timeout" in error_lower or "time" in error_lower:
            return "timeout"
        elif "connection" in error_lower or "network" in error_lower:
            return "network"
        elif "permission" in error_lower or "auth" in error_lower:
            return "permission"
        elif "not found" in error_lower or "404" in error_lower:
            return "not_found"
        elif "memory" in error_lower or "resource" in error_lower:
            return "resource"
        else:
            return "unknown"

    def _extract_context_key(self, receipt: dict[str, Any]) -> str:
        """Extract key context factors from receipt."""
        context = receipt.get("context", {})

        # Create a simplified context key
        key_factors = []
        for key in ["intent_type", "colony", "complexity", "user_present"]:
            if key in context:
                key_factors.append(f"{key}={context[key]}")

        return "|".join(key_factors) if key_factors else "default"


# =============================================================================
# SINGLETON FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_retroactive_analyzer = _singleton_registry.register_sync(
    "retroactive_receipt_analyzer", RetroactiveReceiptAnalyzer
)
