# Kagami Orb V3 — Risk Mitigation Plan

**Version:** 1.0
**Date:** 2026-01-11
**Status:** Active
**Last Review:** 2026-01-11

---

## Executive Summary

This document establishes the risk management framework for the Kagami Orb V3 project. Based on Byzantine audit findings, we have identified 14 risks across Critical, High, and Medium severity levels. This plan defines mitigation strategies, fallback options, ownership, and monitoring cadence for each risk.

**Risk Summary:**
| Severity | Count | Acceptable Before Prototype |
|----------|-------|----------------------------|
| Critical | 5 | 0 unmitigated |
| High | 5 | ≤2 with active mitigation |
| Medium | 4 | Monitored |

---

## Risk Matrix Visualization

```
                    IMPACT
           Low      Medium      High
         ┌─────────┬─────────┬─────────┐
    High │   M-11  │  H-6    │  C-1    │
         │   M-13  │  H-7    │  C-2    │
         │         │  H-8    │  C-3    │
P        │         │         │  C-4    │
R        ├─────────┼─────────┼─────────┤
O  Med   │   M-12  │  H-9    │  C-5    │
B        │   M-14  │  H-10   │         │
A        │         │         │         │
B        ├─────────┼─────────┼─────────┤
I   Low  │         │         │         │
L        │         │         │         │
I        │         │         │         │
T        └─────────┴─────────┴─────────┘
Y

Legend:
  C = Critical (Red Zone) — Must mitigate before prototype
  H = High (Orange Zone) — Active mitigation required
  M = Medium (Yellow Zone) — Monitor and plan
```

---

## Risk Register

### Summary Table

| ID | Risk Name | Probability | Impact | Score | Status | Owner | Due |
|----|-----------|-------------|--------|-------|--------|-------|-----|
| C-1 | Thermal Budget Overrun | High | High | 9 | Open | Tim | Before Phase 2 |
| C-2 | sensiBel Mic Availability | High | High | 9 | Open | Contractor | Week 2 |
| C-3 | Hailo-10H Availability | High | High | 9 | Open | Tim | Week 1 |
| C-4 | PCB Design Incomplete | High | High | 9 | Open | Contractor | Week 10 |
| C-5 | Battery Safety (Sealed) | Medium | High | 6 | Open | Contractor + Lab | Before Production |
| H-6 | Mass Budget Overrun | High | Medium | 6 | Open | Contractor | Week 6 |
| H-7 | Camera Optical Quality | High | Medium | 6 | Open | Contractor | Week 4 |
| H-8 | I2C Address Conflict | High | Medium | 6 | Open | Contractor | Week 3 |
| H-9 | Contractor Budget Underestimation | Medium | Medium | 4 | Open | Tim | Week 1 |
| H-10 | Timeline Slip | Medium | Medium | 4 | Monitoring | Tim | Ongoing |
| M-11 | EMI/EMC Compliance | High | Low | 3 | Open | Contractor | Week 8 |
| M-12 | Camera Privacy Trust | Medium | Low | 2 | Open | Tim | Week 6 |
| M-13 | Maglev-WPT Coupling | High | Low | 3 | Open | Contractor | Week 4 |
| M-14 | AMOLED Transparency | Medium | Low | 2 | Open | Contractor | Week 5 |

---

## Critical Risks (Must Mitigate Before Prototype)

### C-1: Thermal Budget Risk

**Risk Statement:** Peak power consumption of 26.7W vastly exceeds the 2-4W passive dissipation capability of an 85mm sealed sphere.

| Attribute | Value |
|-----------|-------|
| **ID** | C-1 |
| **Probability** | High |
| **Impact** | High |
| **Risk Score** | 9 (3 × 3) |
| **Owner** | Tim |
| **Due Date** | Before Phase 2 |
| **Status** | Open |

**Root Cause Analysis:**
- QCS6490 SoC: 3-6W typical, 8W peak
- Hailo-10H NPU: 2.5W typical, 5W max
- AMOLED display: 0.5-1.5W
- Wireless charging losses: 3-5W (at 85% efficiency)
- Audio amplifier: 2-3W peak
- Total peak: ~26.7W vs ~2-4W passive dissipation

