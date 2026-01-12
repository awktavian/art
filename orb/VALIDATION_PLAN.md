# Kagami Orb — Validation Test Plan

## Why This Document Exists

**The design is 100% complete. Validation is 0% complete.**

This document defines the tests that must pass before the Kagami Orb is considered production-ready. Until these tests pass, we're at 10% of done.

---

## Phase 0: Component Acquisition

**Budget: $497**

| # | Item | Cost | Source | Lead Time |
|---|------|------|--------|-----------|
| 1 | ZT-HX500 Maglev Module (500g) | $180 | AliExpress | 7-14 days |
| 2 | **80mm Resonant TX Coil** (Litz wire, 15 turns) | $25 | Würth Elektronik | 5-7 days |
| 3 | **80mm Resonant RX Coil** (Litz wire, 20 turns) | $25 | Würth Elektronik | 5-7 days |
| 4 | **Resonant TX Driver** (bq500215) | $18 | TI/DigiKey | 3-5 days |
| 5 | **Resonant RX Controller** (bq51025) | $12 | TI/DigiKey | 3-5 days |
| 6 | **Ferrite Shields** (2× 90mm Mn-Zn, 0.8mm) | $30 | Fair-Rite | 5-7 days |
| 7 | QCS6490 (8GB) + IO Board | $80 | Qualcomm | 3-5 days |
| 8 | sensiBel SBM100B Mic Array | $35 | sensiBel | 5-7 days |
| 9 | Hailo-10H NPU | $60 | Hailo | 3-5 days |
| 10 | HD108 RGBW Ring (16 LED) | $12 | Adafruit | 3-5 days |
| 11 | 85mm Acrylic Hemispheres | $50 | TAP Plastics | 5-7 days |
| 12 | Heatsinks, thermal pads, misc | $30 | DigiKey | 3-5 days |
| 13 | Standard Qi 15W EPP pair (for baseline test only) | $50 | AliExpress | 7-14 days |

**Budget: ~$600** (increased for custom resonant components)

**Order all on Day 0.**

---

## Phase 1: Critical Path Validation (Week 1-2)

### TEST 1.0: Standard Qi Baseline (EXPECTED TO FAIL)

**Purpose:** Document why standard Qi EPP doesn't work, establishing baseline for comparison.

**Setup:**
1. Place standard Qi EPP TX coil on flat surface
2. Place maglev magnet ring between TX and RX
3. 3D print spacers: 10mm, 15mm
4. Connect RX to power meter

**Procedure:**
1. Test without magnets at 15mm gap:
   - Measure efficiency
   - Record if FOD triggers
2. Test with N52 magnet ring present:
   - Record FOD false alarm rate
   - Measure if any power transfers
3. Document failure modes

**Expected Results (TO DOCUMENT):**
- [ ] ❌ FOD false alarm rate: DOCUMENT (expect ~100%)
- [ ] ❌ Efficiency at 15mm: DOCUMENT (expect <50%)
- [ ] ❌ Power transfer with magnets: DOCUMENT (expect 0W due to FOD)

**Purpose:** This test PROVES why custom resonant is required. Document for contractor.

---

### TEST 1.1: Custom Resonant Power Through Maglev Gap

**Purpose:** Verify custom resonant coils deliver power through the levitation gap.

**Setup:**
1. Place **80mm resonant TX coil** (Litz wire) on flat surface
2. Install **ferrite shield** (0.8mm Mn-Zn) between TX coil and maglev magnets
3. 3D print spacers: 10mm, 12mm, 15mm, 18mm, 20mm
4. Place **80mm resonant RX coil** on spacer
5. Tune TX and RX to ~140kHz with capacitors
6. Connect TX to 24V 3A supply via bq500215 driver
7. Connect RX to bq51025 controller → power meter

**Procedure:**
1. For each gap distance:
   - Measure input power (TX)
   - Measure output power (RX)
   - Calculate efficiency: η = P_out / P_in
   - Record alignment tolerance (move RX ±5mm, ±10mm)
2. Record thermal: TX coil temp after 10 min continuous
3. Record EMI: WiFi signal strength at 1m
4. Record coupling coefficient measurement (if equipment available)

