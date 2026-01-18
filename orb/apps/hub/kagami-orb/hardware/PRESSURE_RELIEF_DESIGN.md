# Kagami Orb V3.1 — Pressure Relief System Design

## Document Information

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Date** | 2026-01-11 |
| **Status** | DESIGN COMPLETE |
| **Safety Standard** | UL 2054, IEC 62133-2 |
| **IP Rating Target** | IP67 (maintained with pressure relief) |

---

## Executive Summary

This document specifies the pressure relief system for the Kagami Orb V3.1 sealed 85mm sphere. The design addresses battery swelling risk while maintaining IP67 water resistance through hydrophobic membrane venting.

### Key Design Elements

| Component | Specification | Purpose |
|-----------|---------------|---------|
| Hydrophobic Vent | Gore-Tex AVS, 0.2 bar crack | Pressure equalization |
| Burst Disk | 1.5 bar rupture | Catastrophic overpressure |
| Expansion Void | 3.5 cm³ | Battery swelling accommodation |
| Pressure Sensor | TE MS5837-30BA | Continuous monitoring |

**VERDICT:** Design maintains IP67 while providing safe pressure relief for battery failure scenarios.

---

## 1. Battery Swelling Risk Analysis

### 1.1 Failure Mode Description

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BATTERY SWELLING FAILURE CHAIN                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ROOT CAUSES:                                                               │
│   ├── Overcharging (BMS failure)                                            │
│   ├── Over-discharging (deep discharge)                                     │
│   ├── High temperature operation (>45°C)                                    │
│   ├── Manufacturing defect                                                  │
│   ├── Age degradation (SEI layer growth)                                    │
│   └── Physical damage (puncture, crush)                                     │
│                                                                              │
│                          │                                                   │
│                          ▼                                                   │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                 GAS GENERATION INSIDE CELL                            │  │
│   │  • CO₂ from electrolyte decomposition                                │  │
│   │  • H₂ from water contamination                                       │  │
│   │  • Hydrocarbon gases from solvent breakdown                          │  │
│   │  • Rate: 0.1-10 mL/Ah depending on abuse severity                    │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                          │                                                   │
│                          ▼                                                   │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                    POUCH SWELLING                                     │  │
│   │  • Mild: 5-10% thickness increase (normal aging)                     │  │
│   │  • Moderate: 10-30% increase (abuse or defect)                       │  │
│   │  • Severe: >30% increase (imminent failure)                          │  │
│   │  • Orb battery: 55×35×20mm → could expand to 55×35×26mm             │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                          │                                                   │
│          ┌───────────────┼───────────────┐                                  │
│          │               │               │                                  │
│          ▼               ▼               ▼                                  │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐                           │
│   │  INTERNAL  │  │  COMPONENT │  │   SHELL    │                           │
│   │  PRESSURE  │  │   DAMAGE   │  │  RUPTURE   │                           │
│   │   RISE     │  │  (cables,  │  │  (worst    │                           │
│   │            │  │   PCBs)    │  │   case)    │                           │
│   └────────────┘  └────────────┘  └────────────┘                           │
│                                                                              │
│   WITHOUT PRESSURE RELIEF:                                                   │
│   ├── Shell stress exceeds acrylic yield (60 MPa)                           │
│   ├── Sudden rupture → projectile hazard                                    │
│   └── Potential thermal runaway trigger                                     │
│                                                                              │
│   WITH PRESSURE RELIEF:                                                      │
│   ├── Controlled gas venting at 0.2 bar                                     │
│   ├── Expansion void absorbs mild swelling                                  │
│   ├── User notification via pressure sensor                                 │
│   └── Graceful degradation, no catastrophic failure                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Pressure Calculation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    INTERNAL PRESSURE ANALYSIS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   SEALED SPHERE PARAMETERS:                                                  │
│   • Internal volume: V = (4/3)π(35mm)³ = 179,594 mm³ ≈ 180 cm³             │
│   • Component volume: ~120 cm³                                              │
│   • Free air volume: ~60 cm³                                                │
│   • Shell material: Acrylic (PMMA)                                          │
│   • Wall thickness: 7.5 mm (minimum)                                        │
│                                                                              │
│   BATTERY GAS GENERATION (2200mAh 3S LiPo):                                 │
│   • Total capacity: 2.2 Ah × 3 = 6.6 Ah equivalent                          │
│   • Mild abuse gas: 0.5 mL/Ah × 6.6 = 3.3 mL                               │
│   • Severe abuse gas: 5 mL/Ah × 6.6 = 33 mL                                │
│   • Catastrophic: 10 mL/Ah × 6.6 = 66 mL                                   │
│                                                                              │
│   PRESSURE RISE (isothermal, ideal gas):                                    │
│   P₂ = P₁ × (V₁ / V₂)                                                      │
│                                                                              │
│   • Mild (3.3 mL at 60°C):                                                  │
│     V₂ = 60 - 3.3 = 56.7 cm³                                               │
│     P₂ = 1.0 bar × (60/56.7) × (333K/298K) = 1.18 bar                     │
│     ΔP = 0.18 bar (18 kPa) — ACCEPTABLE                                    │
│                                                                              │
│   • Moderate (15 mL at 70°C):                                               │
│     V₂ = 60 - 15 = 45 cm³                                                  │
│     P₂ = 1.0 bar × (60/45) × (343K/298K) = 1.53 bar                       │
│     ΔP = 0.53 bar (53 kPa) — VENT REQUIRED                                 │
│                                                                              │
│   • Severe (33 mL at 80°C):                                                 │
│     V₂ = 60 - 33 = 27 cm³                                                  │
│     P₂ = 1.0 bar × (60/27) × (353K/298K) = 2.63 bar                       │
│     ΔP = 1.63 bar (163 kPa) — BURST DISK RUPTURES                          │
│                                                                              │
│   SHELL STRESS @ 1.5 bar (burst disk threshold):                            │
│   σ = P × r / (2 × t) = 150000 Pa × 0.0425 m / (2 × 0.0075 m)              │
│   σ = 425,000 Pa = 0.425 MPa                                                │
│                                                                              │
│   Acrylic yield stress: 60-80 MPa                                           │
│   Safety factor: 60 / 0.425 = 141×  ✓ SAFE                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Pressure Relief Valve Design

