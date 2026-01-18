# Kagami Orb V3.1 — Magnetic PTZ System

## Overview

The levitating orb presents a unique opportunity: **it's already unconstrained in space**. By manipulating the electromagnetic field, we can give the orb full **Pan-Tilt-Zoom control** without any mechanical gimbals.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     MAGNETIC PTZ CONTROL CONCEPT                                 │
│                                                                                  │
│                              PAN (Yaw)                                          │
│                                 ↻                                               │
│                          ╭─────────────╮                                        │
│                         │   📷 👁️     │  ← Camera tracks with eye              │
│                          ╰──────┬──────╯                                        │
│                                 │                                               │
│                          TILT (Pitch)                                           │
│                           ↙     │     ↘                                         │
│                    ±20°        │        ±20°                                    │
│                                 │                                               │
│                    ╔═══════════╧═══════════╗                                    │
│                    ║   TORQUE COIL ARRAY    ║                                   │
│                    ║  ◉     MAGLEV     ◉    ║  ← 4 peripheral coils             │
│                    ║      ╭───────╮          ║                                   │
│                    ║  ◉   │ MAIN  │   ◉      ║  ← Differential energization     │
│                    ║      │ COIL  │          ║     creates rotation torque      │
│                    ║      ╰───────╯          ║                                   │
│                    ╚════════════════════════╝                                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Physics Basis

### How It Works

1. **Levitation** maintains vertical position via main electromagnet
2. **Torque coils** create asymmetric fields that rotate the orb
3. **Hall sensors** provide closed-loop feedback for position
4. **PID controller** maintains stable orientation

### Torque Generation

```
τ = m × B

Where:
  τ = torque vector (N·m)
  m = magnetic moment of orb's permanent magnet (A·m²)
  B = magnetic field from torque coils (T)

The cross product means:
- Field perpendicular to magnet → maximum torque
- Field parallel to magnet → zero torque (levitation)
```

### Degrees of Freedom

| DOF | Name | Range | Method | Difficulty |
|-----|------|-------|--------|------------|
| **Pan** | Yaw (Z-axis rotation) | **360° continuous** | Rotating field | ⭐ Easy |
| **Tilt** | Pitch (X-axis) | **±20°** | Asymmetric pull | ⭐⭐ Medium |
| **Roll** | Roll (Y-axis) | **±20°** | Asymmetric pull | ⭐⭐ Medium |
| **Zoom** | Camera zoom | 1×–10× | Digital (IMX989) | ⭐ Easy |

---

## Hardware Design

### Base Coil Array

```
                    TOP VIEW OF BASE
        ┌─────────────────────────────────────────┐
        │                                         │
        │            ◉ COIL_N (North)             │
        │                                         │
        │                                         │
        │    ◉                     ◉              │
        │  COIL_W           ╭───────╮   COIL_E    │
        │  (West)           │ MAIN  │   (East)    │
        │                   │ LEVIT │             │
        │                   ╰───────╯             │
        │                                         │
        │            ◉ COIL_S (South)             │
        │                                         │
        │  ┌─────┐                    ┌─────┐     │
        │  │HALL1│                    │HALL2│     │
        │  └─────┘                    └─────┘     │
        │                                         │
        │  ┌─────┐                    ┌─────┐     │
        │  │HALL3│                    │HALL4│     │
        │  └─────┘                    └─────┘     │
        └─────────────────────────────────────────┘
```

### Coil Specifications

| Coil | Purpose | Inductance | Current | Wire |
|------|---------|------------|---------|------|
| **MAIN** | Levitation | 1 mH | 0–2A | 18 AWG |
| **COIL_N** | Tilt North | 100 µH | 0–500mA | 22 AWG |
| **COIL_S** | Tilt South | 100 µH | 0–500mA | 22 AWG |
| **COIL_E** | Tilt East | 100 µH | 0–500mA | 22 AWG |
| **COIL_W** | Tilt West | 100 µH | 0–500mA | 22 AWG |

### Hall Sensor Array

4× Hall effect sensors (DRV5053) detect the orb's magnetic field angle:

```rust
struct OrbOrientation {
    yaw: f32,    // 0–360° rotation
    pitch: f32,  // -20° to +20° forward/back tilt
    roll: f32,   // -20° to +20° left/right tilt
}

fn calculate_orientation(hall_readings: [i16; 4]) -> OrbOrientation {
    // Hall sensors detect field strength at 4 points
    // Differential readings give orientation
    let north_south = hall_readings[0] - hall_readings[2];
    let east_west = hall_readings[1] - hall_readings[3];

    OrbOrientation {
        yaw: atan2(east_west, north_south).to_degrees(),
        pitch: (north_south as f32 / MAX_READING) * 20.0,
        roll: (east_west as f32 / MAX_READING) * 20.0,
    }
}
```

---

## Control System

### Pan Control (Yaw)

Create a rotating magnetic field by phase-shifting coil currents:

