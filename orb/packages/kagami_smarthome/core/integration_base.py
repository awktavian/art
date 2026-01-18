"""Integration Base — Abstract base class for all smart home integrations.

Provides a unified interface for:
- Connection lifecycle (connect, disconnect, is_connected)
- Health monitoring (health_check, HealthStatus)
- Credential management (load_credentials)
- Error handling patterns

All vendor integrations SHOULD inherit from IntegrationBase to ensure
consistent behavior across the system. This enables:
- Unified health monitoring via IntegrationManager
- Consistent reconnection logic
- Standardized credential loading from Keychain
- Common error handling patterns

Usage:
    class MyIntegration(IntegrationBase):
        integration_name = "my_integration"
        credential_keys = [
            ("my_integration_host", "host"),
            ("my_integration_token", "token"),
        ]

        async def connect(self) -> bool:
            # Load credentials automatically
            await self.load_credentials()
            # Implementation...
            return True

        async def disconnect(self) -> None:
            # Cleanup...
            pass

Created: January 12, 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from kagami_smarthome.types import SmartHomeConfig

logger = logging.getLogger(__name__)


class HealthLevel(Enum):
    """Health status levels for integrations."""

    HEALTHY = "healthy"  # All systems operational
    DEGRADED = "degraded"  # Partially operational, some features unavailable
    UNHEALTHY = "unhealthy"  # Not operational, needs attention
    UNKNOWN = "unknown"  # Status cannot be determined


@dataclass
class HealthStatus:
    """Health check result for an integration.

    Provides detailed health information including:
    - Overall health level
    - Whether the integration is reachable
    - Latency metrics
    - Error details if unhealthy
    - Last successful operation timestamp
    - Custom metadata for integration-specific info

    Usage:
        status = await integration.health_check()
        if status.level == HealthLevel.HEALTHY:
            print(f"All good! Latency: {status.latency_ms}ms")
        elif status.level == HealthLevel.DEGRADED:
            print(f"Partially working: {status.message}")
        else:
            print(f"Down: {status.error}")
    """

    level: HealthLevel
    reachable: bool = True
    latency_ms: float | None = None
    message: str = ""
    error: str | None = None
    last_success: datetime | None = None
    checked_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Check if the integration is fully healthy."""
        return self.level == HealthLevel.HEALTHY

    @property
    def is_operational(self) -> bool:
        """Check if the integration is at least partially operational."""
        return self.level in (HealthLevel.HEALTHY, HealthLevel.DEGRADED)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "level": self.level.value,
            "reachable": self.reachable,
            "latency_ms": self.latency_ms,
            "message": self.message,
            "error": self.error,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "checked_at": self.checked_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def healthy(
        cls,
        message: str = "All systems operational",
        latency_ms: float | None = None,
        **metadata: Any,
    ) -> HealthStatus:
        """Create a healthy status."""
        return cls(
            level=HealthLevel.HEALTHY,
            reachable=True,
            latency_ms=latency_ms,
            message=message,
            last_success=datetime.now(),
            metadata=metadata,
        )

    @classmethod
    def degraded(
        cls,
        message: str,
        latency_ms: float | None = None,
        **metadata: Any,
    ) -> HealthStatus:
        """Create a degraded status."""
        return cls(
            level=HealthLevel.DEGRADED,
            reachable=True,
            latency_ms=latency_ms,
            message=message,
            metadata=metadata,
        )

    @classmethod
    def unhealthy(
        cls,
        error: str,
        reachable: bool = False,
        **metadata: Any,
    ) -> HealthStatus:
        """Create an unhealthy status."""
        return cls(
            level=HealthLevel.UNHEALTHY,
            reachable=reachable,
            error=error,
            message=f"Integration unhealthy: {error}",
            metadata=metadata,
        )

    @classmethod
    def unknown(cls, message: str = "Status unknown") -> HealthStatus:
        """Create an unknown status."""
        return cls(
            level=HealthLevel.UNKNOWN,
            reachable=False,
            message=message,
        )


