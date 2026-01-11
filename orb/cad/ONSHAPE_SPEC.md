# Kagami Orb V3 — CAD Specification

## Overview

All CAD work for the Kagami Orb V3 is done in **OnShape** (web-based parametric CAD).

**OnShape Document:** `Kagami Orb V3` (to be created)
**Design Version:** 3.0 — 85mm Sealed SOTA

---

## V3 Design Parameters

| Parameter | V3 Value | Notes |
|-----------|----------|-------|
| **Outer Diameter** | 85mm | Sealed sphere |
| **Inner Diameter** | 70mm | Component volume |
| **Shell Thickness** | 7.5mm | Structural + thermal |
| **Display Aperture** | 70mm | 2.8" round viewing area |
| **LED Ring Diameter** | 55mm | 16× HD108 at equator |
| **RX Coil Diameter** | 70mm | Compact wireless power |
| **Weight Target** | 350g | Levitation compatible |

---

## V3 Part List

| Part | Material | Fabrication | Priority | OpenSCAD |
|------|----------|-------------|----------|----------|
| Internal Frame | CF-PETG / Tough 2000 | Form 4 SLA | P0 | `internal_frame.scad` |
| Display Mount | Grey Pro | Form 4 SLA (25μm) | P0 | `display_mount.scad` |
| LED Mount Ring | Grey Pro | Form 4 SLA | P0 | `led_mount_ring.scad` |
| Battery Cradle | Tough 2000 | Form 4 SLA | P0 | `battery_cradle.scad` |
| Diffuser Ring | White / Frosted | Form 4 SLA | P1 | `diffuser_ring.scad` |
| Resonant Coil Mount | Tough 2000 | Form 4 SLA | P1 | `resonant_coil_mount.scad` |
| Outer Shell (2×) | Acrylic 85mm | Buy (TAP Plastics) | - | - |
| Dielectric Mirror | Film | Buy (Edmund Optics) | - | - |
| Base Enclosure | Walnut | CNC | P2 | - |
| **Outdoor Canopy** | Copper/Aluminum | Metal Spinning | P3 | - |
| **Support Arms ×3** | 304 Stainless | Laser + Bend | P3 | `canopy_arms.svg` |
| **Mount Ring** | Walnut | CNC | P3 | `canopy_mount_ring.dxf` |

---

## Part 1: Internal Frame (V3)

### Design Requirements

```
PURPOSE: Main structural element for 85mm sealed sphere
SIZE: 65mm diameter × 45mm height (fits inside 70mm inner shell)

┌─────────────────────────────────────────────────────────────────────────────────┐
│                       V3 INTERNAL FRAME (Cross Section)                          │
│                                                                                  │
│            ╭──────────── 65mm ────────────╮                                     │
│            │                               │                                     │
│            │  ┌─────────────────────────┐  │                                     │
│            │  │   DISPLAY MOUNT ZONE    │  │ ← Display mount interfaces here    │
│            │  │   (78mm ring above)     │  │                                     │
│            │  ├─────────────────────────┤  │                                     │
│            │  │                         │  │                                     │
│            │  │   QCS6490 SoM PLATFORM  │  │ ← 40×35mm SoM mount                │
│            │  │   ┌─────────────────┐   │  │                                     │
│       45mm │  │   │   □ □ □ □ □     │   │  │ ← M2 standoffs                     │
│            │  │   │   HAILO-10H     │   │  │ ← M.2 2242 slot                    │
│            │  │   └─────────────────┘   │  │                                     │
│            │  │                         │  │                                     │
│            │  │   BATTERY INTERFACE     │  │ ← M3 mount points                   │
│            │  │                         │  │                                     │
│            │  ├─────────────────────────┤  │                                     │
│            │  │   LED RING TABS (×4)    │  │ ← 90° spacing                       │
│            │  └─────────────────────────┘  │                                     │
│            ╰───────────────────────────────╯                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Key Dimensions

| Feature | Dimension | Tolerance |
|---------|-----------|-----------|
| Overall diameter | 65mm | ±0.3mm |
| Overall height | 45mm | ±0.3mm |
| SoM platform | 40×35mm | ±0.2mm |
| M.2 slot | 42×22mm | ±0.2mm |
| Wall thickness | 2.5mm | ±0.2mm |
| LED tab width | 6mm | ±0.2mm |

---

## Part 2: Display Mount (V3 — NEW)

### Design Requirements

```
PURPOSE: Hold 2.8" round AMOLED + camera behind pupil
SIZE: 78mm OD × 6mm height

