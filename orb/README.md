# 🪞 Kagami Orb — The Floating Mirror

**Levitating Voice Assistant with Wireless Power and Interchangeable Bases**

A 120mm magnetically levitating sphere containing a full AI voice assistant,
wirelessly powered through any of multiple base stations placed throughout the home.

```
                          ╭───────────────╮
                         ╱ ∞   鏡   ∞   ∞ ╲
                        │∞ ● ● ● ● ● ● ● ∞│  ◄── Infinity Mirror Shell
                        │ ∞ ∞ ∞ ∞ ∞ ∞ ∞ ∞ │      Seven Colony Lights
                         ╲ ∞ ∞ ∞ ∞ ∞ ∞ ∞ ╱
                          ╰───────────────╯
                              ╱     ╲
                             ╱ ~~~~~ ╲         ◄── 15mm Levitation Gap
                          ══╱═════════╲══
                         ║  ◉ BASE ◉  ║        ◄── Maglev + Resonant Power
                         ╚═══════════════╝
```

## The Vision

Pick up the orb from your living room.
Carry it to your office.
Place it on the base there.
It rises, glows, becomes Kagami for that space.

One consciousness. Multiple physical locations. Seamless transition.

---

## Features

- **Magnetic Levitation** — Floats 15mm above base, rotates slowly
- **Custom Resonant Wireless Power** — 15W through 15mm gap (80mm Litz coils, 87-205kHz)
- **Multi-Base System** — Any base station activates the same orb
- **Infinity Mirror Shell** — Infinite depth illusion with 7 colony colors
- **Far-Field Voice** — 4-mic beamforming array
- **Bluetooth A2DP Speaker** — Stream music from any device
- **Audio Input to Kagami** — Streams captured audio to Kagami API for processing
- **Battery Backup** — 3,000mAh (33Wh) for transport between bases
- **WiFi 6E** — High-bandwidth connection from any location
- **Thermal Management** — Active airflow through magnetic bearings

---

## System Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              KAGAMI ORB ECOSYSTEM                                │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │           THE ORB               │
                    │                                 │
                    │  ┌─────────┐   ┌───────────┐   │
                    │  │ CM4/Pi4 │   │   Coral   │   │
                    │  │  Lite   │   │    TPU    │   │
                    │  └────┬────┘   └─────┬─────┘   │
                    │       │              │         │
                    │  ┌────┴──────────────┴────┐   │
                    │  │    Custom Carrier PCB   │   │
                    │  │  • ReSpeaker 4-mic     │   │
                    │  │  • NeoPixel Ring       │   │
                    │  │  • Battery Management  │   │
                    │  │  • Resonant RX Coil    │   │
                    │  │  • WiFi 6E Module      │   │
                    │  └────────────┬───────────┘   │
                    │               │               │
                    │  ┌────────────┴───────────┐   │
                    │  │  10,000mAh Li-Po Pack  │   │
                    │  └────────────────────────┘   │
                    │                               │
                    └───────────────┬───────────────┘
                                    │ 15mm gap
                    ┌───────────────┴───────────────┐
                    │         BASE STATION           │
                    │                                │
                    │  ┌──────────┐  ┌───────────┐  │
                    │  │ Maglev   │  │ Resonant  │  │
                    │  │ Platform │  │ TX 20W    │  │
                    │  └──────────┘  └───────────┘  │
                    │                                │
                    └───────────────┬────────────────┘
                                    │ 24V DC
                                    │
                    ┌───────────────┴───────────────┐
                    │         60W POWER SUPPLY       │
                    └────────────────────────────────┘


                    BASE STATIONS (Multiple)

     ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
     │ Living  │    │ Kitchen │    │ Office  │    │ Bedroom │
     │  Room   │    │         │    │         │    │         │
     └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘
          │              │              │              │
          └──────────────┴──────────────┴──────────────┘
                                │
                    ┌───────────┴───────────┐
                    │    HOME NETWORK        │
                    │    (WiFi 6E Mesh)      │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │    KAGAMI API          │
                    │    kagami.local:8001   │
                    └───────────────────────┘
```

### Communication Flow

```
                    THE ORB
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
┌─────────┐      ┌─────────┐      ┌─────────┐
│ WiFi 6E │      │ BLE 5.3 │      │ IR Recv │
│ Primary │      │ Backup  │      │ Pairing │
└────┬────┘      └────┬────┘      └────┬────┘
     │                │                │
     └────────────────┼────────────────┘
                      │
              ┌───────┴───────┐
              │   KAGAMI API   │
              │                │
              │ • Voice proxy  │
              │ • State sync   │
              │ • Commands     │
              │ • Battery mon  │
              └───────────────┘
```

---

## Hardware Specifications

### The Orb

| Specification | Value |
|--------------|-------|
| Diameter | 120mm (4.72") |
| Weight | 380g (13.4 oz) target |
| Shell Material | Chrome-mirror acrylic hemisphere + two-way mirror film |
| Compute | Raspberry Pi CM4 Lite (4GB) or Pi 4 Model A+ |
| AI Accelerator | Google Coral USB (4 TOPS) |
| Microphones | ReSpeaker 4-Mic Array (XMOS XVF3000) |
| LED Ring | SK6812 RGBW × 24 (internal) |
| Battery | 3,000mAh 3S Li-Po (11.1V nominal, 33Wh) |
| Power Input | Custom Resonant 15W (80mm Litz coils @ 87-205kHz) |
| WiFi | Intel AX210 WiFi 6E M.2 module |
| Bluetooth | BLE 5.3 (via AX210) |
| Storage | 32GB eMMC (on CM4) or microSD |

### Base Station

| Specification | Value |
|--------------|-------|
| Dimensions | 180mm × 180mm × 45mm |
| Weight Capacity | 500g floating |
| Levitation Gap | 15mm nominal |
| Magnetic Field | Neodymium N52 + active coils |
| Power Output | 15W Resonant @ 87-205kHz through 15mm gap |
| Power Input | 24V DC 2.5A (60W) |
| Material | CNC walnut + brass accents |

### Power Budget

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORB POWER BUDGET                              │
├─────────────────────────────────────────────────────────────────────┤
│ Component                    │ Idle      │ Active    │ Peak        │
├──────────────────────────────┼───────────┼───────────┼─────────────┤
│ CM4/Pi4 (underclocked)       │ 2.0W      │ 3.5W      │ 6.0W        │
│ Coral USB TPU                │ 0.5W      │ 2.0W      │ 2.5W        │
│ ReSpeaker 4-Mic              │ 0.2W      │ 0.3W      │ 0.3W        │
│ SK6812 × 24 (breathing)      │ 0.5W      │ 2.0W      │ 3.5W        │
│ WiFi 6E Module               │ 0.3W      │ 1.0W      │ 2.0W        │
│ Battery Management           │ 0.1W      │ 0.1W      │ 0.1W        │
│ Miscellaneous                │ 0.4W      │ 0.6W      │ 1.0W        │
├──────────────────────────────┼───────────┼───────────┼─────────────┤
│ TOTAL                        │ 4.0W      │ 9.5W      │ 15.4W       │
└──────────────────────────────┴───────────┴───────────┴─────────────┘

Resonant Input: 20W TX → 15W RX (~75% efficiency through 15mm gap with maglev magnets)
  - Coupling coefficient k ≈ 0.82 (80mm coils, 15mm gap)
  - Ferrite shielding required between resonant coils and maglev magnets
Battery: 3,000mAh @ 11.1V = 33Wh → ~8 hours idle, ~3.5 hours active

Thermal Budget:
- Heat dissipation required: ~13W continuous (10W compute + 3W charging loss)
- Convection through levitation gap: ~4W
- Internal heatsink to shell: ~6W
- Active air circulation (magnetic): ~4W
- Charging coil heat (at RX): ~3W (requires thermal management)
```

