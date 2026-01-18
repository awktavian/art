"""
Stress Test for CBF QP Solver (POCS Implementation).

Moved from tests/core/safety/test_cbf_solver_stress.py on Nov 30, 2025.

This test validates that the solver behaves robustly under:
1. Constraint Saturation (Many conflicting constraints)
2. High-Frequency calls (Performance)
3. Numerical Instability (Near-parallel half-spaces)

It ensures the "Map vs Territory" gap doesn't lead to unsafe control.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_e2e


import time
import math
from typing import List  # noqa: UP035
from kagami.policy.cbf import strict_filter, strict_filter_multi


@pytest.mark.stress
@pytest.mark.slow
def test_solver_basic_safety() -> None:
    """Basic check: Single constraint pushes u out of unsafe region."""
    u_nom = [1.0, 1.0]
    # Constraint: u[0] + u[1] <= 1.0  =>  -u[0] - u[1] >= -1.0
    # a = [-1, -1], b = -1
    a = [-1.0, -1.0]
    b = -1.0
    u_min = [0.0, 0.0]
    u_max = [2.0, 2.0]

    res = strict_filter(u_nominal=u_nom, a=a, b=b, u_min=u_min, u_max=u_max)

    assert res["feasible"] is True
    u = res["u"]
    # Check constraint satisfaction
    val = u[0] * a[0] + u[1] * a[1]
    assert val >= b - 1e-6
    # Should project to boundary: u=[0.5, 0.5] is closest to [1,1] on line x+y=1
    assert abs(u[0] - 0.5) < 1e-4
    assert abs(u[1] - 0.5) < 1e-4


@pytest.mark.stress
@pytest.mark.slow
def test_solver_saturation_infeasibility() -> None:
    """Test solver behavior when constraints are mutually exclusive."""
    u_nom = [0.5, 0.5]
    u_min = [0.0, 0.0]
    u_max = [1.0, 1.0]

    # Constraint 1: u[0] >= 0.8
    c1 = {"a": [1.0, 0.0], "b": 0.8}
    # Constraint 2: u[0] <= 0.2 => -u[0] >= -0.2
    c2 = {"a": [-1.0, 0.0], "b": -0.2}

    # Sequential filter (POCS)
    res = strict_filter_multi(
        u_nominal=u_nom, constraints=[c1, c2], u_min=u_min, u_max=u_max, passes=10
    )

    # Should report infeasible
    assert res["feasible"] is False
    # But should still return *some* u (best effort or last valid)
    # In a real safety system, feasible=False should trigger an emergency stop/fallback
    assert len(res["u"]) == 2


@pytest.mark.stress
@pytest.mark.slow
def test_solver_high_dimension_stress() -> None:
    """Stress test with 50 dimensions and 100 constraints."""
    dim = 50
    n_constraints = 100

    u_nom = [0.5] * dim
    u_min = [0.0] * dim
    u_max = [1.0] * dim

    constraints = []
    # Generate random constraints
    # For reproducibility, use deterministic pattern
    for i in range(n_constraints):
        # Create a random normal vector
        # Use sin/cos to avoid zero vector
        a = [math.sin((i + 1) * (j + 1)) for j in range(dim)]
        # Normalize
        norm = math.sqrt(sum(x * x for x in a))
        if norm < 1e-9:
            a = [1.0] + [0.0] * (dim - 1)
        else:
            a = [x / norm for x in a]
        b = -0.5  # Easy constraint
        constraints.append({"a": a, "b": b})

    start_time = time.perf_counter()
    res = strict_filter_multi(
        u_nominal=u_nom, constraints=constraints, u_min=u_min, u_max=u_max, passes=5
    )
    duration = time.perf_counter() - start_time

    # Performance check: Should be < 75ms for 100 constraints (relaxed from 50ms for CI stability)
    assert duration < 0.075
    assert res["feasible"] is True


@pytest.mark.stress
@pytest.mark.slow
def test_solver_numerical_instability() -> None:
    """Test with nearly parallel constraints causing 'canyon' effect."""
    u_nom = [0.0, 0.0]
    u_min = [-10.0, -10.0]
    u_max = [10.0, 10.0]

    # Two nearly parallel lines forming a narrow channel
    # x + y >= 0
    c1 = {"a": [1.0, 1.0], "b": 0.0}
    # -x - y >= -0.001  =>  x + y <= 0.001
    c2 = {"a": [-1.0, -1.0], "b": -0.001}

    res = strict_filter_multi(
        u_nominal=[5.0, 5.0],
        constraints=[c1, c2],
        u_min=u_min,
        u_max=u_max,
        passes=20,  # Far away
    )

    assert res["feasible"] is True
    u = res["u"]
    val = u[0] + u[1]
    # Should be in [0, 0.001]
    assert 0.0 <= val <= 0.001 + 1e-6


if __name__ == "__main__":
    # Manual run if called directly
    test_solver_basic_safety()
    test_solver_saturation_infeasibility()
    test_solver_high_dimension_stress()
    test_solver_numerical_instability()
    print("All solver stress tests passed.")
