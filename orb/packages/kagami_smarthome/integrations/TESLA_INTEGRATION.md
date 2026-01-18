# Tesla Fleet API — Complete Markov Blanket Integration

**Model S Plaid — Full Sensory + Effector Coverage**

---

## Markov Blanket Architecture

```
                        ENVIRONMENT (η)
                            Tesla
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     │                     ▼
   ┌─────────┐                │              ┌─────────┐
   │ SENSORY │                │              │ EFFECTOR│
   │   (s)   │                │              │   (a)   │
   │         │                │              │         │
   │ Fleet   │      ┌─────────┴─────────┐    │ Vehicle │
   │Telemetry│      │    INTERNAL (μ)   │    │Commands │
   │  500ms  │ ───▶ │      Kagami       │ ──▶│  65 API │
   │         │      │                   │    │ calls   │
   │ 18,768  │      │  • State cache    │    │         │
   │ alerts  │      │  • CBF filter     │    │  CBF    │
   │         │      │  • Alert router   │    │protected│
   │ 78+     │      │  • Command exec   │    │         │
   │ fields  │      └───────────────────┘    │         │
   └─────────┘                               └─────────┘
```

---

## Coverage Summary

| Layer | Before | After | Coverage |
|-------|--------|-------|----------|
| **Sensory (s)** | 12 fields, 5 min poll | 78 fields, 500ms SSE | **100%** |
| **Alerts** | 0 | 18,768 (5,000 Model S) | **100%** |
| **Effector (a)** | 14 commands | 65 commands | **100%** |
| **Safety (CBF)** | None | All commands filtered | **100%** |

---

## Latency

| Metric | Value |
|--------|-------|
| Fleet Telemetry native rate | 500ms |
| SSE transport overhead | ~50-100ms |
| **Total sense latency** | **~550-600ms** |
| Command execution | ~200-500ms |
| **Total round-trip** | **~750-1100ms** |

---

## Files

| File | Purpose |
|------|---------|
| `tesla.py` | Core integration + SSE streaming |
| `tesla_alerts.py` | Alert dictionary + priority routing |
| `tesla_alerts.csv` | Full 18,768 alert dictionary |
| `tesla_commands.py` | Complete 65-command effector |
| `tesla_alerts_model_s_customer.csv` | Model S customer alerts |

---

## Sensory Layer (s)

### Fleet Telemetry Fields (78)

**Charging (26 fields)**
- ACChargingEnergyIn, ACChargingPower, BatteryLevel, BMSState
- BatteryHeaterOn, ChargeCurrentRequest/Max, ChargeLimitSoc
- ChargePort, ChargePortDoorOpen, ChargePortLatch, ChargerPhases
- ChargingCableType, ChargeState, DCChargingEnergyIn/Power
- EnergyRemaining, EstBatteryRange, FastChargerPresent
- IdealBatteryRange, MinutesToFullCharge, RatedRange
- ScheduledChargingPending/StartTime, TimeToFullCharge, UsableSoc

**Climate (15 fields)**
- AutoSeatClimateLeft/Right, CabinOverheatProtectionMode/TempLimit
- ClimateState, ClimateKeeperMode, DefrostMode
- InsideTemp, OutsideTemp, PreconditioningEnabled
- SeatHeaterLeft/Right/RearLeft/RearRight, SentryMode

**Location (6 fields)**
- DestinationLocation, GpsState, Heading, Location, Odometer, RouteLastUpdated

**Drive State (8 fields)**
- CruiseState, DriverAssistLevel, DriveRail, Gear
- Power, ShiftState, Speed, SteeringAngle

**Vehicle State (19 fields)**
- CenterDisplay, DoorsState, FdWindow, FpWindow, FtState
- HomelinkNearby, Locked, MediaPlaybackStatus, OriginLocation
- RdWindow, RpWindow, RtState, SoftwareUpdateVersion
- SpeedLimitMode, TpmsFl/Fr/Rl/Rr, VehicleName, WiperHeatEnabled

**Safety (4 fields)**
- AutomaticBlindSpotCamera, AutomaticEmergencyBrakingOff
- BlindSpotCollisionWarningChime, ForwardCollisionWarningLevel

**Alerts (1 field)**
- Alerts: Array of active alert signal names → routes to Alert Dictionary

### Alert Categories (Model S 2021+)

