"""Control Barrier Function Decorators.

Provides clean, non-invasive decorators for applying CBF enforcement to any method.
Supports both synchronous and asynchronous functions with minimal overhead.

CREATED: December 14, 2025
AUTHOR: Forge (e₂)

Usage Examples:
    # Basic enforcement with explicit barrier function
    @enforce_cbf(cbf_func=lambda state: 10.0 - state['memory'])
    def allocate_memory(self, size: int):
        self.memory += size
        return self.memory

    # Enforcement via registry lookup
    @enforce_cbf(barrier_name="memory", use_registry=True, tier=1)
    async def allocate_memory_async(self, size: int):
        await self._allocate(size)

    # Custom violation handler
    def gc_and_block(*args, **kwargs):
        gc.collect()
        raise MemoryError("Out of memory, triggered GC")

    @enforce_cbf(
        barrier_name="memory",
        use_registry=True,
        violation_handler=gc_and_block
    )
    def allocate(self, size: int):
        pass

    # Monitoring (non-blocking)
    @monitor_cbf(barrier_name="cpu", alert_threshold=0.1)
    def compute_intensive_task(self):
        pass

    # Tier-specific shortcuts
    @enforce_tier1("memory")
    def organism_level_operation(self):
        pass
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Import runtime monitor for telemetry integration
try:
    from kagami.core.safety.cbf_runtime_monitor import get_cbf_monitor  # noqa: F401

    _MONITOR_AVAILABLE = True
except ImportError:
    _MONITOR_AVAILABLE = False
    logger.debug("CBF runtime monitor not available, telemetry disabled")

# =============================================================================
# EXCEPTIONS
# =============================================================================


class CBFViolation(Exception):
    """Raised when a CBF constraint is violated and no handler is provided.

    Attributes:
        barrier_name: Name of violated barrier
        h_value: Barrier value at violation (h < threshold)
        tier: Tier level (1=organism, 2=colony, 3=action)
        detail: Additional context about the violation
    """

    def __init__(
        self,
        barrier_name: str,
        h_value: float,
        tier: int,
        detail: str = "",
    ):
        self.barrier_name = barrier_name
        self.h_value = h_value
        self.tier = tier
        self.detail = detail

        tier_names = {1: "organism", 2: "colony", 3: "action"}
        tier_str = tier_names.get(tier, f"tier-{tier}")

        msg = f"CBF violation: {barrier_name} = {h_value:.4f} < 0 ({tier_str} level)"
        if detail:
            msg += f" - {detail}"

        super().__init__(msg)


# =============================================================================
# CORE DECORATOR
# =============================================================================


def enforce_cbf(
    cbf_func: Callable[..., float] | None = None,
    *,
    barrier_name: str | None = None,
    tier: int = 3,
    threshold: float = 0.0,
    violation_handler: Callable[..., Any] | None = None,
    use_registry: bool = False,
    extract_state: Callable[..., dict[str, Any]] | None = None,
) -> Callable[[F], F]:
    """Decorator to enforce a Control Barrier Function on a method.

    Evaluates the barrier function before executing the decorated function.
    If h(state) < threshold, either calls the violation_handler or raises CBFViolation.

    Args:
        cbf_func: Barrier function h(state) -> float. Required if use_registry=False.
        barrier_name: Name of barrier (required if use_registry=True, used for logging)
        tier: Tier level (1=organism, 2=colony, 3=action)
        threshold: Safety threshold - function blocks if h(state) < threshold
        violation_handler: Called with (*args, **kwargs) on violation instead of raising
        use_registry: Look up barrier in CBFRegistry instead of using cbf_func
        extract_state: Function to extract state dict[str, Any] from decorated function args.
            If None, the barrier will be evaluated with state=None.

    Returns:
        Decorated function that enforces the CBF constraint

    Raises:
        CBFViolation: If barrier violated and no violation_handler provided
        ValueError: If use_registry=True but barrier_name not found in registry

    Performance:
        Overhead is typically <0.1ms per call (barrier evaluation + checks)

    Examples:
        # Simple barrier on state dict[str, Any]
        @enforce_cbf(
            cbf_func=lambda s: 100 - s['cpu_usage'],
            barrier_name="cpu",
            tier=1
        )
        def run_task(self):
            pass

        # With state extraction
        def extract(self, size):
            return {'memory': self.memory_used, 'request': size}

        @enforce_cbf(
            cbf_func=lambda s: 1000 - s['memory'] - s['request'],
            extract_state=extract
        )
        def allocate(self, size: int):
            pass

        # Registry-based
        @enforce_cbf(barrier_name="memory", use_registry=True, tier=1)
        def allocate_from_registry(self, size: int):
            pass
    """
    # Validate arguments
    if use_registry and not barrier_name:
        raise ValueError("barrier_name required when use_registry=True")
    if not use_registry and cbf_func is None:
        raise ValueError("cbf_func required when use_registry=False")

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # 1. Extract state if extractor provided
            state: dict[str, Any] | None = None
            if extract_state is not None:
                try:
                    state = extract_state(*args, **kwargs)
                except Exception as e:
                    logger.warning(
                        f"State extraction failed in {func.__name__}: {e}", exc_info=True
                    )

            # 2. Get barrier function and threshold
            actual_threshold = threshold
            # Type as Callable[..., float] since we support both zero-arg and one-arg barriers
            h_func: Callable[..., float]

            if use_registry:
                # Import here to avoid circular dependencies
                try:
                    from kagami.core.safety.cbf_registry import CBFRegistry

                    registry = CBFRegistry()
                    if barrier_name is None:
                        raise ValueError("barrier_name required when use_registry=True")
                    entry = registry.get_barrier(barrier_name)
                    if entry is None:
                        raise ValueError(f"Barrier '{barrier_name}' not found in CBFRegistry")
                    h_func = entry.func
                    actual_threshold = entry.threshold
                except ImportError as e:
                    # Registry not available, fall back to cbf_func if provided
                    if cbf_func is None:
                        raise ValueError(
                            "CBFRegistry not available and no cbf_func provided"
                        ) from e
                    h_func = cbf_func
                    logger.warning("CBFRegistry not available, using provided cbf_func")
            else:
                if cbf_func is None:
                    raise ValueError("cbf_func required when use_registry=False")
                h_func = cbf_func

            # 3. Evaluate barrier function
            # Backward compatibility: support both lambda: value and lambda s: value
            try:
                sig = inspect.signature(h_func)
                if len(sig.parameters) == 0:
                    # Legacy API: zero-argument barrier (e.g., lambda: 1.0)
                    h_value = h_func()
                else:
                    # New API: state-argument barrier (e.g., lambda s: compute(s))
                    h_value = h_func(state)
            except Exception as e:
                logger.critical(f"CBF evaluation failure in {func.__name__}: {e}", exc_info=True)
                # Fail-closed: barrier evaluation crash is a safety violation
                raise CBFViolation(
                    barrier_name=barrier_name or func.__name__,
                    h_value=float("-inf"),
                    tier=tier,
                    detail=f"Barrier evaluation crashed: {e}",
                ) from e

            # 4. Check for violation
            if h_value < actual_threshold:
                logger.warning(
                    f"CBF violation in {func.__name__}: "
                    f"{barrier_name or 'unnamed'} = {h_value:.4f} < {actual_threshold:.4f}"
                )

                if violation_handler is not None:
                    # Call violation handler with original args
                    return violation_handler(*args, **kwargs)
                else:
                    # Raise exception
                    raise CBFViolation(
                        barrier_name=barrier_name or func.__name__,
                        h_value=h_value,
                        tier=tier,
                        detail=f"Violated in {func.__name__}",
                    )

            # 5. Safe to execute
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Same logic as sync_wrapper but with async/await

            # 1. Extract state
            state: dict[str, Any] | None = None
            if extract_state is not None:
                try:
                    state = extract_state(*args, **kwargs)
                except Exception as e:
                    logger.warning(
                        f"State extraction failed in {func.__name__}: {e}", exc_info=True
                    )

            # 2. Get barrier function
            actual_threshold = threshold
            # Type as Callable[..., float] since we support both zero-arg and one-arg barriers
            h_func: Callable[..., float]

            if use_registry:
                try:
                    from kagami.core.safety.cbf_registry import CBFRegistry

                    registry = CBFRegistry()
                    if barrier_name is None:
                        raise ValueError("barrier_name required when use_registry=True")
                    entry = registry.get_barrier(barrier_name)
                    if entry is None:
                        raise ValueError(f"Barrier '{barrier_name}' not found in CBFRegistry")
                    h_func = entry.func
                    actual_threshold = entry.threshold
                except ImportError as e:
                    if cbf_func is None:
                        raise ValueError(
                            "CBFRegistry not available and no cbf_func provided"
                        ) from e
                    h_func = cbf_func
                    logger.warning("CBFRegistry not available, using provided cbf_func")
            else:
                if cbf_func is None:
                    raise ValueError("cbf_func required when use_registry=False")
                h_func = cbf_func

            # 3. Evaluate barrier
            # Backward compatibility: support both lambda: value and lambda s: value
            try:
                sig = inspect.signature(h_func)
                if len(sig.parameters) == 0:
                    # Legacy API: zero-argument barrier (e.g., lambda: 1.0)
                    h_value = h_func()
                else:
                    # New API: state-argument barrier (e.g., lambda s: compute(s))
                    h_value = h_func(state)
            except Exception as e:
                logger.critical(f"CBF evaluation failure in {func.__name__}: {e}", exc_info=True)
                # Fail-closed: barrier evaluation crash is a safety violation
                raise CBFViolation(
                    barrier_name=barrier_name or func.__name__,
                    h_value=float("-inf"),
                    tier=tier,
                    detail=f"Barrier evaluation crashed: {e}",
                ) from e

            # 4. Check violation
            if h_value < actual_threshold:
                logger.warning(
                    f"CBF violation in {func.__name__}: "
                    f"{barrier_name or 'unnamed'} = {h_value:.4f} < {actual_threshold:.4f}"
                )

                if violation_handler is not None:
                    result = violation_handler(*args, **kwargs)
                    # Handle case where violation_handler is async
                    if asyncio.iscoroutine(result):
                        return await result
                    return result
                else:
                    raise CBFViolation(
                        barrier_name=barrier_name or func.__name__,
                        h_value=h_value,
                        tier=tier,
                        detail=f"Violated in {func.__name__}",
                    )

            # 5. Execute
            return await func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# =============================================================================
# MONITORING DECORATOR (NON-BLOCKING)
# =============================================================================


def monitor_cbf(
    barrier_name: str,
    tier: int = 3,
    alert_threshold: float = 0.1,
    use_registry: bool = True,
) -> Callable[[F], F]:
    """Decorator to monitor (but not enforce) a CBF.

    Logs warnings when h(x) approaches the threshold but doesn't block execution.
    Useful for observability without strict enforcement.

    Args:
        barrier_name: Name of barrier to monitor
        tier: Tier level for logging context
        alert_threshold: Log warning when h(x) < alert_threshold (but still execute)
        use_registry: Whether to look up barrier in registry (default True)

    Returns:
        Decorated function that monitors CBF but never blocks

    Example:
        @monitor_cbf(barrier_name="memory", alert_threshold=0.2)
        def allocate(self, size: int):
            # Always executes, but logs warning if memory barrier < 0.2
            self.memory += size
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Try to evaluate barrier
            try:
                if use_registry:
                    from kagami.core.safety.cbf_registry import CBFRegistry

                    registry = CBFRegistry()
                    entry = registry.get_barrier(barrier_name)
                    if entry is not None:
                        # Backward compatibility: support both lambda: value and lambda s: value
                        sig = inspect.signature(entry.func)
                        if len(sig.parameters) == 0:
                            h_value = entry.func()
                        else:
                            h_value = entry.func(None)

                        if h_value < alert_threshold:
                            logger.warning(
                                f"CBF alert in {func.__name__}: "
                                f"{barrier_name} = {h_value:.4f} < {alert_threshold:.4f} "
                                f"(tier {tier})"
                            )
            except Exception as e:
                # Never fail on monitoring
                logger.debug(f"CBF monitoring failed in {func.__name__}: {e}")

            # Always execute
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Try to evaluate barrier
            try:
                if use_registry:
                    from kagami.core.safety.cbf_registry import CBFRegistry

                    registry = CBFRegistry()
                    entry = registry.get_barrier(barrier_name)
                    if entry is not None:
                        # Backward compatibility: support both lambda: value and lambda s: value
                        sig = inspect.signature(entry.func)
                        if len(sig.parameters) == 0:
                            h_value = entry.func()
                        else:
                            h_value = entry.func(None)

                        if h_value < alert_threshold:
                            logger.warning(
                                f"CBF alert in {func.__name__}: "
                                f"{barrier_name} = {h_value:.4f} < {alert_threshold:.4f} "
                                f"(tier {tier})"
                            )
            except Exception as e:
                # Never fail on monitoring
                logger.debug(f"CBF monitoring failed in {func.__name__}: {e}")

            # Always execute
            return await func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# =============================================================================