**Mitigation Strategy:**
1. **Immediate:** Commission FEA (Finite Element Analysis) thermal simulation before Phase 2
2. **Design:** Implement aggressive thermal throttling in firmware:
   - Tier 1 (>45°C): Reduce NPU to 50% clock
   - Tier 2 (>55°C): Disable NPU, reduce SoC to idle
   - Tier 3 (>65°C): Emergency shutdown, controlled landing
3. **Hardware:** Evaluate copper heat spreader from SoC to sphere surface
4. **Architecture:** Consider 100mm sphere variant with 40% more surface area

**Fallback Plan:**
- If 85mm fails thermal validation, pivot to 100mm sphere design
- 100mm provides ~39% more surface area for heat dissipation
- Requires new BOM for enclosure and coils

**Acceptance Criteria:**
- [ ] FEA simulation shows <60°C internal at sustained 10W load
- [ ] Thermal throttling firmware implemented and tested
- [ ] 2-hour continuous operation test passes

**Monitoring:**
- Weekly thermal simulation updates during Phase 1
- Temperature sensor integration in prototype firmware

---

### C-2: sensiBel Microphone Availability Risk

**Risk Statement:** sensiBel SBM100B is a single-source component from a startup company with no verified purchase path for prototypes.

| Attribute | Value |
|-----------|-------|
| **ID** | C-2 |
| **Probability** | High |
| **Impact** | High |
| **Risk Score** | 9 (3 × 3) |
| **Owner** | Contractor |
| **Due Date** | Week 2 |
| **Status** | Open |

**Root Cause Analysis:**
- sensiBel is a Norwegian MEMS startup (founded 2017)
- Optical MEMS technology is novel (not yet commoditized)
- No distributor listings on Digi-Key, Mouser, or Arrow
- -26dB SNR specification is class-leading but unverified
- Prototype quantities may not be available

**Mitigation Strategy:**
1. **Week 1:** Contact sensiBel directly via sales@sensibel.no
   - Request samples (4 units minimum)
   - Obtain lead time and MOQ information
   - Request eval board if available
2. **Week 1:** Qualify backup microphone: **Infineon IM69D130**
   - Available at Digi-Key ($3.50/unit)
   - -26dB SNR (comparable to sensiBel claim)
   - PDM output (requires firmware change from I2S)
3. **Week 2:** Make go/no-go decision on sensiBel

**Fallback Plan (Tier 1):**
- **Infineon IM69D130** ($3.50 ea, Digi-Key stock)
  - SNR: -26dB (claimed, need validation)
  - Interface: PDM (requires different audio path)
  - Form factor: 3.5mm × 2.65mm × 1.0mm
  - Firmware: PDM-to-PCM conversion in ESP32-S3

**Fallback Plan (Tier 2):**
- **INMP441** ($8/unit, widely available)
  - SNR: ~60dB (lower quality)
  - Interface: I2S (compatible with current design)
  - Trade-off: Reduced far-field performance

**Acceptance Criteria:**
- [ ] sensiBel samples ordered with confirmed ship date, OR
- [ ] IM69D130 qualified with SNR validation, OR
- [ ] INMP441 fallback accepted with documented limitations

**Monitoring:**
- Daily contact log with sensiBel during Week 1
- Parallel evaluation of IM69D130 on XMOS dev board

---

### C-3: Hailo-10H Availability Risk

**Risk Statement:** Hailo-10H is a new product requiring direct quote, with unknown lead times and production volume availability.

| Attribute | Value |
|-----------|-------|
| **ID** | C-3 |
| **Probability** | High |
| **Impact** | High |
| **Risk Score** | 9 (3 × 3) |
| **Owner** | Tim |
| **Due Date** | Week 1 |
| **Status** | Open |

**Root Cause Analysis:**
- Hailo-10H announced Q4 2025, limited initial availability
- No distributor stock (Digi-Key/Mouser show "Quote Required")
- GenAI-optimized NPU is differentiator but production may be limited
- M.2 form factor requires specific carrier board design

**Mitigation Strategy:**
1. **Day 1:** Contact Hailo directly via sales@hailo.ai
   - Request Hailo-10H M.2 module (1 unit for prototype)
   - Obtain pricing and lead time
   - Request eval kit ($149) as backup
2. **Week 1:** Evaluate **Hailo-8L** as fallback
   - 13 TOPS (vs 40 TOPS)
   - Available via distributors
   - Same M.2 form factor
3. **Week 1:** Confirm QCS6490 Hexagon NPU can handle critical inference paths

