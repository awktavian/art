"""Security Service — Locks, Cameras, and Alarm Control.

Handles security through:
- August: Smart locks
- UniFi Protect: Cameras and motion detection
- Envisalink/DSC: Security panel and zones

Created: December 30, 2025
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.integrations.august import AugustIntegration
    from kagami_smarthome.integrations.control4 import Control4Integration
    from kagami_smarthome.integrations.envisalink import EnvisalinkIntegration
    from kagami_smarthome.integrations.unifi import UniFiIntegration

logger = logging.getLogger(__name__)


class SecurityService:
    """Service for security control.

    Coordinates locks, cameras, and alarm system.

    Usage:
        security_svc = SecurityService(august, control4, envisalink, unifi)
        await security_svc.lock_all()
        state = await security_svc.get_security_state()
    """

    def __init__(
        self,
        august: AugustIntegration | None = None,
        control4: Control4Integration | None = None,
        envisalink: EnvisalinkIntegration | None = None,
        unifi: UniFiIntegration | None = None,
    ) -> None:
        """Initialize security service."""
        self._august = august
        self._control4 = control4
        self._envisalink = envisalink
        self._unifi = unifi

    def set_integrations(
        self,
        august: AugustIntegration | None = None,
        control4: Control4Integration | None = None,
        envisalink: EnvisalinkIntegration | None = None,
        unifi: UniFiIntegration | None = None,
    ) -> None:
        """Update integrations."""
        if august:
            self._august = august
        if control4:
            self._control4 = control4
        if envisalink:
            self._envisalink = envisalink
        if unifi:
            self._unifi = unifi

    # =========================================================================
    # Lock Control (August primary, Control4 fallback)
    # =========================================================================

    async def lock_all(self) -> bool:
        """Lock all doors.

        Prefers August direct API for lower latency.

        Returns:
            True if successful
        """
        if self._august and self._august.is_connected:
            return await self._august.lock_all()
        if self._control4:
            return await self._control4.lock_all()
        return False

    async def unlock_door(self, door: str) -> bool:
        """Unlock a specific door.

        Args:
            door: Door name

        Returns:
            True if successful
        """
        if self._august and self._august.is_connected:
            return await self._august.unlock_by_name(door)
        if self._control4:
            return await self._control4.unlock_door(door)
        return False

    async def get_lock_states(self) -> dict[str, bool]:
        """Get all lock states.

        Returns:
            Dict of door_name -> is_locked
        """
        if self._august and self._august.is_connected:
            from kagami_smarthome.integrations.august import LockState

            await self._august.refresh_state()
            return {
                info.name: info.lock_state == LockState.LOCKED
                for info in self._august.get_locks().values()
            }

        if self._control4:
            states = {}
            for lock_id, lock in self._control4.get_locks().items():
                state = await self._control4.get_lock_state(lock_id)
                states[lock.get("name", f"Lock {lock_id}")] = state
            return states

        return {}

    def is_any_door_open(self) -> bool:
        """Check if any door is open (via August door sense)."""
        if self._august and self._august.is_connected:
            return self._august.is_any_door_open()
        return False

    def get_lock_battery_levels(self) -> dict[str, float]:
        """Get battery levels for all locks.

        Returns:
            Dict of lock_name -> battery_percent
        """
        if self._august and self._august.is_connected:
            return {info.name: info.battery_level for info in self._august.get_locks().values()}
        return {}

    # =========================================================================
    # Alarm Control (Envisalink/DSC)
    # =========================================================================

    async def arm_security(self, mode: str = "away") -> bool:
        """Arm the security system.

        Args:
            mode: "away" or "stay"

        Returns:
            True if successful
        """
        if not self._envisalink:
            logger.warning("Envisalink not available for arming")
            return False

        if mode == "away":
            return await self._envisalink.arm_away()
        elif mode == "stay":
            return await self._envisalink.arm_stay()
        else:
            logger.warning(f"Unknown arm mode: {mode}")
            return False

    async def disarm_security(self, code: str | None = None) -> bool:
        """Disarm the security system.

        Args:
            code: Security code (uses default if not provided)

        Returns:
            True if successful
        """
        if not self._envisalink:
            return False
        return await self._envisalink.disarm(code)

    async def get_security_state(self) -> dict[str, Any]:
        """Get comprehensive security state.

        Returns:
            Dict with alarm state, zones, locks, etc.
        """
        from kagami_smarthome.types import SecurityState

        state = SecurityState(
            armed=False,
            arm_mode=None,
            zones_open=[],
            zones_faulted=[],
            alarm_active=False,
            entry_delay=False,
            exit_delay=False,
        )

        if self._envisalink and self._envisalink.is_connected:
            partition = self._envisalink.get_partition_state(1)
            if partition:
                state.armed = partition.armed
                state.arm_mode = partition.mode.value if partition.mode else None
                state.alarm_active = partition.alarm
                state.entry_delay = partition.entry_delay
                state.exit_delay = partition.exit_delay

            # Get zone states
            for zone_id, zone in self._envisalink.get_zones().items():
                if zone.open:
                    state.zones_open.append(zone.name)
                if zone.fault:
                    state.zones_faulted.append(zone.name)

        return {
            "armed": state.armed,
            "arm_mode": state.arm_mode,
            "zones_open": state.zones_open,
            "zones_faulted": state.zones_faulted,
            "alarm_active": state.alarm_active,
            "entry_delay": state.entry_delay,
            "exit_delay": state.exit_delay,
        }

    def get_open_zones(self) -> list[str]:
        """Get list of open security zones."""
        if not self._envisalink:
            return []
        return [zone.name for zone in self._envisalink.get_zones().values() if zone.open]

    def get_recent_motion_zones(self, seconds: float = 300) -> list[str]:
        """Get zones with recent motion.

        Args:
            seconds: Time window to check

        Returns:
            List of zone names with recent motion
        """
        if not self._envisalink:
            return []

        from kagami_smarthome.integrations.envisalink import ZoneType

        cutoff = time.time() - seconds
        return [
            zone.name
            for zone in self._envisalink.get_zones().values()
            if zone.type == ZoneType.MOTION and zone.last_triggered and zone.last_triggered > cutoff
        ]

    def get_dsc_temperature(self) -> tuple[float | None, float | None]:
        """Get DSC panel temperature sensors.

        Returns:
            Tuple of (indoor_temp, outdoor_temp) in Fahrenheit
        """
        if not self._envisalink:
            return (None, None)
        return self._envisalink.get_temperatures()

    def get_dsc_trouble_status(self) -> dict[str, Any]:
        """Get DSC trouble status."""
        if not self._envisalink:
            return {}
        return self._envisalink.get_trouble_status()

    # =========================================================================
    # Camera Control (UniFi Protect)
    # =========================================================================

    async def get_camera_snapshot(self, camera_name: str) -> bytes | None:
        """Get snapshot from camera.

        Args:
            camera_name: Camera name

        Returns:
            JPEG image bytes or None
        """
        if not self._unifi:
            return None
        return await self._unifi.get_camera_snapshot(camera_name)

    def get_recent_motion_events(self, minutes: int = 30) -> list[dict[str, Any]]:
        """Get recent motion events from cameras.

        Args:
            minutes: Time window to check

        Returns:
            List of motion events
        """
        if not self._unifi:
            return []
        return self._unifi.get_motion_events(minutes=minutes)

    def get_camera_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all cameras.

        Returns:
            Dict of camera_name -> status
        """
        if not self._unifi:
            return {}
        return self._unifi.get_camera_status()


__all__ = ["SecurityService"]
