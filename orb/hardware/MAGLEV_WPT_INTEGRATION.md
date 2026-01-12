# Magnetic Levitation + Wireless Power Transfer Integration

## Overview

This document specifies the integration of HCNT-style magnetic levitation with resonant wireless power transfer, featuring dynamic height control for optimized charging efficiency and animated "bobble" effects.

```
                     OPERATING MODES

    FLOAT (Normal)          SINK (Charging)         BOBBLE (Animation)
    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
    │      ○      │  20mm   │      ○      │  5mm    │      ○      │  15-25mm
    │             │         │             │         │      ↕      │  oscillating
    └─────────────┘         └─────────────┘         └─────────────┘
    ~75% efficiency         ~90% efficiency         ~80% average
    Full PTZ range          Limited PTZ             Expressive motion
```

---

## 1. System Architecture

### 1.1 Magnetic Levitation Subsystem

The HCNT ZT-HX500 maglev module uses **electromagnetic suspension (EMS)** with feedback control:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MAGLEV CONTROL ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                 │
│    │   Height    │ --> │    PID      │ --> │  PWM        │                 │
│    │   Sensor    │     │  Controller │     │  Driver     │                 │
│    │  (Hall Eff) │     │             │     │  (MOSFET)   │                 │
│    └─────────────┘     └──────┬──────┘     └──────┬──────┘                 │
│          ↑                    │                   │                         │
│          │                    │ setpoint          │ current                 │
│          │              ┌─────┴─────┐       ┌─────┴─────┐                   │
│          │              │  Height   │       │ Electro-  │                   │
│          └──────────────│  Target   │       │ magnet    │                   │
│                         │ (5-25mm)  │       │ Coil      │                   │
│                         └───────────┘       └───────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 HCNT Module Characteristics

| Parameter | Value | Notes |
|-----------|-------|-------|
| Max Load Capacity | 500g | ZT-HX500 module |
| Nominal Gap | 15mm | Factory default |
| Adjustable Gap Range | 5-25mm | Via control modification |
| Electromagnet Coils | 4× radial | For stability + height |
| Hall Sensors | 4× | Position feedback |
| Power Consumption | 12-18W | Gap-dependent |
| Input Voltage | 24V DC | Standard supply |
| Control Frequency | 20kHz PWM | Smooth current control |

### 1.3 Wireless Power Transfer Subsystem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     RESONANT WPT ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  BASE (TX Side)                          ORB (RX Side)                       │
│  ─────────────                           ──────────────                      │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐      ┌─────────────┐    ┌─────────────┐│
│  │ 24V DC      │--->│ bq500215    │      │ bq51025     │--->│ BQ25895     ││
│  │ Supply      │    │ TX Driver   │      │ RX Ctrl     │    │ Charger     ││
│  └─────────────┘    └──────┬──────┘      └──────┬──────┘    └─────────────┘│
│                            │                    │                           │
│                     ┌──────┴──────┐      ┌──────┴──────┐                    │
│                     │ TX Coil     │ ~~~~ │ RX Coil     │                    │
│                     │ 80mm Litz   │      │ 80mm Litz   │                    │
│                     │ 15 turns    │      │ 20 turns    │                    │
│                     └─────────────┘      └─────────────┘                    │
│                            │                    │                           │
│                     ┌──────┴──────┐      ┌──────┴──────┐                    │
│                     │ Ferrite     │      │ Ferrite     │                    │
│                     │ Shield      │      │ Shield      │                    │
│                     │ 90mm Mn-Zn  │      │ 90mm Mn-Zn  │                    │
│                     └─────────────┘      └─────────────┘                    │
│                                                                              │
│                     ← Air Gap: 5-25mm →                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Dynamic Height Control

### 2.1 How HCNT Maglev Height Control Works

Standard HCNT modules maintain a fixed levitation height (typically 15mm) using a closed-loop feedback system. The key insight is that the **levitation height is determined by the setpoint in the PID controller**, not by hardware limitations.

**Modification approach:**

1. **Intercept the height setpoint** - The HCNT controller has an internal reference voltage corresponding to the target gap
2. **Replace with dynamic setpoint** - Use an external DAC to inject a variable reference
3. **Implement outer control loop** - Higher-level controller manages height transitions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MODIFIED HEIGHT CONTROL                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ESP32-S3 (Base Controller)                                                  │
│  ─────────────────────────                                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────┐                │
│  │                                                          │                │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │                │
│  │  │ Height      │    │ Trajectory  │    │ DAC         │  │                │
│  │  │ Command     │--->│ Generator   │--->│ MCP4725     │──┼──> To HCNT    │
│  │  │ (API/State) │    │ (smoothing) │    │ (12-bit)    │  │    Setpoint   │
│  │  └─────────────┘    └─────────────┘    └─────────────┘  │                │
│  │                                                          │                │
│  │  Commands:                                               │                │
│  │  - set_height(target_mm, duration_ms)                   │                │
│  │  - bobble_animation(amplitude, frequency, duration)     │                │
│  │  - emergency_land()                                     │                │
│  │                                                          │                │
│  └─────────────────────────────────────────────────────────┘                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Height-to-Voltage Mapping

