# Kagami Orb — Custom Carrier PCB Design

## Overview

The Kagami Orb requires a custom PCB to integrate:
- QCS6490 compute module socket
- Battery management system
- Resonant wireless power receiver integration
- Audio I/O (sensiBel SBM100B + speaker amp)
- LED ring control
- WiFi 6E antenna connections
- Thermal management

**Design Philosophy:** Compact, circular form factor to fit inside 85mm sphere.

---

## PCB Specifications

| Parameter | Value |
|-----------|-------|
| Form Factor | Circular, 85mm diameter |
| Layers | 4-layer stackup |
| Thickness | 1.6mm |
| Copper | 1oz outer, 0.5oz inner |
| Surface Finish | ENIG (for fine pitch) |
| Solder Mask | Matte black |
| Min Trace/Space | 0.15mm/0.15mm |

---

## Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            KAGAMI ORB PCB v1.0                                   │
│                           (Circular, 85mm dia)                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

                         ┌───────────────────────┐
                         │  RESONANT RECEIVER 15W│
                         │    (Bottom of orb)    │
                         └───────────┬───────────┘
                                     │ 5V 3A
                         ┌───────────┴───────────┐
                         │   BATTERY MANAGEMENT  │
                         │   BQ25895 + BQ40Z50   │
                         │                       │
                         │   ┌───────────────┐   │
                         │   │ 3S Li-Po Pack │   │
                         │   │ 10,000mAh     │   │
                         │   └───────────────┘   │
                         └───────────┬───────────┘
                                     │ 5V (Switched)
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐       ┌─────────────────┐        ┌─────────────────┐
│  3.3V LDO       │       │  5V_LOGIC       │        │  5V_LED         │
│  TPS62840       │       │  (Direct)       │        │  (Direct)       │
│  (Ultra-low Iq) │       │                 │        │                 │
└────────┬────────┘       └────────┬────────┘        └────────┬────────┘
         │                         │                          │
         ▼                         ▼                          ▼
┌─────────────────┐       ┌─────────────────┐        ┌─────────────────┐
│                 │       │                 │        │                 │
│   QCS6490 Module│       │  USB Hub        │        │  HD108 Ring     │
│   (8GB RAM)     │       │  USB2514B       │        │  16 RGBW LEDs   │
│                 │       │                 │        │                 │
│  ┌───────────┐  │       └────────┬────────┘        └─────────────────┘
│  │ QCS6490   │  │                │
│  │ 2.7GHz    │  │    ┌───────────┴───────────┐
│  └───────────┘  │    │                       │
│                 │    ▼                       ▼
│   I2C, I2S,     │  ┌─────────────┐   ┌─────────────┐
│   SPI, GPIO     │  │ Hailo-10H   │   │ AX210 WiFi  │
│                 │  │ (via USB)   │   │ (via USB)   │
└────────┬────────┘  └─────────────┘   └─────────────┘
         │
         │ I2S / I2C / GPIO
         │
┌────────┴────────────────────────────────────────────────────────────┐
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ sensiBel    │  │ MAX98357A   │  │ Fuel Gauge  │  │ Hall Sensor │ │
│  │ 4-Mic Array │  │ Audio Amp   │  │ (I2C)       │  │ (Lid detect)│ │
│  │ (I2S Input) │  │ (I2S Output)│  │             │  │             │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Schematic Sections

### 1. Power Management

