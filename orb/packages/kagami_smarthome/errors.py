"""SmartHome Error Types — Actionable error messages.

Provides custom exceptions with:
- Clear problem description
- Actionable troubleshooting steps
- Context for debugging

Created: January 2, 2026
"""

from __future__ import annotations

from typing import Any


class SmartHomeError(Exception):
    """Base exception for SmartHome errors."""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        self.message = message
        self.context = context or {}
        super().__init__(message)


class ConnectionError(SmartHomeError):
    """Integration connection failed."""

    @classmethod
    def control4(cls, host: str, error: str) -> ConnectionError:
        """Control4 connection failure."""
        return cls(
            f"Failed to connect to Control4 Director at {host}. "
            f"Error: {error}\n\n"
            "Troubleshooting steps:\n"
            "1. Verify Director is powered on and connected to network\n"
            "2. Check network connectivity: ping {host}\n"
            "3. Verify credentials in Keychain: security find-generic-password -s kagami -a control4_host\n"
            "4. Check firewall allows port 5020",
            context={"integration": "control4", "host": host, "error": error},
        )

    @classmethod
    def unifi(cls, host: str, error: str) -> ConnectionError:
        """UniFi connection failure."""
        return cls(
            f"Failed to connect to UniFi at {host}. "
            f"Error: {error}\n\n"
            "Troubleshooting steps:\n"
            "1. Verify UniFi Controller is running\n"
            "2. Check network connectivity: ping {host}\n"
            "3. Verify local admin credentials in Keychain\n"
            "4. Check if 2FA is blocking (use local admin account)",
            context={"integration": "unifi", "host": host, "error": error},
        )

    @classmethod
    def denon(cls, host: str, error: str) -> ConnectionError:
        """Denon AVR connection failure."""
        return cls(
            f"Failed to connect to Denon AVR at {host}:23. "
            f"Error: {error}\n\n"
            "Troubleshooting steps:\n"
            "1. Verify AVR is powered on (not standby)\n"
            "2. Check network connectivity: ping {host}\n"
            "3. Test telnet: telnet {host} 23\n"
            "4. Verify only one telnet connection active (limit: 1)",
            context={"integration": "denon", "host": host, "error": error},
        )

    @classmethod
    def tesla(cls, error: str) -> ConnectionError:
        """Tesla connection failure."""
        return cls(
            f"Failed to connect to Tesla API. "
            f"Error: {error}\n\n"
            "Troubleshooting steps:\n"
            "1. Check refresh token in Keychain: security find-generic-password -s kagami -a tesla_refresh_token\n"
            "2. Verify vehicle is online (check Tesla app)\n"
            "3. Re-authenticate: python scripts/tesla_oauth.py\n"
            "4. Check Fleet API status: https://status.teslaapi.io",
            context={"integration": "tesla", "error": error},
        )


class SafetyError(SmartHomeError):
    """Safety constraint violation (h(x) < 0)."""

    @classmethod
    def fireplace(cls, reason: str) -> SafetyError:
        """Fireplace safety violation."""
        return cls(
            f"Fireplace action blocked by safety system. "
            f"Reason: {reason}\n\n"
            "Safety constraints:\n"
            "- Maximum 4 hours continuous operation\n"
            "- Requires presence in room\n"
            "- Not allowed during away mode",
            context={"action": "fireplace", "reason": reason},
        )

    @classmethod
    def lock(cls, door: str, reason: str) -> SafetyError:
        """Lock safety violation."""
        return cls(
            f"Lock action on '{door}' blocked by safety system. Reason: {reason}",
            context={"action": "lock", "door": door, "reason": reason},
        )

    @classmethod
    def tv_mount(cls, reason: str) -> SafetyError:
        """TV mount safety violation."""
        return cls(
            f"TV mount action blocked by safety system. "
            f"Reason: {reason}\n\n"
            "Safety constraints:\n"
            "- Only preset positions allowed (1-4)\n"
            "- Movement blocked during seismic activity",
            context={"action": "tv_mount", "reason": reason},
        )


class ValidationError(SmartHomeError):
    """Input validation failed."""

    @classmethod
    def invalid_room(cls, room: str, valid_rooms: list[str]) -> ValidationError:
        """Unknown room name."""
        return cls(
            f"Unknown room: '{room}'. Valid rooms: {', '.join(sorted(valid_rooms)[:5])}...",
            context={"room": room, "valid_rooms": valid_rooms},
        )

    @classmethod
    def out_of_range(cls, param: str, value: Any, min_val: Any, max_val: Any) -> ValidationError:
        """Value out of allowed range."""
        return cls(
            f"Invalid {param}: {value}. Must be between {min_val} and {max_val}.",
            context={"param": param, "value": value, "min": min_val, "max": max_val},
        )


class RateLimitError(SmartHomeError):
    """Rate limit exceeded."""

    @classmethod
    def exceeded(cls, integration: str, retry_after: float) -> RateLimitError:
        """Rate limit exceeded for integration."""
        return cls(
            f"Rate limit exceeded for {integration}. Retry after {retry_after:.1f} seconds.",
            context={"integration": integration, "retry_after": retry_after},
        )


class TimeoutError(SmartHomeError):
    """Operation timed out."""

    @classmethod
    def integration(cls, integration: str, timeout: float, operation: str) -> TimeoutError:
        """Integration operation timed out."""
        return cls(
            f"{integration} {operation} timed out after {timeout:.1f}s. "
            "The device may be offline or slow to respond.",
            context={"integration": integration, "timeout": timeout, "operation": operation},
        )


class DeviceNotFoundError(SmartHomeError):
    """Device not found."""

    @classmethod
    def device(cls, device_type: str, identifier: str) -> DeviceNotFoundError:
        """Device not found by identifier."""
        return cls(
            f"{device_type} '{identifier}' not found. It may be offline or not yet discovered.",
            context={"device_type": device_type, "identifier": identifier},
        )


__all__ = [
    "ConnectionError",
    "DeviceNotFoundError",
    "RateLimitError",
    "SafetyError",
    "SmartHomeError",
    "TimeoutError",
    "ValidationError",
]
