# Kagami Orb V3 — Assembly Guide

## Prerequisites

Before beginning assembly, ensure you have:

### Components
- All items from [V3 BOM](bom.html) (or [CSV](hardware/kagami_orb_bom.csv))
- 3D printed parts (see [CAD Viewer](cad/visualization/viewer.html))
- Custom PCB or breadboard prototype

### Tools
- Soldering station (fine tip, temperature controlled)
- Multimeter
- Precision screwdriver set (Phillips #0, #00)
- Tweezers (ESD-safe)
- Heat gun (for heat shrink)
- Hot glue gun
- IPA and lint-free wipes
- ESD mat and wrist strap

### Software
- QCS6490 SDK (Thundercomm)
- Hailo SDK
- SSH client
- Serial terminal (for debug)

---

## V3 Exploded Assembly Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     KAGAMI ORB V3 — EXPLODED ASSEMBLY                           │
│                            85mm SEALED SPHERE                                   │
│                                                                                  │
│   TOP (Display Side)                                                             │
│   ══════════════════                                                             │
│                                                                                  │
│                         ╭───────────────────╮                                   │
│                        │  DIELECTRIC MIRROR  │ ← 74mm touch-through film        │
│                         ╰─────────┬─────────╯                                   │
│                                   │                                              │
│                         ╭─────────┴─────────╮                                   │
│                        │   2.8" ROUND AMOLED │ ← 480×480 living eye display     │
│                        │   (72mm active)     │                                   │
│                         ╰─────────┬─────────╯                                   │
│                                   │                                              │
│                         ┌─────────┴─────────┐                                   │
│                        │    DISPLAY MOUNT    │ ← Grey Pro, 78×6mm               │
│                        │  ┌───────────────┐  │                                   │
│                        │  │   📷 IMX989   │  │ ← 50.3MP hidden in pupil         │
│                        │  │   (8mm hole)  │  │                                   │
│                        │  └───────────────┘  │                                   │
│                         └─────────┬─────────┘                                   │
│                                   │                                              │
│                         ┌─────────┴─────────┐                                   │
│                        │    QCS6490 SoM      │ ← 40×35mm, 12 TOPS               │
│                        │  ┌───────────────┐  │                                   │
│                        │  │  HAILO-10H    │  │ ← M.2 2242, 40 TOPS             │
│                        │  │  (M.2 slot)   │  │                                   │
│                        │  └───────────────┘  │                                   │
│                         └─────────┬─────────┘                                   │
│                                   │                                              │
│                         ╭─────────┴─────────╮                                   │
│                        ╱   INTERNAL FRAME    ╲ ← CF-PETG, 65×45mm              │
│                       ╱     (main structure)  ╲                                 │
│                       │  🎤×4 sensiBel mics   │ ← Optical MEMS array            │
│                       │  🔊 XMOS XVF3800      │ ← Audio DSP                     │
│                        ╲                      ╱                                  │
│                         ╰─────────┬─────────╯                                   │
│                                   │                                              │
│       ┌───────────────────────────┼───────────────────────────┐                 │
│       │                           │                           │                 │
│   ┌───┴───┐               ┌───────┴───────┐               ┌───┴───┐            │
│   │ LED   │               │   DIFFUSER    │               │  BMR  │            │
│   │ RING  │               │    RING       │               │SPEAKER│            │
│   │ 16×HD │               │  (white)      │               │ 28mm  │            │
│   │  108  │               │               │               │       │            │
│   └───────┘               └───────────────┘               └───────┘            │
│                                   │                                              │
│                         ┌─────────┴─────────┐                                   │
│                        │   BATTERY CRADLE    │ ← Tough 2000, 63×43mm            │
│                        │  ┌───────────────┐  │                                   │
│                        │  │  2200mAh 3S   │  │ ← 24Wh LiPo (VERIFIED fits)      │
│                        │  │  + BQ25895    │  │ ← Charger IC                     │
│                        │  │  + BQ40Z50    │  │ ← Fuel gauge                     │
│                        │  └───────────────┘  │                                   │
│                         └─────────┬─────────┘                                   │
│                                   │                                              │
│                         ┌─────────┴─────────┐                                   │
│                        │   COIL MOUNT        │ ← Tough 2000, 72×6mm             │
│                        │  ┌───────────────┐  │                                   │
│                        │  │   RX COIL     │  │ ← 70mm Litz, 18 turns            │
│                        │  │   70mm        │  │                                   │
│                        │  └───────────────┘  │                                   │
│                        │  ┌───────────────┐  │                                   │
│                        │  │   FERRITE     │  │ ← 60×60mm Fair-Rite              │
│                        │  └───────────────┘  │                                   │
│                         └─────────┬─────────┘                                   │
│                                   │                                              │
│   ═══════════════════════════════════════════════════════════════════════       │
│                          15mm LEVITATION GAP                                     │
│   ═══════════════════════════════════════════════════════════════════════       │
│                                   │                                              │
│   BASE STATION                    │                                              │
│   ════════════                    │                                              │
│                         ╭─────────┴─────────╮                                   │
│                        │   PTZ TORQUE COILS  │ ← 4× peripheral coils            │
│                        │      ◉   ◉   ◉   ◉  │   (pan/tilt control)            │
│                         ╰─────────┬─────────╯                                   │
│                                   │                                              │
│                         ╭─────────┴─────────╮                                   │
│                        │     TX COIL         │ ← 70mm Litz, 14 turns            │
│                        │   (wireless power)  │                                   │
│                         ╰─────────┬─────────╯                                   │
│                                   │                                              │
│                         ┌─────────┴─────────┐                                   │
│                        │    HCNT MAGLEV      │ ← 500g levitation module         │
│                        │   (electromagnet)   │                                   │
│                         └─────────┬─────────┘                                   │
│                                   │                                              │
│                         ┌─────────┴─────────┐                                   │
│                        │   ESP32-S3 + PWR    │ ← Base controller                 │
│                        │   Hall sensors ×4   │ ← Orientation feedback           │
│                         └─────────┬─────────┘                                   │
│                                   │                                              │
│                      ╔════════════╧════════════╗                                │
│                      ║    WALNUT ENCLOSURE     ║ ← CNC, 180×25mm                │
│                      ║   ○ ○ ○ ○ ○ ○ ○ ○      ║ ← SK6812 status ring (×8)      │
│                      ╚═════════════════════════╝                                │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Assembly Sequence Summary

| Phase | Components | Time Est. | Difficulty |
|-------|-----------|-----------|------------|
| **1. Base Station** | Enclosure, Maglev, TX Coil, ESP32, PTZ coils | 3 hours | ⭐⭐ |
| **2. Power Assembly** | RX Coil, Ferrite, Battery, BMS, Cradle | 2 hours | ⭐⭐ |
| **3. Compute Stack** | QCS6490, Hailo-10H, IMX989, thermal | 2 hours | ⭐⭐⭐ |
| **4. Audio/Sensors** | sensiBel mics, XMOS, BMR speaker | 1.5 hours | ⭐⭐ |
| **5. Display Assembly** | AMOLED, dielectric mirror, mount | 1 hour | ⭐⭐⭐ |
| **6. LED Ring** | HD108 ×16, diffuser ring, mount | 1 hour | ⭐⭐ |
| **7. Frame Integration** | Internal frame, cable routing | 1.5 hours | ⭐⭐ |
| **8. Shell Assembly** | Hemispheres, adhesive seal | 1 hour | ⭐⭐⭐ |
| **9. Calibration** | Levitation tune, PTZ calibration, software | 2 hours | ⭐⭐⭐ |
| **TOTAL** | | **~15 hours** | |

### Interactive 3D View

View the complete assembly in 3D: **[WebGL Part Viewer](cad/visualization/viewer.html)**

---

## Phase 1: Base Station Assembly (3 hours)

### 1.1 Walnut Enclosure Preparation

1. CNC machine walnut block to 180mm diameter, 25mm height
2. Create central cavity for electronics (160mm × 20mm)
3. Mill LED ring channel on top surface
4. Drill cable entry hole (side, for power)
5. Sand and apply finish (tung oil recommended)

### 1.2 Maglev Module Installation

1. Test HCNT module with 24V supply
2. Position centrally in enclosure
3. Secure with M3 screws (4×)
4. Wire to ESP32 control board

### 1.3 TX Coil & PTZ Array

```
TX Coil Winding:
• 70mm diameter
• 14 turns Litz wire
• 40μH inductance
• Center-tapped for bq500215

PTZ Torque Coils (×4):
• 20mm diameter each
• 100μH inductance
• Positioned at 0°, 90°, 180°, 270°
• Connected to DRV8833 H-bridge
```

### 1.4 Base Electronics

1. Mount ESP32-S3-WROOM-1-N8R8
2. Install DRV8833 motor drivers (×2)
3. Connect 4× DRV5053 Hall sensors (orientation feedback)
4. Wire SK6812 LED ring (8 LEDs)
5. Test "thinking" animation pattern

---

## Phase 2: Power Assembly (2 hours)

### 2.1 RX Coil Mount

1. Print coil mount (Tough 2000)
2. Position 60×60mm ferrite sheet
3. Wind RX coil: 70mm, 18 turns Litz, 85μH
4. Secure coil in mount recess
5. Route leads through channel

### 2.2 Battery & BMS

1. Test 2200mAh 3S LiPo (should read ~11.1V) — max size 55×35×20mm
2. Solder BQ25895 charge circuit
3. Solder BQ40Z50 fuel gauge
4. Connect protection circuits
5. Mount in battery cradle with foam padding
6. Secure with velcro straps

### 2.3 Wireless Power Test

```
Bench test before assembly:
1. Apply 24V to TX coil via bq500215
2. Position RX 15mm above TX
3. Measure received voltage (should be 15-20V)
4. Verify thermal: coils should stay <50°C
5. Check efficiency: target 75%+
```

---

## Phase 3: Compute Stack (2 hours)

### 3.1 QCS6490 SoM Setup

1. Flash Thundercomm firmware
2. Test boot sequence via serial
3. Verify WiFi 6E connectivity
4. Test NPU with sample inference

### 3.2 Hailo-10H Installation

1. Insert M.2 2242 module
2. Secure with retention screw
3. Test PCIe link (should show 4-lane Gen3)
4. Verify 40 TOPS benchmark

### 3.3 IMX989 Camera

1. Mount camera module behind display
2. Route flex cable to SoM
3. Align with 8mm display aperture
4. Test capture at 50.3MP

### 3.4 Thermal Management

```
Thermal stack (critical!):
1. Apply thermal pad to QCS6490 (1mm, 6W/mK)
2. Install 14×14mm heatsink
3. Apply graphite sheet to internal frame top
4. Ensure thermal path to shell

⚠️ Sealed design means NO airflow!
   Heat must conduct to shell surface.
```

---

## Phase 4: Audio/Sensors (1.5 hours)

### 4.1 sensiBel Microphone Array

1. Mount 4× SBM100B at 90° spacing
2. Connect to XMOS XVF3800 via TDM
3. Test -26dB SNR (should be industry-leading)
4. Verify beamforming direction

### 4.2 XMOS Voice Processor

1. Connect XVF3800 to QCS6490 via USB
2. Load AEC and beamforming firmware
3. Test wake word detection
4. Verify echo cancellation

### 4.3 BMR Speaker

1. Mount Tectonic TEBM28C20N-4 pointing down
2. Connect to MAX98357A I2S amp
3. Test frequency response (350Hz–20kHz)

---

## Phase 5: Display Assembly (1 hour)

### 5.1 Display Mount

1. Print display mount (Grey Pro, 25μm)
2. Clean mounting surfaces with IPA
3. Test fit with display module

### 5.2 AMOLED Installation

⚠️ **CRITICAL: The display MUST be 2.8" round (72mm active).
   The BOM lists "3.4 inch" which is an ERROR — 86mm won't fit in 85mm sphere!**

1. Position 2.8" AMOLED in recess
2. Align camera aperture with display center
3. Secure with retention clips
4. Route flex cable through channel

### 5.3 Dielectric Mirror

1. Cut 74mm disc from dielectric film
2. Clean both surfaces
3. Apply with no air bubbles
4. Test capacitive touch through mirror

---

## Phase 6: LED Ring (1 hour)

### 6.1 LED PCB Assembly

1. Position 16× HD108 LEDs on ring PCB
2. Solder with temperature-controlled iron (260°C max)
3. Connect 74AHCT125 level shifter (3.3V→5V)
4. Test all LEDs with rainbow pattern

### 6.2 Installation

1. Snap LED ring into mount
2. Install diffuser ring (white resin)
3. Connect to ESP32-S3 data line
4. Test "thinking" and "ambient" patterns

---

## Phase 7: Frame Integration (1.5 hours)

### 7.1 Component Mounting

1. Mount QCS6490 + Hailo on SoM platform
2. Secure battery cradle to frame
3. Position audio components
4. Route all cables through channels

### 7.2 Cable Management

```
Cable routing priority:
1. Power (thickest, route first)
2. High-speed (MIPI, PCIe - keep short)
3. Audio (shield from power)
4. GPIO/I2C (flexible routing)

Use kapton tape at crossings.
```

---

## Phase 8: Shell Assembly (1 hour)

### 8.1 Hemisphere Preparation

1. Clean 85mm acrylic hemispheres
2. Apply anti-fingerprint coating
3. Test fit with internal assembly

### 8.2 Final Seal

⚠️ **SEALED DESIGN — No access after this step!**

1. Final functional test (all systems)
2. Apply adhesive to hemisphere flange
3. Join hemispheres carefully
4. Cure adhesive per spec
5. Final exterior cleaning

---

## Phase 9: Calibration (2 hours)

### 9.1 Levitation Calibration

```bash
# Run levitation calibration
./calibrate_levitation.py --weight 350 --height 15

# Expected output:
# Levitation force: OK (420g capacity)
# Stability margin: 18%
# Gap height: 15.2mm ± 0.5mm
```

### 9.2 PTZ Calibration

```bash
# Calibrate PTZ system
./calibrate_ptz.py

# Steps:
# 1. Home position (level)
# 2. Pan 360° test
# 3. Tilt ±20° test
# 4. Hall sensor mapping
```

### 9.3 Software Setup

1. Flash production firmware
2. Configure WiFi credentials
3. Pair with kagami-hub
4. Test voice commands
5. Verify living eye animations

---

## Troubleshooting

| Issue | Likely Cause | Solution |
|-------|-------------|----------|
| Won't levitate | Weight >500g, magnet alignment | Check total weight, realign |
| Unstable float | Hall sensor calibration | Run levitation calibration |
| Overheating | Poor thermal path | Verify thermal pad contact |
| Display not working | Flex cable | Reseat connector, check for damage |
| No wireless charge | Coil misalignment | Center RX over TX, check gap |
| PTZ drift | Hall calibration | Run PTZ calibration |
| Audio echo | AEC config | Update XMOS firmware |

---

## Safety Warnings

⚠️ **Li-Po Battery**: Risk of fire if damaged. Never puncture, crush, or overheat.

⚠️ **Magnetic Field**: Strong magnets present. Keep away from pacemakers, credit cards.

⚠️ **Sealed Enclosure**: Internal components not serviceable after assembly.

⚠️ **Thermal**: Surface may reach 45°C during heavy use. Normal operation.

---

## Changelog

### V3.0 (January 2026)
- Complete rewrite for V3 85mm SOTA design
- Updated all components to V3 BOM
- Added PTZ torque coil assembly
- Added sensiBel microphone array
- Fixed display size to 2.8" (72mm)
- Removed all CM4/Coral references
