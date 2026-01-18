"""Visitor Service — WiFi Presence Monitoring and Guest Detection.

Handles visitor detection features:
- Monitor new device connections
- Categorize devices (owner, family, friend, unknown)
- Track visitor sessions
- Generate alerts for unknown devices
- Device registration

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)


class VisitorService:
    """Service for visitor detection and tracking.

    Usage:
        visitor_svc = VisitorService(controller)
        await visitor_svc.start_visitor_detection()
        if visitor_svc.has_visitors():
            visitors = visitor_svc.get_active_visitors()
    """

    def __init__(self, controller: SmartHomeController | None = None) -> None:
        """Initialize visitor service."""
        self._controller = controller

    def set_controller(self, controller: SmartHomeController) -> None:
        """Set or update controller reference."""
        self._controller = controller

    def _get_detector(self) -> Any:
        """Get visitor detector instance."""
        if not self._controller:
            return None
        from kagami_smarthome.visitor_detection import get_visitor_detector

        return get_visitor_detector(self._controller)

    # =========================================================================
    # Detection Control
    # =========================================================================

    async def start_visitor_detection(self) -> Any:
        """Start visitor detection for WiFi presence monitoring.

        Returns:
            VisitorDetector instance
        """
        if not self._controller:
            return None
        from kagami_smarthome.visitor_detection import start_visitor_detection

        return await start_visitor_detection(self._controller)

    def get_visitor_detector(self) -> Any:
        """Get visitor detector (if started)."""
        return self._get_detector()

    # =========================================================================
    # Device Registration
    # =========================================================================

    def register_device(
        self,
        mac: str,
        name: str,
        category: str,
        owner_name: str | None = None,
        device_type: str = "unknown",
    ) -> dict[str, Any]:
        """Register a known device for visitor detection.

        Args:
            mac: Device MAC address
            name: Friendly name
            category: "owner", "family", "friend", "service", "infrastructure"
            owner_name: Who owns this device
            device_type: Type of device (phone, laptop, tablet, etc.)

        Returns:
            Registration result
        """
        detector = self._get_detector()
        if not detector:
            return {"error": "Visitor detection not started"}

        from kagami_smarthome.visitor_detection import DeviceCategory

        device = detector.register_device(
            mac=mac,
            name=name,
            category=DeviceCategory(category),
            owner_name=owner_name,
            device_type=device_type,
        )
        return device.to_dict()

    def get_registered_devices(self) -> list[dict[str, Any]]:
        """Get all registered devices."""
        detector = self._get_detector()
        if not detector:
            return []
        return [d.to_dict() for d in detector.get_registered_devices()]

    # =========================================================================
    # Visitor Tracking
    # =========================================================================

    def get_active_visitors(self) -> list[dict[str, Any]]:
        """Get currently active visitor sessions."""
        detector = self._get_detector()
        if not detector:
            return []
        return [s.to_dict() for s in detector.get_active_visitors()]

    def get_visitor_count(self) -> int:
        """Get count of active visitors."""
        detector = self._get_detector()
        if not detector:
            return 0
        return detector.get_visitor_count()

    def has_visitors(self) -> bool:
        """Check if there are any active visitors."""
        detector = self._get_detector()
        if not detector:
            return False
        return detector.has_visitors()

    # =========================================================================
    # Alerts
    # =========================================================================

    def get_visitor_alerts(self, pending_only: bool = True) -> list[dict[str, Any]]:
        """Get visitor-related alerts.

        Args:
            pending_only: If True, only return unacknowledged alerts

        Returns:
            List of alert info
        """
        detector = self._get_detector()
        if not detector:
            return []
        if pending_only:
            return [a.to_dict() for a in detector.get_pending_alerts()]
        return [a.to_dict() for a in detector.get_all_alerts()]

    def acknowledge_visitor_alerts(self) -> int:
        """Acknowledge all pending visitor alerts.

        Returns:
            Count of alerts acknowledged
        """
        detector = self._get_detector()
        if not detector:
            return 0
        return detector.acknowledge_all_alerts()

    # =========================================================================
    # Status
    # =========================================================================

    def get_visitor_detection_status(self) -> dict[str, Any]:
        """Get visitor detection system status."""
        detector = self._get_detector()
        if not detector:
            return {"running": False, "reason": "Not started"}
        return detector.get_status()


__all__ = ["VisitorService"]
