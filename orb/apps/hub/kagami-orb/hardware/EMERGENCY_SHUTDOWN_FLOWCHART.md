# Kagami Orb V3.1 — Emergency Shutdown Procedures

## Document Information

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Date** | 2026-01-11 |
| **Status** | COMPLETE |
| **Safety Basis** | Control Barrier Function h(x) >= 0 |
| **Related Docs** | THERMAL_FEA_ANALYSIS.md, PRESSURE_RELIEF_DESIGN.md, FMEA_V3.md |

---

## Executive Summary

This document defines the multi-stage emergency response system for the Kagami Orb V3.1. The system implements progressive degradation with user notification, ensuring safety while maximizing uptime.

### Safety Philosophy

```
h(x) >= 0. Always.

The orb must never:
• Cause thermal injury (surface > 48°C)
• Experience battery thermal runaway
• Operate in unsafe pressure state
• Violate privacy without indication
• Continue operating after CBF violation
```

---

## 1. Multi-Stage Thermal Throttling

### 1.1 Thermal State Machine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    THERMAL STATE MACHINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Tj = Junction Temperature (QCS6490)                                        │
│   Ts = Surface Temperature (Shell max)                                       │
│   Tb = Battery Temperature                                                   │
│                                                                              │
│                                                                              │
│   ┌───────────────┐                                                          │
│   │    NORMAL     │◄──────────────────────────────────────────────┐         │
│   │   Tj < 65°C   │                                               │         │
│   │   Ts < 40°C   │                                               │         │
│   │   Tb < 40°C   │                                               │         │
│   │               │                                               │         │
│   │  Full power   │                                               │         │
│   │  All features │                                               │         │
│   └───────┬───────┘                                               │         │
│           │                                                       │         │
│           │ Tj >= 65°C OR Ts >= 40°C OR Tb >= 40°C               │         │
│           ▼                                                       │         │
│   ┌───────────────┐                                               │         │
│   │     WARM      │◄────────────────────────────────────┐        │         │
│   │  65 <= Tj <75 │                                     │        │         │
│   │  40 <= Ts <43 │                                     │        │         │
│   │  40 <= Tb <43 │                                     │        │         │
│   │               │                                     │        │         │
│   │  Reduce bg    │                                     │        │         │
│   │  tasks 50%    │                                     │        │         │
│   │  Warn user    │                                     │        │         │
│   └───────┬───────┘                                     │        │         │
│           │                                             │        │         │
│           │ Tj >= 75°C OR Ts >= 43°C OR Tb >= 43°C     │ Cool   │ Cool    │
│           ▼                                             │ down   │ down    │
│   ┌───────────────┐                                     │        │         │
│   │   THROTTLE    │─────────────────────────────────────┘        │         │
│   │  75 <= Tj <85 │                                              │         │
│   │  43 <= Ts <46 │                                              │         │
│   │  43 <= Tb <45 │                                              │         │
│   │               │                                              │         │
│   │  CPU to 50%   │                                              │         │
│   │  NPU to 50%   │                                              │         │
│   │  Suspend AI   │                                              │         │
│   │  Dim display  │                                              │         │
│   └───────┬───────┘                                              │         │
│           │                                                      │         │
│           │ Tj >= 85°C OR Ts >= 46°C OR Tb >= 45°C              │         │
│           ▼                                                      │         │
│   ┌───────────────┐                                              │         │
│   │   CRITICAL    │──────────────────────────────────────────────┘         │
│   │  85 <= Tj <95 │                                                        │
│   │  46 <= Ts <48 │                                                        │
│   │   Tb >= 45    │                                                        │
│   │               │                                                        │
│   │  CPU to 25%   │                                                        │
│   │  NPU disabled │                                                        │
│   │  Display min  │                                                        │
│   │  Hailo off    │                                                        │
│   │  Voice alert  │                                                        │
│   └───────┬───────┘                                                        │
│           │                                                                 │
│           │ Tj >= 95°C OR Ts >= 48°C OR Tb >= 50°C OR CBF VIOLATED         │
│           ▼                                                                 │
│   ╔═══════════════╗                                                        │
│   ║   SHUTDOWN    ║                                                        │
│   ║   Tj >= 95°C  ║                                                        │
│   ║   Ts >= 48°C  ║                                                        │
│   ║   Tb >= 50°C  ║                                                        │
│   ║               ║                                                        │
│   ║ Voice: "Orb   ║                                                        │
│   ║  shutting     ║                                                        │
│   ║  down for     ║                                                        │
│   ║  safety"      ║                                                        │
│   ║               ║                                                        │
│   ║ Push notif    ║                                                        │
│   ║ Graceful stop ║                                                        │
│   ║ Power off     ║                                                        │
│   ╚═══════════════╝                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Power Limits Per State

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    POWER BUDGET BY STATE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   STATE        DOCKED POWER    PORTABLE POWER    ACTIONS                     │
│   ──────────────────────────────────────────────────────────────────────    │
│   NORMAL       22.7W (burst)   6.7W              Full performance            │
│                13.8W (sustain)                                               │
│                                                                              │
│   WARM         13.8W           5.0W              Reduce background:          │
│                                                  • Pause indexing            │
│                                                  • Reduce AI inference       │
│                                                  • Yellow status LED         │
│                                                                              │
│   THROTTLE     10.0W           4.0W              Throttle compute:           │
│                                                  • CPU 1.5 GHz (vs 2.7)     │
│                                                  • NPU 50% duty             │
│                                                  • Display 50% brightness   │
│                                                  • Amber status LED         │
│                                                  • Audible warning beep     │
│                                                                              │
│   CRITICAL     6.7W            3.0W              Minimal operation:          │
│                                                  • CPU 800 MHz              │
│                                                  • NPU disabled             │
│                                                  • Hailo disabled           │
│                                                  • Display 20% brightness   │
│                                                  • Red status LED           │
│                                                  • Voice: "Cooling down"    │
│                                                  • Push notification        │
│                                                                              │
│   SHUTDOWN     0W              0W                Safe shutdown:              │
│                                                  • Save state               │
│                                                  • Voice: "Shutting down"   │
│                                                  • Push: "Thermal limit"    │
│                                                  • Power off                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Component-Specific Throttling

