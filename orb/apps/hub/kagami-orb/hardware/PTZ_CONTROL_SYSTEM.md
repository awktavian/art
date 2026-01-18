# Kagami Orb — Magnetic PTZ Control System

**Date:** January 2026
**Status:** SPECIFICATION (with firmware implementation)
**CANONICAL REFERENCE:** See `hardware/SPECS.md` for hardware specifications

---

## Design Summary

| Parameter | Value |
|-----------|-------|
| Diameter | 95mm |
| Mass | 420g |
| PTZ Range | ±20° pitch/roll, 360° pan |
| Cellular | Quectel EG25-G (LTE Cat 4) |
| Coils | 8 (maglev + PTZ) |
| Peak Power | 45W (burst), 20W (sustained) |

---

## Overview

The Kagami Orb uses magnetic levitation for floating. When docked, we can manipulate the electromagnetic field to create **Pan-Tilt-Zoom (PTZ)** control without any mechanical gimbals.

---

## Degrees of Freedom

| DOF | Name | Range | Method | Speed |
|-----|------|-------|--------|-------|
| **Pan** | Yaw (Z-axis) | 360° continuous | Rotating magnetic field | 90°/s |
| **Tilt** | Pitch (X-axis) | ±20° | Differential lift force | 30°/s |
| **Roll** | Roll (Y-axis) | ±20° | Differential lift force | 30°/s |
| **Zoom** | Digital | 1×–10× | IMX989 crop/interpolation | Instant |

---

## Physical Principles

### Levitation Force

The orb contains a permanent magnet array. The base contains electromagnets that:
1. Provide levitation force (upward, opposing gravity)
2. Provide stabilization (restoring force when displaced)

**Levitation equilibrium:**
```
F_lift = m × g

Where:
  F_lift = electromagnetic lift force (N)
  m = orb mass = 0.420 kg (V3.2 95mm with cellular)
  g = 9.81 m/s²

F_lift_required = 0.420 × 9.81 = 4.12 N
```

### Torque Generation

To tilt the orb, we create asymmetric forces:

```
        Side View (Pitch)
        ═════════════════

                     ↑ F_front (increased)
                     │
            ╭────────┼────────╮
            │        │        │
            │    ⬡   │   ⬡    │  ← Orb rotates
            │        │        │     about center
            ╰────────┼────────╯
                     │
                     ↑ F_back (decreased)

            ════════════════════
                   BASE

Torque τ = (F_front - F_back) × r

Where r = radius from center to force application point (~30mm)
```

### Force-Current Relationship

For an electromagnet:
```
F = k × I² / d²

Where:
  k = coil constant (depends on geometry, turns, core material)
  I = current (A)
  d = distance from coil to magnet (m)
```

For our coils (N=200 turns, Ø25mm core):
```
k ≈ 2.5 × 10⁻⁴ N·m²/A²

At neutral levitation d = 20mm = 0.020m (midpoint of 18-25mm range):
F = 2.5 × 10⁻⁴ × I² / (0.020)² = 0.625 × I² N

For I = 1.5A (max V3.2):  F = 1.41 N per coil
For I = 1.0A (base):      F = 0.625 N per coil

Total lift at base current: 8 × 0.625 = 5.0 N
Required lift (420g): 0.420 × 9.81 = 4.12 N
Margin: 21% at neutral gap (more at closer gaps)
```

**Gap Sensitivity:**
- At 18mm: F ∝ 1/(0.018)² = +23% more force
- At 25mm: F ∝ 1/(0.025)² = -36% less force
- System auto-adjusts current to maintain levitation

---

## Coil Array Design

### Configuration: 8 Coils in Ring

```
            Top View of Base (looking down)
            ════════════════════════════════

                        N (0°)
                         ◎
                    NW ◎   ◎ NE
                  (315°)   (45°)

                W ◎    ⬡    ◎ E
              (270°)  ORB  (90°)

                    SW ◎   ◎ SE
                  (225°)   (135°)
                         ◎
                        S (180°)

            Coil positions: θᵢ = i × 45°  for i = 0..7
            Coil radius from center: R = 40mm
```

