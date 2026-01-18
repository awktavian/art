"""Oelo Service — Outdoor Lighting Control.

Handles Oelo outdoor lighting:
- On/off control
- Color selection
- Patterns and scenes
- Holiday modes

Created: December 30, 2025
Updated: January 3, 2026 — Wired to actual integration methods
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kagami_smarthome.integrations.oelo import OeloIntegration

logger = logging.getLogger(__name__)


class OeloService:
    """Service for Oelo outdoor lighting control.

    Usage:
        oelo_svc = OeloService(oelo_integration)
        await oelo_svc.outdoor_lights_on()
        await oelo_svc.outdoor_christmas()
    """

    def __init__(self, oelo: OeloIntegration | None = None) -> None:
        """Initialize Oelo service."""
        self._oelo = oelo

    def set_integration(self, oelo: OeloIntegration) -> None:
        """Set or update Oelo integration."""
        self._oelo = oelo

    @property
    def is_available(self) -> bool:
        """Check if Oelo service is available."""
        return self._oelo is not None and self._oelo.is_connected

    async def outdoor_lights_on(self) -> bool:
        """Turn outdoor lights on (warm white)."""
        if not self._oelo:
            return False
        return await self._oelo.on()

    async def outdoor_lights_off(self) -> bool:
        """Turn outdoor lights off."""
        if not self._oelo:
            return False
        return await self._oelo.off()

    async def outdoor_lights_color(self, color: str) -> bool:
        """Set outdoor lights to a specific color.

        Args:
            color: Color name or hex code

        Returns:
            True if color was set
        """
        if not self._oelo:
            return False
        return await self._oelo.set_color(color)

    async def outdoor_lights_pattern(
        self,
        pattern: str,
        zone: int | None = None,
        speed_override: int | None = None,
    ) -> bool:
        """Set outdoor lights to a pattern.

        Args:
            pattern: Pattern name from PATTERNS dict
            zone: Optional specific zone (None = all zones)
            speed_override: Optional speed override

        Returns:
            True if pattern was set
        """
        if not self._oelo:
            return False
        return await self._oelo.set_pattern(pattern, zone, speed_override)

    async def outdoor_christmas(self) -> bool:
        """Set outdoor lights to Christmas pattern."""
        if not self._oelo:
            return False
        return await self._oelo.set_pattern("christmas")

    async def outdoor_halloween(self) -> bool:
        """Set outdoor lights to Halloween pattern."""
        if not self._oelo:
            return False
        return await self._oelo.set_pattern("halloween")

    async def outdoor_july4th(self) -> bool:
        """Set outdoor lights to patriotic July 4th pattern."""
        if not self._oelo:
            return False
        return await self._oelo.set_pattern("july4th")

    async def outdoor_valentines(self) -> bool:
        """Set outdoor lights to Valentine's Day pattern."""
        if not self._oelo:
            return False
        return await self._oelo.set_pattern("valentines")

    async def outdoor_stpatricks(self) -> bool:
        """Set outdoor lights to St. Patrick's Day pattern."""
        if not self._oelo:
            return False
        return await self._oelo.set_pattern("stpatricks")

    async def outdoor_thanksgiving(self) -> bool:
        """Set outdoor lights to Thanksgiving pattern."""
        if not self._oelo:
            return False
        return await self._oelo.set_pattern("thanksgiving")

    async def outdoor_party(self) -> bool:
        """Set outdoor lights to party mode."""
        if not self._oelo:
            return False
        return await self._oelo.party_mode()

    async def outdoor_welcome(self) -> bool:
        """Set outdoor lights to welcome mode (warm white)."""
        if not self._oelo:
            return False
        return await self._oelo.welcome_home()

    async def outdoor_rainbow(self, speed: int = 8) -> bool:
        """Set outdoor lights to rainbow mode."""
        if not self._oelo:
            return False
        return await self._oelo.rainbow(speed)

    async def outdoor_alert(self) -> bool:
        """Set outdoor lights to alert/security mode."""
        if not self._oelo:
            return False
        return await self._oelo.alert_mode()

    def list_patterns(self) -> list[str]:
        """List all available Oelo patterns."""
        if not self._oelo:
            return []
        return self._oelo.list_patterns()


__all__ = ["OeloService"]
