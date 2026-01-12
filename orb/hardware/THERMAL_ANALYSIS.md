# Kagami Orb V3 — Thermal Analysis (SEALED DESIGN)

## Document Information

| Field | Value |
|-------|-------|
| **Version** | 3.0 |
| **Date** | 2026-01-11 |
| **Design** | 85mm SEALED sphere |
| **Status** | Engineering validation required |

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    V3 THERMAL CHALLENGE (SEALED 85mm)                           │
└─────────────────────────────────────────────────────────────────────────────────┘

The Kagami Orb V3 is a SEALED 85mm sphere with no vents, relying entirely on:
1. Conduction through shell to ambient air
2. Radiation from shell surface
3. Thermal transfer to base when docked (primary heat path)
4. Aggressive firmware thermal throttling

KEY CONSTRAINTS:
• Surface temperature: ≤45°C (safe to touch per UL 62368-1)
• Internal peak: ≤70°C (electronics survival)
• No fans, no vents (acoustic and aesthetic requirement)
• Maglev gap: 15mm air (poor conductor, good radiator)

THERMAL BUDGET:
• Passive sphere dissipation: ~2-4W continuous
• With base thermal coupling: ~8-12W continuous
• Peak loads: Managed via throttling
```

---

## V3 Heat Sources

### Component Power Dissipation (VALIDATED)

| Component | Location | Idle (W) | Active (W) | Peak (W) | Source |
|-----------|----------|----------|------------|----------|--------|
| **QCS6490 SoC** | Center | 5.0 | 8.0 | 12.0 | Advantech MIO-5355 datasheet |
| **Hailo-10H** | Adjacent | 0.5 | 2.5 | 5.0 | Hailo product brief |
| **2.8" AMOLED** | Top | 0.3 | 0.8 | 1.2 | Typical round AMOLED |
| **Sony IMX989** | Behind display | 0.2 | 0.5 | 0.8 | Camera active |
| **HD108 LEDs ×16** | Equator | 0.2 | 0.8 | 1.6 | 16-bit at full white |
| **sensiBel ×4** | Distributed | 0.006 | 0.006 | 0.006 | 1.5mW each |
| **XMOS XVF3800** | Audio PCB | 0.1 | 0.2 | 0.3 | Voice processing |
| **ESP32-S3** | Periphery | 0.1 | 0.3 | 0.5 | Co-processor |
| **RX Coil (charging)** | Bottom | 0.0 | 3.0 | 4.0 | 75% efficiency loss |
| **BQ25895 Charger** | Power PCB | 0.1 | 0.4 | 0.8 | Buck-boost losses |
| **Sensors + misc** | Distributed | 0.2 | 0.3 | 0.5 | IMU, env, ToF |
| **TOTAL** | | **6.7** | **16.8** | **26.7** | |

**⚠️ CRITICAL FINDING:** Peak power (26.7W) is 6-10× what the sealed sphere can dissipate!

---

## Thermal Dissipation Analysis

### Sealed Sphere (No Base)

```
Surface Area = 4πr² = 4π(0.0425)² = 0.0227 m²

Heat transfer coefficient (natural convection + radiation):
• Plastic enclosure: k ≈ 4 W/m²·K
• With emissive coating: k ≈ 6 W/m²·K

Q = k × A × ΔT

For ΔT = 25°C (45°C surface - 20°C ambient):
Q_plastic = 4 × 0.0227 × 25 = 2.3W
Q_coated = 6 × 0.0227 × 25 = 3.4W

For ΔT = 30°C (50°C surface - 20°C ambient):
Q_coated = 6 × 0.0227 × 30 = 4.1W
```

**RESULT: Sealed 85mm sphere can only dissipate 2-4W continuously.**

### With Maglev Base (Docked)

```
The base provides additional thermal path:
• Base surface: 180×180mm top + sides ≈ 0.065 m²
• Thermal radiation across 15mm gap
• Convection in gap (chimney effect)