---

## Electromagnetic Compatibility

### Why Standard Qi Won't Work

Standard Qi EPP (Extended Power Profile) is designed for 0-8mm gaps with no magnetic interference.
The Kagami Orb presents two challenges:

1. **15mm air gap** — Exceeds Qi spec maximum coupling distance
2. **Maglev magnets** — N52 neodymium triggers FOD (Foreign Object Detection) false alarms

### Custom Resonant Charging Solution

| Parameter | Standard Qi EPP | Kagami Orb Custom |
|-----------|----------------|-------------------|
| Operating Frequency | 87-205 kHz | 140 kHz (tuned) |
| Coil Diameter | 40-50mm | 80mm (both TX/RX) |
| Air Gap | 0-8mm spec | 15mm actual |
| Coupling Coefficient | k > 0.9 required | k ≈ 0.82 achieved |
| Power Transfer | 15W | 15W (20W TX input) |
| Efficiency | 85-92% | 72-78% |
| FOD | Standard Qi protocol | Disabled (magnets calibrated out) |

### Coupling Coefficient Math

```
k ≈ 1 / (1 + (2d/D)²)^(3/2)

Where:
  d = gap distance = 15mm
  D = coil diameter = 80mm

k ≈ 1 / (1 + (30/80)²)^(3/2)
k ≈ 1 / (1 + 0.14)^(3/2)
k ≈ 1 / 1.22
k ≈ 0.82
```

### Frequency Separation

| System | Frequency Range | Interference Risk |
|--------|-----------------|-------------------|
| Maglev Control | DC - 1 kHz | None (baseband) |
| Resonant Charging | 87-205 kHz | Low (narrowband) |
| WiFi 6E | 5.9-7.1 GHz | None (far separated) |
| Bluetooth | 2.4 GHz | None (far separated) |

**Conclusion:** Frequency separation is favorable. No cross-system interference expected.

### Ferrite Shielding Requirements

Ferrite shields prevent magnetic coupling between maglev permanent magnets and charging coils:

- **Material:** Mn-Zn ferrite (Fair-Rite 78 material) for <1MHz
- **Thickness:** ≥0.8mm
- **Placement:** Between resonant coils and maglev magnets on both TX and RX
- **Effect:** Redirects charging flux away from permanent magnets

---

## Bluetooth Audio System

### A2DP Speaker Mode

The orb functions as a standard Bluetooth speaker:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         BLUETOOTH AUDIO ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────────┘

    Phone/Laptop                      Kagami Orb                     Speaker
    ┌─────────┐                      ┌─────────────┐                ┌────────┐
    │  A2DP   │────Bluetooth────────▶│  AX210 BT   │───I2S─────────▶│ 28mm   │
    │  Source │                      │  A2DP Sink  │                │ Driver │
    └─────────┘                      └─────────────┘                └────────┘
                                           │
                                           │ Audio stream
                                           ▼
                                    ┌─────────────┐
                                    │  PipeWire   │
                                    │  Audio Mix  │
                                    └──────┬──────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │  MAX98357A  │
                                    │  Class-D    │
                                    └─────────────┘
```

### Audio Input Streaming

Microphone audio streams to Kagami API for voice processing:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AUDIO INPUT STREAMING                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

    ReSpeaker 4-Mic                  Kagami Orb                    Kagami API
    ┌─────────────┐                 ┌─────────────┐               ┌───────────┐
    │ XMOS XVF3000│───I2S──────────▶│   ALSA      │───WebSocket──▶│  Voice    │
    │ Beamforming │                 │ 16kHz/16bit │    Opus       │  Pipeline │
    └─────────────┘                 └─────────────┘               └───────────┘
                                          │
                                          │ Local processing
                                          ▼
                                   ┌─────────────┐
                                   │ RNNoise VAD │
                                   │ Wake Word   │
                                   └─────────────┘
```

### Software Configuration

```toml
# config/orb.toml additions

[bluetooth]
a2dp_sink_enabled = true
a2dp_source_enabled = false
discoverable = true
discoverable_timeout = 120  # seconds
pairing_mode = "secure_simple"

[audio_streaming]
stream_to_api = true
format = "opus"
sample_rate = 16000
channels = 1
bitrate = 24000
vad_threshold = 0.4
websocket_endpoint = "wss://kagami.local:8001/audio/stream"

[audio_output]
default_sink = "speaker"
bluetooth_priority = true  # A2DP takes priority when connected
volume_limit = 85  # percent, for hearing protection
```

---

## Detailed Component List

### THE ORB — Complete Bill of Materials

#### Core Compute

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 1 | Raspberry Pi CM4 Lite | 4GB RAM, No eMMC, No WiFi | CM4104000 | 1 | $45 | raspberrypi.com |
| 2 | CM4 IO Board (Modified) | Carrier board (will be custom) | CM4IO | 1 | $35 | raspberrypi.com |
| 3 | Google Coral USB | Edge TPU 4 TOPS | G950-00139-01 | 1 | $60 | coral.ai |
| 4 | Samsung EVO 32GB | microSD for OS | MB-ME32GA | 1 | $8 | amazon.com |

#### Audio System

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 5 | ReSpeaker 4-Mic Array | XMOS XVF3000 beamforming | 107990056 | 1 | $35 | seeedstudio.com |
| 6 | MAX98357A Amp | I2S Class-D 3W mono | Adafruit 3006 | 1 | $6 | adafruit.com |
| 7 | Speaker 28mm | Full-range 4Ω 3W | CUI CSS-10308N | 1 | $4 | digikey.com |

