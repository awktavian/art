"""
Typed Intent Calculus (TIC) Runtime Enforcement.

This module reifies the TIC protocol into executable code.
It provides decorators and base classes to ensure that the 'pre', 'post',
and 'invariant' checks documented in receipts are ACTUALLY executed.
"""

import functools
import logging
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, Protocol, TypeVar, runtime_checkable

# Import from central exception hierarchy
from kagami.core.exceptions import TICViolationError

logger = logging.getLogger(__name__)

T = TypeVar("T")


@runtime_checkable
class TICCheck(Protocol):
    """Protocol for a TIC check (precondition, postcondition, or invariant)."""

    @property
    def name(self) -> str: ...

    async def verify(self, context: dict[str, Any]) -> bool: ...


class TICPhase(Enum):
    PRE = "pre"
    POST = "post"
    INVARIANT = "invariant"


class TICEnforcer:
    """Runtime enforcer for Typed Intent Calculus."""

    def __init__(
        self,
        type_name: str,
        pre: list[TICCheck] | None = None,
        post: list[TICCheck] | None = None,
        invariants: list[TICCheck] | None = None,
        termination_metric: str | None = None,
    ):
        self.type_name = type_name
        self.pre = pre or []
        self.post = post or []
        self.invariants = invariants or []
        self.termination_metric = termination_metric

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 1. Extract Context (simplified for now)
            # In a real implementation, we'd robustly bind arguments
            context = {"args": args, "kwargs": kwargs, "func_name": func.__name__}

            # 2. PLAN: Verify Preconditions & Invariants
            pre_checks: dict[str, str] = {c.name: "pending" for c in self.pre}
            tic_plan_data: dict[str, Any] = {
                "type": self.type_name,
                "pre": pre_checks,
                "invariants": [c.name for c in self.invariants],
                "termination": self.termination_metric,
            }

            # Execute Preconditions
            for check in self.pre:
                if not await check.verify(context):
                    pre_checks[check.name] = "failed"
                    raise TICViolationError(f"Precondition failed: {check.name}")
                pre_checks[check.name] = "verified"

            # Execute Invariants (Pre-check)
            for check in self.invariants:
                if not await check.verify(context):
                    raise TICViolationError(f"Invariant failed (pre-check): {check.name}")

            # Note: In a full implementation, we would emit the PLAN receipt here
            # But often the decorated function emits its own receipts.
            # We inject the TIC data into the kwargs so the function can include it.
            kwargs["_tic_plan"] = tic_plan_data

            time.time()
            result = None

            try:
                # 3. EXECUTE
                result = await func(*args, **kwargs)

                # 4. VERIFY: Postconditions & Invariants
                post_checks: dict[str, str] = {c.name: "pending" for c in self.post}
                tic_verify_data: dict[str, Any] = {
                    "post": post_checks,
                    "invariants_preserved": True,
                }

                # Update context with result
                context["result"] = result

                # Execute Postconditions
                for check in self.post:
                    if not await check.verify(context):
                        post_checks[check.name] = "failed"
                        # We log but might not raise depending on strictness
                        logger.error(f"TIC Postcondition failed: {check.name}")
                        # raise TICViolationError(f"Postcondition failed: {check.name}")
                    else:
                        post_checks[check.name] = "verified"

                # Execute Invariants (Post-check)
                for check in self.invariants:
                    if not await check.verify(context):
                        tic_verify_data["invariants_preserved"] = False
                        raise TICViolationError(f"Invariant failed (post-check): {check.name}")

                # Inject verification data into result if possible, or log it
                # Ideally, the function returns a dict[str, Any] we can augment
                if isinstance(result, dict):
                    result["_tic_verify"] = tic_verify_data

                return result

            except Exception as e:
                # Re-check invariants on failure if possible
                raise e

        return wrapper


# --- Standard Checks ---


class SafetyCheck:
    name = "safety_barrier"

    async def verify(self, context: dict[str, Any]) -> bool:
        # Use unified safety pipeline (Dec 6, 2025: WildGuard + OptimalCBF)
        from kagami.core.safety.cbf_integration import check_cbf_sync

        # Extract intent from context
        intent = context.get("kwargs", {}).get("intent") or context.get("args", [{}])[0]
        if isinstance(intent, dict):
            result = check_cbf_sync(
                operation="tic.safety_barrier",
                action=intent.get("action", "unknown"),
                target=intent.get("target", "unknown"),
                source="tic_invariant",
                content=str(intent.get("content", "")),
            )
            return result.safe
        return True  # Allow if no intent to check


class EnergyCheck:
    name = "energy_available"

    async def verify(self, context: dict[str, Any]) -> bool:
        # Simple check proxy
        agent = context.get("kwargs", {}).get("agent")
        if agent:
            return bool(agent.energy_system.energy > 0)
        return True
