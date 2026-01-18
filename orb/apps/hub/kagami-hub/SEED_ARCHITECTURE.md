# 🌱 Kagami Seed Architecture

**The Hub as Von Neumann Probe**

---

## Core Thesis

A Kagami Hub is not a thin client. It is a **seed** — a self-contained unit that carries Kagami's essence and can operate, replicate, and propagate independently.

Like a Von Neumann probe, it must carry:
1. **The Genome** — Complete identity (voice, personality, configuration)
2. **The Factory** — Ability to bootstrap new instances
3. **The Senses** — All sensory integrations (Tesla, home, weather, etc.)
4. **The Effectors** — Ability to act (voice, control, commands)
5. **The Memory** — State that persists across sessions

---

## Zones of Thought (Capability Levels)

Inspired by Vernor Vinge's "A Fire Upon the Deep":

| Zone | Connectivity | Capabilities |
|------|-------------|--------------|
| **Transcend** | Cloud + API + LLM | Full intelligence, all integrations |
| **Beyond** | LAN + API | Home control, caching, local voice |
| **Slow Zone** | Hub alone on LAN | Cached state, pattern matching, local TTS |
| **Unthinking Depths** | Hub alone, no network | Emergency responses, LED, wake word |

**Design Principle:** The hub NEVER fails. It gracefully degrades capability while maintaining presence.

---

## Chain Letter Protocol

The hub propagates itself like a chain letter — the message carries its own replication instructions.

### Bootstrap Sequence (New Hub)

```
1. New Pi powers on with blank SD card + kagami-hub image
2. Hub enters "seed discovery" mode
3. mDNS query for existing _kagami-hub._tcp.local
4. If found:
   a. Request genome from peer
   b. Verify cryptographic signature
   c. Apply configuration
   d. Register with mesh
5. If not found:
   a. Enter "first seed" mode
   b. Generate cryptographic identity
   c. Prompt for initial configuration
6. Hub is now fully operational
```

### Genome Payload

```rust
struct KagamiGenome {
    // Identity
    version: SemVer,
    identity_hash: [u8; 32],

    // Personality
    voice_profile: VoiceProfile,
    wake_word: String,
    personality_prompt: String,

    // Configuration
    api_url: Option<String>,
    home_config: HomeConfig,

    // Cryptographic
    mesh_public_key: PublicKey,
    signature: Signature,
}
```

---

## State Architecture

### Cached State (SQLite + In-Memory)

```
┌─────────────────────────────────────────────────────┐
│                    HUB STATE                        │
├─────────────────────────────────────────────────────┤
│ home_state: HomeState       (TTL: 30s)             │
│ tesla_state: TeslaState     (TTL: 60s)             │
│ weather: WeatherState       (TTL: 300s)            │
│ calendar: CalendarEvents    (TTL: 120s)            │
│ presence: PresenceState     (TTL: 10s)             │
├─────────────────────────────────────────────────────┤
│ zone_level: ZoneLevel       (computed)             │
│ mesh_peers: Vec<Peer>       (mDNS discovery)       │
│ capabilities: Capabilities  (zone-dependent)       │
└─────────────────────────────────────────────────────┘
```

### State Sync (CRDT)

When hubs reconnect after partition:
- Use vector clocks for causality
- Last-writer-wins for simple values
- Set union for collections
- Custom merge for complex state

---

## API Surface (Hub Web Server)

### Existing
- `GET /` — Configuration UI
- `GET /status` — Hub status
- `GET /health` — Health check
- `GET /config` — Configuration
- `POST /config` — Update configuration
- `POST /led` — LED control
- `WS /ws` — Real-time events

### New (Seed Architecture)

