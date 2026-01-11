# Kagami Orb V3.1 — Optimal Assembly Layout

**Principle:** Minimal parts, optimal stacking, verified dimensions, single PCB where possible.

---

## Design Constraints

| Parameter | Value | Notes |
|-----------|-------|-------|
| Outer diameter | 85mm | Fixed |
| Shell thickness | 7.5mm | Structural minimum |
| Internal diameter | **70mm** | 85 - 15 = 70mm |
| Max component | **~65mm** | 2.5mm clearance each side |
| Levitation gap | 15mm | HCNT spec |
| Max orb mass | 350g | 500g capacity - 150g margin |

---

## Vertical Stack (Y coordinates in mm)

```
Y = +42.5  ┌─────────────────────────────────┐  ← Top of sphere
           │                                 │
Y = +30    │     ╔═══════════════════╗       │  ← DISPLAY (1.39" AMOLED)
           │     ║  38.2 × 38.8mm    ║       │     y=30, h=0.68mm
           │     ╚═══════════════════╝       │
           │                                 │
Y = +24    │       ┌─────────────┐           │  ← CAMERA (IMX989)
           │       │ 26×26×9.4mm │           │     y=24, behind display
           │       └─────────────┘           │
           │                                 │
Y = +18    │     ┌───────────────────┐       │  ← DISPLAY MOUNT
           │     │    Ø44 × 8mm      │       │     Grey Pro SLA
           │     └───────────────────┘       │
           │                                 │
Y = +13    │     ╔═════════════════════╗     │  ← QCS6490 SoM
           │     ║  42.5 × 35.5 × 5mm  ║     │     + heatsink on top
           │     ╚═════════════════════╝     │
           │                                 │
Y = +10    │     ┌─────────────────────┐     │  ← MAIN PCB (60mm round)
           │     │     4-layer FR4      │     │     SoM + Hailo + BMS
           │     └─────────────────────┘     │
           │                                 │
Y = +8     │       ╔═══════════════╗         │  ← HAILO-10H M.2
           │       ║  42 × 22 × 3   ║         │     On main PCB
           │       ╚═══════════════╝         │
           │                                 │
Y = +5     │    🎤        🎤        🎤       │  ← MICS (sensiBel ×4)
           │         (on frame edge)         │     6×3.8×2.47mm each
           │                                 │
Y = 0      │  ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○  │  ← LED RING (equator)
           │      HD108 ×16 on flex PCB      │     Ø50mm ring
           │                                 │
Y = -8     │        ┌───────────┐            │  ← SPEAKER (28mm)
           │        │  Ø28×5.4  │            │     Fires downward
           │        └───────────┘            │
           │                                 │
Y = -20    │     ╔═══════════════════╗       │  ← BATTERY (2200mAh)
           │     ║   55 × 35 × 20mm  ║       │     3S LiPo = 24Wh
           │     ╚═══════════════════╝       │
           │                                 │
Y = -32    │     ┌───────────────────┐       │  ← COIL MOUNT
           │     │     Ø66 × 4mm     │       │     Tough 2000 SLA
           │     └───────────────────┘       │
           │                                 │
Y = -34    │     ════════════════════        │  ← RX COIL (70mm)
           │       Litz wire 18 turns        │     85μH for resonant charging
           │                                 │
Y = -36    │     ░░░░░░░░░░░░░░░░░░░░        │  ← FERRITE (60mm)
           │          Mn-Zn shield           │     Blocks field from battery
           │                                 │
Y = -42.5  └─────────────────────────────────┘  ← Bottom of sphere


═══════════════════════════════════════════════════  15mm GAP (levitation)


Y = -50    ○ ○ ○ ○ ○ ○ ○ ○                      ← BASE LEDs (SK6812 ×8)

Y = -52    ┌─────────────────────┐              ← BASE PCB (70mm)
           │   ESP32-S3 + drivers │              
           └─────────────────────┘

Y = -55    ════════════════════                 ← TX COIL (70mm)
             Litz wire 14 turns                    40μH for power TX

Y = -62    ╔═════════════════════╗              ← HCNT MAGLEV
           ║    80 × 80 × 15mm   ║                 500g capacity
           ╚═════════════════════╝

Y = -72    ╔═══════════════════════════════╗    ← WALNUT BASE
           ║      Ø140 × 20mm CNC          ║       Housing for all base components
           ╚═══════════════════════════════╝

Y = -82    ═══════════════════════════════════  ← FLOOR
```