**Pass Criteria:**
- [ ] ≥12W delivered at 15mm gap (need 15W headroom for charging)
- [ ] ≥70% efficiency at 15mm (expect ~75% with 80mm coils)
- [ ] TX coil temp <55°C
- [ ] RX coil temp <50°C
- [ ] WiFi signal >-65dBm
- [ ] Alignment tolerance ±5mm with <10% efficiency drop

**Fail Pivots:**
- If efficiency <65%: Increase coil diameter to 90mm
- If still <65%: Reduce gap to 12mm
- If 12mm fails: Use wired power through base

---

### TEST 1.1A: FOD Calibration with Maglev Magnets

**Purpose:** Calibrate FOD baseline to eliminate false alarms from permanent magnets.

**Setup:**
1. Resonant TX with FOD sensing enabled
2. N52 magnet ring in final position
3. No foreign objects present

**Procedure:**
1. Power on TX without magnets → record baseline FOD reading
2. Install N52 magnet ring → record FOD reading
3. Calibrate FOD threshold to exclude magnet signature
4. Test FOD detection with:
   - Metal coin in gap: must still detect
   - Keys near coil: must still detect
5. Run 100 power cycles → count false alarms

**Pass Criteria:**
- [ ] FOD false alarm rate <1% after calibration
- [ ] Metal coin detection >95%
- [ ] Keys detection >90%
- [ ] Calibration stable across 100 power cycles

**Fail Pivots:**
- If false alarm >5%: Disable FOD entirely (thermal protection only)
- If metal detection <80%: Accept reduced FOD sensitivity

---

### TEST 1.2: Maglev Stability at Weight

**Purpose:** Verify the maglev module can stably hold our target weight.

**Setup:**
1. Mount maglev base on stable surface
2. Prepare test weights: 300g, 350g, 400g, 450g
3. Mount accelerometer on floating platform
4. Setup video recording for visual analysis

**Procedure:**
1. For each weight:
   - Place weight on float
   - Wait 30 seconds for stabilization
   - Measure vertical position (should be 15mm)
   - Measure oscillation amplitude over 60 seconds
   - Bump test: Push 1cm off center, measure recovery time
2. Record power consumption at each weight
3. Record coil temperature after 10 min

**Pass Criteria:**
- [ ] Stable float at 400g
- [ ] Vertical oscillation <2mm peak-to-peak
- [ ] Horizontal recovery <3 seconds
- [ ] Power consumption <20W
- [ ] Coil temp <50°C

**Fail Pivots:**
- If unstable at 400g: Reduce target weight to 350g
- If oscillation >2mm: Add damping (ferrofluid?)
- If temp too high: Add cooling to base

---

### TEST 1.3: Combined Maglev + Resonant + Electronics

**Purpose:** Verify all systems work together without interference.

**Setup:**
1. Maglev module powered
2. Resonant TX on maglev base (with ferrite shield)
3. 350g test mass with Resonant RX attached
4. WiFi device nearby
5. Audio recording equipment

**Procedure:**
1. Float test mass at 15mm
2. Enable resonant charging (20W TX → 15W RX)
3. Measure:
   - Float stability with resonant charging active
   - Resonant efficiency with maglev active
   - WiFi signal strength at 1m, 2m, 3m
   - Audio recording for coil whine (30 second sample)
4. Run for 30 minutes, check for thermal issues

**Pass Criteria:**
- [ ] No stability degradation with resonant charging active
- [ ] Resonant efficiency matches TEST 1.1 results (±5%)
- [ ] WiFi signal >-65dBm at 2m
- [ ] Audible noise <35dB at 30cm
- [ ] No thermal runaway

**Fail Pivots:**
- If EMI: Add shielding between maglev and WiFi antenna
- If noise: Accept it OR use different PWM frequency
- If thermal: Reduce duty cycle OR add cooling

---

## Phase 2: Thermal Validation (Week 2-3)

### TEST 2.1: Electronics Heat Generation

**Purpose:** Measure actual power consumption and heat output.

**Setup:**
1. QCS6490 mounted on heat sink
2. Hailo-10H attached
3. WiFi adapter active
4. Thermocouples on: QCS6490 SoC, Hailo-10H, WiFi
5. Power meter inline