```c
// Thermal throttling implementation
// File: firmware/thermal_manager.c

typedef struct {
    float tj_limit;      // Junction temperature limit (°C)
    float ts_limit;      // Surface temperature limit (°C)
    float tb_limit;      // Battery temperature limit (°C)
    uint32_t cpu_freq;   // CPU frequency (MHz)
    uint8_t npu_duty;    // NPU duty cycle (%)
    uint8_t hailo_duty;  // Hailo duty cycle (%)
    uint8_t display_pct; // Display brightness (%)
    uint8_t led_color;   // Status LED color
} thermal_state_config_t;

const thermal_state_config_t thermal_configs[] = {
    // NORMAL
    {
        .tj_limit = 65.0, .ts_limit = 40.0, .tb_limit = 40.0,
        .cpu_freq = 2700, .npu_duty = 100, .hailo_duty = 100,
        .display_pct = 100, .led_color = LED_GREEN
    },
    // WARM
    {
        .tj_limit = 75.0, .ts_limit = 43.0, .tb_limit = 43.0,
        .cpu_freq = 2000, .npu_duty = 80, .hailo_duty = 80,
        .display_pct = 80, .led_color = LED_YELLOW
    },
    // THROTTLE
    {
        .tj_limit = 85.0, .ts_limit = 46.0, .tb_limit = 45.0,
        .cpu_freq = 1500, .npu_duty = 50, .hailo_duty = 50,
        .display_pct = 50, .led_color = LED_AMBER
    },
    // CRITICAL
    {
        .tj_limit = 95.0, .ts_limit = 48.0, .tb_limit = 50.0,
        .cpu_freq = 800, .npu_duty = 20, .hailo_duty = 0,
        .display_pct = 20, .led_color = LED_RED
    },
    // SHUTDOWN (limits only, no operation)
    {
        .tj_limit = 999.0, .ts_limit = 999.0, .tb_limit = 999.0,
        .cpu_freq = 0, .npu_duty = 0, .hailo_duty = 0,
        .display_pct = 0, .led_color = LED_OFF
    }
};
```