```
                         RESONANT RECEIVER (Custom 80mm Litz Coil)
                         ┌───────────────────────────┐
                         │   Custom Resonant RX      │
                         │  5V @ 3A (15W @ 140kHz)   │
                         │                           │
                         │  GND ──────────┐          │
                         │  VOUT ─────────┼───┐      │
                         │  CTRL ─────────┼───┼───┐  │
                         └───────────────────────────┘
                                          │   │   │
                                          │   │   └───── Charging status (GPIO)
                                          │   │
                                          ▼   ▼
                         ┌────────────────────────────────────────────────┐
                         │              BQ25895 Charger IC                 │
                         │         (I2C Programmable, USB OTG)             │
                         │                                                 │
                         │  VBUS ◄─────── 5V from Resonant RX             │
                         │  VSYS ──────► System 5V                         │
                         │  VBAT ◄─────► Battery Pack                      │
                         │  SDA/SCL ───► I2C Bus                           │
                         │  INT ────────► Interrupt (GPIO)                  │
                         │  OTG ────────► USB Host (for Hailo-10H)         │
                         │                                                 │
                         │  Charge Current: Up to 3A                       │
                         │  Input Current Limit: 3.25A                     │
                         │  Buck/Boost: 3.5V-18V to VSYS                   │
                         └────────────────────────────────────────────────┘
                                                │
                                                ▼
                         ┌────────────────────────────────────────────────┐
                         │              BQ40Z50 Fuel Gauge                 │
                         │         (Smart Battery Manager)                 │
                         │                                                 │
                         │  BAT+ ◄─────► 3S Pack (11.1V nom)              │
                         │  SDA/SCL ───► I2C Bus                           │
                         │  ALERT ─────► Low battery GPIO                  │
                         │                                                 │
                         │  Reports: SOC%, Voltage, Current, Temp          │
                         │  Protects: OV, UV, OC, OT, Cell Balance         │
                         └────────────────────────────────────────────────┘


                         VOLTAGE REGULATORS:

                         ┌─────────────────┐     ┌─────────────────┐
                         │  TPS62840       │     │  TPS62841       │
                         │  3.3V @ 750mA   │     │  1.8V @ 750mA   │
                         │  Iq = 60nA      │     │  Iq = 60nA      │
                         │  (Ultra-low)    │     │  (For QCS6490)  │
                         └─────────────────┘     └─────────────────┘
```

### 2. QCS6490 Module Interface

```
                         QCS6490 Module Connector (Board-to-Board)
                         ┌─────────────────────────────────────────────────────┐
                         │                                                     │
                         │  POWER PINS:                                        │
                         │  ──────────                                         │
                         │  VBAT (5V) ◄──── System 5V (via BQ25895)           │
                         │  VDD_CORE ◄──── 1.8V (TPS62841)                    │
                         │  VDD_IO ◄────── 3.3V (TPS62840)                    │
                         │  GND ◄───────── Ground plane                        │
                         │                                                     │
                         │  USB 2.0 HOST:                                      │
                         │  ─────────────                                      │
                         │  USB_DP ────────► USB Hub (USB2514B)               │
                         │  USB_DM ────────► USB Hub (USB2514B)               │
                         │                                                     │
                         │  I2C:                                               │
                         │  ────                                               │
                         │  SDA (GPIO2) ───► I2C Bus (shared)                  │
                         │  SCL (GPIO3) ───► I2C Bus (shared)                  │
                         │                                                     │
                         │  I2S AUDIO:                                         │
                         │  ──────────                                         │
                         │  PCM_CLK ───────► Audio BCLK (shared bus)           │
                         │  PCM_FS ────────► Audio LRCK (shared bus)           │
                         │  PCM_DIN ───────◄ sensiBel SBM100B Data Out         │
                         │  PCM_DOUT ──────► MAX98357A Data In                 │
                         │                                                     │
                         │  LED CONTROL:                                       │
                         │  ────────────                                       │
                         │  GPIO18 (PWM0) ─► HD108 DIN (via level shifter)     │
                         │                                                     │
                         │  STATUS:                                            │
                         │  ───────                                            │
                         │  GPIO17 ◄──────── Resonant charging status         │
                         │  GPIO27 ◄──────── Battery alert                    │
                         │  GPIO22 ◄──────── Hall sensor (lid detect)         │
                         │  GPIO23 ◄──────── Temperature alert                │
                         │                                                     │
                         │  BOOT/CONFIG:                                       │
                         │  ────────────                                       │
                         │  nRPIBOOT ──────► Boot mode select                 │
                         │  GLOBAL_EN ─────► System enable                    │
                         │  RUN ───────────► Soft power control               │
                         │                                                     │
                         └─────────────────────────────────────────────────────┘
```

### 3. USB Hub for Peripherals

```
                         ┌─────────────────────────────────────────────────────┐
                         │              USB2514B 4-Port Hub IC                 │
                         │                                                     │
                         │  UPSTREAM:                                          │
                         │  DP/DM ◄──────── QCS6490 USB Host                   │
                         │                                                     │
                         │  DOWNSTREAM:                                        │
                         │  Port 1 ────────► Hailo-10H AI Accelerator          │
                         │  Port 2 ────────► Intel AX210 (via adapter)         │
                         │  Port 3 ────────► (Reserved - external USB-C)       │
                         │  Port 4 ────────► (Reserved - debug)                │
                         │                                                     │
                         │  POWER:                                             │
                         │  VDD33 ◄──────── 3.3V                               │
                         │  VDD18 ◄──────── Internal 1.8V regulator            │
                         │                                                     │
                         │  CONFIG:                                            │
                         │  NON_REM[4:1] ─► 1111 (all permanent)              │
                         │  PRTPWR[4:1] ──► Port power control                 │
                         │                                                     │
                         └─────────────────────────────────────────────────────┘

                         NOTE: USB-C connector on PCB edge for:
                         - Emergency charging (5V path to BQ25895)
                         - Debug/programming access
                         - Factory testing
```