**Procedure:**
1. Boot system, record idle power
2. Run CPU stress test, record power + temps
3. Run AI inference loop on Hailo-10H, record power + temps
4. Run WiFi throughput test, record power + temps
5. Run all simultaneously for 30 minutes

**Pass Criteria:**
- [ ] Idle power <5W
- [ ] Max power <15W
- [ ] QCS6490 temp <80°C (throttle point is 85°C)
- [ ] Hailo-10H temp <70°C
- [ ] No throttling during combined test

**Fail Pivots:**
- If power >15W: Reduce QCS6490 clock OR duty cycle AI
- If throttling: Better heatsink OR active cooling

---

### TEST 2.2: Thermal in Enclosed Shell

**Purpose:** Verify temperatures are safe in sealed sphere.

**Setup:**
1. Mount electronics in closed hemisphere
2. Thermocouples: Internal (near QCS6490), External (sphere surface)
3. IR thermometer for surface mapping
4. 25°C ambient temperature

**Procedure:**
1. Seal electronics in hemisphere
2. Run stress test (same as TEST 2.1)
3. Record temps every 5 minutes for 60 minutes
4. Note steady-state temps
5. Map external surface temps with IR

**Pass Criteria:**
- [ ] Internal temp <70°C at steady state
- [ ] External surface <50°C (safe to touch)
- [ ] No hot spots >55°C on surface
- [ ] No throttling during test

**Fail Pivots:**
- If surface >50°C: Add vents (TEST 2.3)
- If internal >70°C: Larger heatsink + vents
- If still failing: Use half-sphere design

---

### TEST 2.3: Thermal with Vents

**Purpose:** Measure improvement from chimney-effect vents.

**Setup:**
1. Drill 6mm holes at top and bottom of hemisphere
2. Add dust filter mesh
3. Same sensor setup as TEST 2.2

**Procedure:**
1. Repeat TEST 2.2 procedure
2. Compare temps to sealed results
3. Measure airflow with anemometer (optional)

**Pass Criteria:**
- [ ] ≥10°C reduction from sealed
- [ ] Surface temp <45°C
- [ ] Internal temp <65°C

**Documentation:**
- Record optimal vent size and placement
- Photo document the solution

---

### TEST 2.4: Extended Thermal Soak (2 Hours)

**Purpose:** Verify system stability under extended continuous operation with charging.

**Setup:**
1. Complete orb assembly floating on base
2. Resonant charging active (15W continuous)
3. Electronics at mixed load (simulating real use)
4. Thermocouples on: QCS6490 SoC, Hailo-10H, RX coil, shell surface
5. 25°C ambient room temperature

**Procedure:**
1. Run continuous for 2 hours:
   - 50% idle (LED breathing)
   - 30% voice processing
   - 20% AI inference on Hailo-10H
2. Record temperatures every 10 minutes
3. Note any thermal throttling events
4. Check for thermal runaway (temps continuously rising)

**Pass Criteria:**
- [ ] QCS6490 temp stable <75°C (not continuously rising)
- [ ] Hailo-10H temp stable <65°C
- [ ] RX coil temp stable <55°C
- [ ] Shell surface <48°C at steady state
- [ ] No thermal throttling
- [ ] No thermal runaway (temps plateau by t=60min)

**Fail Pivots:**
- If runaway: Improve thermal path OR reduce charging power
- If throttling: Larger heatsink OR active cooling
- If shell >50°C: Add vents OR reduce LED brightness

---

## Phase 3: Voice, Audio & UX Validation (Week 3-4)

### TEST 3.1: Far-Field Voice Recognition

**Purpose:** Verify wake word detection at distance and angle.

**Setup:**
1. sensiBel SBM100B mounted in test sphere
2. Speakers at fixed distances: 1m, 2m, 3m, 4m
3. Test script with 100 wake word utterances
4. Multiple speakers (male/female/varied accent)

**Procedure:**
1. For each distance:
   - Play 100 wake words from speaker
   - Record success/fail for each
   - Calculate success rate
2. Repeat at angles: 0°, 45°, 90°, 135°, 180°
3. Test in different rooms (varying acoustics)

