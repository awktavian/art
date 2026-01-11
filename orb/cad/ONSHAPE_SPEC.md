# Kagami Orb — OnShape CAD Specification

## Overview

All CAD work for the Kagami Orb is done in **OnShape** (web-based parametric CAD).

**OnShape Document:** `Kagami Orb v1.0` (to be created)

---

## Part List

| Part | Material | Print/Buy | Priority |
|------|----------|-----------|----------|
| Internal Frame | CF-PETG or Tough 2000 | Print (Form 4) | P0 |
| LED Mount Ring | Grey Pro | Print (Form 4) | P0 |
| Battery Cradle | Tough 2000 | Print (Form 4) | P0 |
| CM4 Mount Bracket | Grey Pro | Print (Form 4) | P1 |
| Resonant Coil Mount | Tough 2000 | Print (Form 4) | P1 |
| Diffuser Ring | White resin | Print (Form 4) | P1 |
| Outer Shell | Acrylic 120mm | Buy (TAP Plastics) | - |
| Inner Mirror | Acrylic 100mm | Buy | - |
| Base Enclosure | Walnut | CNC | P2 |
| **Outdoor Canopy** | Copper or Aluminum | CNC/Spin | P3 |
| **Canopy Support Arms** | Stainless Steel | Laser + Bend | P3 |
| **Canopy Mount Ring** | Walnut | CNC | P3 |

---

## Part 1: Internal Frame

### Design Requirements

```
PURPOSE: Main structural element holding all electronics
SIZE: Must fit inside 120mm sphere with 10mm wall clearance
      Effective diameter: 100mm max

FEATURES:
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         INTERNAL FRAME (Top View)                                │
│                                                                                  │
│                              ┌─────────────┐                                     │
│                             ╱               ╲                                    │
│                            ╱   CM4 MOUNT    ╲                                   │
│                           │     PLATFORM     │  ← 55×40mm cutout                │
│                           │    ┌───────┐     │                                   │
│                           │    │ ○ ○ ○ │     │  ← M2.5 standoffs               │
│                           │    │       │     │                                   │
│                           │    │ CM4   │     │                                   │
│                           │    │       │     │                                   │
│                           │    └───────┘     │                                   │
│                           │                  │                                   │
│                            ╲   CORAL MOUNT  ╱                                   │
│                             ╲    ┌───┐     ╱                                    │
│                              ╲   │TPU│    ╱                                     │
│                               ╲  └───┘   ╱                                      │
│                                ╰────────╯                                       │
│                                                                                  │
│  SIDE FEATURES:                                                                  │
│  • LED ring mount tabs (6×, 60° spacing)                                        │
│  • Battery cradle mount points (4×)                                             │
│  • Cable routing channels                                                       │
│  • Ventilation slots                                                            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Dimensions

| Feature | Dimension | Tolerance |
|---------|-----------|-----------|
| Overall diameter | 95mm | ±0.5mm |
| Overall height | 60mm | ±0.5mm |
| CM4 platform | 55×40mm | ±0.2mm |
| Standoff holes | M2.5 | ±0.1mm |
| Wall thickness | 3mm | ±0.2mm |
| LED mount tab width | 8mm | ±0.3mm |

### Assembly Features

- 6× M2.5 threaded inserts for CM4 standoffs
- 4× M3 threaded inserts for battery cradle
- Snap-fit tabs for LED ring (replaceable)
- Alignment features for shell mating

---

## Part 2: LED Mount Ring

### Design Requirements

```
PURPOSE: Hold SK6812 24-LED ring at sphere equator
SIZE: Fits inside sphere equator with diffuser

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         LED MOUNT RING (Cross Section)                           │
│                                                                                  │
│        ┌──────────────────────────────────────────────────────────┐             │
│        │                   DIFFUSER SLOT                          │             │
│        │◄─────────────── 75mm ID ──────────────────►│             │
│        │                                              │             │
│    ════│════════════════════════════════════════════│════         │
│        │         LED RING GROOVE (68mm)             │   ↑         │
│        │    ┌────────────────────────────────┐      │   │         │
│        │    │ ● ● ● ● ● LED PCB ● ● ● ● ● │      │   8mm        │
│        │    └────────────────────────────────┘      │   │         │
│    ════│════════════════════════════════════════════│════ ↓       │
│        │                                              │             │
│        │◄────────────── 85mm OD ──────────────────►│             │
│        └──────────────────────────────────────────────┘             │
│                                                                      │
│  FEATURES:                                                           │
│  • Groove for SK6812 ring PCB (68mm ID, 74mm OD)                    │
│  • Slot for diffuser ring above LEDs                                │
│  • Cable exit notch for data/power                                  │
│  • 6× snap tabs to frame                                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Dimensions

