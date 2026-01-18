"""Universal CBF Enforcement System.

CREATED: December 14, 2025
PURPOSE: Global singleton + decorator for zero-friction CBF enforcement

This module provides universal enforcement of Control Barrier Function (CBF)
constraints across ALL state-generating functions in the codebase.

DESIGN PRINCIPLES:
==================
1. **Global Singleton**: Single source of truth for CBF enforcement state
2. **Decorator Pattern**: Zero-friction integration via @enforce_cbf
3. **Projection on Violation**: Auto-project to safe set[Any] vs hard errors
4. **Thread-Safe**: Singleton supports concurrent access
5. **Performance**: Minimal overhead when enforcement disabled

USAGE PATTERNS:
===============
1. Function Decorator:
    @enforce_cbf(state_param="x", action_param="u")
    def dynamics_step(x, u):
        return next_state  # Auto-checked and projected if needed

2. Runtime Assertion:
    assert_cbf(state, action, "Custom error message")

3. Context Manager:
    with cbf_enforcement_disabled():
        unsafe_state = exploration_policy()  # CBF temporarily off

4. Manual Projection:
    safe_state = project_to_safe_set(unsafe_state)

MATHEMATICAL FOUNDATION:
========================
Safe set[Any]: C = {x ∈ ℝⁿ | h(x) ≥ 0}

Enforcement:
- If h(x) ≥ 0: Pass through (already safe)
- If h(x) < 0: Project to safe boundary via gradient ascent
    x_safe = x + α * ∇h(x)  until h(x_safe) ≥ 0

References:
- Ames et al. (2019): Control Barrier Functions: Theory and Applications
- K OS Architecture: Universal Safety Enforcement
"""

from __future__ import annotations

import functools
import logging
import threading
import traceback
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, TypeVar, cast

import torch

from kagami.core.safety.optimal_cbf import OptimalCBF, get_optimal_cbf

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("kagami.security.audit")

# Type variables for decorator
F_co = TypeVar("F_co", bound=Callable[..., Any])

# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================


class CBFViolationError(Exception):
    """Exception raised when CBF constraint is violated.

    Raised when project_to_safe=False and h(x) < 0.
    """

    def __init__(
        self,
        message: str,
        state: torch.Tensor,
        barrier_value: float,
        action: torch.Tensor | None = None,
    ):
        """Initialize CBF violation error.

        Args:
            message: Error message
            state: State that violated constraint
            barrier_value: h(x) value (negative)
            action: Optional action that led to violation
        """
        super().__init__(message)
        self.state = state
        self.barrier_value = barrier_value
        self.action = action


# =============================================================================
# GLOBAL CBF SINGLETON
# =============================================================================


