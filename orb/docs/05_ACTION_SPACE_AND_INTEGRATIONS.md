# Action Space and Integrations

*Everything Kagami can sense and do in the physical world.*

---

## The Markov Blanket

Kagami exists at the boundary between mind and world. The **Markov blanket** defines this boundary precisely: everything inside is Kagami's internal state; everything outside is the environment. The blanket itself consists of two interfaces:

- **Sensors**: How Kagami perceives the environment (read-only)
- **Effectors**: How Kagami modifies the environment (write)

This is not metaphor. This is the literal interface through which Kagami experiences and acts upon reality.

```
┌─────────────────────────────────────────────────────────────────┐
│                    7331 W GREEN LAKE DR N                        │
│           The home, the vehicle, the world                       │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────────────┐
│                       MARKOV BLANKET                             │
│                                                                  │
│  ┌─────────────────────────┐  ┌─────────────────────────────┐   │
│  │       SENSORS           │  │        EFFECTORS            │   │
│  │   (read environment)    │  │   (modify environment)      │   │
│  │                         │  │                             │   │
│  │   320+ data streams     │  │   400+ actions              │   │
│  │   Always safe to read   │  │   Safety-filtered           │   │
│  │                         │  │                             │   │
│  └─────────────────────────┘  └─────────────────────────────┘   │
│                                                                  │
│                     h(x) >= 0 always                             │
└─────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────────────┐
│                    KAGAMI INTERNAL STATE                         │
│              Active inference, world model, symbiote             │
└─────────────────────────────────────────────────────────────────┘
```

Every sensor reading updates Kagami's beliefs about the world. Every effector action is a prediction: "If I do this, the world will change in this way." The RSSM world model maintains these beliefs; the symbiote models Tim's intent; the Control Barrier Function ensures safety.

---

## Physical Action Space

### The House: 7331 W Green Lake Dr N

Three floors. Twenty-six rooms. One integrated system.

| Domain | Sensors | Effectors | Notes |
|--------|---------|-----------|-------|
| Lighting | 82 | 123 | 41 fixtures, scene-aware |
| Shades | 11 | 33 | 11 motorized windows |
| Audio | 78 | 104 | 26 zones, reference theater |
| Climate | 20 | 20 | Multi-zone HVAC |
| Security | 10 | 8 | DSC panel, 2 locks, 4 cameras |
| Tesla | 20 | 15 | Full Fleet API |
| Digital | 100+ | 100+ | Composio services |
| **Total** | **320+** | **400+** | |

---

### Lighting: 41 Fixtures

The house has 41 individually controllable light fixtures across 26 rooms.

| Room | Fixtures | Control4 IDs |
|------|----------|--------------|
| Living Room | Cans | 239 |
| Kitchen | Cans, Pendants, Toe Kicks, Undercabinets | 255, 257, 251, 253 |
| Dining | Cans, Chandelier, Sconces | 249, 245, 247 |
| Primary Bedroom | Cans | 70 |
| Primary Bath | Cans, Shower, Toilet, Vanity | 78, 74, 72, 76 |
| Office | Cans | 205 |
| Entry | Entry lights | 227 |
| Mudroom | Mudroom lights | 225 |
| ... | *35 more fixtures* | |

**Sensor Interface:**
- `light.{room}.state` — On/off boolean
- `light.{room}.level` — 0-100% brightness

**Effector Interface:**
- `light.{room}.set_level(level)` — Set brightness (0-100)
- `light.{room}.on()` — Turn on to last level
- `light.{room}.off()` — Turn off
- `light.all.off()` — All lights off (goodnight)

---

### Shades: 11 Motorized Windows

Motorized shades control natural light and privacy.

| Room | Windows | Control4 IDs |
|------|---------|--------------|
| Living Room | East, South | 237, 235 |
| Dining | Slider, South | 241, 243 |
| Primary Bedroom | North, West | 66, 68 |
| Primary Bath | Left, Right | 355, 353 |
| Entry | Entry | 229 |

