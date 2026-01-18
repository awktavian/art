"""Resident Override CBF — Protect Manual Actions from Automation.

h(x) = time_since_manual_change - cooldown_period

When a resident manually changes a device (light, shade, etc.), automation
should NOT override that change for a cooldown period. This CBF enforces
that constraint.

SAFETY INVARIANT:
    h(x) >= 0 → automation allowed
    h(x) < 0  → automation BLOCKED (manual change too recent)

Created: January 3, 2026
Author: Kagami (鏡)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """Types of controllable devices."""

    LIGHT = "light"
    SHADE = "shade"
    LOCK = "lock"
    THERMOSTAT = "thermostat"
    TV = "tv"
    FIREPLACE = "fireplace"


@dataclass
class ManualChangeRecord:
    """Record of a manual device change."""

    device_id: int
    device_type: DeviceType
    old_value: Any
    new_value: Any
    timestamp: float = field(default_factory=time.time)
    source: str = "manual"  # "manual", "automation", "schedule"


class ResidentOverrideCBF:
    """Control Barrier Function protecting manual device changes.

    Tracks when residents manually change devices and blocks automation
    from overriding those changes for a configurable cooldown period.

    Usage:
        cbf = ResidentOverrideCBF(cooldown_seconds=7200)  # 2 hours

        # Record manual change (from Control4 WebSocket event)
        cbf.record_manual_change(shade_id=235, device_type=DeviceType.SHADE, value=50)

        # Check before automation
        h = cbf.barrier_value(device_id=235, device_type=DeviceType.SHADE)
        if h < 0:
            # BLOCKED - manual change too recent
            logger.info(f"Automation blocked: h(x) = {h:.1f}s until cooldown")
        else:
            # ALLOWED - proceed with automation
            await controller.set_shade_level(235, optimal_level)

    CBF Math:
        h(x) = time_since_manual_change - cooldown_period
        h(x) >= 0 → safe to automate
        h(x) < 0  → blocked (seconds remaining until safe)
    """

    # Default cooldowns per device type (seconds)
    DEFAULT_COOLDOWNS = {
        DeviceType.LIGHT: 3600,  # 1 hour
        DeviceType.SHADE: 7200,  # 2 hours
        DeviceType.LOCK: 14400,  # 4 hours (security-critical)
        DeviceType.THERMOSTAT: 7200,  # 2 hours
        DeviceType.TV: 1800,  # 30 minutes
        DeviceType.FIREPLACE: 3600,  # 1 hour
    }

    def __init__(
        self,
        cooldown_seconds: float | None = None,
        cooldowns_by_type: dict[DeviceType, float] | None = None,
    ):
        """Initialize CBF.

        Args:
            cooldown_seconds: Default cooldown for all devices (overrides defaults)
            cooldowns_by_type: Per-type cooldowns (overrides defaults)
        """
        # Manual change records: {(device_id, device_type): ManualChangeRecord}
        self._manual_changes: dict[tuple[int, DeviceType], ManualChangeRecord] = {}

        # Cooldowns
        self._cooldowns = dict(self.DEFAULT_COOLDOWNS)
        if cooldowns_by_type:
            self._cooldowns.update(cooldowns_by_type)
        if cooldown_seconds is not None:
            # Override all with single value
            for dt in DeviceType:
                self._cooldowns[dt] = cooldown_seconds

        # Statistics
        self._stats = {
            "manual_changes_recorded": 0,
            "automation_blocked": 0,
            "automation_allowed": 0,
        }

    def record_manual_change(
        self,
        device_id: int,
        device_type: DeviceType,
        old_value: Any = None,
        new_value: Any = None,
        source: str = "manual",
    ) -> None:
        """Record a manual device change.

        Call this when a device change is detected that was NOT initiated
        by Kagami automation. Typically from Control4 WebSocket events.

        Args:
            device_id: Control4 device ID
            device_type: Type of device
            old_value: Previous value (optional)
            new_value: New value (optional)
            source: Change source ("manual", "wall_switch", "remote", etc.)
        """
        key = (device_id, device_type)
        record = ManualChangeRecord(
            device_id=device_id,
            device_type=device_type,
            old_value=old_value,
            new_value=new_value,
            source=source,
        )
        self._manual_changes[key] = record
        self._stats["manual_changes_recorded"] += 1

        logger.info(
            f"🏠 Resident override recorded: {device_type.value} {device_id} "
            f"→ {new_value} (cooldown: {self._cooldowns[device_type]}s)"
        )

    def record_automation_change(
        self,
        device_id: int,
        device_type: DeviceType,
    ) -> None:
        """Mark a device as changed by automation (clears manual override).

        Call this AFTER successfully applying an automated change.
        This resets the cooldown so future automation isn't blocked.

        Args:
            device_id: Control4 device ID
            device_type: Type of device
        """
        key = (device_id, device_type)
        if key in self._manual_changes:
            del self._manual_changes[key]

    def barrier_value(
        self,
        device_id: int,
        device_type: DeviceType,
    ) -> float:
        """Compute CBF barrier value h(x).

        h(x) = time_since_manual_change - cooldown_period

        Returns:
            h(x) >= 0: Automation allowed (seconds past cooldown)
            h(x) < 0: Automation blocked (seconds until cooldown expires)
            float('inf'): No manual change recorded (always safe)
        """
        key = (device_id, device_type)
        record = self._manual_changes.get(key)

        if record is None:
            # No manual change recorded - always safe
            return float("inf")

        time_since = time.time() - record.timestamp
        cooldown = self._cooldowns.get(device_type, 3600)

        h = time_since - cooldown

        return h

    def is_automation_allowed(
        self,
        device_id: int,
        device_type: DeviceType,
    ) -> bool:
        """Check if automation is allowed for this device.

        Convenience method wrapping barrier_value().

        Returns:
            True if h(x) >= 0 (automation allowed)
            False if h(x) < 0 (automation blocked)
        """
        h = self.barrier_value(device_id, device_type)
        allowed = h >= 0

        if allowed:
            self._stats["automation_allowed"] += 1
        else:
            self._stats["automation_blocked"] += 1
            logger.debug(
                f"🛑 Automation blocked: {device_type.value} {device_id}, "
                f"h(x) = {h:.1f}s (wait {-h:.0f}s)"
            )

        return allowed

    def get_cooldown_remaining(
        self,
        device_id: int,
        device_type: DeviceType,
    ) -> float | None:
        """Get seconds remaining until automation is allowed.

        Returns:
            Seconds remaining (if blocked)
            0 (if allowed)
            None (if no manual change recorded)
        """
        h = self.barrier_value(device_id, device_type)

        if h == float("inf"):
            return None
        elif h >= 0:
            return 0.0
        else:
            return -h

    def clear_override(
        self,
        device_id: int,
        device_type: DeviceType,
    ) -> bool:
        """Manually clear a resident override (emergency or explicit request).

        Args:
            device_id: Control4 device ID
            device_type: Type of device

        Returns:
            True if override was cleared
        """
        key = (device_id, device_type)
        if key in self._manual_changes:
            del self._manual_changes[key]
            logger.info(f"🔓 Override cleared: {device_type.value} {device_id}")
            return True
        return False

    def clear_all_overrides(self) -> int:
        """Clear all resident overrides (emergency reset).

        Returns:
            Number of overrides cleared
        """
        count = len(self._manual_changes)
        self._manual_changes.clear()
        logger.warning(f"🔓 All overrides cleared: {count} devices")
        return count

    def get_active_overrides(self) -> list[dict[str, Any]]:
        """Get list of currently active overrides.

        Returns:
            List of override records with remaining cooldown time
        """
        now = time.time()
        overrides = []

        for (device_id, device_type), record in self._manual_changes.items():
            cooldown = self._cooldowns.get(device_type, 3600)
            time_since = now - record.timestamp
            remaining = max(0, cooldown - time_since)

            if remaining > 0:  # Only include active overrides
                overrides.append(
                    {
                        "device_id": device_id,
                        "device_type": device_type.value,
                        "new_value": record.new_value,
                        "source": record.source,
                        "timestamp": record.timestamp,
                        "cooldown_remaining": remaining,
                        "h_x": time_since - cooldown,
                    }
                )

        return overrides

    def get_stats(self) -> dict[str, Any]:
        """Get CBF statistics."""
        return {
            **self._stats,
            "active_overrides": len(self.get_active_overrides()),
            "cooldowns": {k.value: v for k, v in self._cooldowns.items()},
        }

    def cleanup_expired(self) -> int:
        """Remove expired override records (housekeeping).

        Returns:
            Number of records removed
        """
        now = time.time()
        expired = []

        for key, record in self._manual_changes.items():
            device_type = key[1]
            cooldown = self._cooldowns.get(device_type, 3600)
            if now - record.timestamp > cooldown:
                expired.append(key)

        for key in expired:
            del self._manual_changes[key]

        return len(expired)


# =============================================================================
# SINGLETON
# =============================================================================

_cbf_instance: ResidentOverrideCBF | None = None


def get_resident_override_cbf() -> ResidentOverrideCBF:
    """Get singleton ResidentOverrideCBF instance."""
    global _cbf_instance
    if _cbf_instance is None:
        _cbf_instance = ResidentOverrideCBF()
    return _cbf_instance


def reset_resident_override_cbf() -> None:
    """Reset singleton (for testing)."""
    global _cbf_instance
    _cbf_instance = None


__all__ = [
    "DeviceType",
    "ManualChangeRecord",
    "ResidentOverrideCBF",
    "get_resident_override_cbf",
    "reset_resident_override_cbf",
]