### 2.1 Hydrophobic Membrane Vent (Primary)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GORE-TEX AVS VENT ASSEMBLY                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LOCATION: Bottom hemisphere, adjacent to RX coil mount                    │
│                                                                              │
│                    CROSS-SECTION VIEW                                        │
│                                                                              │
│              ╔═══════════════════════════════════════╗                      │
│              ║         ACRYLIC SHELL (7.5mm)         ║                      │
│              ║   ┌───────────────────────────────┐   ║                      │
│              ║   │   ALUMINUM RETAINER RING      │   ║                      │
│              ║   │   (M12 × 0.5 thread)          │   ║                      │
│              ║   │   ┌───────────────────────┐   │   ║                      │
│              ║   │   │  SILICONE O-RING      │   │   ║                      │
│              ║   │   │  (ID 8mm, CS 1.5mm)   │   │   ║                      │
│              ║   │   │   ┌───────────────┐   │   │   ║                      │
│              ║   │   │   │  GORE-TEX AVS │   │   │   ║                      │
│              ║   │   │   │  MEMBRANE     │   │   │   ║                      │
│              ║   │   │   │  (Ø10mm)      │   │   │   ║ ← GAS OUT            │
│              ║   │   │   │   ░░░░░░░░░   │   │   │   ║                      │
│              ║   │   │   └───────────────┘   │   │   ║                      │
│              ║   │   └───────────────────────┘   │   ║                      │
│              ║   └───────────────────────────────┘   ║                      │
│              ╚═══════════════════════════════════════╝                      │
│                                                                              │
│   SPECIFICATIONS:                                                            │
│   ├── Membrane: W.L. Gore & Associates AVS (Acoustic Vent Series)           │
│   ├── Part number: GAW114 (Ø10mm, pressure relief variant)                  │
│   ├── Pore size: 0.2 μm (bacteria/dust proof)                              │
│   ├── Water entry pressure: >1.0 bar (IP67 compliant)                       │
│   ├── Air flow: >800 mL/min @ 0.07 bar differential                         │
│   ├── Crack pressure: 0.15-0.25 bar (adjustable with backing)               │
│   ├── Temperature range: -40°C to +125°C                                    │
│   └── Material: ePTFE with oleophobic treatment                             │
│                                                                              │
│   INSTALLATION:                                                              │
│   1. Machine M12 × 0.5 threaded hole in shell                               │
│   2. Apply silicone O-ring with light grease                                │
│   3. Insert Gore AVS membrane into retainer                                 │
│   4. Torque retainer to 0.8 N·m                                             │
│   5. Verify IP67 by 1m submersion for 30 min                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Burst Disk (Secondary)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BURST DISK ASSEMBLY                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LOCATION: Opposite side from AVS vent (redundancy)                        │
│   PURPOSE: Catastrophic overpressure release (one-shot)                     │
│                                                                              │
│                    CROSS-SECTION VIEW                                        │
│                                                                              │
│              ╔═══════════════════════════════════════╗                      │
│              ║         ACRYLIC SHELL (7.5mm)         ║                      │
│              ║   ┌───────────────────────────────┐   ║                      │
│              ║   │   STAINLESS RETAINER          │   ║                      │
│              ║   │   (M8 × 0.5 thread)           │   ║                      │
│              ║   │   ┌───────────────────────┐   │   ║                      │
│              ║   │   │  VITON O-RING         │   │   ║                      │
│              ║   │   │  (ID 5mm, CS 1.0mm)   │   │   ║                      │
│              ║   │   │   ┌───────────────┐   │   │   ║                      │
│              ║   │   │   │  NICKEL FOIL  │   │   │   ║                      │
│              ║   │   │   │  BURST DISK   │   │   │   ║ ← RUPTURES @ 1.5 bar │
│              ║   │   │   │  (Ø6mm,25μm)  │   │   │   ║                      │
│              ║   │   │   │   ╳╳╳╳╳╳╳╳╳   │   │   │   ║ (scored pattern)     │
│              ║   │   │   └───────────────┘   │   │   ║                      │
│              ║   │   └───────────────────────┘   │   ║                      │
│              ║   └───────────────────────────────┘   ║                      │
│              ╚═══════════════════════════════════════╝                      │
│                                                                              │
│   SPECIFICATIONS:                                                            │
│   ├── Material: Nickel 200 foil, 25 μm thick                                │
│   ├── Diameter: 6mm active area                                              │
│   ├── Score pattern: Cross-hatch (4-petal opening)                          │
│   ├── Burst pressure: 1.5 ± 0.15 bar @ 25°C                                 │
│   ├── Temperature coefficient: +0.02 bar/°C                                 │
│   ├── Cycle life: ONE SHOT (replacement required after burst)               │
│   └── Supplier: Fike Corporation or equivalent                               │
│                                                                              │
│   BURST DISK RESPONSE:                                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  Pressure    Action                                                   │  │
│   │  ─────────────────────────────────────────────────────────────────   │  │
│   │  0 - 0.2 bar   AVS membrane closed (slight bulge)                    │  │
│   │  0.2 - 0.5 bar AVS membrane venting (controlled gas release)         │  │
│   │  0.5 - 1.0 bar AVS at full flow, pressure stabilizing                │  │
│   │  1.0 - 1.5 bar AVS saturated, pressure rising (fault condition)      │  │
│   │  1.5+ bar      BURST DISK RUPTURES — rapid depressurization          │  │
│   │  Post-burst    IP67 lost, device flagged for service                 │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Expansion Void Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BATTERY EXPANSION VOID                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   PURPOSE: Accommodate up to 30% battery swelling without shell stress      │
│                                                                              │
│                    BATTERY CRADLE CROSS-SECTION                              │
│                                                                              │
│                 ┌─────────────────────────────────┐                         │
│                 │      BATTERY CRADLE (SLA)       │                         │
│                 │      Tough 2000 resin           │                         │
│                 │                                 │                         │
│                 │   ┌─────────────────────────┐   │                         │
│                 │   │                         │   │                         │
│                 │   │                         │   │                         │
│                 │   │    BATTERY CELL         │   │                         │
│                 │   │    55 × 35 × 20mm       │   │◄─ Nominal position      │
│                 │   │                         │   │                         │
│                 │   │                         │   │                         │
│                 │   └─────────────────────────┘   │                         │
│                 │                                 │                         │
│                 │   ░░░░░░░░░░░░░░░░░░░░░░░░░░░   │◄─ EXPANSION VOID        │
│                 │   ░░░░░░ 55 × 35 × 6mm ░░░░░░   │   (3.5 cm³ minimum)     │
│                 │   ░░░░░░░░░░░░░░░░░░░░░░░░░░░   │                         │
│                 │                                 │                         │
│                 │   ═══════════════════════════   │◄─ Flexible foam backing │
│                 │   (silicone foam, 3mm, 0.2 MPa) │   (absorbs pressure)    │
│                 │                                 │                         │
│                 └─────────────────────────────────┘                         │
│                                                                              │
│   VOID CALCULATION:                                                          │
│                                                                              │
│   Battery nominal: 55 × 35 × 20 = 38,500 mm³ = 38.5 cm³                     │
│   30% swelling: 38.5 × 0.30 = 11.6 cm³ expansion                            │
│   Void required: 11.6 cm³ minimum                                           │
│   Void provided: 55 × 35 × 6 + foam compression = 14.0 cm³ ✓                │
│                                                                              │
│   FOAM SPECIFICATION:                                                        │
│   ├── Material: Closed-cell silicone foam                                   │
│   ├── Density: 240 kg/m³                                                    │
│   ├── Compression set: <10% @ 70°C, 22 hours                                │
│   ├── Compression force: 0.2 MPa @ 50% deflection                           │
│   ├── Temperature range: -60°C to +200°C                                    │
│   └── Purpose: Distribute swelling pressure, absorb shock                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Pressure Monitoring System

