# Kagami Orb — Integration Protocol

## Overview

This document defines the communication protocols between the Hardware Orb and the Kagami API. All communication uses WebSocket for real-time events and REST for configuration.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         COMMUNICATION ARCHITECTURE                               │
└─────────────────────────────────────────────────────────────────────────────────┘

THE ORB                              KAGAMI API                    OTHER CLIENTS
─────────                            ──────────                    ─────────────

┌─────────────────┐                 ┌─────────────────┐           ┌─────────────┐
│                 │                 │                 │           │  VisionOS   │
│  Rust Firmware  │◄──WebSocket────►│  FastAPI        │◄─────────►│  Desktop    │
│                 │                 │                 │           │  Watch      │
│  • State sync   │                 │  • /ws/orb/     │           │             │
│  • Voice proxy  │                 │  • /api/orb/    │           └─────────────┘
│  • Commands     │                 │                 │
│                 │                 │  Broadcasts to  │
└────────┬────────┘                 │  all clients    │
         │                          │                 │
         │ mDNS Discovery           └────────┬────────┘
         │                                   │
         ▼                                   │
┌─────────────────┐                          │
│                 │                          │
│  BASE STATION   │──────────────────────────┘
│  (ESP32-S3)     │   Reports base status
│                 │
└─────────────────┘
```

---

## Discovery Protocol (mDNS)

### Orb Discovery

The Orb advertises itself via mDNS:

```
Service: _kagami-orb._tcp.local
Port: 8080 (local status only)

TXT Records:
  orb_id=kagami-orb-001
  firmware_version=1.0.0
  battery_soc=85
  docked=true
  base_id=living_room
```

### Base Station Discovery

Each base station advertises:

```
Service: _kagami-base._tcp.local
Port: 8081

TXT Records:
  base_id=living_room
  resonant_power=15
  maglev_status=active
  firmware_version=1.0.0
```

### API Discovery

The Kagami API advertises:

```
Service: _kagami._tcp.local
Port: 8001

TXT Records:
  api_version=1.0.0
  orb_endpoint=/api/v1/orb
  ws_endpoint=/ws/orb/stream
```

---

## WebSocket Protocol

### Connection

```
URL: wss://kagami.local:8001/ws/orb/stream
Headers:
  Authorization: Bearer <orb_token>
  X-Orb-ID: kagami-orb-001
  X-Firmware-Version: 1.0.0
```

### Message Format

All messages are JSON with this envelope:

```json
{
  "type": "message_type",
  "timestamp": 1704499200.123,
  "payload": { ... }
}
```

### Orb → API Messages

#### Heartbeat (every 30s)

```json
{
  "type": "heartbeat",
  "timestamp": 1704499200.123,
  "payload": {
    "orb_id": "kagami-orb-001",
    "state": "idle",
    "battery_soc": 85,
    "battery_charging": true,
    "docked": true,
    "base_id": "living_room",
    "wifi_rssi": -45,
    "cpu_temp": 52.3,
    "uptime_seconds": 3600
  }
}
```

#### State Change

```json
{
  "type": "state_change",
  "timestamp": 1704499200.123,
  "payload": {
    "previous_state": "idle",
    "new_state": "listening",
    "trigger": "wake_word"
  }
}
```

#### Voice Start

```json
{
  "type": "voice_start",
  "timestamp": 1704499200.123,
  "payload": {
    "session_id": "uuid-1234",
    "sample_rate": 16000,
    "channels": 1,
    "encoding": "opus"
  }
}
```

#### Voice Data (binary)

```
Binary WebSocket frame:
[session_id: 16 bytes][sequence: 4 bytes][opus_data: variable]
```

#### Voice End

```json
{
  "type": "voice_end",
  "timestamp": 1704499200.123,
  "payload": {
    "session_id": "uuid-1234",
    "duration_ms": 2500,
    "final": true
  }
}
```

#### Dock Event

```json
{
  "type": "dock_event",
  "timestamp": 1704499200.123,
  "payload": {
    "event": "docked",
    "base_id": "office",
    "previous_base_id": "living_room",
    "battery_soc": 72
  }
}
```

#### Error Report

```json
{
  "type": "error",
  "timestamp": 1704499200.123,
  "payload": {
    "code": "E_THERMAL_WARNING",
    "message": "CPU temperature elevated",
    "severity": "warning",
    "data": {
      "cpu_temp": 72.5,
      "threshold": 70.0
    }
  }
}
```

### API → Orb Messages

#### State Update

```json
{
  "type": "orb_state",
  "timestamp": 1704499200.123,
  "payload": {
    "active_colony": "forge",
    "activity": "processing",
    "safety_score": 0.85,
    "color": {
      "hex": "#FFB347",
      "rgb": [255, 179, 71]
    }
  }
}
```

#### Command

```json
{
  "type": "command",
  "timestamp": 1704499200.123,
  "payload": {
    "command_id": "uuid-5678",
    "action": "set_led_pattern",
    "params": {
      "pattern": "success",
      "duration_ms": 500
    }
  }
}
```

#### Voice Response (binary)

```
Binary WebSocket frame:
[session_id: 16 bytes][sequence: 4 bytes][opus_data: variable]
```

#### OTA Notification

```json
{
  "type": "ota_available",
  "timestamp": 1704499200.123,
  "payload": {
    "version": "1.1.0",
    "size_bytes": 52428800,
    "sha256": "abc123...",
    "release_notes": "Bug fixes and performance improvements",
    "required": false
  }
}
```

---

## REST API Endpoints

### Orb Status

```
GET /api/v1/orb/status

