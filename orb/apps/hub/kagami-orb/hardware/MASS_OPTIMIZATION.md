# Kagami Orb V3.1 — Mass Optimization Plan

**CANONICAL REFERENCE**: See `hardware/SPECS.md` for authoritative specifications.
**Last Updated:** January 2026
**Status:** OPTIMIZATION REQUIRED (-41g)

---

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| **Target Mass** | 350g |
| **Current Mass** | 391g |
| **Delta Required** | **-41g** |
| **Optimization Status** | IN PROGRESS |

The Kagami Orb V3.1 is currently 41g over the target mass of 350g. This document
details the component mass breakdown and optimization strategies to achieve target.

**Why 350g matters:**
- Stirlingkit maglev module rated for 500g maximum capacity
- 350g provides 150g safety margin for stable levitation
- Heavier orbs reduce levitation height and stability
- Thermal dissipation degrades with higher mass (more thermal mass)

---

## CURRENT MASS BREAKDOWN

### By Assembly

| Assembly | Components | Current (g) | Notes |
|----------|------------|-------------|-------|
| **Shell** | Top + bottom hemispheres | 90 | PC/ABS 2.5mm wall |
| **Display Assembly** | AMOLED + Camera + Mount | 35 | Including adhesives |
| **Compute Stack** | SoM + Hailo + PCB + heatsink | 56 | Main electronics |
| **Audio System** | Mics + DSP + speaker + amp | 12 | 4x sensiBel |
| **LED Ring** | 16x HD108 + diffuser + flex | 10 | Equator assembly |
| **Battery** | 2200mAh 3S LiPo + BMS | 150 | Major mass item |
| **Power System** | Charger + coil + ferrite | 38 | WPC receive |
| **TOTAL** | — | **391g** | Over by 41g |

### Detailed Component Breakdown

| Component | Manufacturer | Mass (g) | % of Total |
|-----------|--------------|----------|------------|
| Battery cell (3S) | Generic | 140 | 35.8% |
| Shell top | Custom | 45 | 11.5% |
| Shell bottom | Custom | 45 | 11.5% |
| QCS6490 SoM | Thundercomm | 25 | 6.4% |
| Main PCB | Custom | 18 | 4.6% |
| RX Coil | Custom Litz | 15 | 3.8% |
| IMX989 module | SincereFirst | 15 | 3.8% |
| Heatsink | Custom | 12 | 3.1% |
| Ferrite shield | Generic | 12 | 3.1% |
| Battery BMS | Generic | 10 | 2.6% |
| LED diffuser ring | Custom | 8 | 2.0% |
| Hailo-10H | Hailo | 8 | 2.0% |
| Display mount | Custom SLA | 8 | 2.0% |
| Speaker | Yueda | 5 | 1.3% |
| Display (AMOLED) | King Tech | 5 | 1.3% |
| Camera mount | Custom | 5 | 1.3% |
| XMOS DSP | XMOS | 3 | 0.8% |
| ESP32-S3 | Espressif | 3 | 0.8% |
| sensiBel x4 | sensiBel | 2 | 0.5% |
| HD108 LEDs x16 | Rose | 1.6 | 0.4% |
| BQ25895 | TI | 0.1 | <0.1% |
| BQ40Z50 | TI | 0.1 | <0.1% |
| Misc (wires, adhesive) | — | 4 | 1.0% |
| **TOTAL** | — | **391g** | 100% |

---

## OPTIMIZATION STRATEGIES

### Priority 1: Shell Material Change (-25g to -35g)

**Current:** PC/ABS injection molded, 2.5mm wall thickness = 90g total

**Options:**

| Material | Density | Wall | Mass | Delta | Cost Impact |
|----------|---------|------|------|-------|-------------|
| PC/ABS (current) | 1.20 g/cm3 | 2.5mm | 90g | — | — |
| PC (polycarbonate) | 1.20 g/cm3 | 2.0mm | 72g | -18g | +$5 |
| Nylon PA12 | 1.01 g/cm3 | 2.0mm | 61g | -29g | +$15 |
| Carbon fiber/PA | 1.15 g/cm3 | 1.5mm | 52g | -38g | +$50 |
| Magnesium alloy | 1.80 g/cm3 | 0.8mm | 43g | -47g | +$80 |