class IntegrationBase(ABC):
    """Abstract base class for all smart home integrations.

    Provides common functionality for:
    - Connection lifecycle management
    - Credential loading from Keychain
    - Health monitoring
    - Error tracking

    Subclasses MUST implement:
    - connect() -> bool
    - disconnect() -> None
    - is_connected property (or use default implementation)

    Subclasses SHOULD implement:
    - health_check() -> HealthStatus (default provided)

    Subclasses MUST define:
    - integration_name: str - Human-readable name for logging
    - credential_keys: list[tuple[str, str]] - Keychain keys to load

    Example:
        class TeslaIntegration(IntegrationBase):
            integration_name = "Tesla"
            credential_keys = [
                ("tesla_access_token", "access_token"),
                ("tesla_refresh_token", "refresh_token"),
            ]

            def __init__(self, config: SmartHomeConfig):
                super().__init__(config)
                self._client = None

            async def connect(self) -> bool:
                await self.load_credentials()
                if not self._access_token:
                    return False
                self._client = TeslaClient(self._access_token)
                self._connected = True
                return True

            async def disconnect(self) -> None:
                if self._client:
                    await self._client.close()
                self._connected = False
    """

    # Subclasses MUST define these
    integration_name: ClassVar[str] = "base"
    credential_keys: ClassVar[list[tuple[str, str]]] = []

    def __init__(self, config: SmartHomeConfig) -> None:
        """Initialize the integration.

        Args:
            config: SmartHomeConfig instance with credentials and settings
        """
        self.config = config
        self._connected: bool = False
        self._initialized: bool = False

        # Connection tracking
        self._last_connect_attempt: float = 0
        self._last_successful_operation: float = 0
        self._consecutive_failures: int = 0
        self._last_error: str | None = None

        # Loaded credentials (populated by load_credentials)
        self._credentials: dict[str, str | None] = {}

    @property
    def is_connected(self) -> bool:
        """Check if the integration is currently connected.

        Default implementation uses _connected flag.
        Subclasses may override for more sophisticated checks.
        """
        return self._connected

    @property
    def is_initialized(self) -> bool:
        """Check if the integration has been initialized.

        Initialized means connect() was called successfully at least once.
        """
        return self._initialized

    @property
    def last_error(self) -> str | None:
        """Get the last error message, if any."""
        return self._last_error

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the integration.

        Implementations should:
        1. Call await self.load_credentials() to load credentials
        2. Establish connection to the service
        3. Set self._connected = True on success
        4. Set self._initialized = True on first success

        Returns:
            True if connection succeeded, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the integration.

        Implementations should:
        1. Gracefully close any open connections
        2. Cancel any background tasks
        3. Set self._connected = False
        4. Clean up resources
        """
        pass

    async def reconnect(self) -> bool:
        """Reconnect to the integration.

        Default implementation disconnects then connects.
        Subclasses may override for optimized reconnection.

        Returns:
            True if reconnection succeeded
        """
        try:
            await self.disconnect()
        except Exception as e:
            logger.warning(f"{self.integration_name}: Error during disconnect for reconnect: {e}")

        return await self.connect()

    async def health_check(self) -> HealthStatus:
        """Perform a health check on the integration.

        Default implementation checks is_connected and tracks errors.
        Subclasses SHOULD override for more sophisticated health checks
        (e.g., ping the service, check token validity).

        Returns:
            HealthStatus with current health information
        """
        if not self._initialized:
            return HealthStatus.unknown(f"{self.integration_name} not initialized")

        if not self.is_connected:
            return HealthStatus.unhealthy(
                f"{self.integration_name} not connected",
                reachable=False,
                consecutive_failures=self._consecutive_failures,
            )

        # Default: assume healthy if connected
        return HealthStatus.healthy(
            f"{self.integration_name} connected",
            consecutive_failures=self._consecutive_failures,
            last_operation=self._last_successful_operation,
        )

    async def load_credentials(self) -> None:
        """Load credentials from Keychain into config.

        Uses the credential_keys class variable to map Keychain keys
        to config attributes. Credentials are also stored in self._credentials
        for direct access.

        This is the canonical way for integrations to load credentials.
        Call this at the start of connect().

        Example credential_keys:
            credential_keys = [
                ("tesla_access_token", "access_token"),  # keychain_key -> attr_name
                ("tesla_refresh_token", "refresh_token"),
            ]
        """
        if not self.credential_keys:
            return

        try:
            from kagami_smarthome.secrets import load_integration_credentials

            load_integration_credentials(
                self.integration_name,
                self.config,
                self.credential_keys,
            )

            # Also store in _credentials for direct access
            from kagami_smarthome.secrets import secrets

            for keychain_key, attr_name in self.credential_keys:
                value = secrets.get(keychain_key)
                self._credentials[attr_name] = value

            logger.debug(f"{self.integration_name}: Loaded {len(self.credential_keys)} credentials")

        except ImportError:
            logger.warning(f"{self.integration_name}: Could not import secrets module")
        except Exception as e:
            logger.warning(f"{self.integration_name}: Error loading credentials: {e}")

    def get_credential(self, key: str) -> str | None:
        """Get a loaded credential by attribute name.

        Args:
            key: The attribute name (second element of credential_keys tuple)

        Returns:
            The credential value or None
        """
        return self._credentials.get(key)

    def has_credentials(self, *required_keys: str) -> bool:
        """Check if required credentials are available.

        Args:
            *required_keys: Attribute names to check (from credential_keys)

        Returns:
            True if all required credentials are present and non-empty
        """
        for key in required_keys:
            if not self._credentials.get(key):
                return False
        return True

    def _record_success(self) -> None:
        """Record a successful operation. Call after successful API calls."""
        self._last_successful_operation = time.time()
        self._consecutive_failures = 0
        self._last_error = None

    def _record_failure(self, error: str) -> None:
        """Record a failed operation. Call after failed API calls.

        Args:
            error: Description of the error
        """
        self._consecutive_failures += 1
        self._last_error = error

    async def ensure_connected(self) -> bool:
        """Ensure the integration is connected, reconnecting if needed.

        Returns:
            True if connected (or successfully reconnected)
        """
        if self.is_connected:
            return True

        logger.info(f"{self.integration_name}: Not connected, attempting reconnect...")
        return await self.reconnect()

    def __repr__(self) -> str:
        """String representation for debugging."""
        status = "connected" if self.is_connected else "disconnected"
        return f"<{self.__class__.__name__} ({self.integration_name}): {status}>"


class PollingIntegrationBase(IntegrationBase):
    """Base class for integrations that use polling for state updates.

    Extends IntegrationBase with:
    - Configurable polling interval
    - Background polling task management
    - State update callback support

    Subclasses should implement:
    - _poll_once() - Called each polling cycle
    """

    # Default polling interval in seconds
    default_poll_interval: ClassVar[float] = 60.0

    def __init__(self, config: SmartHomeConfig) -> None:
        """Initialize polling integration.

        Args:
            config: SmartHomeConfig instance
        """
        super().__init__(config)
        self._poll_task: asyncio.Task[None] | None = None
        self._poll_interval: float = self.default_poll_interval
        self._polling: bool = False

    @property
    def is_polling(self) -> bool:
        """Check if polling is active."""
        return self._polling and self._poll_task is not None

    async def start_polling(self, interval: float | None = None) -> None:
        """Start the background polling task.

        Args:
            interval: Optional polling interval override
        """
        if self._poll_task is not None:
            return  # Already polling

        if interval is not None:
            self._poll_interval = interval

        self._polling = True
        self._poll_task = asyncio.create_task(
            self._poll_loop(),
            name=f"{self.integration_name}_poll",
        )
        logger.debug(f"{self.integration_name}: Started polling (interval={self._poll_interval}s)")

    async def stop_polling(self) -> None:
        """Stop the background polling task."""
        self._polling = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        logger.debug(f"{self.integration_name}: Stopped polling")

    async def _poll_loop(self) -> None:
        """Background polling loop. Calls _poll_once() each cycle."""
        while self._polling:
            try:
                await self._poll_once()
                self._record_success()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._record_failure(str(e))
                logger.warning(f"{self.integration_name}: Poll error: {e}")

            await asyncio.sleep(self._poll_interval)

    async def _poll_once(self) -> None:
        """Perform a single poll cycle.

        Subclasses should override this to fetch and update state.
        """
        pass  # Default implementation does nothing

    async def disconnect(self) -> None:
        """Disconnect and stop polling."""
        await self.stop_polling()
        self._connected = False


class WebSocketIntegrationBase(IntegrationBase):
    """Base class for integrations that use WebSocket for real-time updates.

    Extends IntegrationBase with:
    - WebSocket connection management
    - Auto-reconnection with exponential backoff
    - Message handling infrastructure

    Subclasses should implement:
    - _ws_connect() -> WebSocket connection
    - _handle_message(data) - Called for each received message
    """

    # Reconnection settings
    initial_reconnect_delay: ClassVar[float] = 1.0
    max_reconnect_delay: ClassVar[float] = 60.0
    reconnect_backoff_multiplier: ClassVar[float] = 2.0

    def __init__(self, config: SmartHomeConfig) -> None:
        """Initialize WebSocket integration.

        Args:
            config: SmartHomeConfig instance
        """
        super().__init__(config)
        self._ws: Any = None  # WebSocket connection
        self._ws_task: asyncio.Task[None] | None = None
        self._ws_connected: bool = False
        self._reconnect_delay: float = self.initial_reconnect_delay

    @property
    def websocket_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws_connected

    async def start_websocket(self) -> bool:
        """Start the WebSocket connection and listener.

        Returns:
            True if WebSocket started successfully
        """
        if self._ws_task is not None:
            return self._ws_connected

        self._ws_task = asyncio.create_task(
            self._ws_loop(),
            name=f"{self.integration_name}_ws",
        )
        logger.debug(f"{self.integration_name}: Started WebSocket listener")

        # Wait briefly to see if connection succeeds
        await asyncio.sleep(0.5)
        return self._ws_connected

    async def stop_websocket(self) -> None:
        """Stop the WebSocket connection."""
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        self._ws_connected = False
        logger.debug(f"{self.integration_name}: Stopped WebSocket")

    async def _ws_loop(self) -> None:
        """Main WebSocket event loop with auto-reconnection."""
        while True:
            try:
                # Connect
                self._ws = await self._ws_connect()

                if not self._ws:
                    raise ConnectionError("WebSocket connection failed")

                self._ws_connected = True
                self._reconnect_delay = self.initial_reconnect_delay
                logger.info(f"{self.integration_name}: WebSocket connected")

                # Read messages
                await self._ws_read_loop()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._ws_connected = False
                logger.warning(f"{self.integration_name}: WebSocket error: {e}")

                # Exponential backoff
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * self.reconnect_backoff_multiplier,
                    self.max_reconnect_delay,
                )

        self._ws_connected = False

    async def _ws_connect(self) -> Any:
        """Create WebSocket connection.

        Subclasses MUST override this to establish the WebSocket connection.

        Returns:
            WebSocket connection object
        """
        raise NotImplementedError("Subclasses must implement _ws_connect()")

    async def _ws_read_loop(self) -> None:
        """Read messages from WebSocket.

        Default implementation assumes self._ws is an aiohttp WebSocket.
        Subclasses may override for different WebSocket libraries.
        """
        import aiohttp

        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await self._handle_message(msg.data)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                await self._handle_message(msg.data)
            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                break

    async def _handle_message(self, data: Any) -> None:
        """Handle a received WebSocket message.

        Subclasses should override this to process messages.

        Args:
            data: The message data (text or bytes)
        """
        pass  # Default implementation does nothing

    async def disconnect(self) -> None:
        """Disconnect and stop WebSocket."""
        await self.stop_websocket()
        self._connected = False


__all__ = [
    "HealthLevel",
    "HealthStatus",
    "IntegrationBase",
    "PollingIntegrationBase",
    "WebSocketIntegrationBase",
]