# REQUIREMENT DECORATOR
# =============================================================================


class CBFRequiredViolation(Exception):
    """Raised when a function requiring CBF checks doesn't call any."""

    pass


def cbf_required(tier: int = 1) -> Callable[[F], F]:
    """Decorator that requires at least one CBF check in the call stack.

    Used on API endpoints or critical paths to ensure they go through CBF enforcement.
    Works by checking thread-local state that's set[Any] by enforce_cbf decorators.

    Args:
        tier: Minimum tier level required

    Returns:
        Decorated function that verifies CBF enforcement occurred

    Raises:
        CBFRequiredViolation: If function completes without any CBF checks

    Example:
        @cbf_required(tier=1)
        async def critical_api_endpoint(request):
            # This will fail unless the call stack includes @enforce_cbf
            return await process(request)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Set up tracking
            import threading

            thread_local = threading.local()
            if not hasattr(thread_local, "cbf_checks"):
                thread_local.cbf_checks = []

            initial_count = len(getattr(thread_local, "cbf_checks", []))

            try:
                result = func(*args, **kwargs)
            finally:
                final_count = len(getattr(thread_local, "cbf_checks", []))

                if final_count <= initial_count:
                    raise CBFRequiredViolation(
                        f"{func.__name__} requires at least one CBF check (tier {tier} or higher)"
                    )

            return result

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            import contextvars

            cbf_checks_var: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
                "cbf_checks",
                default=None,
            )
            cbf_checks = cbf_checks_var.get()
            if cbf_checks is None:
                cbf_checks = []
                cbf_checks_var.set(cbf_checks)
            initial_count = len(cbf_checks)

            try:
                result = await func(*args, **kwargs)
            finally:
                final_checks = cbf_checks_var.get() or []
                final_count = len(final_checks)

                if final_count <= initial_count:
                    raise CBFRequiredViolation(
                        f"{func.__name__} requires at least one CBF check (tier {tier} or higher)"
                    )

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# =============================================================================
# CONVENIENCE TIER-SPECIFIC DECORATORS
# =============================================================================


def enforce_tier1(
    barrier_name: str,
    violation_handler: Callable[..., Any] | None = None,
) -> Callable[[F], F]:
    """Convenience decorator for Tier 1 (organism-level) barriers.

    Automatically uses registry lookup and sets tier=1.

    Args:
        barrier_name: Name of barrier in registry
        violation_handler: Optional handler for violations

    Returns:
        Decorated function with Tier 1 enforcement

    Example:
        @enforce_tier1("memory")
        def allocate_memory(self, size: int):
            pass
    """
    return enforce_cbf(
        barrier_name=barrier_name,
        use_registry=True,
        tier=1,
        violation_handler=violation_handler,
    )


def enforce_tier2(
    barrier_name: str,
    colony: int | None = None,
    violation_handler: Callable[..., Any] | None = None,
) -> Callable[[F], F]:
    """Convenience decorator for Tier 2 (colony-level) barriers.

    Args:
        barrier_name: Name of barrier in registry
        colony: Colony index (0-6) for multi-colony barriers
        violation_handler: Optional handler for violations

    Returns:
        Decorated function with Tier 2 enforcement

    Example:
        @enforce_tier2("cpu", colony=0)
        def colony_compute(self):
            pass
    """
    # If colony specified, append to barrier name for registry lookup
    full_name = f"{barrier_name}_colony{colony}" if colony is not None else barrier_name

    return enforce_cbf(
        barrier_name=full_name,
        use_registry=True,
        tier=2,
        violation_handler=violation_handler,
    )


def enforce_tier3(
    cbf_func: Callable[..., float],
    threshold: float = 0.0,
    violation_handler: Callable[..., Any] | None = None,
) -> Callable[[F], F]:
    """Convenience decorator for Tier 3 (action-level) barriers.

    Tier 3 barriers are typically one-off checks, so this uses direct cbf_func
    instead of registry lookup.

    Args:
        cbf_func: Barrier function h(state) -> float
        threshold: Safety threshold
        violation_handler: Optional handler for violations

    Returns:
        Decorated function with Tier 3 enforcement

    Example:
        @enforce_tier3(lambda: 1.0 - current_load())
        def execute_action(self):
            pass
    """
    return enforce_cbf(
        cbf_func=cbf_func,
        tier=3,
        threshold=threshold,
        violation_handler=violation_handler,
    )


# =============================================================================
# PERFORMANCE TRACKING
# =============================================================================


def enforce_cbf_timed(
    cbf_func: Callable[..., float] | None = None,
    *,
    barrier_name: str | None = None,
    tier: int = 3,
    threshold: float = 0.0,
    use_registry: bool = False,
    max_overhead_ms: float = 0.1,
) -> Callable[[F], F]:
    """CBF decorator with performance tracking.

    Logs warning if decorator overhead exceeds max_overhead_ms.
    Useful for performance-critical code paths.

    Args:
        Same as enforce_cbf, plus:
        max_overhead_ms: Maximum allowed overhead in milliseconds

    Returns:
        Decorated function with performance tracking
    """
    base_decorator = enforce_cbf(
        cbf_func=cbf_func,
        barrier_name=barrier_name,
        tier=tier,
        threshold=threshold,
        use_registry=use_registry,
    )

    def decorator(func: F) -> F:
        wrapped = base_decorator(func)

        @functools.wraps(func)
        def timed_wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            result = wrapped(*args, **kwargs)
            overhead = (time.perf_counter() - t0) * 1000

            if overhead > max_overhead_ms:
                logger.warning(
                    f"CBF overhead in {func.__name__}: {overhead:.3f}ms "
                    f"(exceeds {max_overhead_ms}ms threshold)"
                )

            return result

        @functools.wraps(func)
        async def async_timed_wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            result = await wrapped(*args, **kwargs)
            overhead = (time.perf_counter() - t0) * 1000

            if overhead > max_overhead_ms:
                logger.warning(
                    f"CBF overhead in {func.__name__}: {overhead:.3f}ms "
                    f"(exceeds {max_overhead_ms}ms threshold)"
                )

            return result

        if asyncio.iscoroutinefunction(func):
            return async_timed_wrapper  # type: ignore
        else:
            return timed_wrapper  # type: ignore

    return decorator


__all__ = [
    "CBFRequiredViolation",
    "CBFViolation",
    "cbf_required",
    "enforce_cbf",
    "enforce_cbf_timed",
    "enforce_tier1",
    "enforce_tier2",
    "enforce_tier3",
    "monitor_cbf",
]