---

## 2. CBF Violation Response

### 2.1 Control Barrier Function Monitoring

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTROL BARRIER FUNCTION (CBF)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   h(x) >= 0  ALWAYS                                                          │
│                                                                              │
│   Safety barrier functions monitored:                                        │
│                                                                              │
│   h_thermal(x) = T_limit - T_actual                                         │
│       T_limit = 95°C (junction)                                              │
│       When h < 0: Thermal runaway imminent                                  │
│                                                                              │
│   h_battery(x) = min(                                                        │
│       V_max - V_cell,      // Overvoltage protection                        │
│       V_cell - V_min,      // Undervoltage protection                       │
│       T_batt_limit - T_batt // Thermal protection                           │
│   )                                                                          │
│       V_max = 4.25V/cell, V_min = 2.8V/cell, T_limit = 50°C                │
│       When h < 0: Battery abuse condition                                   │
│                                                                              │
│   h_pressure(x) = P_limit - P_internal                                      │
│       P_limit = 1.5 bar (burst disk threshold)                              │
│       When h < 0: Pressure hazard                                           │
│                                                                              │
│   h_privacy(x) = camera_led_on OR camera_off                                │
│       Binary: Either camera is off, or LED indicates recording             │
│       When h < 0: Privacy violation                                         │
│                                                                              │
│   h_physical(x) = enclosure_intact                                          │
│       Hall sensor detects shell separation                                  │
│       When h < 0: Enclosure compromised                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 CBF Violation Response Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CBF VIOLATION RESPONSE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                         ┌─────────────────┐                                  │
│                         │  CBF MONITOR    │                                  │
│                         │  (100ms loop)   │                                  │
│                         └────────┬────────┘                                  │
│                                  │                                           │
│                 ┌────────────────┼────────────────┐                         │
│                 │                │                │                         │
│            ▼                ▼                ▼                              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│   │ h_thermal(x) │  │ h_battery(x) │  │ h_pressure(x)│                     │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                     │
│          │                 │                 │                              │
│          │ h < 5°C margin  │ h < threshold   │ h < 0.2 bar                 │
│          ▼                 ▼                 ▼                              │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │                      VIOLATION DETECTED                               │ │
│   │                                                                       │ │
│   │  1. IMMEDIATE: Disable all non-essential loads                       │ │
│   │     • Hailo-10H → OFF                                                │ │
│   │     • QCS6490 NPU → OFF                                              │ │
│   │     • Display → 10%                                                  │ │
│   │     • LEDs → RED PULSE                                               │ │
│   │                                                                       │ │
│   │  2. ALERT: Voice + Push notification                                 │ │
│   │     • Voice: "Safety condition detected. Shutting down."             │ │
│   │     • Push: "Orb safety shutdown - [specific reason]"                │ │
│   │                                                                       │ │
│   │  3. LOG: Record violation details                                    │ │
│   │     • Timestamp                                                      │ │
│   │     • Which h(x) violated                                            │ │
│   │     • Sensor values at time of violation                             │ │
│   │     • Battery state                                                  │ │
│   │                                                                       │ │
│   │  4. SHUTDOWN: Graceful power off                                     │ │
│   │     • Save persistent state                                          │ │
│   │     • Close all connections                                          │ │
│   │     • Power off main rail                                            │ │
│   │     • ESP32 remains in monitoring mode (0.5mA)                       │ │
│   │                                                                       │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                  │                                           │
│                                  ▼                                           │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │                      POST-SHUTDOWN STATE                              │ │
│   │                                                                       │ │
│   │  ESP32 monitors:                                                      │ │
│   │  • Temperature sensors (every 10s)                                   │ │
│   │  • Pressure sensor (every 10s)                                       │ │
│   │  • Button press (wake trigger)                                       │ │
│   │                                                                       │ │
│   │  Recovery allowed when:                                              │ │
│   │  • All temperatures < 50°C                                           │ │
│   │  • Pressure < 1.2 bar                                                │ │
│   │  • Cooldown period elapsed (5 minutes minimum)                       │ │
│   │  • User initiates wake (button or app)                               │ │
│   │                                                                       │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. User Notification Sequence

