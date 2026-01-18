"""Reinforcement Learning instrumentation helpers (minimal).

Provides lightweight counters and diversity metrics for tests and
basic runtime introspection. Integrates optionally with Prometheus
metrics if the global registry is available, but degrades gracefully
without it.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

CANONICAL_PHASES = (
    "perceive",
    "model",
    "simulate",
    "act",
    "verify",
    "converge",
    "unknown",
)

try:
    # Optional Prometheus integration
    from .metrics import Counter

    _RL_USAGE_TOTAL = Counter(
        "kagami_rl_usage_total", "Total RL usage events", labelnames=("outcome",)
    )
    _RL_EXPLORATION = Counter(
        "kagami_rl_exploration_total",
        "Exploration factor accumulation (sum)",
        labelnames=(),
    )
except Exception:  # pragma: no cover - metrics optional in tests
    # Metrics unavailable - will be None when accessed
    pass

# Simple module-level counters (used directly by tests)
_rl_total_count: int = 0
_rl_success_count: int = 0

# Default exploration factor used by unified loops
RL_EXPLORATION_FACTOR: float = 0.1


def record_rl_usage(outcome: str, exploration: float | None = None) -> None:
    """Record a reinforcement learning usage event.

    Args:
        outcome: "success" | "fallback" | "error"
        exploration: Optional exploration value in [0, 1]
    """
    global _rl_total_count, _rl_success_count

    _rl_total_count += 1
    if outcome == "success":
        _rl_success_count += 1

    # Update metrics if available
    if _RL_USAGE_TOTAL is not None:
        try:
            _RL_USAGE_TOTAL.labels(outcome=outcome).inc()
        except Exception:
            pass

    if exploration is not None and _RL_EXPLORATION is not None:
        try:
            _RL_EXPLORATION.inc(exploration)
        except Exception:
            pass


def compute_behavioral_diversity(phases: Iterable[str]) -> float:
    """Compute normalized Shannon entropy of observed phases.

    Returns a value in [0, 1]. 0 means no diversity; 1 is maximal over
    the unique set of phases observed.
    """
    phases_list = list(phases)
    if not phases_list:
        return 0.0

    # Frequency table
    freq: dict[str, int] = {}
    for p in phases_list:
        freq[p] = freq.get(p, 0) + 1

    n = len(phases_list)
    unique = len(freq)
    if unique <= 1:
        return 0.0

    # Shannon entropy
    H = 0.0
    for count in freq.values():
        p = count / n  # type: ignore[assignment]
        if p > 0:  # type: ignore  # Operator overload
            H -= p * math.log(p, 2)  # type: ignore

    universe = max(len(CANONICAL_PHASES), unique)
    H_max = math.log(universe, 2)
    if H_max <= 0:
        return 0.0

    return max(0.0, min(1.0, H / H_max))


__all__ = [
    "RL_EXPLORATION_FACTOR",
    "_rl_success_count",
    "_rl_total_count",
    "compute_behavioral_diversity",
    "record_rl_usage",
]