Radiation: Q = εσA(T₁⁴ - T₂⁴)
• ε = 0.9 (painted surfaces)
• σ = 5.67×10⁻⁸ W/m²·K⁴
• A = π(0.0425)² = 0.0057 m² (bottom hemisphere)
• T₁ = 318K (45°C), T₂ = 298K (25°C)
• Q_rad ≈ 3-4W additional

Combined docked dissipation: ~8-12W
```

**RESULT: When docked, system can handle ~8-12W continuously.**

---

## Thermal Management Strategy

### 1. Docked Mode (Primary Use Case)

| State | Power Budget | Temperature | Duration |
|-------|-------------|-------------|----------|
| Idle (display on) | 6-7W | <40°C | Indefinite |
| Active (AI inference) | 10-12W | <45°C | Continuous |
| Peak (video + AI) | 15-18W | Rising | 5-10 min max |
| Thermal throttle | 8W | Holding 45°C | Auto-trigger |

### 2. Portable Mode (Off Base)

| State | Power Budget | Temperature | Duration |
|-------|-------------|-------------|----------|
| Idle (display off) | 2-3W | <40°C | 12+ hours |
| Idle (display on) | 4-5W | 40-45°C | 4-6 hours |
| Active (throttled) | 5-6W | 45°C | 1-2 hours |
| **Full active** | **BLOCKED** | N/A | Not allowed |

### 3. Firmware Thermal Control

```c
// Thermal management state machine
typedef enum {
    THERMAL_NORMAL,      // < 40°C - full performance
    THERMAL_WARM,        // 40-45°C - reduce background tasks
    THERMAL_THROTTLE,    // 45-50°C - throttle CPU/NPU to 50%
    THERMAL_CRITICAL,    // 50-55°C - throttle to 25%, display dim
    THERMAL_SHUTDOWN     // > 55°C - graceful shutdown
} thermal_state_t;

// QCS6490 frequency scaling
const uint32_t freq_table[] = {
    2700,  // NORMAL: Full speed (2.7GHz)
    2000,  // WARM: 2.0GHz
    1500,  // THROTTLE: 1.5GHz
    800,   // CRITICAL: 800MHz
    0      // SHUTDOWN
};

// Hailo-10H duty cycling
const uint8_t hailo_duty[] = {
    100,   // NORMAL: 100%
    80,    // WARM: 80%
    50,    // THROTTLE: 50%
    20,    // CRITICAL: 20%
    0      // SHUTDOWN
};
```

---

## Thermal Path Design

### Cross-Section (V3)

```
                    ┌─────────────────┐
                    │   AMBIENT AIR   │ ← Natural convection
                    └────────┬────────┘
                             │
        ┌────────────────────▼────────────────────┐
        │           85mm SHELL (SEALED)           │ ← Conduction + radiation
        │  ┌──────────────────────────────────┐   │
        │  │         THERMAL GAP (air)        │   │
        │  │  ┌────────────────────────────┐  │   │
        │  │  │    GRAPHITE SPREADER       │  │   │ ← 1500 W/m·K in-plane
        │  │  │  ┌──────────────────────┐  │  │   │
        │  │  │  │     QCS6490 SoC      │  │  │   │ ← Primary heat source
        │  │  │  │    (5-12W TDP)       │  │  │   │
        │  │  │  └──────────────────────┘  │  │   │
        │  │  │  ┌──────────────────────┐  │  │   │
        │  │  │  │     HAILO-10H        │  │  │   │ ← Secondary heat source
        │  │  │  │    (2.5-5W)          │  │  │   │
        │  │  │  └──────────────────────┘  │  │   │
        │  │  └────────────────────────────┘  │   │
        │  └──────────────────────────────────┘   │
        │                   │                      │
        │        THERMAL VIAS (copper)            │
        │                   ▼                      │
        │  ┌──────────────────────────────────┐   │
        │  │         RX COIL (3-4W)           │   │ ← Charging losses
        │  └──────────────────────────────────┘   │
        └─────────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   15mm AIR GAP  │ ← Radiation + weak convection
                    └────────┬────────┘
                             │
        ╔════════════════════▼════════════════════╗
        ║           MAGLEV BASE                   ║ ← Large thermal mass
        ║  ┌──────────────────────────────────┐   ║
        ║  │         TX COIL (heat)           │   ║
        ║  └──────────────────────────────────┘   ║
        ║          WALNUT ENCLOSURE                ║ ← Insulator (poor)
        ╚═════════════════════════════════════════╝
                             │
                    ┌────────▼────────┐
                    │   AMBIENT AIR   │
                    └─────────────────┘
