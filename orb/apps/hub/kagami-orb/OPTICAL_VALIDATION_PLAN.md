# Optical Validation Plan: Camera-Behind-AMOLED

**Version:** 1.0
**Date:** January 2026
**Status:** Critical Path Validation
**Risk Level:** HIGH — Core feature depends on optical quality

---

## Executive Summary

The Kagami Orb's **"living eye"** design places a 50MP Sony IMX989 camera behind a 1.39" round AMOLED display. The camera looks through the display's transparent regions to see the user.

**This is technically challenging.** Similar approaches (Samsung's under-display cameras, ZTE Axon) show degraded image quality. Orb's use case (presence detection, not selfies) may tolerate this — but we must validate.

### Critical Questions

1. **Can the IMX989 see through the AMOLED with acceptable quality for face detection?**
2. **Does the camera work in all lighting conditions?**
3. **Is light transmission sufficient for the sensor's requirements?**
4. **What's the fallback if optical quality is insufficient?**

---

## Optical System Architecture

### Current Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    OPTICAL STACK (CROSS-SECTION)                         │
│                                                                          │
│   LIGHT SOURCE (user/room)                                              │
│         │                                                                │
│         ▼                                                                │
│   ┌─────────────────────────┐  ← AMOLED Display (0.68mm)                │
│   │   Pixel Layer (OLED)    │     - RGB pixels emit light               │
│   │   TFT Backplane         │     - Gaps between pixels are transparent │
│   │   Substrate (glass)     │                                           │
│   └─────────────────────────┘                                           │
│         │                                                                │
│         │  Light passes through inter-pixel gaps                        │
│         ▼                                                                │
│   ┌─────────────────────────┐  ← Air gap (0.5-1.0mm)                    │
│   └─────────────────────────┘                                           │
│         │                                                                │
│         ▼                                                                │
│   ┌─────────────────────────┐  ← Camera Module (9.4mm)                  │
│   │   Lens Stack (7P)       │     - IMX989 1/0.98" sensor               │
│   │   IR Filter             │     - 50.3MP, 1.6μm pixels                │
│   │   IMX989 Sensor         │     - f/1.9 aperture                      │
│   └─────────────────────────┘                                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Optical Parameters

| Parameter | Specification | Notes |
|-----------|---------------|-------|
| **Display Resolution** | 454 × 454 px | 327 PPI |
| **Pixel Pitch** | ~78μm | Gap between pixels ~15-20μm |
| **Transmittance (typical)** | 10-15% | Through powered-off OLED |
| **Sensor Size** | 1/0.98" (16.384mm diag) | Needs max light |
| **Sensor Pixel Size** | 1.6μm | Large for low-light |
| **Aperture** | f/1.9 | Fast lens |

### Optical Challenges

| Challenge | Severity | Explanation |
|-----------|----------|-------------|
| **Low Light Transmission** | HIGH | Only 10-15% of light reaches sensor |
| **Diffraction Effects** | MEDIUM | Light bends around pixel elements |
| **Moiré Patterns** | MEDIUM | Interference between pixel grid and sensor |
| **Color Cast** | LOW | OLED color layers affect spectrum |
| **Flare/Ghosting** | LOW | Reflections within stack |

---

## Validation Test Protocol

### Phase 1: Bench Testing (Week 1-2)

#### Test 1.1: Static Transmittance Measurement

**Objective:** Measure actual light transmission through AMOLED samples.

**Equipment:**
- 1.39" AMOLED display (King Tech RM69330)
- Integrating sphere
- Spectrophotometer
- Calibrated light source (D65 standard illuminant)

**Procedure:**
1. Power AMOLED OFF (all pixels black)
2. Illuminate from front with calibrated source
3. Measure light reaching integrating sphere behind display
4. Calculate transmittance: T = (I_through / I_source) × 100%

**Pass Criteria:**
| Metric | Minimum | Target | Notes |
|--------|---------|--------|-------|
| Visible Transmittance (400-700nm) | 8% | 12% | Below 8% = fail |
| NIR Transmittance (850nm) | 15% | 25% | Face detection uses NIR |
| Uniformity | ±20% | ±10% | Across display area |

#### Test 1.2: Powered Display Transmittance

**Objective:** Measure transmission when display is showing "pupil" (black center).

**Procedure:**
1. Display static pupil image (pure black center, 15mm diameter)
2. Repeat transmittance measurement through pupil region only
3. Compare to fully-off transmittance

**Pass Criteria:**
- Pupil region transmittance ≥ 95% of powered-off transmittance
- No significant difference (OLED black = pixels off)

#### Test 1.3: IMX989 Response Test

**Objective:** Verify IMX989 can capture usable images through AMOLED.

**Equipment:**
- IMX989 camera module (SincereFirst)
- 1.39" AMOLED sample
- ISO 12233 resolution chart
- Light box (5000 lux, 500 lux, 50 lux, 5 lux)

**Procedure:**
1. Mount camera behind AMOLED at design distance
2. Capture resolution chart at each light level
3. Analyze MTF (Modulation Transfer Function)
4. Capture face at each light level

**Pass Criteria:**
| Light Level | Face Detection | Resolution (MTF50) |
|-------------|----------------|-------------------|
| 5000 lux (bright) | 100% | >50 lp/mm |
| 500 lux (office) | 100% | >40 lp/mm |
| 50 lux (dim) | >95% | >30 lp/mm |
| 5 lux (dark) | >80% | >20 lp/mm |

---

### Phase 2: Integration Testing (Week 3-4)

#### Test 2.1: Assembled Orb Optical Path

**Objective:** Validate optical performance in final assembly.

**Setup:**
- Fully assembled Orb prototype (shell + display + camera)
- 3D printed alignment jig
- Controlled lighting environment

**Procedure:**
1. Assemble Orb with production optical stack
2. Capture test images at standard distances (0.5m, 1m, 2m, 3m)
3. Run face detection on each image
4. Measure detection confidence

**Pass Criteria:**
| Distance | Face Detection Rate | Min Confidence |
|----------|-------------------|----------------|
| 0.5m | 100% | 0.95 |
| 1.0m | 100% | 0.90 |
| 2.0m | 98% | 0.80 |
| 3.0m | 90% | 0.70 |

#### Test 2.2: Real-World Lighting

**Objective:** Validate across realistic lighting conditions.

| Condition | Lux Range | Test Location |
|-----------|-----------|---------------|
| Direct sunlight | 10,000+ | Window facing |
| Bright office | 500-1000 | Overhead fluorescent |
| Living room evening | 100-300 | Table lamps |
| Movie watching | 10-50 | TV backlight only |
| Night (no lights) | <5 | Ambient only |

**Procedure:**
1. Place Orb in each lighting condition
2. User walks through room at various angles
3. Log face detection rate, latency, confidence
4. Capture sample images for review

**Pass Criteria:**
- Face detection >90% in all conditions except <5 lux
- Latency <100ms from face appearing to detection
- No false positives (objects detected as faces)

#### Test 2.3: Artifact Assessment

**Objective:** Quantify optical artifacts.

| Artifact | Measurement Method | Maximum Acceptable |
|----------|-------------------|-------------------|
| Moiré | Visual inspection of test patterns | "Not noticeable at 0.5m" |
| Diffraction haze | Contrast ratio measurement | Contrast loss <20% |
| Color cast | ColorChecker analysis | ΔE < 5 |
| Flare | Backlit subject test | No visible flare in face region |

---

### Phase 3: Validation at Scale (Week 5-6)

#### Test 3.1: User Study (N=20)

**Objective:** Validate subjective experience.

**Participants:** 20 users, mixed demographics

**Tasks:**
1. Set up Orb in their home
2. Use for 1 week as primary assistant
3. Complete survey

**Survey Questions:**
- "Did Orb recognize you reliably?" (1-5)
- "Did you notice the camera looking at you?" (Y/N)
- "Were there situations where Orb didn't see you?" (describe)
- "Rate overall presence detection" (1-5)

**Pass Criteria:**
- Average reliability rating ≥ 4.0/5.0
- Average overall rating ≥ 4.0/5.0
- <10% report "frequent" detection failures

#### Test 3.2: Long-Term Stability

**Objective:** Verify no degradation over time.

**Procedure:**
1. Run Orb continuously for 30 days
2. Daily: capture standard test image
3. Weekly: run full detection test suite
4. Compare Day 1 vs Day 30

**Pass Criteria:**
- No measurable degradation in detection rate
- No visible display artifacts developing
- Camera module temperature <60°C sustained

---

## Fallback Options

### If Optical Quality is MARGINAL (Detection works but image quality poor)

| Fallback | Implementation | Impact |
|----------|----------------|--------|
| **Reduce resolution** | Use 12MP center crop instead of 50MP | Lower quality video calls |
| **Add NIR illuminators** | Ring of 850nm LEDs around display | Better low-light, adds BOM |
| **Software enhancement** | AI upscaling, denoising | Processing overhead |
| **Limit features** | Presence only, no video calls | Feature reduction |

### If Optical Quality is UNACCEPTABLE (Detection fails)

| Fallback | Implementation | Impact |
|----------|----------------|--------|
| **Transparent pupil area** | Cut hole in display for camera lens | Visible camera, breaks "eye" illusion |
| **Side camera** | Camera at sphere edge, not center | Less natural gaze tracking |
| **External camera** | Camera in base, looking up | Orb becomes "blind" |
| **Remove camera** | Presence via audio/radar only | Major feature loss |

### Decision Tree

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    OPTICAL VALIDATION DECISION TREE                      │
│                                                                          │
│   Transmittance Test                                                    │
│         │                                                                │
│         ├── >12% → PROCEED to Integration Testing                       │
│         │                                                                │
│         ├── 8-12% → PROCEED with NIR enhancement plan                   │
│         │                                                                │
│         └── <8% → STOP. Evaluate transparent pupil fallback             │
│                                                                          │
│   Integration Testing                                                    │
│         │                                                                │
│         ├── Face detection >95% (all lighting) → SHIP                   │
│         │                                                                │
│         ├── Face detection 80-95% → Add NIR illuminators, retest        │
│         │                                                                │
│         └── Face detection <80% → Evaluate side camera fallback         │
│                                                                          │
│   User Study                                                            │
│         │                                                                │
│         ├── Satisfaction ≥4.0/5 → SHIP                                  │
│         │                                                                │
│         ├── Satisfaction 3.0-4.0 → Improve software, retest             │
│         │                                                                │
│         └── Satisfaction <3.0 → Major redesign required                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Light Transmission Enhancement Options

### Option A: NIR Illumination Ring

Add 850nm IR LEDs around the display perimeter.

| Aspect | Detail |
|--------|--------|
| **Components** | 8x VSMY2850G (850nm, 1.2W each) |
| **Placement** | Behind diffuser, around display |
| **BOM Impact** | +$3 |
| **Power Impact** | +0.5W active |
| **Benefit** | +300% effective low-light sensitivity |

```
┌─────────────────────────────────────────┐
│          DISPLAY WITH NIR RING          │
│                                         │
│      ◎ ◎ ◎ ◎ ◎ ◎ ◎ ◎  ← 8x NIR LEDs    │
│    ◎ ┌─────────────────┐ ◎             │
│    ◎ │                 │ ◎             │
│    ◎ │   AMOLED EYE    │ ◎             │
│    ◎ │     DISPLAY     │ ◎             │
│    ◎ │                 │ ◎             │
│    ◎ └─────────────────┘ ◎             │
│      ◎ ◎ ◎ ◎ ◎ ◎ ◎ ◎                  │
│                                         │
└─────────────────────────────────────────┘
```

### Option B: Larger Transparent Pupil Region

Expand the "pupil" area where camera looks through.

| Current | Modified |
|---------|----------|
| 8mm diameter pupil | 12mm diameter pupil |
| ~50mm² clear area | ~113mm² clear area |
| +126% light capture | — |

**Trade-off:** Larger pupil may look less natural.

### Option C: Higher Sensitivity Lens

Replace f/1.9 lens with faster optics.

| Lens | Light Capture | Cost |
|------|---------------|------|
| f/1.9 (current) | 1.0x | Included |
| f/1.5 | 1.6x | +$15 |
| f/1.2 | 2.5x | +$40 |

**Trade-off:** Faster lens = shallower depth of field, larger module.

---

## Industry Precedents

### Samsung Galaxy Z Fold (Under-Display Camera)

| Metric | Samsung UDC | Orb Target |
|--------|-------------|------------|
| Resolution | 4MP | 50MP (use case different) |
| Quality | "Acceptable for selfies" | Face detection sufficient |
| User Reception | Mixed | N/A |
| Light Transmission | ~10% | 10-15% |

**Lesson:** Samsung reduced resolution to compensate for light loss. We can use full 50MP for face detection (downsample and average).

### ZTE Axon 40 Ultra (Under-Display Camera)

| Metric | ZTE | Notes |
|--------|-----|-------|
| Quality | Improved over previous gen | AI processing helps |
| Visible in use | Slight circle visible | Orb's "pupil" hides this naturally |

**Lesson:** The "pupil" in Orb's eye design naturally explains any visible camera region.

### Oppo Find X3 Pro (Microscope Camera)

**Relevant:** High-resolution sensor in constrained optical path.

**Lesson:** Computational photography can enhance physically limited systems.

---

## Prototype Schedule

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| 1 | Acquire test materials | AMOLED samples, IMX989 module |
| 2 | Bench testing complete | Transmittance data |
| 3 | Integration prototype built | First assembled unit |
| 4 | Integration testing complete | Detection metrics |
| 5 | User study begins | 20 units deployed |
| 6 | User study complete | Survey results |
| 7 | GO/NO-GO decision | Final optical design |

---

## GO/NO-GO Criteria

### GREEN (Proceed to Production)

- [ ] Transmittance ≥10%
- [ ] Face detection ≥95% at 500+ lux
- [ ] Face detection ≥85% at 50 lux
- [ ] User satisfaction ≥4.0/5.0
- [ ] No user-visible artifacts

### YELLOW (Proceed with Enhancement)

- [ ] Transmittance 8-10%
- [ ] Face detection 80-95% at 500+ lux
- [ ] Requires NIR illumination addition
- [ ] User satisfaction 3.5-4.0/5.0

### RED (Major Redesign)

- [ ] Transmittance <8%
- [ ] Face detection <80% at 500+ lux
- [ ] User satisfaction <3.5/5.0
- [ ] Fallback to transparent pupil or side camera

---

## Conclusion

The camera-behind-AMOLED design is **technically risky but achievable** based on industry precedents. The key insight is that Orb doesn't need selfie-quality images — it needs **reliable face detection**.

### Success Factors

1. **Large sensor (IMX989)** — Maximum light capture
2. **Natural pupil design** — Camera visible region is expected
3. **Computational enhancement** — AI can compensate for optical limits
4. **NIR fallback** — Low-light solution exists if needed

### Risk Mitigation

This validation plan ensures we know the optical limitations before production. If validation fails, we have clear fallback options that preserve the core experience (levitation + eye + presence).

**The eye that sees you — even through itself.**

---

*"Light finds a way."* — 鏡
