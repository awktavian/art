"""Visitor Detection — Identify and Track Visitors via WiFi Presence.

Provides intelligent visitor detection by monitoring WiFi device connections:
1. Device Categorization — Owner, Known (family/friends), Guest, Unknown
2. Visitor History — Track when visitors arrive/leave
3. Automatic Guest Mode — Trigger guest mode when visitors detected
4. Notifications — Alert when new devices connect
5. Device Registration — Allow registering known devices

Architecture:
- Monitors UniFi Network for device connections
- Categorizes devices based on MAC address registry
- Tracks visitor sessions (arrival, departure, duration)
- Integrates with Guest Mode for automated responses
- Provides notification hooks for alerts

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# DEVICE CATEGORIES
# =============================================================================


class DeviceCategory(str, Enum):
    """Device ownership category."""

    OWNER = "owner"  # Tim's devices (phone, laptop, watch)
    FAMILY = "family"  # Family member devices
    FRIEND = "friend"  # Known friend devices
    SERVICE = "service"  # Service personnel (cleaner, handyman)
    AIRBNB = "airbnb"  # Short-term rental guests
    INFRASTRUCTURE = "infrastructure"  # Smart home devices (TVs, speakers, etc.)
    UNKNOWN = "unknown"  # Unrecognized device


@dataclass
class RegisteredDevice:
    """A registered/known device."""

    mac: str  # MAC address (lowercase, colon-separated)
    name: str  # Friendly name
    category: DeviceCategory
    owner_name: str | None = None  # Who owns this device
    device_type: str = "unknown"  # phone, laptop, tablet, etc.
    notes: str = ""
    registered_at: float = field(default_factory=time.time)
    last_seen: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "mac": self.mac,
            "name": self.name,
            "category": self.category.value,
            "owner_name": self.owner_name,
            "device_type": self.device_type,
            "notes": self.notes,
            "registered_at": self.registered_at,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegisteredDevice:
        """Create from dictionary."""
        return cls(
            mac=data["mac"],
            name=data["name"],
            category=DeviceCategory(data["category"]),
            owner_name=data.get("owner_name"),
            device_type=data.get("device_type", "unknown"),
            notes=data.get("notes", ""),
            registered_at=data.get("registered_at", time.time()),
            last_seen=data.get("last_seen", 0.0),
        )


# =============================================================================
# VISITOR TRACKING
# =============================================================================


@dataclass
class VisitorSession:
    """A visitor session (arrival to departure)."""

    mac: str
    device_name: str
    arrival_time: float
    departure_time: float | None = None
    category: DeviceCategory = DeviceCategory.UNKNOWN

    # Room tracking (from localization)
    rooms_visited: list[str] = field(default_factory=list)
    current_room: str | None = None

    @property
    def is_active(self) -> bool:
        """Check if visitor is still present."""
        return self.departure_time is None

    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds."""
        end = self.departure_time or time.time()
        return end - self.arrival_time

    @property
    def duration_minutes(self) -> int:
        """Get session duration in minutes."""
        return int(self.duration_seconds / 60)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mac": self.mac,
            "device_name": self.device_name,
            "arrival_time": self.arrival_time,
            "departure_time": self.departure_time,
            "category": self.category.value,
            "rooms_visited": self.rooms_visited,
            "duration_minutes": self.duration_minutes,
        }


@dataclass
class VisitorAlert:
    """A visitor-related alert."""

    alert_type: str  # "new_device", "visitor_arrived", "visitor_departed", "unknown_device"
    mac: str
    device_name: str
    category: DeviceCategory
    timestamp: float = field(default_factory=time.time)
    message: str = ""
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.alert_type,
            "mac": self.mac,
            "device_name": self.device_name,
            "category": self.category.value,
            "timestamp": self.timestamp,
            "message": self.message,
            "acknowledged": self.acknowledged,
        }


# =============================================================================
# DEVICE REGISTRY
# =============================================================================