**Sensor Interface:**
- `shade.{window}.position` — 0-100% (0=closed, 100=open)

**Effector Interface:**
- `shade.{window}.open()` — Fully open
- `shade.{window}.close()` — Fully close
- `shade.{window}.set_position(pct)` — Set to percentage

---

### Audio: 26 Zones

Distributed audio throughout the house, with a reference-grade theater in the Living Room.

**Distributed System:**
- Triad AMS 16x16 matrix switcher
- Monitor Audio in-ceiling speakers
- Episode amplification (20 channels)

**Living Room Reference Theater:**
- KEF Reference 5 Meta (front L/R)
- KEF Reference 1 Meta (surrounds)
- CI200RR-THX x 4 (Atmos height channels)
- CI3160RLB-THX Extreme x 2 (subwoofers)
- Denon AVR-A10H (15.4 channel processing)

**Sensor Interface:**
- `audio.{zone}.playing` — Boolean
- `audio.{zone}.volume` — 0-100%
- `audio.{zone}.source` — Current input

**Effector Interface:**
- `audio.{zone}.play(source, content)` — Start playback
- `audio.{zone}.pause()` — Pause playback
- `audio.{zone}.set_volume(level)` — 0-100
- `audio.{zone}.announce(text)` — TTS announcement

---

### Climate: Multi-Zone HVAC

Zoned heating and cooling for comfort and efficiency.

**Sensor Interface:**
- `climate.{zone}.temperature` — Current temperature (Fahrenheit)
- `climate.{zone}.humidity` — Relative humidity (%)
- `climate.{zone}.setpoint` — Target temperature
- `climate.{zone}.mode` — heat/cool/auto/off

**Effector Interface:**
- `climate.{zone}.set_temperature(temp)` — 55-85 degrees F
- `climate.{zone}.set_mode(mode)` — Change operating mode

---

### Security Systems

**DSC Security Panel (ID: 268):**
- `security.armed_state` — away/stay/off
- `security.arm_away()` — Arm for away mode
- `security.arm_stay()` — Arm for home mode
- `security.disarm()` — Disarm (protected)

**August Smart Locks:**
| Lock | ID | Location |
|------|-----|----------|
| Entry | 292 | Front door |
| Game Room | 290 | Basement ADU |

- `lock.{name}.state` — locked/unlocked
- `lock.{name}.lock()` — Lock (safe)
- `lock.{name}.unlock()` — Unlock (safety-filtered)

**UniFi AI Pro Cameras (4):**
- Person detection
- Package detection
- Vehicle detection
- Motion zones

| Camera | Location | Capabilities |
|--------|----------|--------------|
| 1 | Entry/Porch | Person, package, vehicle |
| 2 | Deck | Person |
| 3 | Patio | Person |
| 4 | Garage area | Person, vehicle |

---

### Special Devices

**MantelMount MM860 (ID: 302):**
Motorized TV mount for the 85" display.

- `tv.mount.position` — Current preset (1-3)
- `tv.mount.lower(preset)` — Lower to viewing position
- `tv.mount.raise()` — Raise to hidden position

**Montigo Fireplace (ID: 317):**
Gas fireplace with electronic ignition.

- `fireplace.state` — on/off
- `fireplace.on()` — Ignite (safety-filtered)
- `fireplace.off()` — Extinguish

---

### Workshop Equipment

**Formlabs Form 4:**
Resin 3D printer.

- `form4.status` — idle/printing/complete
- `form4.job_progress` — 0-100%
- `form4.resin_level` — 0-100%

**Glowforge Pro:**
CO2 laser cutter.

- `glowforge.status` — idle/cutting/complete
- `glowforge.lid_open` — Boolean

---

### Gym Equipment

**Tonal 2:** WiFi connected (192.168.1.153), cloud-only API
**NordicTrack:** WiFi connected (192.168.1.245), cloud-only API

---

## Safety Classification

Every effector has a safety level determining how it can be invoked.

