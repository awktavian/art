"""Kagami Tunnel - Secure Internet Tunneling for Mesh Networking.

Provides secure, encrypted tunneling for Kagami mesh network when
devices are outside the local network.

Architecture:
```
                    INTERNET
                       |
    +------------------+------------------+
    |            TUNNEL SERVER            |
    |       (runs on hub, port 9443)      |
    +------------------+------------------+
              |                |
        Noise XX          Noise XX
        handshake         handshake
              |                |
    +---------+----+   +-------+-------+
    | Remote Client|   | Remote Client |
    |   (iOS)      |   |   (Desktop)   |
    +--------------+   +---------------+
```

Features:
- Noise Protocol XX for mutual authentication
- Ed25519/X25519 key pairs (reuses mesh auth)
- ChaCha20-Poly1305 symmetric encryption
- Automatic local/remote network detection
- STUN for NAT type detection
- Relay fallback for symmetric NAT

Quick Start:
```python
from kagami_tunnel import TunnelServer, TunnelClient, NoiseKeypair

# On hub - start tunnel server
server_keypair = NoiseKeypair.generate()
server = TunnelServer(static_keypair=server_keypair)
server.trust_peer(client_public_key)
await server.start(port=9443)

# On client - connect to hub
client_keypair = NoiseKeypair.generate()
client = TunnelClient(static_keypair=client_keypair)
client.server_public_key = server_keypair.public_key
await client.connect("hub.example.com", 9443)

# Send/receive encrypted data
await client.send(b"Hello, hub!")
```

Security:
- h(x) >= 0. Always.
- All traffic encrypted end-to-end
- Mutual authentication via Noise XX
- Forward secrecy via ephemeral keys
- Peer verification via static keys

Colony: Crystal (D5) - Security verification

Created: January 2026
"""

from kagami_tunnel.client import (
    AutoTunnelClient,
    ClientState,
    ConnectionMode,
    TunnelClient,
    get_tunnel_client,
    shutdown_tunnel_client,
)
from kagami_tunnel.discovery import (
    NATType,
    NetworkInfo,
    STUNClient,
    STUNMessage,
    discover_hub_mdns,
    discover_network,
    get_external_ip,
    get_external_ip_stun,
    get_local_ip,
    is_local_network,
    is_private_ip,
    is_same_network,
)
from kagami_tunnel.noise import (
    CipherState,
    DecryptionError,
    HandshakeError,
    HandshakeState,
    NoiseError,
    NoiseHandshake,
    NoiseKeypair,
    NoiseTransport,
    SymmetricState,
    create_static_keypair,
    keypair_from_ed25519_seed,
)
from kagami_tunnel.relay import (
    RelayAllocation,
    RelayChannel,
    RelayClient,
    RelayError,
    RelayMessage,
    RelayMessageType,
    RelayServer,
)
from kagami_tunnel.server import (
    DEFAULT_PORT,
    ConnectionState,
    FrameType,
    ServerState,
    TunnelConnection,
    TunnelServer,
    get_tunnel_server,
    shutdown_tunnel_server,
)

__version__ = "1.0.0"

__all__ = [
    # Constants
    "DEFAULT_PORT",
    # Client
    "AutoTunnelClient",
    # Noise Protocol
    "CipherState",
    "ClientState",
    "ConnectionMode",
    # Server
    "ConnectionState",
    "DecryptionError",
    "FrameType",
    "HandshakeError",
    "HandshakeState",
    # Discovery
    "NATType",
    "NetworkInfo",
    "NoiseError",
    "NoiseHandshake",
    "NoiseKeypair",
    "NoiseTransport",
    # Relay
    "RelayAllocation",
    "RelayChannel",
    "RelayClient",
    "RelayError",
    "RelayMessage",
    "RelayMessageType",
    "RelayServer",
    "STUNClient",
    "STUNMessage",
    "ServerState",
    "SymmetricState",
    "TunnelClient",
    "TunnelConnection",
    "TunnelServer",
    # Version
    "__version__",
    "create_static_keypair",
    "discover_hub_mdns",
    "discover_network",
    "get_external_ip",
    "get_external_ip_stun",
    "get_local_ip",
    "get_tunnel_client",
    "get_tunnel_server",
    "is_local_network",
    "is_private_ip",
    "is_same_network",
    "keypair_from_ed25519_seed",
    "shutdown_tunnel_client",
    "shutdown_tunnel_server",
]