### 3.1 Notification Escalation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    USER NOTIFICATION ESCALATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LEVEL 1: INFORMATIONAL (WARM state)                                        │
│   ─────────────────────────────────────────────────────────────────────     │
│   • LED: Yellow status ring (subtle pulse)                                   │
│   • Display: Small thermal icon in corner                                    │
│   • Voice: None (silent)                                                     │
│   • Push: None                                                               │
│   • Logging: Event recorded                                                  │
│                                                                              │
│   LEVEL 2: WARNING (THROTTLE state)                                          │
│   ─────────────────────────────────────────────────────────────────────     │
│   • LED: Amber status ring (breathing)                                       │
│   • Display: "Performance reduced - cooling down"                            │
│   • Voice: Single soft chime                                                 │
│   • Push: "Orb is cooling down" (if enabled)                                │
│   • Logging: Event recorded with sensor values                              │
│                                                                              │
│   LEVEL 3: ALERT (CRITICAL state)                                            │
│   ─────────────────────────────────────────────────────────────────────     │
│   • LED: Red status ring (fast pulse)                                        │
│   • Display: Full-screen "COOLING DOWN" with temperature                     │
│   • Voice: "Orb is very warm. Cooling down to protect the hardware."        │
│   • Push: "Orb critical temperature - features limited" (forced)            │
│   • Logging: Full diagnostic snapshot                                        │
│                                                                              │
│   LEVEL 4: SHUTDOWN                                                          │
│   ─────────────────────────────────────────────────────────────────────     │
│   • LED: Red status ring (solid, then off)                                   │
│   • Display: "SHUTTING DOWN FOR SAFETY" (3 seconds)                         │
│   • Voice: "Orb shutting down for safety. Please let it cool down."         │
│   • Push: "Orb safety shutdown - will restart when safe" (urgent)           │
│   • Logging: Full crash dump + sensor history                               │
│   • Post: LED blinks red every 30s until recovery                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Voice Alert Scripts

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VOICE ALERT LIBRARY                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   THERMAL ALERTS:                                                            │
│                                                                              │
│   thermal_throttle:                                                          │
│     "I'm getting a bit warm. Reducing power to cool down."                  │
│                                                                              │
│   thermal_critical:                                                          │
│     "Temperature is high. Some features are temporarily disabled."          │
│                                                                              │
│   thermal_shutdown:                                                          │
│     "Shutting down for safety. Please let me cool down."                    │
│                                                                              │
│   thermal_recovery:                                                          │
│     "All cooled down. Ready to go."                                         │
│                                                                              │
│   BATTERY ALERTS:                                                            │
│                                                                              │
│   battery_low:                                                               │
│     "Battery is getting low. Please put me on the charger."                 │
│                                                                              │
│   battery_critical:                                                          │
│     "Battery critically low. Shutting down to protect the battery."         │
│                                                                              │
│   battery_charging_suspended:                                                │
│     "Charging paused because I'm too warm. Will resume when cooled."        │
│                                                                              │
│   battery_swelling_detected:                                                 │
│     "Battery health issue detected. Please contact support."                │
│                                                                              │
│   PRESSURE ALERTS:                                                           │
│                                                                              │
│   pressure_elevated:                                                         │
│     "Internal pressure is elevated. Monitoring the situation."              │
│                                                                              │
│   pressure_critical:                                                         │
│     "Safety shutdown due to pressure. Please contact support immediately."  │
│                                                                              │
│   PRIVACY ALERTS:                                                            │
│                                                                              │
│   camera_active:                                                             │
│     "Camera is now active." (when user activates)                           │
│                                                                              │
│   camera_privacy_mode:                                                       │
│     "Privacy mode enabled. Camera is completely off."                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Safe Shutdown State Transitions