```rust
/// Generate rotating field for pan control
fn pan_control(target_angle: f32, speed: f32) -> CoilCurrents {
    let phase = target_angle.to_radians();

    CoilCurrents {
        north: (phase.cos() * speed).clamp(-1.0, 1.0),
        south: (-phase.cos() * speed).clamp(-1.0, 1.0),
        east: (phase.sin() * speed).clamp(-1.0, 1.0),
        west: (-phase.sin() * speed).clamp(-1.0, 1.0),
    }
}

// Continuous 360° rotation
async fn pan_to(&mut self, target_yaw: f32) {
    loop {
        let current = self.hall_sensors.read_orientation().yaw;
        let error = angle_diff(target_yaw, current);

        if error.abs() < 2.0 { break; }  // ±2° tolerance

        let speed = self.pid_yaw.update(error);
        self.set_coil_currents(pan_control(current + error.signum() * 10.0, speed));

        sleep(10.ms()).await;
    }
}
```

### Tilt Control (Pitch/Roll)

Pull one side of the orb down by energizing coils asymmetrically:

```rust
/// Generate tilt by asymmetric field
fn tilt_control(pitch: f32, roll: f32) -> CoilCurrents {
    // pitch > 0 = tilt forward (camera looks down)
    // roll > 0 = tilt right

    CoilCurrents {
        north: (-pitch * 0.3).clamp(-0.5, 0.5),  // Pull north down = tilt forward
        south: (pitch * 0.3).clamp(-0.5, 0.5),
        east: (-roll * 0.3).clamp(-0.5, 0.5),
        west: (roll * 0.3).clamp(-0.5, 0.5),
    }
}

async fn tilt_to(&mut self, target_pitch: f32, target_roll: f32) {
    // Clamp to safe range
    let pitch = target_pitch.clamp(-20.0, 20.0);
    let roll = target_roll.clamp(-20.0, 20.0);

    loop {
        let current = self.hall_sensors.read_orientation();
        let pitch_error = pitch - current.pitch;
        let roll_error = roll - current.roll;

        if pitch_error.abs() < 1.0 && roll_error.abs() < 1.0 { break; }

        let currents = tilt_control(
            self.pid_pitch.update(pitch_error),
            self.pid_roll.update(roll_error),
        );
        self.set_coil_currents(currents);

        sleep(10.ms()).await;
    }
}
```

### Stability Protection

**CRITICAL:** Tilt affects levitation stability. Implement safety limits:

```rust
const MAX_TILT_ANGLE: f32 = 20.0;  // Degrees
const LEVITATION_MARGIN: f32 = 0.8;  // 80% of max lift force reserved

fn safety_check(&self, requested_tilt: f32) -> bool {
    // Tilt reduces effective levitation force by cos(angle)
    let tilt_rad = requested_tilt.to_radians();
    let lift_factor = tilt_rad.cos();

    // Ensure we have margin for stable levitation
    lift_factor >= LEVITATION_MARGIN
}

// If orb starts to fall, immediately center
async fn emergency_level(&mut self) {
    self.set_coil_currents(CoilCurrents::zero());
    self.orb_state.transition_to(OrbState::SafetyRecovery);
}
```

---

## PTZ API

### Commands

```rust
pub enum PtzCommand {
    /// Pan to absolute angle (0-360°)
    PanTo { yaw: f32 },

    /// Pan relative to current position
    PanBy { delta: f32 },

    /// Continuous pan at speed (-1.0 to 1.0)
    PanContinuous { speed: f32 },

    /// Tilt to absolute angles
    TiltTo { pitch: f32, roll: f32 },

    /// Combined PTZ move
    MoveTo { yaw: f32, pitch: f32, roll: f32 },

    /// Digital zoom (1.0 to 10.0)
    Zoom { factor: f32 },

    /// Return to home position (centered, level)
    Home,

    /// Track a face/object (auto PTZ)
    Track { target: TrackingTarget },
}

pub enum TrackingTarget {
    Face { id: Option<u32> },  // Track specific or any face
    Motion,                    // Track motion center
    Sound { direction: f32 },  // Point toward sound source
}
```

### WebSocket Interface

```json
// Client → Orb
{ "ptz": { "pan_to": 45.0 } }
{ "ptz": { "tilt_to": { "pitch": -10.0, "roll": 0.0 } } }
{ "ptz": { "zoom": 2.5 } }
{ "ptz": { "track": { "face": null } } }  // Track any face
{ "ptz": "home" }

// Orb → Client (status updates)
{
  "ptz_status": {
    "yaw": 45.2,
    "pitch": -9.8,
    "roll": 0.1,
    "zoom": 2.5,
    "tracking": "face",
    "stable": true
  }
}
```

---

## Use Cases

### 1. Face Tracking During Conversation

```
"Hey Kagami" → Orb detects speaker location → Pans to face them
                                             → Eye looks at them
                                             → Camera centered on face
```

