"""Automation Service — Guest Mode, Vacation Mode, Circadian Lighting.

Handles advanced automation features:
- Guest mode (guest_present, party, airbnb)
- Vacation mode with occupancy simulation
- Circadian lighting settings

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)


class AutomationService:
    """Service for advanced automation features.

    Usage:
        auto_svc = AutomationService(controller)
        await auto_svc.set_guest_mode("party", guest_count=5)
        await auto_svc.enable_vacation_mode("2025-01-15")
    """

    def __init__(self, controller: SmartHomeController | None = None) -> None:
        """Initialize automation service."""
        self._controller = controller

    def set_controller(self, controller: SmartHomeController) -> None:
        """Set or update controller reference."""
        self._controller = controller

    # =========================================================================
    # Guest Mode
    # =========================================================================

    async def set_guest_mode(self, mode: str, guest_count: int = 1) -> dict[str, Any]:
        """Set guest mode.

        Args:
            mode: "none", "guest_present", "party", or "airbnb"
            guest_count: Number of guests

        Returns:
            Guest mode configuration
        """
        if not self._controller:
            return {"error": "Controller not initialized"}

        from kagami_smarthome.advanced_automation import GuestMode, get_advanced_automation

        manager = get_advanced_automation(self._controller)
        config = manager.set_guest_mode(GuestMode(mode), guest_count)

        return {
            "mode": config.mode.value,
            "guest_count": config.guest_count,
            "disable_auto_lights": config.disable_auto_lights,
            "disable_auto_hvac": config.disable_auto_hvac,
        }

    async def clear_guest_mode(self) -> bool:
        """Clear guest mode and return to normal operation."""
        if not self._controller:
            return False

        from kagami_smarthome.advanced_automation import get_advanced_automation

        manager = get_advanced_automation(self._controller)
        manager.clear_guest_mode()
        return True

    # =========================================================================
    # Vacation Mode
    # =========================================================================

    async def enable_vacation_mode(
        self,
        end_date: str | None = None,
        simulate_occupancy: bool = True,
    ) -> dict[str, Any]:
        """Enable vacation mode.

        Args:
            end_date: ISO format date when vacation ends (e.g., "2025-01-05")
            simulate_occupancy: Whether to simulate occupancy for security

        Returns:
            Vacation mode configuration
        """
        if not self._controller:
            return {"error": "Controller not initialized"}

        from kagami_smarthome.advanced_automation import get_advanced_automation

        manager = get_advanced_automation(self._controller)
        end_dt = datetime.fromisoformat(end_date) if end_date else None

        config = await manager.enable_vacation_mode(
            end_date=end_dt,
            simulate_occupancy=simulate_occupancy,
        )

        return {
            "enabled": config.enabled,
            "end_date": config.end_date.isoformat() if config.end_date else None,
            "simulate_occupancy": config.simulate_occupancy,
        }

    async def disable_vacation_mode(self) -> bool:
        """Disable vacation mode."""
        if not self._controller:
            return False

        from kagami_smarthome.advanced_automation import get_advanced_automation

        manager = get_advanced_automation(self._controller)
        await manager.disable_vacation_mode()
        return True

    # =========================================================================
    # Circadian Lighting
    # =========================================================================

    def get_circadian_settings(self) -> dict[str, Any]:
        """Get current circadian lighting settings."""
        from kagami_smarthome.advanced_automation import (
            get_circadian_color_temp,
            get_circadian_max_brightness,
            get_current_circadian_phase,
        )

        return {
            "phase": get_current_circadian_phase().value,
            "color_temp_kelvin": get_circadian_color_temp(),
            "max_brightness": get_circadian_max_brightness(),
        }

    def get_advanced_automation_status(self) -> dict[str, Any]:
        """Get status of all advanced automation features."""
        if not self._controller:
            return {"error": "Controller not initialized"}

        try:
            from kagami_smarthome.advanced_automation import get_advanced_automation

            manager = get_advanced_automation(self._controller)
            return manager.get_status()
        except Exception:
            return {"error": "Advanced automation not initialized"}


__all__ = ["AutomationService"]
