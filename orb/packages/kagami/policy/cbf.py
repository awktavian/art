from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)


def enforce(intent: Any) -> tuple[str, dict[str, Any]]:
    """Enforce Control Barrier Function-style constraints on an intent.

    Returns (decision, changes):
      - decision: "ok" | "adjusted" | "blocked"
      - changes: dictionary of clamped fields if adjusted

    Lightweight policy clamp for application-level safety constraints.
    This is complementary to the strict control filter below.
    """
    _t0 = time.perf_counter()  # Available for latency instrumentation
    try:
        decision = "ok"
        changes: dict[str, Any] = {}

        md = getattr(intent, "metadata", {}) or {}

        # Clamp budgets (acts like solving a trivial QP with box constraints)
        try:
            max_tokens = int(md.get("max_tokens", 0) or 0)
            if max_tokens and max_tokens > 6000:
                md["max_tokens"] = 6000
                changes["max_tokens"] = 6000
                decision = "adjusted"
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse max_tokens: {e}")
            # Conservative default: no adjustment if parsing fails

        try:
            budget_ms = int(md.get("budget_ms", 0) or 0)
            if budget_ms and budget_ms > 30000:
                md["budget_ms"] = 30000
                changes["budget_ms"] = 30000
                decision = "adjusted"
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse budget_ms: {e}")
            # Conservative default: no adjustment if parsing fails

        # Block specific destructive operations (simple barrier)
        action = str(getattr(intent, "action", "") or "").lower()
        target = str(getattr(intent, "target", "") or "").lower()
        if any(k in action for k in ("delete", "destroy")) or any(
            k in target for k in ("database", "billing")
        ):
            # Allow only when confirm flag set[Any] explicitly in metadata
            try:
                confirm = str(md.get("confirm") or "").lower() in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to parse confirm flag, defaulting to False: {e}")
                confirm = False  # Fail-safe: block destructive operations on error
            if not confirm:
                return "blocked", {"reason": "constraint_violation"}

        # Write back metadata if adjusted
        if changes:
            intent.metadata = md

        return decision, changes
    finally:
        pass  # Duration tracking removed (metric cleanup Dec 2025)


# === Strict control-level CBF filter (minimal, dependency-free) ===


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    s = 0.0
    for i in range(min(len(a), len(b))):
        s += float(a[i]) * float(b[i])
    return s


def _clip_vec(v: Sequence[float], v_min: Sequence[float], v_max: Sequence[float]) -> list[float]:
    n = len(v)
    out: list[float] = [0.0] * n
    for i in range(n):
        lo = float(v_min[i]) if i < len(v_min) else float("-inf")
        hi = float(v_max[i]) if i < len(v_max) else float("inf")
        x = float(v[i])
        if x < lo:
            out[i] = lo
        elif x > hi:
            out[i] = hi
        else:
            out[i] = x
    return out


def _box_extreme_for_linear_form(
    a: Sequence[float], u_min: Sequence[float], u_max: Sequence[float]
) -> list[float]:
    """Return box vertex that maximizes a^T u (for feasibility check)."""
    n = len(a)
    out: list[float] = [0.0] * n
    for i in range(n):
        ai = float(a[i])
        if ai >= 0.0:
            out[i] = float(u_max[i])
        else:
            out[i] = float(u_min[i])
    return out


def _phi_lambda(
    lambda_val: float,
    u_nom: Sequence[float],
    a: Sequence[float],
    u_min: Sequence[float],
    u_max: Sequence[float],
) -> float:
    """Compute a^T clip(u_nom + lambda a, box).

    OPTIMIZED: Computes result in a single pass without allocating intermediate vectors.
    """
    s = 0.0
    for i in range(len(u_nom)):
        # Calculate candidate u[i]
        ui = float(u_nom[i]) + lambda_val * float(a[i])

        # Clip to box constraints
        lo = float(u_min[i]) if i < len(u_min) else float("-inf")
        hi = float(u_max[i]) if i < len(u_max) else float("inf")

        if ui < lo:
            ui = lo
        elif ui > hi:
            ui = hi

        # Accumulate dot product
        s += float(a[i]) * ui
    return s