### 4.1 Graceful Shutdown Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GRACEFUL SHUTDOWN SEQUENCE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   TIME    ACTION                                      COMPONENT              │
│   ─────────────────────────────────────────────────────────────────────     │
│                                                                              │
│   T+0ms   Shutdown triggered                          ESP32                  │
│           Set flag: shutdown_in_progress = true                             │
│           Disable all new tasks                                             │
│                                                                              │
│   T+50ms  Disable heavy loads                         Power Management      │
│           Hailo-10H → OFF (GPIO low)                                        │
│           QCS6490 NPU → OFF (driver command)                                │
│           Camera → OFF (MIPI disable)                                       │
│                                                                              │
│   T+100ms Voice alert begins                          XMOS + Speaker        │
│           "Orb shutting down for safety."                                   │
│           Duration: ~2500ms                                                 │
│                                                                              │
│   T+200ms Display shutdown message                    AMOLED                │
│           "SHUTTING DOWN FOR SAFETY"                                        │
│           Brightness: 30%                                                   │
│                                                                              │
│   T+500ms Save persistent state                       QCS6490               │
│           • User preferences                                                │
│           • Shutdown reason code                                            │
│           • Sensor snapshot                                                 │
│           • Sync to flash (timeout: 2000ms)                                 │
│                                                                              │
│   T+1000ms Push notification sent                     WiFi                  │
│           Firebase push to all registered devices                           │
│           Message: "Orb safety shutdown - [reason]"                         │
│                                                                              │
│   T+2000ms Close network connections                  QCS6490               │
│           Disconnect WiFi                                                   │
│           Disconnect Bluetooth                                              │
│                                                                              │
│   T+2600ms Voice alert complete                       XMOS                  │
│           Fade out audio                                                    │
│           Disable audio amp                                                 │
│                                                                              │
│   T+3000ms Display off                                AMOLED                │
│           MIPI disable                                                      │
│           Backlight off                                                     │
│                                                                              │
│   T+3500ms QCS6490 shutdown                           SoM                   │
│           Linux orderly shutdown                                            │
│           Power sequence reverse                                            │
│           Verify PMIC rails off                                             │
│                                                                              │
│   T+5000ms LEDs off                                   HD108 Ring            │
│           Final red flash                                                   │
│           All LEDs off                                                      │
│                                                                              │
│   T+5500ms Enter monitoring mode                      ESP32                 │
│           Main power rail OFF                                               │
│           ESP32 in deep sleep (0.5mA)                                       │
│           Wake sources:                                                     │
│             • Button press                                                  │
│             • Temperature < 50°C AND timer > 5min                           │
│             • Dock detection (hall sensor)                                  │
│                                                                              │
│   TOTAL SHUTDOWN TIME: 5.5 seconds (max)                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Emergency Hard Shutdown

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EMERGENCY HARD SHUTDOWN                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Triggered when:                                                            │
│   • Tj >= 100°C (thermal emergency)                                         │
│   • Battery voltage < 2.5V/cell (critical undervoltage)                     │
│   • Pressure >= 1.5 bar (burst disk about to rupture)                       │
│   • Watchdog timeout (system hang)                                          │
│   • BMS protection triggered                                                │
│                                                                              │
│   TIME    ACTION                                                             │
│   ─────────────────────────────────────────────────────────────────────     │
│                                                                              │
│   T+0ms   Emergency detected                                                │
│           ESP32 takes control                                               │
│           Bypass normal shutdown                                            │
│                                                                              │
│   T+10ms  Cut all power                                                     │
│           Main PMIC disable (GPIO)                                          │
│           Hailo power cut                                                   │
│           Only ESP32 + sensors remain                                       │
│                                                                              │
│   T+50ms  Log event (if possible)                                           │
│           Flash emergency code                                              │
│           Timestamp                                                         │
│                                                                              │
│   T+100ms Enter deep sleep                                                  │
│           Monitor for recovery conditions                                   │
│                                                                              │
│   NO VOICE ALERT (power cut too fast)                                       │
│   NO PUSH NOTIFICATION (no time)                                            │
│   LED: Brief red flash before power off                                     │
│                                                                              │
│   TOTAL HARD SHUTDOWN TIME: 100ms                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Recovery Procedure

