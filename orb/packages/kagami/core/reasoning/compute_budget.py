"""Test-Time Compute (TTC) Budget Management.

Provides budget allocation for reasoning strategies based on risk and complexity.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


@dataclass
class ComputeBudget:
    """Test-time compute budget allocation."""

    mode: Literal["flash", "balanced", "thorough", "exhaustive"]
    sc_samples: int  # Self-consistency samples
    think_tokens: int  # Reasoning tokens
    rollout_K: int  # Rollout breadth
    rollout_H: int  # Rollout depth


def budget_for(
    mode: Literal["flash", "balanced", "thorough", "exhaustive"] = "balanced",
    risk: float = 0.5,
    complexity: float = 0.5,
) -> ComputeBudget:
    """Allocate compute budget based on mode and task properties.

    Args:
        mode: Base compute mode
        risk: Risk level (0.0 to 1.0)
        complexity: Task complexity (0.0 to 1.0)

    Returns:
        ComputeBudget with allocated resources
    """
    # Base budgets for each mode
    base_budgets = {
        "flash": ComputeBudget(
            mode="flash",
            sc_samples=1,
            think_tokens=128,
            rollout_K=1,
            rollout_H=1,
        ),
        "balanced": ComputeBudget(
            mode="balanced",
            sc_samples=3,
            think_tokens=512,
            rollout_K=3,
            rollout_H=3,
        ),
        "thorough": ComputeBudget(
            mode="thorough",
            sc_samples=5,
            think_tokens=1024,
            rollout_K=5,
            rollout_H=5,
        ),
        "exhaustive": ComputeBudget(
            mode="exhaustive",
            sc_samples=7,
            think_tokens=2048,
            rollout_K=7,
            rollout_H=7,
        ),
    }

    budget = base_budgets[mode]

    # Scale up based on risk and complexity
    urgency = (risk + complexity) / 2.0
    scale = 1.0 + urgency * 0.5  # Up to 50% increase

    return ComputeBudget(
        mode=budget.mode,
        sc_samples=int(budget.sc_samples * scale),
        think_tokens=int(budget.think_tokens * scale),
        rollout_K=int(budget.rollout_K * scale),
        rollout_H=int(budget.rollout_H * scale),
    )


def get_default_mode() -> Literal["flash", "balanced", "thorough", "exhaustive"]:
    """Get default TTC mode from environment.

    Returns:
        Default compute mode (defaults to "balanced")
    """
    mode = os.environ.get("KAGAMI_TTC_MODE", "balanced")
    valid_modes = {"flash", "balanced", "thorough", "exhaustive"}

    if mode not in valid_modes:
        return "balanced"

    return mode  # type: ignore[return-value]
