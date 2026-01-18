from __future__ import annotations

from typing import Any

"""Safety Cost Functions for MPC

Penalizes barrier function violations in predicted trajectories:
    L_safety = Σ max(0, -h(x_t))

Integrates with Control Barrier Function (CBF) to ensure
h(x) ≥ 0 throughout planned trajectories.
"""
import logging
from collections.abc import Callable

import torch

logger = logging.getLogger(__name__)


def barrier_violation_cost(
    trajectory: list[torch.Tensor],
    safety_checker: Callable[[torch.Tensor], float],
    penalty_weight: float = 10.0,
) -> torch.Tensor:
    """Compute cost for CBF violations in trajectory.

    Cost = λ · Σ max(0, -h(x_t))

    Higher cost = more violations or larger violations

    Args:
        trajectory: List of states [B, dim] along trajectory
        safety_checker: Function that computes h(x) for each state
        penalty_weight: Weight for safety violations

    Returns:
        Total safety cost [B, 1]
    """
    violations = []

    for x_t in trajectory:
        h = safety_checker(x_t)

        # Convert to tensor if scalar
        if isinstance(h, (int, float)):
            h = torch.tensor(h, device=x_t.device)  # type: ignore[assignment]

        # Penalize violations (h < 0)
        violation = torch.clamp(-h, min=0.0)  # type: ignore[call-overload]
        violations.append(violation)

    # Sum violations over trajectory
    total_violation = sum(violations) if violations else torch.tensor(0.0)

    return penalty_weight * total_violation


def soft_barrier_cost(
    trajectory: list[torch.Tensor],
    safety_checker: Callable[[torch.Tensor], float],
    sharpness: float = 10.0,
    penalty_weight: float = 5.0,
) -> torch.Tensor:
    """Soft (differentiable) barrier cost using exponential.

    Cost = λ · Σ exp(-β · h(x_t))

    Smooth approximation to hard barrier for gradient-based optimization.

    Args:
        trajectory: List of states along trajectory
        safety_checker: Function that computes h(x)
        sharpness: Controls how quickly cost increases near boundary
        penalty_weight: Overall weight for safety

    Returns:
        Soft safety cost
    """
    soft_violations = []

    for x_t in trajectory:
        h = safety_checker(x_t)

        if isinstance(h, (int, float)):
            h = torch.tensor(h, device=x_t.device)  # type: ignore[assignment]

        # Exponential penalty: high when h → 0 or negative
        soft_penalty = torch.exp(-sharpness * h)  # type: ignore[arg-type]
        soft_violations.append(soft_penalty)

    total_soft = sum(soft_violations) if soft_violations else torch.tensor(0.0)

    return penalty_weight * total_soft  # type: ignore[return-value]


def trajectory_safety_score(
    trajectory: list[torch.Tensor],
    safety_checker: Callable[[torch.Tensor], float],
) -> dict[str, Any]:
    """Comprehensive safety analysis of trajectory.

    Args:
        trajectory: List of states
        safety_checker: CBF h(x) function

    Returns:
        {
            'safe': bool,
            'min_barrier': float,
            'violations': List of violation info,
            'hard_cost': float,
            'soft_cost': float,
        }
    """
    barrier_values = []
    violations = []

    for t, x_t in enumerate(trajectory):
        h = safety_checker(x_t)

        if isinstance(h, (int, float)):
            h_val = h
            h = torch.tensor(h, device=x_t.device)  # type: ignore[assignment]
        else:
            h_val = h.item()  # type: ignore[unreachable]

        barrier_values.append(h_val)

        if h_val < 0:
            violations.append(
                {
                    "step": t,
                    "barrier_value": h_val,
                    "violation_magnitude": -h_val,
                }
            )

    min_barrier = min(barrier_values) if barrier_values else 0.0
    is_safe = len(violations) == 0

    # Compute costs
    hard_cost = barrier_violation_cost(trajectory, safety_checker)
    soft_cost = soft_barrier_cost(trajectory, safety_checker)

    return {
        "safe": is_safe,
        "min_barrier": min_barrier,
        "mean_barrier": sum(barrier_values) / len(barrier_values) if barrier_values else 0.0,
        "violations": violations,
        "num_violations": len(violations),
        "hard_cost": (
            float(hard_cost.item()) if isinstance(hard_cost, torch.Tensor) else hard_cost
        ),
        "soft_cost": (
            float(soft_cost.item()) if isinstance(soft_cost, torch.Tensor) else soft_cost
        ),
    }


if __name__ == "__main__":
    # Smoke test
    print("=" * 60)
    print("Safety Cost Function Test")
    print("=" * 60)

    # Create dummy trajectory
    trajectory = [torch.randn(2, 15) * scale for scale in [0.5, 0.8, 1.0, 0.9, 0.7]]

    # Dummy safety checker (h(x) = 1 - ||x||)
    def dummy_cbf(x: Any) -> None:
        """Simple barrier: safe when ||x|| < 1"""
        norm = x.norm(dim=-1).mean()
        return 1.0 - norm.item()  # type: ignore[no-any-return]

    # Compute safety costs
    hard_cost = barrier_violation_cost(trajectory, dummy_cbf, penalty_weight=10.0)  # type: ignore[arg-type]
    soft_cost = soft_barrier_cost(trajectory, dummy_cbf, sharpness=10.0, penalty_weight=5.0)  # type: ignore[arg-type]

    print("\n✅ Cost functions computed")
    print(f"   Hard cost (violations): {hard_cost:.3f}")
    print(f"   Soft cost (exponential): {soft_cost:.3f}")

    # Full analysis
    analysis = trajectory_safety_score(trajectory, dummy_cbf)  # type: ignore[arg-type]

    print("\n✅ Safety analysis complete")
    print(f"   Safe: {analysis['safe']}")
    print(f"   Min barrier: {analysis['min_barrier']:.3f}")
    print(f"   Mean barrier: {analysis['mean_barrier']:.3f}")
    print(f"   Violations: {analysis['num_violations']}")
    print(f"   Hard cost: {analysis['hard_cost']:.3f}")
    print(f"   Soft cost: {analysis['soft_cost']:.3f}")

    print("\n" + "=" * 60)
    print("✅ Safety cost functions operational")
    print("=" * 60)
