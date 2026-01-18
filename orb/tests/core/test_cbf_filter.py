
from __future__ import annotations


import math

from kagami.policy.cbf import strict_filter, strict_filter_multi


def test_strict_filter_1d_active_constraint():
    # 1D: a u >= b with box [0, 1]
    u_nom = [0.2]
    a = [1.0]
    b = 0.8  # requires pushing towards 0.8
    u_min = [0.0]
    u_max = [1.0]

    out = strict_filter(u_nominal=u_nom, a=a, b=b, u_min=u_min, u_max=u_max)
    assert out["feasible"] is True
    assert math.isclose(out["u"][0], 0.8, rel_tol=1e-6, abs_tol=1e-8)
    assert out["lambda"] >= 0.0


def test_strict_filter_1d_infeasible():
    # 1D infeasible: a u >= b with box [0, 0.5] and b=0.8
    u_nom = [0.1]
    a = [1.0]
    b = 0.8
    u_min = [0.0]
    u_max = [0.5]

    out = strict_filter(u_nominal=u_nom, a=a, b=b, u_min=u_min, u_max=u_max)
    assert out["feasible"] is False
    # Best we can do is u=0.5 (upper bound)
    assert math.isclose(out["u"][0], 0.5, rel_tol=1e-6, abs_tol=1e-8)


def test_strict_filter_2d_projection_with_box():
    # 2D: a^T u >= b with box and nominal outside half-space
    u_nom = [0.0, 0.0]
    a = [1.0, 1.0]
    b = 1.0
    u_min = [0.0, 0.0]
    u_max = [0.8, 0.8]

    out = strict_filter(u_nominal=u_nom, a=a, b=b, u_min=u_min, u_max=u_max)
    assert out["feasible"] is True
    # Any point on clipped line u1+u2=1 within box; solution should respect box
    u = out["u"]
    assert 0.0 <= u[0] <= 0.8 and 0.0 <= u[1] <= 0.8
    assert (u[0] + u[1]) >= 1.0 - 1e-8


def test_strict_filter_multi_two_constraints():
    # Enforce u1 >= 0.4 and u2 >= 0.5 within box [0,1]^2
    u_nom = [0.0, 0.0]
    constraints = [
        {"a": [1.0, 0.0], "b": 0.4},
        {"a": [0.0, 1.0], "b": 0.5},
    ]
    u_min = [0.0, 0.0]
    u_max = [1.0, 1.0]

    out = strict_filter_multi(
        u_nominal=u_nom,
        constraints=constraints,
        u_min=u_min,
        u_max=u_max,
        robust_delta=0.0,
    )
    assert out["feasible"] is True
    u = out["u"]
    assert u[0] >= 0.4 - 1e-8 and u[1] >= 0.5 - 1e-8


def test_strict_filter_robust_margin_makes_harder():
    # 1D: with robust margin 0.1, pushes to 0.9
    u_nom = [0.2]
    a = [1.0]
    b = 0.8
    u_min = [0.0]
    u_max = [1.0]

    out = strict_filter(u_nominal=u_nom, a=a, b=b, u_min=u_min, u_max=u_max, robust_delta=0.1)
    assert out["feasible"] is True
    assert abs(out["u"][0] - 0.9) <= 1e-8
