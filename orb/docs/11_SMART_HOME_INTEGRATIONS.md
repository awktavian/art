# Smart Home Integrations

*Every device, every service, every connection to the physical world.*

---

## Overview

Kagami integrates with 28 hardware platforms and services through direct API implementations. No cloud middlemen where avoidable—direct connections for lowest latency and highest reliability.

**Location:** `packages/kagami_smarthome/integrations/`

---

## Integration Summary

| Category | Count | Examples |
|----------|-------|----------|
| Lighting & Shades | 3 | Control4, Govee, Oelo |
| Climate & HVAC | 2 | Mitsubishi, Weather |
| Security & Locks | 3 | Control4, August, Envisalink |
| Entertainment | 4 | Denon, LG TV, Samsung TV, Spotify |
| Appliances | 5 | LG ThinQ, Sub-Zero/Wolf, Electrolux, TOTO, SmartThings |
| Health & Sleep | 2 | Apple Health, Eight Sleep |
| Vehicle | 1 | Tesla Fleet API |
| Network & Cameras | 1 | UniFi |
| Maker Equipment | 2 | Formlabs, Glowforge |
| Location | 3 | Apple Find My, Maps, Tesla Geo |
| Wearables | 1 | Meta Smart Glasses |
| System | 1 | Kagami Host |

---

## Core Integrations

### Control4 (Primary Home Automation)

**File:** `control4.py`

The backbone of the house. 41 lights, 12 shades, 26 audio zones.

| Capability | Count | Protocol |
|------------|-------|----------|
| Lighting | 41 fixtures | Director API |
| Shades | 12 windows | Director API |
| Audio | 26 zones | Director API |
| Security | DSC panel | Director API |
| Locks | 2 August | Director API |
| Fireplace | 1 Montigo | Director API |
| TV Mount | MantelMount | Director API |

### Tesla Fleet API

**File:** `tesla/tesla.py`

Real-time vehicle telemetry and control.

| Feature | Detail |
|---------|--------|
| Telemetry | 500ms SSE streaming |
| Commands | 65 vehicle commands |
| Telemetry Fields | 78 |
| Alerts | 18,769 definitions |
| Geofencing | 5 zones (1km, 500m, home, departing, away) |

Categories: Charging, Climate, Security, Media, Navigation

### Eight Sleep

**File:** `eight_sleep.py`

Sleep detection and bed temperature control.

| Sensor | Purpose |
|--------|---------|
| Presence | In bed detection |
| Heart rate | Sleep stage inference |
| Movement | Wake detection |
| Temperature | Each side independently |

### UniFi

**File:** `unifi.py`

Network monitoring and camera integration.

| Feature | Detail |
|---------|--------|
| Cameras | 4x AI Pro with person/package detection |
| Network | 38 WiFi clients |
| Presence | Device-based occupancy |

---

## Entertainment

### Denon AV Receiver

**File:** `denon.py`

Home theater control via telnet.

| Capability | Model |
|------------|-------|
| Processor | AVR-A10H |
| Channels | 15.4 |
| Protocol | Telnet |

### LG TV

**File:** `lg_tv.py`

webOS TV control via WebSocket.

### Samsung TV

**File:** `samsung_tv.py`

Tizen Smart TV control via REST/WebSocket.

### Spotify

**File:** `spotify.py`

Music streaming via librespot-python.

| Feature | Detail |
|---------|--------|
| Playback | Full control |
| Queue | Management |
| Search | Track/album/artist |
| Connect | Device handoff |

---

## Appliances

### LG ThinQ

**File:** `lg_thinq.py`

Smart appliance control via cloud API.

| Appliance | Capabilities |
|-----------|--------------|
| Refrigerator | Temperature, door status |
| Oven | Preheat, timer |
| Washer | Cycle control, status |
| Dryer | Cycle control, status |

### Sub-Zero / Wolf / Cove

**File:** `subzero_wolf.py`

Premium kitchen appliances.

| Brand | Products |
|-------|----------|
| Sub-Zero | Refrigerator, freezer |
| Wolf | Range, oven |
| Cove | Dishwasher |

### Electrolux

**File:** `electrolux.py`

Washer and dryer monitoring.

### TOTO

**File:** `toto.py`

Smart toilet control and monitoring.

---

## Health & Biometrics

### Apple Health

**File:** `apple_health.py`

HealthKit data integration.

| Metric | Detail |
|--------|--------|
| Heart rate | Continuous |
| Sleep | Stages and duration |
| Activity | Steps, calories, distance |
| Workouts | Type, duration, metrics |
| Blood oxygen | SpO2 |
| Respiratory rate | Breaths per minute |

### Eight Sleep

See Core Integrations above.

---

## Security & Locks

### August Smart Locks

**File:** `august.py`

Direct lock control via yalexs API.

| Lock | Location |
|------|----------|
| Entry | Front door |
| Game Room | Basement ADU |