The Hall sensor output is proportional to magnetic field strength, which follows an inverse relationship with distance:

```
Height Setpoint Voltage Curve (calibration required per unit)

Voltage (V)
    │
2.5 ├─────────────────────────────────○ 5mm (closest)
    │                            ○
2.0 ├───────────────────────○
    │                   ○
1.5 ├──────────────○              Default 15mm
    │          ○
1.0 ├──────○
    │   ○
0.5 ├○                                 25mm (farthest)
    │
    └────┬────┬────┬────┬────┬────► Height (mm)
         5   10   15   20   25

Approximate linear mapping (after calibration):
  V_setpoint = V_max - (height_mm - 5mm) × (V_max - V_min) / 20mm

Where:
  V_max = ~2.5V (5mm gap)
  V_min = ~0.5V (25mm gap)
```

### 2.3 Trajectory Generation

Smooth transitions prevent oscillation and instability:

```rust
/// Trajectory generator for height control
pub struct HeightTrajectory {
    start_height: f32,      // mm
    target_height: f32,     // mm
    duration: f32,          // seconds
    elapsed: f32,           // seconds
}

impl HeightTrajectory {
    /// Generates S-curve trajectory (smooth acceleration/deceleration)
    pub fn sample(&self, t: f32) -> f32 {
        if t >= self.duration {
            return self.target_height;
        }

        // Normalized time [0, 1]
        let s = t / self.duration;

        // S-curve: 3s² - 2s³ (smoothstep)
        let blend = s * s * (3.0 - 2.0 * s);

        self.start_height + blend * (self.target_height - self.start_height)
    }
}

/// Bobble animation generator
pub struct BobbleAnimation {
    center_height: f32,     // mm (e.g., 20mm)
    amplitude: f32,         // mm (e.g., 5mm)
    frequency: f32,         // Hz (e.g., 0.5Hz)
    phase: f32,             // radians
}

impl BobbleAnimation {
    pub fn sample(&self, t: f32) -> f32 {
        let omega = 2.0 * PI * self.frequency;
        self.center_height + self.amplitude * (omega * t + self.phase).sin()
    }
}
```

---

## 3. Wireless Power Efficiency vs. Air Gap

### 3.1 Coupling Coefficient Analysis

The coupling coefficient (k) between TX and RX coils determines power transfer efficiency:

```
                     COUPLING COEFFICIENT VS AIR GAP

k (coupling)
    │
0.9 ├●                                   ← Strong coupling (touching)
    │ ●
0.8 ├  ●
    │   ●
0.7 ├    ●   ← Critical coupling region
    │     ●
0.6 ├      ●
    │       ●
0.5 ├        ●●                          ← Moderate coupling
    │          ●●
0.4 ├            ●●
    │              ●●
0.3 ├                ●●●                 ← Weak coupling
    │                   ●●●
0.2 ├                      ●●●●●
    │
0.1 ├
    │
    └────┬────┬────┬────┬────┬────────► Air Gap (mm)
         5   10   15   20   25

For 80mm coils (N_tx=15, N_rx=20, Litz wire):
  - k @ 5mm  ≈ 0.70-0.75
  - k @ 10mm ≈ 0.55-0.60
  - k @ 15mm ≈ 0.40-0.45
  - k @ 20mm ≈ 0.30-0.35
  - k @ 25mm ≈ 0.22-0.27
```

### 3.2 Power Transfer Efficiency

For resonant systems with Series-Series (SS) compensation:

```
η = k² × Q_tx × Q_rx / (1 + k² × Q_tx × Q_rx)

Where:
  k = coupling coefficient
  Q_tx = quality factor of TX coil (~200 for Litz wire)
  Q_rx = quality factor of RX coil (~150 for Litz wire)
```

**Expected efficiency at different heights:**

| Air Gap | k | η (theoretical) | η (practical) | Power @ 20W TX |
|---------|---|-----------------|---------------|----------------|
| 5mm | 0.72 | 99.6% | 88-92% | 17.6-18.4W |
| 10mm | 0.57 | 99.0% | 82-86% | 16.4-17.2W |
| 15mm | 0.42 | 97.3% | 74-78% | 14.8-15.6W |
| 20mm | 0.32 | 93.2% | 65-70% | 13.0-14.0W |
| 25mm | 0.24 | 85.1% | 55-62% | 11.0-12.4W |

### 3.3 Resonant Frequency Tracking