### Coil Specifications (V3.2)

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Quantity** | 8 | Ring arrangement, 45° spacing |
| **Coil tilt** | 15° outward | For yaw torque generation |
| **Turns** | 200 | AWG 24 enameled copper |
| **Core diameter** | 25mm | Ferrite core |
| **Core height** | 15mm | Standard pot core |
| **Resistance** | **2.5Ω** | CANONICAL (measured) |
| **Inductance** | 8mH | At 1kHz |
| **Max current** | **1.5A** | Thermal-limited (was 2.5A) |
| **Base current** | 1.0A | Neutral lift contribution |
| **Control rate** | 500Hz | 2ms loop period |

### Total Power Budget (V3.2 — Passive Cooling)

| Mode | Current/Coil | Power/Coil | Total (8 coils) | Duration |
|------|--------------|------------|-----------------|----------|
| Levitation only | 1.0A | 2.5W | 20W | Continuous |
| +20° tilt | 1.2A (front) | 3.6W | 28W | Continuous |
| Burst (max PTZ) | 1.5A (peak) | 5.6W | **45W** | ≤30s |
| Cooldown | 0.8A (all) | 1.6W | 12.8W | 60s after burst |
| Emergency level | 1.0A (all) | 2.5W | 20W | Until reset |

### Passive Thermal Management

**No active cooling fan** — base station maintains splash resistance (IPX4).

**Thermal dissipation path:**
```
PTZ Coils → Thermal Potting (Bergquist 3500S35) → Aluminum Spreader (110×110×3mm)
          → Graphite TIM → Walnut Enclosure → Table/Air
```

**Passive dissipation capacity:**
- Continuous: ~25W
- Burst (thermal mass): 45W for ≤30s

### Firmware ThermalAccumulator

The `ThermalAccumulator` enforces duty cycle limits to prevent overheating:

```rust
pub enum ThermalState {
    Normal,           // Full 1.5A available
    Burst { remaining_s },  // 1.5A for up to 30s
    Cooldown { remaining_s }, // 0.8A max for 60s
}
```

**State transitions:**
1. **Normal → Burst**: Power exceeds 25W threshold
2. **Burst → Cooldown**: 30s elapsed OR energy threshold exceeded
3. **Cooldown → Normal**: 60s elapsed AND energy < 30% threshold

---

## Mathematical Model

### Coordinate System

```
        Z (up)
        │
        │    Y (right)
        │   ╱
        │  ╱
        │ ╱
        └────────── X (forward)

Pan (θ_z):   Rotation about Z
Pitch (θ_x): Rotation about X (nose up/down)
Roll (θ_y):  Rotation about Y (left/right tilt)
```

### Coil Position Vectors

```python
# Position of coil i in base frame
def coil_position(i):
    """Return (x, y, z) of coil i center."""
    theta = i * (2 * pi / 8)  # 0, 45, 90, ... degrees
    R = 0.040  # 40mm radius
    return (R * cos(theta), R * sin(theta), 0)
```

### Force Calculation

```python
def coil_force(I, d, theta):
    """
    Calculate force vector from a single coil.

    Args:
        I: Current in coil (A)
        d: Distance from coil to orb magnet (m)
        theta: Angle of coil from center (rad)

    Returns:
        (Fx, Fy, Fz) force vector in Newtons
    """
    k = 2.5e-4  # Coil constant (N·m²/A²)

    # Force magnitude (always attractive toward coil)
    F_mag = k * I**2 / d**2

    # Force direction (from orb toward coil)
    # For small tilts, mostly vertical (Fz dominant)
    # Horizontal components create centering force

    Fx = -F_mag * sin(theta) * 0.1  # Small radial component
    Fy = -F_mag * cos(theta) * 0.1
    Fz = F_mag * 0.99  # Mostly vertical

    return (Fx, Fy, Fz)
```

### Torque Calculation