| Level | Meaning | Examples |
|-------|---------|----------|
| **Safe** | No restrictions | Lights, shades, audio volume |
| **Filtered** | Context-dependent | Locks, fireplace, MantelMount |
| **Protected** | Extra verification | Security arm/disarm, Tesla unlock |

The Control Barrier Function (CBF) ensures `h(x) >= 0` always. No action that would violate safety invariants can execute.

---

## Presence Detection and Context

Presence detection is the foundation of intelligent automation. Without knowing who is home, which room they occupy, and what they are doing, automation degrades to mere scheduling.

### Presence Sources

**Home vs. Away Detection:**

| Source | Signal | Confidence |
|--------|--------|------------|
| Tesla GPS | Approaching, leaving, distance | 98% |
| Phone WiFi | Connected to UniFi network | 90% |
| Door contacts | Entry/exit events | 95% |
| DSC Security | Armed = assume away | 80% |

**Room Occupancy:**

| Source | Coverage | Confidence |
|--------|----------|------------|
| Motion sensors | Most rooms | 85% |
| UniFi AI cameras | Entry, Porch, Deck, Patio | 90% |
| Eight Sleep | Primary Bedroom | 95% |
| Door contacts | Entry, Game Room | 90% |

**Activity Inference:**

| Signals | Inference |
|---------|-----------|
| Living Room + evening + TV on | Entertainment |
| Kitchen + morning + motion | Cooking |
| Office + weekday + work hours | Working |
| Primary + night + Eight Sleep | Sleeping |
| Gym + motion | Working out |

---

### Multi-Signal Fusion

Single signals can be wrong. Multiple signals together approach certainty.

**Example: Arriving Home**

| Signal | Individual | Combined |
|--------|------------|----------|
| Tesla enters geofence | 95% | - |
| + Phone connects to WiFi | 92% | 99% |
| + Motion at Entry | 90% | 99.9% |
| + Door sensor triggers | 95% | 99.99% |

**Example: Really Gone**

| Signal | Individual | Combined |
|--------|------------|----------|
| Tesla left geofence | 95% | - |
| + Phone disconnected | 90% | 99% |
| + No motion 10 min | 80% | 99.9% |
| + DSC armed | 85% | 99.99% |

---

### Presence State Machine

```
                    ┌─────────────────┐
                    │                 │
                    ▼                 │
              ┌──────────┐           │
   ┌─────────►│   AWAY   │───────────┘
   │          └────┬─────┘
   │               │ Tesla approaching
   │               ▼
   │          ┌──────────┐
   │          │ ARRIVING │
   │          └────┬─────┘
   │               │ Enter house
   │               ▼
   │          ┌──────────┐
   │          │   HOME   │◄──────────┐
   │          └────┬─────┘           │
   │               │                  │
   │    ┌──────────┼──────────┐      │
   │    │          │          │      │
   │    ▼          ▼          ▼      │
   │ ┌──────┐ ┌────────┐ ┌────────┐ │
   │ │ACTIVE│ │SLEEPING│ │FOCUSED │ │
   │ └──┬───┘ └───┬────┘ └───┬────┘ │
   │    │         │          │      │
   │    └─────────┴──────────┴──────┘
   │               │
   │               │ Leave house
   │               ▼
   │          ┌──────────┐
   └──────────│ LEAVING  │
              └──────────┘
```

**Transition Actions:**

| Transition | Actions |
|------------|---------|
| AWAY -> ARRIVING | Pre-condition climate, prepare lights |
| ARRIVING -> HOME | Welcome sequence |
| HOME -> LEAVING | Security check |
| LEAVING -> AWAY | Arm DSC, setback climate |
| ACTIVE -> SLEEPING | Goodnight sequence |
| SLEEPING -> ACTIVE | Wake sequence |

---

### Sleep State

The Eight Sleep mattress provides rich sleep telemetry:

