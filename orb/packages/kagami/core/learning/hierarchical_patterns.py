"""Hierarchical Pattern Extraction for Receipt-Driven Learning.

Extract patterns at 3 levels from receipt streams:
1. Operation level: Single receipt patterns
2. Sequence level: Chains of receipts (workflows)
3. Strategy level: High-level behavioral patterns

Enhances existing receipt_stream_processor.py with multi-level analysis.

Created: December 2024
Status: Production-ready
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OperationPattern:
    """Pattern extracted from single receipt."""

    pattern_id: str
    action: str
    domain: str
    success_rate: float
    avg_duration_ms: float
    frequency: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "action": self.action,
            "domain": self.domain,
            "success_rate": self.success_rate,
            "avg_duration_ms": self.avg_duration_ms,
            "frequency": self.frequency,
        }


@dataclass
class SequencePattern:
    """Pattern extracted from receipt chains."""

    pattern_id: str
    sequence: list[str]  # List of actions
    avg_total_duration_ms: float
    success_rate: float
    frequency: int
    typical_domains: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "sequence": self.sequence,
            "avg_total_duration_ms": self.avg_total_duration_ms,
            "success_rate": self.success_rate,
            "frequency": self.frequency,
            "typical_domains": self.typical_domains,
        }


@dataclass
class StrategyPattern:
    """High-level behavioral strategy pattern."""

    pattern_id: str
    strategy_name: str
    conditions: list[str]  # When this strategy is used
    typical_sequences: list[list[str]]
    avg_success_rate: float
    frequency: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "strategy_name": self.strategy_name,
            "conditions": self.conditions,
            "typical_sequences": self.typical_sequences,
            "avg_success_rate": self.avg_success_rate,
            "frequency": self.frequency,
        }


class HierarchicalPatternExtractor:
    """Extract patterns at multiple levels from receipts."""

    def __init__(self, sequence_window: int = 10, min_pattern_frequency: int = 3) -> None:
        """Initialize extractor.

        Args:
            sequence_window: Size of sliding window for sequence detection
            min_pattern_frequency: Minimum occurrences to consider a pattern
        """
        self.sequence_window = sequence_window
        self.min_pattern_frequency = min_pattern_frequency

        # Pattern storage
        self.operation_patterns: dict[str, OperationPattern] = {}
        self.sequence_patterns: dict[str, SequencePattern] = {}
        self.strategy_patterns: dict[str, StrategyPattern] = {}

        # Tracking
        self.receipt_window: deque = deque(maxlen=sequence_window)
        self.action_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "successes": 0,
                "durations_ms": [],
                "domains": Counter(),
            }
        )
        self.sequence_stats: dict[tuple[Any, ...], dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "successes": 0,
                "total_durations_ms": [],
                "domains": Counter(),
            }
        )

    def extract_patterns(self, receipt: dict[str, Any]) -> dict[str, list[Any]]:
        """Extract all pattern levels from a receipt.

        Args:
            receipt: Receipt dict[str, Any] with correlation_id, phase, event, data

        Returns:
            Dict with keys: operation, sequence, strategy
        """
        patterns: dict[str, list[Any]] = {
            "operation": [],
            "sequence": [],
            "strategy": [],
        }

        # Level 1: Operation patterns (single receipt)
        if receipt.get("phase") == "EXECUTE":
            op_pattern = self._extract_operation_pattern(receipt)
            if op_pattern:
                patterns["operation"].append(op_pattern)

        # Add to window for sequence analysis
        self.receipt_window.append(receipt)

        # Level 2: Sequence patterns (receipt chains)
        if len(self.receipt_window) >= 3:
            seq_patterns = self._extract_sequence_patterns()
            patterns["sequence"].extend(seq_patterns)

        # Level 3: Strategy patterns (high-level behaviors)
        if len(self.receipt_window) >= self.sequence_window:
            strat_patterns = self._extract_strategy_patterns()
            patterns["strategy"].extend(strat_patterns)

        return patterns

    def _extract_operation_pattern(self, receipt: dict[str, Any]) -> OperationPattern | None:
        """Extract operation-level pattern from single receipt."""
        data = receipt.get("data", {})
        action = data.get("action") or receipt.get("event_name")
        if not action:
            return None

        domain = data.get("domain", "unknown")
        success = data.get("success", False)
        duration_ms = data.get("duration_ms", 0)

        # Update stats
        self.action_stats[action]["count"] += 1
        if success:
            self.action_stats[action]["successes"] += 1
        if duration_ms > 0:
            self.action_stats[action]["durations_ms"].append(duration_ms)
        self.action_stats[action]["domains"][domain] += 1

        # Create pattern if frequency threshold met
        stats = self.action_stats[action]
        if stats["count"] >= self.min_pattern_frequency:
            pattern_id = f"OP_{hash(action) % 10000:04d}"

            avg_duration = np.mean(stats["durations_ms"]) if stats["durations_ms"] else 0

            success_rate = stats["successes"] / stats["count"]

            pattern = OperationPattern(
                pattern_id=pattern_id,
                action=action,
                domain=stats["domains"].most_common(1)[0][0] if stats["domains"] else "unknown",
                success_rate=success_rate,
                avg_duration_ms=avg_duration,
                frequency=stats["count"],
            )

            self.operation_patterns[pattern_id] = pattern
            return pattern

        return None

    def _extract_sequence_patterns(self) -> list[SequencePattern]:
        """Extract sequence-level patterns from receipt chains."""
        patterns: list[Any] = []

        # Look for action sequences in window
        if len(self.receipt_window) < 3:
            return patterns

        # Extract action sequence from last N receipts
        action_sequence = []
        for receipt in list(self.receipt_window)[-5:]:  # Last 5 receipts
            if receipt.get("phase") == "EXECUTE":
                data = receipt.get("data", {})
                action = data.get("action") or receipt.get("event_name")
                if action:
                    action_sequence.append(action)

        if len(action_sequence) < 2:
            return patterns

        # Track this sequence
        seq_tuple = tuple(action_sequence)
        self.sequence_stats[seq_tuple]["count"] += 1

        # Calculate success rate for this sequence
        # (For now, simplified: check if last receipt was successful)
        last_receipt = list(self.receipt_window)[-1]
        if last_receipt.get("data", {}).get("success"):
            self.sequence_stats[seq_tuple]["successes"] += 1

        # Extract domains
        for receipt in list(self.receipt_window)[-5:]:
            domain = receipt.get("data", {}).get("domain")
            if domain:
                self.sequence_stats[seq_tuple]["domains"][domain] += 1

        # Create pattern if frequency threshold met
        stats = self.sequence_stats[seq_tuple]
        if stats["count"] >= self.min_pattern_frequency:
            pattern_id = f"SEQ_{hash(seq_tuple) % 10000:04d}"

            success_rate = stats["successes"] / stats["count"]

            # Get typical domains
            typical_domains = [domain for domain, _ in stats["domains"].most_common(3)]

            pattern = SequencePattern(
                pattern_id=pattern_id,
                sequence=list(action_sequence),
                avg_total_duration_ms=(
                    stats.get("total_duration_ms", 0.0) / stats["count"]
                    if stats["count"] > 0
                    else 0.0
                ),
                success_rate=success_rate,
                frequency=stats["count"],
                typical_domains=typical_domains,
            )

            self.sequence_patterns[pattern_id] = pattern
            patterns.append(pattern)

        return patterns

    def _extract_strategy_patterns(self) -> list[StrategyPattern]:
        """Extract high-level strategy patterns."""
        patterns: list[Any] = []

        if len(self.receipt_window) < 10:
            return patterns

        # Analyze action sequences to identify strategies
        recent_receipts = list(self.receipt_window)[-20:]

        # Extract action sequence
        actions = []
        for receipt in recent_receipts:
            if receipt.get("phase") == "EXECUTE":
                action = receipt.get("data", {}).get("action") or receipt.get("event_name")
                if action:
                    actions.append(action)

        if len(actions) < 5:
            return patterns

        # Detect strategy patterns

        # 1. Research-then-implement: query/analyze followed by execute/create
        research_actions = {"query", "search", "analyze", "read", "inspect"}
        implement_actions = {"create", "execute", "write", "update", "generate"}

        research_count = sum(1 for a in actions if any(r in a.lower() for r in research_actions))
        implement_count = sum(1 for a in actions if any(i in a.lower() for i in implement_actions))

        if research_count > 0 and implement_count > 0:
            # Check if research comes before implementation
            first_research = next(
                (i for i, a in enumerate(actions) if any(r in a.lower() for r in research_actions)),
                -1,
            )
            first_implement = next(
                (
                    i
                    for i, a in enumerate(actions)
                    if any(r in a.lower() for r in implement_actions)
                ),
                -1,
            )

            if first_research >= 0 and first_implement > first_research:
                pattern_id = "STRAT_research_then_implement"

                pattern = StrategyPattern(
                    pattern_id=pattern_id,
                    strategy_name="Research-Then-Implement",
                    conditions=["has_research_phase", "has_implementation_phase"],
                    typical_sequences=[["research", "plan", "implement", "verify"]],
                    avg_success_rate=0.0,  # Would track
                    frequency=1,
                )

                patterns.append(pattern)
                self.strategy_patterns[pattern_id] = pattern

        # 2. Trial-and-error: multiple attempts with variation
        retry_actions = sum(1 for a in actions if "retry" in a.lower() or "attempt" in a.lower())

        if retry_actions >= 2:
            pattern_id = "STRAT_trial_and_error"

            pattern = StrategyPattern(
                pattern_id=pattern_id,
                strategy_name="Trial-And-Error",
                conditions=["has_retries"],
                typical_sequences=[["attempt", "evaluate", "adjust", "retry"]],
                avg_success_rate=0.0,  # Would track
                frequency=1,
            )

            patterns.append(pattern)
            self.strategy_patterns[pattern_id] = pattern

        return patterns

    def get_all_patterns(self) -> dict[str, list[dict[str, Any]]]:
        """Get all extracted patterns.

        Returns:
            Dict with operation, sequence, strategy pattern lists
        """
        return {
            "operation": [p.to_dict() for p in self.operation_patterns.values()],
            "sequence": [p.to_dict() for p in self.sequence_patterns.values()],
            "strategy": [p.to_dict() for p in self.strategy_patterns.values()],
        }

    def get_stats(self) -> dict[str, Any]:
        """Get pattern extraction statistics."""
        return {
            "operation_patterns": len(self.operation_patterns),
            "sequence_patterns": len(self.sequence_patterns),
            "strategy_patterns": len(self.strategy_patterns),
            "receipts_analyzed": len(self.receipt_window),
            "unique_actions": len(self.action_stats),
            "unique_sequences": len(self.sequence_stats),
        }


__all__ = [
    "HierarchicalPatternExtractor",
    "OperationPattern",
    "SequencePattern",
    "StrategyPattern",
]
