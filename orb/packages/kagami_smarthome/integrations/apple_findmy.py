"""Apple Find My Integration.

Provides device location, play sound, lost mode, and device management
via iCloud Find My service.

Features:
- Play sound on any Apple device (iPhone, iPad, Mac, AirPods, Watch)
- Get real-time device locations
- Enable Lost Mode with custom message
- Display messages on devices
- Battery status monitoring
- Persistent session (no repeated 2FA)

Requires: Apple ID credentials with 2FA (one-time setup)

Architecture:
- Sessions are cached in ~/.pyicloud/ for persistence
- 2FA only required on first login or after ~60 days
- Integrates with SmartHomeController for unified access

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

# HARDENED: pyicloud is REQUIRED - no optional dependencies
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException

if TYPE_CHECKING:
    from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)

# Cookie directory for session persistence
COOKIE_DIRECTORY = Path.home() / ".pyicloud"
PYICLOUD_AVAILABLE = True


@dataclass
class AppleDeviceInfo:
    """Information about an Apple device."""

    name: str
    device_type: str
    device_class: str
    battery_level: float  # 0.0 to 1.0
    battery_status: str
    location: dict[str, Any] | None
    is_online: bool

    @property
    def battery_percent(self) -> int:
        """Battery level as percentage."""
        return int(self.battery_level * 100)


class AppleFindMyIntegration:
    """Apple Find My integration for device location and control.

    Sessions are persisted to ~/.pyicloud/ for automatic reconnection
    without requiring 2FA on every startup.
    """

    def __init__(
        self,
        apple_id: str | None = None,
        password: str | None = None,
        config: SmartHomeConfig | None = None,
    ):
        """Initialize Find My integration.

        Args:
            apple_id: Apple ID email (or from config/keychain)
            password: Apple ID password (or from config/keychain)
            config: SmartHomeConfig to load credentials from
        """
        # Load from config or keychain if not provided
        if config is not None:
            apple_id = apple_id or getattr(config, "apple_id", None)
            password = password or getattr(config, "apple_password", None)

        # Fall back to keychain
        if not apple_id or not password:
            from kagami_smarthome.secrets import secrets

            apple_id = apple_id or secrets.get("apple_id")
            password = password or secrets.get("apple_password")

        if not apple_id or not password:
            raise ValueError("Apple ID and password required. Set via keychain or config.")

        self._apple_id = apple_id
        self._password = password
        self._api: PyiCloudService | None = None
        self._connected = False
        self._requires_2fa = False
        self._2fa_pending = False

        # Ensure cookie directory exists for session persistence
        COOKIE_DIRECTORY.mkdir(parents=True, exist_ok=True)

    @property
    def is_connected(self) -> bool:
        """Check if connected to iCloud."""
        return self._connected and self._api is not None

    @property
    def requires_2fa(self) -> bool:
        """Check if 2FA is required."""
        return self._requires_2fa

    async def connect(self) -> bool:
        """Connect to iCloud Find My service.

        Uses persistent cookie storage for automatic reconnection.
        2FA is only required on first login or after session expires (~60 days).

        Returns:
            True if connected, False if 2FA needed or failed
        """
        # HARDENED: pyicloud is now always available - no fallback check needed

        try:
            # Run in executor since pyicloud is synchronous
            loop = asyncio.get_event_loop()

            # Use cookie_directory for persistent sessions
            self._api = await loop.run_in_executor(
                None,
                lambda: PyiCloudService(
                    self._apple_id,
                    self._password,
                    cookie_directory=str(COOKIE_DIRECTORY),
                ),
            )

            if self._api.requires_2fa:
                self._requires_2fa = True
                self._2fa_pending = True
                logger.info("Apple Find My: 2FA required (check your Apple device)")
                return False

            self._connected = True
            self._requires_2fa = False

            # Count devices for logging
            try:
                device_count = len(list(self._api.devices))
                logger.info(f"✅ Apple Find My: Connected ({device_count} devices)")
            except Exception:
                logger.info("✅ Apple Find My: Connected")

            return True

        except PyiCloudFailedLoginException as e:
            logger.error(f"Apple Find My: Login failed - {e}")
            return False
        except Exception as e:
            logger.error(f"Apple Find My: Connection error - {e}")
            return False

    async def submit_2fa_code(self, code: str) -> bool:
        """Submit 2FA verification code.

        After successful verification, the session is trusted and persisted
        to ~/.pyicloud/ for automatic reconnection without 2FA.

        Args:
            code: 6-digit verification code (spaces allowed)

        Returns:
            True if verification successful
        """
        if not self._api:
            return False

        # Clean up code (remove spaces)
        code = code.replace(" ", "").replace("-", "")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._api.validate_2fa_code(code))

            if result:
                # Trust the session for persistent login
                if not self._api.is_trusted_session:
                    logger.info("Apple Find My: Trusting session for persistent login...")
                    await loop.run_in_executor(None, self._api.trust_session)

                self._connected = True
                self._requires_2fa = False
                self._2fa_pending = False

                # Log success with device count
                try:
                    device_count = len(list(self._api.devices))
                    logger.info(
                        f"✅ Apple Find My: 2FA verified, session trusted ({device_count} devices)"
                    )
                except Exception:
                    logger.info("✅ Apple Find My: 2FA verified, session trusted")

                return True

            logger.warning("Apple Find My: Invalid 2FA code")
            return False

        except Exception as e:
            logger.error(f"Apple Find My: 2FA error - {e}")
            return False

    async def get_devices(self) -> list[AppleDeviceInfo]:
        """Get all Apple devices.

        Returns:
            List of device information
        """
        if not self.is_connected:
            return []

        devices = []

        try:
            loop = asyncio.get_event_loop()

            for device in self._api.devices:
                status = await loop.run_in_executor(None, device.status)

                # Get location if available
                location = None
                try:
                    loc = await loop.run_in_executor(None, lambda: device.location())
                    if loc:
                        location = {
                            "latitude": loc.get("latitude"),
                            "longitude": loc.get("longitude"),
                            "accuracy": loc.get("horizontalAccuracy"),
                            "timestamp": loc.get("timeStamp"),
                        }
                except Exception as e:
                    logger.debug(f"Apple Find My: Could not get location for device: {e}")

                info = AppleDeviceInfo(
                    name=device["name"],
                    device_type=status.get("deviceDisplayName", "Unknown"),
                    device_class=status.get("deviceClass", ""),
                    battery_level=float(status.get("batteryLevel", 0) or 0),
                    battery_status=status.get("batteryStatus", "Unknown"),
                    location=location,
                    is_online=status.get("deviceStatus") == "200",
                )
                devices.append(info)

        except Exception as e:
            logger.error(f"Apple Find My: Error getting devices - {e}")

        return devices

    async def play_sound(self, device_name: str | None = None) -> bool:
        """Play sound on a device to help locate it.

        Args:
            device_name: Name of device (partial match). If None, plays on first iPhone.

        Returns:
            True if sound command sent successfully
        """
        if not self.is_connected:
            logger.error("Apple Find My: Not connected")
            return False

        try:
            loop = asyncio.get_event_loop()
            target_device = None

            for device in self._api.devices:
                name = device["name"].lower()
                status = await loop.run_in_executor(None, device.status)
                device_type = status.get("deviceDisplayName", "").lower()

                # If specific device requested
                if device_name:
                    if device_name.lower() in name or device_name.lower() in device_type:
                        target_device = device
                        break
                # Default to first iPhone
                elif "iphone" in name or "iphone" in device_type:
                    target_device = device
                    break

            if not target_device:
                # Fall back to first device
                target_device = list(self._api.devices)[0]

            device_name = target_device["name"]
            logger.info(f"🔊 Playing sound on {device_name}")

            await loop.run_in_executor(None, target_device.play_sound)

            logger.info(f"✅ Sound playing on {device_name}")
            return True

        except Exception as e:
            logger.error(f"Apple Find My: Play sound failed - {e}")
            return False

    async def play_sound_all(self) -> dict[str, bool]:
        """Play sound on ALL devices.

        Returns:
            Dict mapping device name to success status
        """
        if not self.is_connected:
            return {}

        results = {}
        loop = asyncio.get_event_loop()

        for device in self._api.devices:
            name = device["name"]
            try:
                await loop.run_in_executor(None, device.play_sound)
                results[name] = True
                logger.info(f"🔊 Sound sent to {name}")
            except Exception as e:
                results[name] = False
                logger.warning(f"Failed to play sound on {name}: {e}")

        return results

    async def get_device_location(self, device_name: str | None = None) -> dict[str, Any] | None:
        """Get location of a specific device.

        Args:
            device_name: Device name (partial match). If None, returns first iPhone location.

        Returns:
            Location dict with latitude, longitude, accuracy, timestamp
        """
        if not self.is_connected:
            return None

        try:
            loop = asyncio.get_event_loop()

            for device in self._api.devices:
                name = device["name"].lower()
                status = await loop.run_in_executor(None, device.status)
                device_type = status.get("deviceDisplayName", "").lower()

                # Match device
                if device_name:
                    if device_name.lower() not in name and device_name.lower() not in device_type:
                        continue
                elif "iphone" not in name and "iphone" not in device_type:
                    continue

                # Get location
                loc = await loop.run_in_executor(None, lambda: device.location())
                if loc:
                    return {
                        "device": device["name"],
                        "latitude": loc.get("latitude"),
                        "longitude": loc.get("longitude"),
                        "accuracy": loc.get("horizontalAccuracy"),
                        "timestamp": loc.get("timeStamp"),
                        "address": loc.get("address"),
                    }

        except Exception as e:
            logger.error(f"Apple Find My: Location error - {e}")

        return None

    async def enable_lost_mode(
        self,
        device_name: str,
        phone_number: str,
        message: str = "This device has been lost. Please call the number shown.",
    ) -> bool:
        """Enable Lost Mode on a device.

        Args:
            device_name: Name of device
            phone_number: Phone number to display
            message: Message to display on device

        Returns:
            True if Lost Mode enabled
        """
        if not self.is_connected:
            return False

        try:
            loop = asyncio.get_event_loop()

            for device in self._api.devices:
                if device_name.lower() in device["name"].lower():
                    await loop.run_in_executor(
                        None, lambda: device.lost_device(phone_number, message)
                    )
                    logger.info(f"🔒 Lost Mode enabled on {device['name']}")
                    return True

        except Exception as e:
            logger.error(f"Apple Find My: Lost Mode error - {e}")

        return False

    async def display_message(
        self,
        device_name: str,
        message: str,
        subject: str = "Message from Kagami",
        sound: bool = True,
    ) -> bool:
        """Display a message on a device.

        Args:
            device_name: Name of device
            message: Message to display
            subject: Subject line
            sound: Whether to play a sound

        Returns:
            True if message sent
        """
        if not self.is_connected:
            return False

        try:
            loop = asyncio.get_event_loop()

            for device in self._api.devices:
                if device_name.lower() in device["name"].lower():
                    await loop.run_in_executor(
                        None, lambda: device.display_message(subject, message, sound)
                    )
                    logger.info(f"📱 Message sent to {device['name']}")
                    return True

        except Exception as e:
            logger.error(f"Apple Find My: Message error - {e}")

        return False

    async def disconnect(self) -> None:
        """Disconnect from iCloud."""
        self._api = None
        self._connected = False
        logger.info("Apple Find My: Disconnected")


# Convenience function for quick access
async def find_my_iphone(
    apple_id: str, password: str, code_2fa: str | None = None
) -> AppleFindMyIntegration:
    """Quick setup for Find My iPhone.

    Args:
        apple_id: Apple ID email
        password: Apple ID password
        code_2fa: Optional 2FA code if already known

    Returns:
        Connected AppleFindMyIntegration instance
    """
    integration = AppleFindMyIntegration(apple_id, password)

    connected = await integration.connect()

    if not connected and integration.requires_2fa and code_2fa:
        await integration.submit_2fa_code(code_2fa)

    return integration
