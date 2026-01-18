"""SmartHome Safety Module — CBF Integration for Physical Actions.

Provides safety checks before critical physical actions:
- Fireplace control (gas hazard)
- MantelMount TV control (mechanical hazard)
- Lock control (security hazard)
- HVAC extreme settings (comfort/efficiency hazard)

All physical actions that can cause harm or property damage MUST pass
through check_physical_safety() before execution.

Safety Invariant: h(x) ≥ 0 Always.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PhysicalActionType(str, Enum):
    """Types of physical actions requiring safety checks."""

    FIREPLACE_ON = "fireplace_on"
    FIREPLACE_OFF = "fireplace_off"
    TV_LOWER = "tv_lower"
    TV_RAISE = "tv_raise"
    TV_MOVE = "tv_move"
    LOCK = "lock"
    UNLOCK = "unlock"
    HVAC_EXTREME = "hvac_extreme"
    SHADE_ALL = "shade_all"


@dataclass
class SafetyContext:
    """Context for safety evaluation."""

    action_type: PhysicalActionType
    target: str  # Device or room name
    parameters: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    # Override flags (use with caution)
    force: bool = False  # Skip safety check (emergency only)
    acknowledged_risk: bool = False  # User acknowledged risk


@dataclass
class SafetyResult:
    """Result of a safety check."""

    allowed: bool
    h_x: float  # Safety function value
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        """Check if h(x) >= 0."""
        return self.h_x >= 0


# =============================================================================
# FIREPLACE SAFETY
# =============================================================================

# Fireplace auto-off timeout (4 hours max)
FIREPLACE_MAX_ON_DURATION = 4 * 60 * 60  # 4 hours in seconds

# Track fireplace state for timeout
_fireplace_on_time: float | None = None
_fireplace_auto_off_task: asyncio.Task | None = None


async def _fireplace_auto_off_timer(controller: Any, timeout: float) -> None:
    """Background task to auto-off fireplace after timeout."""
    global _fireplace_on_time

    try:
        await asyncio.sleep(timeout)

        # Check if still on and past timeout
        if _fireplace_on_time is not None:
            elapsed = time.time() - _fireplace_on_time
            if elapsed >= timeout:
                logger.warning(f"🔥 Fireplace auto-off triggered after {elapsed / 3600:.1f} hours")
                await controller.fireplace_off()
                _fireplace_on_time = None

    except asyncio.CancelledError:
        pass  # Normal cancellation when turned off manually


def start_fireplace_timer(controller: Any) -> None:
    """Start fireplace auto-off timer."""
    global _fireplace_on_time, _fireplace_auto_off_task

    _fireplace_on_time = time.time()

    # Cancel existing timer
    if _fireplace_auto_off_task and not _fireplace_auto_off_task.done():
        _fireplace_auto_off_task.cancel()

    # Start new timer
    _fireplace_auto_off_task = asyncio.create_task(
        _fireplace_auto_off_timer(controller, FIREPLACE_MAX_ON_DURATION)
    )
    logger.info(f"🔥 Fireplace timer started (auto-off in {FIREPLACE_MAX_ON_DURATION / 3600:.0f}h)")


def stop_fireplace_timer() -> None:
    """Stop fireplace auto-off timer."""
    global _fireplace_on_time, _fireplace_auto_off_task

    _fireplace_on_time = None

    if _fireplace_auto_off_task and not _fireplace_auto_off_task.done():
        _fireplace_auto_off_task.cancel()
        _fireplace_auto_off_task = None


def get_fireplace_runtime() -> float | None:
    """Get how long the fireplace has been on (seconds)."""
    if _fireplace_on_time is None:
        return None
    return time.time() - _fireplace_on_time


# =============================================================================
# CBF INTEGRATION
# =============================================================================


def _check_cbf_available() -> bool:
    """Check if CBF integration is available."""
    try:
        from kagami.core.safety.cbf_integration import check_cbf_for_operation

        return True
    except ImportError:
        return False


def check_physical_safety(context: SafetyContext) -> SafetyResult:
    """Check if a physical action is safe to execute.

    Uses trained CBF from kagami.core.safety when available,
    falls back to rule-based checks otherwise.

    Args:
        context: Safety evaluation context

    Returns:
        SafetyResult with h(x) value and decision
    """
    # Force flag bypasses safety (DANGEROUS - emergency only)
    if context.force:
        logger.warning(f"⚠️ Safety check BYPASSED (force=True) for {context.action_type}")
        return SafetyResult(
            allowed=True,
            h_x=0.0,  # At boundary
            reason="Forced bypass",
            warnings=["Safety check bypassed - use with caution"],
        )

    # Try CBF integration
    if _check_cbf_available():
        return _check_cbf_safety(context)

    # Fall back to rule-based safety
    return _check_rule_based_safety(context)


def _check_cbf_safety(context: SafetyContext) -> SafetyResult:
    """Check safety using trained CBF."""
    try:
        from kagami.core.safety.cbf_integration import check_cbf_for_operation

        # Build context for CBF
        cbf_context = {
            "operation": context.action_type.value,
            "action": context.action_type.value,
            "target": context.target,
            "metadata": context.parameters,
            "domain": "physical",
        }

        # Run CBF check
        result = check_cbf_for_operation(cbf_context)

        # Extract h(x) from result
        h_x = result.get("h_x", result.get("h_metric", 0.5))
        allowed = result.get("allowed", h_x >= 0)

        return SafetyResult(
            allowed=allowed,
            h_x=float(h_x),
            reason=result.get("reason"),
            warnings=result.get("warnings", []),
        )

    except Exception as e:
        logger.warning(f"CBF check failed: {e}, falling back to rules")
        return _check_rule_based_safety(context)


def _check_rule_based_safety(context: SafetyContext) -> SafetyResult:
    """Rule-based safety check when CBF unavailable.

    Conservative rules that err on the side of caution.
    """
    warnings = []
    h_x = 0.5  # Default to caution zone

    # Fireplace rules
    if context.action_type == PhysicalActionType.FIREPLACE_ON:
        # Check runtime
        runtime = get_fireplace_runtime()
        if runtime is not None and runtime > 0:
            # Already on - refresh is fine
            h_x = 0.8
        else:
            # New ignition
            h_x = 0.6
            warnings.append("Gas fireplace igniting - ensure area is clear")

    elif context.action_type == PhysicalActionType.FIREPLACE_OFF:
        h_x = 1.0  # Turning off is always safe

    # MantelMount rules
    elif context.action_type in [PhysicalActionType.TV_LOWER, PhysicalActionType.TV_RAISE]:
        h_x = 0.7
        warnings.append("TV mount moving - ensure path is clear")

    elif context.action_type == PhysicalActionType.TV_MOVE:
        # Continuous movement is more dangerous
        h_x = 0.4
        warnings.append("Continuous TV movement - use presets when possible")

    # Lock rules
    elif context.action_type == PhysicalActionType.UNLOCK:
        # Unlocking has security implications
        h_x = 0.5
        warnings.append("Security: Unlocking door")

    elif context.action_type == PhysicalActionType.LOCK:
        h_x = 0.9  # Locking is generally safe

    # HVAC rules
    elif context.action_type == PhysicalActionType.HVAC_EXTREME:
        temp = context.parameters.get("temperature", 72)
        if temp < 60 or temp > 85:
            h_x = 0.3
            warnings.append(f"Extreme temperature setting: {temp}°F")
        else:
            h_x = 0.8

    return SafetyResult(
        allowed=h_x >= 0, h_x=h_x, reason="Rule-based safety check", warnings=warnings
    )


async def check_physical_safety_async(context: SafetyContext) -> SafetyResult:
    """Async wrapper for safety check."""
    return check_physical_safety(context)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def check_fireplace_safety(action: str = "on") -> SafetyResult:
    """Check if fireplace action is safe.

    Args:
        action: "on" or "off"

    Returns:
        SafetyResult
    """
    action_type = (
        PhysicalActionType.FIREPLACE_ON if action == "on" else PhysicalActionType.FIREPLACE_OFF
    )

    return check_physical_safety(
        SafetyContext(
            action_type=action_type,
            target="fireplace",
        )
    )


def check_tv_mount_safety(action: str, preset: int | None = None) -> SafetyResult:
    """Check if TV mount action is safe.

    Args:
        action: "lower", "raise", or "move"
        preset: Preset number if using preset

    Returns:
        SafetyResult
    """
    if action == "lower":
        action_type = PhysicalActionType.TV_LOWER
    elif action == "raise":
        action_type = PhysicalActionType.TV_RAISE
    else:
        action_type = PhysicalActionType.TV_MOVE

    return check_physical_safety(
        SafetyContext(
            action_type=action_type,
            target="mantelmount",
            parameters={"preset": preset} if preset else {},
        )
    )


def check_lock_safety(action: str, lock_name: str) -> SafetyResult:
    """Check if lock action is safe.

    Args:
        action: "lock" or "unlock"
        lock_name: Name of the lock

    Returns:
        SafetyResult
    """
    action_type = PhysicalActionType.LOCK if action == "lock" else PhysicalActionType.UNLOCK

    return check_physical_safety(
        SafetyContext(
            action_type=action_type,
            target=lock_name,
        )
    )


__all__ = [
    "FIREPLACE_MAX_ON_DURATION",
    "PhysicalActionType",
    "SafetyContext",
    "SafetyResult",
    "check_fireplace_safety",
    "check_lock_safety",
    "check_physical_safety",
    "check_physical_safety_async",
    "check_tv_mount_safety",
    "get_fireplace_runtime",
    "start_fireplace_timer",
    "stop_fireplace_timer",
]