| Feature | Dimension | Tolerance |
|---------|-----------|-----------|
| Inner diameter | 75mm | ±0.3mm |
| Outer diameter | 85mm | ±0.3mm |
| Height | 8mm | ±0.2mm |
| LED groove depth | 2mm | ±0.1mm |
| Diffuser slot width | 3mm | ±0.2mm |

---

## Part 3: Battery Cradle

### Design Requirements

```
PURPOSE: Secure 3S Li-Po pack in bottom of sphere
SIZE: Accommodate 100×60×20mm pouch cell

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         BATTERY CRADLE (Isometric)                               │
│                                                                                  │
│                    ╭──────────────────────────╮                                 │
│                   ╱                            ╲                                │
│                  ╱   ┌────────────────────┐    ╲                               │
│                 │    │                    │     │                               │
│                 │    │     BATTERY        │     │                               │
│                 │    │     POCKET         │     │  ← Foam lined                │
│                 │    │                    │     │                               │
│                 │    └────────────────────┘     │                               │
│                  ╲                              ╱                                │
│                   ╲   STRAP SLOTS (2×)        ╱                                 │
│                    ╲  ══════    ══════       ╱                                  │
│                     ╰────────────────────────╯                                  │
│                                                                                  │
│  FEATURES:                                                                       │
│  • Pocket for 100×60×20mm battery                                               │
│  • 2× Velcro strap slots                                                        │
│  • Foam padding recesses                                                        │
│  • Wire exit channel                                                            │
│  • 4× M3 mount holes to frame                                                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Dimensions

| Feature | Dimension | Tolerance |
|---------|-----------|-----------|
| Pocket length | 102mm | ±1mm |
| Pocket width | 62mm | ±1mm |
| Pocket depth | 22mm | ±1mm |
| Wall thickness | 2mm | ±0.3mm |
| Strap slot width | 15mm | ±0.5mm |

---

## Part 4: CM4 Mount Bracket

```
PURPOSE: Heat sink mount and CM4 alignment
SIZE: Matches CM4 footprint with thermal standoff

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CM4 MOUNT BRACKET (Top View)                             │
│                                                                                  │
│            ┌──────────────────────────────────────────────┐                     │
│            │  ○                                       ○   │  ← M2.5 holes      │
│            │                                              │                     │
│            │      ┌────────────────────────────┐          │                     │
│            │      │                            │          │                     │
│            │      │     HEATSINK CONTACT       │          │                     │
│            │      │       (40×40mm)            │          │  ← Thermal path    │
│            │      │                            │          │                     │
│            │      └────────────────────────────┘          │                     │
│            │                                              │                     │
│            │  ○                                       ○   │                     │
│            └──────────────────────────────────────────────┘                     │
│                                                                                  │
│  FEATURES:                                                                       │
│  • 4× M2.5 holes matching CM4 pattern                                           │
│  • Central thermal contact area                                                  │
│  • Raised standoffs for airflow                                                  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 5: Diffuser Ring

```
PURPOSE: Soften LED hotspots for infinity effect
MATERIAL: White resin or frosted acrylic

Simple ring:
• ID: 70mm
• OD: 80mm
• Height: 3mm
• Frosted or opal finish
```

---

## Part 6: Resonant Coil Mount

```
PURPOSE: Position resonant receiver coil at bottom of orb
SIZE: Matches 80mm Litz coil footprint

Simple platform:
• Diameter: 85mm (matches 80mm Litz coil)
• Height: 5mm
• Alignment pins for coil centering
• Mount holes to frame
```

---

## Assembly Model

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         FULL ASSEMBLY (Cross Section)                            │
│                                                                                  │
│                              ┌─────────────┐                                     │
│                             ╱               ╲                                    │
│                         ───╱─── OUTER SHELL ─╲───                               │
│                        ╱  ╱                    ╲  ╲                              │
│                       │  │  ┌──── AIR GAP ────┐ │  │                            │
│                       │  │  │                  │ │  │                            │
│                       │  │  │   CM4 + CORAL    │ │  │                            │
│                       │  │  │   ┌─────────┐    │ │  │                            │
│                       │  │  │   │ HEATSINK│    │ │  │                            │
│          LED RING ─── │  │──│───●●●●●●●●●●────│ │  │                            │
│                       │  │  │   └─────────┘    │ │  │                            │
│                       │  │  │     FRAME        │ │  │                            │
│                       │  │  │                  │ │  │                            │
│                       │  │  │    BATTERY       │ │  │                            │
│                       │  │  │   ┌────────┐     │ │  │                            │
│                       │  │  │   │ 10Ah   │     │ │  │                            │
│                       │  │  │   └────────┘     │ │  │                            │
│                       │  │  │                  │ │  │                            │
│                       │  │  │ RESONANT RECEIVER │ │  │                            │
│                        ╲  ╲ └──────────────────┘ ╱  ╱                           │
│                         ───╲─── INNER SHELL ──╱───                               │
│                             ╲               ╱                                    │
│                              └─────────────┘                                     │
│                                    │                                             │
│                              15mm GAP                                            │
│                                    │                                             │
│                         ══════════════════════                                   │
│                                 BASE                                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## OnShape Workflow