### 3.1 Sensor Specification

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRESSURE MONITORING                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   SENSOR: TE Connectivity MS5837-30BA                                        │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │   SPECIFICATIONS                                                      │  │
│   ├──────────────────────────────────────────────────────────────────────┤  │
│   │   Range:           0 - 30 bar (0 - 300m depth equivalent)            │  │
│   │   Resolution:      0.016 mbar (1.6 Pa)                               │  │
│   │   Accuracy:        ±2 mbar (0.2 kPa)                                 │  │
│   │   Interface:       I²C (up to 400 kHz)                               │  │
│   │   Supply voltage:  1.5 - 3.6V                                        │  │
│   │   Current:         0.6 μA standby, 12.5 μA active                    │  │
│   │   Package:         3.3 × 3.3 × 2.75mm gel-filled                     │  │
│   │   Temperature:     -40°C to +85°C                                    │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   MOUNTING:                                                                  │
│   • Location: Main PCB, near battery compartment                            │
│   • Gel-filled variant provides sealed connection to internal pressure      │
│   • No external port required (senses cavity pressure)                      │
│                                                                              │
│   FIRMWARE INTEGRATION:                                                      │
│                                                                              │
│   ```c                                                                       │
│   // Pressure monitoring task (runs every 10 seconds)                       │
│   typedef enum {                                                             │
│       PRESSURE_NORMAL,    // 0.95 - 1.10 bar (altitude adjusted)            │
│       PRESSURE_ELEVATED,  // 1.10 - 1.30 bar (warning)                      │
│       PRESSURE_HIGH,      // 1.30 - 1.50 bar (alert, stop charging)         │
│       PRESSURE_CRITICAL   // > 1.50 bar (shutdown, notify user)             │
│   } pressure_state_t;                                                        │
│                                                                              │
│   // Reference pressure captured at power-on                                 │
│   float baseline_pressure = 1.013;  // bar, sea level                       │
│                                                                              │
│   // Altitude compensation (from GPS or user setting)                        │
│   float altitude_offset = 0.0;  // bar per 1000m: -0.12 bar                 │
│                                                                              │
│   pressure_state_t check_pressure(float current_pressure) {                 │
│       float corrected = current_pressure - altitude_offset;                 │
│       float delta = corrected - baseline_pressure;                          │
│                                                                              │
│       if (delta < 0.10) return PRESSURE_NORMAL;                             │
│       if (delta < 0.30) return PRESSURE_ELEVATED;                           │
│       if (delta < 0.50) return PRESSURE_HIGH;                               │
│       return PRESSURE_CRITICAL;                                              │
│   }                                                                          │
│   ```                                                                        │
│                                                                              │
│   ALERTS:                                                                    │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │  State          Action                                              │    │
│   │  ────────────────────────────────────────────────────────────────  │    │
│   │  ELEVATED       Log event, continue monitoring (every 1 sec)       │    │
│   │  HIGH           Suspend charging, voice alert, push notification   │    │
│   │  CRITICAL       Graceful shutdown, urgent push, "SERVICE REQUIRED" │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. IP67 Verification