```python
def total_torque(currents, orb_position, orb_orientation):
    """
    Calculate total torque on orb from all coils.

    Args:
        currents: List of 8 currents [I_N, I_NE, ..., I_NW]
        orb_position: (x, y, z) of orb center
        orb_orientation: (roll, pitch, yaw) in radians

    Returns:
        (τx, τy, τz) torque vector in N·m
    """
    tau_total = [0, 0, 0]

    for i in range(8):
        # Coil position
        coil_pos = coil_position(i)

        # Vector from orb center to coil
        r = (coil_pos[0] - orb_position[0],
             coil_pos[1] - orb_position[1],
             coil_pos[2] - orb_position[2])

        # Distance
        d = sqrt(r[0]**2 + r[1]**2 + r[2]**2)

        # Coil angle
        theta = i * (2 * pi / 8)

        # Force from this coil
        F = coil_force(currents[i], d, theta)

        # Torque τ = r × F
        tau = cross_product(r, F)

        tau_total[0] += tau[0]
        tau_total[1] += tau[1]
        tau_total[2] += tau[2]

    return tau_total
```

### Current Calculation (Inverse Kinematics)

```python
def calculate_currents(pitch_cmd, roll_cmd, pan_rate, base_lift=1.0):
    """
    Calculate coil currents to achieve desired orientation.

    Args:
        pitch_cmd: Desired pitch angle (radians, -20° to +20°)
        roll_cmd: Desired roll angle (radians, -20° to +20°)
        pan_rate: Desired pan angular velocity (rad/s)
        base_lift: Base levitation current (A)

    Returns:
        List of 8 currents [I_N, I_NE, I_E, I_SE, I_S, I_SW, I_W, I_NW]
    """
    currents = []

    # Control gains (tuned experimentally)
    K_PITCH = 0.5  # A per radian
    K_ROLL = 0.5
    K_PAN = 0.3

    # Maximum current per coil
    I_MAX = 2.5

    for i in range(8):
        coil_angle = i * (2 * pi / 8)

        # Base levitation current (equal for all coils)
        I = base_lift

        # Pitch contribution
        # Front coils (N, NE, NW) increase, back coils decrease
        pitch_factor = cos(coil_angle)  # +1 at N, -1 at S
        I += pitch_cmd * K_PITCH * pitch_factor

        # Roll contribution
        # East coils increase, west coils decrease
        roll_factor = sin(coil_angle)  # +1 at E, -1 at W
        I += roll_cmd * K_ROLL * roll_factor

        # Pan contribution (rotating field for spin)
        # Creates a traveling wave around the ring
        global pan_phase
        pan_phase += pan_rate * dt
        I += K_PAN * sin(coil_angle - pan_phase)

        # Clamp to safe range
        I = max(0.2, min(I_MAX, I))  # Never fully off (stability)

        currents.append(I)

    return currents
```

---

## PID Controller

### Controller Structure

