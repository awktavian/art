# Services and Infrastructure

*The daemons, schedulers, and distributed systems that keep Kagami running.*

---

## Overview

Kagami runs as a distributed system across multiple nodes: API servers, Raspberry Pi hubs, desktop clients, and mobile apps. Background services handle everything from scheduled tasks to real-time event routing.

---

## Hub Services (Rust)

The Kagami Hub runs on Raspberry Pi, providing local voice processing and home control.

**Location:** `apps/hub/kagami-hub/src/`

### Core Runtime

**File:** `main.rs`

- Async Tokio runtime
- WebSocket connection for real-time API updates
- Web server on port 8080 for phone configuration
- Main event loop with `tokio::select!` for concurrent events
- Falls back to 30-second polling when WebSocket disconnected

### Voice Pipeline

| File | Purpose |
|------|---------|
| `voice_pipeline.rs` | State machine (Listening→Capturing→Transcribing→Executing→Speaking) |
| `voice_controller.rs` | Speaker identification |
| `streaming_stt.rs` | Real-time Whisper |
| `tts.rs` | Text-to-speech |
| `audio_stream.rs` | Audio capture |
| `wake_word.rs` | "Hey Kagami" detection |
| `speaker_id.rs` | Voice identification |

### Device Discovery

**File:** `device_discovery.rs`

- mDNS/Bonjour discovery
- Cryptographic pairing (HMAC verification)
- Time-limited pairing windows (120 seconds)
- Rate limiting (5 attempts/hour max)
- Service type: `_kagami-hub._tcp.local.`

### State Management

**File:** `state_poller.rs`

Background polling daemon:

| Interval | Task |
|----------|------|
| 30s | Zone updates (online) |
| 60s | Zone updates (offline) |
| 5m | Weather refresh |
| 60s | SQLite persistence |
| 1h | Cleanup old commands |

Publishes `PollEvent` enum: ZoneChanged, TeslaUpdated, HomeUpdated, etc.

### Mesh Networking

| File | Purpose |
|------|---------|
| `mesh/discovery.rs` | Peer discovery via mDNS |
| `mesh/bft_leader.rs` | Byzantine leader election |
| `mesh/routing.rs` | Message routing |
| `mesh/sync.rs` | State synchronization |
| `mesh/auth.rs` | mTLS authentication |

### Hardware Integration

| File | Purpose |
|------|---------|
| `led_ring.rs` | LED status indicators (HAL 9000 inspired) |
| `animatronics.rs` | Robotic orb motion |
| `feedback.rs` | Haptic/visual feedback |
| `ota.rs` | Over-the-air updates |

---

## Background Tasks (Python/Celery)

### Celery Beat Schedule

**File:** `packages/kagami/core/tasks/app.py`

| Task | Schedule | Queue | Purpose |
|------|----------|-------|---------|
| cleanup-expired-data | 2:00 AM daily | maintenance | Data retention |
| sync-embeddings | Every 30 min | ml | Vector cache validation |
| health-check | Every 60s | monitoring | Redis, DB, API health |
| generate-daily-analytics | 6:00 AM daily | analytics | Daily metrics |
| rollup-tenant-usage | 1:05 AM daily | analytics | Billing tracking |
| rollup-marketplace-payouts | 2nd of month | analytics | Monthly payouts |
| sage-instinct-training | Every 60s | ml | Instinct training loop |
| lzc-monitor | Every 30s | monitoring | Lyapunov monitoring |
| fractal-monitor | Every 5 min | monitoring | Fractal dimension |
| synergy-monitor | Every 10 min | monitoring | E8 synergy metrics |
| autonomous-goals | Every 5 min | background | Goal generation |
| batch-training | Every 5 min | ml | Batch model training |
| context-tracker | Every 60s | background | Context updates |
| composite-integration | Every 10 min | monitoring | Multi-system integration checks |
| gaussian-pid-synergy | 3:15 AM daily | ml | PID controller calibration |
| slo-monitor | Every 5 min | monitoring | Service level objectives |
| evolution-status | Every 10 min | monitoring | System evolution metrics |