**Pass Criteria:**
- [ ] ≥95% at 1m
- [ ] ≥90% at 2m
- [ ] ≥85% at 3m
- [ ] ≥80% at all angles at 2m

**Fail Pivots:**
- If <85% at 3m: Beamforming tuning
- If angle-dependent: Adjust mic array placement
- If still failing: External mic pod option

---

### TEST 3.2: Echo Cancellation

**Purpose:** Verify voice works while speaker is playing.

**Setup:**
1. Full audio system: sensiBel SBM100B + speaker + amp
2. Test music tracks at defined volumes
3. Wake word + command test script

**Procedure:**
1. Play music at 25% volume
2. Speak 50 commands, record success rate
3. Repeat at 50%, 75%, 100% volume
4. Test with various music genres (bass-heavy, vocal, etc.)

**Pass Criteria:**
- [ ] ≥95% at 25% volume
- [ ] ≥85% at 50% volume
- [ ] ≥70% at 75% volume
- [ ] Note acceptable max volume

**Fail Pivots:**
- If AEC fails: Tune AEC parameters
- If still failing: Reduce speaker max volume
- If hardware limitation: Use different DSP

---

### TEST 3.3: Background Noise

**Purpose:** Verify voice works in typical home environments.

**Setup:**
1. Record or simulate home noises:
   - Quiet room (<30dB)
   - TV at conversation level (~50dB)
   - HVAC running (~40dB)
   - Multiple people talking (~55dB)

**Procedure:**
1. For each noise condition:
   - Play background noise
   - Speak 50 wake words + commands
   - Record success rate
2. Measure noise suppression effect

**Pass Criteria:**
- [ ] ≥95% in quiet room
- [ ] ≥85% with TV/HVAC
- [ ] ≥75% with conversation

---

### TEST 3.4: Bluetooth A2DP Speaker Mode

**Purpose:** Verify orb functions as a standard Bluetooth speaker.

**Setup:**
1. Orb with Bluetooth enabled
2. Test phone/laptop with A2DP source
3. Audio analyzer for quality measurement
4. dB meter for volume testing

**Procedure:**
1. Pair test device with orb
2. Play test tones: 100Hz, 1kHz, 10kHz
3. Measure frequency response
4. Play music tracks, subjective quality assessment
5. Test reconnection after disconnect
6. Test range: 1m, 3m, 5m, 10m

**Pass Criteria:**
- [ ] Pairing completes in <10 seconds
- [ ] Audio plays within 2 seconds of play command
- [ ] Frequency response: 200Hz-15kHz (±6dB)
- [ ] Subjective quality: "acceptable for small speaker"
- [ ] Range: functional at 5m, degraded at 10m
- [ ] Reconnection <5 seconds

**Fail Pivots:**
- If pairing fails: Check Bluetooth stack configuration
- If quality poor: Adjust DSP/EQ settings
- If range poor: Verify antenna placement

---

### TEST 3.5: Audio Input Streaming to Kagami API

**Purpose:** Verify microphone audio streams reliably to Kagami API.

**Setup:**
1. Orb connected to WiFi
2. Kagami API running with WebSocket endpoint
3. Audio capture on API side
4. Test audio source (calibrated speaker)

**Procedure:**
1. Play 1kHz tone at 1m → verify capture on API
2. Play speech samples → verify transcription accuracy
3. Measure latency: time from sound to API receipt
4. Test continuous streaming for 10 minutes
5. Test stream recovery after WiFi dropout

**Pass Criteria:**
- [ ] 1kHz tone captured cleanly (no distortion)
- [ ] Speech transcription accuracy ≥95% at 2m
- [ ] Latency <300ms end-to-end
- [ ] No stream drops in 10-minute continuous test
- [ ] Stream recovers <5 seconds after WiFi restored

**Fail Pivots:**
- If latency >500ms: Reduce Opus buffer size
- If drops: Implement reconnection logic
- If quality poor: Adjust sample rate/bitrate

---

## Phase 4: Integration & Multi-Base (Week 4-6)

### TEST 4.1: Full System Integration

**Purpose:** Verify everything works together in final form.

**Setup:**
1. Complete orb assembly
2. Complete base station
3. Kagami API running
4. All integrations enabled

