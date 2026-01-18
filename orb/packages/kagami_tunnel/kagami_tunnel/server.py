"""Tunnel Server for Kagami Hub.

The tunnel server runs on the hub and accepts incoming tunnel connections
from remote clients. Features:

- Noise XX handshake for mutual authentication
- Ed25519 peer verification (reuses mesh auth)
- ChaCha20-Poly1305 encrypted transport
- Multiple concurrent client connections
- Connection keepalive and timeout handling
- Peer authorization based on trusted keys

Architecture:
```
                    INTERNET
                       |
    +------------------+------------------+
    |            TUNNEL SERVER            |
    |  (runs on hub, accepts tunnels)     |
    +------------------+------------------+
           |          |          |
    +------+   +------+   +------+
    |Client|   |Client|   |Client|
    | iOS  |   |Watch |   |Desk  |
    +------+   +------+   +------+
```

Colony: Crystal (D5) - Security verification
h(x) >= 0. Always.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
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

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_PORT = 9443
HANDSHAKE_TIMEOUT = 30.0  # seconds
KEEPALIVE_INTERVAL = 30.0  # seconds
KEEPALIVE_TIMEOUT = 90.0  # seconds
MAX_FRAME_SIZE = 65535
HEADER_SIZE = 4  # 2 bytes type + 2 bytes length


class FrameType(Enum):
    """Tunnel frame types."""

    HANDSHAKE = 0x01
    DATA = 0x02
    KEEPALIVE = 0x03
    CLOSE = 0x04
    ERROR = 0x05


class ConnectionState(Enum):
    """Tunnel connection state."""

    HANDSHAKING = auto()
    ESTABLISHED = auto()
    CLOSING = auto()
    CLOSED = auto()


class ServerState(Enum):
    """Tunnel server state."""

    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()


# =============================================================================
# Frame Protocol
# =============================================================================


def encode_frame(frame_type: FrameType, payload: bytes) -> bytes:
    """Encode a frame with type and length prefix.

    Format: [type: 2 bytes][length: 2 bytes][payload]
    """
    if len(payload) > MAX_FRAME_SIZE:
        raise ValueError(f"Payload too large: {len(payload)}")

    return struct.pack(">HH", frame_type.value, len(payload)) + payload


def decode_frame_header(data: bytes) -> tuple[FrameType, int]:
    """Decode frame header.

    Returns:
        Tuple of (frame_type, payload_length).
    """
    if len(data) < HEADER_SIZE:
        raise ValueError("Header too short")

    type_val, length = struct.unpack(">HH", data[:HEADER_SIZE])

    try:
        frame_type = FrameType(type_val)
    except ValueError:
        raise ValueError(f"Unknown frame type: {type_val}")

    return frame_type, length


# =============================================================================
# Client Connection
# =============================================================================


@dataclass
class TunnelConnection:
    """Represents a connected tunnel client.

    Manages the lifecycle of a single tunnel connection:
    - Noise handshake
    - Encrypted message transport
    - Keepalive handling
    - Clean disconnection
    """

    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    server: TunnelServer

    # Connection identity
    connection_id: str = ""
    remote_public_key: bytes | None = None

    # State
    state: ConnectionState = ConnectionState.HANDSHAKING
    handshake: NoiseHandshake | None = None
    transport: NoiseTransport | None = None

    # Timing
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    # Tasks
    _read_task: asyncio.Task | None = None
    _keepalive_task: asyncio.Task | None = None

    async def start(self) -> bool:
        """Start connection handling.

        Performs handshake and starts read/keepalive tasks.

        Returns:
            True if handshake succeeded.
        """
        try:
            # Perform Noise handshake as responder
            success = await self._perform_handshake()
            if not success:
                return False

            # Verify peer is authorized
            if not self._verify_peer():
                logger.warning(f"Unauthorized peer attempted connection: {self.connection_id}")
                await self.close()
                return False

            # Start background tasks
            self._read_task = asyncio.create_task(self._read_loop())
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

            self.state = ConnectionState.ESTABLISHED
            logger.info(f"Tunnel connection established: {self.connection_id}")
            return True

        except Exception as e:
            logger.error(f"Connection startup failed: {e}")
            await self.close()
            return False

    async def close(self) -> None:
        """Close the connection gracefully."""
        if self.state == ConnectionState.CLOSED:
            return

        self.state = ConnectionState.CLOSING

        # Cancel tasks
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except (asyncio.CancelledError, Exception):
                pass

        # Send close frame if possible
        try:
            if self.transport:
                await self._send_frame(FrameType.CLOSE, b"")
        except Exception:
            pass

        # Close socket
        try:
            self.writer.close()
            await asyncio.wait_for(self.writer.wait_closed(), timeout=1.0)
        except (TimeoutError, asyncio.CancelledError, Exception):
            pass

        self.state = ConnectionState.CLOSED
        logger.info(f"Tunnel connection closed: {self.connection_id}")

    async def send(self, data: bytes) -> None:
        """Send encrypted data to the client.

        Args:
            data: Plaintext data to send.
        """
        if self.state != ConnectionState.ESTABLISHED:
            raise NoiseError("Connection not established")

        await self._send_frame(FrameType.DATA, data)

    async def _perform_handshake(self) -> bool:
        """Perform Noise XX handshake as responder."""
        try:
            # Create responder handshake state
            self.handshake = NoiseHandshake.responder(self.server.static_keypair)

            # Read first message (-> e)
            msg1 = await self._recv_handshake_message()
            self.handshake.read_message(msg1)

            # Write response (<- e, ee, s, es)
            msg2 = self.handshake.write_message()
            await self._send_handshake_message(msg2)

            # Read final message (-> s, se)
            msg3 = await self._recv_handshake_message()
            self.handshake.read_message(msg3)

            # Handshake complete
            if not self.handshake.is_complete():
                raise HandshakeError("Handshake did not complete")

            # Create transport
            self.transport = NoiseTransport.from_handshake(self.handshake)
            self.remote_public_key = self.handshake.get_remote_static_key()

            # Generate connection ID from public key
            if self.remote_public_key:
                self.connection_id = self.remote_public_key[:8].hex()

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

    def _verify_peer(self) -> bool:
        """Verify peer is in trusted keys list."""
        if not self.remote_public_key:
            return False

        # If no trusted keys configured, reject all
        if not self.server.trusted_keys:
            logger.warning("No trusted keys configured - rejecting all connections")
            return False

        return self.remote_public_key in self.server.trusted_keys

    async def _send_handshake_message(self, data: bytes) -> None:
        """Send handshake message."""
        frame = encode_frame(FrameType.HANDSHAKE, data)
        self.writer.write(frame)
        await self.writer.drain()

    async def _recv_handshake_message(self) -> bytes:
        """Receive handshake message with timeout."""
        async with asyncio.timeout(HANDSHAKE_TIMEOUT):
            # Read header
            header = await self.reader.readexactly(HEADER_SIZE)
            frame_type, length = decode_frame_header(header)

            if frame_type != FrameType.HANDSHAKE:
                raise HandshakeError(f"Expected HANDSHAKE, got {frame_type}")

            # Read payload
            payload = await self.reader.readexactly(length)
            return payload

    async def _send_frame(self, frame_type: FrameType, data: bytes) -> None:
        """Send encrypted frame."""
        if self.transport and frame_type == FrameType.DATA:
            # Encrypt data frames
            encrypted = self.transport.encrypt(data)
            frame = encode_frame(frame_type, encrypted)
        else:
            frame = encode_frame(frame_type, data)

        self.writer.write(frame)
        await self.writer.drain()
        self.last_activity = time.time()

    async def _read_loop(self) -> None:
        """Background task to read incoming frames."""
        try:
            while self.state == ConnectionState.ESTABLISHED:
                # Read header
                header = await self.reader.readexactly(HEADER_SIZE)
                frame_type, length = decode_frame_header(header)

                # Read payload
                payload = await self.reader.readexactly(length)
                self.last_activity = time.time()

                # Handle frame
                await self._handle_frame(frame_type, payload)

        except asyncio.CancelledError:
            pass
        except asyncio.IncompleteReadError:
            logger.info(f"Client disconnected: {self.connection_id}")
        except DecryptionError as e:
            logger.warning(f"Decryption failed: {e}")
        except Exception as e:
            logger.error(f"Read error: {e}")
        finally:
            await self.close()

    async def _handle_frame(self, frame_type: FrameType, payload: bytes) -> None:
        """Handle received frame."""
        if frame_type == FrameType.DATA:
            # Decrypt and process data
            if self.transport:
                plaintext = self.transport.decrypt(payload)
                await self._on_data(plaintext)

        elif frame_type == FrameType.KEEPALIVE:
            # Respond to keepalive
            await self._send_frame(FrameType.KEEPALIVE, b"")

        elif frame_type == FrameType.CLOSE:
            logger.info(f"Client requested close: {self.connection_id}")
            await self.close()

        elif frame_type == FrameType.ERROR:
            error_msg = payload.decode("utf-8", errors="replace")
            logger.warning(f"Client error: {error_msg}")

    async def _on_data(self, data: bytes) -> None:
        """Handle received data.

        Override this method or set server.on_data callback.
        """
        if self.server.on_data:
            await self.server.on_data(self, data)

    async def _keepalive_loop(self) -> None:
        """Background task to send keepalives and check timeout."""
        try:
            while self.state == ConnectionState.ESTABLISHED:
                await asyncio.sleep(KEEPALIVE_INTERVAL)

                # Check for timeout
                idle_time = time.time() - self.last_activity
                if idle_time > KEEPALIVE_TIMEOUT:
                    logger.warning(f"Connection timed out: {self.connection_id}")
                    await self.close()
                    return

                # Send keepalive
                try:
                    await self._send_frame(FrameType.KEEPALIVE, b"")
                except Exception:
                    pass

        except asyncio.CancelledError:
            pass


# =============================================================================
# Tunnel Server
# =============================================================================


@dataclass
class TunnelServer:
    """Tunnel server for accepting remote client connections.

    Runs on the Kagami hub and accepts encrypted tunnel connections
    from remote apps (iOS, watchOS, desktop, etc).

    Example:
        # Create server with static keypair
        keypair = NoiseKeypair.generate()
        server = TunnelServer(static_keypair=keypair)

        # Add trusted client keys
        server.trust_peer(client_public_key)

        # Set data callback
        server.on_data = handle_tunnel_data

        # Start server
        await server.start(port=9443)

        # Later: stop
        await server.stop()
    """

    # Server identity
    static_keypair: NoiseKeypair

    # Configuration
    host: str = "0.0.0.0"
    port: int = DEFAULT_PORT
    max_connections: int = 100

    # Trusted peer public keys
    trusted_keys: set[bytes] = field(default_factory=set)

    # Callbacks
    on_data: Callable[[TunnelConnection, bytes], Awaitable[None]] | None = None
    on_connect: Callable[[TunnelConnection], Awaitable[None]] | None = None
    on_disconnect: Callable[[TunnelConnection], Awaitable[None]] | None = None

    # State
    state: ServerState = ServerState.STOPPED
    _server: asyncio.Server | None = None
    _connections: dict[str, TunnelConnection] = field(default_factory=dict)
    _accept_task: asyncio.Task | None = None

    @classmethod
    def create(
        cls,
        private_key_bytes: bytes | None = None,
        port: int = DEFAULT_PORT,
    ) -> TunnelServer:
        """Create a tunnel server.

        Args:
            private_key_bytes: Optional X25519 private key. If not provided,
                               a new keypair is generated.
            port: Port to listen on.

        Returns:
            TunnelServer instance.
        """
        if private_key_bytes:
            keypair = NoiseKeypair.from_private_bytes(private_key_bytes)
        else:
            keypair = NoiseKeypair.generate()

        return cls(static_keypair=keypair, port=port)

    def get_public_key(self) -> bytes:
        """Get server's public key for client configuration."""
        return self.static_keypair.public_key

    def trust_peer(self, public_key: bytes) -> None:
        """Add a trusted peer public key.

        Args:
            public_key: X25519 public key (32 bytes).
        """
        if len(public_key) != 32:
            raise ValueError("Public key must be 32 bytes")

        self.trusted_keys.add(public_key)
        logger.info(f"Added trusted peer: {public_key[:8].hex()}")

    def untrust_peer(self, public_key: bytes) -> None:
        """Remove a trusted peer public key."""
        self.trusted_keys.discard(public_key)
        logger.info(f"Removed trusted peer: {public_key[:8].hex()}")

    async def start(
        self,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """Start the tunnel server.

        Args:
            host: Bind address (default: 0.0.0.0).
            port: Listen port (default: 9443).
        """
        if self.state != ServerState.STOPPED:
            raise RuntimeError(f"Server not stopped: {self.state}")

        self.state = ServerState.STARTING
        self.host = host or self.host
        self.port = port or self.port

        try:
            self._server = await asyncio.start_server(
                self._handle_connection,
                self.host,
                self.port,
            )

            self.state = ServerState.RUNNING
            logger.info(
                f"Tunnel server started on {self.host}:{self.port} "
                f"(pub: {self.static_keypair.public_key[:8].hex()})"
            )

        except Exception as e:
            self.state = ServerState.STOPPED
            raise RuntimeError(f"Failed to start server: {e}") from e

    async def stop(self) -> None:
        """Stop the tunnel server and close all connections."""
        if self.state == ServerState.STOPPED:
            return

        self.state = ServerState.STOPPING

        # Close all connections
        for conn in list(self._connections.values()):
            await conn.close()
        self._connections.clear()

        # Stop server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        self.state = ServerState.STOPPED
        logger.info("Tunnel server stopped")

    async def broadcast(self, data: bytes) -> None:
        """Send data to all connected clients.

        Args:
            data: Data to broadcast.
        """
        for conn in list(self._connections.values()):
            if conn.state == ConnectionState.ESTABLISHED:
                try:
                    await conn.send(data)
                except Exception as e:
                    logger.warning(f"Broadcast failed to {conn.connection_id}: {e}")

    async def send_to(self, connection_id: str, data: bytes) -> bool:
        """Send data to a specific client.

        Args:
            connection_id: Target connection ID.
            data: Data to send.

        Returns:
            True if sent successfully.
        """
        conn = self._connections.get(connection_id)
        if conn and conn.state == ConnectionState.ESTABLISHED:
            try:
                await conn.send(data)
                return True
            except Exception as e:
                logger.warning(f"Send failed to {connection_id}: {e}")
        return False

    def get_connection(self, connection_id: str) -> TunnelConnection | None:
        """Get connection by ID."""
        return self._connections.get(connection_id)

    def list_connections(self) -> list[str]:
        """List all active connection IDs."""
        return [
            cid
            for cid, conn in self._connections.items()
            if conn.state == ConnectionState.ESTABLISHED
        ]

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle new incoming connection."""
        # Check connection limit
        if len(self._connections) >= self.max_connections:
            logger.warning("Connection limit reached, rejecting")
            writer.close()
            return

        # Create connection object
        conn = TunnelConnection(
            reader=reader,
            writer=writer,
            server=self,
        )

        # Perform handshake and start connection
        if await conn.start():
            self._connections[conn.connection_id] = conn

            # Notify callback
            if self.on_connect:
                try:
                    await self.on_connect(conn)
                except Exception as e:
                    logger.error(f"on_connect callback error: {e}")

            # Wait for connection to close
            while conn.state == ConnectionState.ESTABLISHED:
                await asyncio.sleep(1)

            # Remove from connections
            self._connections.pop(conn.connection_id, None)

            # Notify callback
            if self.on_disconnect:
                try:
                    await self.on_disconnect(conn)
                except Exception as e:
                    logger.error(f"on_disconnect callback error: {e}")


# =============================================================================
# Factory Functions
# =============================================================================


_tunnel_server: TunnelServer | None = None


async def get_tunnel_server(
    private_key_bytes: bytes | None = None,
    port: int = DEFAULT_PORT,
) -> TunnelServer:
    """Get or create the singleton tunnel server.

    Args:
        private_key_bytes: Optional X25519 private key.
        port: Listen port.

    Returns:
        TunnelServer instance.
    """
    global _tunnel_server

    if _tunnel_server is None:
        _tunnel_server = TunnelServer.create(
            private_key_bytes=private_key_bytes,
            port=port,
        )

    return _tunnel_server


async def shutdown_tunnel_server() -> None:
    """Shutdown the singleton tunnel server."""
    global _tunnel_server

    if _tunnel_server:
        await _tunnel_server.stop()
        _tunnel_server = None


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "DEFAULT_PORT",
    "ConnectionState",
    "FrameType",
    "ServerState",
    "TunnelConnection",
    "TunnelServer",
    "get_tunnel_server",
    "shutdown_tunnel_server",
]