**Fallback Plan (Tier 1):**
- **Hailo-8L** ($45, distributor stock)
  - 13 TOPS INT8 (vs 40 TOPS INT4)
  - Sufficient for wake word, KWS, basic inference
  - Trade-off: No local LLM inference, must offload to cloud

**Fallback Plan (Tier 2):**
- **CPU-only inference**
  - Use QCS6490 Kryo cores only
  - Latency: ~500ms per inference (vs ~50ms with NPU)
  - Acceptable for prototype validation

**Acceptance Criteria:**
- [ ] Hailo-10H ordered with confirmed ship date, OR
- [ ] Hailo-8L qualified and ordered, OR
- [ ] CPU-only mode validated for critical paths

**Monitoring:**
- Daily contact log with Hailo during Week 1
- Firmware validation of fallback inference paths

---

### C-4: PCB Design Incomplete

**Risk Statement:** Custom carrier PCB schematic capture is incomplete, blocking board fabrication and all subsequent integration.

| Attribute | Value |
|-----------|-------|
| **ID** | C-4 |
| **Probability** | High |
| **Impact** | High |
| **Risk Score** | 9 (3 × 3) |
| **Owner** | Contractor |
| **Due Date** | Week 10 |
| **Status** | Open |

**Root Cause Analysis:**
- Main carrier PCB connects: QCS6490, Hailo-10H, XMOS, ESP32-S3, power management
- Schematic capture requires all component datasheets validated
- 4-layer stack-up minimum for signal integrity
- Critical path: Without PCB, cannot integrate subsystems

**Mitigation Strategy:**
1. **Phase 1-2:** Use development boards for subsystem validation
   - QCS6490: Thundercomm TurboX C6490 DK
   - Hailo: Hailo-10H eval kit
   - Audio: XMOS XVF3800 dev board
2. **Phase 3:** Complete schematic capture as deliverable
   - Include all power rails with sequencing
   - Include I2C address map (verified)
   - Include thermal via placement
3. **Phase 4:** PCB fabrication and assembly
   - Use JLCPCB/PCBWay for 4-layer prototype
   - 5-7 day turn time for expedited

**Fallback Plan:**
- Continue prototype validation with dev boards (larger form factor)
- Accept "fat prototype" that validates function but not form
- Defer compact PCB to production phase

**Acceptance Criteria:**
- [ ] Complete schematic with BOM cross-reference
- [ ] DRC clean PCB layout
- [ ] Gerbers generated and validated
- [ ] First article boards received and tested

**Monitoring:**
- Weekly schematic review during Phase 3
- Checklist verification of all subsystem connections

---

### C-5: Battery Safety (Sealed Enclosure)

**Risk Statement:** LiPo battery in a sealed 85mm sphere poses swelling and thermal runaway risks without pressure relief.

| Attribute | Value |
|-----------|-------|
| **ID** | C-5 |
| **Probability** | Medium |
| **Impact** | High |
| **Risk Score** | 6 (2 × 3) |
| **Owner** | Contractor + Certification Lab |
| **Due Date** | Before Production |
| **Status** | Open |

**Root Cause Analysis:**
- LiPo cells can swell up to 10% during normal aging
- Thermal runaway can occur at >80°C internal cell temperature
- Sealed sphere provides no gas venting path
- Swelling can exert mechanical pressure on AMOLED display

**Mitigation Strategy:**
1. **Design:** Include pressure relief valve in sphere design
   - Spring-loaded valve at pole opposite display
   - Opens at 5 PSI differential
   - Re-seals after pressure equalization
2. **Design:** Create swelling accommodation zone
   - 2mm gap around battery in mounting
   - Foam padding to absorb minor expansion
3. **Firmware:** Aggressive battery thermal management
   - Charge termination at 45°C cell temperature
   - Discharge current limit at 50°C
4. **Certification:** Budget for UL 2054 battery testing
   - Crush test, overcharge test, short circuit test
   - Required for production units

**Fallback Plan:**
- Reduce battery capacity to smaller cells with more margin
- Use LiFePO4 chemistry (safer but lower density)
- Accept shorter runtime for enhanced safety

**Acceptance Criteria:**
- [ ] Pressure relief valve tested and validated
- [ ] Battery thermal limits implemented in BMS firmware
- [ ] UL 2054 testing plan documented (production phase)
- [ ] 100 charge cycles without visible swelling