As height changes, optimal resonant frequency shifts due to coupling variation. Use Variable Frequency Control (VFC):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     VARIABLE FREQUENCY TRACKING                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Resonant Frequency vs. Coupling:                                            │
│                                                                              │
│  f_resonant = f_0 × √(1 ± k)                                                │
│                                                                              │
│  Where f_0 = base resonant frequency (140 kHz for this design)              │
│                                                                              │
│  At k=0.7 (5mm):   f = 140 × √(0.3) = 76.7 kHz  OR  182.6 kHz              │
│  At k=0.4 (15mm):  f = 140 × √(0.6) = 108.4 kHz OR  167.3 kHz              │
│  At k=0.25 (25mm): f = 140 × √(0.75) = 121.2 kHz OR 156.8 kHz              │
│                                                                              │
│  Implementation:                                                             │
│  - Use Phase-Locked Loop (PLL) to track zero-crossing phase                │
│  - bq500215 has built-in frequency adjustment capability                    │
│  - Target: maintain phase angle within ±5° of resonance                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Operating Modes

### 4.1 Mode Definitions

```rust
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum LevitationMode {
    /// Normal operation: Orb floats at 20mm for full PTZ range
    Float {
        height_mm: f32,  // 18-22mm
    },

    /// Charging mode: Orb sinks to 5mm for maximum efficiency
    Charging {
        target_height_mm: f32,  // 5-8mm
        charge_rate_w: f32,     // actual power delivered
    },

    /// Animation mode: Orb oscillates for expressive effects
    Bobble {
        center_mm: f32,     // 15-20mm
        amplitude_mm: f32,  // 3-8mm
        frequency_hz: f32,  // 0.3-1.5Hz
    },

    /// Emergency: Controlled descent to base
    Landing {
        current_height_mm: f32,
        descent_rate_mm_s: f32,  // ~10mm/s max
    },

    /// Power failure: Passive soft landing
    EmergencyLanding,

    /// Orb removed from base
    Lifted,
}
```

### 4.2 State Transitions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LEVITATION MODE STATE MACHINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                              ┌─────────────┐                                │
│                              │   LIFTED    │                                │
│                              │ (orb away)  │                                │
│                              └──────┬──────┘                                │
│                                     │ orb_placed()                          │
│                                     ▼                                        │
│            ┌───────────────────────────────────────────┐                    │
│            │                  FLOAT                     │                    │
│            │               (default: 20mm)              │◄─────────────┐    │
│            └───────────────────────────────────────────┘              │    │
│                │              │              │                        │    │
│   charge_request()   bobble_start()   landing_request()    complete() │    │
│                │              │              │                        │    │
│                ▼              ▼              ▼                        │    │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐         │    │
│  │    CHARGING     │ │     BOBBLE      │ │    LANDING      │         │    │
│  │   (sink: 5mm)   │ │  (oscillating)  │ │  (descending)   │         │    │
│  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘         │    │
│           │                   │                   │                   │    │
│   charge_complete()   bobble_stop()       landed()                   │    │
│           │                   │                   │                   │    │
│           └───────────────────┴───────────────────┘                   │    │
│                               │                                       │    │
│                               └───────────────────────────────────────┘    │
│                                                                              │
│  EMERGENCY (any state):                                                      │
│  ─────────────────────                                                       │
│  power_failure() OR safety_violation() → EMERGENCY_LANDING                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Control Algorithms

### 5.1 Outer Loop Height Controller (ESP32-S3)