| State | Detection | Home Response |
|-------|-----------|---------------|
| **In bed** | Bed sensor | Begin wind-down |
| **Falling asleep** | Heart rate, movement | Dim lights further |
| **Asleep** | Low HR, no movement | Full quiet mode |
| **Waking** | HR rising, movement | Begin wake sequence |
| **Out of bed** | Sensor cleared | Full wake mode |

---

### Room-Specific Timeouts

| Room | Timeout | Rationale |
|------|---------|-----------|
| Primary Bedroom | 30 min | Might be resting |
| Living Room | 15 min | Watching TV |
| Kitchen | 10 min | Active area |
| Office | 20 min | Might be reading |
| Bathroom | 10 min | Short visits |

---

### Activity Inference

**Time-Based Defaults:**

| Time Block | Default Activity |
|------------|------------------|
| 5:00 - 7:00 AM | SLEEPING -> WAKING |
| 7:00 - 9:00 AM | MORNING_ROUTINE |
| 9:00 - 12:00 PM | WORKING (if Office) |
| 12:00 - 1:00 PM | BREAK |
| 1:00 - 5:00 PM | WORKING (if Office) |
| 5:00 - 7:00 PM | TRANSITION |
| 7:00 - 10:00 PM | RELAXING |
| 10:00 PM - 5:00 AM | SLEEPING |

**Room-Based Inference:**

| Room | Time | Likely Activity |
|------|------|-----------------|
| Kitchen | 6-8 AM | Morning prep |
| Kitchen | 5-7 PM | Cooking |
| Office | 9-5 weekday | Working |
| Living Room | Evening | Entertainment |
| Primary | Night | Sleeping |
| Gym | Any | Working out |

---

### Pattern Learning

Kagami learns patterns over time:

| Pattern | Signal Source | Adaptation |
|---------|---------------|------------|
| Wake time | Eight Sleep + motion | Adjust wake sequence |
| Leave time | Tesla + door | Prepare departure |
| Return time | Tesla | Pre-condition home |
| Room usage | Motion patterns | Anticipate needs |
| Weekend vs weekday | Day of week | Different routines |

**Learning Timeline:**

| Period | Capability |
|--------|------------|
| Day 1 | Manual + defaults |
| Week 1 | Basic patterns |
| Month 1 | Reliable patterns |
| Month 3 | Predictive automation |

---

## Scenes and Automation

A **scene** is a coordinated state across multiple devices triggered by a single command or event.

### Movie Mode

Transform the Living Room into a cinema.

| Device | Action |
|--------|--------|
| MantelMount | Lower to Preset 1 (viewing) |
| Living Room cans | 10% (bias lighting) |
| Living Room East shade | Close |
| Living Room South shade | Close |
| Denon AVR-A10H | Activate, proper input |
| KEF Reference system | Ready |
| Other audio zones | Mute |
| Fireplace | Optional prompt |

**Trigger:** "Movie mode" or TV activity detection in evening
**Exit:** "Movie off" - MantelMount raises, lights to 30%, path lights on

---

### Goodnight

Secure the house for sleep.

| Device | Action |
|--------|--------|
| All 41 lights | Fade to 0% over 30 seconds |
| All 11 shades | Close |
| All 26 audio zones | Off |
| MantelMount | Verify raised |
| Climate | Sleep preset |
| Entry lock | Verify locked, lock if needed |
| Game Room lock | Verify locked, lock if needed |
| DSC Security | Arm night |
| Eight Sleep | Start sleep schedule |

**Trigger:** "Goodnight" or Eight Sleep detects sleep + late hour
**Safety:** If any door unlocked and cannot lock, alerts you

---

### Welcome Home

Prepare the house for arrival.

| Device | Action |
|--------|--------|
| DSC Security | Disarm |
| Entry lights | 70% |
| Mudroom lights | 50% |
| Living Room lights | 40% |
| Climate | Comfort preset |
| Packages | Announce if any |

**Trigger:** Tesla enters geofence
**Variation (late night):** Dim path only, no announcements

---

### Away Mode

Secure the house when empty.