### 5.1 Automatic Recovery

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AUTOMATIC RECOVERY                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ESP32 MONITORING LOOP (during shutdown):                                   │
│                                                                              │
│   while (shutdown_state == true) {                                           │
│                                                                              │
│       // Wake every 30 seconds to check                                     │
│       deep_sleep(30000);                                                    │
│                                                                              │
│       // Read sensors (quick, low power)                                    │
│       float tj = read_temperature(SENSOR_JUNCTION);                         │
│       float tb = read_temperature(SENSOR_BATTERY);                          │
│       float pressure = read_pressure();                                     │
│       bool button = read_button();                                          │
│       bool docked = read_hall_sensor();                                     │
│                                                                              │
│       // Blink LED to show monitoring                                       │
│       led_blink_red(100);                                                   │
│                                                                              │
│       // Check recovery conditions                                          │
│       if (tj < 50.0 && tb < 45.0 && pressure < 1.2) {                       │
│           recovery_timer++;                                                 │
│                                                                              │
│           if (recovery_timer >= 10) {  // 5 minutes elapsed                 │
│               if (button || docked) {                                       │
│                   // User wants to restart                                  │
│                   initiate_recovery();                                      │
│               } else {                                                       │
│                   // Ready but waiting for user                             │
│                   led_blink_green(100);                                     │
│               }                                                              │
│           }                                                                  │
│       } else {                                                               │
│           recovery_timer = 0;  // Reset cooldown                            │
│       }                                                                      │
│   }                                                                          │
│                                                                              │
│   RECOVERY SEQUENCE:                                                         │
│   ─────────────────────────────────────────────────────────────────────     │
│   1. Power on main PMIC                                                     │
│   2. Boot QCS6490 (normal boot sequence)                                    │
│   3. Display: "Recovered from safety shutdown"                               │
│   4. Voice: "All cooled down. Ready to go."                                 │
│   5. Push: "Orb has recovered and is ready"                                 │
│   6. Clear shutdown flags                                                   │
│   7. Log recovery event                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Manual Recovery (Service Mode)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MANUAL RECOVERY / SERVICE MODE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   For persistent issues or after burst disk rupture:                         │
│                                                                              │
│   ENTRY:                                                                     │
│   1. Press and hold button for 10 seconds while docked                      │
│   2. LED: Blue pulse pattern                                                │
│   3. Voice: "Service mode activated"                                        │
│                                                                              │
│   SERVICE MODE FEATURES:                                                     │
│   • Bypass thermal limits (for diagnostics only)                            │
│   • Display raw sensor values                                               │
│   • Enable USB debug console                                                │
│   • Allow firmware update                                                   │
│   • Reset to factory defaults                                               │
│                                                                              │
│   SERVICE MODE RESTRICTIONS:                                                 │
│   • 10-minute timeout (auto-exit)                                           │
│   • Cannot disable CBF monitoring                                           │
│   • Cannot disable battery protection                                       │
│   • Cannot disable pressure monitoring                                      │
│                                                                              │
│   BURST DISK REPLACEMENT:                                                    │
│   If burst disk has ruptured:                                               │
│   1. Service mode will detect (pressure sensor shows ambient)               │
│   2. Display: "BURST DISK TRIGGERED - SERVICE REQUIRED"                     │
│   3. Voice: "Internal pressure relief activated. Service is required."      │
│   4. System will boot but with warning                                      │
│   5. Push persistent notification until service complete                    │
│   6. After disk replacement, technician clears flag                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Privacy Camera Indicator