| Category | Count | Description |
|----------|-------|-------------|
| RCM2 | 419 | Restraints, airbags, seatbelts |
| IBST | 120 | Integrated Brake System |
| ESP | 83 | Stability, traction |
| DI | 62 | Drive inverter |
| CP | 61 | Charge port |
| BMS | 54 | Battery management |
| UI | 49 | Touchscreen |
| FC | 49 | Front controller |
| APP | 45 | Autopilot/FSD |
| **Total** | **1,311** | Customer-facing |

---

## Effector Layer (a)

### All 65 Commands by Category

**Trunk (2)**
- `actuate_trunk` — Open front/rear trunk

**Charging (14)**
- `add_charge_schedule` — Add charging schedule
- `charge_max_range` — Set to 100%
- `charge_port_door_close/open` — Charge port door
- `charge_standard` — Set to 90%
- `charge_start/stop` — Control charging
- `remove_charge_schedule` — Remove schedule
- `set_charge_limit` — Set percentage
- `set_charging_amps` — Set amperage
- `set_scheduled_charging` — Enable/disable
- `set_scheduled_departure` — Departure time

**Climate (16)**
- `add_precondition_schedule` — Precondition schedule
- `auto_conditioning_start/stop` — Climate on/off
- `remote_auto_seat_climate_request` — Auto seat climate
- `remote_auto_steering_wheel_heat_climate_request` — Auto wheel heat
- `remote_seat_cooler_request` — Seat cooler
- `remote_seat_heater_request` — Seat heater
- `remote_steering_wheel_heat_level_request` — Wheel heat level
- `remote_steering_wheel_heater_request` — Wheel heater toggle
- `remove_precondition_schedule` — Remove schedule
- `set_bioweapon_mode` — Bioweapon defense
- `set_cabin_overheat_protection` — COP settings
- `set_climate_keeper_mode` — Dog/Camp mode
- `set_cop_temp` — COP temperature
- `set_preconditioning_max` — Max defrost
- `set_temps` — Set temperatures

**Locks (2)**
- `door_lock` — Lock doors
- `door_unlock` — Unlock doors (PROTECTED)

**Media (7)**
- `adjust_volume` — Set volume
- `media_next_fav/prev_fav` — Favorite stations
- `media_next_track/prev_track` — Track control
- `media_toggle_playback` — Play/pause
- `media_volume_down` — Volume down

**Navigation (4)**
- `navigation_gps_request` — Send GPS coords
- `navigation_request` — Send destination
- `navigation_sc_request` — Nearest Supercharger
- `navigation_waypoints_request` — Multi-waypoints

**Security (8)**
- `clear_pin_to_drive_admin` — Clear PIN (CRITICAL)
- `guest_mode` — Guest mode
- `reset_pin_to_drive_pin` — Reset PIN
- `reset_valet_pin` — Reset valet PIN
- `set_pin_to_drive` — PIN to drive
- `set_sentry_mode` — Sentry mode
- `set_valet_mode` — Valet mode
- `set_vehicle_name` — Vehicle name

**Windows (2)**
- `sun_roof_control` — Sunroof stop/close/vent
- `window_control` — Windows vent/close

**Alerts (3)**
- `flash_lights` — Flash headlights
- `honk_horn` — Honk (CAUTION)
- `remote_boombox` — Boombox sound

**Software (2)**
- `cancel_software_update` — Cancel update
- `schedule_software_update` — Schedule update

**Drive (6) — HIGH SAFETY**
- `remote_start_drive` — Keyless driving (CRITICAL)
- `speed_limit_activate/deactivate` — Speed limit mode
- `speed_limit_clear_pin/clear_pin_admin` — Clear PIN
- `speed_limit_set_limit` — Set limit

**HomeLink (1)**
- `trigger_homelink` — Garage door!

**Data (2)**
- `erase_user_data` — Factory reset (CRITICAL)
- `upcoming_calendar_entries` — Get calendar

---

## CBF Safety Levels

| Level | h(x) | Commands | Action |
|-------|------|----------|--------|
| SAFE | >0.5 | Most commands | Execute |
| CAUTION | 0-0.5 | honk, windows, guest | Log warning |
| PROTECTED | ~0 | unlock, valet, speed | Requires confirmation |
| CRITICAL | <0 | remote_start, erase | Double confirmation |

---

## What Tim Needs To Do With The Car

### ✅ Already Done
- [x] Public key generated (`com.tesla.3p.public-key.pem` in Downloads)