┌─────────────────────────────────────────────────────────────────────────────────┐
│                       DISPLAY MOUNT (Top View)                                   │
│                                                                                  │
│                         ╭─────── 78mm ───────╮                                  │
│                        │                       │                                 │
│                        │    ╭─── 70mm ───╮    │ ← Viewing aperture              │
│                        │   │               │   │                                 │
│                        │   │    ╭─────╮    │   │                                 │
│                        │   │    │ 8mm │    │   │ ← Camera aperture (pupil)      │
│                        │   │    ╰─────╯    │   │                                 │
│                        │   │               │   │                                 │
│                        │    ╰─────────────╯    │                                 │
│                        │         │             │                                 │
│                        │    FLEX CHANNEL       │ ← 15mm wide                    │
│                         ╰─────────────────────╯                                  │
│                                                                                  │
│   FEATURES:                                                                      │
│   • 2.8" AMOLED recess (72mm active, 76mm module)                               │
│   • Camera aperture 8mm (IMX989 behind display)                                 │
│   • Dielectric mirror film recess                                               │
│   • Retention clips (×4)                                                        │
│   • M2 screw mounts (×3)                                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Key Dimensions

| Feature | Dimension | Notes |
|---------|-----------|-------|
| Mount OD | 78mm | Fits inside 85mm shell |
| Viewing aperture | 70mm | Display active area |
| Camera aperture | 8mm | IMX989 behind |
| Display recess | 76mm × 3.5mm | Module depth |
| Mirror recess | 74mm × 0.5mm | Dielectric film |

---

## Part 3: LED Mount Ring (V3)

### Design Requirements

```
PURPOSE: Hold 16× HD108 LEDs at sphere equator
SIZE: 58mm OD × 6mm height

┌─────────────────────────────────────────────────────────────────────────────────┐
│                       LED MOUNT RING (Top View)                                  │
│                                                                                  │
│                         ╭─────── 58mm ───────╮                                  │
│                        │     ○ ○ ○ ○ ○        │ ← 16× HD108 positions           │
│                        │   ○             ○    │   (22.5° spacing)               │
│                        │  ○    ╭─────╮    ○   │                                 │
│                        │ ○     │ 48mm│     ○  │ ← Inner opening                 │
│                        │  ○    ╰─────╯    ○   │                                 │
│                        │   ○             ○    │                                 │
│                        │     ○ ○ ○ ○ ○        │                                 │
│                         ╰─────────────────────╯                                  │
│                                                                                  │
│   • PCB slot: 1.6mm for LED ring PCB                                            │
│   • Diffuser slot: 2mm at top                                                   │
│   • Mount tabs: 4× at 90° for frame attachment                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 4: Battery Cradle (V3)

### Design Requirements

```
PURPOSE: Hold compact 3S 2200mAh LiPo + BMS (VERIFIED 55×35×20mm)
SIZE: ~63×43×16mm

┌─────────────────────────────────────────────────────────────────────────────────┐
│                       BATTERY CRADLE (Top View)                                  │
│                                                                                  │
│              ╭──────────── 63mm ────────────╮                                   │
│              │  ╔═══════════════════════╗   │                                   │
│              │  ║                       ║   │                                   │
│              │  ║   BATTERY POCKET      ║   │ ← 55×35×12mm                      │
│         43mm │  ║   (foam-lined)        ║   │                                   │
│              │  ║                       ║   │                                   │
│              │  ╠═══════════════════════╣   │                                   │
│              │  ║  BMS POCKET           ║   │ ← BQ25895 + BQ40Z50              │
│              │  ╚═══════════════════════╝   │                                   │
│              ╰──────────────────────────────╯                                   │
│                                                                                  │
│   FEATURES:                                                                      │
│   • Strap slots for velcro retention                                            │
│   • Wire exit channels                                                          │
│   • Thermal pad recess (bottom)                                                 │
│   • M3 mount points (×4)                                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Resonant Coil Mount (V3)

### Design Requirements