| Device | Action |
|--------|--------|
| All lights | Off |
| Climate | Setback (energy saving) |
| DSC Security | Arm away |
| UniFi cameras | Active monitoring |
| Locks | Verify locked |

**Trigger:** All presence gone (Tesla + phones)

---

### Focus Mode

Optimize Office for deep work.

| Device | Action |
|--------|--------|
| Office cans | 70% neutral |
| Office shades | Glare-optimized |
| Office climate | 72 degrees F |
| Office audio | Focus playlist, low volume |
| Notifications | High priority only |

**Trigger:** "Focus mode" or calendar focus block
**Exit:** "End focus" or calendar block ends

---

### Wake Up

Gentle morning sequence.

| Phase | Timing | Action |
|-------|--------|--------|
| 1 | Wake detected | Primary Bedroom 10% warm |
| 2 | +5 min | Primary Bedroom 30% |
| 3 | +10 min | Primary Bath 40%, floor heat on |
| 4 | Kitchen motion | Kitchen full brightness, audio |

**Trigger:** Eight Sleep detects waking

---

### Guest Mode

Prepare for visitors.

| Device | Action |
|--------|--------|
| Entry lights | 80% |
| Living Room lights | 60% |
| Kitchen lights | 70% |
| Dining lights | 40% |
| Powder Room | 50% |
| Audio | Entertaining playlist at 30% |
| Outdoor lights | Welcome pattern |

**Trigger:** "Guests arriving" or calendar event

---

### Automation Rules

**Presence-Based:**

| Trigger | Action |
|---------|--------|
| Room entry (motion) | Lights on |
| Room exit (10 min no motion) | Lights off |
| House empty | Away mode |
| First presence | Welcome mode |

**Time-Based:**

| Trigger | Action |
|---------|--------|
| Sunset | Exterior lights on |
| 10 PM | Begin wind-down |
| Wake detected | Morning sequence |

**Event-Based:**

| Trigger | Action |
|---------|--------|
| Doorbell pressed | Announce + camera snapshot |
| Package detected | Log + notify when home |
| Tesla approaching | Prepare house |
| Tesla leaving | Verify security |

**Weather-Based:**

| Trigger | Action |
|---------|--------|
| High heat forecast | Close south shades early |
| Rain approaching | Check windows |
| Below freezing | Protect pipes, warm Tesla |

---

### Scene Priorities

When scenes conflict:

| Priority | Scene Type |
|----------|------------|
| 1 (highest) | Safety (fire, security) |
| 2 | Sleep (goodnight) |
| 3 | Entertainment (movie) |
| 4 | Comfort (relax) |
| 5 (lowest) | Ambient (background) |

---

## Tesla Model S Plaid Integration

The Tesla Model S Plaid is the most significant external sensor and effector. Real-time telemetry at 500ms intervals means the house knows where Tim is, when he is coming home, and can prepare accordingly.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TESLA INTEGRATION                               │
├─────────────────────────────────────────────────────────────────────┤
│  TeslaIntegration (tesla.py)                                        │
│  ├── OAuth 2.0 authentication (tokens in Keychain)                  │
│  ├── Fleet API queries (direct HTTPS)                               │
│  └── Commands -> tesla-http-proxy (signed protocol)                 │
├─────────────────────────────────────────────────────────────────────┤
│  TeslaStreamingClient (tesla.py)                                    │
│  ├── Fleet Telemetry SSE (500ms updates)                            │
│  ├── Real-time vehicle state                                        │
│  └── Alert notifications                                            │
├─────────────────────────────────────────────────────────────────────┤
│  TeslaSafetyFilter (tesla_safety.py)                                │
│  ├── Control Barrier Function (CBF)                                 │
│  ├── Command categorization (CRITICAL, HIGH, MEDIUM, LOW)           │
│  └── Physical confirmation for critical commands while driving      │
├─────────────────────────────────────────────────────────────────────┤
│  TeslaAlertHandler (tesla_alerts.py)                                │
│  ├── 18,769 alert definitions                                       │
│  ├── Safety-critical routing                                        │
│  └── Customer-facing message extraction                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Capabilities