### 2. Room Scanning

```
"Kagami, look around" → Orb does slow 360° pan
                       → Camera records panorama
                       → "I see the living room, kitchen, and Tim at the desk"
```

### 3. Security Mode

```
Motion detected → Orb pans to motion source
               → Camera zooms in
               → "I noticed movement near the front door"
```

### 4. Presentation Mode

```
"Kagami, watch my presentation" → Orb tracks the display/screen
                                → Zooms to capture slides
                                → Records meeting
```

### 5. Pet/Baby Monitoring

```
"Kagami, watch Luna" → Orb tracks cat movement
                     → Auto-adjusts zoom
                     → Alerts if pet leaves room
```

---

## Alternative: Internal Magnetorquer

For even finer control, we could add **coils inside the orb** that interact with the base's field:

```
┌─────────────────────────────────────────────────────────────────┐
│              INTERNAL MAGNETORQUER OPTION                        │
│                                                                  │
│                    ╭───────────────────╮                        │
│                   │    Z-AXIS COIL     │  ← Yaw torque          │
│                   │  ┌───────────────┐ │                        │
│                   │  │ ╭───────────╮ │ │                        │
│                   │  │ │  X-COIL   │ │ │  ← Pitch torque        │
│                   │  │ │  ╭─────╮  │ │ │                        │
│                   │  │ │  │Y-COIL│  │ │ │  ← Roll torque        │
│                   │  │ │  ╰─────╯  │ │ │                        │
│                   │  │ ╰───────────╯ │ │                        │
│                   │  └───────────────┘ │                        │
│                    ╰───────────────────╯                        │
│                                                                  │
│  • 3 orthogonal coils inside orb                                │
│  • Interact with base's magnetic field                          │
│  • Like satellite magnetorquers                                 │
│  • Pros: Very precise, less base complexity                     │
│  • Cons: Uses orb's limited internal space                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Comparison

| Approach | Pros | Cons | Recommended |
|----------|------|------|-------------|
| **Base torque coils** | Simple orb, all control in base | Limited tilt range | ✅ V3 |
| **Internal magnetorquer** | Fine control, 3-axis | Uses orb space, power | V4 |
| **Reaction wheel** | Very precise yaw | Adds mass, complexity | V4 |

---

## Bill of Materials (PTZ Addon)

| Component | Part Number | Qty | Unit Cost | Purpose |
|-----------|-------------|-----|-----------|---------|
| Torque coil 100µH | Custom wound | 4 | $5 | Orientation control |
| DRV5053 Hall sensor | DRV5053EAQLPG | 4 | $0.80 | Position feedback |
| DRV8833 Motor driver | DRV8833PWP | 2 | $2.50 | Coil current control |
| **Total** | | | **~$30** | |

---

## Integration with Living Eye

The PTZ system and living eye work together:

```
┌─────────────────────────────────────────────────────────────────┐
│                PTZ + EYE COORDINATION                           │
│                                                                  │
│   Person moves left                                              │
│         ↓                                                        │
│   Face detection identifies new position                         │
│         ↓                                                        │
│   ┌─────┴─────┐                                                  │
│   ↓           ↓                                                  │
│   Eye pupil   Orb pans     (simultaneous)                       │
│   tracks      to center                                          │
│   left        person                                             │
│   ↓           ↓                                                  │
│   └─────┬─────┘                                                  │
│         ↓                                                        │
│   Camera centered on face                                        │
│   Eye looking at person                                          │
│   Natural, alive appearance                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

The eye can "look" independently via software animation, while PTZ moves the whole orb for larger adjustments. This creates incredibly lifelike behavior!

---

## Safety Constraints

```rust
// h(x) ≥ 0 for PTZ operations
fn ptz_safety_barrier(state: &OrbState) -> f32 {
    let tilt_margin = 1.0 - (state.pitch.abs() + state.roll.abs()) / MAX_TILT_ANGLE;
    let levitation_stable = state.levitation_force / state.orb_weight;
    let thermal_ok = 1.0 - state.coil_temp / MAX_COIL_TEMP;

    // Minimum of all safety factors
    tilt_margin.min(levitation_stable - 1.0).min(thermal_ok)
}

// If h(x) < 0, emergency level
if ptz_safety_barrier(&state) < 0.0 {
    emergency_level().await;
}
```

---

## Conclusion

The Kagami Orb's magnetic levitation enables **contactless PTZ control**:

- ✅ **360° continuous pan** via rotating field
- ✅ **±20° tilt** via asymmetric field
- ✅ **10× digital zoom** via IMX989
- ✅ **Face/motion tracking** via AI
- ✅ **Coordinated with living eye** for natural appearance

This transforms the orb from a static display to an **active, attentive presence** that can look around, track faces, and engage with the room.

---

## Changelog

### V1.0 (January 2026)
- Initial magnetic PTZ design
- Base torque coil array approach
- Integration with V3 living eye system