```
PURPOSE: Hold 70mm RX coil at sphere bottom
SIZE: 72mm diameter × 6mm height

┌─────────────────────────────────────────────────────────────────────────────────┐
│                       COIL MOUNT (Cross Section)                                 │
│                                                                                  │
│              ╭─────────── 72mm ───────────╮                                     │
│              │                             │                                     │
│              │   ══════════════════════   │ ← Coil recess (70mm, 3mm deep)     │
│              │  │░░░░░░░░░░░░░░░░░░░░░│   │ ← Ferrite sheet (60mm)             │
│              │   ════════╤════════════    │                                     │
│              │           │                │                                     │
│              │     THERMAL VIAS (×8)      │ ← 4mm holes for heat path          │
│              │           │                │                                     │
│              ╰───────────┴────────────────╯                                     │
│                                                                                  │
│   FEATURES:                                                                      │
│   • Coil recess with wire channel                                               │
│   • Ferrite recess (bottom)                                                     │
│   • 8× thermal vias for heat conduction                                         │
│   • Alignment pins (×3)                                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Assembly Stack

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       V3 ASSEMBLY STACK (85mm Sphere)                            │
│                                                                                  │
│   TOP (Display Side)                                                             │
│   ═══════════════════                                                            │
│                                                                                  │
│   ┌─────────────────┐                                                            │
│   │ Outer Shell Top │  ← 85mm acrylic hemisphere                                │
│   ├─────────────────┤                                                            │
│   │ Dielectric Film │  ← Touch-through mirror                                   │
│   ├─────────────────┤                                                            │
│   │ 2.8" AMOLED     │  ← 480×480 round display                                  │
│   ├─────────────────┤                                                            │
│   │ Display Mount   │  ← Grey Pro, 78mm                                         │
│   ├─────────────────┤                                                            │
│   │ IMX989 Camera   │  ← Behind display center                                  │
│   ├─────────────────┤                                                            │
│   │ QCS6490 + Hailo │  ← Main compute                                           │
│   ├─────────────────┤                                                            │
│   │ Internal Frame  │  ← CF-PETG, 65mm                                          │
│   ├─────────────────┤                                                            │
│   │ LED Mount Ring  │  ← 16× HD108 at equator                                   │
│   ├─────────────────┤                                                            │
│   │ Diffuser Ring   │  ← Light diffusion                                        │
│   ├─────────────────┤                                                            │
│   │ Battery + BMS   │  ← 2200mAh 3S LiPo (VERIFIED)                             │
│   ├─────────────────┤                                                            │
│   │ Battery Cradle  │  ← Tough 2000                                             │
│   ├─────────────────┤                                                            │
│   │ RX Coil Mount   │  ← Tough 2000, 72mm                                       │
│   ├─────────────────┤                                                            │
│   │ RX Coil 70mm    │  ← Litz wire, 18 turns                                    │
│   ├─────────────────┤                                                            │
│   │ Outer Shell Bot │  ← 85mm acrylic hemisphere                                │
│   └─────────────────┘                                                            │
│                                                                                  │
│   BOTTOM (Base Side)                                                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Print Settings (Form 4)

| Part | Resin | Layer Height | Supports | Post-Cure |
|------|-------|--------------|----------|-----------|
| Internal Frame | Tough 2000 | 50μm | Auto | 60min @ 70°C |
| Display Mount | Grey Pro | 25μm | Manual | 30min @ 60°C |
| LED Mount Ring | Grey Pro | 50μm | Auto | 30min @ 60°C |
| Battery Cradle | Tough 2000 | 50μm | Auto | 60min @ 70°C |
| Diffuser Ring | White | 50μm | Auto | 15min @ 60°C |
| Coil Mount | Tough 2000 | 50μm | Auto | 60min @ 70°C |

---

## Tolerances & Fits

| Interface | Fit Type | Clearance |
|-----------|----------|-----------|
| Frame ↔ Shell | Loose | 2.5mm |
| Display ↔ Mount | Press | 0.1mm |
| LED Ring ↔ Frame | Snap | 0.2mm |
| Battery ↔ Cradle | Loose | 0.3mm |
| Coil ↔ Mount | Press | 0.1mm |
| Shell halves | Adhesive | 0mm (glued) |

---

## Changelog

### V3.0 (January 2026)
- Complete redesign for 85mm sealed sphere
- Added Display Mount (new part)
- Updated all dimensions for compact form
- Removed CM4 references (now QCS6490)
- Added M.2 slot for Hailo-10H