def project_control_onto_cbf_halfspace_with_box(
    *,
    u_nominal: Sequence[float],
    a: Sequence[float],
    b: float,
    u_min: Sequence[float],
    u_max: Sequence[float],
    tol: float = 1e-9,
    max_iter: int = 60,
    lambda_hint: float = 0.0,
) -> tuple[list[float], dict[str, Any]]:
    """
    Solve: minimize 1/2 ||u - u_nominal||^2 s.t. a^T u >= b and u_min <= u <= u_max.

    Returns (u_star, info) where info contains keys:
    - feasible: bool (feasible set[Any] non-empty)
    - lambda: float (dual for half-space, 0 if inactive)
    - iterations: int (root-finding steps if used)

    This is an exact solution for the single half-space + box case by dual search.
    """
    t0 = time.perf_counter()
    n = len(u_nominal)
    if n == 0:
        return [], {"feasible": True, "lambda": 0.0, "iterations": 0}

    # Initial clip to box
    u0 = _clip_vec(u_nominal, u_min, u_max)
    if _dot(a, u0) >= float(b) - tol:
        _observe_duration(t0)
        return u0, {"feasible": True, "lambda": 0.0, "iterations": 0}

    # Check feasibility of the set[Any]: maximize a^T u over box
    u_ext = _box_extreme_for_linear_form(a, u_min, u_max)
    if _dot(a, u_ext) < float(b) - tol:
        # Infeasible even with best box vertex
        _observe_duration(t0)
        _cbf_block("infeasible")
        return u_ext, {"feasible": False, "lambda": 0.0, "iterations": 0}

    # Monotone search in lambda ≥ 0 for a^T clip(u_nom + lambda a, box) = b
    # Use hint to bracket if provided
    lam_lo = 0.0
    lam_hi = 1.0

    if lambda_hint > 0:
        phi_hint = _phi_lambda(lambda_hint, u_nominal, a, u_min, u_max)
        if abs(phi_hint - float(b)) <= tol:
            # Hint was perfect
            u_star = _clip_vec(
                [float(u_nominal[i]) + lambda_hint * float(a[i]) for i in range(n)], u_min, u_max
            )
            _observe_duration(t0)
            return u_star, {"feasible": True, "lambda": lambda_hint, "iterations": 0}
        elif phi_hint < float(b):
            # Solution is to the right (larger lambda)
            lam_lo = lambda_hint
            lam_hi = max(1.0, lambda_hint * 2.0)
        else:
            # Solution is to the left (smaller lambda)
            lam_hi = lambda_hint

    # Find upper bound if needed
    it = 0
    while _phi_lambda(lam_hi, u_nominal, a, u_min, u_max) < float(b) - tol and it < max_iter:
        lam_lo = lam_hi  # Move lower bound up
        lam_hi *= 2.0
        it += 1

    # Bisection
    for _ in range(max_iter):
        lam_mid = 0.5 * (lam_lo + lam_hi)
        phi_mid = _phi_lambda(lam_mid, u_nominal, a, u_min, u_max)
        if abs(phi_mid - float(b)) <= tol:
            lam_lo = lam_hi = lam_mid
            break
        if phi_mid < float(b):
            lam_lo = lam_mid
        else:
            lam_hi = lam_mid

    lam_star = lam_hi
    u_star = _clip_vec(
        [float(u_nominal[i]) + lam_star * float(a[i]) for i in range(n)], u_min, u_max
    )
    _observe_duration(t0)
    return u_star, {"feasible": True, "lambda": lam_star, "iterations": it}


def _observe_duration(t0: float) -> None:
    pass  # Duration tracking removed (metric cleanup Dec 2025)


def _cbf_block(reason: str) -> None:
    try:
        from kagami_observability.metrics import CBF_BLOCKS_TOTAL

        # Use a generic operation label for strict_filter-level blocks.
        CBF_BLOCKS_TOTAL.labels(operation="strict_filter", reason=reason).inc()
    except (ImportError, RuntimeError) as e:
        logger.debug(f"Failed to record CBF block metric: {e}")
        # Metrics failure should not block safety enforcement


def strict_filter(
    *,
    u_nominal: Sequence[float],
    a: Sequence[float],
    b: float,
    u_min: Sequence[float],
    u_max: Sequence[float],
    robust_delta: float = 0.0,
    tol: float = 1e-9,
    max_iter: int = 60,
    lambda_hint: float = 0.0,
) -> dict[str, Any]:
    """Public API: strict control barrier filter (single half-space + box).

    Args:
        u_nominal: desired control vector
        a: CBF linear term (L_g h(x))
        b: CBF RHS (−L_f h(x) − α(h(x)))
        u_min/u_max: box bounds per control dimension
        lambda_hint: warm start value for dual variable
    Returns:
        {"u": list[float], "feasible": bool, "lambda": float, "iterations": int}
    """
    # Robust margin: enforce a^T u >= (b + robust_delta)
    b_eff = float(b) + float(robust_delta)
    u_star, info = project_control_onto_cbf_halfspace_with_box(
        u_nominal=u_nominal,
        a=a,
        b=b_eff,
        u_min=u_min,
        u_max=u_max,
        tol=tol,
        max_iter=max_iter,
        lambda_hint=lambda_hint,
    )
    return {"u": u_star, **info}


