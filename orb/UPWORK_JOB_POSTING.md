# Upwork Job Posting — Kagami Orb

## Public Resources

| Resource | URL |
|----------|-----|
| **Pitch Page** | https://storage.googleapis.com/kagami-media-public/orb/index.html |
| **Full Spec** | https://storage.googleapis.com/kagami-media-public/orb/README.md |
| **Validation Plan** | https://storage.googleapis.com/kagami-media-public/orb/VALIDATION_PLAN.md |
| **Bill of Materials** | https://storage.googleapis.com/kagami-media-public/orb/hardware/kagami_orb_bom.csv |

---

## Job Title (RECOMMENDED)

> **Build a Floating Voice Assistant — Maglev + Wireless Charging + QCS6490 Prototype**

### Alternative Titles:
- QCS6490 Voice Assistant with Magnetic Levitation & Wireless Charging — Full Prototype Build
- Hardware Engineer for IoT Voice Assistant Prototype — QCS6490, Maglev, Resonant Wireless Charging, 4-Mic Array

---

## Job Description

# 🔮 Build a Floating Voice Assistant Prototype

## Overview

I'm looking for an experienced hardware engineer to build a fully functional prototype of a custom voice assistant that **floats using magnetic levitation** and charges wirelessly. This is a unique, high-end smart home device with complete specifications already developed.

**This is a real build project, not just consulting.** I need someone who can source components, assemble hardware, write firmware, and ship me a working prototype.

## What You're Building

**The "Kagami Orb"** — an 85mm spherical voice assistant that:
- Floats 18-25mm above a magnetic levitation base
- Charges wirelessly via **custom resonant coils** (NOT standard Qi—see Technical Notes)
- Has 4-microphone far-field voice input
- **Chrome speaker at center** — 28mm driver with LED reflections on metallic surface
- Functions as a **Bluetooth A2DP speaker**
- Streams audio input to my smart home API
- Features an infinity mirror LED ring effect (16 LEDs reflecting infinitely)
- Runs on QCS6490 with Hailo-10H NPU
- Connects to my existing smart home API
- **Two dock options:** Indoor (walnut base) + Outdoor (with weatherproof canopy)

Think: **Amazon Echo meets levitating desk globe meets infinity mirror art piece**

**Open & Hackable:** All firmware is open source. GPIO pins exposed for expansion. Standard I2C/SPI interfaces. The orb is designed to be modified, not locked down.

🌐 **See the interactive pitch page:** https://storage.googleapis.com/kagami-media-public/orb/index.html

## Deliverables

1. **Working Prototype** — Fully assembled and tested orb
2. **Indoor Dock** — Walnut base with maglev + resonant TX
3. **Outdoor Dock** — Same base with weatherproof canopy (IP65)
4. **Floating Orb** — All electronics, battery, chrome speaker, infinity mirror shell
5. **Firmware** — Boot, WiFi, voice pipeline, LED control (open source)
6. **Documentation** — Assembly photos, wiring diagrams, GPIO pinout, test results
7. **Shipped to Seattle, WA**

## Technical Specifications

### Orb (Floating Unit)
| Component | Specification |
|-----------|---------------|
| Compute | QCS6490 (8GB RAM, 2.7GHz) |
| AI Accelerator | Hailo-10H NPU |
| Microphones | sensiBel SBM100B 4-Mic Array (I2S) |
| LEDs | HD108 RGBW Ring (16 LEDs) |
| **Speaker** | **28mm chrome driver + MAX98357A Class-D amp** |
| **Bluetooth** | **A2DP sink for speaker mode** |
| Battery | 2,200mAh Li-Po with BMS |
| **Wireless Power RX** | **Custom 70mm resonant coil @ 140kHz** |
| Shell | 85mm clear acrylic sphere with mirror film |
| Target Weight | <400g |
| **Expansion** | **GPIO header exposed, I2C/SPI accessible** |

### Indoor Dock (Base Station)
| Component | Specification |
|-----------|---------------|
| Maglev Module | 500g capacity electromagnetic levitation |
| **Wireless Power TX** | **Custom 70mm resonant coil @ 140kHz (20W)** |
| **Ferrite Shielding** | **Mn-Zn between coils and maglev magnets** |
| Power Input | 24V 3A DC |
| Enclosure | CNC walnut, 180mm × 180mm × 45mm |
| Finish | Hand-rubbed tung oil |

### Outdoor Dock (With Canopy)
| Component | Specification |
|-----------|---------------|
| Base | Same as indoor dock |
| **Canopy** | **Powder-coated aluminum or brushed copper** |
| Diameter | 300mm (covers full orb trajectory) |
| Clearance | 250mm above base |
| Weather Rating | **IP65 (canopy assembly)** |
| Drainage | 5° slope, water channels to edges |

