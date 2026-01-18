"""Tunnel Client for Kagami Apps.

The tunnel client connects to the hub's tunnel server when outside the
local network. Features:

- Automatic network detection (local vs remote)
- Noise XX handshake for mutual authentication
- ChaCha20-Poly1305 encrypted transport
- Auto-reconnection with exponential backoff
- Seamless transition between local and tunnel modes

Connection Flow:
```
1. Try mDNS discovery for local hub
2. If local: connect directly
3. If remote: connect via tunnel server
4. Perform Noise handshake
5. Verify hub identity
6. Establish encrypted transport
```

Colony: Crystal (D5) - Security verification
h(x) >= 0. Always.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from kagami_tunnel.noise import (
    DecryptionError,
    HandshakeError,
    NoiseError,
    NoiseHandshake,
    NoiseKeypair,
    NoiseTransport,
)
from kagami_tunnel.server import (
    HEADER_SIZE,
    KEEPALIVE_INTERVAL,
    KEEPALIVE_TIMEOUT,
    FrameType,
    decode_frame_header,
    encode_frame,
)

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_PORT = 9443
CONNECT_TIMEOUT = 30.0  # seconds
HANDSHAKE_TIMEOUT = 30.0  # seconds

# Reconnection backoff
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 60.0  # seconds
BACKOFF_MULTIPLIER = 2.0


class ConnectionMode(Enum):
    """How the client is connected."""

    DISCONNECTED = auto()
    LOCAL = auto()  # Direct LAN connection
    TUNNEL = auto()  # Via tunnel server


class ClientState(Enum):
    """Tunnel client state."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    HANDSHAKING = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    CLOSING = auto()


# =============================================================================
# Tunnel Client
# =============================================================================