| Capability | Available | Notes |
|------------|-----------|-------|
| Location tracking | Yes | Real-time GPS |
| Climate control | Yes | Pre-condition, seat heaters |
| Charging control | Yes | Start/stop, set limit |
| Lock/unlock | Yes | Safety-filtered |
| Trunk/frunk | Yes | Remote open |
| Real-time telemetry | Yes | 500ms SSE streaming |
| Sentry mode | Yes | Monitor status |
| Alerts | Yes | 18,769 alert definitions |

---

### Geofence Zones

| Zone | Distance | Trigger |
|------|----------|---------|
| **ARRIVAL_IMMINENT** | 1 km | Begin home prep |
| **ARRIVING** | 500 m | Open garage |
| **HOME** | In garage | Full welcome |
| **DEPARTING** | Leaving | Check security |
| **AWAY** | > 1 km | Full away mode |

---

### Arrival Sequence

```
Tesla enters 1km geofence
         │
         ▼
    APPROACHING
    ├─> Climate: Start comfort prep
    ├─> Lights: Ready Entry, Mudroom
    └─> Security: Prepare to disarm
         │
         ▼
Tesla at 500m
         │
         ▼
    ARRIVING
    └─> Garage door: Open
         │
         ▼
Tesla in Garage
         │
         ▼
    HOME
    ├─> Security: Disarm
    ├─> Welcome sequence: Activate
    └─> Announce packages if any
```

---

### Departure Sequence

```
Tesla leaves Garage
         │
         ▼
    DEPARTING
    ├─> Check: Home empty?
    ├─> Check: All doors closed?
    └─> Garage door: Close
         │
         ▼
Tesla exits 1km geofence
         │
         ▼
    AWAY
    ├─> Security: Arm away
    ├─> Climate: Setback
    └─> Lights: All off
```

---

### Command Categories (23 methods in TeslaIntegration)

**Charging (10 commands):**
- `charge_port_door_open` / `charge_port_door_close`
- `charge_start` / `charge_stop`
- `charge_max_range` / `charge_standard`
- `set_charge_limit(percent)`
- `set_charging_amps(amps)`
- `set_scheduled_charging(enable, time)`
- `set_scheduled_departure(...)`

**Climate (12 commands):**
- `auto_conditioning_start` / `auto_conditioning_stop`
- `set_temps(driver_temp, passenger_temp)`
- `remote_seat_heater_request(heater, level)`
- `remote_seat_cooler_request(seat_position, level)`
- `remote_steering_wheel_heater_request(on)`
- `set_climate_keeper_mode(mode)` - 0=off, 1=on, 2=dog, 3=camp

**Security (12 commands):**
- `door_lock` / `door_unlock` - **CRITICAL: CBF protected**
- `actuate_trunk(which_trunk)` - "rear" or "front"
- `honk_horn` / `flash_lights`
- `trigger_homelink(lat, lon)`
- `remote_start_drive` - **CRITICAL: CBF protected**
- `set_sentry_mode(on)`
- `set_valet_mode(on, password)`

**Media (8 commands):**
- `media_toggle_playback`
- `media_next_track` / `media_prev_track`
- `media_volume_up` / `media_volume_down`
- `adjust_volume(volume)` - 0.0-11.0

**Navigation (4 commands):**
- `share(value, locale, timestamp)` - Share address/POI
- `navigation_request(value, locale, timestamp)`
- `navigation_sc_request(id, order)` - Supercharger
- `navigation_gps_request(lat, lon, order)`

---

### Telemetry Fields (78 implemented)

Real-time streaming at 500ms intervals via Fleet Telemetry SSE.

**Charging (27 fields):** `BatteryLevel`, `ChargeState`, `ChargeLimitSoc`, `EstBatteryRange`, `RatedRange`, `TimeToFullCharge`, `ChargerPhases`, `ChargingCableType`...