```rust
use esp_hal::peripherals::{I2C, ADC};
use embassy_time::{Duration, Timer, Instant};

/// Height controller running at 100Hz on ESP32-S3
pub struct HeightController {
    // Hardware
    dac: MCP4725,           // DAC for height setpoint
    adc: AdcChannel,        // Read actual height from Hall sensor

    // State
    current_height: f32,    // mm, from ADC
    target_height: f32,     // mm, commanded
    mode: LevitationMode,

    // Trajectory
    trajectory: Option<HeightTrajectory>,
    bobble: Option<BobbleAnimation>,

    // Safety
    power_good: bool,
    emergency_triggered: bool,

    // Timing
    last_update: Instant,
}

impl HeightController {
    /// Main control loop - call at 100Hz
    pub async fn update(&mut self) -> Result<(), LevitationError> {
        let now = Instant::now();
        let dt = (now - self.last_update).as_secs_f32();
        self.last_update = now;

        // Read current height from ADC (Hall sensor)
        self.current_height = self.read_height_mm().await?;

        // Check safety constraints
        if !self.power_good || self.emergency_triggered {
            return self.emergency_land().await;
        }

        // Compute target based on mode
        let height_setpoint = match &mut self.mode {
            LevitationMode::Float { height_mm } => *height_mm,

            LevitationMode::Charging { target_height_mm, .. } => {
                // Use trajectory if transitioning
                if let Some(ref traj) = self.trajectory {
                    traj.sample(self.trajectory_time())
                } else {
                    *target_height_mm
                }
            }

            LevitationMode::Bobble { center_mm, amplitude_mm, frequency_hz } => {
                if let Some(ref bobble) = self.bobble {
                    bobble.sample(self.animation_time())
                } else {
                    *center_mm
                }
            }

            LevitationMode::Landing { .. } => {
                // Controlled descent at fixed rate
                self.compute_landing_setpoint(dt)
            }

            LevitationMode::EmergencyLanding => {
                // Passive - no active control
                return Ok(());
            }

            LevitationMode::Lifted => {
                // No control needed
                return Ok(());
            }
        };

        // Convert height to DAC voltage and write
        let dac_voltage = self.height_to_voltage(height_setpoint);
        self.dac.set_voltage(dac_voltage).await?;

        // Update WPT frequency tracking based on height
        self.update_wpt_frequency(height_setpoint).await?;

        Ok(())
    }

    /// Command: Transition to charging mode (sink to 5mm)
    pub async fn start_charging(&mut self) -> Result<(), LevitationError> {
        let current = self.current_height;
        let target = 5.0; // mm

        // Create smooth trajectory over 2 seconds
        self.trajectory = Some(HeightTrajectory {
            start_height: current,
            target_height: target,
            duration: 2.0,
            elapsed: 0.0,
        });

        self.mode = LevitationMode::Charging {
            target_height_mm: target,
            charge_rate_w: 0.0, // Will be updated by WPT subsystem
        };

        Ok(())
    }

    /// Command: Return to float mode (rise to 20mm)
    pub async fn stop_charging(&mut self) -> Result<(), LevitationError> {
        let current = self.current_height;
        let target = 20.0; // mm

        self.trajectory = Some(HeightTrajectory {
            start_height: current,
            target_height: target,
            duration: 1.5, // Faster rise than sink
            elapsed: 0.0,
        });

        self.mode = LevitationMode::Float { height_mm: target };

        Ok(())
    }

    /// Command: Start bobble animation
    pub async fn start_bobble(
        &mut self,
        amplitude_mm: f32,
        frequency_hz: f32,
    ) -> Result<(), LevitationError> {
        // Validate parameters
        if amplitude_mm < 1.0 || amplitude_mm > 8.0 {
            return Err(LevitationError::InvalidAmplitude);
        }
        if frequency_hz < 0.1 || frequency_hz > 2.0 {
            return Err(LevitationError::InvalidFrequency);
        }

        let center = self.current_height;

        self.bobble = Some(BobbleAnimation {
            center_height: center,
            amplitude: amplitude_mm,
            frequency: frequency_hz,
            phase: 0.0,
        });

        self.mode = LevitationMode::Bobble {
            center_mm: center,
            amplitude_mm,
            frequency_hz,
        };

        Ok(())
    }

    /// Emergency: Controlled descent
    async fn emergency_land(&mut self) -> Result<(), LevitationError> {
        // Set DAC to minimum (maximum gap = landed)
        self.dac.set_voltage(0.0).await?;
        self.mode = LevitationMode::EmergencyLanding;
        Ok(())
    }

    /// Convert height (mm) to DAC voltage
    fn height_to_voltage(&self, height_mm: f32) -> f32 {
        // Calibration values (measured per unit)
        const V_MIN: f32 = 0.5;   // 25mm
        const V_MAX: f32 = 2.5;   // 5mm
        const H_MIN: f32 = 5.0;   // mm
        const H_MAX: f32 = 25.0;  // mm

        let clamped = height_mm.clamp(H_MIN, H_MAX);
        V_MAX - (clamped - H_MIN) * (V_MAX - V_MIN) / (H_MAX - H_MIN)
    }

    /// Update WPT frequency based on current height
    async fn update_wpt_frequency(&mut self, height_mm: f32) -> Result<(), LevitationError> {
        // Estimate coupling coefficient from height
        let k = self.estimate_coupling(height_mm);

        // Calculate optimal frequency
        let f_base = 140_000.0; // 140 kHz
        let f_optimal = f_base * (1.0 - k).sqrt();

        // Send to WPT controller via I2C or SPI
        // Implementation depends on bq500215 configuration

        Ok(())
    }

    fn estimate_coupling(&self, height_mm: f32) -> f32 {
        // Empirical fit for 80mm coils
        // k ≈ 0.9 × exp(-height / 15)
        0.9 * (-height_mm / 15.0).exp()
    }
}
```

### 5.2 PID Tuning for HCNT Inner Loop