### ⚠️ CRITICAL TECHNICAL NOTE: Wireless Charging

**Standard Qi EPP will NOT work** at 18-25mm gap with maglev magnets:
- Gap exceeds Qi spec (8mm max)
- N52 magnets trigger FOD (Foreign Object Detection) false alarms
- Result: 0W power transfer

**Solution: Custom resonant coupling**
- 70mm diameter Litz wire coils (vs 40mm standard Qi)
- Tuned to ~140kHz
- Achieves k ≈ 0.82 coupling coefficient
- ~75% efficiency (20W TX → 15W RX)
- Ferrite shielding isolates from maglev magnets

**If you've done resonant wireless power transfer before, call that out in your proposal!**

### Software Requirements
| Function | Implementation |
|----------|----------------|
| Boot | Linux (Yocto), auto-start |
| WiFi | WPA2 Enterprise support |
| Wake Word | Local detection (Porcupine or similar) |
| Voice Capture | 16kHz, 16-bit, beamformed |
| LED Control | SPI/DMA, smooth animations |
| API Client | HTTP/WebSocket to my backend |

## What I'm Providing

✅ **Complete specifications** — 900+ line technical document
✅ **Bill of Materials** — Every component with sources
✅ **CAD guidance** — Dimensions and tolerances
✅ **API documentation** — For smart home integration
✅ **Budget for components** — I'll reimburse or pay upfront
✅ **3D printing capability** — I have a Formlabs Form 4 if you need parts printed
✅ **Laser cutting capability** — I have a Glowforge Pro for enclosure parts

## Required Experience

**Must have demonstrated experience with:**
- [ ] Qualcomm QCS6490 / embedded SoC development (show me a project)
- [ ] Power electronics — battery management, charging circuits
- [ ] Audio systems — microphone arrays, DSP, echo cancellation
- [ ] LED control — addressable LEDs, animations
- [ ] Embedded Linux — systemd, device trees, drivers
- [ ] 3D printing / enclosure design

**Nice to have:**
- [ ] Magnetic levitation projects
- [ ] **Resonant wireless power transfer** (strongly preferred over standard Qi experience)
- [ ] Voice assistant development (Mycroft, Rhasspy, etc.)
- [ ] Smart home integration (Home Assistant, MQTT)
- [ ] Bluetooth audio (A2DP sink configuration)

## Project Phases

### Phase 1: Critical Path Validation ($700-1000)
- **Test custom resonant power delivery** through 18-25mm air gap (NOT standard Qi)
- Calibrate FOD to exclude maglev magnet signature
- Test maglev stability at target weight
- Verify no EMI between resonant coils and WiFi
- **Deliverable:** Test report with photos/video, go/no-go decision

### Phase 2: Electronics Integration ($800-1200)
- Assemble QCS6490 + Hailo-10H + sensiBel SBM100B + LEDs
- Build power management (battery + resonant RX + BMS)
- Configure Bluetooth A2DP sink
- Bench test all functions
- **Deliverable:** Working electronics stack, firmware basics

### Phase 3: Enclosure & Assembly ($600-1000)
- Fabricate or source sphere shell
- Build base station enclosure
- Integrate electronics into enclosures
- **Deliverable:** Fully assembled prototype

### Phase 4: Software & Testing ($400-800)
- Voice pipeline (wake word → capture → API streaming)
- LED animations (colony colors, breathing, reactions)
- Bluetooth speaker pairing and playback
- 2-hour thermal soak test
- Multi-day stability testing
- **Deliverable:** Working prototype with documented test results

### Phase 5: Polish & Ship ($200-400)
- Final assembly and QA
- Documentation package
- Careful packaging and shipping
- **Deliverable:** Prototype arrives in Seattle working

## Budget

**Total Budget: $3,700 - $6,400 USD**

This includes:
- Your labor (hourly or fixed price, your preference)
- Component costs (I can pay upfront or reimburse with receipts)
- Shipping to Seattle, WA

I'm flexible on structure — we can do:
- Fixed price per phase (milestone payments)
- Hourly with weekly cap
- Hybrid (fixed for hardware, hourly for debugging)

## Timeline

**Target: 6-8 weeks to working prototype**

| Week | Phase |
|------|-------|
| 1-2 | Phase 1: Validation |
| 2-3 | Phase 2: Electronics |
| 3-5 | Phase 3: Enclosure |
| 5-7 | Phase 4: Software |
| 7-8 | Phase 5: Polish & Ship |

I understand hardware projects have unknowns. I'm flexible on timeline if you communicate proactively.

## How to Apply

**Please include in your proposal:**