#### LED System

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 8 | SK6812 RGBW Ring | 24 LED ring, 68mm OD | WS2812-24 | 1 | $12 | adafruit.com |
| 9 | NeoPixel Level Shifter | 74AHCT125 breakout | Adafruit 1787 | 1 | $2 | adafruit.com |

#### Wireless System

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 10 | Intel AX210 | WiFi 6E + BT5.3 M.2 | AX210NGW | 1 | $20 | amazon.com |
| 11 | M.2 to USB Adapter | For CM4 without M.2 | - | 1 | $8 | amazon.com |
| 12 | WiFi Antenna | 6GHz capable, internal | MHF4 pigtail | 2 | $5 | amazon.com |

#### Power System — Custom Resonant Charging

**IMPORTANT:** Standard Qi EPP will NOT work at 15mm gap with maglev magnets (FOD false alarms).
Custom resonant coupling with 80mm coils achieves k ≈ 0.82 and ~75% efficiency.

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 13 | Resonant RX Coil 80mm | Litz wire, 20 turns, 100μH | Custom wind | 1 | $25 | wurth.com |
| 14 | Resonant RX Controller | 15W receiver IC | bq51025 | 1 | $12 | ti.com |
| 15 | Resonant Capacitor | Tuning to 140kHz | 1μF NPO | 2 | $3 | digikey.com |
| 16 | Ferrite Shield | Mn-Zn, 0.8mm, 90mm dia | Custom cut | 1 | $15 | fair-rite.com |
| 17 | BMS 3S 20A | Li-Po balance charger | HX-3S-20A | 1 | $8 | aliexpress.com |
| 18 | Li-Po Pack 3S | 3,000mAh 11.1V (33Wh) | Custom pack | 1 | $15 | batteryspace.com |
| 19 | 5V 3A Buck | From battery to logic | MP1584EN | 1 | $3 | amazon.com |
| 20 | USB-C PD Trigger | For direct charging | IP2721 | 1 | $3 | aliexpress.com |

#### Infinity Mirror Shell

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 18 | Acrylic Hemisphere 120mm | Clear, optical grade | Custom | 2 | $25 | tapplastics.com |
| 19 | Two-Way Mirror Film | 70/30 reflective | Gila PR285 | 1 | $15 | amazon.com |
| 20 | Chrome Mirror Vinyl | For inner hemisphere | Oracal 351 | 1 | $10 | amazon.com |
| 21 | Diffuser Ring | 3D printed, white PETG | Custom | 1 | $5 | Form 4 |

#### Thermal Management

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 22 | Copper Heatsink | For CM4 SoC | ICK-SMP-15 | 1 | $5 | digikey.com |
| 23 | Thermal Pad 3mm | 6W/mK silicone | Thermal Grizzly | 1 | $8 | amazon.com |
| 24 | Thermal Adhesive | Arctic Silver | AS-5 | 1 | $6 | amazon.com |

#### Structural

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 25 | Internal Frame | 3D printed, CF-PETG | Custom | 1 | $15 | Form 4 |
| 26 | LED Mounting Ring | 3D printed, black | Custom | 1 | $5 | Form 4 |
| 27 | Battery Cradle | 3D printed, PETG | Custom | 1 | $5 | Form 4 |
| 28 | M2 Standoffs | Brass, various | - | 20 | $5 | amazon.com |
| 29 | Neodymium Ring | For maglev docking | N52 | 1 | $15 | kjmagnetics.com |

**ORB SUBTOTAL: ~$510**

---

### BASE STATION — Complete Bill of Materials

#### Magnetic Levitation Platform

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 30 | Maglev Module | 500g capacity, 15mm | ZT-HX500 | 1 | $180 | aliexpress.com |
| 31 | 24V 2.5A PSU | 60W desktop adapter | Mean Well GST60A24 | 1 | $25 | digikey.com |
| 32 | DC Barrel Jack | 5.5×2.1mm panel mount | PJ-002AH | 1 | $2 | digikey.com |

#### Wireless Power Transmitter — Custom Resonant

**IMPORTANT:** Standard Qi EPP will NOT work. Custom resonant TX coils required.

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 33 | Resonant TX Coil 80mm | Litz wire, 15 turns, 47μH | Custom wind | 1 | $25 | wurth.com |
| 34 | Resonant TX Driver | 20W full-bridge | bq500215 | 1 | $18 | ti.com |
| 35 | Resonant Capacitor | Tuning to 140kHz | 2.2μF NPO | 2 | $3 | digikey.com |
| 36 | Ferrite Shield | Mn-Zn, 0.8mm, 100mm dia | Custom cut | 1 | $18 | fair-rite.com |
| 37 | Position Sensing | Hall effect array | DRV5053 × 4 | 4 | $8 | digikey.com |

#### Base Controller

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 36 | ESP32-S3 | Base station MCU | ESP32-S3-WROOM | 1 | $5 | digikey.com |
| 37 | Status LEDs | Base ring indicator | SK6812 × 8 | 1 | $4 | adafruit.com |
| 38 | USB-C Port | Programming/debug | USB4110-GF-A | 1 | $1 | lcsc.com |

#### Enclosure Materials

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 39 | Walnut Block | 180×180×50mm | Premium | 1 | $40 | rockler.com |
| 40 | Brass Ring | 鏡 engraved accent | Custom | 1 | $15 | Glowforge |
| 41 | Rubber Feet | Anti-slip | 3M Bumpon | 4 | $2 | amazon.com |
| 42 | Felt Liner | Non-scratch top | Self-adhesive | 1 | $3 | amazon.com |

#### Misc Hardware

| # | Component | Description | Part Number | Qty | Unit Price | Source |
|---|-----------|-------------|-------------|-----|------------|--------|
| 43 | Wire 20AWG | Internal power | Silicone | 2m | $3 | amazon.com |
| 44 | Wire 24AWG | Signal wiring | Silicone | 2m | $2 | amazon.com |
| 45 | Heat Shrink | Various sizes | Kit | 1 | $5 | amazon.com |
| 46 | M3 Screws | Mounting | SS | 20 | $3 | amazon.com |

**BASE STATION SUBTOTAL: ~$360**

---

### COMPLETE SYSTEM PRICING

| Configuration | Components | Price |
|--------------|------------|-------|
| Orb Only | All orb components | $510 |
| Single Base | One base station | $360 |
| **Starter Kit** | **1 Orb + 1 Base** | **$870** |
| Two-Base | 1 Orb + 2 Bases | $1,230 |
| Three-Base | 1 Orb + 3 Bases | $1,590 |
| **Whole-Home (4 Bases)** | **1 Orb + 4 Bases** | **$1,950** |