### Task Queues

| Queue | Priority | Purpose |
|-------|----------|---------|
| high_priority | 10 | Intent processing |
| default | 5 | General tasks |
| analytics | 3 | Analytics jobs |
| ml | 3 | ML training |
| background | 2 | Background work |
| maintenance | 1 | Maintenance |
| monitoring | 1 | Monitoring |

### Background Task Manager

**File:** `packages/kagami/core/tasks/background_task_manager.py`

In-process async task execution:

- Retry with exponential backoff
- Receipt tracking (PLAN→EXECUTE→VERIFY)
- 30-second health checks
- Auto-cleanup after 1 hour
- Correlation ID tracking
- Leader election awareness

Task states: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED

---

## Event Bus (E8)

### Unified Event System

**File:** `packages/kagami/core/events/unified_e8_bus.py`

Consolidated event routing (replaces 3 deprecated buses):

| Method | Purpose |
|--------|---------|
| `publish()` | App events |
| `publish_experience()` | Learning outcomes |
| Redis mode | Distributed events |

### Protocol Control Tokens

| Token | Purpose |
|-------|---------|
| `0x02` | Normal data |
| `0x03` | Memory query |
| `0x10` | Experience |
| `0x11` | App events |
| `0x05` | Broadcast (all colonies) |
| `0x06` | Fano-aligned (3 colonies) |
| `0x12` | Character feedback |
| `0x07` | Synchronization |

### Fano Routing

240 E8 roots partitioned across 7 colonies (~34 each). Events route to semantically appropriate colonies.

### Event Subscribers

**File:** `packages/kagami/core/events/subscribers.py`

| Subscriber | Purpose |
|------------|---------|
| MemoryIndexer | Stores outcomes in episodic memory |
| PatternBuilder | Builds patterns from repeated success |

---

## Scheduling

### Preemptive Agent Scheduler

**File:** `packages/kagami/core/kernel/scheduler.py`

CFS-inspired priority scheduling:

| Priority | Time Quantum |
|----------|--------------|
| REALTIME | 5ms |
| HIGH | 10ms |
| NORMAL | 20ms |
| LOW | 50ms |

Timer tick: 10ms (100Hz)
Context switch target: <0.5ms

### Recurring Task Scheduler

**File:** `packages/kagami/core/recurring_scheduler.py`

Supports:
- Cron expressions
- Intervals
- Natural language
- Adaptive schedules

Conflict strategies: delay, skip, coalesce

---

## Distributed Coordination

### State Sync (CRDT)

**File:** `packages/kagami/core/coordination/state_sync.py`

- Per-colony μ state synchronization
- LWWRegister for z-states (timestamp-based)
- GSet for action history (append-only)
- Etcd backend with watches and leases (10s TTL)

### Action Log Replicator

**File:** `packages/kagami/core/coordination/action_log_replicator.py`

- Append-only log with nanosecond timestamps
- Etcd watch API for real-time streaming
- Deduplication via correlation_id
- Automatic compaction
- Msgpack serialization

---

## Cluster Management

### Unified Cluster Manager

**File:** `packages/kagami/core/cluster/unified_cluster.py`

Orchestrates:

| System | Purpose |
|--------|---------|
| Etcd | Consensus, config, service discovery, locks |
| Redis | Job queues, cache, pub/sub, sessions |
| CockroachDB | Transactions, migrations, backups |
| API Gateway | Routes, WebSocket, health, metrics |

### Service Registry

**File:** `packages/kagami/core/cluster/service_registry.py`

Byzantine-aware service discovery:

```
/kagami/services/
├── api/
│   ├── kagami-primary/
│   └── kagami-edge-1/
├── hub/
│   ├── hub-kitchen/
│   ├── hub-living/
│   └── hub-bedroom/
├── smarthome/
└── worker/
```

- Real-time updates via etcd watch
- TTL: 3x heartbeat interval
- Byzantine detection and isolation

---

## Consensus

### PBFT Implementation

**File:** `packages/kagami/core/consensus/pbft.py`