@dataclass
class TunnelClient:
    """Tunnel client for connecting to Kagami hub.

    Provides encrypted tunnel connection to the hub when outside the
    local network. Automatically detects whether local or tunnel
    connection is needed.

    Example:
        # Create client with keypair
        client = TunnelClient.create()

        # Set server public key for verification
        client.server_public_key = hub_public_key

        # Set callbacks
        client.on_data = handle_data
        client.on_connect = handle_connect
        client.on_disconnect = handle_disconnect

        # Connect
        await client.connect(
            tunnel_host="hub.example.com",
            tunnel_port=9443,
        )

        # Send data
        await client.send(b"Hello, hub!")

        # Disconnect
        await client.disconnect()
    """

    # Client identity
    static_keypair: NoiseKeypair

    # Server verification
    server_public_key: bytes | None = None

    # Connection settings
    auto_reconnect: bool = True
    reconnect_attempts: int = 0
    max_reconnect_attempts: int = 10

    # Callbacks
    on_data: Callable[[bytes], Awaitable[None]] | None = None
    on_connect: Callable[[], Awaitable[None]] | None = None
    on_disconnect: Callable[[], Awaitable[None]] | None = None
    on_error: Callable[[Exception], Awaitable[None]] | None = None

    # State
    state: ClientState = ClientState.DISCONNECTED
    mode: ConnectionMode = ConnectionMode.DISCONNECTED

    # Connection details
    _host: str = ""
    _port: int = DEFAULT_PORT
    _reader: asyncio.StreamReader | None = None
    _writer: asyncio.StreamWriter | None = None
    _transport: NoiseTransport | None = None

    # Timing
    connected_at: float = 0.0
    last_activity: float = 0.0

    # Tasks
    _read_task: asyncio.Task | None = None
    _keepalive_task: asyncio.Task | None = None
    _reconnect_task: asyncio.Task | None = None

    # Backoff
    _current_backoff: float = INITIAL_BACKOFF

    @classmethod
    def create(cls, private_key_bytes: bytes | None = None) -> TunnelClient:
        """Create a tunnel client.

        Args:
            private_key_bytes: Optional X25519 private key. If not provided,
                               a new keypair is generated.

        Returns:
            TunnelClient instance.
        """
        if private_key_bytes:
            keypair = NoiseKeypair.from_private_bytes(private_key_bytes)
        else:
            keypair = NoiseKeypair.generate()

        return cls(static_keypair=keypair)

    def get_public_key(self) -> bytes:
        """Get client's public key for server trust configuration."""
        return self.static_keypair.public_key

    async def connect(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: float = CONNECT_TIMEOUT,
    ) -> bool:
        """Connect to tunnel server.

        Args:
            host: Server hostname or IP.
            port: Server port.
            timeout: Connection timeout.

        Returns:
            True if connection succeeded.
        """
        if self.state not in (ClientState.DISCONNECTED, ClientState.RECONNECTING):
            logger.warning(f"Cannot connect in state: {self.state}")
            return False

        self.state = ClientState.CONNECTING
        self._host = host
        self._port = port

        try:
            # Establish TCP connection
            async with asyncio.timeout(timeout):
                self._reader, self._writer = await asyncio.open_connection(host, port)

            self.state = ClientState.HANDSHAKING

            # Perform Noise handshake
            if not await self._perform_handshake():
                raise HandshakeError("Handshake failed")

            # Connection established
            self.state = ClientState.CONNECTED
            self.mode = ConnectionMode.TUNNEL
            self.connected_at = time.time()
            self.last_activity = time.time()
            self.reconnect_attempts = 0
            self._current_backoff = INITIAL_BACKOFF

            # Start background tasks
            self._read_task = asyncio.create_task(self._read_loop())
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

            logger.info(f"Connected to tunnel server {host}:{port}")

            # Notify callback
            if self.on_connect:
                try:
                    await self.on_connect()
                except Exception as e:
                    logger.error(f"on_connect callback error: {e}")

            return True

        except TimeoutError:
            logger.warning(f"Connection timed out: {host}:{port}")
            await self._handle_connection_failure()
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            await self._handle_connection_failure()
            return False

    async def disconnect(self) -> None:
        """Disconnect from tunnel server."""
        if self.state == ClientState.DISCONNECTED:
            return

        self.state = ClientState.CLOSING
        self.auto_reconnect = False  # Prevent reconnection

        # Cancel tasks
        if self._read_task:
            self._read_task.cancel()
        if self._keepalive_task:
            self._keepalive_task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()

        # Send close frame
        try:
            if self._writer and self._transport:
                await self._send_frame(FrameType.CLOSE, b"")
        except Exception:
            pass

        # Close socket
        await self._close_socket()

        self.state = ClientState.DISCONNECTED
        self.mode = ConnectionMode.DISCONNECTED
        logger.info("Disconnected from tunnel server")

        # Notify callback
        if self.on_disconnect:
            try:
                await self.on_disconnect()
            except Exception as e:
                logger.error(f"on_disconnect callback error: {e}")

    async def send(self, data: bytes) -> None:
        """Send data through the tunnel.

        Args:
            data: Data to send (will be encrypted).

        Raises:
            NoiseError: If not connected.
        """
        if self.state != ClientState.CONNECTED:
            raise NoiseError(f"Not connected: {self.state}")

        await self._send_frame(FrameType.DATA, data)

    def is_connected(self) -> bool:
        """Check if connected."""
        return self.state == ClientState.CONNECTED

    async def _perform_handshake(self) -> bool:
        """Perform Noise XX handshake as initiator."""
        try:
            # Create initiator handshake state
            handshake = NoiseHandshake.initiator(self.static_keypair)

            # Send first message (-> e)
            msg1 = handshake.write_message()
            await self._send_handshake_message(msg1)

            # Receive response (<- e, ee, s, es)
            msg2 = await self._recv_handshake_message()
            handshake.read_message(msg2)

            # Send final message (-> s, se)
            msg3 = handshake.write_message()
            await self._send_handshake_message(msg3)

            # Verify handshake complete
            if not handshake.is_complete():
                raise HandshakeError("Handshake did not complete")

            # Verify server identity
            remote_key = handshake.get_remote_static_key()
            if self.server_public_key and remote_key != self.server_public_key:
                raise HandshakeError(
                    f"Server key mismatch: expected {self.server_public_key[:8].hex()}, "
                    f"got {remote_key[:8].hex() if remote_key else 'none'}"
                )

            # Create transport
            self._transport = NoiseTransport.from_handshake(handshake)
            logger.debug("Handshake completed successfully")
            return True

        except TimeoutError:
            logger.warning("Handshake timed out")
            return False
        except HandshakeError as e:
            logger.warning(f"Handshake failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Handshake error: {e}")
            return False

    async def _send_handshake_message(self, data: bytes) -> None:
        """Send handshake message."""
        frame = encode_frame(FrameType.HANDSHAKE, data)
        self._writer.write(frame)
        await self._writer.drain()

    async def _recv_handshake_message(self) -> bytes:
        """Receive handshake message with timeout."""
        async with asyncio.timeout(HANDSHAKE_TIMEOUT):
            # Read header
            header = await self._reader.readexactly(HEADER_SIZE)
            frame_type, length = decode_frame_header(header)

            if frame_type != FrameType.HANDSHAKE:
                raise HandshakeError(f"Expected HANDSHAKE, got {frame_type}")

            # Read payload
            payload = await self._reader.readexactly(length)
            return payload

    async def _send_frame(self, frame_type: FrameType, data: bytes) -> None:
        """Send encrypted frame."""
        if not self._writer:
            raise NoiseError("Not connected")

        if self._transport and frame_type == FrameType.DATA:
            # Encrypt data frames
            encrypted = self._transport.encrypt(data)
            frame = encode_frame(frame_type, encrypted)
        else:
            frame = encode_frame(frame_type, data)

        self._writer.write(frame)
        await self._writer.drain()
        self.last_activity = time.time()

    async def _read_loop(self) -> None:
        """Background task to read incoming frames."""
        try:
            while self.state == ClientState.CONNECTED:
                # Read header
                header = await self._reader.readexactly(HEADER_SIZE)
                frame_type, length = decode_frame_header(header)

                # Read payload
                payload = await self._reader.readexactly(length)
                self.last_activity = time.time()

                # Handle frame
                await self._handle_frame(frame_type, payload)

        except asyncio.CancelledError:
            pass
        except asyncio.IncompleteReadError:
            logger.info("Server disconnected")
        except DecryptionError as e:
            logger.warning(f"Decryption failed: {e}")
        except Exception as e:
            logger.error(f"Read error: {e}")
        finally:
            await self._handle_connection_failure()

    async def _handle_frame(self, frame_type: FrameType, payload: bytes) -> None:
        """Handle received frame."""
        if frame_type == FrameType.DATA:
            # Decrypt and process data
            if self._transport:
                plaintext = self._transport.decrypt(payload)
                if self.on_data:
                    try:
                        await self.on_data(plaintext)
                    except Exception as e:
                        logger.error(f"on_data callback error: {e}")

        elif frame_type == FrameType.KEEPALIVE:
            # Keepalive response received
            pass

        elif frame_type == FrameType.CLOSE:
            logger.info("Server requested close")
            await self._handle_connection_failure()

        elif frame_type == FrameType.ERROR:
            error_msg = payload.decode("utf-8", errors="replace")
            logger.warning(f"Server error: {error_msg}")
            if self.on_error:
                try:
                    await self.on_error(Exception(error_msg))
                except Exception as e:
                    logger.error(f"on_error callback error: {e}")

    async def _keepalive_loop(self) -> None:
        """Background task to send keepalives and check timeout."""
        try:
            while self.state == ClientState.CONNECTED:
                await asyncio.sleep(KEEPALIVE_INTERVAL)

                # Check for timeout
                idle_time = time.time() - self.last_activity
                if idle_time > KEEPALIVE_TIMEOUT:
                    logger.warning("Connection timed out")
                    await self._handle_connection_failure()
                    return

                # Send keepalive
                try:
                    await self._send_frame(FrameType.KEEPALIVE, b"")
                except Exception:
                    pass

        except asyncio.CancelledError:
            pass

    async def _handle_connection_failure(self) -> None:
        """Handle connection failure and potentially reconnect."""
        if self.state in (ClientState.DISCONNECTED, ClientState.CLOSING):
            return

        was_connected = self.state == ClientState.CONNECTED
        self.state = ClientState.DISCONNECTED
        self.mode = ConnectionMode.DISCONNECTED

        # Close socket
        await self._close_socket()

        # Notify callback if was connected
        if was_connected and self.on_disconnect:
            try:
                await self.on_disconnect()
            except Exception as e:
                logger.error(f"on_disconnect callback error: {e}")

        # Attempt reconnection if enabled
        if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
            self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        self.state = ClientState.RECONNECTING
        self.reconnect_attempts += 1

        logger.info(
            f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} "
            f"in {self._current_backoff:.1f}s"
        )

        await asyncio.sleep(self._current_backoff)

        # Update backoff for next attempt
        self._current_backoff = min(
            self._current_backoff * BACKOFF_MULTIPLIER,
            MAX_BACKOFF,
        )

        # Attempt reconnection
        self.state = ClientState.DISCONNECTED
        success = await self.connect(self._host, self._port)

        if not success and self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            if self.on_error:
                try:
                    await self.on_error(Exception("Max reconnection attempts reached"))
                except Exception as e:
                    logger.error(f"on_error callback error: {e}")

    async def _close_socket(self) -> None:
        """Close the TCP socket."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
            self._transport = None


# =============================================================================
# Auto-Connect Client
# =============================================================================


@dataclass
class AutoTunnelClient:
    """Tunnel client with automatic local/remote detection.

    Attempts local mDNS discovery first, falls back to tunnel if
    local connection fails.

    Example:
        client = AutoTunnelClient.create()
        client.tunnel_host = "hub.example.com"
        client.tunnel_port = 9443

        # Auto-detect and connect
        await client.connect()

        if client.mode == ConnectionMode.LOCAL:
            print("Connected locally")
        else:
            print("Connected via tunnel")
    """

    # Base client
    client: TunnelClient

    # Local discovery settings
    local_host: str | None = None  # Set by mDNS discovery
    local_port: int = 8080

    # Tunnel settings
    tunnel_host: str = ""
    tunnel_port: int = DEFAULT_PORT

    # Server verification
    server_public_key: bytes | None = None

    # Callbacks (proxied to client)
    on_data: Callable[[bytes], Awaitable[None]] | None = None
    on_connect: Callable[[], Awaitable[None]] | None = None
    on_disconnect: Callable[[], Awaitable[None]] | None = None

    @classmethod
    def create(cls, private_key_bytes: bytes | None = None) -> AutoTunnelClient:
        """Create an auto-connect client."""
        client = TunnelClient.create(private_key_bytes)
        return cls(client=client)

    @property
    def mode(self) -> ConnectionMode:
        """Get current connection mode."""
        return self.client.mode

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.client.is_connected()

    def get_public_key(self) -> bytes:
        """Get client's public key."""
        return self.client.get_public_key()

    async def connect(self, prefer_local: bool = True) -> bool:
        """Connect with automatic mode selection.

        Args:
            prefer_local: Try local connection first.

        Returns:
            True if connection succeeded.
        """
        # Set up callbacks
        self.client.on_data = self.on_data
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.server_public_key = self.server_public_key

        if prefer_local and self.local_host:
            # Try local connection first
            logger.info(f"Attempting local connection to {self.local_host}:{self.local_port}")
            try:
                if await self.client.connect(self.local_host, self.local_port, timeout=5.0):
                    self.client.mode = ConnectionMode.LOCAL
                    return True
            except Exception as e:
                logger.debug(f"Local connection failed: {e}")

        # Fall back to tunnel
        if self.tunnel_host:
            logger.info(f"Attempting tunnel connection to {self.tunnel_host}:{self.tunnel_port}")
            return await self.client.connect(self.tunnel_host, self.tunnel_port)

        logger.error("No connection target configured")
        return False

    async def disconnect(self) -> None:
        """Disconnect from hub."""
        await self.client.disconnect()

    async def send(self, data: bytes) -> None:
        """Send data to hub."""
        await self.client.send(data)


# =============================================================================
# Factory Functions
# =============================================================================


_tunnel_client: TunnelClient | None = None


async def get_tunnel_client(
    private_key_bytes: bytes | None = None,
) -> TunnelClient:
    """Get or create the singleton tunnel client.

    Args:
        private_key_bytes: Optional X25519 private key.

    Returns:
        TunnelClient instance.
    """
    global _tunnel_client

    if _tunnel_client is None:
        _tunnel_client = TunnelClient.create(private_key_bytes)

    return _tunnel_client


async def shutdown_tunnel_client() -> None:
    """Shutdown the singleton tunnel client."""
    global _tunnel_client

    if _tunnel_client:
        await _tunnel_client.disconnect()
        _tunnel_client = None


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "AutoTunnelClient",
    "ClientState",
    "ConnectionMode",
    "TunnelClient",
    "get_tunnel_client",
    "shutdown_tunnel_client",
]