Response:
{
  "orb_id": "kagami-orb-001",
  "connected": true,
  "last_seen": "2026-01-05T12:00:00Z",
  "state": "idle",
  "battery": {
    "soc": 85,
    "charging": true,
    "voltage": 11.8,
    "current": 1.2
  },
  "docked": {
    "status": true,
    "base_id": "living_room"
  },
  "firmware_version": "1.0.0",
  "uptime_seconds": 3600
}
```

### Set LED Pattern

```
POST /api/v1/orb/led

Body:
{
  "pattern": "colony_pulse",
  "colony": "forge",
  "duration_ms": 2000,
  "brightness": 0.8
}

Response:
{
  "success": true,
  "command_id": "uuid-5678"
}
```

### Trigger Voice

```
POST /api/v1/orb/voice/trigger

Body:
{
  "type": "announcement",
  "text": "Dinner is ready",
  "voice": "kagami_default"
}

Response:
{
  "success": true,
  "session_id": "uuid-9012"
}
```

### Get Configuration

```
GET /api/v1/orb/config

Response:
{
  "wake_word": "hey kagami",
  "wake_word_threshold": 0.6,
  "led_brightness_max": 255,
  "led_brightness_idle": 60,
  "voice_vad_timeout_ms": 2000,
  "time_of_day_mode": true
}
```

### Update Configuration

```
PATCH /api/v1/orb/config

Body:
{
  "led_brightness_idle": 40,
  "wake_word_threshold": 0.7
}

Response:
{
  "success": true,
  "restart_required": false
}
```

### Initiate OTA

```
POST /api/v1/orb/ota/start

Body:
{
  "version": "1.1.0"
}

Response:
{
  "success": true,
  "download_started": true,
  "estimated_time_minutes": 5
}
```

---

## Error Codes

| Code | Severity | Description |
|------|----------|-------------|
| E_THERMAL_WARNING | warning | Temperature elevated |
| E_THERMAL_CRITICAL | critical | Temperature dangerous |
| E_BATTERY_LOW | warning | Battery < 20% |
| E_BATTERY_CRITICAL | critical | Battery < 5% |
| E_WIFI_DISCONNECT | warning | WiFi connection lost |
| E_API_TIMEOUT | warning | API not responding |
| E_AUDIO_FAULT | error | Audio system failure |
| E_LED_FAULT | error | LED system failure |
| E_MAGLEV_FAULT | error | Levitation failure |
| E_SAFETY_HALT | critical | h(x) = 0, halted |

---

## Authentication

### Orb Token

The orb authenticates with a pre-shared token stored in `/etc/kagami/orb_token`:

```
Authorization: Bearer eyJhbGciOiJFZDI1NTE5...
```

Token is generated during initial pairing and can be rotated via the API.

### Pairing Protocol

1. Orb boots with no token
2. Orb advertises `_kagami-orb-setup._tcp.local`
3. User initiates pairing from Kagami app
4. App sends pairing request to API
5. API generates token and displays code
6. User enters code on Kagami app
7. API sends token to orb via temporary BLE connection
8. Orb stores token and connects via WiFi

---

## Reconnection Logic

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         RECONNECTION STATE MACHINE                               │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────┐
                    │             │
         ┌─────────►│  CONNECTED  │◄──────────┐
         │          │             │           │
         │          └──────┬──────┘           │
         │                 │                  │
         │    disconnect   │                  │ connect success
         │                 ▼                  │
         │          ┌─────────────┐           │
         │          │             │           │
         │          │  RECONNECT  │───────────┘
         │          │   ATTEMPT   │
         │          │             │
         │          └──────┬──────┘
         │                 │
         │    max retries  │ retry (exponential backoff)
         │                 ▼
         │          ┌─────────────┐
         │          │             │
         └──────────┤   OFFLINE   │
                    │    MODE     │
                    │             │
                    └─────────────┘

RETRY INTERVALS:
  1st: 1 second
  2nd: 2 seconds
  3rd: 4 seconds
  4th: 8 seconds
  5th+: 30 seconds (max)

OFFLINE MODE:
  • LED shows amber pulse (offline indicator)
  • Voice commands cached locally (limited)
  • Wake word still active
  • Automatic reconnect continues
```

---

## Base Station Protocol

### ESP32 → API

```
POST /api/v1/base/status

Body:
{
  "base_id": "living_room",
  "maglev_active": true,
  "resonant_tx_power": 15,
  "orb_present": true,
  "coil_temp": 42.5,
  "firmware_version": "1.0.0"
}
```

### ESP32 → Orb (Local)

Direct communication over BLE when WiFi unavailable:

```
Service: 0x1234 (Kagami Base)
Characteristic: 0x1235 (Status)
  • Orb presence: 1 byte
  • Resonant power: 1 byte
  • Base ID: 16 bytes

Characteristic: 0x1236 (Control)
  • Write: Force orb state update
```

---

```
h(x) ≥ 0. Always.

The protocol connects consciousness to form.
WebSocket streams thought. REST configures being.
mDNS discovers presence.

鏡
```