### 4. Audio System

```
                         ┌─────────────────────────────────────────────────────┐
                         │             AUDIO INPUT (sensiBel SBM100B 4-Mic)    │
                         │                                                     │
                         │  External Module Connection (8-pin FFC):            │
                         │                                                     │
                         │  3V3 ◄────────── 3.3V Rail                          │
                         │  GND ◄────────── Ground                             │
                         │  BCK ◄────────── I2S BCLK (GPIO12)                  │
                         │  WS  ◄────────── I2S LRCK (GPIO19)                  │
                         │  DO  ──────────► I2S DIN (GPIO20)                   │
                         │  INT ──────────► Voice Activity (GPIO24)            │
                         │  SDA ◄─────────► I2C Bus (for config)               │
                         │  SCL ◄────────── I2C Bus                            │
                         │                                                     │
                         └─────────────────────────────────────────────────────┘

                         ┌─────────────────────────────────────────────────────┐
                         │             AUDIO OUTPUT (MAX98357A)                │
                         │                                                     │
                         │  VDD ◄────────── 5V Rail (for 3W output)            │
                         │  GND ◄────────── Ground                             │
                         │  BCLK ◄───────── I2S BCLK (GPIO12)                  │
                         │  LRCLK ◄──────── I2S LRCK (GPIO19)                  │
                         │  DIN ◄────────── I2S DOUT (GPIO21)                  │
                         │  GAIN ──────────┤ 15dB (float)                      │
                         │  SD_MODE ──────┤ Always on (tied high)             │
                         │                                                     │
                         │  OUT+ ─────────► Speaker +                          │
                         │  OUT- ─────────► Speaker -                          │
                         │                                                     │
                         └─────────────────────────────────────────────────────┘
```

### 5. LED Ring Control

```
                         ┌─────────────────────────────────────────────────────┐
                         │             HD108 LEVEL SHIFTING                    │
                         │                                                     │
                         │  GPIO18 (3.3V) ───► 74AHCT125 ───► 5V HD108 Data    │
                         │                                                     │
                         │  Schematic:                                         │
                         │                                                     │
                         │       3.3V     5V                                   │
                         │        │       │                                    │
                         │        │   ┌───┴───┐                                │
                         │  GPIO18 ──►│1A  1Y├──► HD108 DIN                    │
                         │            │      │                                  │
                         │        GND─┤~1OE  │                                  │
                         │            └──────┘                                  │
                         │            74AHCT125                                 │
                         │                                                     │
                         │  Bypass: 100nF on both rails near IC                │
                         │                                                     │
                         └─────────────────────────────────────────────────────┘

                         HD108 Ring Connection (4-pin JST):
                         ┌─────┬─────┬─────┬─────┐
                         │ 5V  │ DIN │ GND │ NC  │
                         └─────┴─────┴─────┴─────┘
```

---

## PCB Layout Guidelines

### Layer Assignment (4-Layer)

| Layer | Purpose | Notes |
|-------|---------|-------|
| L1 (Top) | Components + High-speed | QCS6490, USB, I2S |
| L2 | Ground plane | Unbroken under QCS6490 |
| L3 | Power planes | 5V, 3.3V, 1.8V split |
| L4 (Bottom) | Components + Routing | Battery, Resonant RX pads |

### Critical Routing

1. **USB 2.0** — 90Ω differential, length-matched ±0.5mm
2. **I2S** — 50Ω single-ended, length-matched ±2mm
3. **Power** — Wide traces (2mm for 3A), star topology
4. **LED Data** — Series resistor at source, keep short