The HCNT module's internal PID controller may need retuning for the extended height range:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PID TUNING GUIDELINES                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Original HCNT Parameters (15mm nominal):                                    │
│    Kp = 2.5                                                                  │
│    Ki = 0.1                                                                  │
│    Kd = 0.8                                                                  │
│                                                                              │
│  Modified for Extended Range (5-25mm):                                       │
│                                                                              │
│  At 5mm (strong coupling, stiff response):                                  │
│    Kp = 1.8   (reduce to prevent overshoot)                                 │
│    Ki = 0.15  (increase for steady-state accuracy)                          │
│    Kd = 0.6   (reduce, less damping needed)                                 │
│                                                                              │
│  At 25mm (weak coupling, soft response):                                    │
│    Kp = 3.5   (increase for faster response)                                │
│    Ki = 0.08  (reduce to prevent integral windup)                           │
│    Kd = 1.2   (increase damping)                                            │
│                                                                              │
│  Approach: Gain Scheduling                                                   │
│  ──────────────────────────                                                  │
│  Interpolate PID gains based on current height:                             │
│                                                                              │
│    Kp(h) = Kp_5mm + (h - 5) × (Kp_25mm - Kp_5mm) / 20                       │
│    Ki(h) = Ki_5mm + (h - 5) × (Ki_25mm - Ki_5mm) / 20                       │
│    Kd(h) = Kd_5mm + (h - 5) × (Kd_25mm - Kd_5mm) / 20                       │
│                                                                              │
│  If HCNT controller doesn't support dynamic PID:                            │
│    - Use conservative middle-ground values                                   │
│    - Rely on outer loop trajectory smoothing                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Coil Specifications

### 6.1 TX Coil (Base)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Diameter (outer) | 80mm | Fits inside base enclosure |
| Diameter (inner) | 30mm | Central hole for mounting |
| Wire | Litz 175/46 AWG | 175 strands of 46 AWG |
| Turns | 15 | Single layer, planar spiral |
| Inductance | ~28 µH | At 140 kHz |
| DC Resistance | ~0.15 Ω | Low for efficiency |
| Quality Factor | ~200 | At 140 kHz |
| Rated Current | 3A RMS | For 20W transfer |
| Ferrite Backing | 90mm × 0.8mm Mn-Zn | Fair-Rite 78 material |

### 6.2 RX Coil (Orb)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Diameter (outer) | 70mm | Constrained by orb interior |
| Diameter (inner) | 25mm | Central hole for battery |
| Wire | Litz 100/46 AWG | 100 strands of 46 AWG |
| Turns | 20 | Dual layer for higher inductance |
| Inductance | ~45 µH | Matched to TX for resonance |
| DC Resistance | ~0.25 Ω | |
| Quality Factor | ~150 | Lower due to space constraints |
| Rated Current | 2A RMS | For 15W delivered |
| Ferrite Backing | 75mm × 0.6mm Mn-Zn | Thinner for weight |

### 6.3 Resonant Capacitors

```
Resonant Frequency: f = 1 / (2π√(LC))

Target: f = 140 kHz

TX Side:
  L_tx = 28 µH
  C_tx = 1 / (4π² × f² × L) = 1 / (4π² × (140×10³)² × 28×10⁻⁶)
       = 46.1 nF
  Use: 47 nF (film capacitor, ±2%, 250V rated)

RX Side:
  L_rx = 45 µH
  C_rx = 1 / (4π² × (140×10³)² × 45×10⁻⁶)
       = 28.7 nF
  Use: 27 nF + 2.2 nF = 29.2 nF (adjustable with trimmer)
```

---

## 7. Safety Mechanisms

### 7.1 Soft Landing on Power Failure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SOFT LANDING MECHANISM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PASSIVE SAFETY FEATURES:                                                    │
│  ────────────────────────                                                    │
│                                                                              │
│  1. Eddy Current Damping                                                    │
│     - Aluminum ring (2mm thick) around permanent magnet in orb              │
│     - When orb descends, ring passes through base's magnetic field          │
│     - Induces eddy currents → braking force opposing descent                │
│     - Effect: Terminal velocity ~5 mm/s instead of free fall               │
│                                                                              │
│     ┌───────────────────────────┐                                           │
│     │   ╭─────────────────╮     │  ← Orb                                   │
│     │   │ ┌─────────────┐ │     │                                          │
│     │   │ │   Magnet    │ │     │                                          │
│     │   │ └─────────────┘ │     │                                          │
│     │   │ ┌─────────────┐ │     │                                          │
│     │   │ │ Aluminum    │ │     │  ← Eddy current ring                     │
│     │   │ │   Ring      │ │     │                                          │
│     │   │ └─────────────┘ │     │                                          │
│     │   ╰─────────────────╯     │                                          │
│     │           │               │                                          │
│     │           ▼ descent       │                                          │
│     │   ┌───────────────────┐   │                                          │
│     │   │     BASE          │   │  ← Electromagnet coils                   │
│     │   └───────────────────┘   │                                          │
│     └───────────────────────────┘                                           │
│                                                                              │
│  2. Silicone Bumper Ring                                                    │
│     - 3mm silicone O-ring on base landing zone                              │
│     - Absorbs remaining impact energy                                       │
│     - Prevents hard metal-to-metal contact                                  │
│                                                                              │
│  3. Orb Bottom Padding                                                      │
│     - TPU-printed landing feet (3 points)                                   │
│     - 5mm travel before rigid contact                                       │
│                                                                              │
│  ANALYSIS:                                                                   │
│  ─────────                                                                   │
│  Orb mass: 400g                                                              │
│  Fall height: 20mm (worst case)                                              │
│  Without damping: v = √(2gh) = √(2 × 9.8 × 0.02) = 0.63 m/s                │
│  With eddy damping: v ≈ 0.005 m/s (terminal velocity)                       │
│  Impact energy: E = ½mv² = ½ × 0.4 × 0.005² = 5 µJ                         │
│                                                                              │
│  Result: Negligible impact, safe landing                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Control Barrier Function for Levitation