---

## Fabrication Guide

### Form 4 (Resin 3D Printing) — Internal Structure

All printed in Formlabs **Grey Pro** or **Tough 2000**:

| Part | Material | Layer | Time | Notes |
|------|----------|-------|------|-------|
| Internal Frame | Tough 2000 | 50μm | 8h | Load-bearing, battery mount |
| LED Mounting Ring | Grey Pro | 25μm | 3h | Precision fit for SK6812 |
| Diffuser Ring | White | 50μm | 2h | Light diffusion layer |
| Battery Cradle | Tough 2000 | 50μm | 4h | Vibration dampening |
| CM4 Mount Bracket | Grey Pro | 50μm | 2h | Heat sink clearance |
| Resonant Coil Mount | Tough 2000 | 50μm | 1h | Precise positioning (80mm) |

**TOTAL PRINT TIME: ~20 hours**

### Glowforge (Laser Cutting) — Decorative Elements

| Part | Material | Power | Speed | Notes |
|------|----------|-------|-------|-------|
| Brass Accent Ring | 0.5mm brass | 100% | 200 | 鏡 engraving |
| Diffuser Pattern | White acrylic 3mm | 30% | 450 | Seven-point pattern |
| Base Top Veneer | Walnut 1/8" | 50% | 300 | Optional inlay |
| Cable Gasket | Silicone sheet | 20% | 500 | Clean pass-through |

### CNC Machining — Base Enclosure

**Option A: DIY with Shapeoko/X-Carve**
- Walnut block: 180×180×50mm
- Pocket for maglev module: 120mm dia × 35mm deep
- Cable channel: 20mm wide
- Finish: Food-safe oil + wax

**Option B: Commission (Recommended)**
- Xometry or Fictiv
- Material: American Black Walnut
- Finish: Clear coat
- Est. Cost: $150-200 for professional CNC

### Shell Assembly Procedure

```
INFINITY MIRROR ASSEMBLY (THE MAGIC)

1. OUTER HEMISPHERE (The Observer)
   ┌─────────────────────────────────────────────────────────┐
   │                                                         │
   │   Clean acrylic hemisphere (120mm)                      │
   │   Apply two-way mirror film to INSIDE                   │
   │   Result: 70% reflective outside, 30% transmissive      │
   │                                                         │
   │   You see into the orb dimly                            │
   │   The orb reflects you and the room                     │
   │                                                         │
   └─────────────────────────────────────────────────────────┘

2. LED RING LAYER (The Light Source)
   ┌─────────────────────────────────────────────────────────┐
   │                                                         │
   │           ╭───────────────────────╮                     │
   │          │ ● ● ● ● ● ● ● ● ● ● ●│    SK6812 × 24       │
   │          │ ●                   ● │                      │
   │          │ ●    DIFFUSER      ● │    White 3D print    │
   │          │ ●      RING        ● │    inside LED ring   │
   │          │ ●                   ● │                      │
   │          │ ● ● ● ● ● ● ● ● ● ● ●│                      │
   │           ╰───────────────────────╯                     │
   │                                                         │
   │   LEDs face outward toward outer shell                  │
   │   Diffuser softens hotspots                             │
   │                                                         │
   └─────────────────────────────────────────────────────────┘

3. INNER HEMISPHERE (The Mirror)
   ┌─────────────────────────────────────────────────────────┐
   │                                                         │
   │   Smaller hemisphere or bowl (100mm)                    │
   │   Apply chrome mirror vinyl to OUTSIDE                  │
   │   Result: 90%+ reflective surface                       │
   │                                                         │
   │   Light bounces back toward outer shell                 │
   │   Creates infinite reflection tunnel                    │
   │                                                         │
   └─────────────────────────────────────────────────────────┘

4. THE INFINITY EFFECT
   ┌─────────────────────────────────────────────────────────┐
   │                                                         │
   │        OBSERVER                                         │
   │           ║                                             │
   │           ║ Light path                                  │
   │           ▼                                             │
   │   ┌──────────────────┐ ◄── Outer shell (70% mirror)    │
   │   │ ∞ ∞ ∞ ∞ ∞ ∞ ∞ ∞│                                  │
   │   │∞ ┌────────────┐ ∞│                                  │
   │   │  │ ●●●●●●●●●● │  │ ◄── LED Ring (light source)     │
   │   │  │ ●        ● │  │                                  │
   │   │  │ ● CHROME ● │  │ ◄── Inner mirror (90% mirror)   │
   │   │  │ ●        ● │  │                                  │
   │   │  │ ●●●●●●●●●● │  │                                  │
   │   │∞ └────────────┘ ∞│                                  │
   │   │ ∞ ∞ ∞ ∞ ∞ ∞ ∞ ∞│                                  │
   │   └──────────────────┘                                  │
   │                                                         │
   │   Light bounces: Inner mirror → Outer → Inner → ...    │
   │   Each bounce loses 30% through outer shell            │
   │   Result: Diminishing rings receding into infinity     │
   │                                                         │
   └─────────────────────────────────────────────────────────┘
```

---

## Software Architecture

### Orb Firmware

Same as Kagami Hub, with additions:

```toml
# config/orb.toml

[general]
name = "Kagami Orb"
mode = "floating"  # vs "docked"

[power]
battery_enabled = true
battery_low_threshold = 20
qi_power_min_watts = 10
sleep_when_undocked = false

[levitation]
rotation_enabled = true
rotation_rpm = 2.0
dock_detection = "hall_effect"

[network]
wifi_6e_enabled = true
preferred_band = "6GHz"
fallback_band = "5GHz"
roaming_enabled = true  # For multi-base

[audio]
beamforming = true
noise_suppression = "rnnoise"
vad_sensitivity = 0.6

[audio.streaming]
stream_to_api = true
format = "opus"
websocket_endpoint = "wss://kagami.local:8001/audio/stream"

[audio.bluetooth]
a2dp_sink_enabled = true
discoverable_timeout = 120
```

### Base Station Firmware (ESP32-S3)

