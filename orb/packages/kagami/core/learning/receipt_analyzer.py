"""Receipt pattern analyzer for meta-learning.

Analyzes receipts to detect failure patterns and update agent strategy,
enabling autonomous improvement per P1-8.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class ReceiptPatternAnalyzer:
    """Analyzes receipts to extract learning patterns."""

    def __init__(self) -> None:
        self._patterns: dict[str, dict[str, Any]] = {}
        self._failure_count: dict[str, int] = defaultdict(int)

    async def analyze_recent_receipts(
        self, receipts: list[dict[str, Any]], window_hours: int = 24
    ) -> dict[str, Any]:
        """Analyze recent receipts for patterns.

        Args:
            receipts: List of receipt dictionaries
            window_hours: Time window to analyze

        Returns:
            Analysis with detected patterns, failure rates, recommendations
        """
        if not receipts:
            return {"patterns": [], "failure_rate": 0.0, "recommendations": []}
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        recent = [r for r in receipts if self._parse_timestamp(r.get("ts")) > cutoff]
        if not recent:
            return {"patterns": [], "failure_rate": 0.0, "recommendations": []}
        failures = [r for r in recent if r.get("status") == "error"]
        failure_rate = len(failures) / len(recent) if recent else 0.0
        failure_patterns = self._extract_failure_patterns(failures)
        recommendations = self._generate_recommendations(failure_patterns, failure_rate)
        return {
            "total_receipts": len(recent),
            "failures": len(failures),
            "failure_rate": failure_rate,
            "patterns": failure_patterns,
            "recommendations": recommendations,
            "window_hours": window_hours,
        }

    def _extract_failure_patterns(self, failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract common patterns from failures."""
        patterns = []
        by_action: dict[str, list[Any]] = defaultdict(list[Any])
        for failure in failures:
            action = failure.get("action", "unknown")
            by_action[action].append(failure)
        for action, action_failures in by_action.items():
            if len(action_failures) >= 3:
                error_types = defaultdict(int)  # type: ignore[var-annotated]
                for f in action_failures:
                    error = f.get("event", {}).get("data", {}).get("error")
                    if error:
                        error_types[error] += 1
                patterns.append(
                    {
                        "action": action,
                        "failure_count": len(action_failures),
                        "common_errors": dict(error_types),
                        "severity": "high" if len(action_failures) > 5 else "medium",
                    }
                )
        return patterns

    def _generate_recommendations(
        self, patterns: list[dict[str, Any]], failure_rate: float
    ) -> list[str]:
        """Generate actionable recommendations from patterns."""
        recommendations = []
        if failure_rate > 0.2:
            recommendations.append(
                f"High failure rate ({failure_rate:.1%}) - review recent changes"
            )
        for pattern in patterns:
            action = pattern["action"]
            count = pattern["failure_count"]
            recommendations.append(
                f"Action '{action}' failing frequently ({count} times) - investigate and add error handling"
            )
            common_errors = pattern.get("common_errors", {})
            for error, error_count in common_errors.items():
                if error_count >= 2:
                    recommendations.append(f"  → Add validation for '{error}' in {action}")
        return recommendations

    async def store_learning(self, pattern: dict[str, Any], valence: float = -0.8) -> None:
        """Store learned pattern in episodic memory.

        Args:
            pattern: Detected pattern dictionary
            valence: Emotional valence (-1.0 to 1.0, negative for failures)
        """
        try:
            from kagami.core.instincts.learning_instinct import LearningInstinct

            instinct = LearningInstinct()
            await instinct.remember(  # type: ignore[call-arg]
                event=f"Failure pattern: {pattern.get('action')}",  # type: ignore[arg-type]
                valence=valence,
                pattern=str(pattern),
                action_bias=[f"validate_before_{pattern.get('action')}"],
                attention_weight=abs(valence),
            )
            logger.info(f"Stored learning pattern: {pattern.get('action')}")
        except Exception as e:
            logger.debug(f"Failed to store learning: {e}")

    def _parse_timestamp(self, ts: Any) -> datetime:
        """Parse timestamp from receipt."""
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts / 1000)
        elif isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                return datetime.utcnow()
        else:
            return datetime.utcnow()
