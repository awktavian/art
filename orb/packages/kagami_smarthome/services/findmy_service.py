"""FindMy Service — Apple Find My Integration.

Handles Apple Find My (iCloud):
- Device location
- Play sound
- 2FA handling

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.integrations.apple_findmy import AppleFindMyIntegration

logger = logging.getLogger(__name__)


class FindMyService:
    """Service for Apple Find My device tracking.

    Usage:
        findmy_svc = FindMyService(apple_findmy_integration)
        await findmy_svc.find_my_play_sound("iPhone")
        devices = await findmy_svc.find_my_get_devices()
    """

    def __init__(self, apple_findmy: AppleFindMyIntegration | None = None) -> None:
        """Initialize Find My service."""
        self._apple_findmy = apple_findmy

    def set_integration(self, apple_findmy: AppleFindMyIntegration) -> None:
        """Set or update Apple Find My integration."""
        self._apple_findmy = apple_findmy

    @property
    def is_available(self) -> bool:
        """Check if Find My service is available."""
        return self._apple_findmy is not None

    async def find_my_play_sound(self, device_name: str | None = None) -> bool:
        """Play sound on a device.

        Args:
            device_name: Device name (None = default device)

        Returns:
            True if sound was played
        """
        if not self._apple_findmy:
            return False
        return await self._apple_findmy.play_sound(device_name)

    async def find_my_play_sound_all(self) -> dict[str, bool]:
        """Play sound on all devices.

        Returns:
            Dict of device_name -> success
        """
        if not self._apple_findmy:
            return {}
        return await self._apple_findmy.play_sound_all()

    async def find_my_get_devices(self) -> list[dict[str, Any]]:
        """Get all Find My devices.

        Returns:
            List of device info dicts
        """
        if not self._apple_findmy:
            return []
        return await self._apple_findmy.get_devices()

    async def find_my_locate(self, device_name: str | None = None) -> dict[str, Any] | None:
        """Get location of a device.

        Args:
            device_name: Device name (None = default device)

        Returns:
            Location dict or None
        """
        if not self._apple_findmy:
            return None
        return await self._apple_findmy.locate(device_name)

    async def find_my_submit_2fa(self, code: str) -> bool:
        """Submit 2FA code for iCloud authentication.

        Args:
            code: 6-digit 2FA code

        Returns:
            True if authentication succeeded
        """
        if not self._apple_findmy:
            return False
        return await self._apple_findmy.submit_2fa(code)

    def find_my_needs_2fa(self) -> bool:
        """Check if 2FA is required."""
        if not self._apple_findmy:
            return False
        return self._apple_findmy.needs_2fa()


__all__ = ["FindMyService"]