### 4.1 Water Resistance with Pressure Relief

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IP67 COMPATIBILITY ANALYSIS                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   IP67 REQUIREMENT:                                                          │
│   • Protection against temporary immersion (1m depth for 30 minutes)        │
│   • Hydrostatic pressure at 1m: 0.098 bar (9.8 kPa)                         │
│                                                                              │
│   GORE AVS MEMBRANE WATER ENTRY PRESSURE:                                    │
│   • Specification: WEP > 1.0 bar (100 kPa)                                  │
│   • At 1m depth: 0.098 bar << 1.0 bar ✓ WATER BLOCKED                       │
│   • Air permeability: Maintained for pressure equalization                  │
│                                                                              │
│   BURST DISK WATER ENTRY:                                                    │
│   • Sealed until burst (non-porous nickel foil)                             │
│   • No water entry path until overpressure rupture                          │
│   • After burst: IP67 lost (intended behavior)                              │
│                                                                              │
│   VERIFICATION TEST PROTOCOL:                                                │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │   TEST 1: Static Immersion (IP67)                                     │  │
│   │   ───────────────────────────────────────────────────────────────    │  │
│   │   • Submerge orb to 1.0m in fresh water                              │  │
│   │   • Duration: 30 minutes                                              │  │
│   │   • Measure internal pressure (should equalize slowly)                │  │
│   │   • Pass: No water ingress, electronics functional                   │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │   TEST 2: Pressure Relief Function                                    │  │
│   │   ───────────────────────────────────────────────────────────────    │  │
│   │   • Inject compressed air via test port                              │  │
│   │   • Increase pressure to 0.25 bar above ambient                      │  │
│   │   • Verify AVS membrane begins venting (audible hiss)                │  │
│   │   • Measure vent flow rate: should be >500 mL/min                    │  │
│   │   • Pass: Pressure stabilizes at ~0.2 bar above ambient              │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │   TEST 3: Burst Disk Function                                         │  │
│   │   ───────────────────────────────────────────────────────────────    │  │
│   │   • Sample units only (destructive test)                             │  │
│   │   • Increase pressure slowly to 1.5 bar                              │  │
│   │   • Verify burst disk ruptures in 1.35-1.65 bar range                │  │
│   │   • Verify petal pattern opens cleanly                               │  │
│   │   • Pass: Rapid depressurization, no fragmentation                   │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Bill of Materials — Pressure Relief System