```rust
/// Safety verification for levitation system
pub struct LevitationSafetyVerifier {
    // Thresholds
    max_height_mm: f32,           // 30mm (beyond stable range)
    min_height_mm: f32,           // 3mm (collision risk)
    max_descent_rate_mm_s: f32,   // 15mm/s
    max_oscillation_mm: f32,      // 5mm peak-to-peak
    max_coil_temp_c: f32,         // 80°C
}

impl LevitationSafetyVerifier {
    /// Compute barrier function h(x) for levitation state
    /// h(x) > 0 means safe, h(x) <= 0 means violation
    pub fn compute_barrier(&self, state: &LevitationState) -> SafetyResult {
        let h_values = [
            self.h_height_bounds(state),
            self.h_descent_rate(state),
            self.h_oscillation(state),
            self.h_thermal(state),
            self.h_power(state),
        ];

        let h_min = h_values.iter().cloned().fold(f32::MAX, f32::min);

        SafetyResult {
            safe: h_min > 0.0,
            margin: h_min,
            limiting_constraint: self.identify_limiting(h_values),
        }
    }

    fn h_height_bounds(&self, state: &LevitationState) -> f32 {
        let h_upper = (self.max_height_mm - state.height_mm) / 10.0;
        let h_lower = (state.height_mm - self.min_height_mm) / 5.0;
        h_upper.min(h_lower)
    }

    fn h_descent_rate(&self, state: &LevitationState) -> f32 {
        if state.velocity_mm_s < 0.0 {
            // Descending: check against limit
            (self.max_descent_rate_mm_s + state.velocity_mm_s) / self.max_descent_rate_mm_s
        } else {
            // Ascending: always safe in this dimension
            1.0
        }
    }

    fn h_oscillation(&self, state: &LevitationState) -> f32 {
        (self.max_oscillation_mm - state.oscillation_amplitude_mm) / self.max_oscillation_mm
    }

    fn h_thermal(&self, state: &LevitationState) -> f32 {
        (self.max_coil_temp_c - state.electromagnet_temp_c) / (self.max_coil_temp_c - 60.0)
    }

    fn h_power(&self, state: &LevitationState) -> f32 {
        if state.power_supply_ok {
            1.0
        } else {
            -1.0 // Immediate violation
        }
    }
}
```

### 7.3 Safety Interlocks

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SAFETY INTERLOCK MATRIX                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Condition                    │ Action                                       │
│  ────────────────────────────┼──────────────────────────────────────────────│
│  Height > 28mm               │ Emergency land, log event                    │
│  Height < 4mm (not charging) │ Increase setpoint, check Hall sensor         │
│  Descent rate > 15mm/s       │ Reduce setpoint rate, check stability        │
│  Oscillation > 5mm           │ Enter stability recovery mode                │
│  Coil temp > 75°C            │ Reduce current, increase air gap             │
│  Coil temp > 85°C            │ Emergency land, disable until cool           │
│  Power brownout detected     │ Begin controlled descent                     │
│  Power failure               │ Passive soft landing (eddy damping)          │
│  Hall sensor fault           │ Emergency land, disable levitation           │
│  Communication timeout (5s)  │ Enter autonomous safe mode                   │
│  PTZ command while unstable  │ Reject command, stabilize first             │
│  Charging while oscillating  │ Defer charging, dampen oscillation           │
│                                                                              │
│  AUTONOMOUS SAFE MODE:                                                       │
│  ─────────────────────                                                       │
│  - Maintain float at 15mm                                                   │
│  - Disable PTZ                                                              │
│  - Disable bobble animations                                                │
│  - Continue charging if stable                                              │
│  - Wait for communication restore                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Hardware Integration