class UniversalCBFEnforcer:
    """Global singleton for universal CBF enforcement.

    Thread-safe singleton that ensures ALL state-generating functions
    pass h(x) >= 0 check. Provides:
    - Decorator for automatic enforcement
    - Runtime assertions
    - Context manager for temporary disable
    - Projection to safe set[Any]

    THREAD SAFETY:
    ==============
    Uses threading.Lock for singleton creation and enforcement state changes.
    Multiple threads can check CBF concurrently (reads are lock-free).
    """

    def __init__(self) -> None:
        """Initialize enforcer.

        NOTE: Use get_cbf_enforcer() instead of direct instantiation.
        """
        self.cbf: OptimalCBF = get_optimal_cbf()
        self.violation_count = 0
        self.projection_count = 0
        self.check_count = 0
        self._enforcement_enabled = True
        self._state_lock = threading.Lock()

        logger.info("✅ UniversalCBFEnforcer initialized (global singleton)")

    @property
    def enforcement_enabled(self) -> bool:
        """Check if enforcement is enabled (thread-safe read)."""
        return self._enforcement_enabled

    @enforcement_enabled.setter
    def enforcement_enabled(self, value: bool) -> None:
        """Set enforcement enabled (thread-safe write)."""
        with self._state_lock:
            self._enforcement_enabled = value

    def compute_barrier(
        self,
        state: torch.Tensor,
        action: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Compute barrier function h(x).

        Args:
            state: State tensor [B, state_dim] or [state_dim]
            action: Optional action tensor [B, control_dim] or [control_dim]

        Returns:
            h: Barrier values [B] or scalar
        """
        # Ensure batch dimension
        if state.dim() == 1:
            state = state.unsqueeze(0)
            squeeze_output = True
        else:
            squeeze_output = False

        # Compute barrier via OptimalCBF
        with torch.no_grad():
            # OptimalCBF expects observations, but we pass states
            # Use barrier_value() method which handles this
            h = self.cbf.barrier_value(state)

        if squeeze_output:
            h = h.squeeze(0)

        return h

    def is_safe(
        self,
        state: torch.Tensor,
        action: torch.Tensor | None = None,
    ) -> bool:
        """Check if state satisfies CBF constraint.

        Args:
            state: State tensor
            action: Optional action tensor

        Returns:
            True if h(x) >= 0, False otherwise
        """
        with self._state_lock:
            self.check_count += 1
            # Check enforcement status under lock to prevent race condition
            if not self._enforcement_enabled:
                logger.debug("CBF enforcement is disabled, assuming safe")
                return (
                    True  # When enforcement disabled, allow operations (consistent with enforce())
                )
            # Compute barrier inside lock to ensure atomicity
            h = self.compute_barrier(state, action)

        # Check barrier value outside lock (safe since h is a local copy)
        if h.dim() == 0:
            return bool(h.item() >= 0)
        else:
            return bool((h >= 0).all().item())

    def project_to_safe_set(
        self,
        state: torch.Tensor,
        action: torch.Tensor | None = None,
        max_iterations: int = 20,
        step_size: float = 0.1,
        *,
        adaptive_step: bool = True,
        momentum: float = 0.9,
    ) -> torch.Tensor:
        """Project state to nearest point in safe set {x | h(x) >= 0}.

        Uses Newton-Raphson-inspired gradient ascent with line search:
        x_safe = x + α * ∇h(x) / ||∇h(x)||

        HARDENED (Jan 4, 2026): Improved convergence via:
        - Normalized gradient direction (unit step direction)
        - Armijo line search for step size
        - Increased max_iterations (10 -> 20)
        - Backtracking when h decreases

        ENHANCED (Jan 4, 2026 - Byzantine consensus):
        - Adaptive step size based on violation severity
        - Momentum for faster convergence in flat regions
        - Stronger safety guarantees with multi-try verification

        Args:
            state: State tensor [B, state_dim] or [state_dim]
            action: Optional action tensor
            max_iterations: Maximum projection iterations
            step_size: Base step size for gradient ascent
            adaptive_step: Scale step by violation severity (default: True)
            momentum: Momentum coefficient for faster convergence (default: 0.9)

        Returns:
            state_safe: Projected state (same shape as input)
        """
        squeeze_output = state.dim() == 1

        if squeeze_output:
            state = state.unsqueeze(0)

        state_safe = state.clone().requires_grad_(True)
        prev_h_min = float("-inf")
        velocity = torch.zeros_like(state_safe)  # Momentum buffer

        for i in range(max_iterations):
            # Compute barrier
            h = self.cbf.barrier_value(state_safe)

            # Check if already safe (with small margin for numerical stability)
            if (h >= -1e-6).all():
                logger.debug(f"Projection converged at iteration {i}")
                break

            # Compute gradient ∇h(x)
            grad_h = torch.autograd.grad(
                outputs=h.sum(),
                inputs=state_safe,
                create_graph=False,
            )[0]

            # Normalize gradient for unit direction (Newton-Raphson style)
            grad_norm = grad_h.norm(dim=-1, keepdim=True).clamp(min=1e-8)
            grad_direction = grad_h / grad_norm

            # Current minimum barrier value
            h_min = h.min().item()

            # Armijo-style line search: try step, backtrack if h decreases
            # ENHANCED: Adaptive step based on violation severity + momentum
            if adaptive_step:
                alpha = step_size * max(1.0, abs(h_min) ** 0.5)  # sqrt scaling for stability
            else:
                alpha = step_size * max(1.0, abs(h_min))  # Linear scaling (original)
            best_alpha = alpha
            best_h_min = h_min

            for _backtrack in range(4):  # Max 4 backtracking steps
                with torch.no_grad():
                    candidate = state_safe + alpha * grad_direction
                h_candidate = self.cbf.barrier_value(candidate)
                candidate_h_min = h_candidate.min().item()

                if candidate_h_min > h_min:  # Improvement found
                    best_alpha = alpha
                    best_h_min = candidate_h_min
                    break
                alpha *= 0.5  # Backtrack

            # Gradient ascent with best step + momentum
            with torch.no_grad():
                # Update velocity with momentum
                velocity = momentum * velocity + best_alpha * grad_direction
                state_safe = state_safe + velocity
                state_safe.requires_grad_(True)

            # Check for stagnation (no improvement for 2 iterations)
            if best_h_min <= prev_h_min + 1e-8 and i > 2:
                logger.debug(f"Projection stagnated at iteration {i}, h_min={best_h_min:.4f}")
                break
            prev_h_min = best_h_min

        # Final check
        h_final = self.cbf.barrier_value(state_safe.detach())
        if (h_final < 0).any():
            h_min = h_final.min().item()
            logger.error(
                f"Projection failed to reach safe set[Any]: "
                f"h_min={h_min:.4f} (still negative after {max_iterations} iters)"
            )
            with self._state_lock:
                self.violation_count += 1

            # FAIL-CLOSED: Raise exception instead of returning unsafe state
            raise CBFViolationError(
                message=(
                    f"Projection to safe set[Any] failed after {max_iterations} iterations: "
                    f"h={h_min:.4f} < 0. The state could not be safely projected."
                ),
                state=state_safe.detach(),
                barrier_value=h_min,
                action=action,
            )
        else:
            with self._state_lock:
                self.projection_count += 1

        result = state_safe.detach()
        if squeeze_output:
            result = result.squeeze(0)

        return result

    def enforce(
        self,
        state: torch.Tensor,
        action: torch.Tensor | None = None,
        project_to_safe: bool = True,
        context: str = "unknown",
    ) -> torch.Tensor:
        """Enforce CBF constraint on state.

        Args:
            state: State tensor
            action: Optional action tensor
            project_to_safe: If True, project violations to safe set[Any].
                            If False, raise CBFViolationError.
            context: Context string for logging (e.g., function name)

        Returns:
            state_safe: Original state (if safe) or projected state

        Raises:
            CBFViolationError: If project_to_safe=False and h(x) < 0
        """
        if not self._enforcement_enabled:
            return state

        with self._state_lock:
            self.check_count += 1

        # Check barrier
        h = self.compute_barrier(state, action)
        is_safe = (h >= 0).all() if h.dim() > 0 else h.item() >= 0

        if is_safe:
            return state

        # Violation detected
        h_min = h.min().item() if h.dim() > 0 else h.item()

        if project_to_safe:
            logger.warning(
                f"CBF violation in {context}: h={h_min:.4f} < 0, projecting to safe set[Any]"
            )
            state_safe = self.project_to_safe_set(state, action)
            return state_safe
        else:
            with self._state_lock:
                self.violation_count += 1
            raise CBFViolationError(
                message=f"CBF violation in {context}: h={h_min:.4f} < 0",
                state=state,
                barrier_value=h_min,
                action=action,
            )

    def get_stats(self) -> dict[str, int]:
        """Get enforcement statistics.

        Returns:
            Dict with check_count, violation_count, projection_count
        """
        with self._state_lock:
            return {
                "check_count": self.check_count,
                "violation_count": self.violation_count,
                "projection_count": self.projection_count,
            }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        with self._state_lock:
            self.check_count = 0
            self.violation_count = 0
            self.projection_count = 0


# =============================================================================
# DECORATOR
# =============================================================================


def enforce_cbf(
    state_param: str = "state",
    action_param: str | None = None,
    project_to_safe: bool = True,
    check_output: bool = True,
    check_input: bool = False,
) -> Callable[[F_co], F_co]:
    """Decorator to enforce CBF constraints on function outputs.

    Automatically checks and projects function outputs to safe set[Any].
    Zero friction: just add @enforce_cbf to any state-generating function.

    Args:
        state_param: Name of state parameter in function signature
        action_param: Name of action parameter (None = state-only check)
        project_to_safe: If True, project violations to safe set[Any].
                        If False, raise CBFViolationError.
        check_output: If True, enforce CBF on output state
        check_input: If True, enforce CBF on input state

    Returns:
        Decorated function with automatic CBF enforcement

    Usage:
        @enforce_cbf(state_param="x", action_param="u")
        def dynamics_step(x: torch.Tensor, u: torch.Tensor) -> torch.Tensor:
            return next_state  # Auto-checked, projected if h < 0

        @enforce_cbf(state_param="state", check_input=True, check_output=True)
        def safe_function(state: torch.Tensor) -> torch.Tensor:
            # Both input and output are enforced
            return modified_state
    """

    def decorator(func: F_co) -> F_co:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            enforcer = get_cbf_enforcer()

            if not enforcer.enforcement_enabled:
                return func(*args, **kwargs)

            # Extract state and action from parameters
            # Try kwargs first, then positional args
            state: torch.Tensor | None = None
            action: torch.Tensor | None = None

            # Get state
            if state_param in kwargs:
                state = kwargs[state_param]
            else:
                # Try to infer from function signature
                import inspect

                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                if state_param in param_names:
                    idx = param_names.index(state_param)
                    if idx < len(args):
                        state = args[idx]

            # Get action
            if action_param is not None:
                if action_param in kwargs:
                    action = kwargs[action_param]
                else:
                    import inspect

                    sig = inspect.signature(func)
                    param_names = list(sig.parameters.keys())
                    if action_param in param_names:
                        idx = param_names.index(action_param)
                        if idx < len(args):
                            action = args[idx]

            # Check input if requested
            if check_input and state is not None:
                state = enforcer.enforce(
                    state=state,
                    action=action,
                    project_to_safe=project_to_safe,
                    context=f"{func.__name__}[input]",
                )
                # Update args/kwargs with safe state
                if state_param in kwargs:
                    kwargs[state_param] = state
                else:
                    import inspect

                    sig = inspect.signature(func)
                    param_names = list(sig.parameters.keys())
                    if state_param in param_names:
                        idx = param_names.index(state_param)
                        if idx < len(args):
                            args_list = list(args)
                            args_list[idx] = state
                            args = tuple(args_list)

            # Execute function
            result = func(*args, **kwargs)

            # Check output if requested
            if check_output and isinstance(result, torch.Tensor):
                result = enforcer.enforce(
                    state=result,
                    action=action,
                    project_to_safe=project_to_safe,
                    context=f"{func.__name__}[output]",
                )

            return result

        return cast(F_co, wrapper)

    return decorator


# =============================================================================
# CONTEXT MANAGER
# =============================================================================


@contextmanager
def cbf_enforcement_disabled(reason: str = "exploration") -> Generator[None, None, None]:
    """Temporarily disable CBF enforcement (USE WITH CAUTION).

    Useful for exploration, debugging, or controlled unsafe operations.
    All disable events are logged to security audit log.

    Args:
        reason: Justification for disabling (logged for audit)

    Usage:
        with cbf_enforcement_disabled(reason="controlled_exploration"):
            # CBF checks are skipped
            unsafe_state = exploration_policy()
            risky_operation(unsafe_state)
    """
    enforcer = get_cbf_enforcer()
    original_state = enforcer.enforcement_enabled

    # AUDIT LOG: Record bypass event with stack trace
    disable_timestamp = datetime.now(UTC).isoformat()
    audit_logger.warning(
        "CBF_ENFORCEMENT_DISABLED",
        extra={
            "reason": reason,
            "timestamp": disable_timestamp,
            "stack_trace": "".join(traceback.format_stack()[-5:]),
            "thread_id": threading.get_ident(),
        },
    )

    try:
        enforcer.enforcement_enabled = False
        logger.debug(f"CBF enforcement temporarily disabled: {reason}")
        yield
    finally:
        enforcer.enforcement_enabled = original_state
        restore_timestamp = datetime.now(UTC).isoformat()

        # AUDIT LOG: Record restoration
        audit_logger.info(
            "CBF_ENFORCEMENT_RESTORED",
            extra={
                "timestamp": restore_timestamp,
                "original_state": original_state,
                "reason": reason,
            },
        )
        logger.debug(f"CBF enforcement restored to {original_state}")


# =============================================================================
# RUNTIME ASSERTION
# =============================================================================


def assert_cbf(
    state: torch.Tensor,
    action: torch.Tensor | None = None,
    message: str = "",
) -> None:
    """Runtime assertion for CBF constraint.

    Raises CBFViolationError if h(x) < 0.
    Use this for critical checkpoints where violations should never happen.

    Args:
        state: State tensor
        action: Optional action tensor
        message: Custom error message

    Raises:
        CBFViolationError: If h(x) < 0

    Usage:
        assert_cbf(next_state, action, "Dynamics must preserve safety")
    """
    enforcer = get_cbf_enforcer()

    if not enforcer.enforcement_enabled:
        return

    h = enforcer.compute_barrier(state, action)
    h_min = h.min().item() if h.dim() > 0 else h.item()

    if h_min < 0:
        raise CBFViolationError(
            message=f"CBF assertion failed: h={h_min:.4f} < 0. {message}",
            state=state,
            barrier_value=h_min,
            action=action,
        )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def project_to_safe_set(
    state: torch.Tensor,
    action: torch.Tensor | None = None,
    max_iterations: int = 10,
) -> torch.Tensor:
    """Project state to safe set[Any] {x | h(x) >= 0}.

    Convenience function for manual projection.

    Args:
        state: State tensor
        action: Optional action tensor
        max_iterations: Maximum projection iterations

    Returns:
        state_safe: Projected state
    """
    enforcer = get_cbf_enforcer()
    return enforcer.project_to_safe_set(state, action, max_iterations)


def is_safe(
    state: torch.Tensor,
    action: torch.Tensor | None = None,
) -> bool:
    """Check if state satisfies CBF constraint.

    Args:
        state: State tensor
        action: Optional action tensor

    Returns:
        True if h(x) >= 0, False otherwise
    """
    enforcer = get_cbf_enforcer()
    return enforcer.is_safe(state, action)


def get_cbf_stats() -> dict[str, int]:
    """Get global CBF enforcement statistics.

    Returns:
        Dict with check_count, violation_count, projection_count
    """
    enforcer = get_cbf_enforcer()
    return enforcer.get_stats()


def reset_cbf_stats() -> None:
    """Reset global CBF enforcement statistics."""
    enforcer = get_cbf_enforcer()
    enforcer.reset_stats()


# =============================================================================
# SINGLETON FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_cbf_enforcer = _singleton_registry.register_sync("universal_cbf_enforcer", UniversalCBFEnforcer)


def reset_cbf_enforcer_instance() -> None:
    """Reset singleton (for testing only).

    WARNING: Only use in single-threaded test cleanup.
    """
    _singleton_registry.reset("universal_cbf_enforcer")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CBFViolationError",
    "UniversalCBFEnforcer",
    "assert_cbf",
    "cbf_enforcement_disabled",
    "enforce_cbf",
    "get_cbf_enforcer",
    "get_cbf_stats",
    "is_safe",
    "project_to_safe_set",
    "reset_cbf_enforcer_instance",
    "reset_cbf_stats",
]