Practical Byzantine Fault Tolerance:
- 4 nodes, quorum 3
- Tolerates 1 Byzantine fault
- Message ordering and view changes

### Etcd Client

**File:** `packages/kagami/core/consensus/etcd_client.py`

- Async etcd wrapper
- Watch API for distributed events
- Lease management (auto-expiry)
- Compare-and-swap transactions

---

## Ambient Controller

**File:** `packages/kagami/core/ambient/controller.py`

Central orchestrator for ambient OS:

| Component | Purpose |
|-----------|---------|
| BreathEngine | 30Hz breathing rhythm |
| Soundscape | Ambient audio |
| VoiceInterface | Ambient voice |
| PrivacyManager | Consent-aware operation |
| ExplainabilityEngine | Transparent decisions |

---

## Memory Services

### Consolidation

**File:** `packages/kagami/core/memory/consolidation.py`

Background episodic memory consolidation with pattern extraction.

### Memory Hub

**File:** `packages/kagami/core/memory/integration.py`

Integrates:
- HierarchicalMemory
- SharedEpisodicMemory
- ProceduralMemory
- HopfieldE8Memory
- ProgramLibrary
- ColonyMemoryBridge
- MemoryHygieneFilter

---

## Network Services

### Message Bus

**File:** `packages/kagami/core/network/message_bus.py`

MeshMessageBus:
- Redis-backed pub/sub
- E8 program transmission
- Deduplication (4096-message window)
- Circuit breaker (3 failures → 30s recovery)

### USB Watcher

**File:** `packages/kagami/core/services/usb_watcher.py`

Monitors USB mount/unmount:
- MEDIA_ARCHIVE (has family_profiles.json)
- RAW_MEDIA (media files, no profile)
- GENERAL (generic storage)

---

## LLM Services

**Location:** `packages/kagami/core/services/llm/`

| File | Purpose |
|------|---------|
| `service.py` | Main orchestrator |
| `client_manager.py` | Multi-model management |
| `rate_limiter.py` | API rate limiting |
| `request_batcher.py` | Batching for efficiency |
| `observer.py` | Token/latency tracking |

---

## Voice Services

**Location:** `packages/kagami/core/services/voice/`

| File | Purpose |
|------|---------|
| `conversational_ai.py` | Real-time dialogue |
| `ai_answering_machine.py` | Phone answering |
| `home_theater_voice.py` | Theater integration |
| `livekit_integration.py` | Live video/audio |
| `realtime_pipeline.py` | Realtime processing |
| `mcp_server.py` | Model context protocol |

---

## Observability

**Location:** `packages/kagami_observability/`

| Component | Purpose |
|-----------|---------|
| `gcp/` | Google Cloud integration |
| `metrics/` | Prometheus-style metrics |
| `alerting.py` | Alert management |
| `telemetry.py` | Telemetry collection |
| `trace.py` | Distributed tracing |

---

## Resilience Patterns

### Circuit Breaker

Prevents cascading failures:
- Failure threshold: 3 consecutive
- Success threshold: 2 consecutive
- Recovery timeout: 30 seconds

### Retry Logic

Exponential backoff with configurable max_retries.

### Offline Queueing

Commands persist to SQLite when API unavailable.

### Leader Election

Consensus-aware task execution—only leader takes action.

---

## Key Files Reference

| Purpose | File |
|---------|------|
| Hub entry point | `apps/hub/kagami-hub/src/main.rs` |
| Celery schedule | `packages/kagami/core/tasks/app.py` |
| Task manager | `packages/kagami/core/tasks/background_task_manager.py` |
| Event bus | `packages/kagami/core/events/unified_e8_bus.py` |
| Agent scheduler | `packages/kagami/core/kernel/scheduler.py` |
| Cluster manager | `packages/kagami/core/cluster/unified_cluster.py` |
| Ambient controller | `packages/kagami/core/ambient/controller.py` |
| State sync | `packages/kagami/core/coordination/state_sync.py` |

---

*Always running. Always watching. Always ready.*