**Monitoring:**
- Weekly visual inspection of battery during prototype testing
- Temperature logging during all charge/discharge cycles

---

## High Risks

### H-6: Mass Budget Overrun

**Risk Statement:** Current mass estimates show 41g over the 400g maglev limit.

| Attribute | Value |
|-----------|-------|
| **ID** | H-6 |
| **Probability** | High |
| **Impact** | Medium |
| **Risk Score** | 6 (3 × 2) |
| **Owner** | Contractor |
| **Due Date** | Week 6 |
| **Status** | Open |

**Current Mass Budget:**
| Component | Estimated Mass |
|-----------|----------------|
| QCS6490 SoM | 15g |
| Hailo-10H | 8g |
| ESP32-S3 | 3g |
| XMOS XVF3800 | 5g |
| Battery (2200mAh 3S) | 75g |
| AMOLED display | 25g |
| Sony IMX989 camera | 15g |
| Speaker + amp | 20g |
| Microphones (4×) | 4g |
| PCB + connectors | 40g |
| LEDs + wiring | 15g |
| RX coil | 30g |
| Enclosure (acrylic) | 150g |
| Thermal management | 20g |
| Misc (screws, gaskets) | 16g |
| **Total** | **441g** |
| **Target** | **400g** |
| **Overrun** | **41g (10.25%)** |

**Mitigation Strategy:**
1. **Enclosure:** Switch to thin-wall injection molding (saves ~40g)
2. **Battery:** Evaluate smaller 1500mAh cell (saves ~25g, loses 1.5h runtime)
3. **Coil:** Optimize RX coil winding (saves ~5g)
4. **PCB:** Use flex-rigid PCB where possible (saves ~10g)

**Fallback Plan:**
- Upgrade to 600g maglev module (HCNT ZT-HX600, +$30)
- Accept larger base footprint

**Acceptance Criteria:**
- [ ] Actual mass measurement <400g, OR
- [ ] Upgraded maglev module specified

---

### H-7: Camera Optical Quality

**Risk Statement:** Sony IMX989 optical path through AMOLED pupil aperture is unvalidated.

| Attribute | Value |
|-----------|-------|
| **ID** | H-7 |
| **Probability** | High |
| **Impact** | Medium |
| **Risk Score** | 6 (3 × 2) |
| **Owner** | Contractor |
| **Due Date** | Week 4 |
| **Status** | Open |

**Technical Concerns:**
- Camera views through circular aperture in AMOLED
- Dielectric mirror coating may cause reflections
- Pupil animation may create light artifacts
- Focus distance (25cm-∞) may be affected by optical stack

**Mitigation Strategy:**
1. **Week 2:** Acquire IMX989 module and AMOLED sample
2. **Week 3:** Build optical test fixture
3. **Week 4:** Validate MTF, distortion, and low-light performance
4. Design anti-reflection coating for aperture edge

**Fallback Plan:**
- Use separate camera window (breaks "hidden in pupil" aesthetic)
- Reduce camera spec to smaller sensor

**Acceptance Criteria:**
- [ ] MTF >50% at 1000 lp/mm center
- [ ] No visible ghosting from display backlight
- [ ] Focus functional 25cm to infinity

---

### H-8: I2C Address Conflict

**Risk Statement:** Multiple I2C devices may have hardcoded addresses that conflict.

| Attribute | Value |
|-----------|-------|
| **ID** | H-8 |
| **Probability** | High |
| **Impact** | Medium |
| **Risk Score** | 6 (3 × 2) |
| **Owner** | Contractor |
| **Due Date** | Week 3 |
| **Status** | Open |

**Current I2C Map (Preliminary):**
| Device | Default Address | Configurable |
|--------|-----------------|--------------|
| ICM-45686 IMU | 0x68 | Yes (AD0 pin) |
| SHT45 Temp/Humidity | 0x44 | No |
| VL53L8CX ToF | 0x29 | Yes (I2C_RST) |
| AS7343 Spectral | 0x39 | No |
| SEN66 Air Quality | 0x6B | No |
| BQ25895 Charger | 0x6A | No |

**Mitigation Strategy:**
1. **Week 1:** Document all I2C addresses from datasheets
2. **Week 2:** Identify conflicts and resolution options
3. **Week 3:** Use I2C multiplexer (TCA9548A) if needed