### Envisalink (DSC)

**File:** `envisalink.py`

Security panel integration via TPI protocol.

| Feature | Detail |
|---------|--------|
| Zones | Armed state |
| Sensors | Door/window contacts |
| Temperature | Zone temps |

### Apple Find My

**File:** `apple_findmy.py`

Device location via iCloud API.

| Feature | Detail |
|---------|--------|
| Location | Real-time device position |
| Play Sound | Find lost device |
| Lost Mode | Lock and message |

---

## Climate

### Mitsubishi HVAC

**File:** `mitsubishi.py`

Multi-zone heating and cooling.

| Feature | Detail |
|---------|--------|
| Zones | Multi-zone control |
| Modes | Heat, cool, auto, dry |
| Vanes | Horizontal/vertical position |

---

## Maker Equipment

### Formlabs Form 4

**File:** `formlabs.py`

Resin 3D printer control via local API.

| Sensor | Purpose |
|--------|---------|
| Status | idle/printing/complete |
| Progress | Job percentage |
| Resin | Tank level |

### Glowforge Pro

**File:** `glowforge.py`

Laser cutter monitoring (limited—no official API).

| Sensor | Purpose |
|--------|---------|
| Status | idle/cutting/complete |
| Lid | Open/closed |

---

## Lighting

### Govee

**File:** `govee.py`

Smart light strips and accessories.

### Oelo

**File:** `oelo.py`

Outdoor lighting control via HTTP API.

---

## Wearables

### Meta Smart Glasses

**File:** `meta_glasses.py`

Visual context and private audio.

| Feature | Detail |
|---------|--------|
| Camera | POV visual context |
| Audio | 5-mic array input |
| Speakers | Open-ear private audio |
| Context | Scene understanding |

---

## Location Services

### Maps

**File:** `maps.py`

Google Maps integration.

| Feature | Detail |
|---------|--------|
| Distance | ETA to home |
| Traffic | Route conditions |

### Tesla Geofencing

**File:** `tesla/geo.py`

Vehicle-based presence detection.

| Zone | Distance | Trigger |
|------|----------|---------|
| ARRIVAL_IMMINENT | 1 km | Begin prep |
| ARRIVING | 500 m | Open garage |
| HOME | In garage | Welcome |
| DEPARTING | Leaving | Check security |
| AWAY | > 1 km | Full away mode |

---

## Additional Integrations

### SmartThings

**File:** `smartthings.py`

Samsung SmartThings Cloud integration.

| Feature | Detail |
|---------|--------|
| Authentication | Personal Access Token (PAT) |
| Devices | Samsung appliances, third-party |
| Mode | Cloud-based |

### Weather Service

**File:** `weather.py`

OpenWeatherMap integration for environmental context.

| Feature | Detail |
|---------|--------|
| Data | Real-time weather, 48-hour forecast |
| Coverage | Cloud coverage for shade optimization |
| Portability | Uses central location config |

### Kagami Host System

**File:** `kagami_host.py`

Mac Studio self-monitoring integration.

| Feature | Detail |
|---------|--------|
| Hardware | Apple M3 Ultra, 512GB RAM |
| Monitoring | CPU, memory, thermal, network |
| Alerts | High load, low disk, temperature |

---

## API Types Used

| Protocol | Integrations |
|----------|--------------|
| REST/HTTP | Most cloud services |
| WebSocket | LG TV, Samsung TV, Denon |
| OAuth 2.0 | Tesla, Spotify, Apple |
| Telnet | Denon AVR |
| TPI | Envisalink/DSC |
| SSE | Tesla Fleet Telemetry |
| Local API | Control4, Formlabs |
| mDNS | Device discovery |

---

## Safety Classification

Every effector has a safety level:

| Level | Meaning | Examples |
|-------|---------|----------|
| **Safe** | No restrictions | Lights, shades, audio |
| **Filtered** | Context-dependent | Locks, fireplace |
| **Protected** | Extra verification | Security arm/disarm, Tesla unlock |

The Control Barrier Function ensures `h(x) >= 0` for all actions.

---

## Adding New Integrations

1. Create file in `packages/kagami_smarthome/integrations/`
2. Implement async `connect()`, `disconnect()`, `get_state()`
3. Define sensors and effectors
4. Register with safety classification
5. Add to `__init__.py` exports

---

## Key Files

| File | Purpose |
|------|---------|
| `__init__.py` | Central exports, all integration classes |
| `control4.py` | Primary home automation |
| `tesla/tesla.py` | Vehicle integration |
| `eight_sleep.py` | Sleep detection |
| `unifi.py` | Network and cameras |
| `apple_health.py` | Biometric data |
| `weather.py` | Environmental context |
| `smartthings.py` | Samsung cloud integration |
| `kagami_host.py` | Host system monitoring |

---

*The house is alive. Every sensor tells a story. Every effector changes the world.*
