"""Control4 Home Automation Integration.

Direct REST API implementation with automatic token refresh.

Provides:
- Lighting control (Lutron LEAP dimmers/switches) - 41 fixtures
- Shade control (Lutron LEAP roller shades) - 12 shades
- Multi-room audio (Triad 16x16 AMS matrix) - 26 zones
- Security (DSC TL-280 panel via IT-100)
- Lock control (August Smart Locks) - 2 locks
- Fireplace control
- MantelMount TV mount control
- Scene activation
- Device state monitoring

Architecture:
- Director API runs on core5 (192.168.1.2), NOT core1 (192.168.1.11)
- Token obtained via Control4 cloud auth, valid ~24 hours
- This module handles automatic refresh

Created: December 29, 2025
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import aiohttp
from aiohttp import ClientTimeout
from kagami.core.shared_abstractions.retry_policy import (
    BackoffStrategy,
    RetryPolicy,
)

from kagami_smarthome.core.integration_base import (
    HealthStatus,
    IntegrationBase,
)
from kagami_smarthome.types import SecurityState

if TYPE_CHECKING:
    from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


def _log_request_context(
    method: str, url: str, status: int | None = None, error: str | None = None
) -> None:
    """Log HTTP request context for debugging."""
    if status:
        if 200 <= status < 300:
            logger.debug(f"Control4 {method} {url} → {status}")
        else:
            logger.warning(f"Control4 {method} {url} → {status}")
    if error:
        logger.error(f"Control4 {method} {url} → ERROR: {error}")


# Control4 API endpoints
AUTH_ENDPOINT = "https://apis.control4.com/authentication/v1/rest"
CONTROLLER_AUTH_ENDPOINT = "https://apis.control4.com/authentication/v1/rest/authorization"
ACCOUNTS_ENDPOINT = "https://apis.control4.com/account/v3/rest/accounts"
APPLICATION_KEY = "78f6791373d61bea49fdb9fb8897f1f3af193f11"

# Item types from Control4 API
ITEM_TYPE_USER = 1
ITEM_TYPE_HOME = 2
ITEM_TYPE_HOUSE = 3
ITEM_TYPE_FLOOR = 4
ITEM_TYPE_DRIVER = 6
ITEM_TYPE_DEVICE = 7
ITEM_TYPE_ROOM = 8
ITEM_TYPE_AGENT = 9


@dataclass
class Control4Token:
    """Control4 authentication tokens."""

    account_token: str
    director_token: str
    controller_name: str
    expires_at: float  # Unix timestamp


class Control4Integration(IntegrationBase):
    """Control4 home automation via direct REST API.

    Uses aiohttp for all HTTP requests with automatic token refresh.
    No dependency on pyControl4 library.

    Features:
    - Automatic credential loading from Keychain (via IntegrationBase)
    - Automatic token refresh before expiry (24h tokens)
    - Automatic token storage in Keychain
    - Health tracking via base class
    """

    # IntegrationBase configuration
    integration_name: ClassVar[str] = "Control4"
    credential_keys: ClassVar[list[tuple[str, str]]] = [
        ("control4_host", "control4_host"),
        ("control4_bearer_token", "control4_bearer_token"),
        ("control4_username", "control4_username"),
        ("control4_password", "control4_password"),
        ("control4_controller_name", "control4_controller_name"),
    ]

    def __init__(self, config: SmartHomeConfig) -> None:
        super().__init__(config)
        self._session: aiohttp.ClientSession | None = None
        self._token: Control4Token | None = None

        # Discovered devices (populated on connect)
        self._items: dict[int, dict[str, Any]] = {}
        self._rooms: dict[int, dict[str, Any]] = {}
        self._lights: dict[int, dict[str, Any]] = {}
        self._shades: dict[int, dict[str, Any]] = {}
        self._audio_zones: dict[int, dict[str, Any]] = {}
        self._locks: dict[int, dict[str, Any]] = {}
        self._security_panel_id: int | None = None
        self._ams_id: int | None = None  # Triad AMS audio matrix
        self._fireplace_id: int | None = None
        self._mantelmount_id: int | None = None

        # Token refresh task
        self._refresh_task: asyncio.Task[None] | None = None

    def _validate_bearer_token(self, token: str | None) -> bool:
        """Validate bearer token format and basic security requirements.

        Args:
            token: The bearer token to validate

        Returns:
            True if token meets basic security requirements, False otherwise
        """
        if not token:
            return False
        if len(token) < 10:
            return False
        # Check for basic complexity (not all same chars, has letters and numbers/symbols)
        if len(set(token)) < 4:
            return False
        # Check not a common/weak token (exact match only)
        weak_tokens = {"password", "admin", "test", "token", "123456", "abcdef", "password123"}
        if token.lower() in weak_tokens:
            return False
        return True

    def _build_endpoint(self, path: str) -> str:
        """Build full API endpoint URL.

        Args:
            path: API path (e.g., "/items")

        Returns:
            Full HTTPS URL for the endpoint
        """
        # Normalize path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"https://{self.config.control4_host}:8443/api/v1{path}"

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests.

        Returns:
            Dict with Authorization and other required headers
        """
        headers = {
            "User-Agent": "Kagami-SmartHome/1.0",
            "Content-Type": "application/json",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token.director_token}"
        elif self.config.control4_bearer_token:
            headers["Authorization"] = f"Bearer {self.config.control4_bearer_token}"
        return headers

    def _create_ssl_context(self) -> ssl.SSLContext | bool:
        """Create SSL context based on configuration.

        SSL verification can be configured via:
        1. config.control4_verify_ssl (default: True)
        2. CONTROL4_VERIFY_SSL environment variable ("0", "false", "no" to disable)
        3. config.control4_ca_cert or CONTROL4_CA_CERT for custom CA certificate

        Returns:
            ssl.SSLContext if custom CA cert provided or verification disabled,
            True for default verification, False should never be returned.
        """
        # Check environment variable override (for development)
        env_verify = os.environ.get("CONTROL4_VERIFY_SSL", "").lower()
        if env_verify in ("0", "false", "no"):
            verify_ssl = False
            logger.warning(
                "Control4: SSL verification disabled via CONTROL4_VERIFY_SSL environment variable. "
                "This is insecure and should only be used for development with self-signed certificates."
            )
        else:
            verify_ssl = self.config.control4_verify_ssl

        # Check for custom CA certificate
        ca_cert = self.config.control4_ca_cert or os.environ.get("CONTROL4_CA_CERT")

        if ca_cert:
            # Use custom CA certificate
            ssl_context = ssl.create_default_context()
            try:
                ssl_context.load_verify_locations(ca_cert)
                logger.info(f"Control4: Using custom CA certificate: {ca_cert}")
                return ssl_context
            except (FileNotFoundError, ssl.SSLError) as e:
                logger.error(f"Control4: Failed to load CA certificate '{ca_cert}': {e}")
                # Fall back to default verification
                return True

        if not verify_ssl:
            # Disable verification (insecure, for self-signed certs only)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            return ssl_context

        # Default: enable full SSL verification
        return True

    async def _ensure_credentials_loaded(self) -> None:
        """Ensure credentials are loaded from Keychain.

        Uses the base class load_credentials method, then applies defaults.
        """
        await self.load_credentials()

        # Default host if still not set
        if not self.config.control4_host:
            self.config.control4_host = "192.168.1.2"  # Default to core5

    def _save_token_to_keychain(self, token: str) -> bool:
        """Save bearer token to Keychain."""
        try:
            import subprocess
        except ImportError:
            return False

        try:
            subprocess.run(
                [
                    "security",
                    "delete-generic-password",
                    "-s",
                    "kagami",
                    "-a",
                    "control4_bearer_token",
                ],
                capture_output=True,
            )
            result = subprocess.run(
                [
                    "security",
                    "add-generic-password",
                    "-s",
                    "kagami",
                    "-a",
                    "control4_bearer_token",
                    "-w",
                    token,
                ],
                capture_output=True,
            )
            if result.returncode == 0:
                logger.info("Control4: Bearer token saved to Keychain")
                return True
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            logger.debug(f"Control4: Could not save to Keychain: {e}")
        except Exception as e:
            logger.warning(f"Control4: Unexpected keychain error: {e}")
        return False

    @property
    def is_connected(self) -> bool:
        """Check if connected to Control4 Director."""
        return self._initialized and self._session is not None and self._connected

    async def connect(self) -> bool:
        """Connect to Control4 Director with automatic token management."""
        self._last_connect_attempt = time.time()

        # Load credentials from Keychain (via base class)
        await self._ensure_credentials_loaded()

        if not self.config.control4_host:
            self._record_failure("host not configured")
            logger.warning("Control4: host not configured")
            return False

        # Create SSL context based on configuration (secure by default)
        ssl_context = self._create_ssl_context()

        # Configure connection pooling for better performance and reliability
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=10,  # Total connection pool size
            limit_per_host=5,  # Max connections per host
            ttl_dns_cache=300,  # DNS cache TTL (5 minutes)
            use_dns_cache=True,
            keepalive_timeout=60,  # Keep connections alive for 1 minute
            enable_cleanup_closed=True,  # Clean up closed connections
        )

        # Configure session with timeouts and retry settings
        timeout = aiohttp.ClientTimeout(
            total=60,  # Total request timeout
            connect=10,  # Connection timeout
            sock_read=30,  # Socket read timeout
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": "Kagami-SmartHome/1.0"},
        )

        # Try to use existing bearer token first
        if self.config.control4_bearer_token:
            self._token = Control4Token(
                account_token="",
                director_token=self.config.control4_bearer_token,
                controller_name="",
                expires_at=time.time() + 86400,  # Assume 24h validity
            )

            if await self._test_connection():
                await self._discover_devices()
                self._initialized = True
                self._connected = True
                self._record_success()
                self._start_token_refresh()
                logger.info(
                    f"✅ Control4: {len(self._rooms)} rooms, "
                    f"{len(self._lights)} lights, {len(self._audio_zones)} audio zones"
                )
                return True
            else:
                logger.info("Control4: Saved token expired, refreshing via cloud auth...")

        # Cloud auth with username/password - auto-refreshes token
        if self.config.control4_username and self.config.control4_password:
            if await self._authenticate():
                await self._discover_devices()
                self._initialized = True
                self._connected = True
                self._record_success()
                self._start_token_refresh()
                logger.info(
                    f"✅ Control4: {len(self._rooms)} rooms, "
                    f"{len(self._lights)} lights, {len(self._audio_zones)} audio zones"
                )
                return True
            else:
                self._record_failure("Cloud auth failed")
                logger.warning("Control4: Cloud auth failed - check username/password in keychain")

        self._record_failure("No valid authentication method available")
        logger.error("Control4: No valid authentication method available")
        return False

    async def _test_connection(self) -> bool:
        """Test if current token works."""
        if not self._session or not self._token:
            return False

        try:
            url = f"https://{self.config.control4_host}/api/v1/items"
            headers = {"Authorization": f"Bearer {self._token.director_token}"}

            async with self._session.get(
                url, headers=headers, timeout=ClientTimeout(total=10)
            ) as resp:
                return resp.status == 200
        except (TimeoutError, aiohttp.ClientError) as e:
            logger.debug(f"Control4: Connection test failed: {e}")
        except Exception as e:
            logger.warning(f"Control4: Unexpected connection test error: {e}")
        return False

    async def _authenticate(self) -> bool:
        """Authenticate via Control4 cloud and get Director token."""
        if not self._session:
            return False

        try:
            # Step 1: Get account bearer token
            payload = {
                "clientInfo": {
                    "device": {
                        "deviceName": "kagami",
                        "deviceUUID": "kagami-smarthome-001",
                        "make": "Kagami",
                        "model": "SmartHome",
                        "os": "Python",
                        "osVersion": "3.11",
                    },
                    "userInfo": {
                        "applicationKey": APPLICATION_KEY,
                        "password": self.config.control4_password,
                        "userName": self.config.control4_username,
                    },
                }
            }

            async with self._session.post(
                AUTH_ENDPOINT, json=payload, timeout=ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Control4: Auth failed: {text}")
                    return False

                data = await resp.json()
                account_token = data.get("authToken", {}).get("token")
                if not account_token:
                    logger.error("Control4: No account token in response")
                    return False

            # Step 2: Get controllers
            headers = {"Authorization": f"Bearer {account_token}"}
            async with self._session.get(
                ACCOUNTS_ENDPOINT, headers=headers, timeout=ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    logger.warning("Control4: Could not get controllers")
                    controller_name = self.config.control4_controller_name or ""
                else:
                    data = await resp.json()
                    # Handle different response formats
                    if isinstance(data, dict) and "account" in data:
                        # New format: {"account": {"controllerCommonName": "..."}}
                        controller_name = data["account"].get("controllerCommonName", "")
                    elif isinstance(data, list) and data:
                        controller_name = data[0].get("controllerCommonName", "")
                    elif isinstance(data, dict):
                        controller_name = data.get("controllerCommonName", "")
                    else:
                        controller_name = self.config.control4_controller_name or ""

            if not controller_name:
                logger.error("Control4: No controller found")
                return False

            # Step 3: Get Director bearer token
            payload = {
                "serviceInfo": {
                    "commonName": controller_name,
                    "services": "director",
                }
            }
            headers = {
                "Authorization": f"Bearer {account_token}",
                "Content-Type": "application/json",
            }

            async with self._session.post(
                CONTROLLER_AUTH_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Control4: Director token failed: {text}")
                    return False

                data = await resp.json()
                director_token = data.get("authToken", {}).get("token")
                valid_seconds = data.get("authToken", {}).get("validSeconds", 86400)

                if not director_token:
                    logger.error("Control4: No director token in response")
                    return False

            self._token = Control4Token(
                account_token=account_token,
                director_token=director_token,
                controller_name=controller_name,
                expires_at=time.time() + valid_seconds - 300,  # 5 min buffer
            )

            # Save token to keychain for future use
            self._save_token_to_keychain(director_token)

            logger.info(f"Control4: Authenticated to {controller_name}")
            return True

        except aiohttp.ClientError as e:
            logger.error(f"Control4: Network error during authentication: {e}")
        except TimeoutError:
            logger.error("Control4: Authentication timeout - check network connectivity")
        except json.JSONDecodeError as e:
            logger.error(f"Control4: Invalid JSON response during authentication: {e}")
        except KeyError as e:
            logger.error(f"Control4: Missing required field in authentication response: {e}")
        except Exception as e:
            logger.error(f"Control4: Unexpected authentication error: {e}")
        return False

    def _start_token_refresh(self) -> None:
        """Start background token refresh task.

        Runs indefinitely with exponential backoff on failures.
        Never stops - always tries to recover.
        """
        if self._refresh_task:
            self._refresh_task.cancel()

        async def refresh_loop() -> None:
            consecutive_failures = 0
            base_delay = 60  # 1 minute base delay

            while True:
                try:
                    # Check if token needs refresh (1 hour before expiry)
                    if self._token and time.time() > self._token.expires_at - 3600:
                        logger.info("Control4: Refreshing token...")
                        success = await self._authenticate()

                        if success:
                            consecutive_failures = 0
                            logger.info("✅ Control4: Token refreshed successfully")
                        else:
                            consecutive_failures += 1
                            # Exponential backoff: 1min, 2min, 4min, 8min, max 1hr
                            delay = min(base_delay * (2**consecutive_failures), 3600)
                            logger.warning(
                                f"Control4: Token refresh failed, retry in {delay}s "
                                f"(attempt {consecutive_failures})"
                            )
                            await asyncio.sleep(delay)
                            continue  # Retry immediately after backoff

                    # Standard check interval when token is valid
                    await asyncio.sleep(1800)  # Check every 30 minutes

                except asyncio.CancelledError:
                    break
                except (TimeoutError, aiohttp.ClientError) as e:
                    consecutive_failures += 1
                    delay = min(base_delay * (2**consecutive_failures), 3600)
                    logger.warning(f"Control4: Network error ({e}), retry in {delay}s")
                    await asyncio.sleep(delay)

                except Exception as e:
                    consecutive_failures += 1
                    delay = min(base_delay * (2**consecutive_failures), 3600)
                    logger.error(f"Control4: Token refresh error ({e}), retry in {delay}s")
                    await asyncio.sleep(delay)

        self._refresh_task = asyncio.create_task(refresh_loop(), name="control4_token_refresh")

    def _create_api_retry_policy(self, max_retries: int = 2) -> RetryPolicy:
        """Create a RetryPolicy for Control4 API calls.

        Args:
            max_retries: Maximum retry attempts

        Returns:
            Configured RetryPolicy for API operations
        """
        return RetryPolicy(
            max_attempts=max_retries + 1,  # max_retries + initial attempt = max_attempts
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay=1.0,
            max_delay=30.0,
            retryable_exceptions=(
                TimeoutError,
                aiohttp.ClientError,
                aiohttp.ServerDisconnectedError,
            ),
            name="Control4 API",
        )

    async def _api_get(self, path: str, max_retries: int = 2) -> Any:
        """Make GET request to Director API using unified RetryPolicy.

        Args:
            path: API endpoint path
            max_retries: Maximum retry attempts for network failures

        Returns:
            JSON response or None if failed
        """
        if not self._session or not self._token:
            logger.debug("Control4: API call attempted without session/token")
            return None

        url = f"https://{self.config.control4_host}/api/v1{path}"
        auth_refreshed = False
        # Capture session and token for type narrowing in nested function
        session = self._session
        token = self._token

        async def do_request() -> Any:
            nonlocal auth_refreshed
            headers = {"Authorization": f"Bearer {token.director_token}"}

            async with session.get(url, headers=headers, timeout=ClientTimeout(total=30)) as resp:
                _log_request_context("GET", path, resp.status)

                if resp.status == 200:
                    self._record_success()
                    return await resp.json()
                elif resp.status == 401:
                    # Token expired, try refresh (only once per call)
                    if not auth_refreshed:
                        logger.info("Control4: Token expired during API call, refreshing...")
                        if await self._authenticate():
                            auth_refreshed = True
                            # Raise to trigger retry with new token
                            raise aiohttp.ClientError("Token refreshed, retrying")
                    self._record_failure("Authentication failed")
                    logger.error("Control4: Authentication failed, cannot complete API call")
                    return None
                elif resp.status == 404:
                    logger.debug(f"Control4: Endpoint not found: {path}")
                    return None  # Don't retry 404s
                elif resp.status in (500, 502, 503, 504):
                    self._record_failure(f"Server error {resp.status}")
                    # Raise to trigger retry
                    raise aiohttp.ClientError(f"Server error {resp.status}")
                else:
                    text = await resp.text()
                    self._record_failure(f"API error {resp.status}")
                    logger.warning(f"Control4 API error {resp.status} on {path}: {text[:200]}")
                    return None

        policy = self._create_api_retry_policy(max_retries)
        try:
            return await policy.execute(do_request)
        except json.JSONDecodeError as e:
            _log_request_context("GET", path, error=f"Invalid JSON: {e}")
            self._record_failure(f"Invalid JSON: {e}")
            return None
        except Exception as e:
            _log_request_context("GET", path, error=f"Failed after retries: {e}")
            self._record_failure(f"Failed after retries: {e}")
            return None

    async def _api_post(self, path: str, data: dict[str, Any], max_retries: int = 2) -> bool:
        """Make POST request to Director API using unified RetryPolicy.

        Args:
            path: API endpoint path
            data: JSON payload to send
            max_retries: Maximum retry attempts for network failures

        Returns:
            True if successful, False otherwise
        """
        if not self._session or not self._token:
            logger.debug("Control4: POST attempted without session/token")
            return False

        url = f"https://{self.config.control4_host}/api/v1{path}"
        auth_refreshed = False
        # Capture session and token for type narrowing in nested function
        session = self._session
        token = self._token

        async def do_request() -> bool:
            nonlocal auth_refreshed
            headers = {
                "Authorization": f"Bearer {token.director_token}",
                "Content-Type": "application/json",
            }

            async with session.post(
                url, json=data, headers=headers, timeout=ClientTimeout(total=30)
            ) as resp:
                _log_request_context("POST", path, resp.status)

                if resp.status in (200, 204):
                    self._record_success()
                    return True
                elif resp.status == 401:
                    # Token expired, try refresh (only once per call)
                    if not auth_refreshed:
                        logger.info("Control4: Token expired during POST, refreshing...")
                        if await self._authenticate():
                            auth_refreshed = True
                            # Raise to trigger retry with new token
                            raise aiohttp.ClientError("Token refreshed, retrying")
                    self._record_failure("Authentication failed on POST")
                    logger.error("Control4: Authentication failed, cannot complete POST")
                    return False
                elif resp.status == 404:
                    logger.debug(f"Control4: POST endpoint not found: {path}")
                    return False  # Don't retry 404s
                elif resp.status in (500, 502, 503, 504):
                    self._record_failure(f"Server error {resp.status} on POST")
                    # Raise to trigger retry
                    raise aiohttp.ClientError(f"Server error {resp.status}")
                else:
                    text = await resp.text()
                    self._record_failure(f"POST error {resp.status}")
                    logger.warning(f"Control4 POST error {resp.status} on {path}: {text[:200]}")
                    return False

        policy = self._create_api_retry_policy(max_retries)
        try:
            result: bool = await policy.execute(do_request)
            return result
        except Exception as e:
            logger.error(f"Control4: POST {path} failed after retries: {e}")
            self._record_failure(f"POST failed after retries: {e}")
            return False

    async def _discover_devices(self) -> None:
        """Discover all Control4 items."""
        items = await self._api_get("/items")
        if not items:
            return

        self._items.clear()
        self._rooms.clear()
        self._lights.clear()
        self._shades.clear()
        self._audio_zones.clear()
        self._locks.clear()

        for item in items:
            item_id = item.get("id")
            item_type = item.get("type")
            name = item.get("name", "")
            name_lower = name.lower()

            self._items[item_id] = item

            # Rooms (type 8)
            if item_type == ITEM_TYPE_ROOM and name != "Routines":
                self._rooms[item_id] = {
                    "id": item_id,
                    "name": name,
                }

            # Lights - Lutron LEAP dimmers/switches (type 7)
            if item_type == ITEM_TYPE_DEVICE:
                if (
                    any(
                        x in name_lower
                        for x in [
                            "can",
                            "pendant",
                            "sconce",
                            "chandelier",
                            "toe kick",
                            "undercabinet",
                            "vanity",
                        ]
                    )
                    and "shade" not in name_lower
                ):
                    self._lights[item_id] = {
                        "id": item_id,
                        "name": name,
                        "room_id": item.get("roomId"),
                        "room_name": item.get("roomName", ""),
                    }

                # Shades - Lutron LEAP roller shades (type 7)
                if "shade" in name_lower and "pico" not in name_lower:
                    self._shades[item_id] = {
                        "id": item_id,
                        "name": name,
                        "room_id": item.get("roomId"),
                        "room_name": item.get("roomName", ""),
                    }

                # Locks - August Smart Locks (type 7, "Lock" in name but not "Auto-Lock")
                if (
                    "lock" in name_lower
                    and "auto-lock" not in name_lower
                    and "gateway" not in name_lower
                ):
                    self._locks[item_id] = {
                        "id": item_id,
                        "name": name,
                        "room_id": item.get("roomId"),
                        "room_name": item.get("roomName", ""),
                    }

                # Triad AMS audio matrix
                if "ams" in name_lower and "16x16" in name_lower:
                    self._ams_id = item_id

                # DSC Security Panel
                if name == "Security":
                    self._security_panel_id = item_id

                # Fireplace
                if name == "Fireplace":
                    self._fireplace_id = item_id

                # MantelMount
                if "mantelmount" in name_lower:
                    self._mantelmount_id = item_id

        # All rooms are audio zones (each has Triad AMS output)
        for room_id, room in self._rooms.items():
            self._audio_zones[room_id] = {
                "id": room_id,
                "name": room["name"],
                "type": "room",
            }

        logger.debug(
            f"Control4: Discovered {len(self._items)} items, "
            f"{len(self._lights)} lights, {len(self._shades)} shades, "
            f"{len(self._locks)} locks, AMS={self._ams_id}, Security={self._security_panel_id}"
        )

    # =========================================================================
    # Lighting Control
    # =========================================================================

    async def set_light_level(self, light_id: int, level: int) -> bool:
        """Set light brightness (0-100)."""
        return await self._api_post(
            f"/items/{light_id}/commands",
            {"command": "SET_LEVEL", "params": {"LEVEL": level}},
        )

    async def set_room_lights(self, room_name: str, level: int) -> bool:
        """Set all lights in a room."""
        room_lower = room_name.lower()
        results = []

        for light_id, light in self._lights.items():
            if room_lower in light.get("room_name", "").lower():
                results.append(await self.set_light_level(light_id, level))

        return any(results) if results else False

    async def get_light_state(self, light_id: int) -> dict[str, Any] | None:
        """Get current light state."""
        vars = await self._api_get(f"/items/{light_id}/variables")
        if vars:
            for v in vars:
                if v.get("varName") == "Brightness Percent":
                    return {"level": v.get("value", 0)}
        return None

    # =========================================================================
    # Shade Control (Lutron LEAP Roller Shades)
    # =========================================================================

    async def set_shade_level(self, shade_id: int, level: int) -> bool:
        """Set shade position using SET_LEVEL_TARGET command.

        Control4/Lutron convention:
        - 0 = fully CLOSED (lowered/down)
        - 100 = fully OPEN (raised/up)

        Note: LEVEL_TARGET must be passed as string, not int.
        We use SET_LEVEL_TARGET which works reliably across Lutron LEAP shades.
        """
        return await self._api_post(
            f"/items/{shade_id}/commands",
            {"command": "SET_LEVEL_TARGET", "params": {"LEVEL_TARGET": str(level)}},
        )

    async def open_shade(self, shade_id: int) -> bool:
        """Fully open (raise) shade.

        Uses SET_LEVEL_TARGET with params format which works reliably
        across Lutron LEAP shades. Level 100 = fully open/raised.
        """
        return await self._api_post(
            f"/items/{shade_id}/commands",
            {"command": "SET_LEVEL_TARGET", "params": {"LEVEL_TARGET": "100"}},
        )

    async def close_shade(self, shade_id: int) -> bool:
        """Fully close (lower) shade.

        Uses SET_LEVEL_TARGET with params format which works reliably
        across Lutron LEAP shades. Level 0 = fully closed/lowered.
        """
        return await self._api_post(
            f"/items/{shade_id}/commands",
            {"command": "SET_LEVEL_TARGET", "params": {"LEVEL_TARGET": "0"}},
        )

    async def stop_shade(self, shade_id: int) -> bool:
        """Stop shade movement."""
        return await self._api_post(f"/items/{shade_id}/commands", {"command": "STOP"})

    async def set_room_shades(self, room_name: str, level: int) -> bool:
        """Set all shades in a room to level."""
        room_lower = room_name.lower()
        results = []

        for shade_id, shade in self._shades.items():
            if room_lower in shade.get("room_name", "").lower():
                results.append(await self.set_shade_level(shade_id, level))

        return any(results) if results else False

    async def get_shade_state(self, shade_id: int) -> dict[str, Any]:
        """Get shade state."""
        vars = await self._api_get(f"/items/{shade_id}/variables")
        if not vars:
            return {}

        state: dict[str, Any] = {}
        for v in vars:
            name = v.get("varName", "")
            if name == "Level":
                state["level"] = v.get("value", 0)
            elif name == "Fully Open":
                state["open"] = v.get("value", 0) == 1
            elif name == "Fully Closed":
                state["closed"] = v.get("value", 0) == 1
            elif name == "Opening":
                state["opening"] = v.get("value", 0) == 1
            elif name == "Closing":
                state["closing"] = v.get("value", 0) == 1

        return state

    # =========================================================================
    # Lock Control (August Smart Locks)
    # =========================================================================

    async def lock(self, lock_id: int) -> bool:
        """Lock a door."""
        return await self._api_post(f"/items/{lock_id}/commands", {"command": "LOCK"})

    async def unlock(self, lock_id: int) -> bool:
        """Unlock a door."""
        return await self._api_post(f"/items/{lock_id}/commands", {"command": "UNLOCK"})

    async def get_lock_state(self, lock_id: int) -> dict[str, Any]:
        """Get lock state."""
        vars = await self._api_get(f"/items/{lock_id}/variables")
        if not vars:
            return {}

        for v in vars:
            if v.get("varName") == "STATE":
                return {"locked": v.get("value", "") == "Locked"}

        return {}

    async def lock_all(self) -> bool:
        """Lock all doors."""
        results = [await self.lock(lock_id) for lock_id in self._locks]
        return all(results) if results else False

    async def unlock_door(self, door_name: str) -> bool:
        """Unlock a specific door by name."""
        door_lower = door_name.lower()
        for lock_id, lock in self._locks.items():
            if (
                door_lower in lock.get("name", "").lower()
                or door_lower in lock.get("room_name", "").lower()
            ):
                return await self.unlock(lock_id)
        return False

    # =========================================================================
    # Fireplace Control
    # =========================================================================

    async def fireplace_on(self) -> bool:
        """Turn on fireplace."""
        if not self._fireplace_id:
            return False
        # Fireplace uses relay, toggle state
        return await self._api_post(f"/items/{self._fireplace_id}/commands", {"command": "Select"})

    async def fireplace_off(self) -> bool:
        """Turn off fireplace."""
        if not self._fireplace_id:
            return False
        return await self._api_post(f"/items/{self._fireplace_id}/commands", {"command": "Select"})

    async def get_fireplace_state(self) -> dict[str, Any]:
        """Get fireplace state."""
        if not self._fireplace_id:
            return {}

        vars = await self._api_get(f"/items/{self._fireplace_id}/variables")
        if not vars:
            return {}

        for v in vars:
            if v.get("varName") == "STATE":
                return {"on": v.get("value", 0) == 1}

        return {}

    # =========================================================================
    # MantelMount TV Mount Control (MM860 v2)
    # =========================================================================
    #
    # Commands: Home, Move (Direction), Jog (Direction), Stop, Memory Recall/Save
    # Directions: Up, Down, Left, Right
    # Memory presets: 1-3
    #
    # Variables:
    #   LEFT/RIGHT_ACTUATOR_POSITION: 0-100
    #   MOUNT_ELEVATION: current height
    #   LEFT/RIGHT_AT_LIMIT: 1 if at limit

    async def mantelmount_home(self) -> bool:
        """Return MantelMount to home position (up/hidden)."""
        if not self._mantelmount_id:
            return False
        return await self._api_post(f"/items/{self._mantelmount_id}/commands", {"command": "Home"})

    async def mantelmount_down(self) -> bool:
        """Move MantelMount down (lower TV into viewing position)."""
        if not self._mantelmount_id:
            return False
        return await self._api_post(
            f"/items/{self._mantelmount_id}/commands",
            {"command": "Move", "params": {"Direction": "Down"}},
        )

    async def mantelmount_up(self) -> bool:
        """Move MantelMount up (raise TV toward home)."""
        if not self._mantelmount_id:
            return False
        return await self._api_post(
            f"/items/{self._mantelmount_id}/commands",
            {"command": "Move", "params": {"Direction": "Up"}},
        )

    async def mantelmount_move(self, direction: str) -> bool:
        """Move MantelMount in a direction.

        Args:
            direction: "Up", "Down", "Left", or "Right"
        """
        if not self._mantelmount_id:
            return False
        return await self._api_post(
            f"/items/{self._mantelmount_id}/commands",
            {"command": "Move", "params": {"Direction": direction}},
        )

    async def mantelmount_recall(self, preset: int = 1) -> bool:
        """Recall MantelMount memory preset.

        Args:
            preset: Memory index 1-3
        """
        if not self._mantelmount_id:
            return False
        return await self._api_post(
            f"/items/{self._mantelmount_id}/commands",
            {"command": "Memory Recall", "params": {"MemoryIndex": preset}},
        )

    async def mantelmount_save(self, preset: int = 1) -> bool:
        """Save current MantelMount position to memory preset.

        Args:
            preset: Memory index 1-3
        """
        if not self._mantelmount_id:
            return False
        return await self._api_post(
            f"/items/{self._mantelmount_id}/commands",
            {"command": "Memory Save", "params": {"MemoryIndex": preset}},
        )

    async def mantelmount_stop(self) -> bool:
        """Stop MantelMount movement."""
        if not self._mantelmount_id:
            return False
        return await self._api_post(f"/items/{self._mantelmount_id}/commands", {"command": "Stop"})

    async def get_mantelmount_state(self) -> dict[str, Any]:
        """Get MantelMount state."""
        if not self._mantelmount_id:
            return {}

        vars = await self._api_get(f"/items/{self._mantelmount_id}/variables")
        if not vars:
            return {}

        state: dict[str, Any] = {}
        for v in vars:
            name = v.get("varName", "")
            value = v.get("value")
            if name == "LEFT_ACTUATOR_POSITION":
                state["left_position"] = value
            elif name == "RIGHT_ACTUATOR_POSITION":
                state["right_position"] = value
            elif name == "MOUNT_ELEVATION":
                state["elevation"] = value
            elif name == "LEFT_AT_LIMIT":
                state["left_at_limit"] = value == 1
            elif name == "RIGHT_AT_LIMIT":
                state["right_at_limit"] = value == 1
            elif name == "STATUS":
                state["status"] = value
            elif name == "TEMPERATURE":
                state["temperature"] = value

        return state

    # =========================================================================
    # Audio Control (Triad AMS + Room Zones)
    # =========================================================================

    async def set_room_volume(self, room_id: int, volume: int) -> bool:
        """Set room audio volume (0-100)."""
        return await self._api_post(
            f"/items/{room_id}/commands",
            {"command": "SET_VOLUME_LEVEL", "params": {"LEVEL": volume}},
        )

    async def set_room_mute(self, room_id: int, mute: bool) -> bool:
        """Mute/unmute room audio."""
        cmd = "MUTE_ON" if mute else "MUTE_OFF"
        return await self._api_post(f"/items/{room_id}/commands", {"command": cmd})

    async def play_in_room(self, room_id: int) -> bool:
        """Start audio playback in room."""
        return await self._api_post(f"/items/{room_id}/commands", {"command": "PLAY"})

    async def stop_in_room(self, room_id: int) -> bool:
        """Stop audio playback in room."""
        return await self._api_post(f"/items/{room_id}/commands", {"command": "STOP"})

    async def get_room_audio_state(self, room_id: int) -> dict[str, Any]:
        """Get room audio state."""
        vars = await self._api_get(f"/items/{room_id}/variables")
        if not vars:
            return {}

        state: dict[str, Any] = {}
        for v in vars:
            name = v.get("varName", "")
            if name == "CURRENT_VOLUME":
                state["volume"] = v.get("value", 0)
            elif name == "IS_MUTED":
                state["muted"] = v.get("value", 0) == 1
            elif name == "CURRENT_AUDIO_DEVICE":
                state["device_id"] = v.get("value", 0)

        return state

    async def set_room_audio(
        self, room_name: str, volume: int, source_id: int | None = None
    ) -> bool:
        """Set audio in a room by name."""
        room_lower = room_name.lower()

        for room_id, room in self._rooms.items():
            if room_lower in room["name"].lower():
                result = await self.set_room_volume(room_id, volume)
                if source_id:
                    await self._api_post(
                        f"/items/{room_id}/commands",
                        {"command": "SELECT_AUDIO_DEVICE", "params": {"deviceid": source_id}},
                    )
                return result

        return False

    # =========================================================================
    # Security (DSC via Control4)
    # =========================================================================

    async def get_security_state(self) -> SecurityState:
        """Get DSC panel state."""
        if not self._security_panel_id:
            return SecurityState.DISARMED

        vars = await self._api_get(f"/items/{self._security_panel_id}/variables")
        if not vars:
            return SecurityState.DISARMED

        for v in vars:
            name = v.get("varName", "")
            value = v.get("value")

            if name == "PARTITION_STATE":
                if value == "ARMED_STAY":
                    return SecurityState.ARMED_STAY
                elif value == "ARMED_AWAY":
                    return SecurityState.ARMED_AWAY
                elif value == "ARMED_NIGHT":
                    return SecurityState.ARMED_NIGHT
                elif value == "ALARM":
                    return SecurityState.ALARM
                elif value == "TROUBLE":
                    return SecurityState.TROUBLE

        return SecurityState.DISARMED

    async def arm_security(self, mode: SecurityState, code: str | None = None) -> bool:
        """Arm/disarm security system."""
        if not self._security_panel_id:
            logger.warning("Control4: No security panel discovered")
            return False

        cmd_map = {
            SecurityState.ARMED_STAY: "ARM_STAY",
            SecurityState.ARMED_AWAY: "ARM_AWAY",
            SecurityState.ARMED_NIGHT: "ARM_NIGHT",
            SecurityState.DISARMED: "DISARM",
        }

        cmd = cmd_map.get(mode)
        if not cmd:
            return False

        params: dict[str, Any] = {}
        if mode == SecurityState.DISARMED:
            params["CODE"] = code or self.config.dsc_code or ""

        return await self._api_post(
            f"/items/{self._security_panel_id}/commands",
            {"command": cmd, "params": params},
        )

    # =========================================================================
    # Scenes
    # =========================================================================

    async def activate_scene(self, scene_name: str) -> bool:
        """Activate a Control4 scene by name."""
        # Scenes are typically in the Routines room or as agents
        for item_id, item in self._items.items():
            if item.get("type") == ITEM_TYPE_AGENT:
                if scene_name.lower() in item.get("name", "").lower():
                    return await self._api_post(
                        f"/items/{item_id}/commands", {"command": "EXECUTE"}
                    )
        return False

    # =========================================================================
    # Device Info
    # =========================================================================

    def get_rooms(self) -> dict[int, dict[str, Any]]:
        """Get discovered rooms."""
        return self._rooms.copy()

    def get_lights(self) -> dict[int, dict[str, Any]]:
        """Get discovered lights."""
        return self._lights.copy()

    def get_shades(self) -> dict[int, dict[str, Any]]:
        """Get discovered shades."""
        return self._shades.copy()

    def get_locks(self) -> dict[int, dict[str, Any]]:
        """Get discovered locks."""
        return self._locks.copy()

    def get_audio_zones(self) -> dict[int, dict[str, Any]]:
        """Get audio zones (all rooms)."""
        return self._audio_zones.copy()

    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None

        if self._session:
            await self._session.close()
            self._session = None

        self._connected = False
        self._initialized = False
        self._token = None
        logger.info("Control4: Disconnected")

    async def health_check(self) -> HealthStatus:
        """Perform a health check on the Control4 integration.

        Tests actual connectivity by making an API call to the Director.

        Returns:
            HealthStatus with current health information
        """
        if not self._initialized:
            return HealthStatus.unknown("Control4 not initialized")

        if not self._session or not self._token:
            return HealthStatus.unhealthy(
                "No active session or token",
                reachable=False,
                consecutive_failures=self._consecutive_failures,
            )

        # Test connection with a lightweight API call
        start_time = time.time()
        try:
            if await self._test_connection():
                latency_ms = (time.time() - start_time) * 1000
                self._record_success()
                return HealthStatus.healthy(
                    f"Control4 connected to {self.config.control4_host}",
                    latency_ms=latency_ms,
                    rooms=len(self._rooms),
                    lights=len(self._lights),
                    shades=len(self._shades),
                    locks=len(self._locks),
                    audio_zones=len(self._audio_zones),
                    token_expires_at=self._token.expires_at if self._token else None,
                )
            else:
                self._record_failure("Connection test failed")
                return HealthStatus.unhealthy(
                    "Connection test failed",
                    reachable=True,
                    consecutive_failures=self._consecutive_failures,
                )
        except Exception as e:
            self._record_failure(str(e))
            return HealthStatus.unhealthy(
                f"Health check error: {e}",
                reachable=False,
                consecutive_failures=self._consecutive_failures,
            )


# =============================================================================
# WEBSOCKET REAL-TIME EVENTS (Dec 30, 2025)
# =============================================================================

# Type for event callbacks: (item_id, variable_name, old_value, new_value) -> None
Control4EventCallback = Callable[[int, str, Any, Any], Awaitable[None]]


class Control4WebSocket:
    """WebSocket connection for real-time Control4 events.

    Provides sub-second latency for state changes vs 30s polling.

    Usage:
        ws = Control4WebSocket(integration)
        ws.on_event(callback)  # Subscribe to all events
        await ws.connect()

        # Events will fire your callback:
        # async def callback(item_id, var_name, old_val, new_val):
        #     print(f"Item {item_id} changed: {var_name} = {new_val}")

    Architecture:
        - Connects to Director's WebSocket endpoint
        - Authenticates with bearer token
        - Subscribes to all item variables
        - Dispatches events to callbacks
        - Auto-reconnects on disconnect

    Created: December 30, 2025
    """

    RECONNECT_DELAY = 5.0  # Seconds between reconnect attempts
    PING_INTERVAL = 30.0  # Send ping every 30s to keep connection alive

    def __init__(self, integration: Control4Integration):
        self._integration = integration
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._running = False
        self._listener_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._callbacks: list[Control4EventCallback] = []

        # Track subscribed items for reconnection
        self._subscribed_items: set[int] = set()

        # Statistics
        self._stats = {
            "events_received": 0,
            "reconnects": 0,
            "last_event_time": 0.0,
        }

    def on_event(self, callback: Control4EventCallback) -> None:
        """Register callback for all Control4 events."""
        self._callbacks.append(callback)

    def off_event(self, callback: Control4EventCallback) -> None:
        """Unregister event callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws is not None and not self._ws.closed

    async def connect(self) -> bool:
        """Connect to Control4 Director WebSocket.

        Returns:
            True if connected successfully
        """
        if not self._integration.is_connected:
            logger.warning("Control4WS: REST API not connected, cannot start WebSocket")
            return False

        if not self._integration._token:
            logger.warning("Control4WS: No token available")
            return False

        try:
            # WebSocket endpoint is wss://{host}/api/v1/websocket
            host = self._integration.config.control4_host
            ws_url = f"wss://{host}/api/v1/websocket"

            # Use same SSL context as main integration (secure by default)
            ssl_context = self._integration._create_ssl_context()

            # Get session from integration or create new
            session = self._integration._session
            if not session:
                logger.warning("Control4WS: No HTTP session available")
                return False

            # Connect with bearer token in header
            headers = {
                "Authorization": f"Bearer {self._integration._token.director_token}",
            }

            self._ws = await session.ws_connect(
                ws_url,
                ssl=ssl_context,
                headers=headers,
                heartbeat=self.PING_INTERVAL,
            )

            logger.info(f"✅ Control4WS: Connected to {host}")

            # Start listener and ping tasks
            self._running = True
            self._listener_task = asyncio.create_task(
                self._listen_loop(), name="control4_ws_listener"
            )

            # Subscribe to all known items
            await self._subscribe_all()

            return True

        except aiohttp.ClientError as e:
            logger.error(f"Control4WS: Connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Control4WS: Unexpected error: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect WebSocket."""
        self._running = False

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._ws and not self._ws.closed:
            await self._ws.close()

        self._ws = None
        logger.info("Control4WS: Disconnected")

    async def _subscribe_all(self) -> None:
        """Subscribe to all discovered items."""
        if not self._ws or self._ws.closed:
            return

        # Subscribe to lights, shades, locks, audio zones
        all_items = {
            **self._integration._lights,
            **self._integration._shades,
            **self._integration._locks,
            **self._integration._audio_zones,
        }

        # Add special items
        if self._integration._fireplace_id:
            all_items[self._integration._fireplace_id] = {"name": "fireplace"}
        if self._integration._mantelmount_id:
            all_items[self._integration._mantelmount_id] = {"name": "mantelmount"}
        if self._integration._security_panel_id:
            all_items[self._integration._security_panel_id] = {"name": "security"}

        # Subscribe to all items in parallel
        if all_items:
            await asyncio.gather(
                *[self._subscribe_item(item_id) for item_id in all_items],
                return_exceptions=True,
            )

        logger.info(f"Control4WS: Subscribed to {len(all_items)} items")

    async def _subscribe_item(self, item_id: int) -> None:
        """Subscribe to a specific item's variable changes."""
        if not self._ws or self._ws.closed:
            return

        try:
            # Control4 WebSocket subscription message format
            msg = {
                "type": "subscribe",
                "itemId": item_id,
            }
            await self._ws.send_json(msg)
            self._subscribed_items.add(item_id)
        except Exception as e:
            logger.debug(f"Control4WS: Failed to subscribe to {item_id}: {e}")

    async def _listen_loop(self) -> None:
        """Main WebSocket listener loop."""
        while self._running:
            try:
                if not self._ws or self._ws.closed:
                    # Reconnect
                    await asyncio.sleep(self.RECONNECT_DELAY)
                    self._stats["reconnects"] += 1
                    if not await self.connect():
                        continue

                # Capture ws for type narrowing after connect
                ws = self._ws
                if ws is None:
                    continue

                # Receive message
                msg = await ws.receive(timeout=60.0)

                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.warning("Control4WS: Connection closed, will reconnect")
                    self._ws = None
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"Control4WS: Error: {ws.exception()}")
                    self._ws = None

            except TimeoutError:
                # No message received, connection still alive
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Control4WS: Listen error: {e}")
                await asyncio.sleep(self.RECONNECT_DELAY)

    async def _handle_message(self, raw: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(raw)

            msg_type = data.get("type", "")

            if msg_type == "variableUpdate":
                # Variable change event
                item_id = data.get("itemId")
                var_name = data.get("varName", "")
                old_value = data.get("oldValue")
                new_value = data.get("value")

                if item_id is not None:
                    self._stats["events_received"] += 1
                    self._stats["last_event_time"] = time.time()

                    # Dispatch to callbacks
                    for callback in self._callbacks:
                        try:
                            await callback(item_id, var_name, old_value, new_value)
                        except Exception as e:
                            logger.error(f"Control4WS: Callback error: {e}")

            elif msg_type == "error":
                logger.warning(f"Control4WS: Server error: {data.get('message', 'Unknown')}")

            elif msg_type == "subscribed":
                logger.debug(f"Control4WS: Subscribed to item {data.get('itemId')}")

        except json.JSONDecodeError:
            logger.debug(f"Control4WS: Invalid JSON: {raw[:100]}")
        except Exception as e:
            logger.error(f"Control4WS: Message handling error: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get WebSocket statistics."""
        return {
            **self._stats,
            "connected": self.is_connected,
            "subscribed_items": len(self._subscribed_items),
            "callbacks": len(self._callbacks),
        }