### 🚗 Do At The Car

#### 1. Pair Virtual Key (ONE TIME)

In the Tesla app on your phone:
1. Open Tesla app
2. Go to **Security & Drivers** → **Keys**
3. Tap **Add Key**
4. Select **Add Third-Party Key**
5. Open this link: `https://tesla.com/_ak/awkronos.github.io`
6. **Tap your key card on the center console** when prompted

**Developer Domain:** `awkronos.github.io`
**Public Key:** `https://awkronos.github.io/.well-known/appspecific/com.tesla.3p.public-key.pem`

This enables all 65 vehicle commands.

#### 2. Verify Firmware

Required: **2024.26+** for Fleet Telemetry

In the car:
1. Touch **Controls** → **Software**
2. Check version number
3. If older, schedule update

#### 3. Enable HomeLink (if not done)

In the car:
1. Touch **Controls** → **HomeLink**
2. Add your garage door
3. Test it works from the car

#### 4. Test From Home

After pairing, test these commands:

```python
# Quick test
from kagami_smarthome.integrations.tesla_commands import TeslaCommandExecutor
from kagami_smarthome.integrations.tesla import TeslaIntegration

# Connect
tesla = TeslaIntegration(config)
await tesla.connect()
executor = TeslaCommandExecutor(tesla)

# Test safe commands
await executor.flash_lights()  # Should flash
await executor.honk_horn()     # Should honk

# Test climate
await executor.start_climate()
await executor.set_temps(21)

# Test garage (when near garage)
await executor.trigger_homelink()
```

---

## OAuth2 Scopes Required

Your Tesla Developer App needs these scopes:

| Scope | Required For |
|-------|--------------|
| `vehicle_device_data` | Fleet Telemetry streaming |
| `vehicle_cmds` | All 65 commands |
| `vehicle_location` | GPS position |
| `vehicle_charging_cmds` | Charging control |

---

## Integration Usage

### Streaming (Sensory)

```python
from kagami_smarthome.integrations.tesla import (
    TeslaIntegration,
    TeslaStreamingClient,
)
from kagami_smarthome.integrations.tesla_alerts import (
    TeslaAlertDictionary,
    TeslaAlertRouter,
)

# Connect
tesla = TeslaIntegration(config)
await tesla.connect()

# Start streaming
streaming = TeslaStreamingClient(tesla)

# Handle alerts
dictionary = TeslaAlertDictionary()
await dictionary.load()
router = TeslaAlertRouter(dictionary)

router.on_critical(handle_critical_alert)
streaming.on_alert(router.handle_alert)

await streaming.connect()

# Now receiving 500ms updates + full alert routing
```

### Commands (Effector)

```python
from kagami_smarthome.integrations.tesla_commands import TeslaCommandExecutor

executor = TeslaCommandExecutor(tesla)

# Climate before leaving
await executor.start_climate()
await executor.set_temps(21)
await executor.set_seat_heater(0, 3)  # Driver, max

# When arriving home
await executor.trigger_homelink()  # Open garage

# Charging
await executor.set_charge_limit(80)
await executor.charge_start()

# Security
await executor.set_sentry_mode(True)
await executor.lock()
```

---

## Smart Home Integration Examples

### "Leaving for work" scene

```python
async def leaving_for_work():
    # Start car climate 15 min before
    await executor.start_climate()
    await executor.set_temps(21)
    await executor.set_seat_heater(0, 2)

    # Open garage
    await executor.trigger_homelink()

    # Set nav to office
    await executor.navigate_to("1000 4th Ave, Seattle")
```

### "Car arriving home" trigger

```python
# From Fleet Telemetry location update
async def on_location_update(field, value, ts):
    if field == "Location" and is_near_home(value):
        # Open garage
        await executor.trigger_homelink()

        # Turn on house lights
        await smart_home.set_lights(50, rooms=["Garage", "Mudroom"])

        # Welcome announcement
        await smart_home.announce("Welcome home!", rooms=["Mudroom"])
```

### "Critical alert" response

```python
async def on_critical_alert(alert, data):
    # Announce in all rooms
    await smart_home.announce_all(f"Tesla alert: {alert.customer_message_1}")

    # Flash lights if at home
    if tesla.is_home():
        await executor.flash_lights()
```

---

## Created: December 31, 2025

**Full Markov Blanket discipline achieved.**

```
η → s → μ → a → η'
```