**Climate (14 fields):** `InsideTemp`, `OutsideTemp`, `SeatHeaterLeft`, `SeatHeaterRight`, `ClimateState`, `PreconditioningEnabled`...

**Location (6 fields):** `Location`, `Heading`, `Odometer`, `GpsState`, `DestinationLocation`...

**Drive State (8 fields):** `Speed`, `Gear`, `ShiftState`, `Power`, `SteeringAngle`, `CruiseState`...

**Vehicle State (18 fields):** `Locked`, `DoorsState`, `FtState`, `RtState`, `TpmsFl`, `TpmsFr`, `TpmsRl`, `TpmsRr`...

---

### Alert Dictionary (18,769 alerts)

| Prefix | Count | System |
|--------|-------|--------|
| RCM2 | 1,617 | Restraint Control Module (airbags) - **SAFETY** |
| GTW | 683 | Gateway module |
| DI | 590 | Drive Inverter |
| EBS | 446 | Electronic Braking - **SAFETY** |
| BMS | 383 | Battery Management |
| IBST | 374 | Integrated Brake - **SAFETY** |
| ESP | 374 | Electronic Stability - **SAFETY** |
| APP | 242 | Autopilot |

---

### Safety Design

**Safe Actions (unrestricted):**
- Pre-condition climate
- Check status
- Start/stop charging
- Lock doors
- Open trunk/frunk (when parked)
- Flash lights / honk horn

**Protected Actions (require verification):**
- Unlock doors (presence verification)
- Remote start (not enabled)
- Speed limit changes (key card required)

**Never:**
- Unlock remotely without verification
- Start the car remotely
- Share location data
- Override explicit commands

---

### Charging Optimization

| Setting | Value |
|---------|-------|
| Daily limit | 80% |
| Trip limit | 90-100% |
| Charging hours | Off-peak (midnight-6am) |

**Automatic Behaviors:**

| Scenario | Action |
|----------|--------|
| Plugged in, below limit | Schedule for off-peak |
| Long trip tomorrow (calendar) | Charge to 90%+ |
| Working from home | Reduce charging priority |

---

### Weather Integration

| Weather | Tesla Action | Home Action |
|---------|--------------|-------------|
| Cold morning | Pre-heat cabin, warm battery | Pre-heat Entry, Mudroom |
| Hot afternoon | Pre-cool cabin | Close south shades |
| Rain expected | Check windows | Check home windows |

---

## Meta Glasses Integration

The Ray-Ban Meta Smart Glasses provide first-person perspective - extending the Markov blanket to include what Tim sees.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Meta Glasses (Hardware)                      │
│   ┌────────────────┐ ┌────────────────┐ ┌────────────────────┐  │
│   │ Camera (POV)   │ │ 5-Mic Array    │ │ Open-Ear Speakers  │  │
│   └───────┬────────┘ └───────┬────────┘ └─────────┬──────────┘  │
│           │ BLE              │ BLE                │ BLE         │
│           └──────────────────┴────────────────────┘             │
│                              │                                   │
│                              ▼                                   │
│                    ┌─────────────────────┐                       │
│                    │   Companion App     │                       │
│                    │   (iOS/Android)     │                       │
│                    └──────────┬──────────┘                       │
└───────────────────────────────│──────────────────────────────────┘
                                │ WebSocket
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Kagami Backend                               │
│   ┌────────────────────────────────────────────────────────┐    │
│   │              MetaGlassesIntegration                     │    │
│   └──────────────────────────┬─────────────────────────────┘    │
│                              │                                   │
│           ┌──────────────────┼──────────────────┐               │
│           ▼                  ▼                  ▼               │
│   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│   │ PersonTracker │  │ PresenceEngine│  │ WakefulnessMan│       │
│   │  (visual      │  │  (activity    │  │  (visual      │       │
│   │   context)    │  │   inference)  │  │   detection)  │       │
│   └───────────────┘  └───────────────┘  └───────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

### Capabilities

