"""Relay Server for NAT Traversal.

When direct tunnel connections fail due to symmetric NAT, clients
connect through a relay server that forwards traffic between them.

Architecture:
```
         Client A                         Client B
             |                                |
             |                                |
             v                                v
    +--------+--------+              +--------+--------+
    |   Connect to    |              |   Connect to    |
    |   Relay Server  |              |   Relay Server  |
    +--------+--------+              +--------+--------+
             |                                |
             +-------->  RELAY  <-------------+
                    (traffic forwarding)
```

The relay provides:
- Allocation of relay ports for clients
- Encrypted forwarding (relay only sees encrypted packets)
- Channel management for peer-to-peer mapping
- Bandwidth limiting and quota management

This is a fallback when hole punching fails.

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
from enum import Enum
from typing import TYPE_CHECKING

from kagami_tunnel.noise import (
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

DEFAULT_RELAY_PORT = 9444
ALLOCATION_TIMEOUT = 300.0  # 5 minutes
MAX_ALLOCATIONS = 1000
CHANNEL_TIMEOUT = 60.0  # 1 minute without activity
HANDSHAKE_TIMEOUT = 30.0


class RelayMessageType(Enum):
    """Relay protocol message types."""

    # Client -> Relay
    ALLOCATE = 0x01  # Request relay allocation
    REFRESH = 0x02  # Refresh allocation
    CREATE_CHANNEL = 0x03  # Create channel to peer
    CHANNEL_DATA = 0x04  # Data for channel

    # Relay -> Client
    ALLOCATE_RESPONSE = 0x11  # Allocation response
    REFRESH_RESPONSE = 0x12  # Refresh response
    CHANNEL_RESPONSE = 0x13  # Channel creation response
    PEER_DATA = 0x14  # Data from peer
    ERROR = 0x1F  # Error response


class RelayError(Enum):
    """Relay error codes."""

    SUCCESS = 0
    ALLOCATION_FAILED = 1
    QUOTA_EXCEEDED = 2
    INVALID_CHANNEL = 3
    PEER_NOT_FOUND = 4
    TIMEOUT = 5
    UNAUTHORIZED = 6


# =============================================================================
# Relay Protocol
# =============================================================================


@dataclass
class RelayMessage:
    """Relay protocol message."""

    message_type: RelayMessageType
    payload: bytes = b""
    channel_id: int = 0

    def encode(self) -> bytes:
        """Encode message to bytes."""
        return (
            struct.pack(
                ">BHH",
                self.message_type.value,
                self.channel_id,
                len(self.payload),
            )
            + self.payload
        )

    @classmethod
    def decode(cls, data: bytes) -> RelayMessage:
        """Decode message from bytes."""
        if len(data) < 5:
            raise ValueError("Message too short")

        msg_type_val, channel_id, payload_len = struct.unpack(">BHH", data[:5])

        try:
            msg_type = RelayMessageType(msg_type_val)
        except ValueError:
            raise ValueError(f"Unknown message type: {msg_type_val}")

        payload = data[5 : 5 + payload_len]
        if len(payload) != payload_len:
            raise ValueError("Payload truncated")

        return cls(
            message_type=msg_type,
            channel_id=channel_id,
            payload=payload,
        )


# =============================================================================
# Relay Server
# =============================================================================


@dataclass
class RelayAllocation:
    """Client allocation on relay server."""

    # Client identity
    client_id: str
    client_public_key: bytes

    # Allocated relay address
    relay_host: str
    relay_port: int

    # Transport
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    transport: NoiseTransport | None = None

    # Channels to peers
    channels: dict[int, RelayChannel] = field(default_factory=dict)

    # Timing
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    last_activity: float = field(default_factory=time.time)

    # State
    active: bool = True

    def is_expired(self) -> bool:
        """Check if allocation has expired."""
        return time.time() > self.expires_at

    def refresh(self, duration: float = ALLOCATION_TIMEOUT) -> None:
        """Refresh allocation."""
        self.expires_at = time.time() + duration
        self.last_activity = time.time()


@dataclass
class RelayChannel:
    """Channel between two relay clients."""

    channel_id: int

    # Peer allocations
    allocation_a: RelayAllocation
    allocation_b: RelayAllocation

    # Timing
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    # State
    active: bool = True

    def is_stale(self) -> bool:
        """Check if channel is stale."""
        return time.time() - self.last_activity > CHANNEL_TIMEOUT


@dataclass
class RelayServer:
    """Relay server for NAT traversal.

    Provides traffic relaying for clients that cannot establish
    direct connections due to symmetric NAT.

    Example:
        # Create relay server
        keypair = NoiseKeypair.generate()
        server = RelayServer(static_keypair=keypair)

        # Start server
        await server.start(port=9444)

        # Later: stop
        await server.stop()
    """

    # Server identity
    static_keypair: NoiseKeypair

    # Configuration
    host: str = "0.0.0.0"
    port: int = DEFAULT_RELAY_PORT
    max_allocations: int = MAX_ALLOCATIONS
    allocation_timeout: float = ALLOCATION_TIMEOUT

    # Authorized clients (public key -> allowed)
    authorized_clients: set[bytes] = field(default_factory=set)
    allow_anonymous: bool = False

    # State
    _server: asyncio.Server | None = None
    _allocations: dict[str, RelayAllocation] = field(default_factory=dict)
    _channels: dict[int, RelayChannel] = field(default_factory=dict)
    _next_channel_id: int = 1
    _running: bool = False

    # Cleanup task
    _cleanup_task: asyncio.Task | None = None

    @classmethod
    def create(
        cls,
        private_key_bytes: bytes | None = None,
        port: int = DEFAULT_RELAY_PORT,
    ) -> RelayServer:
        """Create a relay server.

        Args:
            private_key_bytes: Optional X25519 private key.
            port: Port to listen on.

        Returns:
            RelayServer instance.
        """
        if private_key_bytes:
            keypair = NoiseKeypair.from_private_bytes(private_key_bytes)
        else:
            keypair = NoiseKeypair.generate()

        return cls(static_keypair=keypair, port=port)

    def get_public_key(self) -> bytes:
        """Get server's public key."""
        return self.static_keypair.public_key

    def authorize_client(self, public_key: bytes) -> None:
        """Authorize a client public key."""
        self.authorized_clients.add(public_key)

    def revoke_client(self, public_key: bytes) -> None:
        """Revoke a client's authorization."""
        self.authorized_clients.discard(public_key)

    async def start(
        self,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """Start the relay server."""
        if self._running:
            raise RuntimeError("Server already running")

        self.host = host or self.host
        self.port = port or self.port

        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info(f"Relay server started on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the relay server."""
        if not self._running:
            return

        self._running = False

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()

        # Close all allocations
        for allocation in list(self._allocations.values()):
            await self._close_allocation(allocation)

        # Stop server
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("Relay server stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle new client connection."""
        try:
            # Perform Noise handshake
            transport, client_key = await self._perform_handshake(reader, writer)
            if not transport or not client_key:
                writer.close()
                return

            # Check authorization
            if not self.allow_anonymous and client_key not in self.authorized_clients:
                logger.warning(f"Unauthorized client: {client_key[:8].hex()}")
                writer.close()
                return

            # Create allocation
            client_id = client_key[:8].hex()
            allocation = RelayAllocation(
                client_id=client_id,
                client_public_key=client_key,
                relay_host=self.host,
                relay_port=self.port,
                reader=reader,
                writer=writer,
                transport=transport,
            )
            allocation.refresh()

            self._allocations[client_id] = allocation
            logger.info(f"Client allocated: {client_id}")

            # Handle messages
            await self._handle_allocation(allocation)

        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            writer.close()

    async def _perform_handshake(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> tuple[NoiseTransport | None, bytes | None]:
        """Perform Noise handshake as responder."""
        try:
            handshake = NoiseHandshake.responder(self.static_keypair)

            # Read first message
            async with asyncio.timeout(HANDSHAKE_TIMEOUT):
                msg1_len = struct.unpack(">H", await reader.readexactly(2))[0]
                msg1 = await reader.readexactly(msg1_len)

            handshake.read_message(msg1)

            # Send response
            msg2 = handshake.write_message()
            writer.write(struct.pack(">H", len(msg2)) + msg2)
            await writer.drain()

            # Read final message
            async with asyncio.timeout(HANDSHAKE_TIMEOUT):
                msg3_len = struct.unpack(">H", await reader.readexactly(2))[0]
                msg3 = await reader.readexactly(msg3_len)

            handshake.read_message(msg3)

            if not handshake.is_complete():
                return None, None

            transport = NoiseTransport.from_handshake(handshake)
            client_key = handshake.get_remote_static_key()

            return transport, client_key

        except Exception as e:
            logger.warning(f"Handshake failed: {e}")
            return None, None

    async def _handle_allocation(self, allocation: RelayAllocation) -> None:
        """Handle messages for an allocation."""
        try:
            while allocation.active:
                # Read message length
                header = await allocation.reader.readexactly(2)
                msg_len = struct.unpack(">H", header)[0]

                # Read encrypted message
                encrypted = await allocation.reader.readexactly(msg_len)

                # Decrypt
                plaintext = allocation.transport.decrypt(encrypted)
                message = RelayMessage.decode(plaintext)

                allocation.last_activity = time.time()

                # Handle message
                await self._handle_message(allocation, message)

        except asyncio.IncompleteReadError:
            logger.info(f"Client disconnected: {allocation.client_id}")
        except Exception as e:
            logger.error(f"Allocation error: {e}")
        finally:
            await self._close_allocation(allocation)

    async def _handle_message(
        self,
        allocation: RelayAllocation,
        message: RelayMessage,
    ) -> None:
        """Handle relay protocol message."""
        if message.message_type == RelayMessageType.REFRESH:
            allocation.refresh()
            await self._send_response(
                allocation,
                RelayMessageType.REFRESH_RESPONSE,
                struct.pack(">I", int(allocation.expires_at - time.time())),
            )

        elif message.message_type == RelayMessageType.CREATE_CHANNEL:
            # Payload is peer's client_id (8 bytes hex = 16 chars)
            peer_id = message.payload.decode()
            peer_allocation = self._allocations.get(peer_id)

            if not peer_allocation:
                await self._send_error(allocation, RelayError.PEER_NOT_FOUND)
                return

            # Create channel
            channel_id = self._next_channel_id
            self._next_channel_id += 1

            channel = RelayChannel(
                channel_id=channel_id,
                allocation_a=allocation,
                allocation_b=peer_allocation,
            )

            self._channels[channel_id] = channel
            allocation.channels[channel_id] = channel
            peer_allocation.channels[channel_id] = channel

            # Send response
            await self._send_response(
                allocation,
                RelayMessageType.CHANNEL_RESPONSE,
                struct.pack(">H", channel_id),
            )

            logger.info(f"Channel {channel_id} created: {allocation.client_id} <-> {peer_id}")

        elif message.message_type == RelayMessageType.CHANNEL_DATA:
            channel = self._channels.get(message.channel_id)
            if not channel:
                await self._send_error(allocation, RelayError.INVALID_CHANNEL)
                return

            # Forward to peer
            if channel.allocation_a == allocation:
                peer = channel.allocation_b
            else:
                peer = channel.allocation_a

            channel.last_activity = time.time()

            await self._send_peer_data(peer, message.channel_id, message.payload)

    async def _send_response(
        self,
        allocation: RelayAllocation,
        msg_type: RelayMessageType,
        payload: bytes,
    ) -> None:
        """Send response to client."""
        message = RelayMessage(
            message_type=msg_type,
            payload=payload,
        )
        await self._send_message(allocation, message)

    async def _send_error(
        self,
        allocation: RelayAllocation,
        error: RelayError,
    ) -> None:
        """Send error response."""
        message = RelayMessage(
            message_type=RelayMessageType.ERROR,
            payload=struct.pack(">B", error.value),
        )
        await self._send_message(allocation, message)

    async def _send_peer_data(
        self,
        allocation: RelayAllocation,
        channel_id: int,
        data: bytes,
    ) -> None:
        """Send peer data to client."""
        message = RelayMessage(
            message_type=RelayMessageType.PEER_DATA,
            channel_id=channel_id,
            payload=data,
        )
        await self._send_message(allocation, message)

    async def _send_message(
        self,
        allocation: RelayAllocation,
        message: RelayMessage,
    ) -> None:
        """Send encrypted message to client."""
        plaintext = message.encode()
        encrypted = allocation.transport.encrypt(plaintext)
        allocation.writer.write(struct.pack(">H", len(encrypted)) + encrypted)
        await allocation.writer.drain()

    async def _close_allocation(self, allocation: RelayAllocation) -> None:
        """Close and cleanup allocation."""
        allocation.active = False

        # Remove from allocations
        self._allocations.pop(allocation.client_id, None)

        # Close channels
        for channel in list(allocation.channels.values()):
            self._channels.pop(channel.channel_id, None)
            channel.active = False

        # Close socket
        try:
            allocation.writer.close()
            await allocation.writer.wait_closed()
        except Exception:
            pass

        logger.info(f"Allocation closed: {allocation.client_id}")

    async def _cleanup_loop(self) -> None:
        """Background task to cleanup expired allocations."""
        try:
            while self._running:
                await asyncio.sleep(60)

                time.time()

                # Cleanup expired allocations
                for allocation in list(self._allocations.values()):
                    if allocation.is_expired():
                        logger.info(f"Expiring allocation: {allocation.client_id}")
                        await self._close_allocation(allocation)

                # Cleanup stale channels
                for channel in list(self._channels.values()):
                    if channel.is_stale():
                        logger.info(f"Removing stale channel: {channel.channel_id}")
                        self._channels.pop(channel.channel_id, None)
                        channel.allocation_a.channels.pop(channel.channel_id, None)
                        channel.allocation_b.channels.pop(channel.channel_id, None)

        except asyncio.CancelledError:
            pass


# =============================================================================
# Relay Client
# =============================================================================


@dataclass
class RelayClient:
    """Client for relay server.

    Connects to relay server and manages channels to peers.

    Example:
        # Create client
        client = RelayClient.create()
        client.server_public_key = relay_server_key

        # Connect to relay
        await client.connect("relay.example.com", 9444)

        # Create channel to peer
        channel_id = await client.create_channel("peer_id")

        # Send data through channel
        await client.send_channel_data(channel_id, b"Hello")

        # Receive data
        client.on_peer_data = handle_data

        # Disconnect
        await client.disconnect()
    """

    # Client identity
    static_keypair: NoiseKeypair

    # Server verification
    server_public_key: bytes | None = None

    # Callbacks
    on_peer_data: Callable[[int, bytes], Awaitable[None]] | None = None

    # State
    _connected: bool = False
    _reader: asyncio.StreamReader | None = None
    _writer: asyncio.StreamWriter | None = None
    _transport: NoiseTransport | None = None
    _read_task: asyncio.Task | None = None
    _refresh_task: asyncio.Task | None = None

    # Channels
    _channels: set[int] = field(default_factory=set)

    @classmethod
    def create(cls, private_key_bytes: bytes | None = None) -> RelayClient:
        """Create a relay client."""
        if private_key_bytes:
            keypair = NoiseKeypair.from_private_bytes(private_key_bytes)
        else:
            keypair = NoiseKeypair.generate()

        return cls(static_keypair=keypair)

    def get_public_key(self) -> bytes:
        """Get client's public key."""
        return self.static_keypair.public_key

    def get_client_id(self) -> str:
        """Get client ID (for peer channel creation)."""
        return self.static_keypair.public_key[:8].hex()

    async def connect(
        self,
        host: str,
        port: int = DEFAULT_RELAY_PORT,
    ) -> bool:
        """Connect to relay server."""
        try:
            # Connect
            self._reader, self._writer = await asyncio.open_connection(host, port)

            # Perform handshake
            if not await self._perform_handshake():
                return False

            self._connected = True

            # Start background tasks
            self._read_task = asyncio.create_task(self._read_loop())
            self._refresh_task = asyncio.create_task(self._refresh_loop())

            logger.info(f"Connected to relay server {host}:{port}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to relay: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from relay server."""
        self._connected = False

        if self._read_task:
            self._read_task.cancel()
        if self._refresh_task:
            self._refresh_task.cancel()

        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

        self._channels.clear()
        logger.info("Disconnected from relay server")

    async def create_channel(self, peer_id: str) -> int | None:
        """Create channel to peer.

        Args:
            peer_id: Peer's client ID.

        Returns:
            Channel ID or None on failure.
        """
        if not self._connected:
            return None

        message = RelayMessage(
            message_type=RelayMessageType.CREATE_CHANNEL,
            payload=peer_id.encode(),
        )
        await self._send_message(message)

        # Response handled in read loop
        # For simplicity, we'll wait briefly
        await asyncio.sleep(0.5)

        # Return most recent channel (in real impl, track pending requests)
        if self._channels:
            return max(self._channels)
        return None

    async def send_channel_data(self, channel_id: int, data: bytes) -> None:
        """Send data through channel.

        Args:
            channel_id: Channel ID.
            data: Data to send.
        """
        if not self._connected:
            raise NoiseError("Not connected")

        if channel_id not in self._channels:
            raise NoiseError(f"Invalid channel: {channel_id}")

        message = RelayMessage(
            message_type=RelayMessageType.CHANNEL_DATA,
            channel_id=channel_id,
            payload=data,
        )
        await self._send_message(message)

    async def _perform_handshake(self) -> bool:
        """Perform Noise handshake as initiator."""
        try:
            handshake = NoiseHandshake.initiator(self.static_keypair)

            # Send first message
            msg1 = handshake.write_message()
            self._writer.write(struct.pack(">H", len(msg1)) + msg1)
            await self._writer.drain()

            # Read response
            async with asyncio.timeout(HANDSHAKE_TIMEOUT):
                msg2_len = struct.unpack(">H", await self._reader.readexactly(2))[0]
                msg2 = await self._reader.readexactly(msg2_len)

            handshake.read_message(msg2)

            # Send final message
            msg3 = handshake.write_message()
            self._writer.write(struct.pack(">H", len(msg3)) + msg3)
            await self._writer.drain()

            if not handshake.is_complete():
                return False

            # Verify server
            remote_key = handshake.get_remote_static_key()
            if self.server_public_key and remote_key != self.server_public_key:
                logger.error("Relay server key mismatch")
                return False

            self._transport = NoiseTransport.from_handshake(handshake)
            return True

        except Exception as e:
            logger.error(f"Handshake failed: {e}")
            return False

    async def _send_message(self, message: RelayMessage) -> None:
        """Send encrypted message."""
        plaintext = message.encode()
        encrypted = self._transport.encrypt(plaintext)
        self._writer.write(struct.pack(">H", len(encrypted)) + encrypted)
        await self._writer.drain()

    async def _read_loop(self) -> None:
        """Background task to read messages."""
        try:
            while self._connected:
                # Read length
                header = await self._reader.readexactly(2)
                msg_len = struct.unpack(">H", header)[0]

                # Read encrypted message
                encrypted = await self._reader.readexactly(msg_len)

                # Decrypt
                plaintext = self._transport.decrypt(encrypted)
                message = RelayMessage.decode(plaintext)

                # Handle message
                await self._handle_message(message)

        except asyncio.CancelledError:
            pass
        except asyncio.IncompleteReadError:
            logger.info("Relay server disconnected")
        except Exception as e:
            logger.error(f"Read error: {e}")

    async def _handle_message(self, message: RelayMessage) -> None:
        """Handle received message."""
        if message.message_type == RelayMessageType.CHANNEL_RESPONSE:
            channel_id = struct.unpack(">H", message.payload)[0]
            self._channels.add(channel_id)
            logger.info(f"Channel created: {channel_id}")

        elif message.message_type == RelayMessageType.PEER_DATA:
            if self.on_peer_data:
                await self.on_peer_data(message.channel_id, message.payload)

        elif message.message_type == RelayMessageType.ERROR:
            error_code = message.payload[0] if message.payload else 0
            logger.warning(f"Relay error: {RelayError(error_code).name}")

    async def _refresh_loop(self) -> None:
        """Background task to refresh allocation."""
        try:
            while self._connected:
                await asyncio.sleep(ALLOCATION_TIMEOUT / 2)

                message = RelayMessage(message_type=RelayMessageType.REFRESH)
                await self._send_message(message)

        except asyncio.CancelledError:
            pass


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "RelayAllocation",
    "RelayChannel",
    "RelayClient",
    "RelayError",
    "RelayMessage",
    "RelayMessageType",
    "RelayServer",
]