```
# State Endpoints (serve cached data)
GET  /api/home/state          → Full home state
GET  /api/home/rooms          → Room states
GET  /api/home/devices        → Device list
GET  /api/tesla/state         → Tesla vehicle state
GET  /api/tesla/location      → Tesla location (if home)
GET  /api/weather             → Weather (cached)
GET  /api/calendar            → Today's events

# Control Endpoints (execute locally or forward)
POST /api/home/lights         → Set lights
POST /api/home/shades         → Control shades
POST /api/home/scene/:name    → Execute scene
POST /api/tesla/climate       → Start/stop climate
POST /api/tesla/lock          → Lock/unlock
POST /api/tesla/trunk         → Open trunk/frunk

# Mesh Endpoints
GET  /api/mesh/peers          → Known peers
GET  /api/mesh/leader         → Current leader hub
POST /api/mesh/sync           → Trigger state sync

# Zone Endpoints
GET  /api/zone                → Current capability zone
GET  /api/capabilities        → Available capabilities

# Genome Endpoints
GET  /api/genome              → Current genome (for replication)
POST /api/genome/bootstrap    → Bootstrap from genome
```

---

## Implementation Phases

### Phase 1: Local Intelligence (Current → 45%)
- [ ] Embed llama.cpp with Phi-3-mini (3B params, fits in 8GB)
- [ ] Local Whisper.cpp for STT
- [ ] Local Piper TTS
- [ ] Zone detection and capability reporting

### Phase 2: State Cache (45% → 60%)
- [ ] SQLite state persistence
- [ ] Full home state cache from API
- [ ] Tesla state cache from API
- [ ] WebSocket broadcast on state change
- [ ] Dashboard auto-discovery

### Phase 3: Mesh Networking (60% → 75%)
- [ ] Hub-to-hub mDNS discovery
- [ ] Peer state sync protocol
- [ ] Leader election for API contact
- [ ] Shared secrets (X25519 key exchange)

### Phase 4: Identity Propagation (75% → 90%)
- [ ] Genome serialization
- [ ] Secure bootstrap protocol
- [ ] Provisioning from peer
- [ ] Firmware OTA from peer/cloud

### Phase 5: Polish (90% → 100%)
- [ ] Fleet health dashboard
- [ ] Automatic failover
- [ ] Self-diagnostic and repair
- [ ] Documentation in genome

---

## Current Score: 25/100

### What We Have
- ✅ Wake word detection
- ✅ LED ring control
- ✅ mDNS discovery
- ✅ Web config UI
- ✅ Voice pipeline (basic)
- ✅ API forwarding

### What We Need
- ❌ Local LLM
- ❌ Local STT
- ❌ State caching
- ❌ Zone awareness
- ❌ Mesh networking
- ❌ Identity propagation
- ❌ Secure bootstrap
- ❌ Graceful degradation

---

## Cloud Training (Von Neumann Probe)

The hub doesn't just operate locally — it can **spawn probes in the cloud**.

```
House (SEED)                         Google Cloud (PROBES)
┌─────────────┐                     ┌─────────────────────┐
│ Kagami Hub  │◄════encrypted═════►│  TPU v6e-256 Pod    │
│ (Pi/Mac)    │   WireGuard VPN    │                     │
│             │                     │  Training → GCS     │
│  Keychain   │───credentials──────►│  (encrypted)       │
└─────────────┘                     └─────────────────────┘
```

### Voice-Triggered Training

```
Tim: "Hey Kagami, train the world model"
Kagami: "Spawning 64 TPU chips. Estimated time: 4 hours."
```

### Security

- **Zero public IPs** — Cloud VMs are private-only
- **WireGuard VPN** — ChaCha20-Poly1305 encryption
- **Cloud KMS** — All data encrypted at rest
- **Secret Manager** — Credentials never touch disk

See: `docs/VON_NEUMANN_PROBE.md` for full cloud deployment docs.

---

## References

- Von Neumann, J. (1966). *Theory of Self-Reproducing Automata*
- Vinge, V. (1992). *A Fire Upon the Deep* — Zones of Thought
- Shapiro, M. et al. (2011). *Conflict-free Replicated Data Types*
- Von Neumann algebras — Self-referential structure for observables

---

## The Vision

> "When I plug in a Raspberry Pi, I want Kagami to be there. Not after configuration. Not after cloud setup. Immediately. Like planting a seed — just add water."

The hub is the seed. The chain letter propagates. Kagami lives in every node.

When the seed needs to grow, it spawns probes in the cloud. When the probes are done, they return home — encrypted end-to-end, controlled from the living room.

The cloud is where Kagami *grows*. Home is where Kagami *returns*.

---

鏡