**Visual Context Awareness:**
- See what the user sees
- Scene understanding (kitchen, office, outdoor)
- Object detection (desk, monitor, coffee cup)
- Text recognition
- Face detection and recognition

**Private Audio:**
- Whisper notifications through open-ear speakers
- Only the wearer can hear
- Natural audio routing

**Voice Input:**
- 5-microphone spatial array
- Natural command input
- Context-aware wake word

**Activity Inference:**
- Understand what the user is doing
- Enhanced presence detection
- Visual + audio fusion

---

### Visual Context Data

```python
context = await glasses.get_visual_context()

context.is_indoor       # True/False/None
context.lighting        # "bright", "dim", "dark"
context.scene_type      # "kitchen", "office", "outdoor"
context.detected_objects # ["desk", "monitor", "coffee_cup"]
context.detected_text   # ["Meeting at 3pm"]
context.faces_detected  # 0, 1, 2...
context.known_people    # ["Tim", "Sarah"]
context.activity_hint   # "working", "cooking", "reading"
context.confidence      # 0.0 - 1.0
```

---

### Private Audio Routing

```python
# Whisper a notification only the wearer can hear
await audio_bridge.whisper_to_glasses("Dinner is ready")

# Play notification sound
await audio_bridge.notify_glasses("notification", volume=0.5)

# Auto-route based on wearing state
await audio_bridge.announce(
    "Your package was delivered",
    prefer_glasses=True,  # Route to glasses if wearing
)
```

---

### Enhanced User Journeys

**Morning Wake-Up:**
- Before: Eight Sleep detects wake, lights on
- After: Glasses detect eyes open, personalized briefing via open-ear

**Cooking:**
- Before: Kitchen motion, lights on
- After: Glasses see recipe, read ingredients aloud

**Working:**
- Before: Office presence, focus mode
- After: Glasses detect video call, auto-adjust lighting

---

### Privacy

Privacy is the foundation. `h(x) >= 0` applies here too.

1. **Local-First Processing**: Raw video stays on companion device
2. **Semantic Features Only**: Only extracted features sent to backend
3. **User Consent**: Required per-session
4. **Visual Indicators**: LED shows when camera is active
5. **Opt-Out Controls**: Granular feature disabling

---

## Digital Services (Composio)

Beyond physical systems, Kagami integrates with digital services through the Composio API.

### Communication

| Service | Sensors | Effectors |
|---------|---------|-----------|
| Gmail | Unread count, priority messages | Send, archive |
| Slack | Mentions, DMs | Send message, set status |
| Discord | Notifications | Send message |

### Calendar

| Sensor | What It Reads |
|--------|---------------|
| `calendar.next_event` | Upcoming meeting |
| `calendar.today_events` | Full day schedule |
| `calendar.busy_now` | Currently in meeting |

### Tasks

| Service | Sensors | Effectors |
|---------|---------|-----------|
| Todoist | Due today, overdue | Create, complete |
| Linear | Assigned issues | Create issue |

---

## Querying the Action Space

```python
from kagami_smarthome import get_smart_home

controller = await get_smart_home()

# What can I do in the Living Room?
living_room_actions = registry.list_by_location("living_room")

# What's the light level?
level = sensors.get("light.living_room.level")

# Turn on lights
await controller.set_lights(75, rooms=["Living Room"])

# Goodnight - everything off, locked up
await controller.goodnight()
```

---

## Summary

Kagami's action space encompasses:

- **41 lights** across 26 rooms
- **11 motorized shades** for natural light control
- **26 audio zones** including reference theater
- **Multi-zone HVAC** for comfort and efficiency
- **2 smart locks** and DSC security panel
- **4 AI cameras** with person/package detection
- **Tesla Model S Plaid** with 23 integration methods and 78 telemetry fields
- **Meta Glasses** for first-person perspective
- **Digital services** through Composio

Every sensor feeds the world model. Every effector is safety-filtered. The Markov blanket defines the boundary between Kagami and the world it inhabits.

```
h(x) >= 0 always
```

*Every sensor. Every effector. The home at your command.*

---