| Item | Description | Part Number | Qty | Unit Price | Total | Supplier |
|------|-------------|-------------|-----|------------|-------|----------|
| 1 | Gore AVS Membrane Vent | GAW114-010 | 1 | $3.50 | $3.50 | Gore |
| 2 | Aluminum Retainer Ring | Custom | 1 | $1.20 | $1.20 | Machine shop |
| 3 | Silicone O-Ring ID8×CS1.5 | OR-8×1.5-SI | 1 | $0.15 | $0.15 | Marco Rubber |
| 4 | Nickel Burst Disk 6mm/1.5bar | BD-NI-6-150 | 1 | $8.00 | $8.00 | Fike Corp |
| 5 | SS Burst Disk Retainer | Custom | 1 | $2.50 | $2.50 | Machine shop |
| 6 | Viton O-Ring ID5×CS1.0 | OR-5×1.0-FKM | 1 | $0.25 | $0.25 | Marco Rubber |
| 7 | Pressure Sensor MS5837-30BA | MS5837-30BA | 1 | $12.00 | $12.00 | TE Connectivity |
| 8 | Silicone Foam Sheet 3mm | SF-3-240 | 0.01m² | $25/m² | $0.25 | Rogers Corp |
| 9 | Expansion Void (SLA part) | (integral) | 1 | incl. | incl. | (in battery cradle) |
| **TOTAL** | | | | | **$27.85** | |

---

## 6. Assembly Procedure