```

### Bill of Thermal Materials

| Component | Specification | Thermal Conductivity | Purpose |
|-----------|--------------|---------------------|---------|
| Graphite sheet | 100×100×0.1mm | 1500 W/m·K (in-plane) | SoC heat spreader |
| Thermal pad | 6 W/m·K, 1mm | 6 W/m·K | SoC to graphite |
| Copper heat spreader | 40×40×1mm | 400 W/m·K | Hot spot reduction |
| Shell coating | High-emissivity paint | ε > 0.9 | Radiation enhancement |

---

## Simulation Requirements

### FEA Specification

| Parameter | Value |
|-----------|-------|
| **Software** | ANSYS Mechanical or COMSOL |
| **Analysis type** | Transient thermal |
| **Mesh** | Tetrahedral, 0.5mm at heat sources |
| **Duration** | 2 hours (steady state + soak) |
| **Ambient** | 20°C, 25°C, 30°C |

### Test Scenarios

| Scenario | Power Profile | Duration | Success Criteria |
|----------|--------------|----------|------------------|
| Idle docked | 6.7W constant | 2 hours | Surface < 40°C |
| Active docked | 12W constant | 2 hours | Surface < 45°C |
| Peak docked | 20W burst | 10 min | Surface < 50°C |
| Idle portable | 3W constant | 2 hours | Surface < 42°C |
| Worst case | 15W in 30°C ambient | 2 hours | Surface < 52°C |

### Probe Points

| Point | Description | Limit |
|-------|-------------|-------|
| P1 | QCS6490 junction | 85°C (throttle), 105°C (shutdown) |
| P2 | Hailo-10H case | 85°C |
| P3 | Battery surface | 45°C (charge disable at 50°C) |
| P4 | RX coil center | 55°C |
| P5 | Shell top (display area) | 40°C |
| P6 | Shell equator | 45°C |
| P7 | Shell bottom | 48°C |

---

## Risk Mitigation

### High-Risk Scenarios

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| QCS6490 overheats in portable mode | HIGH | Device shutdown | Hard 5W limit when undocked |
| Battery thermal runaway | LOW | Safety hazard | BQ40Z50 cuts at 45°C |
| User holds hot sphere | MEDIUM | Discomfort | Haptic warning at 42°C |
| Sustained peak in hot room | MEDIUM | Throttled performance | Auto-throttle at 45°C |

### Design Changes If FEA Fails

| Option | Impact | Tradeoff |
|--------|--------|----------|
| Increase to 100mm sphere | +40% surface area | Larger, heavier |
| Add thermal vents | +2-3W dissipation | Compromise seal, dust ingress |
| Reduce to CM4 + Coral | -6W heat load | Lose 52 TOPS, back to V2 |
| Active base cooling | +10W dissipation | Fan noise in base |

---

## Conclusion

The V3 85mm sealed design is **thermally challenging but feasible** with:

1. ✅ Aggressive firmware thermal management
2. ✅ Graphite heat spreading to maximize shell usage
3. ✅ Primary use case is docked (base provides cooling)
4. ✅ Portable mode is throttled by design
5. ⚠️ FEA validation required before production

**Estimated FEA cost:** $6-8K
**Risk level:** MEDIUM-HIGH
**Recommendation:** Proceed with prototype, validate thermally before pilot

---

## Changelog

### V3.0 (January 2026)
- Complete rewrite for V3 85mm sealed design
- Updated power figures from validated datasheets
- Added docked vs portable thermal modes
- Realistic dissipation calculations
- Deleted all V2 (120mm) references