1. **Relevant projects** — Links to 2-3 hardware projects you've built (photos/videos preferred)
2. **Technical assessment** — What do you see as the biggest risk in this project?
3. **Your approach** — How would you tackle Phase 1 validation?
4. **Rate/estimate** — Hourly rate or fixed price estimate
5. **Availability** — When can you start? Hours/week dedicated?

**Bonus points if you've worked with:**
- Magnetic levitation
- Wireless charging circuits
- Voice assistant hardware
- Qualcomm QCS6490 specifically

## About Me

I'm a software engineer in Seattle building a custom smart home system. I have extensive software experience but limited hardware skills — that's why I need you. I'm technical enough to review your work and provide useful feedback, but I need someone who can actually build the physical device.

I have a home workshop with:
- Formlabs Form 4 (resin 3D printer)
- Glowforge Pro (laser cutter)
- Basic electronics tools

I can print/cut parts if that helps reduce your workload.

## Questions?

Happy to answer questions before you apply. I have:
- Complete technical specification (900+ lines)
- Bill of Materials with sources
- Validation test plan
- Risk assessment and pivot options

Looking forward to working with a skilled hardware engineer to bring this floating mirror to life! 🪞

---

## Upwork Settings

| Setting | Value |
|---------|-------|
| **Category** | Engineering & Architecture > Electrical Engineering |
| **Subcategory** | Embedded Systems, PCB Design, Hardware Prototyping |
| **Experience Level** | Expert |
| **Budget Type** | Fixed Price: $3,700 - $6,400 OR Hourly: $40-80/hr |
| **Project Length** | 1-3 months |

### Skills to Tag
- Qualcomm QCS6490
- Embedded Systems
- Electronics
- PCB Design
- IoT
- Python
- Linux
- Hardware Prototyping
- 3D Printing
- Audio Engineering
- Wireless Power Transfer
- Bluetooth

### Screening Questions
1. "Have you built a project with Qualcomm QCS6490 or similar embedded SoC? Please share a link or photo."
2. "Have you worked with wireless power transfer (Qi or resonant)? Describe briefly."
3. "What's your experience with audio/microphone systems?"
4. "Do you understand why standard Qi won't work at 18-25mm gap with maglev magnets?"
5. "Are you able to ship a completed prototype to Seattle, WA, USA?"

---

## Attachments to Include

When posting, include these **public URLs** in the job description:

| Document | Public URL |
|----------|------------|
| Full Spec | https://storage.googleapis.com/kagami-media-public/orb/README.md |
| Bill of Materials | https://storage.googleapis.com/kagami-media-public/orb/hardware/kagami_orb_bom.csv |
| Validation Plan | https://storage.googleapis.com/kagami-media-public/orb/VALIDATION_PLAN.md |
| Pitch Page | https://storage.googleapis.com/kagami-media-public/orb/index.html |

---

## Red Flags to Watch For

### 🚩 AVOID applicants who:
- Have no hardware projects in their portfolio (software only)
- Can't explain the biggest risk (shows they didn't read the spec)
- Quote significantly below $2,500 (likely underestimating)
- Have no reviews/history on hardware projects
- Are vague about their approach to Phase 1
- Can't ship internationally (if they're overseas)

### ✅ PREFER applicants who:
- Show photos/videos of past hardware builds
- Ask smart technical questions before bidding
- **Identify that standard Qi won't work** and propose resonant solution
- Understand coupling coefficient (k) and coil sizing
- Have experience with voice/audio systems
- Propose a validation-first approach
- Are in a timezone compatible with Seattle (PST)

---

## Follow-Up Templates

### Initial Response to Promising Candidate

```
Hi [Name],

Thanks for your interest in the Kagami Orb project! Your experience with [specific thing they mentioned] looks relevant.

Before we proceed, I'd like to share the full technical specification. Could you review it and let me know:

1. What do you see as the top 3 risks?
2. How would you approach the resonant-through-maglev-gap validation?
3. Any concerns about the timeline or budget?

I've attached the complete spec (README.md) and Bill of Materials.

Looking forward to your thoughts!
Tim
```

### Interview Questions

1. "Standard Qi EPP won't work at 18-25mm with maglev magnets. How would you design the resonant charging system?"
2. "What coupling coefficient would you expect with 70mm coils at 18-25mm gap? How does coil diameter affect this?"
3. "The sensiBel SBM100B 4-Mic needs echo cancellation when the speaker is playing. How would you approach that?"
4. "If the thermal tests show the sphere gets too hot with charging, what are your fallback options?"
5. "Have you shipped hardware to a client before? How do you package delicate electronics?"
6. "What's your communication style? How often would you update me on progress?"

---

```
h(x) ≥ 0. Always.
鏡
```