**Fallback Plan:**
- Implement I2C bus segmentation with multiplexer
- Move conflicting devices to separate bus

**Acceptance Criteria:**
- [ ] Complete I2C address map documented
- [ ] All devices respond to i2cdetect scan
- [ ] No bus contention observed

---

### H-9: Contractor Budget Underestimation

**Risk Statement:** Project complexity may exceed initial $8,500 budget estimate.

| Attribute | Value |
|-----------|-------|
| **ID** | H-9 |
| **Probability** | Medium |
| **Impact** | Medium |
| **Risk Score** | 4 (2 × 2) |
| **Owner** | Tim |
| **Due Date** | Week 1 |
| **Status** | Open |

**Budget Analysis:**
| Phase | Estimated Hours | Rate | Cost |
|-------|-----------------|------|------|
| Component sourcing | 10h | $75/h | $750 |
| Subsystem integration | 40h | $75/h | $3,000 |
| Firmware development | 30h | $75/h | $2,250 |
| PCB design | 20h | $75/h | $1,500 |
| Assembly & test | 20h | $75/h | $1,500 |
| Documentation | 10h | $75/h | $750 |
| **Subtotal** | **130h** | | **$9,750** |
| **Current Budget** | | | **$8,500** |
| **Gap** | | | **$1,250** |