```python
class PtzPidController:
    """PID controller for PTZ orientation."""

    def __init__(self):
        # Pitch PID gains
        self.Kp_pitch = 2.0
        self.Ki_pitch = 0.5
        self.Kd_pitch = 0.8

        # Roll PID gains
        self.Kp_roll = 2.0
        self.Ki_roll = 0.5
        self.Kd_roll = 0.8

        # Pan PID gains
        self.Kp_pan = 1.5
        self.Ki_pan = 0.2
        self.Kd_pan = 0.5

        # Integral accumulators
        self.pitch_integral = 0
        self.roll_integral = 0
        self.pan_integral = 0

        # Previous errors (for derivative)
        self.prev_pitch_error = 0
        self.prev_roll_error = 0
        self.prev_pan_error = 0

        # Anti-windup limits
        self.integral_limit = 0.5  # radians

    def update(self, target, current, dt):
        """
        Compute control output.

        Args:
            target: (pitch, roll, pan) target angles
            current: (pitch, roll, pan) current angles
            dt: Time step in seconds

        Returns:
            (pitch_cmd, roll_cmd, pan_cmd) control outputs
        """
        # Pitch control
        pitch_error = target[0] - current[0]
        self.pitch_integral += pitch_error * dt
        self.pitch_integral = clip(self.pitch_integral, -self.integral_limit, self.integral_limit)
        pitch_deriv = (pitch_error - self.prev_pitch_error) / dt

        pitch_cmd = (self.Kp_pitch * pitch_error +
                     self.Ki_pitch * self.pitch_integral +
                     self.Kd_pitch * pitch_deriv)

        self.prev_pitch_error = pitch_error

        # Roll control (same structure)
        roll_error = target[1] - current[1]
        self.roll_integral += roll_error * dt
        self.roll_integral = clip(self.roll_integral, -self.integral_limit, self.integral_limit)
        roll_deriv = (roll_error - self.prev_roll_error) / dt

        roll_cmd = (self.Kp_roll * roll_error +
                    self.Ki_roll * self.roll_integral +
                    self.Kd_roll * roll_deriv)

        self.prev_roll_error = roll_error

        # Pan control (wraps at 360°)
        pan_error = normalize_angle(target[2] - current[2])
        self.pan_integral += pan_error * dt
        self.pan_integral = clip(self.pan_integral, -self.integral_limit, self.integral_limit)
        pan_deriv = (pan_error - self.prev_pan_error) / dt

        pan_cmd = (self.Kp_pan * pan_error +
                   self.Ki_pan * self.pan_integral +
                   self.Kd_pan * pan_deriv)

        self.prev_pan_error = pan_error

        return (pitch_cmd, roll_cmd, pan_cmd)
```

### Tuning Guidelines

| Parameter | Value | Effect |
|-----------|-------|--------|
| **Kp** | 2.0 | Higher = faster response, more overshoot |
| **Ki** | 0.5 | Higher = eliminates steady-state error, more oscillation |
| **Kd** | 0.8 | Higher = more damping, less overshoot |

**Ziegler-Nichols tuning:**
1. Set Ki = Kd = 0
2. Increase Kp until oscillation (Ku = 3.0)
3. Measure oscillation period (Tu = 0.5s)
4. Set: Kp = 0.6×Ku = 1.8, Ki = 2×Kp/Tu = 7.2, Kd = Kp×Tu/8 = 0.11

**Fine-tuned values** (from simulation):
- Kp = 2.0, Ki = 0.5, Kd = 0.8 for smooth, stable response

---

## Safety Barrier Function

### h_ptz(x) Definition

```python
def h_ptz(state):
    """
    Compute PTZ safety barrier value.

    h_ptz >= 0: Safe to operate
    h_ptz < 0: Emergency level required

    Args:
        state: Current system state

    Returns:
        Barrier value (float)
    """
    # Lift margin: Need F_lift > m*g to stay levitating
    lift_margin = state.lift_force / (state.orb_mass * 9.81) - 1.0

    # Tilt margin: Larger tilts are less stable
    tilt_angle = sqrt(state.pitch**2 + state.roll**2)
    tilt_margin = 1.0 - tilt_angle / radians(25)  # 25° = absolute limit

    # Thermal margin: Coils overheat if driven too hard
    max_coil_temp = max(state.coil_temperatures)
    thermal_margin = 1.0 - max_coil_temp / 85  # 85°C = coil limit

    # Combined barrier (take minimum)
    h = min(lift_margin, tilt_margin, thermal_margin)

    return h
```

### Safety Response

```python
def safety_check(state):
    """Check safety and take action if needed."""
    h = h_ptz(state)

    if h < 0:
        # EMERGENCY: Return to level immediately
        emergency_level()
        return SafetyResult.EmergencyLevel

    elif h < 0.2:
        # MARGINAL: Reduce PTZ range
        limit_tilt(max_angle=radians(10))
        return SafetyResult.Marginal

    elif h < 0.5:
        # CAUTIOUS: Reduce PTZ speed
        limit_speed(max_rate=radians(15))  # 15°/s
        return SafetyResult.Cautious

    else:
        # SAFE: Full operation
        return SafetyResult.Safe
```

---