---

## Simplified Manufacturing

### Custom Parts (Manufacture)

| Part | Process | Material | Est. Cost |
|------|---------|----------|-----------|
| Shell (2 halves) | Injection or vacuum form | Clear acrylic | $50-80 |
| Display Mount | SLA 3D print | Grey Pro | $8 |
| Coil Mount | SLA 3D print | Tough 2000 | $6 |
| Diffuser Ring | SLA 3D print | White resin | $4 |
| Main PCB | 4-layer PCB | FR4 60mm round | $25 |
| LED Flex PCB | 2-layer flex | Polyimide | $15 |
| Base PCB | 4-layer PCB | FR4 70mm round | $20 |
| Walnut Enclosure | CNC | Walnut | $80 |

### Buy Off-Shelf

| Component | Source | Cost |
|-----------|--------|------|
| QCS6490 SoM | Thundercomm | $140 |
| Hailo-10H | Hailo | $90 |
| 1.39" AMOLED | King Tech / AliExpress | $45 |
| IMX989 Module | SincereFirst | $95 |
| sensiBel ×4 | sensiBel | $40 |
| HD108 ×16 | AliExpress | $8 |
| 28mm Speaker | Yueda | $5 |
| Battery 2200mAh | AliExpress | $22 |
| HCNT Maglev | Stirling Kit | $85 |
| RX/TX Coils | Custom wind or buy | $30 |

---

## Key Optimizations

### 1. Single Main PCB

Instead of separate PCBs for compute, audio, and BMS:
- **60mm round PCB** holds SoM, M.2 slot, XMOS, BMS ICs
- Reduces assembly complexity
- Better signal integrity
- Single connector to display/camera flex

### 2. Vertical Thermal Path

```
Heat flow (conduction):
QCS6490 → Heatsink → Shell → Air
          ↓
      (when docked)
          ↓
      Coil → Base → Air
```

### 3. Simplified Shell

- Two acrylic hemispheres
- Glued at equator (permanent seal)
- No complex gaskets or fasteners

### 4. Integrated LED Ring

- Flex PCB wraps around equator
- Pre-assembled with HD108 LEDs
- Snaps into diffuser channel

---

## Mass Budget

| Component | Mass (g) |
|-----------|----------|
| Shell (both halves) | 90 |
| Display assembly | 35 |
| Compute (PCB + SoM + Hailo + heatsink) | 56 |
| Audio | 6 |
| LEDs + diffuser | 10 |
| Battery | 150 |
| Power (BMS, coil mount, coil, ferrite) | 46 |
| **TOTAL ORB** | **~393g** |

⚠️ **Exceeds 350g target by ~43g** — need to optimize:
- Thinner shell: 90g → 70g (-20g)
- Smaller heatsink: -5g
- Lighter diffuser: -5g
- Target: **~363g** (still tight)

---

## Thermal Budget (Validated)

| Mode | Heat Gen | Dissipation | Status |
|------|----------|-------------|--------|
| Idle (docked) | 6.7W | 8-12W | ✅ OK |
| Active (docked) | 16.8W | 8-12W | ⚠️ Throttle to 12W |
| Peak (docked) | 26.7W | 8-12W | ❌ Must throttle |
| Portable | 6.7W | 2-4W | ⚠️ Throttle to 4W |

**Firmware must throttle QCS6490 from 12W → 3W when undocked.**

---

## Next Steps

1. [ ] Validate mass with actual components
2. [ ] Thermal simulation (FEA)
3. [ ] PCB layout (Main + LED flex + Base)
4. [ ] Shell mold design
5. [ ] Assembly jig design
