# Kagami Tunnel

Secure internet tunneling for Kagami mesh networking.

## Overview

Kagami Tunnel provides encrypted tunnel connections between the Kagami hub and remote clients (iOS, watchOS, desktop) when outside the local network.

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

## Features

- **Noise Protocol XX** for mutual authentication with identity hiding
- **Ed25519/X25519** key pairs (compatible with mesh auth keys)
- **ChaCha20-Poly1305** for symmetric encryption
- **Automatic network detection** (local vs remote)
- **STUN** for NAT type detection
- **Relay fallback** for symmetric NAT

## Installation

```bash
pip install kagami-tunnel

# With mDNS discovery support
pip install kagami-tunnel[mdns]
```

## Quick Start

### Hub (Server)

```python
from kagami_tunnel import TunnelServer, NoiseKeypair

# Create server with persistent keypair
keypair = NoiseKeypair.generate()
server = TunnelServer(static_keypair=keypair)

# Trust client public keys
server.trust_peer(client_public_key)

# Handle incoming data
async def on_data(conn, data):
    print(f"Received from {conn.connection_id}: {data}")
    await conn.send(b"Echo: " + data)

server.on_data = on_data

# Start server
await server.start(port=9443)
```

### Client

```python
from kagami_tunnel import TunnelClient, NoiseKeypair

# Create client
client = TunnelClient.create()

# Set server public key for verification
client.server_public_key = server_public_key

# Handle incoming data
async def on_data(data):
    print(f"Received: {data}")

client.on_data = on_data

# Connect
await client.connect("hub.example.com", 9443)

# Send data
await client.send(b"Hello, hub!")

# Disconnect
await client.disconnect()
```

### Auto-Connect Client

```python
from kagami_tunnel import AutoTunnelClient, ConnectionMode

# Create auto-connect client
client = AutoTunnelClient.create()
client.tunnel_host = "hub.example.com"
client.tunnel_port = 9443
client.server_public_key = server_public_key

# Auto-detect and connect
await client.connect()

if client.mode == ConnectionMode.LOCAL:
    print("Connected locally via mDNS")
else:
    print("Connected via tunnel")
```

## Network Discovery

```python
from kagami_tunnel import discover_network, NATType

# Discover network info
info = await discover_network()

print(f"Local IP: {info.local_ip}")
print(f"External IP: {info.external_ip}")
print(f"NAT Type: {info.nat_type}")

if info.needs_tunnel():
    print("Tunnel required for connectivity")
```

## Relay Server (NAT Traversal Fallback)

For symmetric NAT environments where direct connections fail:

```python
from kagami_tunnel import RelayServer, RelayClient

# Server side
relay = RelayServer.create(port=9444)
relay.authorize_client(client_key)
await relay.start()

# Client side
client = RelayClient.create()
await client.connect("relay.example.com", 9444)

# Create channel to peer
channel = await client.create_channel(peer_id)
await client.send_channel_data(channel, b"Hello peer")
```

## Security

- **h(x) >= 0. Always.** - All operations maintain safety constraints
- **End-to-end encryption** - All traffic encrypted with ChaCha20-Poly1305
- **Mutual authentication** - Both parties verify identity via Noise XX
- **Forward secrecy** - Ephemeral keys per session
- **Identity hiding** - Static keys encrypted during handshake

## Protocol Details

### Noise XX Handshake

```
    -> e                              (initiator sends ephemeral)
    <- e, ee, s, es                   (responder sends ephemeral, static)
    -> s, se                          (initiator sends static)
```

### Frame Protocol

```
+--------+--------+------------------+
|  Type  | Length |     Payload      |
| 2 bytes| 2 bytes|    N bytes       |
+--------+--------+------------------+
```

Frame types:
- `0x01` HANDSHAKE - Noise handshake messages
- `0x02` DATA - Encrypted application data
- `0x03` KEEPALIVE - Connection keepalive
- `0x04` CLOSE - Graceful disconnect
- `0x05` ERROR - Error notification

## Development

```bash
# Install dev dependencies
pip install kagami-tunnel[dev]

# Run tests
pytest

# Type checking
mypy kagami_tunnel

# Linting
ruff check kagami_tunnel
```

## License

MIT
