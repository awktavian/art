# Kagami Orb V3 — Failure Mode and Effects Analysis (FMEA)

## Document Information

| Field | Value |
|-------|-------|
| **Version** | 3.0 |
| **Date** | 2026-01-11 |
| **Status** | Draft |
| **Design Reference** | HARDWARE_BOM.md V3.0 |
| **RPN Target** | All RPNs < 100 before prototype; All RPNs < 50 before production |

---

## Executive Summary

The Kagami Orb V3 represents a significant redesign from V2, introducing multiple novel integration challenges:

- **85mm compact form factor** (29% smaller than V2's 120mm)
- **Camera behind AMOLED display** (novel optical stack)
- **52 TOPS AI compute** in sealed sphere (thermal challenge)
- **Single-source components** (sensiBel, Hailo-10H)
- **Maglev + wireless charging coexistence** (EMI challenge)

This FMEA identifies **47 failure modes** across 4 risk categories, with **8 critical items** (RPN > 100) requiring immediate mitigation before prototyping.

### Risk Summary

| Category | Failure Modes | Critical (RPN>100) | High (RPN 50-100) | Medium (RPN 25-50) | Low (RPN<25) |
|----------|--------------|-------------------|-------------------|-------------------|--------------|
| Critical Integration | 15 | 4 | 6 | 4 | 1 |
| Component Risks | 12 | 2 | 4 | 4 | 2 |
| Design Risks | 12 | 2 | 5 | 3 | 2 |
| Manufacturing Risks | 8 | 0 | 4 | 3 | 1 |
| **TOTAL** | **47** | **8** | **19** | **14** | **6** |

---

## FMEA Scoring Criteria

### Severity (S) — Impact on user/system

| Score | Description | Examples |
|-------|-------------|----------|
| 1 | Negligible | Cosmetic issue, no functional impact |
| 2-3 | Minor | Slight degradation, workaround exists |
| 4-5 | Moderate | Feature degraded, user notices |
| 6-7 | High | Feature fails, device partially functional |
| 8-9 | Very High | Critical function fails, device unusable |
| 10 | Catastrophic | Safety hazard, fire, injury risk |

### Occurrence (O) — Likelihood of occurrence

| Score | Description | Probability |
|-------|-------------|-------------|
| 1 | Remote | <1 in 1,000,000 |
| 2-3 | Low | 1 in 100,000 to 1 in 10,000 |
| 4-5 | Moderate | 1 in 2,000 to 1 in 400 |
| 6-7 | High | 1 in 80 to 1 in 20 |
| 8-9 | Very High | 1 in 8 to 1 in 2 |
| 10 | Certain | >1 in 2, expected on every unit |

### Detection (D) — Ability to detect before harm

| Score | Description | Detection Method |
|-------|-------------|------------------|
| 1 | Almost Certain | Automated 100% test catches it |
| 2-3 | High | Visual inspection or simple test |
| 4-5 | Moderate | Requires specific test procedure |
| 6-7 | Low | Intermittent, hard to reproduce |
| 8-9 | Very Low | Only appears in field use |
| 10 | Undetectable | No known detection method |

### Risk Priority Number (RPN)

```
RPN = Severity × Occurrence × Detection

Thresholds:
  RPN > 100: CRITICAL — Must mitigate before prototype
  RPN 50-100: HIGH — Must mitigate before production
  RPN 25-50: MEDIUM — Monitor and improve
  RPN < 25: LOW — Accept
```

---

## 1. Critical Integration Points

### 1.1 Camera Behind AMOLED Display

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPTICAL STACK CROSS-SECTION                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   LIGHT PATH FROM USER → CAMERA                                  │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ DIELECTRIC MIRROR COATING (70-85% reflective)          │   │
│   └─────────────────────────────────────────────────────────┘   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ OLEOPHOBIC (AF) COATING (anti-fingerprint)             │   │
│   └─────────────────────────────────────────────────────────┘   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ COVER GLASS (0.5-1.0mm)                                │   │
│   └─────────────────────────────────────────────────────────┘   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ ROUND AMOLED 800×800 (3.4" diagonal)                   │   │
│   │   ├── Transparent pupil zone (6-8mm Ø)                 │   │
│   │   └── Active iris/sclera display area                  │   │
│   └─────────────────────────────────────────────────────────┘   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ AIR GAP (0.5-1.0mm)                                    │   │
│   └─────────────────────────────────────────────────────────┘   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ CAMERA MODULE (Sony IMX989 1")                         │   │
│   │   ├── 8P+IR Lens (f/2.0)                               │   │
│   │   └── 26×26×9.4mm module                               │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| CI-01 | **Dielectric mirror blocks too much light** | Camera image dark, poor low-light | 7 | 5 | 4 | **140** | Specify 70% reflectivity max; validate with optical bench; consider 60% for camera zone | 56 |
| CI-02 | **AMOLED transparency insufficient** | Camera cannot see through "off" pixels | 8 | 4 | 5 | **160** | Verify AMOLED part spec includes transparency; test actual panels before committing | 64 |
| CI-03 | Camera-display alignment out of tolerance | Pupil animation doesn't center on camera | 5 | 6 | 3 | 90 | Design alignment jig; use mechanical registration features; 3D print alignment fixture | 45 |
| CI-04 | Light leakage around pupil zone | Visible bright ring around camera hole | 4 | 5 | 2 | 40 | Add black gasket/mask around camera aperture; test light seal | 20 |
| CI-05 | Internal reflections (ghosting) | Secondary images visible in camera | 5 | 4 | 5 | 100 | AR coating on camera lens; validate optical stack with test rig | 50 |
| CI-06 | Dielectric coating delamination | Touch stops working; visual artifacts | 6 | 3 | 4 | 72 | Specify automotive-grade coating; environmental stress test (85°C/85%RH) | 36 |
| CI-07 | Oleophobic coating wears off | Fingerprints visible, touch inconsistent | 3 | 5 | 2 | 30 | Use durable Daikin Optool DSX-E; document reapplication procedure | 15 |

### 1.2 Dielectric Mirror + Capacitive Touch

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| CI-08 | **Dielectric mirror attenuates touch signal** | Touch unresponsive or erratic | 7 | 5 | 4 | **140** | Verify coating thickness < 200nm; test touch sensitivity before/after coating; use mutual capacitance sensing | 56 |
| CI-09 | Touch interference from display refresh | Ghost touches during animation | 5 | 4 | 5 | 100 | Use display sync for touch sampling; implement touch filtering algorithm | 50 |
| CI-10 | Grounding path through mirror coating | ESD damage to touch controller | 6 | 3 | 6 | 108 | Add ESD protection on touch lines; verify coating isolation | 54 |

### 1.3 Maglev + Wireless Charging Coexistence

```
┌─────────────────────────────────────────────────────────────────┐
│                    ELECTROMAGNETIC SYSTEMS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   FREQUENCY SEPARATION:                                          │
│                                                                  │
│   DC ──────────── Maglev (electromagnet control)                │
│   0-1 kHz ─────── Maglev PID loop                               │
│   145 kHz ─────── Wireless charging (resonant)                  │
│   2.4 GHz ─────── Bluetooth 5.4                                 │
│   5-6 GHz ─────── WiFi 6E                                       │
│                                                                  │
│   MAGNETIC FIELD INTERACTION:                                    │
│                                                                  │
│        ORBY                          MAGLEV FIELD                │
│   ┌─────────────┐                    ┌─────────────┐            │
│   │  70mm RX    │  ← 15mm gap →      │  N52 NdFeB  │            │
│   │  COIL       │                    │  MAGNETS    │            │
│   │  (145kHz)   │                    │  + Coils    │            │
│   └─────────────┘                    └─────────────┘            │
│        ↓↓↓                                ↓↓↓                    │
│   [ FERRITE     ]                    [ FERRITE     ]            │
│   [ SHIELD      ]                    [ SHIELD      ]            │
│                                                                  │
│   WITHOUT SHIELDING: Charging flux couples into maglev          │
│   WITH SHIELDING: Flux redirected, <5% coupling                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| CI-11 | **Charging field couples into maglev** | Levitation instability during charging | 7 | 4 | 5 | **140** | Add Mn-Zn ferrite shields (0.8mm) between RX coil and maglev; measure coupling with spectrum analyzer | 56 |
| CI-12 | Maglev magnets saturate ferrite shields | Shield becomes ineffective | 6 | 3 | 6 | 108 | Select 78-material ferrite rated for DC bias; verify with B-H curve test | 54 |
| CI-13 | Resonant frequency drift from temperature | Charging efficiency drops | 4 | 4 | 4 | 64 | Use NPO capacitors (temperature stable); implement frequency tracking | 32 |
| CI-14 | Charging coil overheats (>55°C) | Efficiency degradation; BMS thermal cutoff | 5 | 5 | 3 | 75 | Add thermal path from coil to shell; duty-cycle charging if needed; temperature sensor on coil | 38 |
| CI-15 | N52 magnets demagnetize from heat | Levitation force weakens over time | 8 | 2 | 7 | 112 | Keep magnets < 80°C (N52 Curie ~150°C); thermal simulation required | 56 |

### 1.4 Thermal Management in Sealed 85mm Sphere

```
┌─────────────────────────────────────────────────────────────────┐
│                    V3 THERMAL BUDGET (85mm SPHERE)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   HEAT SOURCES:                                                  │
│                                                                  │
│   Component              Idle    Active    Peak                  │
│   ─────────────────────────────────────────────                  │
│   QCS6490 SoM            2.0W    5.0W      8.0W                  │
│   Hailo-10H              0.5W    2.5W      5.0W                  │
│   AMOLED Display         0.5W    1.0W      2.0W                  │
│   Sony IMX989            0.2W    0.8W      1.5W                  │
│   WiFi 6E/BT             0.3W    1.0W      2.0W                  │
│   XMOS XVF3800           0.1W    0.2W      0.3W                  │
│   HD108 LEDs             0.2W    1.0W      2.0W                  │
│   Charging coil losses   0.0W    3.0W      4.0W                  │
│   Misc (regulators)      0.2W    0.5W      1.0W                  │
│   ─────────────────────────────────────────────                  │
│   TOTAL                  4.0W    15.0W     25.8W                 │
│                                                                  │
│   THERMAL CONSTRAINTS:                                           │
│                                                                  │
│   Surface temperature    < 48°C (safe to touch)                  │
│   Internal air           < 70°C (electronics survival)           │
│   Battery                < 45°C (charging cutoff)                │
│   RX coil                < 55°C (efficiency limit)               │
│   AMOLED                 < 85°C (display limit)                  │
│   QCS6490 junction       < 105°C (throttles at 95°C)             │
│                                                                  │
│   THERMAL PATHS (85mm sphere, ~227 cm² surface):                 │
│                                                                  │
│   Convection (levitation gap): ~4-5 W @ ΔT=20°C                  │
│   Radiation (acrylic shell):   ~3-4 W @ ΔT=20°C                  │
│   Conduction to shell:         ~2-3 W @ ΔT=20°C                  │
│   ─────────────────────────────────────────────                  │
│   TOTAL DISSIPATION CAPACITY:  ~9-12 W                           │
│                                                                  │
│   ⚠️ GAP: Active load (15W) exceeds passive cooling (12W max)   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| CI-16 | **Thermal runaway during sustained use** | Component damage; shutdown; fire risk | 9 | 4 | 4 | **144** | Add thermal throttling at 65°C; duty-cycle AI inference; FEA thermal simulation; consider vent holes | 72 |
| CI-17 | QCS6490 thermal throttling | Slow response; degraded UX | 5 | 6 | 2 | 60 | Copper heatsink with thermal vias; underclocking when idle; dynamic power management | 30 |
| CI-18 | Battery thermal cutoff activates | Charging stops; reduced runtime | 5 | 4 | 3 | 60 | Physical separation from heat sources; thermal insulation; temperature monitoring | 30 |
| CI-19 | AMOLED overheats | Display artifacts; reduced lifespan | 6 | 3 | 4 | 72 | Heat spreader behind display; reduce brightness when hot; display thermal sensor | 36 |
| CI-20 | Hailo-10H thermal shutdown | AI inference disabled | 4 | 4 | 3 | 48 | Thermal pad to common heatsink; workload scheduling; fallback to QCS6490 NPU | 24 |

---

## 2. Component Risks

### 2.1 Sony IMX989 (Camera Sensor)

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| CR-01 | **IMX989 availability/lead time** | Production delays | 7 | 5 | 5 | **175** | Qualify IMX890 as backup; establish relationship with multiple module houses; 6-month buffer stock | 70 |
| CR-02 | Module house quality issues | Inconsistent image quality; DOA units | 6 | 4 | 4 | 96 | Incoming inspection; golden sample comparison; multiple supplier qualification | 48 |
| CR-03 | 1" sensor focus calibration | Out-of-focus images | 5 | 3 | 3 | 45 | Design adjustable focus mechanism; use AF module variant; factory calibration | 22 |

### 2.2 sensiBel SBM100B (Optical MEMS Microphones)

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| CR-04 | **Single-source component unavailable** | No production; complete redesign | 8 | 4 | 7 | **224** | Qualify INMP441 array as fallback; negotiate supply agreement; maintain 12-month inventory | 89 |
| CR-05 | New technology reliability unknown | Field failures; warranty claims | 7 | 4 | 6 | 168 | Extended qualification testing (2000hr HTOL); accelerated life testing; limit initial production run | 84 |
| CR-06 | Optical MEMS sensitivity to particulates | Audio quality degradation | 5 | 3 | 5 | 75 | Sealed acoustic path; mesh filter over port; cleanroom assembly | 38 |

### 2.3 QCS6490 SoM (System on Module)

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| CR-07 | Thundercomm SoM supply disruption | Production halt | 8 | 3 | 5 | 120 | Qualify alternative SoM (Qualcomm RB5, etc.); maintain safety stock | 60 |
| CR-08 | WiFi 6E certification issues | Cannot ship in certain markets | 6 | 3 | 4 | 72 | Early FCC/CE pre-compliance testing; engage certification lab early | 36 |
| CR-09 | Android/Linux BSP quality | Software instability; delayed development | 5 | 4 | 3 | 60 | Request BSP evaluation before committing; parallel development on dev kit | 30 |

### 2.4 Hailo-10H (AI Accelerator)

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| CR-10 | Hailo-10H SDK compatibility issues | Model conversion fails; can't use full performance | 5 | 4 | 4 | 80 | Early SDK evaluation; prototype model pipeline; fallback to QCS6490 NPU | 40 |
| CR-11 | M.2 mechanical stress in sphere | Connector failure from thermal cycling | 4 | 3 | 5 | 60 | Mechanical retention (screw + adhesive); thermal stress testing | 30 |

### 2.5 AMOLED Round Display

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| CR-12 | Round display sourcing instability | Inconsistent supply; quality variance | 6 | 5 | 4 | 120 | Qualify 2-3 suppliers (2.8" IPS); incoming inspection; define acceptance criteria | 60 |
| CR-13 | MIPI DSI timing incompatibility | Display doesn't work with QCS6490 | 5 | 3 | 3 | 45 | Verify MIPI timing specs; prototype early; have backup display option | 22 |

---

## 3. Design Risks

### 3.1 85mm Size Constraint vs Thermal Dissipation

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| DR-01 | **Cannot achieve thermal equilibrium** | Continuous throttling; poor UX | 7 | 5 | 4 | **140** | Commission FEA thermal simulation; design in contingency (vent holes, reduced power mode, larger sphere variant) | 56 |
| DR-02 | Insufficient space for heatsink | Hot spots; uneven temperature | 5 | 4 | 3 | 60 | 3D thermal simulation; optimize component placement; consider vapor chamber | 30 |
| DR-03 | Convection path blocked by components | Reduced cooling efficiency | 4 | 4 | 4 | 64 | Design internal airflow paths; validate with CFD simulation | 32 |

### 3.2 Battery Safety in Enclosed Space

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| DR-04 | **Li-Po thermal runaway** | Fire; explosion; injury | 10 | 2 | 5 | 100 | Quality cells (Sony/Samsung); redundant BMS; thermal fuse; physical separation from heat; UL certification | 40 |
| DR-05 | Battery swelling in sealed enclosure | Shell cracking; component damage | 8 | 3 | 6 | 144 | Design expansion space; pressure relief mechanism; battery SOH monitoring; scheduled replacement | 72 |
| DR-06 | Over-discharge during storage | Dead battery; cell damage | 5 | 4 | 3 | 60 | Ship-mode with <0.5mA drain; storage voltage 3.8V/cell; user activation procedure | 30 |

### 3.3 EMI/EMC from 52 TOPS Compute

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| DR-07 | EMI exceeds FCC Part 15 limits | Cannot sell in USA | 8 | 4 | 4 | **128** | Early pre-compliance testing; proper PCB layout; shielding cans on high-speed ICs | 64 |
| DR-08 | RF interference with WiFi 6E | Poor wireless performance | 5 | 4 | 3 | 60 | Antenna placement optimization; EMI filtering on noisy lines; 6GHz-aware layout | 30 |
| DR-09 | Switching noise affects audio | Audible noise in speaker/mic | 4 | 5 | 3 | 60 | Separate analog/digital grounds; LC filtering on audio power; shielded audio path | 30 |

### 3.4 Wireless Charging Efficiency at 15mm Gap

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| DR-10 | Coupling coefficient < 0.7 | Charging too slow; excessive heat | 5 | 4 | 3 | 60 | Verify coil design with simulation; test multiple coil geometries; consider larger coils | 30 |
| DR-11 | Resonant capacitors drift | Frequency mismatch; efficiency loss | 4 | 3 | 4 | 48 | NPO/C0G capacitors; periodic calibration; frequency tracking algorithm | 24 |
| DR-12 | Misalignment sensitivity | Charging fails if not centered | 4 | 5 | 2 | 40 | Alignment magnets; visual feedback; generous tolerance in coil design | 20 |

---

## 4. Manufacturing Risks

### 4.1 Display-Camera Alignment Tolerance

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| MR-01 | Pupil/camera misalignment > 0.5mm | Visible offset; poor aesthetics | 5 | 5 | 3 | 75 | Custom alignment fixture; ±0.2mm tolerance stack analysis; active alignment with adhesive cure | 38 |
| MR-02 | Camera module Z-height variance | Focus issues; parallax errors | 4 | 4 | 4 | 64 | Incoming inspection with gauge; adjustable mount; shimming procedure | 32 |

### 4.2 Optical Coating Quality Control

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| MR-03 | Dielectric coating non-uniformity | Visible color variation | 4 | 4 | 3 | 48 | Specify coating thickness tolerance (±5%); 100% visual inspection; golden samples | 24 |
| MR-04 | Coating adhesion failure | Delamination in field | 6 | 3 | 5 | 90 | Adhesion testing per ASTM D3359; environmental qualification | 45 |
| MR-05 | Oleophobic coating thickness variance | Inconsistent touch response | 4 | 4 | 4 | 64 | Process control; sample testing; user tolerance for thin spots | 32 |

### 4.3 Maglev Calibration

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| MR-06 | Unit-to-unit levitation height variance | Inconsistent gap; charging issues | 4 | 4 | 3 | 48 | Factory calibration procedure; adjustable base; acceptance test with gauge | 24 |
| MR-07 | Maglev PID tuning varies with orb mass | Instability or oscillation | 5 | 3 | 4 | 60 | Mass tolerance specification; adaptive PID; factory tuning per unit | 30 |

### 4.4 Final Assembly Complexity

| ID | Failure Mode | Effect | S | O | D | RPN | Mitigation | Residual RPN |
|----|--------------|--------|---|---|---|-----|------------|--------------|
| MR-08 | Assembly sequence errors | DOA units; rework cost | 5 | 4 | 3 | 60 | Detailed work instructions; poka-yoke fixtures; in-process checkpoints | 30 |
| MR-09 | Static damage during assembly | Component failure | 6 | 3 | 4 | 72 | ESD controls; wrist straps; conductive workstations; ESD audit | 36 |
| MR-10 | Thermal interface material application | Poor thermal path; hot spots | 5 | 4 | 4 | 80 | Dispensed TIM with volume control; visual inspection of spread pattern | 40 |

---

## 5. Critical Failure Chains

These multi-step failure sequences could lead to serious outcomes:

### Chain 1: Thermal Cascade Failure

```
┌─────────────────────────────────────────────────────────────────┐
│                    THERMAL CASCADE FAILURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   USER RUNS INTENSIVE TASK (vision AI + voice + display)        │
│                          │                                       │
│                          ▼                                       │
│   Compute power peaks at 15-20W                                  │
│                          │                                       │
│                          ▼                                       │
│   Passive cooling capacity exceeded (12W max)                    │
│                          │                                       │
│                          ▼                                       │
│   Internal temperature rises rapidly                             │
│                          │                                       │
│   ┌──────────────────────┼──────────────────────┐               │
│   │                      │                      │               │
│   ▼                      ▼                      ▼               │
│ QCS6490              Battery                 AMOLED             │
│ throttles            triggers                degrades           │
│ (95°C)               cutoff (45°C)           (>85°C)            │
│   │                      │                      │               │
│   ▼                      ▼                      ▼               │
│ Performance          Shutdown               Burn-in/            │
│ drops 50%            imminent              failure              │
│                                                                  │
│   IF NOT MANAGED: Complete system failure                       │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│   MITIGATIONS:                                                   │
│   • Multi-stage thermal throttling (65°C, 75°C, 85°C)           │
│   • Workload scheduling (no simultaneous peak loads)            │
│   • User notification at 60°C                                   │
│   • Graceful degradation (reduce features before shutdown)      │
│   • Design margin: FEA must show <60°C steady state             │
└─────────────────────────────────────────────────────────────────┘
```

### Chain 2: Battery Thermal Event

```
┌─────────────────────────────────────────────────────────────────┐
│                    BATTERY THERMAL EVENT                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   CHARGING WHILE HOT (ambient 30°C + active use)                │
│                          │                                       │
│                          ▼                                       │
│   RX coil losses (3-4W) + compute (10W) = 13-14W heat          │
│                          │                                       │
│                          ▼                                       │
│   Battery temperature approaches 45°C                            │
│                          │                                       │
│   ┌──────────────────────┼──────────────────────┐               │
│   │                      │                      │               │
│   ▼                      ▼                      ▼               │
│ BMS cutoff           Internal               Cell aging          │
│ (expected)           resistance             accelerates         │
│                      rises                                       │
│                          │                                       │
│                          ▼                                       │
│                    IF BMS FAILS:                                 │
│                    Cell overheats                                │
│                          │                                       │
│                          ▼                                       │
│                    Thermal runaway                               │
│                    (FIRE HAZARD)                                 │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│   MITIGATIONS:                                                   │
│   • BMS with redundant thermal cutoff (primary + secondary)     │
│   • PTC resettable fuse in battery pack                         │
│   • Physical thermal barrier between battery and heat sources   │
│   • Suspend charging when internal temp > 40°C                  │
│   • UL 2054 / IEC 62133 battery certification                   │
│   • Thermal fuse directly on cells (one-shot 65°C)              │
└─────────────────────────────────────────────────────────────────┘
```

### Chain 3: Camera-Display Integration Failure

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAMERA INTEGRATION FAILURE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   OPTICAL STACK ASSEMBLED INCORRECTLY                            │
│                          │                                       │
│   ┌──────────────────────┼──────────────────────┐               │
│   │                      │                      │               │
│   ▼                      ▼                      ▼               │
│ Wrong coating       Misalignment          Air gap wrong         │
│ reflectivity        >0.5mm                                       │
│                          │                      │               │
│                          ▼                      ▼               │
│                    Pupil off-center      Internal               │
│                    (cosmetic defect)     reflections            │
│                          │                      │               │
│                          ▼                      ▼               │
│   ▼                 User sees it;        Camera unusable;       │
│ Camera image        returns product      "blind" orb            │
│ too dark                                                         │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│   MITIGATIONS:                                                   │
│   • Optical simulation before tooling commit                    │
│   • Prototype optical stack with each supplier's samples        │
│   • Incoming QC: spectrophotometer for coating reflectivity     │
│   • Assembly fixture with ±0.2mm positioning accuracy           │
│   • 100% camera function test (image quality automated check)   │
│   • Subjective evaluation station for cosmetic defects          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Safety Critical Items

Items requiring verification before any user exposure:

| Priority | ID | Description | Severity | Required Test | Pass Criteria |
|----------|-----|-------------|----------|---------------|---------------|
| **1** | DR-04 | Battery thermal runaway protection | 10 | UL 2054 / IEC 62133 certification | Third-party certification |
| **2** | CI-16 | Thermal runaway prevention | 9 | 2-hour thermal soak @ 30°C ambient | All temps < limits; stable |
| **3** | DR-05 | Battery swelling containment | 8 | Overcharge test; 85°C storage | No shell damage |
| **4** | CI-15 | Magnet demagnetization | 8 | 500-cycle thermal cycle test | Levitation force >95% |
| **5** | DR-07 | EMI compliance | 8 | FCC Part 15B / EN 55032 | Pass with margin |
| **6** | CI-01/02 | Camera optical path | 8 | Image quality validation | SNR > 30dB in 50 lux |

---

## 7. Mitigation Priority Matrix

### Must Implement Before Prototype (RPN > 100)

| ID | Failure Mode | RPN | Primary Mitigation | Owner | Due Date |
|----|--------------|-----|-------------------|-------|----------|
| CR-04 | sensiBel single source | 224 | Qualify INMP441 fallback; establish supply agreement | Procurement | Week 4 |
| CR-01 | IMX989 availability | 175 | Qualify IMX890 backup; buffer stock | Procurement | Week 4 |
| CI-02 | AMOLED transparency | 160 | Test actual panels before design commit | Hardware | Week 2 |
| CI-16 | Thermal runaway | 144 | FEA thermal simulation; design contingency | Thermal | Week 6 |
| DR-05 | Battery swelling | 144 | Expansion space; pressure relief design | Mechanical | Week 6 |
| CI-01 | Mirror blocks light | 140 | Optical bench validation; 60% coating option | Optical | Week 3 |
| CI-08 | Touch attenuation | 140 | Touch sensitivity testing with coating | Touch | Week 3 |
| CI-11 | Charging-maglev coupling | 140 | Ferrite shield design; coupling measurement | EMC | Week 5 |

### Must Implement Before Production (RPN 50-100)

| ID | Failure Mode | RPN | Primary Mitigation |
|----|--------------|-----|--------------------|
| DR-07 | EMI compliance | 128 | Pre-compliance testing; shielding |
| CR-05 | sensiBel reliability | 168 | Extended qualification |
| CR-07 | QCS6490 supply | 120 | Alternative SoM qualification |
| CR-12 | AMOLED sourcing | 120 | Multiple supplier qualification |
| CI-15 | Magnet demagnetization | 112 | Thermal simulation |
| CI-10 | ESD through coating | 108 | ESD protection design |
| CI-12 | Ferrite saturation | 108 | Material selection |
| CI-05 | Internal reflections | 100 | AR coating specification |
| DR-04 | Li-Po thermal runaway | 100 | UL certification |

---

## 8. Recommended Design Changes

### Mandatory Changes (RPN > 100)

1. **Add Thermal Throttling Ladder**
   - 65°C: Reduce CPU to 1.5GHz, disable Hailo background tasks
   - 75°C: Reduce display brightness 50%, disable camera
   - 85°C: Emergency shutdown with voice warning

2. **Dual-Source Microphone Design**
   - Primary: sensiBel SBM100B (4×)
   - Fallback footprint for: INMP441 (4×) on same PCB
   - Software abstraction for either type

3. **Camera Optical Validation Rig**
   - Build before committing to display/coating suppliers
   - Test: coating reflectivity, AMOLED transparency, focus

4. **Ferrite Shield Integration**
   - 0.8mm Mn-Zn ferrite between RX coil and base magnets
   - Verify no DC saturation with gauss meter

5. **Battery Safety System**
   - Primary BMS: BQ40Z50 with thermal cutoff
   - Secondary: PTC resettable fuse (65°C trip)
   - Tertiary: Thermal fuse on cell (one-shot, 70°C)
   - Design expansion void for cell swelling

### Recommended Changes (RPN 50-100)

6. **Thermal Vent Option**
   - Design shell with optional vent holes (pluggable)
   - If FEA shows insufficient cooling, enable vents

7. **EMI Pre-Compliance**
   - Test DVT units in anechoic chamber before certification
   - Budget $5K for early testing

8. **Multi-Supplier Display Qualification**
   - Test 3 AMOLED suppliers
   - Define acceptance spec (brightness, color, transparency)

---

## 9. Test Requirements

### Validation Tests (Before Production)

| Test | Standard | Sample Size | Accept/Reject |
|------|----------|-------------|---------------|
| **Thermal Soak** | Internal | 5 units | All temps < limit for 2 hours |
| **Battery Safety** | UL 2054 | Per UL | Certification pass |
| **EMC Compliance** | FCC Part 15B | 3 units | Pass with 3dB margin |
| **ESD Immunity** | IEC 61000-4-2 | 3 units | Level 4 (8kV contact) |
| **Drop Test** | Internal | 5 units | Survives 1m onto hardwood |
| **Thermal Cycle** | MIL-STD-810 | 5 units | 500 cycles, no degradation |
| **Vibration** | MIL-STD-810 | 3 units | No loose components |
| **Humidity** | 85°C/85%RH | 5 units | 1000 hours, functional |

### Production Tests (100% of Units)

| Test | Method | Pass Criteria |
|------|--------|---------------|
| Power-on self test | Automated | All subsystems respond |
| Camera image quality | Automated | SNR > 30dB, focus pass |
| Display check | Visual + automated | No dead pixels, uniformity |
| Touch calibration | Automated | All zones responsive |
| Audio loopback | Automated | THD < 1%, SNR > 60dB |
| Levitation test | Automated jig | Stable for 60s |
| Wireless charging | Automated | >10W within 30s |
| WiFi/BT | Automated | Connects, RSSI > -50dBm |

---

## 10. Sign-Off

| Review | Date | Reviewer | Status |
|--------|------|----------|--------|
| Initial FMEA (V3) | 2026-01-11 | — | Draft |
| Hardware Review | | | Pending |
| Thermal Validation | | | Pending |
| Safety Review | | | Pending |
| Production Release | | | Pending |

---

## Appendix A: Component Cross-Reference

| Component | Primary | Backup | Single Source Risk |
|-----------|---------|--------|-------------------|
| Camera | Sony IMX989 | Sony IMX890 | LOW |
| Microphone | sensiBel SBM100B | INMP441 (4×) | HIGH → MITIGATED |
| SoM | Thundercomm TurboX C6490 | Qualcomm RB5 | MEDIUM |
| AI Accelerator | Hailo-10H | QCS6490 NPU (reduced) | MEDIUM |
| Display | AliExpress 2.8" Round IPS | Multiple suppliers | LOW |
| Maglev | HCNT module | Goodwell | LOW |
| Wireless RX | Renesas P9415-R | NXP MWPR1516 | LOW |

## Appendix B: Thermal Simulation Requirements

The following FEA thermal simulation is REQUIRED before prototype:

**Inputs:**
- 3D CAD model with all components
- Material properties per Section 1.4
- Heat source powers per thermal budget
- Boundary conditions: 25°C ambient, natural convection

**Required Outputs:**
- Temperature field (steady state and transient)
- Time to thermal equilibrium
- Identification of hot spots
- Recommended mitigations if any limit exceeded

**Budget:** $6,000-8,000
**Timeline:** 3 weeks
**Vendor:** TBD (SimScale, ANSYS consultant, etc.)

---

```
h(x) >= 0. Always.

Every failure mode anticipated.
Every risk assessed.
Every mitigation tested.

The compact mirror must be safe.

鏡
```
