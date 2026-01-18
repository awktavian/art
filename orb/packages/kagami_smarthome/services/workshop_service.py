"""Workshop Service — Formlabs 3D Printer and Glowforge Laser Cutter.

Handles workshop equipment:
- Formlabs Form 4 3D Printer
- Glowforge Pro Laser Cutter

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class WorkshopService:
    """Service for workshop equipment control.

    Usage:
        workshop_svc = WorkshopService(formlabs, glowforge)
        status = workshop_svc.get_workshop_status()
        if workshop_svc.is_printer_printing():
            print(f"Progress: {workshop_svc.get_print_progress()}%")
    """

    def __init__(
        self,
        formlabs: Any = None,
        glowforge: Any = None,
    ) -> None:
        """Initialize workshop service."""
        self._formlabs = formlabs
        self._glowforge = glowforge

    def set_integrations(
        self,
        formlabs: Any = None,
        glowforge: Any = None,
    ) -> None:
        """Set or update workshop integrations."""
        if formlabs:
            self._formlabs = formlabs
        if glowforge:
            self._glowforge = glowforge

    def get_workshop_status(self) -> dict[str, Any]:
        """Get status of all workshop equipment."""
        status: dict[str, Any] = {"formlabs": None, "glowforge": None}

        if self._formlabs and hasattr(self._formlabs, "get_status"):
            try:
                status["formlabs"] = self._formlabs.get_status()
            except Exception as e:
                status["formlabs"] = {"error": str(e)}

        if self._glowforge and hasattr(self._glowforge, "get_status"):
            try:
                status["glowforge"] = self._glowforge.get_status()
            except Exception as e:
                status["glowforge"] = {"error": str(e)}

        return status

    # =========================================================================
    # Formlabs Form 4 3D Printer
    # =========================================================================

    def is_printer_printing(self) -> bool:
        """Check if the 3D printer is currently printing."""
        if not self._formlabs:
            return False
        return self._formlabs.is_printing() if hasattr(self._formlabs, "is_printing") else False

    def get_print_progress(self) -> float:
        """Get current print progress (0-100)."""
        if not self._formlabs:
            return 0.0
        return self._formlabs.get_progress() if hasattr(self._formlabs, "get_progress") else 0.0

    def get_print_time_remaining(self) -> int:
        """Get estimated time remaining in seconds."""
        if not self._formlabs:
            return 0
        if hasattr(self._formlabs, "get_time_remaining"):
            return self._formlabs.get_time_remaining()
        return 0

    async def pause_print(self) -> bool:
        """Pause the current print job."""
        if not self._formlabs:
            return False
        return await self._formlabs.pause() if hasattr(self._formlabs, "pause") else False

    async def resume_print(self) -> bool:
        """Resume a paused print job."""
        if not self._formlabs:
            return False
        return await self._formlabs.resume() if hasattr(self._formlabs, "resume") else False

    async def cancel_print(self) -> bool:
        """Cancel the current print job."""
        if not self._formlabs:
            return False
        return await self._formlabs.cancel() if hasattr(self._formlabs, "cancel") else False

    # =========================================================================
    # Glowforge Pro Laser Cutter
    # =========================================================================

    def is_glowforge_online(self) -> bool:
        """Check if Glowforge is online."""
        if not self._glowforge:
            return False
        return self._glowforge.is_online() if hasattr(self._glowforge, "is_online") else False


__all__ = ["WorkshopService"]