class KnownDeviceRegistry:
    """Registry of known devices for visitor detection.

    NOTE: Renamed from DeviceRegistry (Dec 30, 2025) to avoid collision
    with discovery.DeviceRegistry (network device discovery cache).

    Stores device categories and ownership information.
    Persists to disk for continuity across restarts.

    Uses centralized persistence path from persistence.py.
    """

    def __init__(self, persist_path: Path | None = None):
        # Use centralized path from persistence module
        if persist_path is None:
            from kagami_smarthome.persistence import DEVICE_REGISTRY_FILE

            self.persist_path = DEVICE_REGISTRY_FILE
        else:
            self.persist_path = persist_path

        self._devices: dict[str, RegisteredDevice] = {}

        # Load persisted registry
        self._load()

    def _normalize_mac(self, mac: str) -> str:
        """Normalize MAC address format."""
        # Remove common separators and convert to lowercase colon format
        clean = mac.lower().replace("-", "").replace(":", "").replace(".", "")
        return ":".join(clean[i : i + 2] for i in range(0, 12, 2))

    def register(
        self,
        mac: str,
        name: str,
        category: DeviceCategory,
        owner_name: str | None = None,
        device_type: str = "unknown",
        notes: str = "",
    ) -> RegisteredDevice:
        """Register a device.

        Args:
            mac: Device MAC address
            name: Friendly name
            category: Device category
            owner_name: Who owns this device
            device_type: Type of device
            notes: Additional notes

        Returns:
            RegisteredDevice instance
        """
        mac_normalized = self._normalize_mac(mac)

        device = RegisteredDevice(
            mac=mac_normalized,
            name=name,
            category=category,
            owner_name=owner_name,
            device_type=device_type,
            notes=notes,
        )

        self._devices[mac_normalized] = device
        self._save()

        logger.info(f"📱 Registered device: {name} ({mac_normalized}) as {category.value}")
        return device

    def unregister(self, mac: str) -> bool:
        """Unregister a device.

        Args:
            mac: Device MAC address

        Returns:
            True if device was found and removed
        """
        mac_normalized = self._normalize_mac(mac)

        if mac_normalized in self._devices:
            del self._devices[mac_normalized]
            self._save()
            logger.info(f"📱 Unregistered device: {mac_normalized}")
            return True
        return False

    def get(self, mac: str) -> RegisteredDevice | None:
        """Get a registered device.

        Args:
            mac: Device MAC address

        Returns:
            RegisteredDevice or None if not found
        """
        mac_normalized = self._normalize_mac(mac)
        return self._devices.get(mac_normalized)

    def get_category(self, mac: str) -> DeviceCategory:
        """Get device category.

        Args:
            mac: Device MAC address

        Returns:
            DeviceCategory (UNKNOWN if not registered)
        """
        device = self.get(mac)
        return device.category if device else DeviceCategory.UNKNOWN

    def is_known(self, mac: str) -> bool:
        """Check if device is known (registered)."""
        return self.get(mac) is not None

    def is_owner_device(self, mac: str) -> bool:
        """Check if device belongs to owner."""
        device = self.get(mac)
        return device is not None and device.category == DeviceCategory.OWNER

    def get_all(self) -> list[RegisteredDevice]:
        """Get all registered devices."""
        return list(self._devices.values())

    def get_by_category(self, category: DeviceCategory) -> list[RegisteredDevice]:
        """Get devices by category."""
        return [d for d in self._devices.values() if d.category == category]

    def update_last_seen(self, mac: str, timestamp: float | None = None) -> None:
        """Update last seen time for a device."""
        mac_normalized = self._normalize_mac(mac)
        if mac_normalized in self._devices:
            self._devices[mac_normalized].last_seen = timestamp or time.time()

    def _save(self) -> None:
        """Save registry to disk."""
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "version": 1,
                "devices": [d.to_dict() for d in self._devices.values()],
            }

            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save device registry: {e}")

    def _load(self) -> None:
        """Load registry from disk."""
        if not self.persist_path.exists():
            return

        try:
            with open(self.persist_path) as f:
                data = json.load(f)

            version = data.get("version", 1)
            if version != 1:
                logger.warning(f"Unknown registry version: {version}")
                return

            for device_data in data.get("devices", []):
                device = RegisteredDevice.from_dict(device_data)
                self._devices[device.mac] = device

            logger.info(f"📱 Loaded {len(self._devices)} registered devices")

        except Exception as e:
            logger.error(f"Failed to load device registry: {e}")


# =============================================================================
# VISITOR DETECTOR
# =============================================================================


