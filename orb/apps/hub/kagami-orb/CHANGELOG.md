# Kagami Orb — Changelog

All notable changes to the Kagami Orb project are documented here.

---

## [V3.1] — January 2026

### Thermal Improvements
- Added multi-stage thermal throttling ladder (65C/75C/85C)
- Integrated TMP117 junction temperature monitoring
- Designed thermal bridge to shell with graphite sheet
- Added emergency shutdown protocol with voice warning
- Commissioned FEA thermal simulation requirements

### Viewer Enhancements
- Premium Pixar-quality 3D WebGL viewer with full interactivity
- Exploded view with animation controls
- Part highlighting and selection
- VR/AR mode support via WebXR
- Mobile touch gesture support
- Measurement tools overlay

### Documentation Updates
- Created comprehensive documentation index in README.md
- Fixed display size references (1.39" AMOLED, Ø35.41mm active)
- Removed outdated 2.8" display references from assembly guides
- Added DXF/SVG export workflow notes to CAD documentation
- Verified all component dimensions against manufacturer datasheets
- Created this CHANGELOG.md for version tracking

### BOM Verification
- Online price verification for all major components
- Added verified supplier links and lead times
- Identified single-source risks (sensiBel, Hailo-10H)
- Documented fallback components for critical items
- Price corrections: QCS6490 ($200-260), 1.39" AMOLED ($15-30)

### Risk Mitigation
- Completed FMEA with 47 failure modes identified
- 8 critical items (RPN > 100) with mitigation plans
- Battery safety system with triple-redundant protection
- Dual-source microphone PCB footprint design

---

## [V3.0] — January 2026

### Major Redesign
Complete overhaul from V2 with 85mm compact form factor.

### Form Factor
- Reduced sphere diameter from 120mm (V2) to 85mm
- 29% size reduction while increasing capability
- 85mm acrylic hemisphere shell
- Weight target: 350g (with 500g levitation margin)

### Display System
- NEW: 1.39" round AMOLED (454x454 resolution)
- RM69330 driver with MIPI DSI interface
- Module dimensions: 38.83 x 38.21 x 0.68mm
- Active area: Ø35.41mm
- Dielectric mirror coating for touch-through operation
- Camera aperture in display center (8mm)

### Compute Platform
- QCS6490 SoM: 12.5 TOPS NPU, WiFi 6E, BT 5.2
- Hailo-10H M.2: 40 TOPS INT4 acceleration
- Combined: 52 TOPS AI compute
- ESP32-S3: Co-processor for LED/sensor control

### Camera System
- Sony IMX989 50.3MP 1-inch sensor
- Hidden behind display in pupil position
- 8P+IR lens with f/2.0 aperture
- Module: 26 x 26 x 9.4mm

### Audio System
- sensiBel SBM100B optical MEMS microphones (x4)
- 80dB SNR (industry-leading)
- XMOS XVF3800 voice DSP with AEC/beamforming
- Tectonic TEBM28C20N-4 28mm BMR speaker
- MAX98357A I2S Class-D amplifier

### LED System
- HD108 RGBW LEDs (x16) at equator
- 16-bit color depth (65,536 levels/channel)
- 74AHCT125 level shifter (3.3V to 5V)
- Diffuser ring for soft ambient glow

### Power System
- 3S 2200mAh LiPo battery (24Wh, 11.1V)
- 70mm Litz wire resonant coils
- 15W wireless power transfer at 15mm gap
- BQ25895 buck-boost charger
- BQ40Z50 smart fuel gauge
- Renesas P9415-R WPC receiver

### Levitation
- HCNT 500g magnetic levitation module
- 18-25mm levitation gap
- Magnetic PTZ orientation control
- 4x Hall sensors for orientation feedback

### Base Station
- Walnut CNC enclosure (Ø180mm x 25mm)
- TX coil (70mm, 14 turns)
- ESP32-S3-WROOM-1-N8R8 controller
- HD108 status ring (8 LEDs)
- Mean Well GST60A24 power supply (24V 60W)

---

## [V2.0] — 2025 (Deprecated)

### Original Design
- 120mm sphere diameter
- Raspberry Pi CM4 compute
- Google Coral Edge TPU
- No display (LED-only interface)
- Standard MEMS microphones

**Status:** Superseded by V3.0

---

## Version Numbering

| Version | Status | Description |
|---------|--------|-------------|
| V3.1 | Current | Thermal improvements, viewer enhancements, doc updates |
| V3.0 | Stable | 85mm compact SOTA with living display |
| V2.0 | Deprecated | Original 120mm design |

---

## Document Version Tracking

All documents in this project should reference **V3.1** as the current version.

| Document | Version | Last Updated |
|----------|---------|--------------|
| SPECS.md | V3.1 | January 2026 |
| ASSEMBLY_GUIDE.md | V3.1 | January 2026 |
| HARDWARE_BOM.md | V3.1 | January 2026 |
| FMEA_V3.md | V3.1 | January 2026 |
| VERIFIED_BOM_V3.1.md | V3.1 | January 2026 |
| SYSTEM_DESIGN.md | V3.1 | January 2026 |
| cad/README.md | V3.1 | January 2026 |

---

```
h(x) >= 0. Always.

Every change documented.
Every version tracked.
Every improvement recorded.

The mirror remembers.

鏡
```
