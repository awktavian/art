"""Eight Sleep Smart Mattress Integration.

Direct OAuth2 API implementation for Eight Sleep Pod.

Provides:
- Sleep/wake detection for presence inference
- Bed temperature control (both sides)
- Sleep quality data
- Smart alarm integration

API: Eight Sleep OAuth2 API (as of Dec 2025)
Note: Eight Sleep migrated to OAuth2 in 2024, old session-token API deprecated.

Features:
- Exponential backoff on failures
- Automatic token refresh before expiry
- Auto-reconnection on connection loss
- Connection health monitoring

Created: December 29, 2025
Updated: December 30, 2025 - Added resilience
Updated: January 12, 2026 - Migrated to PollingIntegrationBase
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

import aiohttp
from kagami.core.shared_abstractions.retry_policy import (
    BackoffStrategy,
    RetryPolicy,
)

from kagami_smarthome.core.integration_base import (
    HealthStatus,
    PollingIntegrationBase,
)

if TYPE_CHECKING:
    from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)

# Eight Sleep API endpoints
# Note: Use /login endpoint, NOT OAuth /tokens (which requires different credentials)
CLIENT_API = "https://client-api.8slp.net/v1"
AUTH_URL = f"{CLIENT_API}/login"

# CRITICAL: Eight Sleep API requires specific headers (mimics Android app)
# Without these, API calls hang or return 502 errors
DEFAULT_HEADERS = {
    "content-type": "application/json",
    "connection": "keep-alive",
    "user-agent": "okhttp/4.9.3",
    "accept-encoding": "gzip",
    "accept": "application/json",
}

# Timeout for API calls (Eight Sleep servers can be slow)
DEFAULT_TIMEOUT = 30

# Resilience settings
MAX_RETRIES = 2  # Reduced from 3 - fail faster
BOOT_MAX_RETRIES = 1  # Single attempt during boot - don't block
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 30.0  # Reduced from 60 - don't wait forever
BACKOFF_MULTIPLIER = 2.0
TOKEN_REFRESH_BUFFER = 300  # Refresh 5 minutes before expiry
BOOT_TIMEOUT = 5.0  # Max seconds to spend during boot


class BedSide(Enum):
    """Bed side identifier."""

    LEFT = "left"
    RIGHT = "right"


class SleepStage(Enum):
    """Sleep stage from Eight Sleep."""

    AWAKE = "awake"
    LIGHT = "light"
    DEEP = "deep"
    REM = "rem"
    OUT_OF_BED = "out"
    UNKNOWN = "unknown"


@dataclass
class SleepState:
    """Current sleep state for one side of bed."""

    side: BedSide
    in_bed: bool
    sleep_stage: SleepStage
    temperature: int  # -100 to +100 raw scale
    target_temperature: int
    heating_active: bool
    heart_rate: int | None = None
    hrv: int | None = None
    respiratory_rate: int | None = None


class EightSleepError(Exception):
    """Base exception for Eight Sleep errors."""

    pass


class AuthenticationError(EightSleepError):
    """Authentication failed."""

    pass


class ConnectionError(EightSleepError):
    """Connection to API failed."""

    pass


class EightSleepIntegration(PollingIntegrationBase):
    """Eight Sleep Pod integration via OAuth2 API.

    Uses OAuth2 password grant for authentication.
    Requires Eight Sleep account credentials.

    Features:
    - Automatic retry with exponential backoff
    - Proactive token refresh before expiry
    - Auto-reconnection on connection loss
    - Base class health tracking and credential loading
    """

    # Integration identification (required by base class)
    integration_name: ClassVar[str] = "Eight Sleep"
    credential_keys: ClassVar[list[tuple[str, str]]] = [
        ("eight_sleep_email", "eight_sleep_email"),
        ("eight_sleep_password", "eight_sleep_password"),
    ]

    # Polling configuration
    default_poll_interval: ClassVar[float] = 60.0

    def __init__(self, config: SmartHomeConfig) -> None:
        super().__init__(config)
        self._session: aiohttp.ClientSession | None = None
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: float = 0  # Unix timestamp
        self._user_id: str | None = None
        self._device_id: str | None = None

        # Current state
        self._left_state: SleepState | None = None
        self._right_state: SleepState | None = None
        self._last_update: datetime | None = None

        # Device info
        self._needs_priming = False
        self._has_water = True

        # Event callbacks (list-based for multiple subscribers)
        self._sleep_callbacks: list[Callable[[BedSide, str], None]] = []

        # Resilience tracking (some inherited from base, some specific)
        self._last_failure_time: float = 0
        self._rate_limited_until: float = 0  # Unix timestamp when rate limit expires
        self._reconnect_task: asyncio.Task[None] | None = None

        # Load cached token from Keychain to avoid rate limiting
        self._load_cached_token()

    def _load_cached_token(self) -> None:
        """Load cached Eight Sleep token from Keychain to avoid rate limiting."""
        try:
            from kagami_smarthome.secrets import secrets

            cached_token = secrets.get("eight_sleep_access_token")
            cached_user_id = secrets.get("eight_sleep_user_id")
            cached_expires = secrets.get("eight_sleep_token_expires")

            if cached_token and cached_user_id and cached_expires:
                try:
                    expires_ts = float(cached_expires)
                    # Only use if not expired
                    if time.time() < expires_ts - TOKEN_REFRESH_BUFFER:
                        self._access_token = cached_token
                        self._user_id = cached_user_id
                        self._token_expires_at = expires_ts
                        logger.debug("Eight Sleep: Loaded cached token from Keychain")
                except (ValueError, TypeError):
                    pass  # Invalid cached data, will re-auth

        except Exception as e:
            logger.debug(f"Eight Sleep: Could not load cached token: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected and authenticated."""
        return self._initialized and self._access_token is not None

    @property
    def needs_token_refresh(self) -> bool:
        """Check if token needs refreshing."""
        if not self._token_expires_at:
            return False
        return time.time() > (self._token_expires_at - TOKEN_REFRESH_BUFFER)

    @property
    def is_rate_limited(self) -> bool:
        """Check if we're currently rate limited."""
        return time.time() < self._rate_limited_until

    @property
    def rate_limit_remaining(self) -> float:
        """Seconds remaining until rate limit expires."""
        return max(0, self._rate_limited_until - time.time())

    async def _wait_for_rate_limit(self) -> None:
        """Wait if currently rate limited."""
        if self.is_rate_limited:
            wait_time = self.rate_limit_remaining
            logger.info(f"Eight Sleep: Waiting {wait_time:.0f}s for rate limit to clear")
            await asyncio.sleep(wait_time)

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have a valid session."""
        if not self._session or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            self._session = aiohttp.ClientSession(
                headers=DEFAULT_HEADERS,
                timeout=timeout,
            )
        return self._session

    def _save_token_to_keychain(self) -> None:
        """Save authentication token to Keychain for reuse."""
        if not self._access_token or not self._user_id:
            return

        try:
            from kagami_smarthome.secrets import secrets

            secrets.set("eight_sleep_access_token", self._access_token)
            secrets.set("eight_sleep_user_id", self._user_id)
            secrets.set("eight_sleep_token_expires", str(self._token_expires_at))
            logger.debug("Eight Sleep: Saved token to Keychain")
        except Exception as e:
            logger.debug(f"Eight Sleep: Could not save token: {e}")

    async def _close_session(self) -> None:
        """Close the session if open."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    def _create_retry_policy(self, max_retries: int = MAX_RETRIES) -> RetryPolicy:
        """Create a RetryPolicy for Eight Sleep API calls.

        Args:
            max_retries: Maximum retry attempts

        Returns:
            Configured RetryPolicy for API operations
        """
        return RetryPolicy(
            max_attempts=max_retries + 1,  # max_retries + initial attempt = max_attempts
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay=INITIAL_BACKOFF,
            max_delay=MAX_BACKOFF,
            backoff_multiplier=BACKOFF_MULTIPLIER,
            retryable_exceptions=(
                TimeoutError,
                aiohttp.ClientError,
                aiohttp.ServerDisconnectedError,
            ),
            name="Eight Sleep API",
        )

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        json: dict | None = None,
        headers: dict | None = None,
        max_retries: int = MAX_RETRIES,
        fail_fast: bool = False,
    ) -> tuple[int, dict | str]:
        """Make HTTP request using unified RetryPolicy.

        Handles:
        - 429 Rate Limiting: Waits for Retry-After header or uses exponential backoff
        - 5xx Server Errors: Retries with exponential backoff
        - Timeouts and connection errors: Retries with exponential backoff

        Args:
            fail_fast: If True, don't wait on rate limits - return immediately.
                      Used during boot to avoid blocking startup.

        Returns:
            Tuple of (status_code, response_data)
        """
        session = await self._ensure_session()

        # Track rate limit state for the inner function
        rate_limit_hit = False
        rate_limit_response: tuple[int, dict | str] | None = None

        async def do_request() -> tuple[int, dict | str]:
            nonlocal rate_limit_hit, rate_limit_response

            async with session.request(method, url, json=json, headers=headers) as resp:
                if resp.status in (200, 201):
                    self._record_success()
                    self._rate_limited_until = 0
                    try:
                        data = await resp.json()
                    except Exception:
                        data = await resp.text()
                    return resp.status, data

                elif resp.status == 429:
                    # Rate limited - record when it expires
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                        except ValueError:
                            wait_time = 60
                    else:
                        wait_time = 60  # Default wait

                    self._rate_limited_until = time.time() + wait_time

                    # FAIL FAST: Don't block on rate limits during boot
                    if fail_fast:
                        logger.info(
                            f"Eight Sleep: Rate limited for {wait_time}s (will retry in background)"
                        )
                        try:
                            data = await resp.json()
                        except Exception:
                            data = await resp.text()
                        # Store and return without retrying
                        rate_limit_hit = True
                        rate_limit_response = (resp.status, data)
                        return resp.status, data

                    # Normal mode: raise to trigger retry with wait
                    logger.debug(f"Eight Sleep: Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    raise aiohttp.ClientError(f"Rate limited, retry after {wait_time}s")

                elif resp.status == 401:
                    # Auth error - don't retry, caller should handle
                    try:
                        data = await resp.json()
                    except Exception:
                        data = await resp.text()
                    return resp.status, data

                elif resp.status >= 500:
                    # Server error - raise to trigger retry
                    raise aiohttp.ClientError(f"Server error {resp.status}")

                else:
                    # Other client error - don't retry
                    try:
                        data = await resp.json()
                    except Exception:
                        data = await resp.text()
                    return resp.status, data

        policy = self._create_retry_policy(max_retries)
        try:
            result = await policy.execute(do_request)
            # Check if we hit rate limit in fail_fast mode
            if rate_limit_hit and rate_limit_response:
                return rate_limit_response
            return result
        except Exception as e:
            error_msg = f"Failed after {max_retries} attempts: {e}"
            self._record_failure(error_msg)
            self._last_failure_time = time.time()
            raise ConnectionError(error_msg) from e

    async def connect(self, wait_for_rate_limit: bool = False, boot_mode: bool = True) -> bool:
        """Connect to Eight Sleep API.

        Args:
            wait_for_rate_limit: If False (default), fail fast when rate limited.
                               If True, wait for rate limit to clear.
            boot_mode: If True (default), use fail-fast settings for startup.
                      Don't block, schedule background retry if rate limited.
        """
        # Load credentials using base class method
        await self.load_credentials()

        if not self.config.eight_sleep_email or not self.config.eight_sleep_password:
            logger.debug("Eight Sleep: No credentials configured")
            return False

        # Already connected?
        if self._initialized and self._access_token:
            return True

        # Fail fast if rate limited (don't block boot)
        if self.is_rate_limited:
            if wait_for_rate_limit:
                await self._wait_for_rate_limit()
            else:
                remaining = self.rate_limit_remaining
                logger.info(
                    f"Eight Sleep: Rate limited ({remaining:.0f}s remaining), will retry later"
                )
                if boot_mode:
                    self._schedule_background_connect()
                return False

        try:
            # Authenticate - fail fast in boot mode
            if not await self._authenticate(fail_fast=boot_mode):
                if boot_mode and self.is_rate_limited:
                    self._schedule_background_connect()
                return False

            # Get device info
            if not await self._get_device():
                return False

            # Initial state update (non-critical)
            try:
                await self._update_state()
            except Exception:
                pass  # State update can fail, we're still connected

            self._initialized = True
            self._connected = True  # Base class flag
            self._record_success()  # Reset failure tracking
            device_id_str = self._device_id[:8] if self._device_id else "unknown"
            logger.info(f"Eight Sleep: Connected (device {device_id_str}...)")
            return True

        except EightSleepError as e:
            logger.debug(f"Eight Sleep: Connection failed - {e}")
            if boot_mode:
                self._schedule_background_connect()
            return False
        except Exception as e:
            logger.debug(f"Eight Sleep: Unexpected error - {e}")
            if boot_mode:
                self._schedule_background_connect()
            return False

    def _schedule_background_connect(self) -> None:
        """Schedule background connection attempt after rate limit clears."""
        if self._reconnect_task and not self._reconnect_task.done():
            return  # Already scheduled

        async def background_connect():
            # Wait for rate limit to clear (plus buffer)
            wait_time = self.rate_limit_remaining + 5
            if wait_time > 0:
                logger.debug(f"Eight Sleep: Background retry in {wait_time:.0f}s")
                await asyncio.sleep(wait_time)

            # Try to connect (not in boot mode anymore)
            for attempt in range(3):
                if await self.connect(wait_for_rate_limit=False, boot_mode=False):
                    return
                await asyncio.sleep(30 * (attempt + 1))  # 30s, 60s, 90s

            logger.warning("Eight Sleep: Background connection failed after 3 attempts")

        self._reconnect_task = asyncio.create_task(background_connect())

    async def _authenticate(self, fail_fast: bool = False) -> bool:
        """Authenticate with Eight Sleep using /login endpoint.

        Note: Eight Sleep uses a simple email/password login, not OAuth2.
        The response contains a session object with userId, token, and expirationDate.

        Args:
            fail_fast: If True, don't wait on rate limits - return immediately.
        """
        payload = {
            "email": self.config.eight_sleep_email,
            "password": self.config.eight_sleep_password,
        }

        try:
            # Use single retry in fail_fast mode
            max_retries = BOOT_MAX_RETRIES if fail_fast else MAX_RETRIES
            status, data = await self._request_with_retry(
                "POST", AUTH_URL, json=payload, max_retries=max_retries, fail_fast=fail_fast
            )

            if status == 200 and isinstance(data, dict):
                # Response format: {"session": {"userId": "...", "token": "...", "expirationDate": "..."}}
                session = data.get("session", data)
                self._access_token = session.get("token")
                self._user_id = session.get("userId")

                # Parse expiration date (ISO format) or default to 24 hours
                exp_date = session.get("expirationDate")
                if exp_date:
                    from datetime import datetime

                    try:
                        exp_dt = datetime.strptime(exp_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                        self._token_expires_at = exp_dt.timestamp()
                    except ValueError:
                        self._token_expires_at = time.time() + 86400  # 24 hours
                else:
                    self._token_expires_at = time.time() + 86400  # 24 hours

                # Save token to keychain to avoid rate limiting on next boot
                self._save_token_to_keychain()

                logger.debug(f"Eight Sleep: Authenticated as {self._user_id}")
                return True
            else:
                logger.error(f"Eight Sleep: Auth failed {status}: {str(data)[:200]}")
                return False

        except ConnectionError as e:
            logger.error(f"Eight Sleep: Auth connection error - {e}")
            return False

    async def _refresh_access_token(self) -> bool:
        """Refresh the access token by re-authenticating.

        Note: Eight Sleep /login doesn't use refresh tokens.
        We simply re-authenticate when the session expires.
        """
        logger.debug("Eight Sleep: Session expired, re-authenticating")
        return await self._authenticate()

    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid token, refreshing if needed."""
        if not self._access_token:
            return await self._authenticate()

        if self.needs_token_refresh:
            return await self._refresh_access_token()

        return True

    def _headers(self) -> dict[str, str]:
        """Get API headers with auth."""
        return {"authorization": f"Bearer {self._access_token}"}

    async def _get_device(self) -> bool:
        """Get device (Pod) information."""
        if not await self._ensure_authenticated():
            return False

        url = f"{CLIENT_API}/users/me"

        try:
            status, data = await self._request_with_retry("GET", url, headers=self._headers())

            if status == 401:
                # Token expired, refresh and retry
                if await self._refresh_access_token():
                    return await self._get_device()
                return False

            if status == 200 and isinstance(data, dict):
                user = data.get("user", {})
                devices = user.get("devices", [])
                if devices:
                    self._device_id = devices[0]
                    logger.debug(f"Eight Sleep: Device {self._device_id}")
                    return True
                else:
                    logger.warning("Eight Sleep: No devices found")
                    return False

            return False

        except ConnectionError as e:
            logger.error(f"Eight Sleep: Get device error - {e}")
            return False

    async def _update_state(self) -> None:
        """Update current bed state."""
        if not self._device_id:
            return

        if not await self._ensure_authenticated():
            return

        url = f"{CLIENT_API}/devices/{self._device_id}"

        try:
            status, data = await self._request_with_retry("GET", url, headers=self._headers())

            if status == 401:
                if await self._refresh_access_token():
                    return await self._update_state()
                return

            if status == 200 and isinstance(data, dict):
                result = data.get("result", {})

                # Device info
                self._needs_priming = result.get("needsPriming", False)
                self._has_water = result.get("hasWater", True)

                # Parse left side
                left = result.get("leftKelvin", {})
                self._left_state = SleepState(
                    side=BedSide.LEFT,
                    in_bed=left.get("presence", False),
                    sleep_stage=self._parse_stage(left.get("stage")),
                    temperature=left.get("currentLevel", 0),
                    target_temperature=left.get("targetLevel", 0),
                    heating_active=left.get("active", False),
                )

                # Parse right side
                right = result.get("rightKelvin", {})
                self._right_state = SleepState(
                    side=BedSide.RIGHT,
                    in_bed=right.get("presence", False),
                    sleep_stage=self._parse_stage(right.get("stage")),
                    temperature=right.get("currentLevel", 0),
                    target_temperature=right.get("targetLevel", 0),
                    heating_active=right.get("active", False),
                )

                self._last_update = datetime.now()

        except ConnectionError as e:
            logger.debug(f"Eight Sleep: Update error - {e}")
            # Trigger reconnection if too many failures
            if self._consecutive_failures >= 3:
                self._schedule_reconnect()

    def _parse_stage(self, stage: str | None) -> SleepStage:
        """Parse sleep stage string."""
        if not stage:
            return SleepStage.UNKNOWN
        stage = stage.lower()
        if stage == "awake":
            return SleepStage.AWAKE
        elif stage in ("light", "stage1", "stage2"):
            return SleepStage.LIGHT
        elif stage in ("deep", "stage3", "stage4"):
            return SleepStage.DEEP
        elif stage == "rem":
            return SleepStage.REM
        elif stage in ("out", "notPresent"):
            return SleepStage.OUT_OF_BED
        return SleepStage.UNKNOWN

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._reconnect_task and not self._reconnect_task.done():
            return  # Already reconnecting

        async def reconnect():
            backoff = INITIAL_BACKOFF
            while self._initialized:
                logger.info("Eight Sleep: Attempting reconnection...")
                if await self.connect():
                    logger.info("Eight Sleep: Reconnection successful")
                    return
                await asyncio.sleep(backoff)
                backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF)

        self._reconnect_task = asyncio.create_task(reconnect())

    # =========================================================================
    # Temperature Control
    # =========================================================================

    async def set_temperature(self, side: BedSide, level: int) -> bool:
        """Set bed temperature (-100 to +100 raw scale)."""
        if not self._device_id:
            return False

        if not await self._ensure_authenticated():
            return False

        level = max(-100, min(100, level))
        side_key = "leftKelvin" if side == BedSide.LEFT else "rightKelvin"

        url = f"{CLIENT_API}/devices/{self._device_id}"
        payload = {side_key: {"currentLevel": level}}

        try:
            status, _ = await self._request_with_retry(
                "PUT", url, json=payload, headers=self._headers()
            )
            if status == 200:
                logger.info(f"Eight Sleep: Set {side.value} temp to {level}")
                return True
            return False
        except ConnectionError:
            return False

    async def turn_on(self, side: BedSide) -> bool:
        """Turn on heating/cooling for a side."""
        if not self._device_id:
            return False

        if not await self._ensure_authenticated():
            return False

        side_key = "leftKelvin" if side == BedSide.LEFT else "rightKelvin"
        url = f"{CLIENT_API}/devices/{self._device_id}"
        payload = {side_key: {"active": True}}

        try:
            status, _ = await self._request_with_retry(
                "PUT", url, json=payload, headers=self._headers()
            )
            return status == 200
        except ConnectionError:
            return False

    async def turn_off(self, side: BedSide) -> bool:
        """Turn off heating/cooling for a side."""
        if not self._device_id:
            return False

        if not await self._ensure_authenticated():
            return False

        side_key = "leftKelvin" if side == BedSide.LEFT else "rightKelvin"
        url = f"{CLIENT_API}/devices/{self._device_id}"
        payload = {side_key: {"active": False}}

        try:
            status, _ = await self._request_with_retry(
                "PUT", url, json=payload, headers=self._headers()
            )
            return status == 200
        except ConnectionError:
            return False

    # =========================================================================
    # Sleep Detection
    # =========================================================================

    def is_anyone_in_bed(self) -> bool:
        """Check if anyone is in bed."""
        left_in = self._left_state and self._left_state.in_bed
        right_in = self._right_state and self._right_state.in_bed
        return bool(left_in or right_in)

    def is_anyone_asleep(self) -> bool:
        """Check if anyone is asleep (not awake stage)."""

        def is_asleep(state: SleepState | None) -> bool:
            if not state or not state.in_bed:
                return False
            return state.sleep_stage in (SleepStage.LIGHT, SleepStage.DEEP, SleepStage.REM)

        return is_asleep(self._left_state) or is_asleep(self._right_state)

    def get_sleep_states(self) -> dict[str, SleepState | None]:
        """Get current sleep states."""
        return {
            "left": self._left_state,
            "right": self._right_state,
        }

    def get_device_info(self) -> dict[str, Any]:
        """Get device info."""
        return {
            "device_id": self._device_id,
            "needs_priming": self._needs_priming,
            "has_water": self._has_water,
            "consecutive_failures": self._consecutive_failures,
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }

    async def _poll_once(self) -> None:
        """Perform a single poll cycle (required by PollingIntegrationBase).

        Fetches current state and triggers callbacks for changes.
        """
        old_left_in = self._left_state.in_bed if self._left_state else False
        old_right_in = self._right_state.in_bed if self._right_state else False

        await self._update_state()

        # Check for changes (for event callbacks)
        new_left_in = self._left_state.in_bed if self._left_state else False
        new_right_in = self._right_state.in_bed if self._right_state else False

        if self._sleep_callbacks:
            if old_left_in != new_left_in:
                event = "bed_enter" if new_left_in else "bed_exit"
                for callback in self._sleep_callbacks:
                    try:
                        callback(BedSide.LEFT, event)
                    except Exception as e:
                        logger.debug(f"Eight Sleep: Callback error: {e}")
            if old_right_in != new_right_in:
                event = "bed_enter" if new_right_in else "bed_exit"
                for callback in self._sleep_callbacks:
                    try:
                        callback(BedSide.RIGHT, event)
                    except Exception as e:
                        logger.debug(f"Eight Sleep: Callback error: {e}")

    async def start_monitoring(self, interval: int = 60) -> None:
        """Start background monitoring loop.

        This is a convenience wrapper around the base class start_polling().

        Args:
            interval: Polling interval in seconds (default: 60)
        """
        await self.start_polling(interval=float(interval))

    def on_sleep_change(self, callback: Callable[[BedSide, str], None]) -> None:
        """Register callback for sleep state changes.

        Args:
            callback: Function called with (BedSide, event) where event is "bed_enter" or "bed_exit"
        """
        if callback not in self._sleep_callbacks:
            self._sleep_callbacks.append(callback)

    def remove_sleep_callback(self, callback: Callable[[BedSide, str], None]) -> None:
        """Remove a sleep change callback."""
        if callback in self._sleep_callbacks:
            self._sleep_callbacks.remove(callback)

    async def health_check(self) -> HealthStatus:
        """Check connection health and reconnect if needed.

        Returns:
            HealthStatus with current health information
        """
        if not self._initialized:
            return HealthStatus.unknown(f"{self.integration_name} not initialized")

        # Check rate limit status
        if self.is_rate_limited:
            return HealthStatus.degraded(
                f"Rate limited ({self.rate_limit_remaining:.0f}s remaining)",
                device_id=self._device_id,
                rate_limited_until=self._rate_limited_until,
            )

        # Check if we need to refresh token
        if self.needs_token_refresh:
            start = time.time()
            if not await self._refresh_access_token():
                return HealthStatus.unhealthy(
                    "Token refresh failed",
                    reachable=False,
                    device_id=self._device_id,
                )
            latency = (time.time() - start) * 1000

            return HealthStatus.healthy(
                "Token refreshed successfully",
                latency_ms=latency,
                device_id=self._device_id,
            )

        # Try to update state to verify connection
        start = time.time()
        try:
            await self._update_state()
            latency = (time.time() - start) * 1000

            return HealthStatus.healthy(
                f"{self.integration_name} connected",
                latency_ms=latency,
                device_id=self._device_id,
                left_in_bed=self._left_state.in_bed if self._left_state else None,
                right_in_bed=self._right_state.in_bed if self._right_state else None,
                consecutive_failures=self._consecutive_failures,
            )
        except Exception as e:
            return HealthStatus.unhealthy(
                str(e),
                reachable=False,
                device_id=self._device_id,
                consecutive_failures=self._consecutive_failures,
            )

    async def disconnect(self) -> None:
        """Disconnect from Eight Sleep."""
        self._initialized = False
        self._connected = False

        # Stop polling (base class method)
        await self.stop_polling()

        # Cancel reconnect task
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        await self._close_session()
        self._access_token = None
        self._refresh_token = None
        logger.debug("Eight Sleep: Disconnected")
