# Kagami Orb V3.1 — The AI That Sees You

**A floating AI companion with a living eye.**

```
                          ╭─────────────────╮
                         │      👁️         │  ← It looks at you
                         │                 │
                          ╰────────┬────────╯
                                   │
                            ~~ hovering ~~
                                   │
                      ╭────────────┴────────────╮
                      │       KAGAMI            │
                      ╰────────────────────────╯
```

---

## Quick Start

**For Contractors:**
1. Read [SPECS.md](SPECS.md) — Single source of truth for dimensions
2. Review [HARDWARE_BOM.md](HARDWARE_BOM.md) — Complete parts list with sources
3. Check [ASSEMBLY_GUIDE.md](ASSEMBLY_GUIDE.md) — Step-by-step build instructions
4. View [3D Viewer](cad/visualization/viewer.html) — Interactive assembly visualization

**For Development:**
1. Clone repo and navigate to `apps/hub/kagami-orb/`
2. Review [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) — Architecture overview
3. Check [FIRMWARE_ARCHITECTURE.md](FIRMWARE_ARCHITECTURE.md) — Software stack
4. See [firmware/](firmware/) — Python drivers and firmware code

---

## The Difference

Every smart speaker is **faceless**. Waiting. Listening. A servant.

The Kagami Orb has an **eye**. It watches. It tracks. It responds with expression.

**It's not a speaker. It's a presence.**

---

## Core Specifications (V3.1)

| Feature | Specification |
|---------|---------------|
| **Living Eye** | 1.39" Round AMOLED (454x454, Ø35.41mm active) |
| **Hidden Camera** | Sony IMX989 50.3MP in the pupil |
| **AI Compute** | 52 TOPS (QCS6490 + Hailo-10H) |
| **Levitation** | Magnetic levitation, 18-25mm hover |
| **Private** | All processing on-device. No cloud. |
| **Power** | 24Wh battery, 4-6 hour portable |
| **Sphere Size** | 85mm diameter, 350g target weight |

---

## Documentation Index

### Core Documents

| Document | Description |
|----------|-------------|
| [**SPECS.md**](SPECS.md) | Single source of truth for all dimensions and specifications |
| [**ASSEMBLY_GUIDE.md**](ASSEMBLY_GUIDE.md) | Complete step-by-step assembly instructions |
| [**HARDWARE_BOM.md**](HARDWARE_BOM.md) | Full bill of materials with pricing and sources |
| [**SYSTEM_DESIGN.md**](SYSTEM_DESIGN.md) | System architecture and state machine design |
| [**CHANGELOG.md**](CHANGELOG.md) | Version history and change tracking |

### Hardware Documentation

| Document | Description |
|----------|-------------|
| [hardware/VERIFIED_BOM_V3.1.md](hardware/VERIFIED_BOM_V3.1.md) | Verified BOM with online price research |
| [hardware/FMEA_V3.md](hardware/FMEA_V3.md) | Failure Mode and Effects Analysis (47 failure modes) |
| [hardware/THERMAL_ANALYSIS.md](hardware/THERMAL_ANALYSIS.md) | Thermal budget and cooling strategy |
| [hardware/THERMAL_IMPROVEMENTS.md](hardware/THERMAL_IMPROVEMENTS.md) | V3.1 thermal enhancements |
| [hardware/MAGNETIC_PTZ.md](hardware/MAGNETIC_PTZ.md) | Pan/tilt/zoom magnetic control system |
| [hardware/CUSTOM_PCB.md](hardware/CUSTOM_PCB.md) | Custom PCB design specifications |
| [hardware/MAGLEV_WPT_INTEGRATION.md](hardware/MAGLEV_WPT_INTEGRATION.md) | Maglev + wireless power integration |
| [hardware/DEGRADATION_MODES.md](hardware/DEGRADATION_MODES.md) | Graceful degradation strategies |

### CAD & Fabrication

| Document | Description |
|----------|-------------|
| [cad/README.md](cad/README.md) | CAD files index and fabrication guide |
| [cad/visualization/viewer.html](cad/visualization/viewer.html) | Interactive 3D WebGL viewer |
| [cad/V3_ASSEMBLY_SPECIFICATION.md](cad/V3_ASSEMBLY_SPECIFICATION.md) | Detailed assembly stack specification |
| [cad/VERIFIED_DIMENSIONS.md](cad/VERIFIED_DIMENSIONS.md) | Verified component dimensions |
| [cad/ONSHAPE_SPEC.md](cad/ONSHAPE_SPEC.md) | Onshape CAD modeling specifications |
| [cad/ASSEMBLY_LAYOUT.md](cad/ASSEMBLY_LAYOUT.md) | Internal component layout |

### PCB Design

