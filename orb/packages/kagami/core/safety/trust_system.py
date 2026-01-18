from __future__ import annotations

"""
Autonomy Trust System - Gradual trust based on track record.

Tracks per-action and per-agent reliability and uses it to modulate
graduated confirmation: proven-safe flows receive fewer prompts; risky
or new flows require confirmation.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class TrustScore:
    """Track success and failure counts for trust calculation.

    Uses Wilson-like smoothing to provide robust trust scores even
    with small sample sizes. The score converges to the true success
    rate as more data is collected.

    Attributes:
        successes: Number of successful outcomes
        failures: Number of failed outcomes
    """

    successes: int = 0
    failures: int = 0

    @property
    def total(self) -> int:
        """Get total number of recorded outcomes."""
        return self.successes + self.failures

    @property
    def score(self) -> float:
        """Calculate smoothed trust score using Wilson-like formula.

        Returns:
            Score in range [0, 1] where higher is more trustworthy.
            Uses Bayesian smoothing to handle small sample sizes.
        """
        # Wilson-like smoothing
        n = max(1, self.total)
        p = self.successes / n
        return (p * n + 2) / (n + 4)


class AutonomyTrustRegistry:
    """Registry for tracking trust scores by action type and agent.

    Maintains separate trust scores for:
    - Actions: Keyed by tool name and file extension
    - Agents: Keyed by agent identifier

    Used by graduated confirmation to reduce prompts for proven-safe
    actions and increase prompts for risky or new actions.
    """

    def __init__(self) -> None:
        """Initialize empty trust registries."""
        self._by_action: dict[str, TrustScore] = defaultdict(TrustScore)
        self._by_agent: dict[str, TrustScore] = defaultdict(TrustScore)

    def key_for(self, action: dict[str, Any]) -> str:
        """Generate a unique key for an action.

        Args:
            action: Action dictionary with 'tool' and 'args' keys

        Returns:
            Key in format 'tool:extension' for tracking
        """
        tool = action.get("tool", "unknown")
        args = action.get("args", {})
        file_path = args.get("file_path") or args.get("target_file") or ""
        return f"{tool}:{file_path.split('.')[-1] if file_path else 'none'}"

    def record_outcome(self, *, agent: str, action: dict[str, Any], success: bool) -> None:
        """Record the outcome of an action for trust tracking.

        Args:
            agent: Agent identifier
            action: Action dictionary
            success: Whether the action succeeded
        """
        k = self.key_for(action)
        ts_action = self._by_action[k]
        ts_agent = self._by_agent[agent]
        if success:
            ts_action.successes += 1
            ts_agent.successes += 1
        else:
            ts_action.failures += 1
            ts_agent.failures += 1

    def get_trust_modifier(self, *, agent: str, action: dict[str, Any]) -> float:
        """
        Return a multiplier in [0.8, 1.2] to adjust risk score:
        - High trust (<10% failure) → 0.9
        - Low trust (>30% failure) → 1.1
        Gradual, smoothed, bounded.
        """
        k = self.key_for(action)
        ts_action = self._by_action[k]
        ts_agent = self._by_agent[agent]

        def failure_rate(ts: TrustScore) -> float:
            n = ts.total
            if n < 5:
                return 0.25  # conservative default
            return max(0.0, 1.0 - ts.score)

        fr = 0.6 * failure_rate(ts_action) + 0.4 * failure_rate(ts_agent)
        # Map to modifier: lower fr → lower risk
        if fr < 0.1:
            return 0.9
        if fr > 0.3:
            return 1.1
        # Linear in-between
        return 0.9 + (fr - 0.1) * (1.1 - 0.9) / 0.2


_GLOBAL_TRUST: AutonomyTrustRegistry | None = None


def get_trust_registry() -> AutonomyTrustRegistry:
    """Get the global trust registry singleton.

    Returns:
        Global AutonomyTrustRegistry instance, created if needed.
    """
    global _GLOBAL_TRUST
    if _GLOBAL_TRUST is None:
        _GLOBAL_TRUST = AutonomyTrustRegistry()
    return _GLOBAL_TRUST


__all__ = ["AutonomyTrustRegistry", "TrustScore", "get_trust_registry"]