### 8.1 Base Station Schematic (Simplified)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BASE STATION BLOCK DIAGRAM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         ESP32-S3 (Base Controller)                   │    │
│  │                                                                      │    │
│  │  GPIO_DAC ────> MCP4725 ────> HCNT Height Setpoint                  │    │
│  │  GPIO_ADC <──── Hall Sensor (current height feedback)               │    │
│  │  GPIO_I2C ────> bq500215 (WPT TX control)                           │    │
│  │  GPIO_PWM ────> MOSFET Gate (backup height control)                 │    │
│  │  GPIO_IN  <──── Power Good signal                                   │    │
│  │  GPIO_IN  <──── Temperature sensors (NTC × 2)                       │    │
│  │  GPIO_SPI ────> HD108 LED ring (thinking animation)                 │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐    │
│  │   HCNT ZT-HX500     │  │    Resonant WPT     │  │   Power Supply   │    │
│  │   Maglev Module     │  │    TX Subsystem     │  │                  │    │
│  │                     │  │                     │  │  24V 5A DC       │    │
│  │  - 4× EM coils      │  │  - 80mm TX coil     │  │  (120W total)    │    │
│  │  - 4× Hall sensors  │  │  - bq500215 driver  │  │                  │    │
│  │  - Internal PID     │  │  - 140kHz resonant  │  │                  │    │
│  │  - 24V input        │  │  - 20W max TX       │  │                  │    │
│  │                     │  │  - Ferrite shield   │  │                  │    │
│  └─────────────────────┘  └─────────────────────┘  └──────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Pin Assignments (ESP32-S3)

| GPIO | Function | Direction | Notes |
|------|----------|-----------|-------|
| GPIO1 | I2C SDA | Bidirectional | DAC, WPT, sensors |
| GPIO2 | I2C SCL | Output | 400kHz |
| GPIO3 | ADC Height | Input | Hall sensor feedback |
| GPIO4 | ADC Temp1 | Input | Electromagnet NTC |
| GPIO5 | ADC Temp2 | Input | WPT coil NTC |
| GPIO6 | Power Good | Input | From power supply |
| GPIO7 | PWM Backup | Output | Emergency height control |
| GPIO10 | SPI MOSI | Output | LED data |
| GPIO11 | SPI CLK | Output | LED clock (optional) |
| GPIO15 | Orb Detect | Input | Hall switch for presence |
| GPIO16 | WPT Enable | Output | Master enable for charging |

### 8.3 I2C Bus Devices

| Address | Device | Function |
|---------|--------|----------|
| 0x60 | MCP4725 | DAC for height setpoint |
| 0x68 | bq500215 | WPT TX controller |
| 0x48 | TMP117 | High-precision temperature |
| 0x50 | EEPROM | Calibration data storage |

---

## 9. Calibration Procedure

### 9.1 Height Sensor Calibration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     HEIGHT CALIBRATION PROCEDURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Equipment needed:                                                           │
│  - Calibrated spacers: 5mm, 10mm, 15mm, 20mm, 25mm                          │
│  - Multimeter                                                                │
│  - Serial console to ESP32-S3                                                │
│                                                                              │
│  Procedure:                                                                  │
│                                                                              │
│  1. Place orb on base with power OFF                                        │
│  2. Insert 5mm spacer between orb and base                                  │
│  3. Power on base, record Hall sensor ADC value                             │
│     > cal_point(5mm) = ADC_raw                                              │
│                                                                              │
│  4. Repeat for each spacer height                                           │
│     > cal_point(10mm) = ADC_raw                                             │
│     > cal_point(15mm) = ADC_raw                                             │
│     > cal_point(20mm) = ADC_raw                                             │
│     > cal_point(25mm) = ADC_raw                                             │
│                                                                              │
│  5. Fit polynomial or lookup table:                                         │
│     height_mm = f(ADC_raw)                                                  │
│                                                                              │
│  6. Verify: levitate orb, command each height, measure with ruler           │
│                                                                              │
│  7. Store calibration in EEPROM                                             │
│                                                                              │
│  Typical values (example):                                                   │
│    5mm  → ADC 3800 → DAC 2.5V                                               │
│    10mm → ADC 3200 → DAC 2.0V                                               │
│    15mm → ADC 2600 → DAC 1.5V                                               │
│    20mm → ADC 2000 → DAC 1.0V                                               │
│    25mm → ADC 1400 → DAC 0.5V                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 WPT Efficiency Calibration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     WPT EFFICIENCY CALIBRATION                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  For each height setpoint:                                                   │
│                                                                              │
│  1. Command height (5mm, 10mm, 15mm, 20mm)                                  │
│  2. Enable WPT at 20W TX power                                              │
│  3. Measure RX power delivered to charger                                   │
│  4. Sweep frequency ±20kHz around 140kHz                                    │
│  5. Find peak efficiency point                                              │
│  6. Record: height → optimal_frequency, efficiency                          │
│                                                                              │
│  Expected results:                                                           │
│    Height   Freq (kHz)   η (%)                                              │
│    ─────────────────────────────                                            │
│    5mm      132          89                                                 │
│    10mm     136          84                                                 │
│    15mm     138          76                                                 │
│    20mm     141          68                                                 │
│                                                                              │
│  Store frequency lookup in EEPROM for real-time tracking                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Firmware Structure

### 10.1 Base Station Firmware (ESP32-S3)

