"""August Smart Lock Direct Integration.

Direct API implementation using yalexs library for real-time lock control.
Bypasses Control4 for lower latency and better state accuracy.

Provides:
- Real-time lock/unlock with instant feedback
- Lock state monitoring
- Activity log access
- DoorSense status (door open/closed)
- Battery level monitoring

API: August/Yale Access (via yalexs library)
Note: Requires August account credentials.

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


def _get_blacklisted_house_ids() -> set[str]:
    """Get blacklisted house IDs from secrets.

    Store as comma-separated list in keychain:
        secrets.set("august_blacklisted_houses", "house-id-1,house-id-2")
    """
    from kagami_smarthome.secrets import secrets

    blacklist = secrets.get("august_blacklisted_houses")
    if blacklist:
        return {h.strip() for h in blacklist.split(",") if h.strip()}
    return set()


class LockState(Enum):
    """Lock state."""

    LOCKED = "locked"
    UNLOCKED = "unlocked"
    UNKNOWN = "unknown"


class DoorState(Enum):
    """Door state (DoorSense)."""

    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


@dataclass
class LockInfo:
    """Information about an August lock."""

    lock_id: str
    name: str
    house_name: str
    lock_state: LockState
    door_state: DoorState
    battery_level: float  # 0-100
    is_online: bool
    last_changed: datetime | None = None


class AugustIntegration:
    """August Smart Lock integration via yalexs API.

    Provides direct lock control without Control4 latency.
    Uses yalexs library for August/Yale Access API.

    Features:
    - Automatic credential loading from Keychain
    - Automatic token refresh
    - Real-time lock state
    - DoorSense monitoring
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self._session: Any = None  # aiohttp.ClientSession
        self._api: Any = None  # yalexs.api_async.ApiAsync
        self._authenticator: Any = None
        self._authentication: Any = None
        self._locks: dict[str, LockInfo] = {}
        self._initialized = False

        # Credentials
        self._email: str | None = None
        self._password: str | None = None
        self._install_id: str | None = None
        self._access_token: str | None = None

        # Event callbacks (list-based for multiple subscribers)
        self._lock_callbacks: list[Callable[[str, LockInfo], None]] = []

        # Load credentials from Keychain
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load August credentials from Keychain."""
        try:
            from kagami_smarthome.secrets import secrets

            # Load basic credentials
            self._email = secrets.get("august_email")
            self._password = secrets.get("august_password")
            self._install_id = secrets.get("august_install_id")
            self._access_token = secrets.get("august_access_token")

            # Generate install_id if not present
            if not self._install_id:
                self._install_id = str(uuid.uuid4())
                secrets.set("august_install_id", self._install_id)
                logger.info("August: Generated new install_id")

        except Exception as e:
            logger.debug(f"August: Could not load credentials: {e}")

    def _save_token_to_keychain(self, token: str) -> None:
        """Save access token to Keychain."""
        try:
            from kagami_smarthome.secrets import secrets

            secrets.set("august_access_token", token)
            logger.debug("August: Saved access token to Keychain")
        except Exception as e:
            logger.debug(f"August: Could not save token: {e}")

    @property
    def is_connected(self) -> bool:
        return self._initialized and self._api is not None

    async def connect(self) -> bool:
        """Connect to August API."""
        if not self._email or not self._password:
            logger.debug("August: No credentials configured")
            return False

        try:
            # HARDENED: yalexs is REQUIRED - no optional dependencies
            import aiohttp
            from yalexs.api_async import ApiAsync
            from yalexs.authenticator_async import AuthenticatorAsync

            # Create aiohttp session
            self._session = aiohttp.ClientSession()

            # Create API instance with session (default brand is August)
            self._api = ApiAsync(self._session)

            # Create authenticator - login_method is "email" or "phone"
            self._authenticator = AuthenticatorAsync(
                self._api,
                login_method="email",
                username=self._email,
                password=self._password,
                install_id=self._install_id,
            )

            # Setup authentication state first
            await self._authenticator.async_setup_authentication()

            # Authenticate
            self._authentication = await self._authenticator.async_authenticate()

            if self._authentication.state.value != "authenticated":
                logger.error(f"August: Auth failed - state: {self._authentication.state}")
                # May need 2FA - check if requires validation
                if self._authentication.state.value == "requires_validation":
                    logger.warning(
                        "August: 2FA required. Check your email/phone and run setup again."
                    )
                return False

            # Save token for future use
            if hasattr(self._authentication, "access_token"):
                self._save_token_to_keychain(self._authentication.access_token)

            # Discover locks
            await self._discover_locks()

            self._initialized = True
            logger.info(f"✅ August: Connected ({len(self._locks)} locks)")
            return True

        except Exception as e:
            logger.error(f"August: Connection failed - {e}")
            if self._session:
                await self._session.close()
            return False

    async def _discover_locks(self) -> None:
        """Discover all locks (filtered by house blacklist from secrets)."""
        if not self._api or not self._authentication:
            return

        try:
            locks = await self._api.async_get_locks(self._authentication.access_token)
            blacklisted = _get_blacklisted_house_ids()
            skipped = 0

            for lock in locks:
                house_id = getattr(lock, "house_id", None)

                # Filter: Skip blacklisted houses (configured via secrets)
                if house_id and house_id in blacklisted:
                    logger.debug(f"August: Skipping lock '{lock.device_name}' (blacklisted house)")
                    skipped += 1
                    continue

                # Get detailed info (includes status, battery, etc)
                detail = await self._api.async_get_lock_detail(
                    self._authentication.access_token,
                    lock.device_id,
                )

                self._locks[lock.device_id] = LockInfo(
                    lock_id=lock.device_id,
                    name=detail.device_name if detail else lock.device_name,
                    house_name=getattr(detail, "house_id", "Unknown") if detail else "Unknown",
                    lock_state=self._parse_lock_state(detail.lock_status if detail else None),
                    door_state=self._parse_door_state(detail.door_state if detail else None),
                    battery_level=getattr(detail, "battery_level", 0) or 0 if detail else 0,
                    is_online=getattr(detail, "bridge_is_online", True) if detail else True,
                    last_changed=getattr(detail, "lock_status_datetime", None) if detail else None,
                )

            if skipped:
                logger.info(f"August: Skipped {skipped} locks from blacklisted houses")
            logger.debug(f"August: Discovered {len(self._locks)} locks")

        except Exception as e:
            logger.error(f"August: Discovery failed - {e}")

    def _parse_lock_state(self, state: Any) -> LockState:
        """Parse lock state from API."""
        if not state:
            return LockState.UNKNOWN
        state_str = str(state).lower()
        if "locked" in state_str:
            return LockState.LOCKED
        elif "unlocked" in state_str:
            return LockState.UNLOCKED
        return LockState.UNKNOWN

    def _parse_door_state(self, state: Any) -> DoorState:
        """Parse door state from API."""
        if not state:
            return DoorState.UNKNOWN
        state_str = str(state).lower()
        if "open" in state_str:
            return DoorState.OPEN
        elif "closed" in state_str:
            return DoorState.CLOSED
        return DoorState.UNKNOWN

    # =========================================================================
    # Lock Control
    # =========================================================================

    async def lock(self, lock_id: str | None = None) -> bool:
        """Lock a door. If lock_id is None, locks the first lock."""
        if not self._api or not self._authentication:
            return False

        if not lock_id:
            lock_id = next(iter(self._locks.keys()), None)

        if not lock_id:
            logger.warning("August: No lock found")
            return False

        try:
            await self._api.async_lock(
                self._authentication.access_token,
                lock_id,
            )

            # Update local state
            if lock_id in self._locks:
                self._locks[lock_id].lock_state = LockState.LOCKED
                self._locks[lock_id].last_changed = datetime.now()

            logger.info(
                f"August: Locked {self._locks.get(lock_id, {}).name if lock_id in self._locks else lock_id}"
            )
            return True

        except Exception as e:
            logger.error(f"August: Lock failed - {e}")
            return False

    async def unlock(self, lock_id: str | None = None) -> bool:
        """Unlock a door. If lock_id is None, unlocks the first lock."""
        if not self._api or not self._authentication:
            return False

        if not lock_id:
            lock_id = next(iter(self._locks.keys()), None)

        if not lock_id:
            logger.warning("August: No lock found")
            return False

        try:
            await self._api.async_unlock(
                self._authentication.access_token,
                lock_id,
            )

            # Update local state
            if lock_id in self._locks:
                self._locks[lock_id].lock_state = LockState.UNLOCKED
                self._locks[lock_id].last_changed = datetime.now()

            logger.info(
                f"August: Unlocked {self._locks.get(lock_id).name if lock_id in self._locks else lock_id}"
            )
            return True

        except Exception as e:
            logger.error(f"August: Unlock failed - {e}")
            return False

    async def lock_all(self) -> bool:
        """Lock all doors."""
        results = [await self.lock(lock_id) for lock_id in self._locks]
        return all(results) if results else False

    async def unlock_by_name(self, name: str) -> bool:
        """Unlock a lock by name."""
        name_lower = name.lower()
        for lock_id, info in self._locks.items():
            if name_lower in info.name.lower() or name_lower in info.house_name.lower():
                return await self.unlock(lock_id)
        logger.warning(f"August: Lock not found: {name}")
        return False

    # =========================================================================
    # State
    # =========================================================================

    async def refresh_state(self, lock_id: str | None = None) -> None:
        """Refresh lock state from API."""
        if not self._api or not self._authentication:
            return

        lock_ids = [lock_id] if lock_id else list(self._locks.keys())

        for lid in lock_ids:
            try:
                # Get both lock status and door state (returns tuple when door_status=True)
                lock_status, door_state = await self._api.async_get_lock_status(
                    self._authentication.access_token,
                    lid,
                    door_status=True,
                )

                if lid in self._locks:
                    self._locks[lid].lock_state = self._parse_lock_state(lock_status)
                    self._locks[lid].door_state = self._parse_door_state(door_state)

            except Exception as e:
                logger.debug(f"August: Refresh failed for {lid}: {e}")

    def get_locks(self) -> dict[str, LockInfo]:
        """Get all locks."""
        return self._locks.copy()

    def get_lock_state(self, lock_id: str) -> LockInfo | None:
        """Get state of a specific lock."""
        return self._locks.get(lock_id)

    def is_locked(self, lock_id: str | None = None) -> bool:
        """Check if a lock is locked."""
        if lock_id:
            info = self._locks.get(lock_id)
            return info.lock_state == LockState.LOCKED if info else False
        # Check all locks
        return all(info.lock_state == LockState.LOCKED for info in self._locks.values())

    def is_door_open(self, lock_id: str | None = None) -> bool:
        """Check if a door is open (DoorSense)."""
        if lock_id:
            info = self._locks.get(lock_id)
            return info.door_state == DoorState.OPEN if info else False
        # Check any door open
        return any(info.door_state == DoorState.OPEN for info in self._locks.values())

    def get_battery_levels(self) -> dict[str, float]:
        """Get battery levels for all locks."""
        return {info.name: info.battery_level for info in self._locks.values()}

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def start_monitoring(self, interval: int = 30) -> None:
        """Start background state monitoring."""
        while self._initialized:
            try:
                old_states = {lid: info.lock_state for lid, info in self._locks.items()}

                await self.refresh_state()

                # Check for changes
                if self._lock_callbacks:
                    for lid, info in self._locks.items():
                        old_state = old_states.get(lid)
                        if old_state != info.lock_state:
                            for callback in self._lock_callbacks:
                                try:
                                    callback(lid, info)
                                except Exception as e:
                                    logger.debug(f"August: Callback error: {e}")

            except Exception as e:
                logger.debug(f"August: Monitor error - {e}")

            await asyncio.sleep(interval)

    def on_lock_change(self, callback: Callable[[str, LockInfo], None]) -> None:
        """Register callback for lock state changes.

        Args:
            callback: Function called with (lock_id, LockInfo) when state changes
        """
        if callback not in self._lock_callbacks:
            self._lock_callbacks.append(callback)

    def remove_lock_callback(self, callback: Callable[[str, LockInfo], None]) -> None:
        """Remove a lock change callback."""
        if callback in self._lock_callbacks:
            self._lock_callbacks.remove(callback)

    async def disconnect(self) -> None:
        """Disconnect from August."""
        self._initialized = False
        if self._session:
            try:
                await self._session.close()
            except Exception as e:
                logger.debug(f"August: Session close error (non-fatal): {e}")
        self._session = None
        self._api = None
        logger.debug("August: Disconnected")