**Recommendation:** Switch to **Nylon PA12** at 2.0mm wall thickness.
- Achieves -29g reduction
- Maintains impact resistance
- Moderate cost increase (+$15)
- Can be SLS 3D printed for prototypes, injection molded for production

### Priority 2: Battery Cell Selection (-15g to -25g)

**Current:** Generic 2200mAh 3S LiPo = 150g (with BMS)

**High energy density alternatives:**

| Cell Type | Capacity | Voltage | Energy | Mass | Specific Energy |
|-----------|----------|---------|--------|------|-----------------|
| Generic LiPo (current) | 2200mAh | 11.1V | 24.4Wh | 150g | 163 Wh/kg |
| Panasonic NCR18650GA | 2x 3500mAh (series) | 7.4V | 25.9Wh | 92g | 282 Wh/kg |
| Samsung 21700 50E | 1x 5000mAh | 3.7V | 18.5Wh | 68g | 272 Wh/kg |
| Custom Li-ion 3S1P | 2100mAh | 11.1V | 23.3Wh | 125g | 186 Wh/kg |
| LiFePO4 | 1500mAh | 12.8V | 19.2Wh | 180g | 107 Wh/kg |

**Recommendation:** Switch to **Custom Li-ion 3S1P** using high-density cells.
- Achieves -25g reduction (150g -> 125g)
- Maintains 11.1V nominal voltage
- Similar energy capacity (23.3Wh vs 24.4Wh)
- Requires custom battery pack design

**Alternative for maximum weight savings:**
Use 2S configuration at 7.4V with boost converter, enabling lighter cells.
- Risk: Boost converter adds complexity and efficiency loss
- Savings: Up to -40g possible

### Priority 3: Heatsink Optimization (-5g)

**Current:** Solid aluminum heatsink = 12g

**Options:**

| Design | Material | Mass | Thermal | Notes |
|--------|----------|------|---------|-------|
| Solid block (current) | Al 6061 | 12g | Good | Simple |
| Finned design | Al 6061 | 9g | Better | +surface area |
| Heat pipe + fins | Cu + Al | 8g | Best | Complex |
| Vapor chamber | Cu | 7g | Excellent | Expensive |
| Graphite sheet | Graphite | 4g | Good | New tech |

**Recommendation:** Switch to **graphite thermal interface** + thin aluminum spreader.
- Achieves -5g reduction (12g -> 7g)
- Graphite has 5x thermal conductivity of aluminum in-plane
- Bonds directly to shell for passive cooling

### Priority 4: PCB Stack Optimization (-3g to -5g)

**Current:** 4-layer FR4 PCB = 18g

**Options:**

| Change | Current | Proposed | Savings |
|--------|---------|----------|---------|
| PCB material | FR4 | Rogers 4003C | -2g |
| PCB thickness | 1.6mm | 1.2mm | -3g |
| Copper weight | 2oz | 1oz | -1g |
| Connector elimination | 4 connectors | 2 flex | -1g |

**Recommendation:** Use **1.2mm FR4** with **flex connectors**.
- Achieves -4g reduction (18g -> 14g)
- 1.2mm is standard and readily available
- Flex connectors reduce interconnect mass

### Priority 5: Coil Optimization (-3g)

**Current:** 70mm Litz coil = 15g

**Options:**

| Optimization | Description | Savings |
|--------------|-------------|---------|
| Reduce turns | 20 -> 18 turns | -2g |
| Thinner wire | 100/46 -> 70/46 AWG | -3g |
| PCB coil | Spiral trace | -8g |

**Risk analysis:**
- Fewer turns: Reduces inductance, must retune resonance
- Thinner wire: Higher resistance, lower Q, less efficiency
- PCB coil: Significantly lower Q (~50), efficiency drops to ~70%

**Recommendation:** Use **PCB coil** for charging if efficiency drop acceptable.
- Achieves -8g reduction (15g -> 7g)
- Trade-off: 88% -> 75% efficiency at 5mm gap
- Charging time increases from 2h -> 2.5h

**Alternative (conservative):** Keep Litz coil, accept 15g mass.

### Priority 6: Ferrite Shield (-4g)