## System Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                    ORB                                           │
│  ┌────────────┐    ┌────────────┐    ┌────────────────────────────────────────┐ │
│  │  CAMERA    │───▶│   HAILO    │───▶│         TARGET TRACKER                 │ │
│  │  IMX989    │    │  DETECTOR  │    │  • Face bounding box → pan/tilt target │ │
│  └────────────┘    └────────────┘    │  • Motion centroid → tracking          │ │
│                                       │  • Sound direction → look-at           │ │
│  ┌────────────┐                      └──────────────┬─────────────────────────┘ │
│  │    IMU     │─── Current orientation ─────────────┼─────────────────────────┐ │
│  │ ICM-45686  │                                     │                         │ │
│  └────────────┘                                     ▼                         │ │
│                                       ┌────────────────────────┐              │ │
│                                       │   PTZ COMMAND GEN      │              │ │
│                                       │ target - current = cmd │              │ │
│                                       └──────────┬─────────────┘              │ │
│                                                  │                            │ │
│  ════════════════════════════════════════════════╪════════════════════════════│ │
│                              BLE/WiFi Link       │    Orientation (100Hz)     │ │
└──────────────────────────────────────────────────┼────────────────────────────┘ │
                                                   │                              │
                                                   ▼                              ▼
┌────────────────────────────────────────────────────────────────────────────────────┐
│                                    BASE (ESP32-S3)                                  │
│                                                                                     │
│  ┌─────────────┐    ┌─────────────────────────────────────────────────────────────┐│
│  │    HALL     │───▶│                    PID CONTROLLERS                          ││
│  │  SENSORS    │    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         ││
│  │ (feedback)  │    │  │ PITCH PID   │  │  ROLL PID   │  │  PAN PID    │         ││
│  └─────────────┘    │  │ Kp=2 Ki=0.5 │  │ Kp=2 Ki=0.5 │  │ Kp=1.5      │         ││
│                      │  │ Kd=0.8      │  │ Kd=0.8      │  │ Ki=0.2 Kd=0.5│        ││
│                      │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        ││
│                      └─────────┼────────────────┼────────────────┼───────────────┘│
│                                │                │                │                │
│                                ▼                ▼                ▼                │
│                      ┌────────────────────────────────────────────────────────┐  │
│                      │            COIL CURRENT CALCULATOR                     │  │
│                      │                                                        │  │
│                      │  for i in 0..8:                                       │  │
│                      │    θ = i × 45°                                        │  │
│                      │    I[i] = I_base                                      │  │
│                      │         + pitch_cmd × K_pitch × cos(θ)                │  │
│                      │         + roll_cmd × K_roll × sin(θ)                  │  │
│                      │         + pan_cmd × K_pan × sin(θ - φ)                │  │
│                      │                                                        │  │
│                      └────────────────────────┬───────────────────────────────┘  │
│                                               │                                   │
│                                               ▼                                   │
│                      ┌────────────────────────────────────────────────────────┐  │
│                      │              PWM DRIVERS (8 channels)                  │  │
│                      │  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐     │  │
│                      │  │ N │ │NE │ │ E │ │SE │ │ S │ │SW │ │ W │ │NW │     │  │
│                      │  └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘     │  │
│                      └────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼────────┘  │
│                           │     │     │     │     │     │     │     │           │
│                           ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼           │
│                      ┌────────────────────────────────────────────────────────┐  │
│                      │            8× ELECTROMAGNETIC COILS                    │  │
│                      │         (200 turns each, Ø25mm, 2.5A max)              │  │
│                      └────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                          SAFETY MONITOR                                      │ │
│  │  h_ptz = min(lift_margin, tilt_margin, thermal_margin)                      │ │
│  │  IF h_ptz < 0 → EMERGENCY LEVEL (all coils to base current)                 │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Timing Requirements

| Component | Rate | Latency Budget |
|-----------|------|----------------|
| IMU sampling | 1000 Hz | 1ms |
| Orientation fusion | 500 Hz | 2ms |
| Orientation TX (BLE) | 100 Hz | 10ms |
| Face detection | 30 Hz | 33ms |
| Target tracker | 50 Hz | 20ms |
| PTZ command TX | 50 Hz | 20ms |
| Base PID loop | 500 Hz | 2ms |
| PWM update | 20 kHz | 0.05ms |

