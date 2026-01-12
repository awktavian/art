# Kagami Orb V3.1 — Thermal Improvement Strategy

**Status:** PROPOSED
**Date:** January 2026
**Constraint:** Maintain full waterproofing (sealed sphere)

---

## Executive Summary

The current thermal design dissipates **8-12W docked** vs active load of **13.8W**. This document proposes improvements achieving **15-16W continuous** while maintaining full IP67 waterproofing.

**Key Insight:** All improvements are INTERNAL or SURFACE treatments — no vents, no holes.

---

## Current Thermal Budget

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CURRENT THERMAL PATHS                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Heat Source: QCS6490 + Hailo-10H = 10-13W active                              │
│                                                                                  │
│   Path 1: Conduction → Graphite → Shell → Convection → Air                      │
│           Bottleneck: Acrylic shell (k=0.2 W/m·K)                               │
│           Capacity: ~3-4W                                                        │
│                                                                                  │
│   Path 2: Radiation across 15mm air gap to base                                 │
│           Bottleneck: Distance (15mm), view factor                              │
│           Capacity: ~4-6W                                                        │
│                                                                                  │
│   TOTAL DOCKED: 8-12W (insufficient for 13.8W active)                           │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Proposed Improvements

### TIER 1: Implement for V3.1 (Low Risk, High Impact)

#### 1.1 Vapor Chamber Heat Spreader

Replace thermal pad under QCS6490 with vapor chamber:

```
┌─────────────────────────────────────────────────────────────────┐
│                    VAPOR CHAMBER DESIGN                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   BEFORE (Thermal Pad):                                          │
│   ┌─────────────┐                                                │
│   │   QCS6490   │  Hot spot: 85°C                               │
│   ├─────────────┤                                                │
│   │ Thermal Pad │  k = 6 W/m·K                                  │
│   ├─────────────┤                                                │
│   │  Graphite   │  Spreading limited                            │
│   └─────────────┘                                                │
│                                                                  │
│   AFTER (Vapor Chamber):                                         │
│   ┌─────────────┐                                                │
│   │   QCS6490   │  Hot spot: 65°C (-20°C!)                      │
│   ├─────────────┤                                                │
│   │   Vapor     │  k_eff = 10,000+ W/m·K                        │
│   │   Chamber   │  40×40×2mm (matches SoC)                      │
│   │  ╭━━━━━━╮   │  Working fluid: water                         │
│   │  ┃~~~~~~┃   │  Completely sealed                            │
│   │  ╰━━━━━━╯   │                                                │
│   ├─────────────┤                                                │
│   │  Graphite   │  Now receives uniform heat                    │
│   └─────────────┘                                                │
│                                                                  │
│   Impact: Reduces ΔT_internal by 50%                            │
│   Net gain: +1.5-2W effective dissipation                       │
│   Cost: $15-20                                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Size: 40×40×2mm (fits under QCS6490 SoM)
- Type: Copper-water vapor chamber
- Thermal conductivity: 10,000-50,000 W/m·K (effective)
- Weight: ~8g
- Supplier: Wakefield-Vette, Laird, or AVC

#### 1.2 Phase Change Material (PCM) Buffer

Add paraffin-based PCM to absorb thermal transients:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PCM THERMAL BUFFER                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Material: Paraffin wax (microencapsulated)                     │
│   Melting point: 42°C (tuned to throttle threshold)             │
│   Latent heat: 200 kJ/kg                                         │
│   Mass: 50g                                                      │
│                                                                  │
│   Energy buffer: 50g × 200 kJ/kg = 10,000 J                     │
│                                                                  │
│   Peak absorption capacity:                                      │
│   - Extra 10W for 1,000 seconds (16.7 minutes)                  │
│   - Extra 15W for 667 seconds (11 minutes)                      │
│   - Extra 20W for 500 seconds (8.3 minutes)                     │
│                                                                  │
│   Location: Wrapped around battery cradle (thermal coupling)     │
│                                                                  │
│   Form factor:                                                   │
│   ┌───────────────────────────────────────┐                     │
│   │     ╭────────────────────────╮        │                     │
│   │     │   PCM Sleeve (50g)     │        │                     │
│   │     │   ┌──────────────┐     │        │                     │
│   │     │   │   Battery    │     │        │                     │
│   │     │   │   2200mAh    │     │        │                     │
│   │     │   └──────────────┘     │        │                     │
│   │     ╰────────────────────────╯        │                     │
│   └───────────────────────────────────────┘                     │
│                                                                  │
│   Impact: Extends peak operation from 5 min to 15-20 min        │
│   Cost: $3-5                                                     │
│   Weight: 50g (budget impact: 391g → 441g)                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Product options:**
- Microtek MPCM (microencapsulated paraffin)
- Rubitherm RT42 (bulk paraffin)
- Custom blend from IGI Wax

#### 1.3 Dynamic Levitation Height (Software)

Adjust levitation height based on thermal state:

```
┌─────────────────────────────────────────────────────────────────┐
│                DYNAMIC THERMAL LEVITATION                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   THERMAL STATE    │  LEVITATION HEIGHT  │  RADIATION GAIN      │
│   ─────────────────┼────────────────────┼─────────────────      │
│   NORMAL (<40°C)   │  15mm (default)    │  Baseline             │
│   WARM (40-45°C)   │  12mm              │  +56% (1/d²)          │
│   THROTTLE (>45°C) │  8mm               │  +252% (1/d²)         │
│   CRITICAL (>50°C) │  5mm (minimum)     │  +800% (theoretical)  │
│                                                                  │
│   Radiation equation:                                            │
│   Q_rad ∝ σ·ε·A·(T₁⁴-T₂⁴) / (1 + (d/r)²)                       │
│                                                                  │
│   At 15mm gap: ~4W radiation to base                            │
│   At 8mm gap:  ~7W radiation to base (+75% real-world)          │
│   At 5mm gap:  ~9W radiation to base (+125% real-world)         │
│                                                                  │
│   Safety constraint: h(x) ≥ 0 requires min 5mm                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Firmware implementation:**