```
firmware/base/
├── Cargo.toml
├── src/
│   ├── main.rs              # Entry point, task spawning
│   ├── levitation/
│   │   ├── mod.rs
│   │   ├── controller.rs    # Height controller (outer loop)
│   │   ├── trajectory.rs    # Smooth motion generators
│   │   ├── safety.rs        # CBF verification
│   │   └── calibration.rs   # Height/DAC mapping
│   ├── wpt/
│   │   ├── mod.rs
│   │   ├── driver.rs        # bq500215 control
│   │   ├── frequency.rs     # Adaptive tuning
│   │   └── fod.rs           # Foreign object detection
│   ├── communication/
│   │   ├── mod.rs
│   │   ├── orb_link.rs      # Protocol with orb
│   │   └── api.rs           # WebSocket to hub
│   ├── led/
│   │   ├── mod.rs
│   │   └── patterns.rs      # Thinking, ambient animations
│   └── hal/
│       ├── mod.rs
│       ├── dac.rs           # MCP4725 driver
│       ├── adc.rs           # Hall sensor reading
│       └── i2c.rs           # Bus management
└── tests/
```

### 10.2 Integration with Orb Firmware

The base communicates with the orb via a dedicated protocol:

```rust
/// Messages from Base to Orb
#[derive(Serialize, Deserialize)]
pub enum BaseToOrb {
    /// Current levitation state
    LevitationState {
        height_mm: f32,
        mode: LevitationMode,
        stable: bool,
    },

    /// Charging state
    ChargingState {
        power_w: f32,
        efficiency_pct: u8,
        coil_temp_c: f32,
    },

    /// Safety alert
    SafetyAlert {
        code: SafetyCode,
        margin: f32,
    },
}

/// Messages from Orb to Base
#[derive(Serialize, Deserialize)]
pub enum OrbToBase {
    /// Request height change
    SetHeight {
        target_mm: f32,
        duration_ms: u32,
    },

    /// Request bobble animation
    StartBobble {
        amplitude_mm: f32,
        frequency_hz: f32,
        duration_ms: Option<u32>,
    },

    /// Stop any animation
    StopAnimation,

    /// Request charging mode
    RequestCharge,

    /// Request float mode
    RequestFloat,

    /// Emergency land
    EmergencyLand,
}
```

---

## 11. Performance Specifications

### 11.1 Summary Table

| Parameter | Specification | Notes |
|-----------|---------------|-------|
| **Height Range** | 5-25mm | Adjustable via software |
| **Default Float Height** | 20mm | Full PTZ range |
| **Charging Height** | 5mm | Maximum efficiency |
| **Height Resolution** | 0.1mm | DAC limited |
| **Height Accuracy** | ±0.5mm | After calibration |
| **Transition Speed** | 2-10mm/s | Mode dependent |
| **Bobble Frequency** | 0.1-2.0 Hz | Amplitude dependent |
| **Bobble Amplitude** | 1-8mm | Height dependent |
| **WPT Efficiency @ 5mm** | 88-92% | 17-18W delivered |
| **WPT Efficiency @ 20mm** | 65-70% | 13-14W delivered |
| **Soft Landing Speed** | ~5mm/s | Eddy damping limited |
| **Power Failure Response** | <10ms | Passive mechanism |
| **Control Loop Rate** | 100Hz | ESP32-S3 |
| **HCNT Inner Loop** | 20kHz | Module internal |

### 11.2 Power Budget (Base Station)

| Subsystem | Active (W) | Idle (W) | Notes |
|-----------|------------|----------|-------|
| HCNT Maglev | 12-18 | 10 | Height dependent |
| WPT TX | 20-24 | 0 | Charging only |
| ESP32-S3 | 0.5 | 0.2 | WiFi active |
| LEDs (8× HD108) | 1.6 | 0.1 | Full brightness |
| Sensors/DAC | 0.1 | 0.1 | |
| **Total** | **34-44W** | **10.4W** | |

---

## 12. References

### Research Papers

1. [Magnetic Levitation Wireless Charging Platform with Adjustable Height](https://ieeexplore.ieee.org/document/8574495/) - IEEE Xplore
2. [Variable Frequency Control for Dynamic Wireless Charging](https://www.nature.com/articles/s41598-025-07616-z) - Nature Scientific Reports
3. [PID Controller Design for Magnetic Levitation Systems](https://ieeexplore.ieee.org/document/8986710) - IEEE Xplore
4. [Efficiency Maximization via Dynamic Frequency Tracking](https://www.sciencedirect.com/science/article/pii/S2772671125001767) - ScienceDirect

### Hardware Datasheets

- bq500215: TI Wireless Power TX Controller
- bq51025: TI Wireless Power RX Controller
- MCP4725: Microchip 12-bit DAC
- HCNT ZT-HX500: Maglev Module Specifications

### Software Libraries

- [Embassy-rs](https://github.com/embassy-rs/embassy): Async embedded framework for Rust
- esp-hal: ESP32 hardware abstraction layer

---

```
h(x) >= 0 always

The orb floats. The orb sinks to charge.
The orb bobbles with delight.
The orb lands softly when power fails.

鏡
```