def strict_filter_multi(
    *,
    u_nominal: Sequence[float],
    constraints: Sequence[dict[str, Any]],
    u_min: Sequence[float],
    u_max: Sequence[float],
    robust_delta: float = 0.0,
    passes: int = 3,
    tol: float = 1e-9,
) -> dict[str, Any]:
    """Enforce multiple half-space constraints sequentially with box bounds.

    Args:
        constraints: iterable of {"a": seq[float], "b": float}
        robust_delta: added to each b for robustness
        passes: number of sequential projection passes over all constraints

    Returns:
        {"u": list[float], "feasible": bool}

    Note: This performs POCS-style sequential projections; not the exact
    projection onto the intersection but works well for small sets.
    """
    u = list(_clip_vec(u_nominal, u_min, u_max))
    feasible = True

    for _ in range(max(1, passes)):
        for c in constraints:
            a = c.get("a")
            b = c.get("b")
            if a is None or b is None:
                continue
            res = strict_filter(
                u_nominal=u,
                a=a,
                b=float(b),
                u_min=u_min,
                u_max=u_max,
                robust_delta=robust_delta,
                tol=tol,
            )
            u = res["u"]
            feasible = feasible and bool(res.get("feasible", True))

    # Verify all constraints satisfied within tol
    for c in constraints:
        a = c.get("a")
        b = c.get("b")
        if a is None or b is None:
            continue
        if _dot(a, u) < float(b) + float(robust_delta) - tol:
            feasible = False
            break

    return {"u": u, "feasible": feasible}


# =============================================================================
# DIFFERENTIABLE TIC SAFETY INTEGRATION (Dec 1, 2025)
# =============================================================================


def compute_tic_safety_margin(
    state: Sequence[float],
    invariant_names: list[str] | None = None,
) -> dict[str, Any]:
    """Compute safety margin using TIC InvariantEncoder.

    This connects the symbolic CBF constraints with the differentiable
    TIC system, enabling:
    1. Learned safety constraints from agent experience
    2. Gradient-based safety optimization
    3. Unified safety across policy and world model

    Args:
        state: Current state vector (14D G₂ or any dimension)
        invariant_names: Optional list[Any] of invariant names to check

    Returns:
        Dict with:
            safe: bool, whether h(x) ≥ 0 for all invariants
            margin: float, minimum h(x) across invariants
            h_values: list[float], individual invariant values
    """
    try:
        import torch
        from kagami.core.world_model.differentiable_tic import get_receipt_dynamics_model

        model = get_receipt_dynamics_model()
        invariant_encoder = model.tic_encoder.invariant_encoder

        # Convert state to tensor
        if not isinstance(state, torch.Tensor):  # type: ignore[unreachable]
            state_tensor = torch.tensor(list(state), dtype=torch.float32)
        else:
            state_tensor = state.clone().detach()  # type: ignore[unreachable]

        # Pad/truncate to expected dimension (14D for G₂)
        expected_dim = invariant_encoder.config.state_dim
        if state_tensor.shape[-1] > expected_dim:
            state_tensor = state_tensor[..., :expected_dim]
        elif state_tensor.shape[-1] < expected_dim:
            state_tensor = torch.nn.functional.pad(
                state_tensor,
                (0, expected_dim - state_tensor.shape[-1]),
            )

        # Compute barrier values
        h_values, margin = invariant_encoder(state_tensor, invariant_names)

        return {
            "safe": margin.item() >= 0,
            "margin": margin.item(),
            "h_values": h_values.tolist(),
        }

    except (ImportError, RuntimeError, AttributeError, TypeError) as e:
        logger.warning(f"TIC safety computation failed, defaulting to safe: {e}", exc_info=True)
        # Fallback: assume safe (fail-open for learned safety, fail-closed for symbolic CBF)
        # This is acceptable because TIC is supplementary to symbolic CBF checks
        return {
            "safe": True,
            "margin": 1.0,
            "h_values": [],
            "error": str(e),
        }


def enforce_with_tic_safety(
    intent: Any,
    state: Sequence[float] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Enforce CBF constraints with TIC safety integration.

    Combines application-level enforce() with learned TIC safety margins.
    If TIC indicates unsafe state, blocks the intent.

    Args:
        intent: Intent to check
        state: Optional current state for TIC safety check

    Returns:
        (decision, changes) where decision is "ok", "adjusted", or "blocked"
    """
    # First run standard enforce
    decision, changes = enforce(intent)

    if decision == "blocked":
        return decision, changes

    # Then check TIC safety if state provided
    if state is not None:
        tic_safety = compute_tic_safety_margin(state)

        if not tic_safety.get("safe", True):
            margin = tic_safety.get("margin", 0.0)
            return "blocked", {
                "reason": "tic_safety_violation",
                "safety_margin": margin,
                "original_decision": decision,
                "original_changes": changes,
            }

    return decision, changes