### 6.1 Physical Indicator Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CAMERA PRIVACY INDICATOR                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   REQUIREMENT: Physical indicator when camera is active                      │
│   LOCATION: Adjacent to camera lens, visible from front                     │
│                                                                              │
│                       FRONT VIEW OF DISPLAY                                  │
│                                                                              │
│                        ┌───────────────────┐                                │
│                       ╱                     ╲                               │
│                     ╱     ┌───────────┐      ╲                              │
│                   ╱       │   PUPIL   │        ╲                            │
│                  │        │  (camera  │          │                          │
│                  │        │  behind)  │   ● ◄────┼─── PRIVACY LED           │
│                  │        └───────────┘          │     (RED when camera on) │
│                   ╲                            ╱                            │
│                     ╲                        ╱                              │
│                       ╲                    ╱                                │
│                        └───────────────────┘                                │
│                                                                              │
│   LED SPECIFICATION:                                                         │
│   ├── Type: 0603 SMD LED, high-intensity red                               │
│   ├── Part: Kingbright APHHS1005SURCK                                       │
│   ├── Wavelength: 630nm (visible, not infrared)                             │
│   ├── Brightness: 200 mcd (clearly visible in daylight)                     │
│   ├── Location: 3mm from display edge, at "2 o'clock" position             │
│   ├── Light pipe: Acrylic, 2mm diameter                                    │
│   └── Control: Direct hardware tie to camera power rail                     │
│                                                                              │
│   HARDWARE INTERLOCK:                                                        │
│   ──────────────────────────────────────────────────────────────────────    │
│                                                                              │
│       Camera Power Rail (1.8V_CAM)                                          │
│              │                                                               │
│              ├────────┬────────────────────────────┐                        │
│              │        │                            │                        │
│              ▼        ▼                            ▼                        │
│         ┌───────┐  ┌───────┐                  ┌───────┐                    │
│         │ IMX989│  │Privacy│◄── 200Ω ───────│GPIO28 │                     │
│         │ Sensor│  │  LED  │                  │(status│                    │
│         └───────┘  └───────┘                  │ only) │                    │
│                                               └───────┘                    │
│                                                                              │
│   CRITICAL: LED is powered DIRECTLY from camera rail.                        │
│   Software CANNOT turn on camera without LED illuminating.                   │
│   This is a HARDWARE interlock, not software-controllable.                  │
│                                                                              │
│   GPIO28 is READ-ONLY for status reporting to firmware.                     │
│   Firmware cannot affect LED state except by controlling camera power.      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Privacy States

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRIVACY STATE MACHINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   STATE              LED       CAMERA POWER    NOTES                         │
│   ──────────────────────────────────────────────────────────────────────    │
│   CAMERA_OFF         OFF       OFF             Default state                 │
│   CAMERA_ACTIVE      RED       ON              Recording/streaming           │
│   PRIVACY_MODE       OFF       OFF             User-invoked privacy          │
│                      (triple                   (persists across reboots)    │
│                       blink)                                                 │
│                                                                              │
│   STATE TRANSITIONS:                                                         │
│                                                                              │
│        ┌─────────────────────────────────────────────────────────┐          │
│        │                                                         │          │
│        │   ┌───────────┐    user speaks    ┌──────────────────┐ │          │
│        │   │           │   "privacy mode"  │                  │ │          │
│        └──►│ CAMERA_OFF│─────────────────►│   PRIVACY_MODE   │─┘          │
│            │           │                   │                  │            │
│            └─────┬─────┘                   └────────┬─────────┘            │
│                  │                                  │                       │
│                  │ vision task                      │ "camera on" or        │
│                  │ requested                        │ "exit privacy"        │
│                  ▼                                  ▼                       │
│            ┌─────────────┐                   ┌──────────────────┐           │
│            │             │                   │                  │           │
│            │CAMERA_ACTIVE│◄──────────────────│   (deny until    │           │
│            │             │   (requires user  │    explicit      │           │
│            │ LED = RED   │    confirmation)  │    consent)      │           │
│            │             │                   │                  │           │
│            └─────────────┘                   └──────────────────┘           │
│                  │                                                          │
│                  │ vision task complete                                     │
│                  │ OR user says "camera off"                               │
│                  ▼                                                          │
│            ┌─────────────┐                                                  │
│            │ CAMERA_OFF  │                                                  │
│            │             │                                                  │
│            │ LED = OFF   │                                                  │
│            └─────────────┘                                                  │
│                                                                              │
│   PRIVACY MODE ENTRY/EXIT:                                                   │
│   • Entry: "Hey Kagami, privacy mode" → triple blink → LED off              │
│   • Persistence: Survives reboot until explicitly exited                    │
│   • Exit: "Hey Kagami, camera on" or "exit privacy mode"                    │
│   • Voice confirmation required for exit                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Implementation Checklist