class VisitorDetector:
    """Detects and tracks visitors via WiFi presence.

    Features:
    - Monitor for new device connections
    - Categorize devices (owner, known, unknown)
    - Track visitor sessions (arrival, rooms visited, departure)
    - Generate alerts for unknown devices
    - Auto-trigger guest mode when visitors detected

    Usage:
        detector = VisitorDetector(controller)
        await detector.start()

        # Register known devices
        detector.register_device(
            mac="aa:bb:cc:dd:ee:ff",
            name="Mom's iPhone",
            category=DeviceCategory.FAMILY,
            owner_name="Mom",
        )

        # Check for visitors
        visitors = detector.get_active_visitors()

        # Get alerts
        alerts = detector.get_pending_alerts()
    """

    def __init__(self, controller: SmartHomeController):
        self.controller = controller

        # Device registry
        self.registry = KnownDeviceRegistry()

        # Active visitor sessions
        self._active_sessions: dict[str, VisitorSession] = {}  # MAC -> Session

        # Historical sessions (last 100)
        self._session_history: list[VisitorSession] = []

        # Alerts
        self._alerts: list[VisitorAlert] = []

        # Callbacks
        self._visitor_callbacks: list[Callable[[VisitorSession, str], None]] = []
        self._alert_callbacks: list[Callable[[VisitorAlert], None]] = []

        # Settings
        self._auto_guest_mode = True
        self._alert_on_unknown = True
        self._guest_mode_threshold = 1  # Number of visitors to trigger guest mode
        self._departure_timeout = 600.0  # 10 minutes offline = departed

        # State
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_device_snapshot: dict[str, dict[str, Any]] = {}

    async def start(self) -> None:
        """Start visitor detection."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._detection_loop())
        logger.info("👥 Visitor detection started")

    async def stop(self) -> None:
        """Stop visitor detection."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("👥 Visitor detection stopped")

    async def _detection_loop(self) -> None:
        """Main detection loop."""
        while self._running:
            try:
                await self._check_devices()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Visitor detection error: {e}")
                await asyncio.sleep(60)

    async def _check_devices(self) -> None:
        """Check for new/departed devices."""
        if not self.controller._unifi or not self.controller._unifi.is_connected:
            return

        # Get current WiFi clients
        try:
            clients = self.controller._unifi.get_clients()
        except Exception as e:
            logger.debug(f"Failed to get clients: {e}")
            return

        current_macs = set(clients.keys())
        previous_macs = set(self._last_device_snapshot.keys())

        # New devices - process arrivals in parallel
        new_macs = current_macs - previous_macs
        if new_macs:
            await asyncio.gather(
                *[self._handle_device_arrival(mac, clients[mac]) for mac in new_macs],
                return_exceptions=True,
            )

        # Departed devices - process departures in parallel
        departed_macs = previous_macs - current_macs
        if departed_macs:
            await asyncio.gather(
                *[self._handle_device_departure(mac) for mac in departed_macs],
                return_exceptions=True,
            )

        # Update snapshot
        self._last_device_snapshot = clients

        # Update last seen for all current devices
        for mac in current_macs:
            self.registry.update_last_seen(mac)

        # Check for stale sessions (devices offline too long)
        await self._check_stale_sessions()

    async def _handle_device_arrival(self, mac: str, client_info: dict[str, Any]) -> None:
        """Handle new device connection."""
        device_name = client_info.get("hostname", client_info.get("name", f"Device-{mac[-8:]}"))
        category = self.registry.get_category(mac)

        # Update registered device last seen
        self.registry.update_last_seen(mac)

        # Skip owner and infrastructure devices
        if category in (DeviceCategory.OWNER, DeviceCategory.INFRASTRUCTURE):
            logger.debug(f"👤 Owner/infrastructure device connected: {device_name}")
            return

        # Create visitor session
        session = VisitorSession(
            mac=mac,
            device_name=device_name,
            arrival_time=time.time(),
            category=category,
        )

        self._active_sessions[mac] = session

        # Log and alert
        if category == DeviceCategory.UNKNOWN:
            logger.info(f"⚠️ Unknown device connected: {device_name} ({mac})")

            if self._alert_on_unknown:
                alert = VisitorAlert(
                    alert_type="unknown_device",
                    mac=mac,
                    device_name=device_name,
                    category=category,
                    message=f"Unknown device '{device_name}' connected to WiFi",
                )
                self._add_alert(alert)
        else:
            logger.info(f"👋 Visitor arrived: {device_name} ({category.value})")

            alert = VisitorAlert(
                alert_type="visitor_arrived",
                mac=mac,
                device_name=device_name,
                category=category,
                message=f"{category.value.title()} device '{device_name}' arrived",
            )
            self._add_alert(alert)

        # Notify callbacks
        for callback in self._visitor_callbacks:
            try:
                callback(session, "arrived")
            except Exception as e:
                logger.error(f"Visitor callback error: {e}")

        # Auto guest mode
        if self._auto_guest_mode:
            await self._check_auto_guest_mode()

    async def _handle_device_departure(self, mac: str) -> None:
        """Handle device disconnect."""
        # Don't immediately mark as departed - wait for timeout
        pass

    async def _check_stale_sessions(self) -> None:
        """Check for sessions that have timed out."""
        now = time.time()
        departed = []

        for mac, session in self._active_sessions.items():
            if mac not in self._last_device_snapshot:
                # Device is offline - check how long
                device = self.registry.get(mac)
                if device:
                    offline_duration = now - device.last_seen
                else:
                    # Unknown device - use session arrival as reference
                    offline_duration = self._departure_timeout + 1  # Force departure

                if offline_duration >= self._departure_timeout:
                    departed.append(mac)

        # Process departures
        for mac in departed:
            session = self._active_sessions.pop(mac)
            session.departure_time = time.time()

            # Store in history
            self._session_history.append(session)
            self._session_history = self._session_history[-100:]  # Keep last 100

            logger.info(
                f"👋 Visitor departed: {session.device_name} "
                f"(duration: {session.duration_minutes} min)"
            )

            # Alert
            alert = VisitorAlert(
                alert_type="visitor_departed",
                mac=mac,
                device_name=session.device_name,
                category=session.category,
                message=f"Visitor '{session.device_name}' departed after {session.duration_minutes} min",
            )
            self._add_alert(alert)

            # Notify callbacks
            for callback in self._visitor_callbacks:
                try:
                    callback(session, "departed")
                except Exception as e:
                    logger.error(f"Visitor callback error: {e}")

        # Check if guest mode should be cleared
        if departed and self._auto_guest_mode:
            await self._check_auto_guest_mode()

    async def _check_auto_guest_mode(self) -> None:
        """Check if guest mode should be auto-enabled/disabled."""
        visitor_count = len(self._active_sessions)

        try:
            from kagami_smarthome.advanced_automation import GuestMode, get_advanced_automation

            manager = get_advanced_automation(self.controller)

            if visitor_count >= self._guest_mode_threshold:
                # Enable guest mode if not already
                if not manager.is_guest_mode_active():
                    manager.set_guest_mode(GuestMode.GUEST_PRESENT, visitor_count)
                    logger.info(f"👥 Auto-enabled guest mode ({visitor_count} visitors)")
            else:
                # Clear guest mode if it was auto-set
                if manager.is_guest_mode_active():
                    current_mode = manager.get_guest_mode()
                    # Only clear if it was auto-set (GUEST_PRESENT mode)
                    if current_mode.mode == GuestMode.GUEST_PRESENT:
                        manager.clear_guest_mode()
                        logger.info("👥 Auto-cleared guest mode (visitors departed)")

        except Exception as e:
            logger.debug(f"Guest mode auto-toggle failed: {e}")

    def _add_alert(self, alert: VisitorAlert) -> None:
        """Add an alert and notify callbacks."""
        self._alerts.append(alert)
        # Keep last 50 alerts
        self._alerts = self._alerts[-50:]

        # Notify callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    # =========================================================================
    # Device Registration
    # =========================================================================

    def register_device(
        self,
        mac: str,
        name: str,
        category: DeviceCategory,
        owner_name: str | None = None,
        device_type: str = "unknown",
        notes: str = "",
    ) -> RegisteredDevice:
        """Register a known device.

        Args:
            mac: Device MAC address
            name: Friendly name
            category: Device category
            owner_name: Who owns this device
            device_type: Type of device
            notes: Additional notes

        Returns:
            RegisteredDevice instance
        """
        return self.registry.register(
            mac=mac,
            name=name,
            category=category,
            owner_name=owner_name,
            device_type=device_type,
            notes=notes,
        )

    def register_owner_device(
        self, mac: str, name: str, device_type: str = "phone"
    ) -> RegisteredDevice:
        """Register an owner device (shortcut)."""
        return self.register_device(
            mac=mac,
            name=name,
            category=DeviceCategory.OWNER,
            owner_name="Tim",
            device_type=device_type,
        )

    def register_family_device(
        self,
        mac: str,
        name: str,
        owner_name: str,
        device_type: str = "phone",
    ) -> RegisteredDevice:
        """Register a family member's device (shortcut)."""
        return self.register_device(
            mac=mac,
            name=name,
            category=DeviceCategory.FAMILY,
            owner_name=owner_name,
            device_type=device_type,
        )

    def register_friend_device(
        self,
        mac: str,
        name: str,
        owner_name: str,
        device_type: str = "phone",
    ) -> RegisteredDevice:
        """Register a friend's device (shortcut)."""
        return self.register_device(
            mac=mac,
            name=name,
            category=DeviceCategory.FRIEND,
            owner_name=owner_name,
            device_type=device_type,
        )

    def register_infrastructure_device(
        self, mac: str, name: str, device_type: str
    ) -> RegisteredDevice:
        """Register an infrastructure device (TV, speaker, etc.)."""
        return self.register_device(
            mac=mac,
            name=name,
            category=DeviceCategory.INFRASTRUCTURE,
            device_type=device_type,
        )

    def unregister_device(self, mac: str) -> bool:
        """Unregister a device."""
        return self.registry.unregister(mac)

    # =========================================================================
    # Queries
    # =========================================================================

    def get_active_visitors(self) -> list[VisitorSession]:
        """Get all active visitor sessions."""
        return list(self._active_sessions.values())

    def get_visitor_count(self) -> int:
        """Get count of active visitors."""
        return len(self._active_sessions)

    def has_visitors(self) -> bool:
        """Check if there are any active visitors."""
        return len(self._active_sessions) > 0

    def get_unknown_devices(self) -> list[VisitorSession]:
        """Get active sessions for unknown devices."""
        return [s for s in self._active_sessions.values() if s.category == DeviceCategory.UNKNOWN]

    def get_session_history(self, limit: int = 20) -> list[VisitorSession]:
        """Get recent visitor session history."""
        return self._session_history[-limit:]

    def get_pending_alerts(self) -> list[VisitorAlert]:
        """Get unacknowledged alerts."""
        return [a for a in self._alerts if not a.acknowledged]

    def get_all_alerts(self, limit: int = 20) -> list[VisitorAlert]:
        """Get recent alerts."""
        return self._alerts[-limit:]

    def acknowledge_alert(self, index: int) -> bool:
        """Acknowledge an alert by index."""
        if 0 <= index < len(self._alerts):
            self._alerts[index].acknowledged = True
            return True
        return False

    def acknowledge_all_alerts(self) -> int:
        """Acknowledge all pending alerts. Returns count acknowledged."""
        count = 0
        for alert in self._alerts:
            if not alert.acknowledged:
                alert.acknowledged = True
                count += 1
        return count

    def get_registered_devices(self) -> list[RegisteredDevice]:
        """Get all registered devices."""
        return self.registry.get_all()

    def get_registered_by_category(self, category: DeviceCategory) -> list[RegisteredDevice]:
        """Get registered devices by category."""
        return self.registry.get_by_category(category)

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_visitor(self, callback: Callable[[VisitorSession, str], None]) -> None:
        """Register callback for visitor events.

        Callback receives (session, event_type) where event_type is "arrived" or "departed".
        """
        self._visitor_callbacks.append(callback)

    def on_alert(self, callback: Callable[[VisitorAlert], None]) -> None:
        """Register callback for alerts."""
        self._alert_callbacks.append(callback)

    # =========================================================================
    # Settings
    # =========================================================================

    def set_auto_guest_mode(self, enabled: bool) -> None:
        """Enable/disable automatic guest mode."""
        self._auto_guest_mode = enabled

    def set_alert_on_unknown(self, enabled: bool) -> None:
        """Enable/disable alerts for unknown devices."""
        self._alert_on_unknown = enabled

    def set_departure_timeout(self, seconds: float) -> None:
        """Set timeout before considering a device departed."""
        self._departure_timeout = seconds

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get detector status."""
        return {
            "running": self._running,
            "active_visitors": len(self._active_sessions),
            "unknown_devices": len(self.get_unknown_devices()),
            "pending_alerts": len(self.get_pending_alerts()),
            "registered_devices": len(self.registry.get_all()),
            "session_history_count": len(self._session_history),
            "auto_guest_mode": self._auto_guest_mode,
            "alert_on_unknown": self._alert_on_unknown,
            "departure_timeout_seconds": self._departure_timeout,
        }


# =============================================================================
# FACTORY
# =============================================================================

_visitor_detector: VisitorDetector | None = None


def get_visitor_detector(controller: SmartHomeController) -> VisitorDetector:
    """Get or create visitor detector."""
    global _visitor_detector

    if _visitor_detector is None:
        _visitor_detector = VisitorDetector(controller)

    return _visitor_detector


async def start_visitor_detection(controller: SmartHomeController) -> VisitorDetector:
    """Start visitor detection.

    Args:
        controller: SmartHomeController instance

    Returns:
        Running VisitorDetector
    """
    detector = get_visitor_detector(controller)
    await detector.start()
    return detector


__all__ = [
    # Categories
    "DeviceCategory",
    # Data classes
    "RegisteredDevice",
    "VisitorSession",
    "VisitorAlert",
    # Registry
    "KnownDeviceRegistry",  # Renamed from DeviceRegistry
    # Detector
    "VisitorDetector",
    # Factory
    "get_visitor_detector",
    "start_visitor_detection",
]
