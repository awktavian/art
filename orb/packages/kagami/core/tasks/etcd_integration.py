"""etcd integration for Celery tasks - ensures single-instance execution.

Provides decorators and utilities for Celery tasks to use consensus protocol,
preventing duplicate execution across multiple worker instances.

Uses KagamiConsensus for Byzantine-fault-tolerant coordination.
"""

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def _is_leader() -> bool:
    """Check if current instance is the consensus leader.

    Returns:
        True if leader or consensus unavailable (fail-safe).
    """
    try:
        from kagami.core.coordination.kagami_consensus import get_consensus_protocol

        consensus = get_consensus_protocol()
        if consensus:
            state = consensus.current_state  # type: ignore[attr-defined]
            return not state.converged or state.leader_id == consensus.instance_id  # type: ignore[attr-defined]
        return True  # No consensus = assume single instance
    except Exception:
        return True  # Fail-safe: assume leader


async def _is_leader_async() -> bool:
    """Async check if current instance is the consensus leader.

    Returns:
        True if leader or consensus unavailable (fail-safe).
    """
    return _is_leader()


def leader_only_task(role: str | None = None) -> dict[str, Any]:
    """Decorator for Celery tasks that should only run on the leader instance.

    Args:
        role: Leadership role (defaults to task name, used for logging)

    Usage:
        @celery_app.task
        @leader_only_task(role="training")
        def train_models():
            # Only runs on leader instance
            ...

    Returns:
        Decorated function that checks leadership before executing
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            task_role = role or func.__name__

            try:
                if not await _is_leader_async():
                    logger.info(
                        f"⏭️  Skipping task '{func.__name__}' - not leader for role '{task_role}'"
                    )
                    return {"skipped": True, "reason": "not_leader", "role": task_role}

                logger.info(f"🎖️  Executing task '{func.__name__}' as leader (role: {task_role})")
                result = await func(*args, **kwargs)

                # Emit metric
                try:
                    from kagami_observability.metrics import REGISTRY, Counter

                    if not hasattr(REGISTRY, "_leader_tasks_executed_total"):
                        REGISTRY._leader_tasks_executed_total = Counter(
                            "kagami_leader_tasks_executed_total",
                            "Tasks executed as leader",
                            ["task", "role"],
                            registry=REGISTRY,
                        )

                    REGISTRY._leader_tasks_executed_total.labels(
                        task=func.__name__, role=task_role
                    ).inc()
                except Exception:
                    pass

                return result  # type: ignore[no-any-return]

            except Exception as e:
                logger.error(f"Leader check failed for '{func.__name__}': {e}")
                logger.warning(f"Executing '{func.__name__}' without leadership check")
                return await func(*args, **kwargs)  # type: ignore[no-any-return]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            task_role = role or func.__name__

            try:
                if not _is_leader():
                    logger.info(
                        f"⏭️  Skipping task '{func.__name__}' - not leader for role '{task_role}'"
                    )
                    return {"skipped": True, "reason": "not_leader", "role": task_role}

                logger.info(f"🎖️  Executing task '{func.__name__}' as leader (role: {task_role})")
                result = func(*args, **kwargs)

                # Emit metric
                try:
                    from kagami_observability.metrics import REGISTRY, Counter

                    if not hasattr(REGISTRY, "_leader_tasks_executed_total"):
                        REGISTRY._leader_tasks_executed_total = Counter(
                            "kagami_leader_tasks_executed_total",
                            "Tasks executed as leader",
                            ["task", "role"],
                            registry=REGISTRY,
                        )

                    REGISTRY._leader_tasks_executed_total.labels(
                        task=func.__name__, role=task_role
                    ).inc()
                except Exception:
                    pass

                return result  # type: ignore[no-any-return]

            except Exception as e:
                logger.error(f"Leader check failed for '{func.__name__}': {e}")
                logger.warning(f"Executing '{func.__name__}' without leadership check")
                return func(*args, **kwargs)  # type: ignore[no-any-return]

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator  # type: ignore[return-value]


async def ensure_single_instance_execution(  # type: ignore[no-untyped-def]
    operation_name: str, func: Callable, *args, **kwargs: Any
) -> Any:
    """Ensure a function only executes on one instance via consensus.

    Args:
        operation_name: Name for the operation (for logging)
        func: Function to execute
        *args, **kwargs: Arguments to pass to function

    Returns:
        Function result or None if not leader

    Example:
        result = await ensure_single_instance_execution(
            "nightly_training",
            train_models,
            epochs=10
        )
    """
    try:
        if not await _is_leader_async():
            logger.info(f"⏭️  Skipping '{operation_name}' - not leader")
            return None

        logger.info(f"🎖️  Executing '{operation_name}' as leader")

        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    except Exception as e:
        logger.error(f"Consensus check failed for '{operation_name}': {e}")
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)


__all__ = ["ensure_single_instance_execution", "leader_only_task"]