```rust
/// Dynamic thermal levitation control
fn thermal_levitation_height(temp: f32) -> f32 {
    match temp {
        t if t < 40.0 => 15.0,  // Normal: 15mm float
        t if t < 45.0 => 15.0 - (t - 40.0) * 0.6,  // Linear ramp: 15mm → 12mm
        t if t < 50.0 => 12.0 - (t - 45.0) * 0.8,  // Aggressive: 12mm → 8mm
        _ => 5.0,  // Critical: minimum safe height
    }
}

/// Safety barrier for levitation
fn h_levitation(height: f32) -> f32 {
    (height - 5.0) / 10.0  // h(x) = 0 at 5mm, h(x) = 1 at 15mm
}
```

**Impact:** +2-3W effective dissipation at no cost
**Risk:** None — software only, respects h(x) ≥ 0

#### 1.4 Enhanced Emissivity Coating

Upgrade shell bottom hemisphere coating:

```
Current: Standard high-emissivity paint (ε = 0.90)
Upgrade: Acktar Spectral Black or similar (ε = 0.98)

Radiation improvement:
  Q_new/Q_old = ε_new/ε_old = 0.98/0.90 = 1.089 (+9%)

At 4W baseline radiation: +0.36W
Combined with closer gap: More significant

Cost: $10-15 for enough material
Application: Spray or brush on internal surface of bottom hemisphere
```

---

### TIER 2: Consider for V3.2 (Medium Investment)

#### 2.1 Borosilicate Glass Shell

Replace acrylic with thermally conductive glass:

| Property | Acrylic (PMMA) | Borosilicate |
|----------|----------------|--------------|
| Thermal conductivity | 0.2 W/m·K | 1.1 W/m·K |
| Improvement | Baseline | **5.5× better** |
| Optical clarity | Excellent | Excellent |
| Impact resistance | Good | Moderate |
| Cost (85mm hemisphere) | $15 | $50-80 |
| Weight | 90g | 150g |

**Impact:** Shell thermal resistance drops from R = 37.5 K/W to R = 6.8 K/W

**Considerations:**
- Weight increase: +60g per hemisphere (+120g total)
- Maglev capacity: 500g - 511g = OVER BUDGET
- Would require mass optimization elsewhere or maglev upgrade

**Verdict:** Only viable if other mass reductions achieved first

#### 2.2 Flat Heat Pipe to Bottom

Add dedicated heat transport to radiation zone:

```
┌─────────────────────────────────────────────────────────────────┐
│                  HEAT PIPE ROUTING                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                    ╭──────────╮                                  │
│                   │  Display  │                                  │
│                   │   (top)   │                                  │
│                    ╰────┬─────╯                                  │
│                         │                                        │
│              ╭──────────┼──────────╮                            │
│             │     SoC Zone         │  ◀── HEAT SOURCE           │
│             │   ┌───────────┐      │                            │
│             │   │  QCS6490  │──────┼───╮                        │
│             │   └───────────┘      │   │ Heat Pipe              │
│              ╰──────────┬──────────╯   │ (3×80mm sintered)      │
│                         │              │                        │
│                         │              │                        │
│              ╭──────────┼──────────╮   │                        │
│             │     Battery Zone     │   │                        │
│             │   ┌───────────┐      │   │                        │
│             │   │  Battery  │      │   │                        │
│             │   └───────────┘      │   │                        │
│              ╰──────────┬──────────╯   │                        │
│                         │              │                        │
│              ╭──────────┼──────────╮   │                        │
│             │     RX Coil Zone     │◀──╯ CONDENSER              │
│             │   ╭────────────╮     │     (spreads heat to       │
│             │   │  RX Coil   │     │      bottom shell)         │
│             │   ╰────────────╯     │                            │
│              ╰─────────────────────╯                            │
│                         │                                        │
│                    [15mm AIR GAP]                               │
│                         │                                        │
│                    [MAGLEV BASE]  ◀── Absorbs radiated heat     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Specifications:**
- Type: Sintered copper heat pipe
- Dimensions: 3mm diameter × 80mm length (bent to fit)
- Capacity: 15-20W
- Weight: 5g
- Cost: $8-15

**Impact:** Directs heat to optimal radiation zone (+30% coupling)

#### 2.3 Variable Shell Thickness

Optimize shell for thermal vs structural requirements:

```
Current: 7.5mm uniform thickness