**Procedure:**
1. 8-hour continuous operation test
2. Perform all functions:
   - Voice commands every 30 min
   - LED animations
   - WiFi connectivity check
   - API response time
3. Monitor temps throughout
4. Monitor battery state

**Pass Criteria:**
- [ ] All functions work for 8 hours
- [ ] No thermal throttling
- [ ] No connectivity drops
- [ ] No crashes/reboots

---

### TEST 4.2: Multi-Base Handoff

**Purpose:** Verify seamless transition between bases.

**Setup:**
1. Two complete base stations, 10m apart
2. Orb with full battery
3. Stopwatch

**Procedure:**
1. Start with orb on Base 1
2. Pick up orb (record "lift" event)
3. Walk to Base 2 (15 seconds)
4. Place orb on Base 2 (record "land" event)
5. Measure:
   - Time for Base 2 to recognize orb
   - Time for API to update location
   - Time for orb to reconnect to WiFi
6. Repeat 10 times

**Pass Criteria:**
- [ ] Base recognition <1 second
- [ ] API update <2 seconds
- [ ] WiFi reconnect <3 seconds
- [ ] 100% success rate over 10 trials

---

### TEST 4.3: Battery Life

**Purpose:** Verify portable operation time.

**Setup:**
1. Orb fully charged
2. Remove from base
3. Usage simulation script

**Procedure:**
1. Run simulation:
   - 50% idle (LED slow breathing)
   - 30% listening (active mic)
   - 20% responding (AI + speaker)
2. Measure time until 10% battery
3. Measure time until shutdown

**Pass Criteria:**
- [ ] ≥4 hours to 10% with typical use
- [ ] ≥5 hours to shutdown
- [ ] Low battery warning at 20%
- [ ] Graceful shutdown at 5%

---

## Phase 5: Crystal Polish (Week 6-8)

### Delight Checklist

- [ ] First-reveal packaging designed
- [ ] First-float moment scripted
- [ ] First-conversation personality defined
- [ ] Easter eggs implemented

### Elegance Checklist

- [ ] Seams invisible in final assembly
- [ ] LED patterns reviewed (not garish)
- [ ] Sound design approved
- [ ] Packaging sustainable

### Care Checklist

- [ ] Soft landing tested 100 times
- [ ] Thermal warning voice recorded
- [ ] Battery warning implemented
- [ ] Error messages are patient

### Character Checklist

- [ ] Idle rotation implemented
- [ ] Listening height pulse implemented
- [ ] Time-of-day moods defined
- [ ] Base preference learning works

### Art Checklist

- [ ] Product photography complete
- [ ] Looks good in various decors
- [ ] Patina development plan (brass)
- [ ] Infinity effect validated as "mesmerizing"

---

## Kill Criteria

**If these cannot be achieved, pivot the design:**

| Requirement | Minimum | Pivot If Fail |
|-------------|---------|---------------|
| **Resonant efficiency** | **70%** | **Larger coils (90mm) OR smaller gap (12mm)** |
| **FOD calibration** | **<5% false alarm** | **Disable FOD, use thermal protection only** |
| Maglev stability | ±2mm | Reduce weight OR larger module |
| Surface temp | <48°C | Add vents OR half-sphere |
| **RX coil temp** | **<55°C** | **Better thermal path OR reduce charge rate** |
| Voice at 3m | 85% | External mic pod |
| Battery life | 3 hours | Smaller battery, always on base |
| **Bluetooth range** | **5m** | **Check antenna, or accept limitation** |
| **Audio stream latency** | **<500ms** | **Reduce buffer size OR accept limitation** |

**Note:** Standard Qi EPP is NOT a valid fallback—it will fail at 15mm with maglev magnets.

---

## Sign-Off

| Phase | Date | Signed | Notes |
|-------|------|--------|-------|
| Phase 0 | | | Components ordered |
| Phase 1 | | | Critical path validated |
| Phase 2 | | | Thermal validated |
| Phase 3 | | | Voice validated |
| Phase 4 | | | Integration complete |
| Phase 5 | | | 110/100 achieved |

---

```
h(x) ≥ 0. Always.

Design is 100%. Validation is 0%.
Until we BUILD, we're at 10%.

鏡
```