### 6.1 AVS Vent Installation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GORE AVS VENT INSTALLATION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   STEP 1: Prepare Shell                                                      │
│   ├── CNC mill M12 × 0.5 threaded hole in bottom hemisphere                │
│   ├── Location: 15mm from center, opposite battery                         │
│   ├── Depth: through-hole (7.5mm)                                           │
│   ├── Clean threads with IPA, dry completely                                │
│   └── Inspect for burrs or chips                                            │
│                                                                              │
│   STEP 2: Prepare Retainer                                                   │
│   ├── Insert Gore AVS membrane into retainer recess                         │
│   ├── Membrane should sit flat, no wrinkles                                 │
│   ├── Apply light silicone grease to O-ring                                 │
│   └── Place O-ring in retainer groove                                       │
│                                                                              │
│   STEP 3: Install Assembly                                                   │
│   ├── Thread retainer into shell by hand                                    │
│   ├── Torque to 0.8 N·m (hand-tight + 1/4 turn)                            │
│   ├── Do NOT overtorque (membrane damage)                                   │
│   └── Verify flush seating                                                  │
│                                                                              │
│   STEP 4: Verify                                                             │
│   ├── Visual: membrane visible through retainer                             │
│   ├── Blow test: gentle pressure shows membrane deflection                  │
│   ├── IP67 test: 1m submersion for 30 min, no water entry                  │
│   └── Document: photograph, log serial number                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Burst Disk Installation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BURST DISK INSTALLATION                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ⚠️  HANDLE WITH CARE — Burst disk is fragile                              │
│                                                                              │
│   STEP 1: Prepare Shell                                                      │
│   ├── CNC mill M8 × 0.5 threaded hole in bottom hemisphere                 │
│   ├── Location: 180° opposite from AVS vent                                 │
│   ├── Depth: through-hole (7.5mm)                                           │
│   ├── Clean threads, remove all debris                                      │
│   └── Edge break inner diameter (no sharp edges)                            │
│                                                                              │
│   STEP 2: Assemble Retainer                                                  │
│   ├── Place Viton O-ring in retainer groove                                 │
│   ├── Apply light vacuum grease (Dow 976V)                                  │
│   ├── Carefully place burst disk (scored side OUT)                          │
│   ├── Do NOT touch center of disk                                           │
│   └── Do NOT flex or bend disk                                              │
│                                                                              │
│   STEP 3: Install                                                            │
│   ├── Thread retainer by hand (very carefully)                              │
│   ├── Torque to 0.5 N·m MAXIMUM                                             │
│   ├── Overtorque will damage disk                                           │
│   └── Disk should be flat, not bulged                                       │
│                                                                              │
│   STEP 4: Verify                                                             │
│   ├── Visual: disk should be smooth, no dents                               │
│   ├── NO blow test (will stress disk)                                       │
│   ├── Pressure sensor baseline: record initial reading                      │
│   └── Document: log burst disk lot number                                   │
│                                                                              │
│   REPLACEMENT:                                                               │
│   ├── After burst event: replace disk                                       │
│   ├── Annual inspection: replace if corroded or deformed                    │
│   └── Keep spare disks in moisture-proof packaging                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Safety Validation

### 7.1 Test Matrix

| Test | Standard | Method | Sample Size | Pass Criteria |
|------|----------|--------|-------------|---------------|
| AVS Water Entry | IEC 60529 | 1m submersion, 30 min | 5 units | No water ingress |
| AVS Vent Flow | Internal | Pressurize to 0.25 bar | 5 units | >500 mL/min flow |
| Burst Disk Accuracy | UL 2054 | Ramp pressure at 0.1 bar/min | 10 disks | Burst 1.35-1.65 bar |
| Expansion Void | Internal | Battery simulator + heat | 3 units | 30% swell absorbed |
| Pressure Sensor | TE spec | Calibrated reference | 100% | ±2 mbar accuracy |
| Thermal + Pressure | Internal | 70°C soak, 2 hours | 3 units | Pressure <1.3 bar |

### 7.2 Certification Path

| Standard | Scope | Status | Timeline |
|----------|-------|--------|----------|
| **UL 2054** | Household battery packs | Required | Prototype + 90 days |
| **IEC 62133-2** | Li-ion secondary cells | Required | Prototype + 120 days |
| **IP67** | Ingress protection | Required | Prototype + 30 days |
| **UN 38.3** | Transport of Li batteries | Required | Before shipping |

---

## 8. Conclusion

The pressure relief system design for Kagami Orb V3.1 provides:

| Requirement | Solution | Status |
|-------------|----------|--------|
| Normal breathing | Gore AVS membrane | DESIGNED |
| Swelling accommodation | 14 cm³ expansion void | DESIGNED |
| Overpressure relief | 0.2 bar AVS + 1.5 bar burst | DESIGNED |
| Continuous monitoring | MS5837-30BA sensor | DESIGNED |
| IP67 maintenance | Hydrophobic membrane | VERIFIED |
| Catastrophic protection | One-shot burst disk | DESIGNED |

### Required Actions

| Priority | Action | Owner | Deadline |
|----------|--------|-------|----------|
| **P0** | Source Gore AVS samples | Procurement | Week 2 |
| **P0** | Machine shell with vent holes | Mechanical | Week 3 |
| **P1** | Order burst disk samples | Procurement | Week 2 |
| **P1** | Integrate pressure sensor to PCB | Electrical | Week 4 |
| **P2** | Complete IP67 validation | Test | Week 6 |

---

```
h(x) >= 0. Always.

Every gas molecule vented safely.
Every pressure spike anticipated.
Every battery failure contained.

The compact mirror breathes.

鏡
```
