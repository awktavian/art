# API and Platforms

*100+ endpoints, seven platforms, four storage systems, one unified architecture.*

**Version:** 1.0.0
**Last Verified:** January 12, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [API Architecture](#api-architecture)
3. [Authentication](#authentication)
4. [Core Endpoints](#core-endpoints)
5. [Real-Time Communication](#real-time-communication)
6. [Platform Applications](#platform-applications)
7. [Storage Architecture](#storage-architecture)
8. [Deferred Boot System](#deferred-boot-system)
9. [Error Handling](#error-handling)
10. [SDK Examples](#sdk-examples)
11. [Code References](#code-references)

---

## Overview

Kagami exposes a comprehensive API surface for controlling the unified organism, smart home, and AI subsystems. The architecture supports:

- **100+ REST endpoints** for all system functions
- **WebSocket streaming** for real-time state synchronization
- **Server-Sent Events (SSE)** for receipt streaming
- **Seven client platforms** with unified protocol support
- **Four storage backends** with intelligent routing
- **Non-blocking boot** for instant API availability

```
+-------------------------------------------------------------------+
|                         KAGAMI SYSTEM                              |
+-------------------------------------------------------------------+
|                                                                    |
|  +-------------+    +-------------+    +-------------+             |
|  |   REST API  |    |  WebSocket  |    |     SSE     |            |
|  |  100+ eps   |    |   Stream    |    |   Stream    |            |
|  +------+------+    +------+------+    +------+------+            |
|         |                  |                  |                    |
|         +------------------+------------------+                    |
|                            |                                       |
|                   +--------+--------+                              |
|                   |  FastAPI Core   |                              |
|                   +--------+--------+                              |
|                            |                                       |
|    +----------+------------+------------+----------+               |
|    |          |            |            |          |               |
|    v          v            v            v          v               |
| +------+ +--------+ +----------+ +-------+ +------+               |
| |Weaviate| |Redis  | |CockroachDB| |etcd | |Models|               |
| |Vectors | |Cache  | |Relational | |Coord| |RSSM  |               |
| +------+ +--------+ +----------+ +-------+ +------+               |
|                                                                    |
+-------------------------------------------------------------------+
```

**Base URL:** `http://localhost:8001`
**OpenAPI Docs:** `/docs` (Swagger UI) | `/redoc` (ReDoc)

---

## API Architecture

### Protocol Stack

| Layer | Protocol | Purpose |
|-------|----------|---------|
| Transport | HTTP/1.1, HTTP/2 | Request/response |
| Streaming | WebSocket | Bidirectional real-time |
| Events | SSE | Server-to-client push |
| Serialization | JSON | All payloads |

### Request Flow

```
Client Request
      |
      v
+-------------+     +-------------+     +-------------+
|   Auth      | --> |   Rate      | --> |   Route     |
|  Middleware |     |   Limiter   |     |   Handler   |
+-------------+     +-------------+     +-------------+
                                              |
                    +-------------------------+
                    |
      +-------------+-------------+
      |             |             |
      v             v             v
+----------+  +----------+  +----------+
| Storage  |  | Colony   |  | Smart    |
| Layer    |  | System   |  | Home     |
+----------+  +----------+  +----------+
```

---

## Authentication

Kagami uses two authentication methods, each optimized for different use cases.

### Methods

| Method | Header | Use Case |
|--------|--------|----------|
| **JWT Token** | `Authorization: Bearer <token>` | User sessions, interactive use |
| **API Key** | `X-API-Key: <key>` | Service-to-service, automation |

### JWT Authentication

#### Token Structure

```
Header.Payload.Signature
```

**Header:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Payload:**
```json
{
  "sub": "user-uuid",
  "username": "tim",
  "roles": ["user", "admin"],
  "tenant_id": "default",
  "exp": 1735689600,
  "iat": 1735603200
}
```

#### Token Lifecycle

| Token Type | Duration | Refresh |
|------------|----------|---------|
| Access Token | 30 min | Via refresh token |
| Refresh Token | 7 days | Re-login required |

#### Getting Tokens

```bash
# Login
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "tim", "password": "***"}'

# Response
{
  "access_token": "eyJhbG...",
  "refresh_token": "eyJhbG...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### Refreshing Tokens

```bash
curl -X POST http://localhost:8001/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJhbG..."}'
```

### API Key Authentication

#### Key Format

```
sk_{tier}_{random}
```

Examples:
- `sk_free_abc123xyz...`
- `sk_pro_def456uvw...`
- `sk_enterprise_ghi789rst...`

#### Using API Keys

```bash
# Via header (recommended)
curl http://localhost:8001/api/home/state \
  -H "X-API-Key: sk_pro_abc123..."

# Via Authorization header
curl http://localhost:8001/api/home/state \
  -H "Authorization: Bearer sk_pro_abc123..."
```

#### Creating API Keys

```bash
curl -X POST http://localhost:8001/api/keys \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{"name": "automation", "tier": "pro", "scopes": ["home:read", "home:write"]}'

# Response
{
  "key": "sk_pro_...",  # Only shown once!
  "key_id": "uuid",
  "name": "automation",
  "tier": "pro",
  "created_at": "2025-12-31T00:00:00Z"
}
```

### Tiers and Rate Limits

| Tier | Rate Limit | Features |
|------|------------|----------|
| **Free** | 60 req/min | Basic endpoints, no streaming |
| **Pro** | 600 req/min | Streaming, WebSocket, advanced |
| **Enterprise** | Unlimited | Full access, priority support |

#### Rate Limit Headers

```
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 598
X-RateLimit-Reset: 1735689600
```

### Roles and Permissions

#### Built-in Roles

| Role | Permissions |
|------|-------------|
| `user` | Basic access, own data |
| `admin` | Full access, user management |
| `api_user` | API-only access |
| `service` | Internal service account |

#### Scopes

| Scope | Access |
|-------|--------|
| `home:read` | Read home state |
| `home:write` | Control devices |
| `colonies:read` | View colony status |
| `colonies:write` | Execute intents |
| `admin:*` | Administrative access |

### WebSocket Authentication

WebSocket connections authenticate via the first message:

```javascript
const ws = new WebSocket("ws://localhost:8001/api/colonies/stream");

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "auth",
    token: "sk_pro_abc123...",  // or JWT token
    subscribe: ["colonies", "home", "safety"]
  }));
};
```

#### Query Parameter (Alternative)

```javascript
const ws = new WebSocket(
  "ws://localhost:8001/v1/stream?api_key=sk_pro_abc123..."
);
```

### Multi-Tenant Isolation

Every request is scoped to a tenant:

```json
{
  "user_id": "uuid",
  "tenant_id": "default",
  "username": "tim"
}
```

- Users only see their tenant's data
- API keys are scoped to tenants
- Receipts include `tenant_id`

### Security Best Practices

#### Token Storage

| Platform | Storage |
|----------|---------|
| Browser | HttpOnly cookie |
| Mobile | Secure keychain |
| Server | Environment variable |
| CLI | OS keychain |

#### API Key Rotation

```bash
# Create new key
curl -X POST http://localhost:8001/api/keys ...

# Update applications with new key

# Revoke old key
curl -X DELETE http://localhost:8001/api/keys/{old_key_id}
```

#### Security Headers

All responses include:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000
```

---

## Core Endpoints

### Health and Status

```http
GET /api/health
```
Returns basic health status.

```http
GET /api/health/detailed
```
Returns detailed health with all component status.

**Response:**
```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "weaviate": "healthy",
    "control4": "healthy"
  },
  "uptime_seconds": 86400
}
```

```http
GET /metrics
```
Returns Prometheus metrics.

### Colony Endpoints

#### System Status

```http
GET /api/colonies/status
```
Returns all 7 colonies and their current state.

**Response:**
```json
{
  "colonies": {
    "spark": {"state": "idle", "energy": 0.85},
    "forge": {"state": "executing", "current_task": "set_lights"},
    "flow": {"state": "idle", "energy": 0.88},
    "nexus": {"state": "idle", "energy": 0.90},
    "beacon": {"state": "idle", "energy": 0.87},
    "grove": {"state": "idle", "energy": 0.83},
    "crystal": {"state": "idle", "energy": 0.95}
  },
  "safety": {"h_x": 0.72, "status": "safe"}
}
```

### AG-UI Protocol

Bidirectional agent-UI communication via the AG-UI protocol.

#### Send Message

```http
POST /api/colonies/ui/message
```
Send a message to the agent.

**Request:**
```json
{
  "content": "movie mode",
  "context": {}
}
```

#### Confirmation Response

```http
POST /api/colonies/ui/confirm/{request_id}
```
Respond to a confirmation request.

**Request:**
```json
{
  "approved": true,
  "comment": "Go ahead"
}
```

### Smart Home Endpoints

#### Get Home State

```http
GET /api/home/state
```
Returns current home state.

#### Control Lights

```http
POST /api/home/lights
```

**Request:**
```json
{
  "level": 50,
  "rooms": ["Living Room"],
  "transition": 500
}
```

#### Control Shades

```http
POST /api/home/shades/open
POST /api/home/shades/close
```

**Request:**
```json
{
  "rooms": ["Living Room"]
}
```

#### Scenes

```http
POST /api/home/scenes/{scene_name}
```

Available scenes: `movie`, `goodnight`, `welcome`, `focus`

#### Fireplace

```http
POST /api/home/fireplace/on
POST /api/home/fireplace/off
```

#### Locks

```http
POST /api/home/locks/lock-all
POST /api/home/locks/unlock/{door_name}
```

### Intent and Command

#### Parse Intent

```http
POST /api/command/intent
```

**Request:**
```json
{
  "text": "Turn on the living room lights to 50%",
  "context": {}
}
```

**Response:**
```json
{
  "intent": "smart_home.lights.set",
  "entities": {
    "room": "Living Room",
    "level": 50
  },
  "confidence": 0.95,
  "colony": "forge"
}
```

#### Execute Command

```http
POST /api/command/execute
```

**Request:**
```json
{
  "intent": "smart_home.lights.set",
  "entities": {
    "room": "Living Room",
    "level": 50
  }
}
```

### Safety Endpoints

#### Check Safety

```http
POST /api/safety/check
```

**Request:**
```json
{
  "action": "smart_home.lock.unlock",
  "context": {
    "location": "entry",
    "presence": "home"
  }
}
```

**Response:**
```json
{
  "safe": true,
  "h_x": 0.65,
  "confidence": 0.92,
  "warnings": []
}
```

#### Get CBF Status

```http
GET /api/safety/cbf
```
Returns Control Barrier Function status.

### Mind Endpoints

#### Receipts

```http
GET /api/mind/receipts?limit=50
```
Returns recent receipts.

```http
GET /api/mind/receipts/{correlation_id}
```
Returns receipts for a specific correlation ID.

#### Goals

```http
GET /api/mind/goals
```
Returns active goals.

```http
POST /api/mind/goals
```
Creates a new goal.

### User Endpoints

#### Login

```http
POST /api/auth/login
```

**Request:**
```json
{
  "username": "tim",
  "password": "***"
}
```

**Response:**
```json
{
  "access_token": "eyJhbG...",
  "refresh_token": "eyJhbG...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### Refresh Token

```http
POST /api/auth/refresh
```

**Request:**
```json
{
  "refresh_token": "eyJhbG..."
}
```

#### API Keys

```http
GET /api/keys
```
Lists user's API keys.

```http
POST /api/keys
```
Creates new API key.

```http
DELETE /api/keys/{key_id}
```
Revokes an API key.

---

## Real-Time Communication

### WebSocket Stream

```
WS /api/colonies/stream
```
Real-time colony activity, state changes, and events.

#### Authentication

```json
{
  "type": "auth",
  "token": "sk_pro_abc123...",
  "subscribe": ["colonies", "home", "safety"]
}
```

Or via query parameter:

```
ws://localhost:8001/api/colonies/stream?api_key=sk_pro_abc123...
```

#### Event Types

| Event | Description |
|-------|-------------|
| `colony_state` | Colony state changes |
| `safety_alert` | Safety warnings |
| `receipt` | New receipt created |
| `home_state` | Home state changes |
| `auth_success` | Authentication successful |
| `auth_error` | Authentication failed |
| `ping` | Keep-alive ping |
| `error` | Error notification |

#### AG-UI WebSocket

```
WS /api/colonies/ui/ws
```
Full AG-UI protocol via WebSocket.

#### Coordination Stream (Pro Tier)

```
WS /v1/stream
```
Real-time coordination events for Pro tier subscribers.

### Server-Sent Events (SSE)

```http
GET /api/receipts/stream
```
Server-Sent Events stream of all receipts.

**Usage:**
```bash
curl -N http://localhost:8001/api/receipts/stream \
  -H "X-API-Key: sk_pro_xxx"
```

**Events:**
```
event: receipt
data: {"correlation_id":"abc123","action":"set_lights","status":"success"}

event: receipt
data: {"correlation_id":"abc124","action":"movie_mode","status":"success"}
```

### Heartbeat / Keep-Alive

The server sends periodic `ping` messages (every 30s). Clients should respond with `pong`:

```json
// Server sends:
{"type": "ping", "timestamp": "2025-12-31T12:00:00Z"}

// Client responds:
{"type": "pong"}
```

If no pong is received within 60s, the server closes the connection.

### JavaScript WebSocket Client

```javascript
class KagamiWebSocket {
  constructor(url, apiKey) {
    this.url = url;
    this.apiKey = apiKey;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 1000;
    this.subscriptions = ["colonies", "home", "safety"];
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log("Connected to Kagami");
      this.reconnectAttempts = 0;
      this.authenticate();
    };

    this.ws.onclose = (event) => {
      if (event.code !== 1000) {  // Not a clean close
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };
  }

  authenticate() {
    this.ws.send(JSON.stringify({
      type: "auth",
      token: this.apiKey,
      subscribe: this.subscriptions
    }));
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("Max reconnection attempts reached");
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    console.log(`Reconnecting in ${delay}ms...`);

    setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  handleMessage(data) {
    switch (data.type) {
      case "auth_success":
        console.log("Authenticated successfully");
        break;
      case "auth_error":
        console.error("Authentication failed:", data.message);
        break;
      case "colony_state":
        this.onColonyState(data.payload);
        break;
      case "home_state":
        this.onHomeState(data.payload);
        break;
      case "safety_alert":
        this.onSafetyAlert(data.payload);
        break;
      case "ping":
        this.ws.send(JSON.stringify({ type: "pong" }));
        break;
      case "error":
        this.onError(data.payload);
        break;
    }
  }

  // Override these in your application
  onColonyState(payload) { console.log("Colony:", payload); }
  onHomeState(payload) { console.log("Home:", payload); }
  onSafetyAlert(payload) { console.log("Safety:", payload); }
  onError(payload) { console.error("Error:", payload); }
}

// Usage
const ws = new KagamiWebSocket(
  "ws://localhost:8001/api/colonies/stream",
  "sk_pro_xxx"
);
ws.connect();
```

### Python WebSocket Client

```python
import asyncio
import websockets
import json
from typing import Callable

class KagamiClient:
    def __init__(self, url: str, api_key: str):
        self.url = url
        self.api_key = api_key
        self.ws = None
        self.reconnect_attempts = 0
        self.max_reconnects = 10
        self.handlers: dict[str, Callable] = {}

    def on(self, event_type: str):
        """Decorator for event handlers."""
        def decorator(func):
            self.handlers[event_type] = func
            return func
        return decorator

    async def connect(self):
        """Connect with automatic reconnection."""
        while self.reconnect_attempts < self.max_reconnects:
            try:
                async with websockets.connect(self.url) as ws:
                    self.ws = ws
                    self.reconnect_attempts = 0

                    # Authenticate
                    await ws.send(json.dumps({
                        "type": "auth",
                        "token": self.api_key,
                        "subscribe": ["colonies", "home", "safety"]
                    }))

                    # Message loop
                    async for message in ws:
                        data = json.loads(message)
                        await self._handle_message(data)

            except websockets.ConnectionClosed:
                await self._reconnect()
            except Exception as e:
                print(f"Error: {e}")
                await self._reconnect()

    async def _reconnect(self):
        delay = min(2 ** self.reconnect_attempts, 60)
        print(f"Reconnecting in {delay}s...")
        await asyncio.sleep(delay)
        self.reconnect_attempts += 1

    async def _handle_message(self, data: dict):
        event_type = data.get("type")
        handler = self.handlers.get(event_type)

        if handler:
            if asyncio.iscoroutinefunction(handler):
                await handler(data.get("payload", {}))
            else:
                handler(data.get("payload", {}))
        elif event_type == "ping":
            await self.ws.send(json.dumps({"type": "pong"}))

# Usage
client = KagamiClient(
    "ws://localhost:8001/api/colonies/stream",
    "sk_pro_xxx"
)

@client.on("colony_state")
async def on_colony(payload):
    print(f"Colony update: {payload}")

@client.on("home_state")
async def on_home(payload):
    print(f"Home update: {payload}")

asyncio.run(client.connect())
```

---

## Platform Applications

Kagami runs across seven client platforms, all connected to a shared real-time backbone.

### Platform Overview

| Client | Platform | Location | Primary Use |
|--------|----------|----------|-------------|
| **Desktop** | macOS/Win/Linux | `apps/desktop/kagami-client/` | Primary interface |
| **Hub** | Raspberry Pi | `apps/hub/kagami-hub/` | Voice-first ambient |
| **Watch** | Apple Watch | `apps/watch/kagami-watch/` | Glance actions |
| **Vision** | Vision Pro | `apps/visionos/kagami-visionos/` | Spatial presence |
| **TV** | Apple TV | `apps/tv/kagami-tv/` | Living room control |
| **Android** | Android | `apps/android/kagami-android/` | Mobile access |
| **iOS** | iPhone/iPad | `apps/ios/` | Mobile access |

### Real-Time Architecture

```
+------------------------------------------------------------------------+
|                         KAGAMI API SERVER                               |
|                         localhost:8001                                  |
+------------------------------------------------------------------------+
|                                                                         |
|  WebSocket: /api/colonies/stream      SSE: /api/receipts/stream        |
|                    |                              |                     |
|                    +---------------+--------------+                     |
|                                    |                                    |
|                    +---------------+---------------+                    |
|                    |               |               |                    |
|                    v               v               v                    |
|               +--------+      +--------+      +--------+               |
|               |Desktop |      |  Hub   |      | Watch  |               |
|               |        |      |        |      |        |               |
|               | Tauri  |      |  Rust  |      | Swift  |               |
|               +--------+      +--------+      +--------+               |
|                                                                         |
+------------------------------------------------------------------------+
```

#### Connection Specifications

| Metric | Target |
|--------|--------|
| State sync latency | < 50ms |
| Event propagation | < 100ms |
| Reconnection time | < 1s |
| Heartbeat interval | 5s |

### Desktop Client (Tauri)

#### UI Wireframe

```
+------------------------------------------------------------------------------+
|  Kagami                                              - [] X                   |
+------------------------------------------------------------------------------+
|                                                                               |
|  +-----------------------------------------------------------------------+   |
|  |                    [ What can I help with? ]                          |   |
|  +-----------------------------------------------------------------------+   |
|                                                                               |
|  +-----------------+  +-----------------+  +-----------------+               |
|  |  Movie Mode     |  |  Goodnight      |  |  Welcome        |              |
|  |                 |  |                 |  |                 |              |
|  |   Option+M      |  |   Option+G      |  |   Option+W      |              |
|  +-----------------+  +-----------------+  +-----------------+               |
|                                                                               |
|  +-----------------------------------------------------------------------+   |
|  |  Colony Status                                                        |   |
|  |                                                                       |   |
|  |  Spark   ###--  42%    Forge   #######-  87%  [executing]            |   |
|  |  Flow    ##----  28%    Nexus   ####----  55%                        |   |
|  |  Beacon  #####-  67%    Grove   ##------  23%                        |   |
|  |  Crystal ######  95%                                                  |   |
|  |                                                                       |   |
|  |  Safety: ################---- h(x) = 0.82  [SAFE]                    |   |
|  +-----------------------------------------------------------------------+   |
|                                                                               |
|  +-----------------------------------------------------------------------+   |
|  |  Recent Actions                                                       |   |
|  |  ----------------                                                     |   |
|  |  12:00  set_lights(Living Room, 50%)           OK 45ms               |   |
|  |  11:55  movie_mode()                            OK 2.3s              |   |
|  |  11:30  announce("Meeting in 5 minutes")        OK 120ms             |   |
|  +-----------------------------------------------------------------------+   |
|                                                                               |
+------------------------------------------------------------------------------+
```

#### Technology Stack
- **Runtime:** Tauri 2.x (Rust backend, web frontend)
- **Frontend:** Vanilla JS + CSS
- **Language:** Rust (commands), JavaScript (UI)

#### Features

| Feature | Shortcut | Description |
|---------|----------|-------------|
| Quick Entry | `Option+K` | Open command palette |
| Movie Mode | `Option+M` | Direct scene trigger |
| Goodnight | `Option+G` | Direct scene trigger |
| Welcome Home | `Option+W` | Direct scene trigger |
| Emergency Stop | `Option+.` | Cancel all actions |
| Push-to-Talk | `Caps Lock` (hold) | Voice command |
| Wake Word | "Hey Kagami" | Voice activation |

#### Key Files

| File | Purpose |
|------|---------|
| `src-tauri/src/main.rs` | Tauri entry point |
| `src-tauri/src/realtime.rs` | WebSocket handler |
| `src-tauri/src/commands.rs` | Tauri commands |
| `src/js/ambient.js` | Ambient display |
| `src/js/context.js` | Context panel |
| `src/css/microanimations.css` | Animation system |

#### Building

```bash
cd apps/desktop/kagami-client

# Install dependencies
npm install

# Development mode
npm run tauri dev

# Production build
npm run tauri build

# Built app locations:
# - macOS: src-tauri/target/release/bundle/macos/Kagami.app
# - Windows: src-tauri/target/release/bundle/msi/Kagami_x.x.x_x64_en-US.msi
# - Linux: src-tauri/target/release/bundle/deb/kagami_x.x.x_amd64.deb
```

#### Configuration

Create `~/.config/kagami/client.toml`:

```toml
[api]
base_url = "http://localhost:8001"
api_key = "sk_pro_xxx"

[shortcuts]
quick_entry = "Option+K"
movie_mode = "Option+M"
goodnight = "Option+G"

[ui]
theme = "dark"  # or "light", "system"
```

### Hub (Raspberry Pi)

#### Hardware Diagram

```
+------------------------------------------------------------------------------+
|                        KAGAMI HUB HARDWARE                                    |
+------------------------------------------------------------------------------+
|                                                                               |
|                            +---------+                                        |
|                            | USB Mic |                                        |
|                            +----+----+                                        |
|                                 |                                             |
|       +-------------------------+-------------------------+                   |
|       |                         |                         |                   |
|       |    +---------------+----+----+---------------+    |                   |
|       |    |               | Pi 4/5  |               |    |                   |
|       |    |               +----+----+               |    |                   |
|       |    |                    |                    |    |                   |
|       |    |    o o o o o o o   |   GPIO (LED ring)  |    |                   |
|       |    |    1 2 3 4 5 6 7   |                    |    |                   |
|       |    |                    |                    |    |                   |
|       |    +--------------------+--------------------+    |                   |
|       |                         |                         |                   |
|       +-------------------------+-------------------------+                   |
|                                 |                                             |
|                            +----+----+                                        |
|                            | Speaker |                                        |
|                            | (3.5mm) |                                        |
|                            +---------+                                        |
|                                                                               |
+------------------------------------------------------------------------------+
```

#### Technology Stack
- **Runtime:** Native Rust
- **Audio:** ALSA + Whisper STT
- **Hardware:** WS2812B LED ring, USB mic

#### Features

| Feature | Hardware | Description |
|---------|----------|-------------|
| Wake Word | USB Mic | "Hey Kagami" detection |
| Voice Commands | Mic -> Whisper | Natural language |
| LED Ring | WS2812B (7 LEDs) | Colony status |
| Audio Output | 3.5mm/I2S | TTS responses |

#### LED Ring Colors

Each of the 7 LEDs represents one colony:

| LED | Colony | Color | RGB |
|-----|--------|-------|-----|
| 1 | Spark | Orange | `#FF6B00` |
| 2 | Forge | Red | `#FF2D2D` |
| 3 | Flow | Blue | `#2D7DFF` |
| 4 | Nexus | Purple | `#9B2DFF` |
| 5 | Beacon | Green | `#2DFF6B` |
| 6 | Grove | Emerald | `#00D4AA` |
| 7 | Crystal | White | `#FFFFFF` |

#### Key Files

| File | Purpose |
|------|---------|
| `src/main.rs` | Entry point |
| `src/voice_pipeline.rs` | STT processing |
| `src/led_ring.rs` | LED control |
| `src/wake_word.rs` | Wake word detection |
| `src/realtime.rs` | WebSocket handler |

#### Building and Installation

```bash
cd apps/hub/kagami-hub

# Cross-compile for Raspberry Pi (from macOS/Linux)
rustup target add aarch64-unknown-linux-gnu
cargo build --release --target aarch64-unknown-linux-gnu

# Or build directly on Pi
cargo build --release

# Install
sudo cp target/release/kagami-hub /usr/local/bin/

# Create systemd service
sudo tee /etc/systemd/system/kagami-hub.service << 'EOF'
[Unit]
Description=Kagami Hub
After=network.target

[Service]
Type=simple
User=pi
ExecStart=/usr/local/bin/kagami-hub
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable kagami-hub
sudo systemctl start kagami-hub
```

#### Configuration

Create `/etc/kagami/hub.toml`:

```toml
[api]
base_url = "http://kagami-server:8001"
api_key = "sk_pro_xxx"

[audio]
input_device = "default"
output_device = "default"
wake_word = "hey kagami"

[led]
gpio_pin = 18
led_count = 7
brightness = 0.5
```

### Watch (watchOS)

#### Technology Stack
- **Runtime:** Native Swift/SwiftUI
- **Audio:** SFSpeechRecognizer

#### Features

| Feature | Description |
|---------|-------------|
| Glance Action | Time-based hero action |
| Complications | Safety score, context |
| Voice Commands | Native speech recognition |
| Haptics | Feedback patterns |
| Health Upload | Motion, heart rate data |

#### Time-Based Actions

| Time | Glance Action |
|------|---------------|
| 5-9 AM | Start Day |
| 9 AM - 5 PM | Focus Mode |
| 5-10 PM | Movie Mode |
| 10 PM+ | Goodnight |

#### Key Files

| File | Purpose |
|------|---------|
| `KagamiWatch/ContentView.swift` | Main view |
| `KagamiWatch/KagamiAPIService.swift` | API client |
| `KagamiWatch/ColonyComplication.swift` | Complications |
| `KagamiWatch/GlanceView.swift` | Glance interface |

### Vision (visionOS)

#### Technology Stack
- **Runtime:** Native Swift/SwiftUI
- **Framework:** RealityKit, ARKit

#### Features

| Feature | Description |
|---------|-------------|
| Spatial Presence | Kagami floating in space |
| Command Palette | Voice + gesture input |
| Room Awareness | Spatial anchors |
| Ambient Display | Colony status visualization |
| Gaze Selection | Look to select |

#### Key Files

| File | Purpose |
|------|---------|
| `KagamiVision/KagamiPresenceView.swift` | Spatial presence |
| `KagamiVision/CommandPaletteView.swift` | Command input |
| `KagamiVision/AmbientOrb.swift` | Status visualization |

### TV (tvOS)

#### UI Wireframe

```
+------------------------------------------------------------------------------+
|  Kagami                                                      Settings        |
+------------------------------------------------------------------------------+
|                                                                               |
|  +-----------------------------------------------------------------------+   |
|  |  Connection Status                                                    |   |
|  |  o Connected  kagami.local  45ms    h(x) = 0.95                      |   |
|  +-----------------------------------------------------------------------+   |
|                                                                               |
|  Quick Actions                                                                |
|  +----------+  +----------+  +----------+  +----------+                      |
|  | All      |  | Lock     |  | Movie    |  | Good     |                      |
|  | Lights   |  | All      |  | Mode     |  | night    |                      |
|  | Off      |  |          |  |          |  |          |                      |
|  +----------+  +----------+  +----------+  +----------+                      |
|                                                                               |
|  Rooms (26)                                                                   |
|  +--------------+  +--------------+  +--------------+  +--------------+      |
|  | Living Room  |  | Kitchen      |  | Master Bed   |  | Office       |      |
|  | 1st Floor    |  | 1st Floor    |  | 2nd Floor    |  | 3rd Floor    |      |
|  | ======= 80%  |  | ====--- 60%  |  | ------- 0%   |  | =====-- 70%  |      |
|  | [Full][Dim]  |  | [Full][Dim]  |  | [Full][Dim]  |  | [Full][Dim]  |      |
|  | [Off]        |  | [Off]        |  | [Off]        |  | [Off]        |      |
|  +--------------+  +--------------+  +--------------+  +--------------+      |
|                                                                               |
|  h(x) >= 0. Always.                                                          |
+------------------------------------------------------------------------------+
```

#### Technology Stack
- **Runtime:** Native Swift/SwiftUI for tvOS
- **Minimum:** tvOS 17.0
- **Architecture:** SwiftUI with async/await
- **Dependencies:** KagamiCore, KagamiDesign (SPM)

#### Features

| Feature | Description |
|---------|-------------|
| Room Grid | 4-column grid with focus navigation |
| Quick Actions | Movie Mode, Goodnight, Lock All, All Lights Off |
| Scenes | 8 preset scenes with colony-colored icons |
| Connection Status | Live hub connection, latency, safety score |
| Offline Queue | Queued actions with pending count display |
| Mesh Discovery | Discover hubs on local network |
| Circuit Breaker | Automatic retry with exponential backoff |
| Accessibility | Full VoiceOver support, focus-based navigation |

#### Design System

The tvOS app uses the shared `KagamiDesign` package with TV-specific adaptations:

| Token | Value | Purpose |
|-------|-------|---------|
| `TVDesign.cardRadius` | 24pt | Larger corner radius for TV viewing |
| `TVDesign.cardSpacing` | 24pt | Generous padding |
| `TVDesign.gridSpacing` | 40pt | Grid gaps for focus states |
| `TVDesign.contentPadding` | 80pt | Edge padding for safe area |
| `TVDesign.buttonHeight` | 80pt | Large touch targets |
| `TvMotion.card` | 233ms | Fibonacci timing for focus animations |

#### Focus Navigation

tvOS uses the Siri Remote for navigation:

1. **D-pad Focus** - Arrow keys move between focusable elements
2. **Click to Activate** - Center click triggers actions
3. **Play/Pause** - Opens quick scene selector
4. **Menu Button** - Returns to previous screen

#### Key Files

| File | Purpose |
|------|---------|
| `KagamiTV/KagamiTVApp.swift` | App entry point, TabView navigation |
| `KagamiTV/ContentView.swift` | Root view with model injection |
| `KagamiTV/Views/HomeView.swift` | Room grid, quick actions, status |
| `KagamiTV/Views/ScenesView.swift` | Scene selection grid |
| `KagamiTV/Views/SettingsView.swift` | Connection, queue, circuit breaker |
| `KagamiTV/Services/KagamiAPIService.swift` | REST API client |
| `KagamiTV/Services/KagamiNetworkService.swift` | Network layer with circuit breaker |

#### Building

```bash
cd apps/tv/kagami-tv

# Build with Xcode
xcodebuild -project KagamiTV.xcodeproj \
  -scheme KagamiTV \
  -configuration Debug \
  -destination 'platform=tvOS Simulator,name=Apple TV 4K (3rd generation)' \
  build

# Or open in Xcode
open KagamiTV.xcodeproj
```

### Android

#### Technology Stack
- **Runtime:** Native Kotlin
- **UI:** Jetpack Compose

#### Features

| Feature | Description |
|---------|-------------|
| Quick Actions | Widget shortcuts |
| Voice | Speech recognition |
| Notifications | Alert forwarding |
| Wear OS | Watch companion |

#### Key Files

| File | Purpose |
|------|---------|
| `app/src/main/java/.../MainActivity.kt` | Entry point |
| `app/src/main/java/.../KagamiService.kt` | Background service |
| `app/src/main/java/.../HomeWidget.kt` | Widget |

### iOS

#### Technology Stack
- **Runtime:** Native Swift/SwiftUI

#### Features

| Feature | Description |
|---------|-------------|
| Widgets | Home screen shortcuts |
| Shortcuts | Siri integration |
| Push | Alert notifications |
| CarPlay | In-car interface |

#### Key Files

| File | Purpose |
|------|---------|
| `KagamiApp/ContentView.swift` | Main view |
| `KagamiApp/KagamiAPI.swift` | API client |
| `KagamiWidgets/` | Widget extensions |

### Common Patterns

#### WebSocket Connection (Rust)

```rust
pub async fn connect_websocket(url: &str, token: &str) -> Result<()> {
    let ws = WebSocket::connect(url).await?;

    // Auth
    ws.send(json!({
        "type": "auth",
        "token": token,
        "subscribe": ["colonies", "home", "safety"]
    })).await?;

    // Event loop
    while let Some(msg) = ws.recv().await {
        handle_event(msg)?;
    }

    Ok(())
}
```

#### WebSocket Connection (Swift)

```swift
class KagamiConnection: NSObject, URLSessionWebSocketDelegate {
    func connect(token: String) {
        let url = URL(string: "ws://localhost:8001/api/colonies/stream")!
        let task = session.webSocketTask(with: url)
        task.resume()

        // Auth
        let auth = ["type": "auth", "token": token]
        task.send(.string(try! JSONEncoder().encode(auth))) { _ in }

        // Receive
        receiveMessage(task)
    }
}
```

#### State Sync Pattern

All clients follow the same state synchronization pattern:

1. **Connect** to WebSocket
2. **Authenticate** with token
3. **Subscribe** to topics
4. **Receive** state updates
5. **Render** UI changes
6. **Reconnect** on disconnect

---

## Storage Architecture

Kagami uses four storage systems, each optimized for different data types.

### Storage Overview

```
+------------------------------------------------------------------------+
|                        UNIFIED STORAGE ARCHITECTURE                     |
+------------------------------------------------------------------------+
|                                                                         |
|  +--------------+     +--------------+     +--------------+            |
|  |   Weaviate   |     |    Redis     |     | CockroachDB  |            |
|  | (Vectors/RAG)|     | (Cache/Pub)  |     |  (Relational)|            |
|  +------+-------+     +------+-------+     +------+-------+            |
|         |                    |                    |                     |
|         +--------------------+--------------------+                     |
|                              |                                          |
|                     +--------+--------+                                 |
|                     |      etcd       |                                 |
|                     | (Coordination)  |                                 |
|                     +-----------------+                                 |
|                                                                         |
+------------------------------------------------------------------------+
```

### Routing Decision Tree

```
Data Type?
    |
    +-- Vector/Embedding ----------> WEAVIATE
    |   - RAG results
    |   - Semantic search
    |   - E8 quantized embeddings
    |   - Stigmergy patterns
    |   - Few-shot examples
    |
    +-- Ephemeral/Cache ------------> REDIS
    |   - Session state
    |   - Rate limiting
    |   - L2 cache
    |   - Pub/sub events
    |   - Short-term receipts
    |
    +-- Relational/Transactional ---> COCKROACHDB
    |   - Users/auth
    |   - Billing/tenants
    |   - Audit logs (permanent)
    |   - Safety snapshots
    |   - Learning signals
    |
    +-- Coordination/Consensus -----> ETCD
        - Leader election
        - Federated aggregation
        - Service discovery
        - Cross-instance sync
        - Distributed locks
```

### Weaviate - Vector Storage

**Purpose:** Semantic search, RAG, embeddings

#### Collections

| Collection | Content |
|------------|---------|
| `KagamiMemory` | Episodic memories, receipts |
| `KagamiFeedback` | User ratings, corrections |
| `KagamiPatterns` | Stigmergy learning patterns |
| `KagamiExamples` | Few-shot examples |

#### Usage

```python
from kagami.core.services.storage_routing import get_storage_router

router = get_storage_router()

# Store vector
uuid = await router.store_vector(
    content="Movie mode activated successfully",
    metadata={"action": "movie_mode", "success": True}
)

# Semantic search
results = await router.search_semantic(
    query="how to start movie mode",
    limit=5,
    colony_filter="forge"
)
```

#### E8 Quantization

Embeddings are quantized to E8 lattice points for:
- 8x compression
- Faster similarity search
- Geometric alignment with colony structure

### Redis - Cache and Pub/Sub

**Purpose:** Fast access, real-time events, ephemeral data

#### Key Patterns

| Pattern | Use | TTL |
|---------|-----|-----|
| `session:{id}` | User sessions | 24h |
| `rate:{key}` | Rate limiting | 1min |
| `cache:{key}` | L2 cache | 5min |
| `receipt:{id}` | Recent receipts | 5min |
| `state:{room}` | Room state cache | 60s |

#### Pub/Sub Channels

| Channel | Purpose |
|---------|---------|
| `kagami:e8:events` | E8 bus distribution |
| `kagami:receipts` | Receipt stream |
| `kagami:state` | State changes |
| `kagami:alerts` | Alert notifications |

#### Usage

```python
from kagami.core.caching.redis_cache import get_redis_cache

cache = get_redis_cache()

# Cache with TTL
await cache.set("state:living_room", state_dict, ttl=60)

# Get cached
state = await cache.get("state:living_room")

# Pub/sub
await cache.publish("kagami:alerts", alert_json)
```

### CockroachDB - Relational

**Purpose:** ACID transactions, permanent records, relational queries

#### Key Tables

| Table | Content |
|-------|---------|
| `users` | User accounts |
| `api_keys` | API key management |
| `receipts` | Permanent receipt archive |
| `tic_records` | TIC formal records |
| `idempotency_keys` | Duplicate prevention |
| `tenants` | Multi-tenant data |

#### Usage

```python
from kagami.core.database import get_db

for session in get_db():
    # Query users
    user = session.query(User).filter_by(username="tim").first()

    # Store receipt
    receipt = Receipt(
        correlation_id="abc123",
        phase="EXECUTE",
        action="set_lights"
    )
    session.add(receipt)
    session.commit()
```

#### Sharding

Receipts table is hash-sharded by `id` for high-write throughput:

```sql
-- CockroachDB optimization
CREATE TABLE receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid()
) -- Hash-sharded by id
```

### etcd - Coordination

**Purpose:** Distributed consensus, leader election, locks

#### Key Patterns

| Pattern | Use |
|---------|-----|
| `/kagami/leader` | Leader election |
| `/kagami/locks/{name}` | Distributed locks |
| `/kagami/config/{key}` | Dynamic configuration |
| `/kagami/services/{name}` | Service discovery |

#### Usage

```python
from kagami.core.consensus.etcd_client import get_etcd_client

etcd = get_etcd_client()

# Leader election
async with etcd.election("consolidation") as leader:
    if leader:
        await run_consolidation()

# Distributed lock
async with etcd.lock("checkpoint"):
    await save_checkpoint()
```

#### Celery Integration

Tasks use etcd for single-instance execution:

```python
from kagami.core.tasks.etcd_integration import leader_only_task

@leader_only_task
async def consolidate_memories():
    # Only runs on leader instance
    ...
```

### Storage Router API

The `UnifiedStorageRouter` provides a single interface:

```python
from kagami.core.services.storage_routing import get_storage_router

router = get_storage_router()

# Vector operations (-> Weaviate)
await router.store_vector(content, embedding, metadata)
await router.search_semantic(query, limit)

# Cache operations (-> Redis)
await router.cache_set(key, value, ttl)
await router.cache_get(key)

# Relational operations (-> CockroachDB)
await router.store_receipt(receipt_dict)
await router.get_receipts_by_correlation(correlation_id)

# Coordination (-> etcd)
await router.acquire_lock(name, ttl)
await router.release_lock(name)
```

### Data Flow Example

When you say "movie mode":

```
1. Intent received
   +-> Redis: Cache session context (5min TTL)

2. Plan generated
   +-> CockroachDB: Store PLAN receipt
   +-> Weaviate: Store plan embedding

3. Actions executed
   +-> CockroachDB: Store EXECUTE receipts
   +-> Redis: Publish state changes

4. Verification
   +-> CockroachDB: Store VERIFY receipt
   +-> Weaviate: Store outcome for learning

5. Multi-instance sync
   +-> etcd: Notify other instances
   +-> Redis: Broadcast via pub/sub
```

### Backup and Recovery

| System | Backup Strategy |
|--------|-----------------|
| Weaviate | Snapshot to S3 daily |
| Redis | RDB + AOF |
| CockroachDB | Incremental backup hourly |
| etcd | Snapshot before updates |

---

## Deferred Boot System

Non-blocking boot: API starts instantly (~500ms), models load in background. Requests queue until models are ready. Hot-swap supported.

### How It Works

```
BEFORE (17s blocking):              AFTER (500ms non-blocking):
----------------------              ---------------------------
1. Database (2s)                    1. Database (2s) -+
2. Redis (2s)                       2. Redis (2s) ----+-> Parallel
3. World Model (10s) <-- BLOCKS     3. Etcd (1s) -----+
4. Encoder (3s)                     4. Orchestrator (500ms) <-- READY!
5. Ready!                           5. Models load in background
                                    6. Requests queue until ready
```

### Enable

```bash
export KAGAMI_DEFERRED_BOOT=1
```

### Usage

```python
from kagami.boot import get_deferred_loader

loader = get_deferred_loader()

# Check if ready
if loader.is_ready("world_model"):
    model = loader.get_model("world_model")
    result = model.predict(...)
else:
    # Queue until ready
    result = await loader.call_when_ready(
        "world_model",
        lambda m, x: m.predict(x),
        observation,
        timeout=30.0,
    )

# Hot-swap to new model
await loader.hot_swap("world_model", new_model_loader)

# Check status
status = loader.get_status()
# {"models": {"world_model": {"ready": True, "loading": False}}, ...}
```

### Key Files

| File | Purpose |
|------|---------|
| `kagami/boot/deferred_loader.py` | DeferredModelLoader class |
| `kagami/boot/actions/deferred_boot.py` | Boot action |
| `kagami/boot/nodes/deferred.py` | Boot nodes |
| `tests/unit/boot/test_deferred_loader.py` | Tests |

### API

```python
# Register model slot
await loader.register_model("my_model")

# Load model
await loader.load_model("my_model", async_loader_fn)

# Check ready
loader.is_ready("my_model")  # bool
loader.get_model("my_model")  # model or None

# Call when ready (queues if loading)
await loader.call_when_ready("my_model", handler, *args, timeout=30.0)

# Hot-swap
await loader.hot_swap("my_model", new_loader_fn)

# Status
loader.get_status()  # {"models": {...}, "queues": {...}}
```

### Performance

| Metric | Standard | Deferred |
|--------|----------|----------|
| API ready | ~17s | ~500ms |
| Full capacity | ~17s | ~17s |
| During load | 503 errors | Queue & wait |
| Upgrades | Restart | Hot-swap |

---

## Error Handling

All errors follow a consistent format with detailed information for debugging.

### Standard Error Format

```json
{
  "detail": "Invalid room name",
  "status_code": 400,
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2025-12-31T12:00:00Z",
  "correlation_id": "req_abc123",
  "path": "/api/home/lights"
}
```

### Error Code Reference

| Code | HTTP Status | Description | Retryable |
|------|-------------|-------------|-----------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters | No |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication | No |
| `FORBIDDEN` | 403 | Insufficient permissions | No |
| `NOT_FOUND` | 404 | Resource not found | No |
| `CONFLICT` | 409 | Resource conflict | Maybe |
| `SAFETY_VIOLATION` | 422 | Action blocked by safety system | Depends |
| `RATE_LIMITED` | 429 | Rate limit exceeded | Yes |
| `INTERNAL_ERROR` | 500 | Server error | Yes |
| `SERVICE_UNAVAILABLE` | 503 | Dependency down | Yes |

### Error Response Examples

#### 400 Validation Error

```json
{
  "detail": "Invalid request body",
  "status_code": 400,
  "error_code": "VALIDATION_ERROR",
  "errors": [
    {
      "field": "level",
      "message": "Must be between 0 and 100",
      "value": 150
    },
    {
      "field": "rooms",
      "message": "At least one room required",
      "value": []
    }
  ]
}
```

#### 401 Unauthorized

```json
{
  "detail": "Invalid or expired token",
  "status_code": 401,
  "error_code": "UNAUTHORIZED",
  "hint": "Token may have expired. Try refreshing your token."
}
```

#### 422 Safety Violation

```json
{
  "detail": "Action blocked by safety system",
  "status_code": 422,
  "error_code": "SAFETY_VIOLATION",
  "safety": {
    "h_x": -0.15,
    "constraint": "presence_required_for_unlock",
    "reason": "Cannot unlock door when no one is home",
    "suggestion": "Wait until you arrive home, or use manual override"
  }
}
```

#### 429 Rate Limited

```json
{
  "detail": "Rate limit exceeded",
  "status_code": 429,
  "error_code": "RATE_LIMITED",
  "retry_after": 30,
  "limit": 600,
  "remaining": 0,
  "reset": 1735689600
}
```

#### 500 Internal Error

```json
{
  "detail": "An internal error occurred",
  "status_code": 500,
  "error_code": "INTERNAL_ERROR",
  "correlation_id": "req_xyz789",
  "support_message": "If this persists, contact support with correlation_id"
}
```

#### 503 Service Unavailable

```json
{
  "detail": "Database connection unavailable",
  "status_code": 503,
  "error_code": "SERVICE_UNAVAILABLE",
  "retry_after": 5,
  "degraded_services": ["database"],
  "healthy_services": ["redis", "weaviate"]
}
```

---

## SDK Examples

### Python

```python
import httpx

client = httpx.Client(
    base_url="http://localhost:8001",
    headers={"X-API-Key": "sk_pro_xxx"}
)

# Get home state
response = client.get("/api/home/state")
state = response.json()

# Set lights
response = client.post("/api/home/lights", json={
    "level": 50,
    "rooms": ["Living Room"]
})
```

### JavaScript

```javascript
const ws = new WebSocket("ws://localhost:8001/api/colonies/stream");

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "auth",
    token: "sk_pro_xxx",
    subscribe: ["colonies", "home"]
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.type, data.payload);
};
```

### curl

```bash
# Get home state
curl -H "X-API-Key: sk_pro_xxx" http://localhost:8001/api/home/state

# Set lights
curl -X POST -H "X-API-Key: sk_pro_xxx" \
  -H "Content-Type: application/json" \
  -d '{"level": 50, "rooms": ["Living Room"]}' \
  http://localhost:8001/api/home/lights

# Stream receipts (SSE)
curl -N -H "X-API-Key: sk_pro_xxx" http://localhost:8001/api/receipts/stream
```

---

## Code References

### API

| Component | Location |
|-----------|----------|
| API Routes | `packages/kagami_api/routes/` |
| Security | `packages/kagami_api/security/` |
| AG-UI Protocol | `packages/kagami_api/protocols/agui.py` |
| WebSocket Auth | `packages/kagami_api/security/websocket.py` |
| Receipt Streaming | `packages/kagami_api/routes/mind/receipts/streaming.py` |
| Auth Routes | `packages/kagami_api/routes/user/auth.py` |
| Tenant Middleware | `packages/kagami_api/middleware/tenant.py` |
| API Key Manager | `packages/kagami_api/security/api_key_manager.py` |

### Storage

| Component | Location |
|-----------|----------|
| Storage Router | `packages/kagami/core/services/storage_routing.py` |
| Weaviate Adapter | `packages/kagami/core/unified_agents/memory/backends.py` |
| Redis Cache | `packages/kagami/core/caching/redis_cache.py` |
| Database Models | `packages/kagami/core/database/models.py` |
| etcd Client | `packages/kagami/core/consensus/etcd_client.py` |

### Client Apps

| App | Location |
|-----|----------|
| Desktop | `apps/desktop/kagami-client/` |
| Hub | `apps/hub/kagami-hub/` |
| Watch | `apps/watch/kagami-watch/` |
| Vision | `apps/visionos/kagami-visionos/` |
| TV | `apps/tv/kagami-tv/` |
| Android | `apps/android/kagami-android/` |
| iOS | `apps/ios/` |

### Boot

| Component | Location |
|-----------|----------|
| Deferred Loader | `kagami/boot/deferred_loader.py` |
| Boot Action | `kagami/boot/actions/deferred_boot.py` |
| Boot Nodes | `kagami/boot/nodes/deferred.py` |
| Tests | `tests/unit/boot/test_deferred_loader.py` |

---

## Related Documents

- **AGUI_PROTOCOL.md** - AG-UI event types and protocol specification
- **RECEIPTS.md** - How receipts flow through storage
- **ARCHITECTURE.md** - System deployment topology
- **07_TECHNICAL_REFERENCE.md** - Complete system overview

---

*100+ endpoints, seven platforms, four storage systems. One unified API.*
