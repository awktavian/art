"""UniFi Protect + Network Integration.

Provides:
- Camera motion/person detection events (Protect)
- WiFi client presence detection (Network)
- Doorbell events
- Camera snapshots
- **Audio streams via RTSP** (microphone + speaker)
- **Two-way audio** communication
- **WebSocket real-time events** (motion, person, vehicle, doorbell)

Camera Hardware (7331 W Green Lake Dr N):
- 4x UniFi AI Pro cameras (UVC-AI-Pro) - working
- 1x Third-party camera - offline
- All have built-in microphone + speaker
- 4K resolution, AI person/vehicle detection
- NVR: UDM Pro Max with 22TB storage (3+ month retention)

RTSP Stream Access:
- Port: 7447
- Format: rtsp://<host>:7447/<camera_id>
- Requires RTSP enabled in Protect settings
- Audio: AAC codec when microphone enabled

WebSocket Real-Time Events (NEW Dec 30, 2025):
- Endpoint: wss://<host>/proxy/protect/api/ws/updates
- Binary protocol with 4 frames: header, action, header, data
- Events: motion start/end, smart detection (person/vehicle), doorbell
- Sub-second latency vs 2s polling

Architecture:
- UDM Pro Max at 192.168.1.1 runs both Protect and Network
- Local API access (bypasses cloud 2FA when using local admin)

Authentication:
Local Admin (Recommended): Create a local-only admin on UDM Pro
   - Go to UniFi OS Settings > Admins > Add Admin
   - Select "Local Access Only"
   - Store: secrets.set("unifi_local_username", "kagami")
           secrets.set("unifi_local_password", "your_password")

Created: December 29, 2025
Updated: December 30, 2025 - Added WebSocket real-time events
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import struct
import time
from collections.abc import Callable
from typing import Any

import aiohttp
from aiohttp import ClientTimeout
from kagami.core.shared_abstractions.retry_policy import (
    BackoffStrategy,
    RetryPolicy,
)

from kagami_smarthome.types import PresenceEvent, SmartHomeConfig

logger = logging.getLogger(__name__)


# =============================================================================
# WebSocket Binary Protocol Constants
# =============================================================================

# Packet types in header
PACKET_TYPE_ACTION = 1
PACKET_TYPE_PAYLOAD = 2

# Payload formats
PAYLOAD_FORMAT_JSON = 1
PAYLOAD_FORMAT_UTF8 = 2
PAYLOAD_FORMAT_BUFFER = 3


class UniFiIntegration:
    """UniFi Protect + Network integration.

    Uses direct REST API calls for maximum reliability.
    Supports multiple authentication methods for UDM Pro.

    Features:
    - Automatic credential loading from Keychain
    - Automatic reconnection on auth failure
    - Session refresh before expiry
    """

    def __init__(self, config: SmartHomeConfig):
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._csrf_token: str | None = None
        self._cookies: dict[str, str] = {}
        self._auth_method: str = "none"

        self._event_callbacks: list[Callable[[PresenceEvent], None]] = []
        self._running = False
        self._poll_task: asyncio.Task[None] | None = None
        self._refresh_task: asyncio.Task[None] | None = None

        # Cached state
        self._cameras: dict[str, dict[str, Any]] = {}
        self._clients: dict[str, dict[str, Any]] = {}  # MAC -> client info
        self._known_clients_online: set[str] = set()
        self._initialized = False

        # Auth tracking
        self._last_auth_time: float = 0
        self._auth_refresh_interval: int = 1800  # Refresh auth every 30 minutes (more aggressive)
        self._consecutive_failures: int = 0
        self._max_consecutive_failures: int = 10
        self._last_successful_api_call: float = 0
        self._health_check_interval: int = 300  # Health check every 5 minutes

        # WebSocket real-time events
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_task: asyncio.Task[None] | None = None
        self._ws_connected: bool = False
        self._ws_reconnect_delay: float = 1.0  # Initial reconnect delay
        self._ws_max_reconnect_delay: float = 60.0  # Max reconnect delay
        self._use_websocket: bool = True  # Prefer WebSocket over polling

        # Identity detection
        self._identity_callback: Callable[[str, str, bytes, dict[str, Any]], None] | None = None
        self._last_snapshot_time: dict[str, float] = {}  # camera_id -> timestamp
        self._snapshot_rate_limit: float = 5.0  # Min seconds between snapshots per camera
        self._identity_detection_enabled: bool = False

        # Load credentials from macOS Keychain
        self._load_credentials_from_keychain()

    def _load_credentials_from_keychain(self) -> None:
        """Load UniFi host from Keychain."""
        try:
            from kagami_smarthome.secrets import load_integration_credentials

            # Only load host - auth credentials are read directly in _auth_local_from_keychain
            load_integration_credentials(
                "UniFi",
                self.config,
                [("unifi_host", "unifi_host")],
            )
        except Exception as e:
            logger.debug(f"UniFi: Could not load from Keychain: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to UniFi controller."""
        return self._initialized and self._session is not None

    @property
    def is_healthy(self) -> bool:
        """Check if connection is healthy (recent successful API calls)."""
        if not self.is_connected:
            return False
        # Unhealthy if no successful call in 10 minutes
        if self._last_successful_api_call > 0:
            return (time.time() - self._last_successful_api_call) < 600
        return self._initialized

    def _create_ssl_context(self) -> ssl.SSLContext | bool:
        """Create SSL context based on configuration.

        SSL verification can be configured via:
        1. config.unifi_verify_ssl (default: True)
        2. UNIFI_VERIFY_SSL environment variable ("0", "false", "no" to disable)

        Returns:
            ssl.SSLContext if verification disabled, True for default verification.
        """
        import os

        # Check environment variable override (for development)
        env_verify = os.environ.get("UNIFI_VERIFY_SSL", "").lower()
        if env_verify in ("0", "false", "no"):
            verify_ssl = False
            logger.warning(
                "UniFi: SSL verification disabled via UNIFI_VERIFY_SSL environment variable. "
                "This is insecure and should only be used for development with self-signed certificates."
            )
        else:
            verify_ssl = self.config.unifi_verify_ssl

        if not verify_ssl:
            # Disable verification (insecure, for self-signed certs only)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            return ssl_context

        # Default: enable full SSL verification
        return True

    async def connect(self) -> bool:
        """Connect to UniFi controller."""
        # Create SSL context based on config (respects unifi_verify_ssl setting)
        ssl_context = self._create_ssl_context()

        # Configure connection pooling for better performance
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=8,  # Total connection pool size
            limit_per_host=4,  # Max connections per host
            ttl_dns_cache=300,  # DNS cache TTL (5 minutes)
            use_dns_cache=True,
            keepalive_timeout=120,  # Keep connections alive for 2 minutes
            enable_cleanup_closed=True,
        )

        # Configure session with timeouts and retry settings
        timeout = aiohttp.ClientTimeout(
            total=45,  # Total request timeout
            connect=10,  # Connection timeout
            sock_read=30,  # Socket read timeout
        )

        # Use cookie jar to persist auth cookies across requests
        cookie_jar = aiohttp.CookieJar(unsafe=True)

        self._session = aiohttp.ClientSession(
            connector=connector,
            cookie_jar=cookie_jar,
            timeout=timeout,
            headers={"User-Agent": "Kagami-SmartHome/1.0"},
        )

        # Try authentication methods in order of preference
        auth_success = await self._authenticate()

        if not auth_success:
            await self._session.close()
            self._session = None
            return False

        # Discover cameras
        await self._discover_cameras()

        # Get initial client list
        await self._update_clients()

        self._initialized = True
        logger.info(
            f"✅ UniFi ({self._auth_method}): {len(self._cameras)} cameras, "
            f"{len(self._clients)} clients"
        )
        return True

    async def _authenticate(self) -> bool:
        """Authenticate with UniFi controller.

        Auth methods (in order):
        1. Local admin credentials from Keychain (recommended, bypasses 2FA)
        2. Stored session token (fallback for cloud accounts)
        """
        if not self._session:
            return False

        # Try local admin from Keychain (recommended, no 2FA)
        if await self._auth_local_from_keychain():
            self._auth_method = "local_keychain"
            return True

        # Fallback: stored session token
        if await self._auth_with_token():
            self._auth_method = "token"
            return True

        logger.error(
            "UniFi: Authentication failed.\n"
            "  Store local admin: secrets.set('unifi_local_username', 'kagami')\n"
            "                     secrets.set('unifi_local_password', 'password')"
        )
        return False

    async def _auth_local_from_keychain(self) -> bool:
        """Authenticate using local admin credentials from Keychain."""
        if not self._session:
            return False

        # Get local admin credentials from Keychain (REQUIRED)
        from kagami_smarthome.secrets import secrets

        username = secrets.get("unifi_local_username") or secrets.get("unifi_username")
        password = secrets.get("unifi_local_password") or secrets.get("unifi_password")

        if not username or not password:
            return False

        host = self.config.unifi_host or "192.168.1.1"
        url = f"https://{host}/api/auth/login"
        payload = {
            "username": username,
            "password": password,
            "rememberMe": True,
        }

        try:
            async with self._session.post(
                url, json=payload, timeout=ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    self._csrf_token = resp.headers.get("X-CSRF-Token")
                    for cookie in resp.cookies.values():
                        self._cookies[cookie.key] = cookie.value
                    logger.info(f"✅ UniFi: Local admin '{username}' authenticated")
                    return True
                else:
                    logger.debug(f"UniFi: Local keychain auth failed ({resp.status})")
        except aiohttp.ClientError as e:
            logger.debug(f"UniFi: Network error during keychain auth: {e}")
        except TimeoutError:
            logger.debug("UniFi: Keychain auth timeout")
        except Exception as e:
            logger.warning(f"UniFi: Unexpected keychain auth error: {e}")

        return False

    async def _auth_with_token(self) -> bool:
        """Authenticate using stored session token."""
        if not self._session:
            return False

        # Try to get token from Keychain
        # Get session token from Keychain
        from kagami_smarthome.secrets import secrets

        token = secrets.get("unifi_session_token")

        if not token:
            return False

        # Set the token cookie
        self._cookies["TOKEN"] = token

        # Test if token works
        url = f"https://{self.config.unifi_host}/proxy/network/api/s/default/self"
        try:
            async with self._session.get(
                url, cookies=self._cookies, timeout=ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    # Get CSRF token from response
                    self._csrf_token = resp.headers.get("X-CSRF-Token")
                    logger.debug("UniFi: Session token valid")
                    return True
                else:
                    logger.debug(f"UniFi: Session token invalid ({resp.status})")
        except aiohttp.ClientError as e:
            logger.debug(f"UniFi: Network error during token auth: {e}")
        except TimeoutError:
            logger.debug("UniFi: Token auth timeout")
        except Exception as e:
            logger.warning(f"UniFi: Unexpected token auth error: {e}")

        return False

    def _create_api_retry_policy(self, max_retries: int = 2) -> RetryPolicy:
        """Create a RetryPolicy for UniFi API calls.

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
            name="UniFi API",
        )

    async def _api_get(self, path: str, max_retries: int = 2) -> Any:
        """Make authenticated GET request using unified RetryPolicy.

        Args:
            path: API endpoint path
            max_retries: Maximum retry attempts for network failures

        Returns:
            JSON response or None if failed
        """
        if not self._session:
            logger.debug("UniFi: API call attempted without session")
            return None

        host = self.config.unifi_host or "192.168.1.1"
        url = f"https://{host}{path}"
        auth_refreshed = False

        async def do_request() -> Any:
            nonlocal auth_refreshed
            headers = {}
            if self._csrf_token:
                headers["X-CSRF-Token"] = self._csrf_token

            async with self._session.get(
                url, headers=headers, timeout=ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    self._last_successful_api_call = time.time()
                    self._consecutive_failures = 0
                    return await resp.json()
                elif resp.status == 401:
                    # Re-authenticate (only once per call)
                    if not auth_refreshed:
                        logger.info("UniFi: Token expired during API call, re-authenticating...")
                        if await self._authenticate():
                            auth_refreshed = True
                            # Raise to trigger retry with new token
                            raise aiohttp.ClientError("Token refreshed, retrying")
                    logger.error("UniFi: Authentication failed, cannot complete API call")
                    return None
                elif resp.status == 403:
                    logger.error(f"UniFi: Access denied to {path}")
                    return None  # Don't retry 403s
                elif resp.status == 404:
                    logger.debug(f"UniFi: Endpoint not found: {path}")
                    return None  # Don't retry 404s
                elif resp.status in (500, 502, 503, 504):
                    # Raise to trigger retry
                    raise aiohttp.ClientError(f"Server error {resp.status}")
                else:
                    logger.warning(f"UniFi API error {resp.status} on {path}")
                    return None

        policy = self._create_api_retry_policy(max_retries)
        try:
            return await policy.execute(do_request)
        except json.JSONDecodeError as e:
            logger.error(f"UniFi: Invalid JSON response from {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"UniFi: {path} failed after retries: {e}")
            return None

    async def _discover_cameras(self) -> None:
        """Discover Protect cameras."""
        # Try Protect API (UDM Pro)
        data = await self._api_get("/proxy/protect/api/cameras")
        if data:
            for cam in data:
                cam_id = cam.get("id", "")
                self._cameras[cam_id] = {
                    "id": cam_id,
                    "name": cam.get("name", "Unknown"),
                    "type": cam.get("type", ""),
                    "is_connected": cam.get("isConnected", False),
                    "last_motion": cam.get("lastMotion"),
                    "last_ring": cam.get("lastRing"),
                    "features": cam.get("featureFlags", {}),
                }
                logger.debug(f"UniFi: Camera {cam.get('name')}")

    async def _update_clients(self) -> None:
        """Update network client list."""
        # Network API on UDM
        data = await self._api_get("/proxy/network/api/s/default/stat/sta")
        if not data:
            # Try alternate endpoint
            data = await self._api_get("/proxy/network/v2/api/site/default/clients/active")

        if data:
            clients = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(clients, list):
                self._clients.clear()
                for client in clients:
                    mac = client.get("mac", "").lower()
                    self._clients[mac] = {
                        "mac": mac,
                        "hostname": client.get("hostname", client.get("name", "")),
                        "ip": client.get("ip", ""),
                        "is_wired": client.get("is_wired", False),
                        "last_seen": client.get("last_seen", 0),
                        "ap_mac": client.get("ap_mac", ""),
                    }

    async def force_reconnect(self) -> bool:
        """Force a full reconnection to UniFi controller.

        Use this when the connection appears unhealthy.
        Returns True if reconnection succeeded.
        """
        logger.info("UniFi: Force reconnecting...")

        # Close existing session
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
        self._initialized = False
        self._csrf_token = None
        self._cookies.clear()

        # Reconnect
        success = await self.connect()
        if success:
            logger.info("✅ UniFi: Force reconnect successful")
            self._consecutive_failures = 0
        else:
            logger.error("❌ UniFi: Force reconnect failed")
        return success

    async def _health_check(self) -> bool:
        """Quick health check - try a simple API call."""
        try:
            data = await self._api_get("/proxy/network/api/s/default/self")
            return data is not None
        except Exception:
            return False

    async def _start_session_refresh(self) -> None:
        """Background task to refresh authentication and monitor health."""
        consecutive_failures = 0
        max_failures = 5
        base_delay = 60  # 1 minute base delay
        health_check_counter = 0

        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute

                if not self._running:
                    break

                health_check_counter += 1

                # Periodic health check every 5 minutes
                if health_check_counter >= 5:
                    health_check_counter = 0
                    if not await self._health_check():
                        logger.warning("UniFi: Health check failed, attempting reconnect...")
                        if await self.force_reconnect():
                            consecutive_failures = 0
                            continue
                        else:
                            consecutive_failures += 1

                # Refresh auth every 30 minutes
                if time.time() - self._last_auth_time > self._auth_refresh_interval:
                    logger.debug("UniFi: Refreshing authentication...")
                    success = await self._authenticate()

                    if success:
                        consecutive_failures = 0
                        self._last_auth_time = time.time()
                        logger.debug("UniFi: Session refreshed successfully")
                    else:
                        consecutive_failures += 1
                        logger.warning(
                            f"UniFi: Session refresh failed (attempt {consecutive_failures}/{max_failures})"
                        )

                        # Try force reconnect on repeated failures
                        if consecutive_failures >= 3:
                            logger.warning(
                                "UniFi: Multiple refresh failures, force reconnecting..."
                            )
                            if await self.force_reconnect():
                                consecutive_failures = 0

                        if consecutive_failures >= max_failures:
                            logger.error(
                                "UniFi: Max session refresh failures reached, stopping refresh loop"
                            )
                            break

            except asyncio.CancelledError:
                break
            except (TimeoutError, aiohttp.ClientError) as e:
                consecutive_failures += 1
                logger.warning(f"UniFi: Network error during session refresh: {e}")

                # Exponential backoff with jitter
                delay = min(base_delay * (2**consecutive_failures), 1800)  # Max 30 minutes
                jitter = delay * 0.1
                actual_delay = delay + (hash(str(time.time())) % max(int(jitter * 2), 1) - jitter)

                logger.debug(f"UniFi: Retrying in {actual_delay:.1f}s")
                await asyncio.sleep(max(actual_delay, 30))

            except Exception as e:
                consecutive_failures += 1
                logger.error(f"UniFi: Unexpected session refresh error: {e}")

                # Standard exponential backoff
                delay = min(base_delay * (2**consecutive_failures), 1800)
                await asyncio.sleep(delay)

    async def start_event_stream(self, prefer_websocket: bool = True) -> None:
        """Start event stream (WebSocket preferred, polling fallback).

        Args:
            prefer_websocket: If True, try WebSocket first. Falls back to polling.
        """
        self._running = True

        # Start session refresh task
        self._refresh_task = asyncio.create_task(self._start_session_refresh())

        # Try WebSocket first if preferred
        if prefer_websocket and self._use_websocket:
            ws_success = await self.start_websocket_events()
            if ws_success:
                logger.info("⚡ UniFi: Using WebSocket for real-time events (sub-second latency)")

                # Still need polling for WiFi client presence (not in WebSocket)
                # Start a reduced-frequency poll for WiFi only
                asyncio.create_task(self._wifi_presence_poll())
                return
            else:
                logger.warning("UniFi: WebSocket failed, falling back to polling")

        async def poll_loop() -> None:
            last_motion_times: dict[str, int] = {}
            last_client_check = 0

            while self._running:
                try:
                    # Check cameras for motion/person detection
                    data = await self._api_get("/proxy/protect/api/cameras")
                    if data:
                        for cam in data:
                            cam_id = cam.get("id", "")
                            cam_name = cam.get("name", "Unknown")

                            # Motion detection
                            last_motion = cam.get("lastMotion", 0)
                            if last_motion and last_motion > last_motion_times.get(cam_id, 0):
                                last_motion_times[cam_id] = last_motion

                                # Check for smart detection
                                smart_types = cam.get("lastSmartDetectTypes", [])
                                if "person" in smart_types:
                                    self._emit_event(
                                        PresenceEvent(
                                            source="unifi_camera",
                                            event_type="person",
                                            location=cam_name,
                                            confidence=0.95,
                                            metadata={"camera_id": cam_id},
                                        )
                                    )
                                elif "vehicle" in smart_types:
                                    self._emit_event(
                                        PresenceEvent(
                                            source="unifi_camera",
                                            event_type="vehicle",
                                            location=cam_name,
                                            confidence=0.9,
                                            metadata={"camera_id": cam_id},
                                        )
                                    )
                                else:
                                    self._emit_event(
                                        PresenceEvent(
                                            source="unifi_camera",
                                            event_type="motion",
                                            location=cam_name,
                                            confidence=0.7,
                                            metadata={"camera_id": cam_id},
                                        )
                                    )

                            # Doorbell ring
                            last_ring = cam.get("lastRing", 0)
                            if (
                                last_ring
                                and cam.get("type") == "UVC G4 Doorbell"
                                and last_ring > last_motion_times.get(f"{cam_id}_ring", 0)
                            ):
                                last_motion_times[f"{cam_id}_ring"] = last_ring
                                self._emit_event(
                                    PresenceEvent(
                                        source="unifi_doorbell",
                                        event_type="ring",
                                        location="front_door",
                                        confidence=1.0,
                                    )
                                )

                    # Check WiFi clients periodically (every 30 seconds)
                    now = time.time()
                    if now - last_client_check > 30:
                        last_client_check = now
                        await self._check_wifi_presence()

                    await asyncio.sleep(2)  # Poll every 2 seconds

                except asyncio.CancelledError:
                    break
                except (TimeoutError, aiohttp.ClientError) as e:
                    self._consecutive_failures += 1
                    logger.warning(
                        f"UniFi: Network error during polling: {e} (failures: {self._consecutive_failures})"
                    )

                    # Auto-reconnect after repeated failures
                    if self._consecutive_failures >= 5:
                        logger.warning("UniFi: Too many failures, triggering reconnect...")
                        await self.force_reconnect()

                    await asyncio.sleep(10)  # Longer delay for network issues
                except json.JSONDecodeError as e:
                    logger.warning(f"UniFi: Invalid JSON in poll response: {e}")
                    await asyncio.sleep(5)
                except Exception as e:
                    self._consecutive_failures += 1
                    logger.error(
                        f"UniFi: Unexpected polling error: {e} (failures: {self._consecutive_failures})"
                    )

                    if self._consecutive_failures >= 5:
                        logger.warning("UniFi: Too many failures, triggering reconnect...")
                        await self.force_reconnect()

                    await asyncio.sleep(15)  # Longer delay for unknown errors

        self._poll_task = asyncio.create_task(poll_loop())
        logger.info("🎥 UniFi: Event stream started (polling mode)")

    async def _wifi_presence_poll(self) -> None:
        """Lightweight polling for WiFi client presence only.

        Used when WebSocket is active (which doesn't include WiFi events).
        """
        while self._running:
            try:
                await self._check_wifi_presence()
                # Check less frequently since this is supplementary
                await asyncio.sleep(30)  # Every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"UniFi: WiFi presence poll error: {e}")
                await asyncio.sleep(30)

    async def _check_wifi_presence(self) -> None:
        """Check WiFi presence of known devices."""
        await self._update_clients()

        known_macs = {m.lower() for m in self.config.known_devices}
        currently_online = set()

        for mac, client in self._clients.items():
            if mac in known_macs:
                currently_online.add(mac)

        # Detect connects
        for mac in currently_online - self._known_clients_online:
            hostname = self._clients.get(mac, {}).get("hostname", mac)
            self._emit_event(
                PresenceEvent(
                    source="unifi_wifi",
                    event_type="connect",
                    location=None,
                    confidence=1.0,
                    metadata={"mac": mac, "hostname": hostname},
                )
            )
            logger.info(f"📱 UniFi: {hostname} connected")

        # Detect disconnects
        for mac in self._known_clients_online - currently_online:
            hostname = mac  # May not have client info anymore
            self._emit_event(
                PresenceEvent(
                    source="unifi_wifi",
                    event_type="disconnect",
                    location=None,
                    confidence=1.0,
                    metadata={"mac": mac},
                )
            )
            logger.info(f"📱 UniFi: {hostname} disconnected")

        self._known_clients_online = currently_online

    def on_event(self, callback: Callable[[PresenceEvent], None]) -> None:
        """Register event callback."""
        self._event_callbacks.append(callback)

    def _emit_event(self, event: PresenceEvent) -> None:
        """Emit event to all callbacks."""
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"UniFi: Event callback error: {e}")

    async def check_wifi_presence(self) -> list[str]:
        """Get list of known devices currently on WiFi."""
        await self._update_clients()

        connected: list[str] = []
        known_macs = {m.lower() for m in self.config.known_devices}

        for mac in self._clients:
            if mac in known_macs:
                connected.append(mac)

        return connected

    async def get_camera_snapshot(self, camera_name: str) -> bytes | None:
        """Get snapshot from camera."""
        if not self._session:
            return None

        host = self.config.unifi_host or "192.168.1.1"
        for cam_id, cam in self._cameras.items():
            if cam["name"].lower() == camera_name.lower():
                url = f"https://{host}/proxy/protect/api/cameras/{cam_id}/snapshot"
                headers = {}
                if self._csrf_token:
                    headers["X-CSRF-Token"] = self._csrf_token

                try:
                    async with self._session.get(
                        url, headers=headers, timeout=ClientTimeout(total=30)
                    ) as resp:
                        if resp.status == 200:
                            return await resp.read()
                except Exception as e:
                    logger.error(f"UniFi: Snapshot error: {e}")

        return None

    async def capture_snapshot_by_id(self, camera_id: str) -> bytes | None:
        """Capture snapshot from camera by ID with rate limiting.

        Args:
            camera_id: UniFi camera ID

        Returns:
            JPEG image bytes or None
        """
        if not self._session:
            return None

        # Rate limit check
        now = time.time()
        last_time = self._last_snapshot_time.get(camera_id, 0)
        if now - last_time < self._snapshot_rate_limit:
            logger.debug(f"UniFi: Snapshot rate limited for {camera_id}")
            return None

        host = self.config.unifi_host or "192.168.1.1"
        url = f"https://{host}/proxy/protect/api/cameras/{camera_id}/snapshot"
        headers = {}
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        try:
            async with self._session.get(
                url, headers=headers, timeout=ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    self._last_snapshot_time[camera_id] = now
                    return await resp.read()
        except Exception as e:
            logger.error(f"UniFi: Snapshot error for {camera_id}: {e}")

        return None

    async def get_event_thumbnail(self, event_id: str) -> bytes | None:
        """Get thumbnail for a detection event.

        Event thumbnails are the actual frames that triggered the detection,
        which are better for face recognition than live snapshots.

        Args:
            event_id: UniFi event ID from WebSocket event

        Returns:
            JPEG image bytes or None
        """
        if not self._session:
            return None

        host = self.config.unifi_host or "192.168.1.1"
        url = f"https://{host}/proxy/protect/api/events/{event_id}/thumbnail"
        headers = {}
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        try:
            async with self._session.get(
                url, headers=headers, timeout=ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    logger.debug(f"UniFi: Event thumbnail {event_id} status {resp.status}")
        except Exception as e:
            logger.error(f"UniFi: Event thumbnail error for {event_id}: {e}")

        return None

    async def get_event_details(self, event_id: str) -> dict[str, Any] | None:
        """Get detailed event data including smart detection metadata.

        Args:
            event_id: UniFi event ID

        Returns:
            Event data dict or None
        """
        if not self._session:
            return None

        host = self.config.unifi_host or "192.168.1.1"
        url = f"https://{host}/proxy/protect/api/events/{event_id}"
        headers = {}
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        try:
            async with self._session.get(
                url, headers=headers, timeout=ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error(f"UniFi: Event details error for {event_id}: {e}")

        return None

    def enable_identity_detection(
        self,
        callback: Callable[[str, str, bytes, dict[str, Any]], None],
        rate_limit: float = 5.0,
    ) -> None:
        """Enable identity detection on person detection events.

        When a person is detected by UniFi AI, the event thumbnail is fetched
        and passed to the callback for face recognition.

        Uses event thumbnails (the actual detection frame) rather than
        live snapshots for better face recognition accuracy.

        Args:
            callback: Function(camera_id, camera_name, image_bytes, metadata) to call
                metadata includes: event_id, confidence, timestamp, smart_types
            rate_limit: Minimum seconds between detections per camera
        """
        self._identity_callback = callback
        self._snapshot_rate_limit = rate_limit
        self._identity_detection_enabled = True
        logger.info(f"UniFi: Identity detection enabled (rate limit: {rate_limit}s)")

    def disable_identity_detection(self) -> None:
        """Disable identity detection."""
        self._identity_detection_enabled = False
        self._identity_callback = None
        logger.info("UniFi: Identity detection disabled")

    async def _trigger_identity_detection(
        self,
        camera_id: str,
        camera_name: str,
        event_id: str | None = None,
        confidence: float = 0.0,
    ) -> None:
        """Trigger identity detection using event thumbnail or snapshot.

        Prefers event thumbnail (the actual detection frame) over live snapshot.
        Rate-limited to prevent excessive API calls.

        Args:
            camera_id: UniFi camera ID
            camera_name: Human-readable camera name
            event_id: Optional event ID for thumbnail retrieval
            confidence: Detection confidence from UniFi (0-1)
        """
        if not self._identity_detection_enabled or not self._identity_callback:
            return

        # Rate limit check
        now = time.time()
        last_time = self._last_snapshot_time.get(camera_id, 0)
        if now - last_time < self._snapshot_rate_limit:
            logger.debug(f"UniFi: Identity detection rate limited for {camera_name}")
            return

        # Try event thumbnail first (better for face recognition)
        image_bytes = None
        if event_id:
            image_bytes = await self.get_event_thumbnail(event_id)

        # Fall back to live snapshot
        if not image_bytes:
            image_bytes = await self.capture_snapshot_by_id(camera_id)

        if not image_bytes:
            logger.debug(f"UniFi: No image available for identity detection on {camera_name}")
            return

        # Update rate limit timestamp
        self._last_snapshot_time[camera_id] = now

        # Build metadata
        metadata = {
            "event_id": event_id,
            "confidence": confidence,
            "timestamp": now,
            "camera_id": camera_id,
            "camera_name": camera_name,
            "source": "event_thumbnail" if event_id else "snapshot",
        }

        try:
            # Call the identity callback (async or sync)
            if asyncio.iscoroutinefunction(self._identity_callback):
                await self._identity_callback(camera_id, camera_name, image_bytes, metadata)
            else:
                self._identity_callback(camera_id, camera_name, image_bytes, metadata)
        except Exception as e:
            logger.error(f"UniFi: Identity callback error: {e}")

    def get_cameras(self) -> dict[str, dict[str, Any]]:
        """Get discovered cameras."""
        return self._cameras.copy()

    def get_clients(self) -> dict[str, dict[str, Any]]:
        """Get network clients."""
        return self._clients.copy()

    def get_rtsp_url(self, camera_name: str, quality: str = "high") -> str | None:
        """Get RTSP stream URL for a camera.

        Args:
            camera_name: Name of camera (e.g., "Driveway", "Back Deck")
            quality: Stream quality - "high", "medium", or "low"

        Returns:
            RTSP URL string or None if camera not found.

        Note:
            - RTSP must be enabled in UniFi Protect camera settings
            - Audio is included when microphone is enabled
            - Format: rtsp://host:7447/camera_id?quality=high
        """
        host = self.config.unifi_host or "192.168.1.1"

        for cam_id, cam in self._cameras.items():
            if cam.get("name", "").lower() == camera_name.lower():
                # UniFi RTSP URL format
                # Quality options: 0=high, 1=medium, 2=low
                quality_map = {"high": 0, "medium": 1, "low": 2}
                q = quality_map.get(quality, 0)

                return f"rtsp://{host}:7447/{cam_id}?quality={q}"

        return None

    def get_all_rtsp_urls(self) -> dict[str, str]:
        """Get RTSP URLs for all cameras.

        Returns:
            Dict mapping camera name to RTSP URL.
        """
        host = self.config.unifi_host or "192.168.1.1"
        urls = {}

        for cam_id, cam in self._cameras.items():
            name = cam.get("name", f"camera_{cam_id[:8]}")
            urls[name] = f"rtsp://{host}:7447/{cam_id}"

        return urls

    def get_camera_audio_info(self, camera_name: str) -> dict[str, Any] | None:
        """Get audio capabilities for a camera.

        Returns dict with:
            - has_microphone: bool
            - has_speaker: bool
            - microphone_enabled: bool
            - speaker_enabled: bool
            - mic_volume: int (0-100)
            - speaker_volume: int (0-100)
        """
        for cam_id, cam in self._cameras.items():
            if cam.get("name", "").lower() == camera_name.lower():
                return {
                    "has_microphone": cam.get("hasMic", True),  # AI Pro has mic
                    "has_speaker": cam.get("hasSpeaker", True),  # AI Pro has speaker
                    "microphone_enabled": cam.get("isMicEnabled", False),
                    "speaker_enabled": cam.get("isSpeakerEnabled", False),
                    "mic_volume": cam.get("micVolume", 100),
                    "speaker_volume": cam.get("speakerVolume", 100),
                    "model": cam.get("modelKey", "unknown"),
                    "rtsp_url": self.get_rtsp_url(camera_name),
                }

        return None

    def get_all_cameras_audio(self) -> dict[str, dict[str, Any]]:
        """Get audio info for all cameras."""
        return {
            cam.get("name", f"camera_{cam_id[:8]}"): {
                "has_microphone": cam.get("hasMic", True),
                "has_speaker": cam.get("hasSpeaker", True),
                "microphone_enabled": cam.get("isMicEnabled", False),
                "model": cam.get("modelKey", "unknown"),
            }
            for cam_id, cam in self._cameras.items()
        }

    # =========================================================================
    # WebSocket Real-Time Events (NEW Dec 30, 2025)
    # =========================================================================

    def _decode_ws_packet(self, data: bytes) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Decode UniFi Protect WebSocket binary packet.

        Binary protocol format (4 frames):
        1. Header Frame (8 bytes): type, format, deflated, unknown, size
        2. Action Frame: JSON with action, id, modelKey, newUpdateId
        3. Header Frame (8 bytes): Same format
        4. Data Frame: JSON payload

        Returns:
            Tuple of (action_frame, data_frame) or (None, None) on error
        """
        if len(data) < 8:
            return None, None

        try:
            # Parse first header (8 bytes)
            # Format: packet_type (1), payload_format (1), deflated (1), unknown (1), size (4)
            _packet_type = data[0]  # noqa: F841 - preserved for protocol documentation
            payload_format = data[1]
            deflated = data[2]
            payload_size = struct.unpack(">I", data[4:8])[0]

            if len(data) < 8 + payload_size:
                return None, None

            # Extract action frame payload
            action_data = data[8 : 8 + payload_size]

            # Decompress if needed
            if deflated:
                import zlib

                action_data = zlib.decompress(action_data)

            # Parse action JSON
            action_frame = None
            if payload_format == PAYLOAD_FORMAT_JSON:
                action_frame = json.loads(action_data.decode("utf-8"))
            elif payload_format == PAYLOAD_FORMAT_UTF8:
                action_frame = {"raw": action_data.decode("utf-8")}

            # Check for second header + data frame
            data_frame = None
            offset = 8 + payload_size

            if len(data) > offset + 8:
                # Parse second header
                data_payload_format = data[offset + 1]
                data_deflated = data[offset + 2]
                data_size = struct.unpack(">I", data[offset + 4 : offset + 8])[0]

                if len(data) >= offset + 8 + data_size:
                    data_payload = data[offset + 8 : offset + 8 + data_size]

                    if data_deflated:
                        import zlib

                        data_payload = zlib.decompress(data_payload)

                    if data_payload_format == PAYLOAD_FORMAT_JSON:
                        data_frame = json.loads(data_payload.decode("utf-8"))
                    elif data_payload_format == PAYLOAD_FORMAT_UTF8:
                        data_frame = {"raw": data_payload.decode("utf-8")}

            return action_frame, data_frame

        except Exception as e:
            logger.debug(f"UniFi WS: Failed to decode packet: {e}")
            return None, None

    def _handle_ws_event(self, action: dict[str, Any], data: dict[str, Any] | None) -> None:
        """Handle a decoded WebSocket event.

        Event types we care about:
        - Camera motion start/end
        - Smart detection (person, vehicle, package, animal)
        - Doorbell ring
        - Client connect/disconnect (Network)
        """
        model_key = action.get("modelKey", "")
        action_type = action.get("action", "")
        device_id = action.get("id", "")

        if not data:
            return

        # Camera events
        if model_key == "camera":
            camera_name = self._cameras.get(device_id, {}).get("name", device_id)

            # Motion detection
            if "isMotionDetected" in data:
                if data["isMotionDetected"]:
                    self._emit_event(
                        PresenceEvent(
                            source="unifi_camera_ws",
                            event_type="motion_start",
                            location=camera_name,
                            confidence=0.8,
                            metadata={"camera_id": device_id, "realtime": True},
                        )
                    )
                    logger.debug(f"📹 UniFi WS: Motion started on {camera_name}")

            # Smart detection
            if "lastSmartDetectTypes" in data:
                smart_types = data.get("lastSmartDetectTypes", [])
                for detect_type in smart_types:
                    confidence = 0.95 if detect_type == "person" else 0.90
                    self._emit_event(
                        PresenceEvent(
                            source="unifi_camera_ws",
                            event_type=detect_type,
                            location=camera_name,
                            confidence=confidence,
                            metadata={"camera_id": device_id, "realtime": True},
                        )
                    )
                    logger.info(f"🧠 UniFi WS: {detect_type} detected on {camera_name}")

                    # Trigger identity detection for person detections
                    # Note: Camera events don't have event_id, use snapshot fallback
                    if detect_type == "person":
                        asyncio.create_task(
                            self._trigger_identity_detection(
                                device_id, camera_name, event_id=None, confidence=confidence
                            )
                        )

            # Doorbell ring
            if "lastRing" in data and action_type == "update":
                self._emit_event(
                    PresenceEvent(
                        source="unifi_camera_ws",
                        event_type="doorbell",
                        location=camera_name,
                        confidence=1.0,
                        metadata={"camera_id": device_id, "realtime": True},
                    )
                )
                logger.info(f"🔔 UniFi WS: Doorbell ring on {camera_name}")

        # Smart Detection Zone events
        elif model_key == "smartDetectZone":
            # These are zone-specific smart detections
            pass

        # Event model (detailed events with metadata)
        elif model_key == "event":
            event_type = data.get("type", "")
            camera_id = data.get("camera", "")
            camera_name = self._cameras.get(camera_id, {}).get("name", camera_id)
            score = data.get("score", 0) / 100.0  # Convert 0-100 to 0-1

            if event_type in ("motion", "smartDetectZone"):
                smart_types = data.get("smartDetectTypes", [])
                event_id = data.get("id")
                for detect_type in smart_types:
                    self._emit_event(
                        PresenceEvent(
                            source="unifi_event_ws",
                            event_type=detect_type,
                            location=camera_name,
                            confidence=score,
                            metadata={
                                "camera_id": camera_id,
                                "event_id": event_id,
                                "realtime": True,
                            },
                        )
                    )

                    # Trigger identity detection for person detections
                    # Use event_id for optimal thumbnail retrieval
                    if detect_type == "person" and event_id:
                        asyncio.create_task(
                            self._trigger_identity_detection(
                                camera_id, camera_name, event_id=event_id, confidence=score
                            )
                        )
            elif event_type == "ring":
                self._emit_event(
                    PresenceEvent(
                        source="unifi_event_ws",
                        event_type="doorbell",
                        location=camera_name,
                        confidence=1.0,
                        metadata={"camera_id": camera_id, "realtime": True},
                    )
                )

    async def _get_bootstrap(self) -> dict[str, Any] | None:
        """Fetch bootstrap data including lastUpdateId.

        Required before WebSocket connection.
        """
        try:
            bootstrap = await self._api_get("/proxy/protect/api/bootstrap")
            if bootstrap:
                logger.debug(
                    f"UniFi WS: Got bootstrap, lastUpdateId={bootstrap.get('lastUpdateId')}"
                )
                return bootstrap
        except Exception as e:
            logger.warning(f"UniFi WS: Failed to get bootstrap: {e}")
        return None

    async def _ws_connect(self) -> aiohttp.ClientWebSocketResponse | None:
        """Establish WebSocket connection to UniFi Protect.

        Requires bootstrap data to get lastUpdateId.

        Returns:
            WebSocket connection or None on failure
        """
        if not self._session or not self._initialized:
            logger.warning("UniFi WS: Not initialized, cannot connect")
            return None

        # First get bootstrap to get lastUpdateId
        bootstrap = await self._get_bootstrap()
        if not bootstrap:
            logger.warning("UniFi WS: Cannot connect without bootstrap data")
            return None

        last_update_id = bootstrap.get("lastUpdateId")
        if not last_update_id:
            logger.warning("UniFi WS: No lastUpdateId in bootstrap")
            return None

        host = self.config.unifi_host or "192.168.1.1"
        # Note: endpoint is /ws/updates (not /api/ws/updates)
        ws_url = f"wss://{host}/proxy/protect/ws/updates?lastUpdateId={last_update_id}"

        # Build headers with auth - cookies from session
        headers: dict[str, str] = {
            "User-Agent": "Kagami/1.0",
        }

        # Add cookies
        cookie_str = "; ".join([f"{k}={v}" for k, v in self._cookies.items()])
        if cookie_str:
            headers["Cookie"] = cookie_str

        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        try:
            # Use same SSL context as main connection (respects config)
            ssl_context = self._create_ssl_context()

            ws = await self._session.ws_connect(
                ws_url,
                headers=headers,
                ssl=ssl_context,
                heartbeat=30.0,
                receive_timeout=60.0,
            )

            logger.info(f"⚡ UniFi WS: Connected (lastUpdateId={last_update_id[:8]}...)")
            self._ws_connected = True
            self._ws_reconnect_delay = 1.0  # Reset reconnect delay on success

            return ws

        except aiohttp.ClientError as e:
            logger.warning(f"UniFi WS: Connection failed: {e}")
            return None
        except Exception as e:
            logger.error(f"UniFi WS: Unexpected connection error: {e}")
            return None

    async def _ws_loop(self) -> None:
        """Main WebSocket event loop with auto-reconnection."""
        while self._running:
            try:
                # Connect
                self._ws = await self._ws_connect()

                if not self._ws:
                    # Connection failed, wait and retry
                    logger.debug(f"UniFi WS: Reconnecting in {self._ws_reconnect_delay}s...")
                    await asyncio.sleep(self._ws_reconnect_delay)
                    self._ws_reconnect_delay = min(
                        self._ws_reconnect_delay * 2, self._ws_max_reconnect_delay
                    )
                    continue

                # Read messages
                async for msg in self._ws:
                    if msg.type == aiohttp.WSMsgType.BINARY:
                        # Decode and handle event
                        action, data = self._decode_ws_packet(msg.data)
                        if action:
                            self._handle_ws_event(action, data)

                    elif msg.type == aiohttp.WSMsgType.TEXT:
                        # Some events come as text JSON
                        try:
                            event_data = json.loads(msg.data)
                            logger.debug(f"UniFi WS: Text event: {event_data}")
                        except json.JSONDecodeError:
                            pass

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.warning(f"UniFi WS: Error: {self._ws.exception()}")
                        break

                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        logger.info("UniFi WS: Connection closed")
                        break

                # Connection ended
                self._ws_connected = False

            except asyncio.CancelledError:
                logger.info("UniFi WS: Event loop cancelled")
                break
            except aiohttp.ClientError as e:
                logger.warning(f"UniFi WS: Client error: {e}")
                self._ws_connected = False
            except Exception as e:
                logger.error(f"UniFi WS: Unexpected error: {e}")
                self._ws_connected = False

            # Clean up
            if self._ws and not self._ws.closed:
                await self._ws.close()
            self._ws = None

            # Wait before reconnecting
            if self._running:
                await asyncio.sleep(self._ws_reconnect_delay)
                self._ws_reconnect_delay = min(
                    self._ws_reconnect_delay * 2, self._ws_max_reconnect_delay
                )

        logger.info("UniFi WS: Event loop stopped")

    async def start_websocket_events(self) -> bool:
        """Start WebSocket real-time event stream.

        Returns:
            True if WebSocket started successfully
        """
        if not self._initialized:
            logger.warning("UniFi WS: Not initialized")
            return False

        # Cancel any existing WebSocket task
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        # Start WebSocket loop
        self._ws_task = asyncio.create_task(self._ws_loop())
        logger.info("⚡ UniFi WS: Real-time event stream started")
        return True

    async def stop_websocket_events(self) -> None:
        """Stop WebSocket event stream."""
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        self._ws_connected = False

        logger.info("UniFi WS: Stopped")

    @property
    def websocket_connected(self) -> bool:
        """Check if WebSocket is currently connected."""
        return self._ws_connected

    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        self._running = False

        # Cancel WebSocket task
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

        # Cancel refresh task
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None

        # Cancel poll task
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._session:
            await self._session.close()
            self._session = None

        self._initialized = False
        logger.info("UniFi: Disconnected")