**End-to-end latency:**
- Face detected → coil response: **<50ms**
- Manual command → motion start: **<20ms**

---

## Tracking Modes

### 1. Face Tracking

```python
class FaceTracker:
    """Track detected faces with PTZ."""

    def __init__(self, camera_type="ov5647"):
        self.smoothing = 0.3  # Low-pass filter coefficient
        self.target_pan = 0
        self.target_pitch = 0

        # Camera FoV depends on tracking camera used
        # OV5647: 62.2° × 48.8° (default, low-power tracking)
        # IMX989: 84° × 63° (optional, high-resolution)
        if camera_type == "imx989":
            self.h_fov = 84.0
            self.v_fov = 63.0
        else:  # ov5647 default
            self.h_fov = 62.2
            self.v_fov = 48.8

    def update(self, face_bbox, frame_size):
        """
        Update target from face detection.

        Args:
            face_bbox: (x, y, w, h) of face in frame
            frame_size: (width, height) of frame
        """
        if face_bbox is None:
            return

        # Face center in normalized coordinates (-1 to 1)
        face_cx = (face_bbox[0] + face_bbox[2]/2) / frame_size[0] * 2 - 1
        face_cy = (face_bbox[1] + face_bbox[3]/2) / frame_size[1] * 2 - 1

        # Convert to pan/tilt angles (half FoV for each direction)
        pan_offset = face_cx * radians(self.h_fov / 2)
        pitch_offset = -face_cy * radians(self.v_fov / 2)

        # Smooth target update
        self.target_pan = lerp(self.target_pan, pan_offset, self.smoothing)
        self.target_pitch = lerp(self.target_pitch, pitch_offset, self.smoothing)

        return (self.target_pitch, 0, self.target_pan)
```

### 2. Sound Tracking

```python
class SoundTracker:
    """Track sound source direction with PTZ."""

    def update(self, doa_azimuth, doa_elevation):
        """
        Update target from Direction of Arrival.

        Args:
            doa_azimuth: Sound direction horizontal (radians)
            doa_elevation: Sound direction vertical (radians)
        """
        # XMOS XVF3800 provides DOA from beamforming
        target_pan = doa_azimuth
        target_pitch = doa_elevation

        return (target_pitch, 0, target_pan)
```

### 3. Motion Tracking

```python
class MotionTracker:
    """Track motion centroid with PTZ."""

    def update(self, motion_mask):
        """
        Update target from motion detection.

        Args:
            motion_mask: Binary mask of moving pixels
        """
        # Find centroid of motion
        moments = cv2.moments(motion_mask)
        if moments['m00'] > 0:
            cx = moments['m10'] / moments['m00']
            cy = moments['m01'] / moments['m00']

            # Convert to angles (same as face tracking)
            ...
```

---

## Hardware Requirements

### Base Station Additions

| Component | Qty | Purpose |
|-----------|-----|---------|
| Torque coils | 4 | Additional coils for PTZ (total 8) |
| MOSFET H-bridge | 8 | Bidirectional current control |
| Current sensors | 8 | Feedback for each coil |
| Hall sensors | 4 | Orb position/orientation sensing |
| Thermal sensors | 8 | Coil temperature monitoring |

### Power Supply

| Requirement | Value |
|-------------|-------|
| Voltage | 24V DC |
| Peak current | 20A (all coils max) |
| Continuous | 8A (levitation + moderate PTZ) |
| PSU rating | 60W minimum, 120W recommended |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial specification |
| 1.1 | Jan 2026 | V3.2 updates: 95mm orb (420g), passive thermal management, ThermalAccumulator firmware, 15° coil tilt for yaw torque |

---

**Document Status:** SPECIFICATION
**Next Action:** Firmware implementation complete — see `firmware/base/src/ptz/`
**Author:** Kagami (鏡)