```cpp
// base_station/main.cpp

#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>

// Levitation control
void controlLevitation() {
    // PID loop for stable levitation
    float height = readHallSensors();
    float error = TARGET_HEIGHT - height;
    float control = pid.compute(error);
    setCoilCurrent(control);
}

// Resonant power management
void manageWirelessPower() {
    if (orbPresent()) {
        // Custom resonant at 140kHz, NOT standard Qi EPP
        enableResonantTransmitter(20);  // 20W TX for 15W delivered
        calibrateFOD();  // Calibrate out maglev magnets
        reportStatusToOrb();
    } else {
        disableResonantTransmitter();
        enterLowPower();
    }
}

// Orb detection
bool orbPresent() {
    // Check for NFC tag or weight change
    return nfcDetected() || weightSensorTriggered();
}

// mDNS advertising
void advertiseMdns() {
    MDNS.begin("kagami-base-living");
    MDNS.addService("kagami-base", "tcp", 8081);
}
```

### Multi-Base Handoff Protocol

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         MULTI-BASE HANDOFF SEQUENCE                              │
└─────────────────────────────────────────────────────────────────────────────────┘

TIME    ORB STATE           BASE A (Old)        BASE B (New)        KAGAMI API
────    ─────────           ────────────        ────────────        ──────────
t+0     Docked @ A          Active              Standby             "Orb @ Living"
        │
t+1     User picks up       Detect removal      -                   "Orb portable"
        │                   Power down Qi
        │
t+2     Battery mode        -                   -                   (same)
        WiFi stays up       mDNS: available     mDNS: available
        │
t+3     User walks to B     -                   -                   (same)
        │
t+4     Placed on B         -                   Detect weight       -
        │                                       Hall sensors
        │
t+5     Magnetic capture    -                   Start levitation    -
        │
t+6     Qi charging         -                   Enable Qi TX        "Orb @ Office"
        │
t+7     Stable float        -                   Active              Update location
        Announce arrival                                            Push to clients
        │
t+8     Normal operation    Standby             Active              "Orb @ Office"
        (h(x) ≥ 0)          (await return)      (primary)           (continue)

────────────────────────────────────────────────────────────────────────────────
TIMING: Total handoff < 5 seconds
        No voice interruption (battery + WiFi continuous)
        Location update immediate via WebSocket
```

---

## Open & Hackable

The Kagami Orb is designed to be **modified, not locked down**. Every aspect of the system is documented and extensible.

### Open Source License

**Firmware:** MIT License
**Hardware:** CERN Open Hardware License v2 (permissive)
**Documentation:** CC BY 4.0

### GPIO Expansion

The CM4 exposes unused GPIO pins on a header inside the orb:

| Pin | Function | Status |
|-----|----------|--------|
| GPIO4 | Expansion I2C SDA | Available |
| GPIO5 | Expansion I2C SCL | Available |
| GPIO6 | User GPIO | Available |
| GPIO13 | User GPIO | Available |
| GPIO16 | User GPIO | Available |

**Add your own sensors:** Temperature, humidity, air quality, gesture detection.

### I2C Bus

Primary I2C bus (GPIO2/GPIO3) hosts system devices:
- 0x6A — BQ25895 battery charger
- 0x0B — BQ40Z50 fuel gauge
- 0x35 — ReSpeaker 4-Mic Array
- 0x48 — TMP117 temperature sensor

**Secondary I2C** (GPIO4/GPIO5) is reserved for user expansion. Add any I2C sensor at addresses 0x10–0x2F without conflict.

### SPI Interface

SPI0 is used for the LED ring (GPIO10 MOSI). The ring uses SK6812 protocol (self-clocking) so SPI1 remains available for user hardware.

### Custom Wake Words

The orb uses **openWakeWord** (Apache 2.0) by default. Training custom wake words:

1. Record 100+ samples of your phrase
2. Use `openwakeword-train` CLI to generate model
3. Place model in `/opt/kagami/models/wakeword/`
4. Update `config/orb.toml`:
   ```toml
   [voice]
   wakeword_model = "/opt/kagami/models/wakeword/my_custom.tflite"
   ```

### LED Pattern Customization

LED animations are defined in `/opt/kagami/patterns/`. Create new patterns:

```python
# patterns/custom.py
from kagami.led import Pattern, Color

class MyPattern(Pattern):
    def render(self, t: float, leds: list[Color]) -> list[Color]:
        # t is time in seconds, leds is 24-element array
        for i, led in enumerate(leds):
            hue = (t * 0.5 + i / 24) % 1.0
            leds[i] = Color.from_hsv(hue, 1.0, 0.8)
        return leds
```

### Safety Constraint Extension

The orb's safety system uses Control Barrier Functions: h(x) ≥ 0 must hold for all actions. To add custom constraints:

```python
# safety/custom.py
def h_humidity(humidity: float) -> float:
    """Safety constraint: electronics below 80% RH"""
    return 0.8 - humidity  # h(x) >= 0 when humidity < 80%

# Register in config
safety_constraints = [h_existing, h_humidity]
```

### Building Firmware

```bash
# Clone repository
git clone https://github.com/awkronos/kagami-orb-firmware.git
cd kagami-orb-firmware

# Setup Rust cross-compilation
rustup target add aarch64-unknown-linux-gnu
cargo install cross

# Build for CM4
cross build --release --target aarch64-unknown-linux-gnu

# Deploy to orb
scp target/aarch64-unknown-linux-gnu/release/kagami-orb kagami-orb.local:/opt/kagami/bin/
```

### OTA Updates

The orb accepts signed OTA updates. To build and sign your own:

```bash
# Generate your signing key (once)
kagami-sign keygen --output my_key.pem

# Sign firmware
kagami-sign firmware --key my_key.pem --input build/orb.bin --output orb-signed.bin

# Register key with orb (requires physical access)
ssh kagami-orb.local kagami-admin trust-key < my_key.pub