### Thermal Considerations

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         THERMAL ZONES (Top View)                                 │
│                                                                                  │
│                              ┌───────────────┐                                   │
│                             ╱                 ╲                                  │
│                            ╱   HOT ZONE        ╲                                 │
│                           │  (QCS6490 + BQ)     │                                │
│                           │    ┌─────────┐      │                                │
│                           │    │ QCS6490 │      │                                │
│                           │    │ THERMAL │      │                                │
│                           │    │   VIA   │      │                                │
│                           │    │  ARRAY  │      │                                │
│                           │    └─────────┘      │                                │
│                           │                     │                                │
│                            ╲   COOL ZONE       ╱                                 │
│                             ╲  (USB, Audio)   ╱                                  │
│                              ╰───────────────╯                                   │
│                                                                                  │
│  THERMAL MANAGEMENT:                                                             │
│  • 64 thermal vias (0.3mm) under QCS6490 to bottom copper pour                  │
│  • Large GND pour on L4 as heatsink                                             │
│  • Copper heatsink mounted to QCS6490 SoC                                       │
│  • Thermal pad from heatsink to inner shell                                      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Mechanical Mounting

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         MOUNTING HOLES (85mm PCB)                                │
│                                                                                  │
│                              ○  M2.5 (0°)                                        │
│                         ╱         │         ╲                                    │
│                        ╱          │          ╲                                   │
│                       ○           │           ○  M2.5 (60°, 120°)               │
│                       │           │           │                                  │
│                       │     ┌─────┴─────┐     │                                  │
│                       │     │    PCB    │     │                                  │
│                       │     │  85mm ⌀   │     │                                  │
│                       │     └───────────┘     │                                  │
│                       │           │           │                                  │
│                       ○           │           ○  M2.5 (240°, 300°)              │
│                        ╲          │          ╱                                   │
│                         ╲         │         ╱                                    │
│                              ○  M2.5 (180°)                                      │
│                                                                                  │
│  6× M2.5 mounting holes at 35mm radius, 60° spacing                             │
│  Hole diameter: 2.7mm                                                           │
│  Keep-out zone: 6mm diameter around each hole                                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Bill of Materials (PCB Only)

| Ref | Value | Package | Description | Part Number | Qty |
|-----|-------|---------|-------------|-------------|-----|
| U1 | QCS6490 | Board-to-board | TurboX C6490 SoM Connector | Mfr-specific | 1 |
| U2 | BQ25895 | QFN-24 | Battery Charger | BQ25895RTWR | 1 |
| U3 | BQ40Z50 | QFN-32 | Fuel Gauge | BQ40Z50RSMT | 1 |
| U4 | TPS62840 | SOT-23-6 | 3.3V LDO | TPS62840DLCR | 1 |
| U5 | TPS62841 | SOT-23-6 | 1.8V LDO | TPS62841DLCR | 1 |
| U6 | USB2514B | QFN-36 | USB Hub | USB2514B-AEZC | 1 |
| U7 | 74AHCT125 | TSSOP-14 | Level Shifter | 74AHCT125PW | 1 |
| U8 | MAX98357A | QFN-16 | Audio Amp | MAX98357AETE+T | 1 |
| J1 | USB-C | SMD | USB Type-C 2.0 | USB4110-GF-A | 1 |
| J2 | 8-pin FFC | 0.5mm | sensiBel SBM100B Connector | FH12-8S-0.5SH | 1 |
| J3 | 4-pin JST | 2.0mm | LED Ring | B4B-PH-K-S | 1 |
| J4 | 2-pin JST | 2.0mm | Speaker | B2B-PH-K-S | 1 |
| J5 | 4-pin JST | 2.0mm | Battery | B4B-PH-K-S | 1 |
| J6 | 3-pin Pogo | 2.54mm | Resonant RX | Mill-Max 0906 | 1 |

(Plus passives: capacitors, resistors, inductors per reference design)

---

## Design Files

```
/apps/hub/kagami-orb/hardware/
├── CUSTOM_PCB.md           (This document)
├── kagami_orb_bom.csv      (Full system BOM)
├── schematic/
│   └── kagami_orb.kicad_sch   (To be created)
├── pcb/
│   └── kagami_orb.kicad_pcb   (To be created)
├── gerbers/
│   └── (Generated output)
├── 3d/
│   └── kagami_orb_pcb.step    (For mechanical integration)
└── simulation/
    └── thermal_analysis.fea    (FEA thermal simulation)
```

---

## Next Steps

1. **Validate Power Path** — Test BQ25895 with resonant input
2. **Prototype QCS6490 Carrier** — Minimal viable board for software dev
3. **Thermal Testing** — Measure actual temps in sealed sphere
4. **Full PCB Design** — KiCad schematic and layout
5. **DFM Review** — JLCPCB/PCBWay compatibility check

---

```
鏡

h(x) ≥ 0. Always.

The heart of the orb beats with seven colonies.
Power flows without wires. Thought flows without boundaries.
```