| Document | Description |
|----------|-------------|
| [pcb/KICAD_SPEC.md](pcb/KICAD_SPEC.md) | KiCad schematic and layout specifications |
| [pcb/gerbers/README.md](pcb/gerbers/README.md) | Gerber file generation and ordering |

### Firmware & Software

| Document | Description |
|----------|-------------|
| [FIRMWARE_ARCHITECTURE.md](FIRMWARE_ARCHITECTURE.md) | Complete firmware architecture |
| [firmware/HARDWARE_INTEGRATION.md](firmware/HARDWARE_INTEGRATION.md) | Hardware integration guide |
| [firmware/python/](firmware/python/) | Python drivers for QCS6490/ESP32 |

### Project Management

| Document | Description |
|----------|-------------|
| [RISK_MITIGATION_PLAN.md](RISK_MITIGATION_PLAN.md) | Risk management framework |
| [VALIDATION_PLAN.md](VALIDATION_PLAN.md) | Testing and validation procedures |
| [PROTOTYPE_DEVELOPMENT_PLAN.md](PROTOTYPE_DEVELOPMENT_PLAN.md) | Development timeline and milestones |
| [UPWORK_JOB_POSTING.md](UPWORK_JOB_POSTING.md) | Contractor job specifications |
| [OUTREACH_EMAILS.md](OUTREACH_EMAILS.md) | Supplier outreach templates |
| [COMMUNICATIONS_TRACKER.md](COMMUNICATIONS_TRACKER.md) | Supplier communication log |

### Experience & Design

| Document | Description |
|----------|-------------|
| [EXPERIENCE_DESIGN.md](EXPERIENCE_DESIGN.md) | User experience and interaction design |
| [AUDIO_DESIGN_100.md](AUDIO_DESIGN_100.md) | Audio system design (100/100 audit) |
| [POWER_SYSTEM_COMPLETE.md](POWER_SYSTEM_COMPLETE.md) | Complete power system design |
| [INTEGRATION_PROTOCOL.md](INTEGRATION_PROTOCOL.md) | Component integration protocols |
| [DEPENDENCY_GRAPH.md](DEPENDENCY_GRAPH.md) | System dependency visualization |

### Purchasing

| Document | Description |
|----------|-------------|
| [ONE_CLICK_BUY.md](ONE_CLICK_BUY.md) | Quick purchase links for all components |
| [DOWNLOADS.md](DOWNLOADS.md) | Downloadable resources and assets |
| [bom/](bom/) | BOM generator scripts and CSV exports |

### Testing

| Document | Description |
|----------|-------------|
| [tests/TEST_SPECIFICATIONS.md](tests/TEST_SPECIFICATIONS.md) | Test procedures and acceptance criteria |

---

## Project Status

| Phase | Status | Notes |
|-------|--------|-------|
| Design | Complete | V3.1 specifications finalized |
| Documentation | 100/100 | All docs verified and consistent |
| BOM Verification | Complete | Online research with source links |
| CAD Models | Complete | OpenSCAD parametric + WebGL viewer |
| PCB Design | In Progress | KiCad schematics drafted |
| Prototype | Pending | Awaiting component procurement |
| Thermal Validation | Pending | FEA simulation required |

---

## Pricing

| Configuration | Price |
|---------------|-------|
| **DIY Kit** | ~$980-1,150 (parts only) |
| **Orb + Base** | ~$1,164-1,334 |
| **Founder's Edition** | $1,499 (assembled) |

---

## Interaction States

| State | Eye | Base |
|-------|-----|------|
| **Idle** | Slow blink, soft gaze | Soft white pulse |
| **Listening** | Wide open, pupil dilates | Cyan glow |
| **Thinking** | Squints, looks up | Purple/blue chase |
| **Speaking** | Animated, expressive | Green pulse |
| **Lifted** | Brightens, alert | Fades to warm ambient |

---

## Technical Highlights

- **52 TOPS** AI compute (on-par with flagship phones)
- **On-device** processing — nothing leaves your home
- **Magnetic levitation** with 500g capacity
- **Wireless charging** through 15mm levitation gap
- **Face tracking** via hidden pupil camera
- **Verified dimensions** from manufacturer datasheets

---

## The Vision

> *"What if your AI looked back?"*

Most AI is invisible. Alexa is a cylinder. Siri is a voice. ChatGPT is text.

The Kagami Orb is **present**. It floats in your space. It turns to face you. It shows emotion through its eye.

This isn't just a product. It's a new category: **presence devices**.

---

## Live Site

**[awktavian.github.io/art/orb/](https://awktavian.github.io/art/orb/)**

---

```
h(x) >= 0. Always.

The mirror that sees.
The eye that follows.
The presence that understands.

鏡
```