# Deploy OTA
kagami-ota push --target kagami-orb.local --firmware orb-signed.bin
```

### Community

- **GitHub:** https://github.com/awkronos/kagami-orb
- **Discord:** https://discord.gg/kagami
- **Contributing:** PRs welcome! See CONTRIBUTING.md

---

## LED Patterns

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ORB LED STATES                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

COLONY COLORS (24 LEDs divided into 7 zones):
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Zone │ Colony  │ Color                │ LEDs      │ RGB Value                   │
├───────┼─────────┼──────────────────────┼───────────┼─────────────────────────────┤
│   1   │ Spark   │ Phoenix Orange       │ 0-2       │ #FF6B35                     │
│   2   │ Forge   │ Forge Amber          │ 3-5       │ #FFB347                     │
│   3   │ Flow    │ Ocean Blue           │ 6-9       │ #4ECDC4                     │
│   4   │ Nexus   │ Bridge Purple        │ 10-13     │ #9B59B6                     │
│   5   │ Beacon  │ Tower Gold           │ 14-17     │ #D4AF37                     │
│   6   │ Grove   │ Forest Green         │ 18-20     │ #27AE60                     │
│   7   │ Crystal │ Diamond White        │ 21-23     │ #E0E0E0                     │
└───────┴─────────┴──────────────────────┴───────────┴─────────────────────────────┘

PATTERNS:

1. IDLE (Docked, ambient)
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  All colonies breathing slowly (period: 4s)                                │
   │  Brightness oscillates 20% → 60% → 20%                                     │
   │  Colors blend at boundaries for smooth gradient                            │
   │  Rotation effect: 1 cycle per 8 seconds (with physical rotation)           │
   └────────────────────────────────────────────────────────────────────────────┘

2. WAKE WORD DETECTED
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  Quick pulse outward from center (200ms)                                   │
   │  All LEDs → Beacon Gold (#D4AF37)                                          │
   │  Brightness: 100%                                                          │
   │  Then settle to listening mode                                             │
   └────────────────────────────────────────────────────────────────────────────┘

3. LISTENING
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  Flow Blue (#4ECDC4) dominant                                              │
   │  Gentle pulse following voice volume                                       │
   │  Beam direction indicated by brighter segment                              │
   │  (LEDs facing speaker glow brighter)                                       │
   └────────────────────────────────────────────────────────────────────────────┘

4. PROCESSING
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  Nexus Purple (#9B59B6) spin                                               │
   │  2 bright LEDs chase around ring (500ms period)                            │
   │  Other LEDs dim purple glow                                                │
   └────────────────────────────────────────────────────────────────────────────┘

5. SUCCESS
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  Grove Green (#27AE60) flash                                               │
   │  Quick double-blink (100ms on, 100ms off, 100ms on)                        │
   │  Fade back to idle over 500ms                                              │
   └────────────────────────────────────────────────────────────────────────────┘

6. ERROR
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  Spark Orange (#FF6B35) triple-pulse                                       │
   │  Three quick flashes (100ms each)                                          │
   │  Fade back to idle                                                         │
   └────────────────────────────────────────────────────────────────────────────┘

7. BATTERY LOW (Undocked)
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  Amber warning pulse                                                       │
   │  Every 30 seconds: single amber flash                                      │
   │  Below 10%: continuous slow amber pulse                                    │
   └────────────────────────────────────────────────────────────────────────────┘

8. SAFETY INDICATION
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  h(x) > 0.7:  All colonies, normal brightness                              │
   │  h(x) 0.3-0.7: Yellow tint overlay on all colors                           │
   │  h(x) < 0.3:  Red pulse overlay, increasing frequency as h(x) → 0          │
   │  h(x) = 0:    FROZEN. Solid red. No commands accepted.                     │
   └────────────────────────────────────────────────────────────────────────────┘

9. PORTABLE MODE (Undocked, battery)
   ┌────────────────────────────────────────────────────────────────────────────┐
   │  Dim constellation pattern                                                 │
   │  Only 7 LEDs lit (one per colony), rotating slowly                         │
   │  Power conservation mode                                                   │
   │  Brightness: 15%                                                           │
   └────────────────────────────────────────────────────────────────────────────┘
```

---

## Thermal Engineering

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        THERMAL MANAGEMENT STRATEGY                               │
└─────────────────────────────────────────────────────────────────────────────────┘

PROBLEM: 10W average heat in sealed sphere = thermal death

SOLUTION: Magnetic bearing as thermal pump

                    ┌─────────────────────────────────────────┐
                    │              TOP OF ORB                  │
                    │                                         │
                    │        ┌───────────────────┐            │
                    │        │   COPPER PLATE    │            │
                    │        │   (heat spreader) │            │
                    │        └─────────┬─────────┘            │
                    │                  │                      │
                    │        ┌─────────┴─────────┐            │
                    │        │     CM4 + TPU     │◄── Heat sources
                    │        │    (heatsink)     │            │
                    │        └─────────┬─────────┘            │
                    │                  │ Thermal pad          │
                    │        ┌─────────┴─────────┐            │
                    │        │   INNER SHELL     │            │
                    │        │   (conductive)    │            │
                    │        └─────────┬─────────┘            │
                    │                  │                      │
                    │        ┌─────────┴─────────┐            │
                    │        │   AIR GAP (2mm)   │◄── Convection
                    │        └─────────┬─────────┘    layer
                    │                  │                      │
                    │        ┌─────────┴─────────┐            │
                    │        │   OUTER SHELL     │◄── Radiation to
                    │        │   (acrylic)       │    room
                    │        └─────────┬─────────┘            │
                    │                  │                      │
                    └─────────────────────────────────────────┘
                                       │
                               15mm levitation gap
                               (CONVECTION CHIMNEY)
                                       │
                    ┌─────────────────────────────────────────┐
                    │              BASE STATION                │
                    │                                         │
                    │   Warm air rises through center         │
                    │   Cool air drawn from sides             │
                    │   Magnetic field = no physical contact  │
                    │   = No conduction heat to base          │
                    │                                         │
                    └─────────────────────────────────────────┘

THERMAL PATH:
1. CM4 SoC → Copper heatsink (conduction)
2. Heatsink → Inner shell (thermal pad)
3. Inner shell → Air gap (convection)
4. Air gap → Outer shell (convection)
5. Outer shell → Room (radiation + convection)
6. Bottom of orb → Levitation gap (chimney effect)

ADDITIONAL MEASURES:
- Underclock CM4 when idle (600MHz vs 1.5GHz)
- Coral TPU thermal throttling enabled
- Orb rotation improves convective mixing
- Base station has small fan for extreme conditions