1. **Create Document:** "Kagami Orb v1.0"
2. **Create Part Studios:**
   - `Internal Frame`
   - `LED Mount Ring`
   - `Battery Cradle`
   - `CM4 Bracket`
   - `Diffuser Ring`
   - `Resonant Coil Mount`
3. **Create Assembly:** `Orb Assembly`
4. **Import:** Hemisphere (as surface body reference)
5. **Mate:** All parts to frame
6. **Export:** STL for each part

---

## STL Export Settings

| Parameter | Value |
|-----------|-------|
| Format | STL (binary) |
| Units | Millimeters |
| Resolution | Fine |
| Chord height | 0.01mm |
| Angle tolerance | 1° |

---

## Form 4 Print Settings

| Part | Material | Layer | Supports | Time |
|------|----------|-------|----------|------|
| Internal Frame | Tough 2000 | 50μm | Yes | 8h |
| LED Mount Ring | Grey Pro | 25μm | Minimal | 3h |
| Battery Cradle | Tough 2000 | 50μm | Yes | 4h |
| CM4 Bracket | Grey Pro | 50μm | Minimal | 2h |
| Diffuser Ring | White | 50μm | No | 2h |
| Resonant Coil Mount | Tough 2000 | 50μm | Minimal | 1h |

**Total Print Time: ~20 hours**

---

## Outdoor Canopy Addon (P3)

The outdoor canopy is an **addon accessory** that converts the indoor dock into a weatherproof outdoor dock. The orb itself requires no modification—only the base station gains a protective pavilion.

### Part 7: Outdoor Canopy

```
PURPOSE: Weatherproof shelter for floating orb
FABRICATION: Metal spinning or CNC from sheet

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CANOPY (Cross Section)                                   │
│                                                                                  │
│                         ╭──────────────────────────╮                            │
│                        ╱         5° SLOPE           ╲                           │
│                       ╱    (drainage to edges)       ╲                          │
│                      ╱                                 ╲                         │
│                     │◄────────── 300mm ───────────────►│                        │
│                     │                                   │                        │
│            ┌────────┴───────────────────────────────────┴────────┐              │
│            │                    DRIP EDGE                         │              │
│            │               (15mm overhang, 45°)                   │              │
│            └─────────────────────────────────────────────────────┘              │
│                                                                                  │
│  FEATURES:                                                                       │
│  • 5° slope from center to edge (water drainage)                                │
│  • 15mm drip edge all around (prevents water run-back)                          │
│  • Center hole: 30mm (ventilation, star visibility)                             │
│  • Material: 1.5mm copper sheet OR 2mm aluminum                                 │
│  • Finish: Brushed copper patina OR powder-coat matte black                     │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Canopy Dimensions

| Feature | Dimension | Tolerance |
|---------|-----------|-----------|
| Outer diameter | 300mm | ±1mm |
| Inner edge diameter | 280mm | ±1mm |
| Center vent hole | 30mm | ±0.5mm |
| Material thickness | 1.5mm (Cu) / 2mm (Al) | - |
| Slope angle | 5° | ±0.5° |
| Drip edge height | 15mm | ±1mm |
| Drip edge angle | 45° | ±2° |

### Part 8: Canopy Support Arms (×3)

```
PURPOSE: Connect canopy to base while allowing orb access
FABRICATION: Laser cut stainless steel, brake bend

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SUPPORT ARM (Side View)                                  │
│                                                                                  │
│                            ┌─── Canopy mount hole (M4)                          │
│                            │                                                     │
│                            ○                                                     │
│                           ╱                                                      │
│                          ╱   ← 250mm total height                               │
│                         ╱                                                        │
│                        │     ← 15mm wide, 3mm thick                             │
│                        │                                                         │
│                        │     ← Slight outward curve (aesthetic)                 │
│                        │                                                         │
│                        ╲                                                         │
│                         ╲                                                        │
│                          ○ ← Base mount hole (M4)                               │
│                                                                                  │
│  FEATURES:                                                                       │
│  • 3× arms at 120° spacing                                                       │
│  • 304 stainless steel, brushed finish                                          │
│  • Brake bend at 15° outward (visual lightness)                                 │
│  • M4 mounting holes top and bottom                                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Support Arm Dimensions