**Current:** 60mm Mn-Zn ferrite disc = 12g

**Options:**

| Change | Description | Savings |
|--------|-------------|---------|
| Thinner disc | 0.5mm -> 0.3mm | -4g |
| Segmented design | 6 wedges | -2g |
| Ferrite sheet | Flexible TDK | -3g |

**Recommendation:** Use **TDK flexible ferrite sheet** (FGSB series).
- Achieves -4g reduction (12g -> 8g)
- Maintains shielding effectiveness
- Easier assembly (conformable)

### Priority 7: Display Mount (-2g)

**Current:** SLA 3D printed mount = 8g

**Options:**

| Change | Description | Savings |
|--------|-------------|---------|
| Thinner walls | 1.2mm -> 0.8mm | -2g |
| Material | SLA -> MJF PA12 | -1g |
| Integrate into shell | Combine parts | -3g |

**Recommendation:** **Integrate display mount into top shell** design.
- Achieves -3g reduction (eliminates separate part)
- Reduces assembly steps
- Requires shell redesign

---

## OPTIMIZATION SUMMARY

| Priority | Optimization | Mass Savings | Difficulty | Cost |
|----------|--------------|--------------|------------|------|
| P1 | Shell: PC/ABS -> PA12 | -29g | Medium | +$15 |
| P2 | Battery: Generic -> Custom | -25g | High | +$30 |
| P3 | Heatsink: Graphite | -5g | Low | +$10 |
| P4 | PCB: 1.2mm + flex | -4g | Medium | +$5 |
| P5 | Coil: PCB spiral | -8g | High | -$10 |
| P6 | Ferrite: TDK sheet | -4g | Low | +$5 |
| P7 | Mount: Integrate | -3g | Medium | $0 |
| **TOTAL POTENTIAL** | — | **-78g** | — | — |

### Recommended Implementation Path

**Phase 1 (Low Risk, -38g):**
1. Shell material change: -29g
2. Heatsink redesign: -5g
3. Ferrite sheet: -4g

**Phase 2 (Medium Risk, -7g if needed):**
4. PCB optimization: -4g
5. Mount integration: -3g

**Phase 3 (High Risk, use only if necessary):**
6. Battery redesign: -25g
7. PCB coil: -8g

**Phase 1 alone achieves 350g target:**
- Current: 391g
- Phase 1 savings: -38g
- Result: **353g** (within margin)

---

## REVISED MASS BUDGET (Post-Optimization)

| Assembly | Current (g) | Optimized (g) | Savings |
|----------|-------------|---------------|---------|
| Shell | 90 | 61 | -29g |
| Display Assembly | 35 | 32 | -3g |
| Compute Stack | 56 | 51 | -5g |
| Audio System | 12 | 12 | 0g |
| LED Ring | 10 | 10 | 0g |
| Battery | 150 | 150 | 0g |
| Power System | 38 | 34 | -4g |
| **TOTAL** | **391g** | **350g** | **-41g** |

---

## IMPLEMENTATION SCHEDULE

| Week | Task | Deliverable |
|------|------|-------------|
| 1 | Shell CAD redesign for PA12 | Updated STEP files |
| 2 | PA12 SLS prototype order | Shell samples |
| 3 | Graphite heatsink design | Thermal validation |
| 4 | TDK ferrite sheet evaluation | Shielding test |
| 5 | Integration testing | Assembled prototype |
| 6 | Mass verification | Certified weight |

---

## RISK ASSESSMENT

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| PA12 impact resistance | Medium | Low | Impact testing |
| Graphite thermal bond | Low | Medium | Thermal grease backup |
| Ferrite sheet shielding | Medium | Low | EMC testing |
| Assembly tolerance | Low | Medium | Jig design |

---

## VERIFICATION PROTOCOL

After optimization, verify:
1. [ ] Total mass <= 350g on calibrated scale
2. [ ] Levitation stable at 18-25mm gap
3. [ ] Thermal performance: T < 55C under load
4. [ ] Drop test: 0.5m onto hardwood, no damage
5. [ ] EMC: FCC Part 15 compliance

---

**CANONICAL REFERENCE**: This document details mass optimization.
For component specifications, see `hardware/SPECS.md`.