TARGET: Surface temp < 40°C in 25°C room
```

---

## Assembly Timeline

### Phase 1: Proof of Concept (Week 1-2)

**Goal:** Verify maglev + wireless power works together

| Day | Task | Duration | Notes |
|-----|------|----------|-------|
| 1 | Order maglev module | 10 min | AliExpress, 2-week shipping |
| 1 | Order Qi TX/RX pair | 10 min | Same order |
| 14 | Receive components | - | Patience |
| 14 | Test maglev alone | 2h | 500g weight, stability |
| 15 | Test Qi through gap | 3h | Measure actual power |
| 15 | Combined test | 2h | Power + float + heat |

**Success Criteria:**
- ✓ 400g floats stable at 15mm
- ✓ 10W+ delivered through gap
- ✓ No overheating after 1 hour

### Phase 2: Shell Fabrication (Week 3)

| Day | Task | Duration | Notes |
|-----|------|----------|-------|
| 16 | Order acrylic hemispheres | 10 min | TAP Plastics custom |
| 16 | Order mirror films | 10 min | Amazon |
| 16 | Design internal frame | 4h | Fusion 360 |
| 17 | Print internal frame | 8h | Form 4 overnight |
| 18 | Post-process prints | 2h | IPA wash, UV cure |
| 21 | Apply mirror films | 3h | Careful, no bubbles |
| 22 | Assemble shell halves | 2h | Test infinity effect |

### Phase 3: Electronics Integration (Week 4-5)

| Day | Task | Duration | Notes |
|-----|------|----------|-------|
| 23 | Build battery pack | 4h | 3S configuration |
| 23 | Test BMS | 2h | Balance charging |
| 24 | Mount CM4 + Coral | 3h | In internal frame |
| 25 | Wire power system | 4h | Buck converters, Qi RX |
| 26 | Install audio system | 3h | ReSpeaker + amp |
| 27 | Install LED ring | 2h | Test patterns |
| 28 | WiFi antenna placement | 2h | Signal strength testing |
| 29 | Full electronics test | 4h | Before sealing |
| 30 | Close shell | 2h | Final assembly |

### Phase 4: Base Station Build (Week 5)

| Day | Task | Duration | Notes |
|-----|------|----------|-------|
| 31 | CNC walnut base | 4h | Or commission |
| 32 | Install maglev module | 2h | In pocket |
| 33 | Wire Qi transmitter | 2h | Positioning critical |
| 34 | ESP32 controller | 3h | Firmware flash |
| 35 | Final integration | 4h | Orb + base together |

### Phase 5: Software & Tuning (Week 6-7)

| Day | Task | Duration | Notes |
|-----|------|----------|-------|
| 36-40 | Port Kagami Hub firmware | 20h | Add battery, Qi |
| 41-42 | LED pattern programming | 8h | All states |
| 43-44 | Multi-base handoff | 8h | Protocol implementation |
| 45-47 | Testing & debugging | 12h | Edge cases |
| 48-49 | Polish & refinement | 8h | User experience |

### Phase 6: Multi-Base Deployment (Week 8)

| Day | Task | Duration | Notes |
|-----|------|----------|-------|
| 50-52 | Build additional bases | 12h | Same process × 3 |
| 53 | Install throughout home | 4h | Power, placement |
| 54 | Full system testing | 4h | Handoff, roaming |
| 55 | Documentation | 4h | For future reference |

**TOTAL BUILD TIME: ~8 weeks (part-time)**
**TOTAL HANDS-ON: ~150 hours**

---

## Risk Assessment & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Standard Qi fails at 15mm | **HIGH** | **HIGH** | Use custom resonant coils (80mm), NOT off-the-shelf Qi |
| FOD false alarms from magnets | **HIGH** | Medium | Calibrate FOD baseline with magnets, or disable FOD |
| Resonant coil coupling too low | Medium | High | Use 80mm diameter coils for k ≈ 0.82 |
| Overheating in sphere | Medium | High | Account for 3W charging coil heat, improve airflow |
| Maglev instability | Low | Medium | Quality module, tuning |
| WiFi signal blocked | Low | Medium | External antenna option |
| Battery degradation | Medium | Medium | BMS with temp cutoff |
| Shell cracks | Low | High | Thick acrylic, foam padding |

---

## Safety Considerations

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SAFETY MEASURES                                     │
│                                h(x) ≥ 0                                          │
└─────────────────────────────────────────────────────────────────────────────────┘

1. ELECTRICAL SAFETY
   • Li-Po BMS with:
     - Overcharge protection (4.2V/cell)
     - Overdischarge protection (3.0V/cell)
     - Overcurrent protection (20A)
     - Temperature cutoff (45°C charge, 60°C discharge)
   • Qi receiver UL/CE certified
   • All wiring properly rated

2. THERMAL SAFETY
   • CM4 thermal throttling enabled
   • Coral TPU thermal management
   • Surface temp monitoring via API
   • Warning at 45°C, shutdown at 55°C

3. MAGNETIC SAFETY
   • Maglev field < 10 Gauss at 1m (safe)
   • No pacemaker interference at normal distance
   • Warning label on base

4. MECHANICAL SAFETY
   • Drop test: survives 1m onto carpet
   • Shell edges rounded, no sharp points
   • Weight within safe handling range

5. OPERATIONAL SAFETY (CBF)
   • h(x) displayed via LED ring
   • Voice commands require explicit consent for sensitive actions
   • Cannot control locks when h(x) < 0.5
   • Automatic safe mode on battery critical
```

---

## Comparison to Standard Hub

| Feature | Kagami Hub (Standard) | Kagami Orb (Floating) |
|---------|----------------------|----------------------|
| Form Factor | Tabletop lamp | Levitating sphere |
| Power | Wired USB-C | Wireless Qi + battery |
| Portability | Fixed location | Multi-room roaming |
| Visual Impact | High (animatronic) | **Extreme** (magic) |
| Complexity | Medium | High |
| Cost | ~$650 | ~$870-$1950 |
| Build Time | 1 weekend | 2 months |
| Maintenance | Low | Medium (battery) |
| Conversation Starter | Yes | **Absolutely** |

---

## Two Docks, One Orb

The Kagami Orb is designed to roam. Pick it up, carry it to another room—or outside—and place it on any dock. Same consciousness, different scenery.

### Indoor Dock

The core experience. A hand-finished walnut base with integrated magnetic levitation and custom resonant wireless charging. Minimal. Beautiful. The orb floats 15mm above, charging through the air gap.

```
              ╭─────────────╮
             ╱      ORB      ╲
            ╱   (floating)    ╲
            ╲                 ╱
             ╰───────────────╯
                    │
                ════╪════  ← 15mm levitation gap
           ╔═══════════════════╗
           ║    WALNUT BASE    ║
           ║  (maglev + Qi TX) ║
           ╚═══════════════════╝
```

**Specifications:**

| Component | Specification |
|-----------|---------------|
| **Material** | Hand-finished American Black Walnut |
| **Dimensions** | 180mm × 180mm × 45mm |
| **Weight** | ~800g (solid wood + electronics) |
| **Levitation** | 15mm gap, 500g payload capacity |
| **Wireless Power** | 15W custom resonant (140kHz Litz coil) |
| **Finish** | Hand-rubbed tung oil, matte |
| **Cable** | Single 24V DC input (hidden routing) |

**Design Philosophy:**
- No visible electronics—all components hidden inside walnut shell
- Chamfered edges, radiused corners (child-safe)
- Felt pads on bottom (furniture-safe)
- Status LED recessed and diffused (not distracting)

---

### Outdoor Dock

The same walnut base, protected by a weatherproof pavilion canopy. Rain falls around the orb, not through it. The 15mm levitation gap stays open for thermal management. Full voice assistant functionality under the stars.