| Feature | Dimension | Tolerance |
|---------|-----------|-----------|
| Total height | 250mm | ±1mm |
| Width | 15mm | ±0.5mm |
| Thickness | 3mm | - |
| Bend angle | 15° outward | ±1° |
| Mount hole diameter | 4.2mm (M4 clearance) | ±0.1mm |

### Part 9: Canopy Mount Ring

```
PURPOSE: Attach support arms to walnut base
FABRICATION: CNC from walnut, matches base aesthetic

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         MOUNT RING (Top View)                                    │
│                                                                                  │
│                              ╭─────────────╮                                    │
│                             ╱               ╲                                   │
│                            ╱   ┌─────────┐   ╲                                  │
│                           │    │  BASE   │    │                                  │
│                           │    │ CUTOUT  │    │  ← Matches base top profile     │
│                           │    └─────────┘    │                                  │
│                           │  ○             ○  │  ← M4 threaded inserts (×3)     │
│                            ╲       ○       ╱                                    │
│                             ╲             ╱                                     │
│                              ╰───────────╯                                      │
│                                                                                  │
│  FEATURES:                                                                       │
│  • Sits atop walnut base (adds 10mm height)                                     │
│  • 3× M4 brass threaded inserts for arm mounting                                │
│  • Center cutout matches base top surface                                       │
│  • Same walnut, same finish as base                                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Mount Ring Dimensions

| Feature | Dimension | Tolerance |
|---------|-----------|-----------|
| Outer diameter | 200mm | ±0.5mm |
| Inner cutout | 160mm | ±0.5mm |
| Height | 10mm | ±0.3mm |
| Insert spacing | 120° | - |
| Insert radius | 85mm from center | ±0.5mm |

---

## Outdoor Canopy Assembly

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    OUTDOOR DOCK ASSEMBLY (Exploded View)                         │
│                                                                                  │
│                              ╭───────────────╮                                  │
│                             ╱     CANOPY      ╲                                 │
│                            ╱   (copper/alum)   ╲                                │
│                           ╰─────────────────────╯                               │
│                                     │                                            │
│                                     ▼ M4 bolts (×3)                             │
│                              │      │      │                                    │
│                              │  ARM │  ARM │  ARM                               │
│                              │      │      │                                    │
│                                     │                                            │
│                                     ▼ M4 bolts (×3)                             │
│                              ╭─────────────╮                                    │
│                              │ MOUNT RING  │                                    │
│                              ╰──────┬──────╯                                    │
│                                     │                                            │
│                                     ▼ Sits on top                               │
│                         ╔═══════════════════════╗                               │
│                         ║    WALNUT BASE        ║                               │
│                         ║  (indoor dock base)   ║                               │
│                         ╚═══════════════════════╝                               │
│                                                                                  │
│  ASSEMBLY ORDER:                                                                 │
│  1. Indoor dock complete and tested                                             │
│  2. Place mount ring on base (alignment pins)                                   │
│  3. Insert M4 bolts through arms into mount ring                                │
│  4. Place canopy on arms, secure with M4 bolts                                  │
│  5. Total assembly time: 15 minutes                                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Canopy Fabrication Options

| Method | Material | Cost | Lead Time | Notes |
|--------|----------|------|-----------|-------|
| **Metal Spinning** | Copper 1.5mm | ~$150 | 2-3 weeks | Best for copper, seamless |
| **CNC Waterjet** | Aluminum 2mm | ~$80 | 1 week | Requires welded drip edge |
| **Sheet Forming** | Aluminum 2mm | ~$60 | 1 week | DIY possible with brake |
| **3D Print + Plate** | PETG + Copper plate | ~$40 | 3 days | Prototype only |

### Recommended Vendors

| Component | Vendor | Notes |
|-----------|--------|-------|
| Copper spinning | Local metal spinner | Search "metal spinning [city]" |
| Stainless arms | SendCutSend | Laser + brake service |
| Walnut ring | Local CNC shop | Or Glowforge if <10mm |

---

```
鏡

h(x) ≥ 0. Always.

The form follows function.
The CAD precedes the print.
OnShape stores the truth.
```