Proposed:
  Top hemisphere (display zone): 7.5mm (maintain strength)
  Equator: 7.5mm (joint integrity)
  Bottom hemisphere (thermal zone): 5.0mm (reduced R)

Thermal improvement: R = L/(kA)
  R_old = 7.5/(0.2×A) = 37.5/A
  R_new = 5.0/(0.2×A) = 25.0/A
  Improvement: 33% lower thermal resistance

Weight savings: ~15g

Risk: Structural analysis required
```

---

### TIER 3: Major Redesign (V4)

#### 3.1 100mm Sphere

Increase sphere diameter for more surface area:

| Parameter | 85mm | 100mm | Change |
|-----------|------|-------|--------|
| Surface area | 0.0227 m² | 0.0314 m² | +38% |
| Internal volume | 321 cm³ | 524 cm³ | +63% |
| Dissipation capacity | 8-12W | 11-17W | +40% |
| Weight (shell) | 90g | 130g | +44% |

**Impact:** Significant thermal improvement but requires full mechanical redesign

---

## Recommended Implementation Package

### V3.1 Thermal Upgrade (Implement Now)

| Component | Impact | Cost | Weight |
|-----------|--------|------|--------|
| Vapor chamber (40×40×2mm) | +1.5W | $18 | +8g |
| PCM buffer (50g paraffin) | +10 min peak | $5 | +50g |
| Enhanced emissivity coating | +0.5W | $10 | 0g |
| Dynamic levitation (software) | +2.5W | $0 | 0g |
| **TOTAL** | **+4.5W + buffer** | **$33** | **+58g** |

### Projected Thermal Performance

```
┌─────────────────────────────────────────────────────────────────┐
│              IMPROVED THERMAL BUDGET                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   MODE              │  LOAD   │  CAPACITY  │  STATUS            │
│   ──────────────────┼─────────┼────────────┼─────────────       │
│   Docked Idle       │  6.7W   │  15-16W    │  ✅ Sustainable    │
│   Docked Active     │  13.8W  │  15-16W    │  ✅ Sustainable    │
│   Docked Peak       │  22.7W  │  15-16W    │  ⚠️ 15-20 min     │
│   Portable Idle     │  3.0W   │  4-5W      │  ✅ Sustainable    │
│   Portable Active   │  5.0W   │  4-5W      │  ⚠️ Throttled     │
│                                                                  │
│   BEFORE: Docked Active (13.8W) exceeded capacity (10W)         │
│   AFTER:  Docked Active (13.8W) within capacity (15-16W) ✅     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## BOM Additions

| Part | Description | Supplier | Qty | Unit Cost | Total |
|------|-------------|----------|-----|-----------|-------|
| Vapor chamber | 40×40×2mm Cu-H₂O | Wakefield-Vette | 1 | $18.00 | $18.00 |
| PCM | RT42 paraffin, 100g pack | Rubitherm | 1 | $5.00 | $5.00 |
| Spectral coating | Acktar Spectral Black | Acktar | 1 | $10.00 | $10.00 |
| **TOTAL** | | | | | **$33.00** |

---

## Weight Budget Impact

```
BEFORE (V3.0):
  Orb total: 391g
  Target: 350g
  Over budget: 41g
  Maglev margin: 109g (500g - 391g)

AFTER (V3.1 Thermal):
  Orb total: 391g + 58g = 449g
  Target: 350g
  Over budget: 99g
  Maglev margin: 51g (500g - 449g)

STATUS: Still within 500g maglev capacity ✅
        But mass optimization recommended for V3.2
```

---

## Implementation Priority

| Priority | Item | Owner | Timeline |
|----------|------|-------|----------|
| P0 | Dynamic levitation firmware | Tim | Week 1 |
| P0 | Order vapor chamber samples | Tim | Week 1 |
| P1 | Integrate vapor chamber into PCB stack | Contractor | Week 2 |
| P1 | Source and test PCM material | Contractor | Week 2 |
| P2 | Apply enhanced emissivity coating | Contractor | Week 3 |
| P2 | Validate thermal improvement via testing | Contractor | Week 4 |

---

## Conclusion

**YES, we can significantly improve thermal dissipation while maintaining full waterproofing.**

The combination of:
1. Vapor chamber heat spreading
2. Phase change material buffering
3. Dynamic levitation height control
4. Enhanced emissivity surface treatment

Increases effective dissipation from **10W to 15-16W** — enough to sustain active mode (13.8W) indefinitely while docked.

Peak loads (22.7W) still require throttling, but PCM extends sustainable burst time from ~5 minutes to ~15-20 minutes.

**Total additional cost: $33**
**Total additional weight: 58g**
**Waterproofing: MAINTAINED (all internal/surface treatments)**

---

```
h(x) ≥ 0 always.
Heat flows. Constraints hold.
The mirror stays cool.
鏡
```