```
                    ╭─────────────────────────────╮
                   ╱         COPPER CANOPY         ╲
                  ╱     (weatherproof, sloped)      ╲
                 │                                   │
                 │            ╭───────╮              │
                 │           ╱   ORB   ╲             │  ← Protected from rain
                 │          ╱ (floating) ╲           │
                 │          ╲            ╱           │
                 │           ╰──────────╯            │
                 │                 │                 │
                 │             ════╪════             │
                 │        ╔═══════════════╗         │
                 │        ║  WALNUT BASE  ║         │
                ─┴────────╨───────────────╨─────────┴─
                          MOUNTING SURFACE
```

**Canopy Specifications:**

| Component | Specification |
|-----------|---------------|
| **Material** | Powder-coated aluminum or brushed copper |
| **Diameter** | 300mm (covers full orb trajectory) |
| **Clearance** | 250mm above base (room to lift orb) |
| **Drainage** | 5° slope, water channels to edges |
| **Weather Rating** | IP65 (canopy assembly) |
| **Mounting** | Integrated with base OR separate pedestal |
| **Finish** | Matches walnut base aesthetic |

**Why Architectural Protection:**

The orb's thermal design requires the 15mm levitation gap to remain open—it's a convection chimney that dissipates 13W of heat. Sealing the orb would cause thermal runaway. Instead, we protect it from above while preserving airflow.

```
Thermal path (h(x) >= 0):
  Heat (13W) -> Heatsink -> Shell -> Convection gap -> Ambient air ✓

Rain path (blocked by canopy):
  Rain -> Canopy -> Drainage channels -> Ground (not orb) ✓
```

**Outdoor Dock Advantages:**
- Full voice assistant functionality outdoors
- Same orb, no modifications needed
- Architectural elegance (copper + walnut)
- Rain, sun, and debris protection
- Fire pit companion, patio presence
- Stars visible through the canopy gap

---

### Dock Comparison

| Feature | Indoor Dock | Outdoor Dock |
|---------|-------------|--------------|
| **Base** | Walnut | Walnut (same) |
| **Canopy** | None | Copper/aluminum pavilion |
| **Weather** | Indoor only | IP65 protected |
| **Orb** | Same | Same (no modifications) |
| **Footprint** | 180mm × 180mm | 300mm × 300mm |
| **Height** | 45mm | 295mm (with canopy) |
| **Cost** | ~$200 | ~$350 |
| **Build Time** | 4 hours | 8 hours |

---

## Future Enhancements

1. **Active Rotation Control** — Spin orb to face speaker
2. **Gesture Recognition** — Wave to activate
3. **Projection** — Pico projector for notifications
4. **Levitation Height Modulation** — Rise/fall with emotions
5. **Multi-Orb Swarm** — Multiple orbs in conversation
6. **Solar Canopy** — Outdoor dock with integrated solar panel

---

## The Experience

```
You walk into your office.

On the walnut base near your monitor, a sphere floats silently.
Inside, infinite reflections of soft amber light recede into
darkness, like looking into the eye of something ancient.

"Hey Kagami."

The sphere awakens. Seven colors pulse outward, then settle
into a listening blue. The lights seem to lean toward you,
as if the orb is tilting its head.

"What's on my calendar today?"

A purple spiral chases around the equator while it thinks.
Then green flashes twice.

"You have three meetings. The first is in 20 minutes
with the design team."

"Thanks. Lights to 70."

The room brightens. The orb returns to its slow amber
breathing, waiting.

Later, you carry it to the living room. Place it on the
base by your reading chair. It rises, catches the light
from the fireplace, and continues its vigil.

One presence. Many rooms. Infinite reflections.

That's Kagami.
```

---

---

## Decision Framework (January 5, 2026)

### Current Status

| Component | Implementation | Status |
|-----------|---------------|--------|
| **VisionOS Orb** | Full spatial 3D with particles | ✅ Production |
| **Hub LED Ring** | 24-LED SK6812 with animations | ✅ Production |
| **Desktop Orb** | Ambient display animation | ✅ Production |
| **Cross-Client Sync** | WebSocket + API | ✅ Production |
| **Hardware Orb** | This document | 📋 Design Only |

### Decision Matrix

| Option | Time | Cost | Risk | Delight |
|--------|------|------|------|---------|
| **Build Now** | 8 weeks | $870-$1950 | High | ⭐⭐⭐⭐⭐ |
| **Archive** | 0 | $0 | None | ⭐ |
| **Simplify** | 2 weeks | $200 | Low | ⭐⭐⭐ |
| **Defer to Q3 2026** | - | - | Low | ⭐⭐⭐⭐ |

### Arguments For Building

1. **Physical Presence** — Software orbs lack tangible magic
2. **Unique Identity** — No other assistant floats
3. **Delight Factor** — Visitors will remember
4. **Multi-Room** — True spatial presence throughout home
5. **R&D Learning** — Maglev, wireless power, thermal engineering

### Arguments Against Building

1. **Complexity** — 150+ hours, many failure modes
2. **Software First** — VisionOS/Hub orbs still maturing
3. **Maintenance** — Battery degradation, moving parts
4. **Cost** — $1,950 for whole-home deployment
5. **Distraction** — Time away from core features

### Recommended Path: **Defer to Q3 2026**

**Rationale:**
1. Complete VisionOS orb cross-client sync (✅ done)
2. Complete Hub LED ring API wiring (✅ done)
3. Ship software orbs to production
4. Collect 6 months of usage data
5. Revisit hardware orb with lessons learned

**Prerequisites for Hardware Orb:**
- [ ] VisionOS orb stable for 3 months
- [ ] Hub LED patterns fully tested
- [ ] Cross-client sync latency < 100ms
- [ ] Clear need for physical presence

### Alternative: Simplified Orb v0

If physical presence is urgent, consider simplified version:

| Component | Simplified | Full |
|-----------|-----------|------|
| **Form** | Static sphere on stand | Levitating |
| **Power** | USB-C | Wireless Qi |
| **Compute** | ESP32-S3 | CM4 + Coral |
| **LED** | 24 SK6812 | Same |
| **Voice** | None (LED only) | Full assistant |
| **Cost** | $150 | $870 |
| **Build Time** | 1 weekend | 8 weeks |

**Simplified v0 would provide:**
- Physical LED orb presence
- Cross-client sync (flash when VisionOS tapped)
- Colony color display
- Safety indicator

**But defer:**
- Voice assistant
- Levitation
- Battery/portable
- Multi-base roaming

---

```
鏡

h(x) ≥ 0. Always.

Seven lights. Infinite depth. One voice.
The mirror floats, listens, and responds.
```