**Mitigation Strategy:**
1. **Week 1:** Negotiate fixed-price milestones with contractor
2. Include 20% contingency in final contract
3. Define scope boundaries clearly (what's in/out)

**Fallback Plan:**
- Reduce scope to core functionality (remove outdoor dock)
- Phase PCB design to future contract

**Acceptance Criteria:**
- [ ] Signed contract with milestone payments
- [ ] Contingency budget approved

---

### H-10: Timeline Slip

**Risk Statement:** 12-week schedule has limited slack for component delays or rework.

| Attribute | Value |
|-----------|-------|
| **ID** | H-10 |
| **Probability** | Medium |
| **Impact** | Medium |
| **Risk Score** | 4 (2 × 2) |
| **Owner** | Tim |
| **Due Date** | Ongoing |
| **Status** | Monitoring |

**Critical Path:**
```
Week 1-2:   Component sourcing (parallel)
Week 3-4:   Subsystem validation
Week 5-6:   Integration
Week 7-8:   Firmware development
Week 9-10:  PCB design
Week 11:    Assembly
Week 12:    Testing & ship
```

**Mitigation Strategy:**
1. Order long-lead components Day 1
2. Validate subsystems in parallel where possible
3. Maintain weekly progress reviews

**Fallback Plan:**
- Accept 2-week schedule extension if needed
- Ship "functional prototype" vs "polished prototype"

**Acceptance Criteria:**
- [ ] Weekly milestone reviews conducted
- [ ] Critical path items tracked in project tool

---

## Medium Risks

### M-11: EMI/EMC Compliance

**Risk Statement:** 140kHz resonant charging may interfere with WiFi/Bluetooth or fail FCC Part 15.

| Attribute | Value |
|-----------|-------|
| **ID** | M-11 |
| **Probability** | High |
| **Impact** | Low |
| **Risk Score** | 3 (3 × 1) |
| **Owner** | Contractor |
| **Due Date** | Week 8 |
| **Status** | Open |

**Mitigation Strategy:**
1. Test WiFi signal strength with wireless charging active
2. Add ferrite shielding if interference detected
3. Budget for pre-compliance EMC scan

**Fallback Plan:**
- Disable charging during active WiFi transmission
- Reduce charging power (10W vs 15W)

**Acceptance Criteria:**
- [ ] WiFi throughput >80% of baseline with charging active
- [ ] No audible interference on speaker output

---

### M-12: Camera Privacy Trust

**Risk Statement:** Hidden camera may create privacy concerns with household members or guests.

| Attribute | Value |
|-----------|-------|
| **ID** | M-12 |
| **Probability** | Medium |
| **Impact** | Low |
| **Risk Score** | 2 (2 × 1) |
| **Owner** | Tim |
| **Due Date** | Week 6 |
| **Status** | Open |

**Mitigation Strategy:**
1. Implement clear LED indicator when camera active
2. Hardware camera disable (physical shutter or power cut)
3. Document privacy controls in user guide

**Fallback Plan:**
- Remove camera from V1 (add in V2 with privacy UX)

**Acceptance Criteria:**
- [ ] Camera active LED visible from all angles
- [ ] Camera can be disabled without device restart

---

### M-13: Maglev-WPT Coupling

**Risk Statement:** Magnetic levitation and wireless power transfer may have unexpected interactions.

| Attribute | Value |
|-----------|-------|
| **ID** | M-13 |
| **Probability** | High |
| **Impact** | Low |
| **Risk Score** | 3 (3 × 1) |
| **Owner** | Contractor |
| **Due Date** | Week 4 |
| **Status** | Open |

**Technical Concerns:**
- 140kHz WPT frequency may induce eddy currents in maglev magnets
- Ferrite shielding required between systems
- Levitation stability during charging transitions

**Mitigation Strategy:**
1. Validate TEST 1.1A (FOD calibration with magnets)
2. Measure levitation stability during charge cycles
3. Tune WPT frequency if needed

**Fallback Plan:**
- Increase ferrite shielding thickness
- Accept reduced WPT efficiency with more shielding

**Acceptance Criteria:**
- [ ] Levitation position stable ±0.5mm during charging
- [ ] FOD false alarm rate <1%

---

### M-14: AMOLED Transparency

**Risk Statement:** Dielectric mirror coating for capacitive touch may affect display visibility or touch accuracy.

| Attribute | Value |
|-----------|-------|
| **ID** | M-14 |
| **Probability** | Medium |
| **Impact** | Low |
| **Risk Score** | 2 (2 × 1) |
| **Owner** | Contractor |
| **Due Date** | Week 5 |
| **Status** | Open |

**Mitigation Strategy:**
1. Test display with and without coating
2. Measure touch accuracy across display surface
3. Validate outdoor visibility

**Fallback Plan:**
- Use standard cover glass (no mirror effect)
- Remove capacitive touch, rely on radar gesture only

**Acceptance Criteria:**
- [ ] Display luminance >300 nits through coating
- [ ] Touch accuracy <2mm error

---

## Risk Monitoring Cadence

### Weekly Review (Every Friday)

| Activity | Participants | Duration |
|----------|--------------|----------|
| Risk register update | Tim, Contractor | 15 min |
| Critical risk status | Tim, Contractor | 15 min |
| New risk identification | All | 10 min |
| Mitigation progress | Contractor | 10 min |

### Phase Gate Reviews

| Gate | Timing | Exit Criteria |
|------|--------|---------------|
| Phase 1 | Week 2 | All C-2, C-3 risks mitigated or accepted |
| Phase 2 | Week 6 | Thermal validation complete (C-1) |
| Phase 3 | Week 10 | PCB design complete (C-4) |
| Phase 4 | Week 12 | All critical risks closed |

---

## Escalation Process

### Level 1: Project Team

**Trigger:** Risk score increases or new risk identified
**Response:** Update risk register, adjust mitigation plan
**Timeline:** Within 24 hours

### Level 2: Stakeholder Review

**Trigger:** Critical risk mitigation fails, or timeline impact >1 week
**Response:** Tim reviews with contractor, decision on fallback
**Timeline:** Within 48 hours

### Level 3: Project Pause

**Trigger:** Safety risk identified, or budget exceeded by >30%
**Response:** Stop work, full reassessment, go/no-go decision
**Timeline:** Immediate

---

## Risk Closure Criteria

A risk is closed when:

1. **Mitigated:** Root cause addressed, verification test passed
2. **Accepted:** Risk acknowledged, fallback plan active, no further action needed
3. **Avoided:** Design change eliminates the risk entirely
4. **Transferred:** Risk moved to another party (e.g., certification lab)

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-11 | Kagami | Initial release based on Byzantine audit |

---

## Related Documents

| Document | Description |
|----------|-------------|
| [VALIDATION_PLAN.md](VALIDATION_PLAN.md) | Test procedures for risk verification |
| [HARDWARE_BOM.md](HARDWARE_BOM.md) | Component specifications and alternatives |
| [POWER_SYSTEM_COMPLETE.md](POWER_SYSTEM_COMPLETE.md) | Thermal and power analysis |
| [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) | Overall architecture |
| [UPWORK_JOB_POSTING.md](UPWORK_JOB_POSTING.md) | Contractor deliverables |

---

*Risk management is not about eliminating all risks — it's about making informed decisions with clear fallback plans.*