### 7.1 Firmware Requirements

| Feature | Priority | Status | Owner |
|---------|----------|--------|-------|
| Thermal state machine | P0 | DESIGNED | Firmware |
| Temperature sensor drivers | P0 | Pending | BSP |
| Power limit enforcement | P0 | DESIGNED | Firmware |
| Voice alert library | P1 | DESIGNED | Audio |
| Push notification integration | P1 | Pending | Cloud |
| Pressure monitoring task | P1 | DESIGNED | Firmware |
| CBF violation handler | P0 | DESIGNED | Firmware |
| Graceful shutdown sequence | P0 | DESIGNED | Firmware |
| Emergency hard shutdown | P0 | DESIGNED | ESP32 |
| Recovery logic | P1 | DESIGNED | ESP32 |
| Privacy LED interlock | P0 | DESIGNED | Hardware |

### 7.2 Hardware Requirements

| Component | Specification | Status |
|-----------|---------------|--------|
| Junction temp sensor | NTC on QCS6490 (via PMIC) | Available |
| Surface temp sensor | NTC on shell (wired to ESP32) | Add to BOM |
| Battery temp sensor | NTC integrated in BMS | Available |
| Pressure sensor | MS5837-30BA on main PCB | Add to BOM |
| Privacy LED | 0603 RED, 200mcd | Add to BOM |
| Privacy LED light pipe | 2mm acrylic rod | Add to BOM |
| Status LED ring | HD108 (existing) | Available |

---

## 8. Conclusion

The Kagami Orb V3.1 emergency shutdown system provides:

| Requirement | Solution | Status |
|-------------|----------|--------|
| Thermal protection | 5-stage throttling + shutdown | DESIGNED |
| CBF enforcement | h(x) >= 0 monitoring loop | DESIGNED |
| User notification | Voice + LED + Push escalation | DESIGNED |
| Graceful shutdown | 5.5s coordinated power-down | DESIGNED |
| Emergency shutdown | 100ms hard power cut | DESIGNED |
| Recovery | Automatic with user trigger | DESIGNED |
| Privacy indicator | Hardware-interlocked LED | DESIGNED |

---

```
h(x) >= 0. Always.

Every thermal transition managed.
Every CBF violation caught.
Every shutdown graceful.
Every recovery safe.

The compact mirror protects itself.

鏡
```
