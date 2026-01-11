# Kagami Orb — KiCad Schematic Specification

## Overview

This document specifies the **full component-level KiCad schematic** for the Kagami Orb custom carrier PCB.

**KiCad Project:** `kagami_orb` (to be created in `apps/hub/kagami-orb/pcb/`)

---

## Schematic Sheets

| Sheet | Name | Contents |
|-------|------|----------|
| 1 | Top Level | Block diagram, connectors |
| 2 | Power Management | Resonant RX, BMS, buck converters |
| 3 | CM4 Interface | Module connector, boot config |
| 4 | USB Hub | USB2514B, downstream ports |
| 5 | Audio | ReSpeaker connector, MAX98357A |
| 6 | LED Control | Level shifter, SK6812 connector |
| 7 | Sensors | Hall effect, temperature, I2C |

---

## Sheet 1: Top Level

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SHEET 1: TOP LEVEL                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────────────────────┐
                    │                    KAGAMI ORB v1.0                           │
                    │                  Custom Carrier PCB                          │
                    │                    85mm Circular                             │
                    └─────────────────────────────────────────────────────────────┘

     ┌──────────┐           ┌──────────┐           ┌──────────┐
     │  POWER   │           │   CM4    │           │  USB HUB │
     │  SHEET 2 │───5V──────│ SHEET 3  │───USB─────│ SHEET 4  │
     │          │           │          │           │          │
     │ Res → BMS│           │ BCM2711  │           │ USB2514B │
     │ → Buck   │           │ 4GB RAM  │           │ 4-Port   │
     └────┬─────┘           └────┬─────┘           └────┬─────┘
          │                      │                      │
          │ 3.3V                 │ I2S, I2C, GPIO       │ USB
          │                      │                      │
     ┌────┴─────┐           ┌────┴─────┐           ┌────┴─────┐
     │ SENSORS  │           │  AUDIO   │           │   LED    │
     │ SHEET 7  │◄──I2C─────│ SHEET 5  │           │ SHEET 6  │
     │          │           │          │           │          │
     │ Hall     │           │ ReSpeaker│           │ 74AHCT   │
     │ Temp     │           │ MAX98357 │           │ SK6812   │
     └──────────┘           └──────────┘           └──────────┘


EXTERNAL CONNECTORS:
────────────────────

J1: USB-C (Programming/Debug/Emergency Charge)
J2: ReSpeaker 8-pin FFC
J3: SK6812 LED Ring (4-pin JST)
J4: Speaker (2-pin JST)
J5: Battery (4-pin JST with balance)
J6: Resonant Receiver (3-pin pogo)
J7: Debug Header (10-pin SWD)
```

---

## Sheet 2: Power Management

### Component List

| Ref | Part | Package | Value | Description |
|-----|------|---------|-------|-------------|
| U1 | BQ25895RTWR | QFN-24 | - | Battery charger |
| U2 | BQ40Z50RSMT | QFN-32 | - | Fuel gauge |
| U3 | TPS62840DLC | SOT-23-6 | 3.3V | Ultra-low Iq LDO |
| U4 | TPS62841DLC | SOT-23-6 | 1.8V | Ultra-low Iq LDO |
| U5 | TPS62A01DRLR | SOT-563 | 5V | 2A buck (backup) |
| Q1 | DMG2305UX | SOT-23 | - | P-FET load switch |
| D1 | PMEG2010ER | SOD-323 | - | Schottky (Resonant input) |
| D2 | SMBJ5.0A | SMB | 5V | TVS protection |
| F1 | 0ZCJ0050AF2E | 1206 | 500mA | Resettable fuse |

### Schematic Block

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SHEET 2: POWER MANAGEMENT                                │
└─────────────────────────────────────────────────────────────────────────────────┘

RESONANT RECEIVER INPUT (Custom 80mm Litz @ 140kHz)
───────────────────────────────────────────────────

J6 (Pogo)       D1              F1
   ┌───┐     ┌──┴──┐        ┌──┴──┐
   │ 1 ├──┬──┤PMEG ├────────┤FUSE ├──────┐
   │ 2 │  │  │2010 │        │500mA│      │
   │ 3 │  │  └─────┘        └─────┘      │
   └───┘  │                              │
          │  C1 10μF                      │ VIN_RES (5V nom)
          └──┤├──GND                      │
                                         │
                                         ▼
                    ┌─────────────────────────────────────────────────┐
                    │                   U1: BQ25895                    │
                    │              Battery Charger IC                  │
                    │                                                  │
                    │  VBUS ◄─────────────────────────────────────────┤ VIN_RES
                    │                                                  │
                    │  VSYS ─────────────────────────────────────────► VSYS (5V)
                    │                                                  │
                    │  VBAT ◄────────────────────────────────────────► J5 (Battery)
                    │                                                  │
                    │  SDA  ─────────────────────────────────────────► I2C_SDA
                    │  SCL  ◄─────────────────────────────────────────  I2C_SCL
                    │                                                  │
                    │  INT  ─────────────────────────────────────────► GPIO_CHG_INT
                    │  CE   ◄────────────────────────────────────────── VCC (always on)
                    │  QON  ◄────────────────────────────────────────── GPIO_SHIP_MODE
                    │                                                  │
                    │  PMID ─────────────────────────────────────────► (Power path)
                    │  REGN ─────────────────────────────────────────► (Internal reg)
                    │                                                  │
                    │  ILIM ◄────────────────────────────────────────── R_ILIM (10kΩ = 3A)
                    │  TS   ◄────────────────────────────────────────── Thermistor
                    │                                                  │
                    └─────────────────────────────────────────────────┘

BATTERY CONNECTION
─────────────────

J5 (Battery JST-PH 4-pin)
   ┌───┐
   │ 1 ├──────────────────────────────────── BAT+ (11.1V nom)
   │ 2 ├──────────────────────────────────── BAL1 (Cell 1)
   │ 3 ├──────────────────────────────────── BAL2 (Cell 2)
   │ 4 ├──────────────────────────────────── GND
   └───┘
          │
          ▼
    ┌─────────────────────────────────────────────────┐
    │                 U2: BQ40Z50                      │
    │               Fuel Gauge IC                      │
    │                                                  │
    │  BAT ◄───────────────────────────────────────── BAT+
    │  PACK+ ─────────────────────────────────────► Protection FET
    │  PACK- ◄────────────────────────────────────── GND (via sense R)
    │                                                  │
    │  SDA  ─────────────────────────────────────────► I2C_SDA
    │  SCL  ◄─────────────────────────────────────────  I2C_SCL
    │                                                  │
    │  ALERT ────────────────────────────────────────► GPIO_BAT_ALERT
    │                                                  │
    └─────────────────────────────────────────────────┘


VOLTAGE REGULATORS
─────────────────

VSYS (5V) ───┬──────────────────────────────────────────► 5V_USB
             │
             ├───┤ U3: TPS62840 ├───────────────────────► 3V3
             │        3.3V @ 750mA
             │        Iq = 60nA
             │
             └───┤ U4: TPS62841 ├───────────────────────► 1V8
                      1.8V @ 750mA
                      Iq = 60nA


USB-C EMERGENCY INPUT
─────────────────

J1 (USB-C)
   ┌───────────┐
   │  CC1/CC2  ├────────────► CC pulldown (5.1kΩ × 2)
   │           │
   │  VBUS     ├────────────► VIN_USB (diode OR with VIN_RES)
   │           │
   │  D+/D-    ├────────────► USB_DATA (to CM4 for debug)
   │           │
   │  GND      ├────────────► GND
   └───────────┘
```

---

## Sheet 3: CM4 Interface

### Component List

| Ref | Part | Package | Description |
|-----|------|---------|-------------|
| J10, J11 | DF40HC(3.0)-100DS | 100-pin | CM4 connectors |
| R1-R4 | 10kΩ | 0402 | Boot config pullups |
| C10-C15 | 100nF | 0402 | Decoupling |
| C16-C17 | 10μF | 0603 | Bulk decoupling |

### Pin Assignments

```
CM4 CONNECTOR PINOUT (Critical Signals)
───────────────────────────────────────

POWER:
  VBAT (5V)         ← VSYS
  VDD_CORE (1.8V)   ← 1V8 rail
  VDD_IO (3.3V)     ← 3V3 rail
  GND               ← Ground plane

USB:
  USB_DP, USB_DM    → USB Hub (USB2514B)

I2S AUDIO:
  GPIO12 (PCM_CLK)  → I2S_BCLK (shared)
  GPIO19 (PCM_FS)   → I2S_LRCLK (shared)
  GPIO20 (PCM_DIN)  ← ReSpeaker Data Out
  GPIO21 (PCM_DOUT) → MAX98357A Data In

I2C:
  GPIO2 (SDA)       ↔ I2C bus
  GPIO3 (SCL)       → I2C bus

LED:
  GPIO18 (PWM0)     → Level shifter → SK6812

GPIO (Status):
  GPIO17            ← Resonant charging status
  GPIO22            ← Hall sensor (dock)
  GPIO23            ← Temperature alert
  GPIO24            ← ReSpeaker VAD
  GPIO27            ← Battery alert

BOOT:
  nRPIBOOT          → R1 to 3V3 (normal boot)
  GLOBAL_EN         → 3V3 (always enabled)
  RUN               → Button (soft power)
```

---

## Sheet 4: USB Hub

### Component List

| Ref | Part | Package | Description |
|-----|------|---------|-------------|
| U6 | USB2514B-AEZC | QFN-36 | 4-port USB hub |
| Y1 | 24MHz | 3.2×2.5 | Crystal |
| R10-R13 | 15kΩ | 0402 | USB termination |

### Downstream Ports

```
USB HUB (USB2514B) DOWNSTREAM ALLOCATION
─────────────────────────────────────────

UPSTREAM:
  CM4 USB_DP/DM ──────► USB2514B USBDP/USBDM

DOWNSTREAM:
  Port 1 ──────────────► Google Coral USB TPU
  Port 2 ──────────────► Intel AX210 WiFi (via adapter)
  Port 3 ──────────────► J1 USB-C (external access)
  Port 4 ──────────────► Reserved (debug header)

CONFIGURATION:
  NON_REM[4:1] = 1111 (all non-removable)
  PRTPWR[4:1]  = controlled by MCU
```

---

## Sheet 5: Audio System

### Component List

| Ref | Part | Package | Description |
|-----|------|---------|-------------|
| J2 | FH12-8S-0.5SH | FFC | ReSpeaker connector |
| U7 | MAX98357AETE | QFN-16 | I2S Class-D amp |
| J4 | B2B-PH-K-S | 2-pin | Speaker connector |
| C20-C22 | Various | - | Filter caps |

### Connections

```
RESPEAKER 4-MIC ARRAY (J2)
─────────────────────────

Pin 1: 3V3         ← 3V3 rail
Pin 2: GND         ← GND
Pin 3: BCK         ← GPIO12 (I2S_BCLK)
Pin 4: WS          ← GPIO19 (I2S_LRCLK)
Pin 5: DO          → GPIO20 (I2S_DIN)
Pin 6: INT         → GPIO24 (VAD)
Pin 7: SDA         ↔ I2C_SDA
Pin 8: SCL         ← I2C_SCL


SPEAKER OUTPUT (U7: MAX98357A)
─────────────────────────────

BCLK   ← GPIO12
LRCLK  ← GPIO19
DIN    ← GPIO21
GAIN   → Float (15dB)
SD     → 3V3 (always on)

OUT+   → Speaker +
OUT-   → Speaker -
```

---

## Sheet 6: LED Control

### Component List

| Ref | Part | Package | Description |
|-----|------|---------|-------------|
| U8 | 74AHCT125PW | TSSOP-14 | Level shifter |
| J3 | B4B-PH-K-S | 4-pin | LED connector |
| R20 | 470Ω | 0402 | Series data resistor |
| C25 | 100nF | 0402 | Bypass |

### Connections

```
LED LEVEL SHIFTING
─────────────────

GPIO18 (3.3V) ───► 74AHCT125 ───► 5V_LED_DATA
                      │
                   R20 470Ω
                      │
                      ▼
                   J3 Pin 2 (DIN)


J3 (SK6812 CONNECTOR)
─────────────────

Pin 1: 5V      ← 5V_LED rail
Pin 2: DIN     ← 5V_LED_DATA
Pin 3: GND     ← GND
Pin 4: NC
```

---

## Sheet 7: Sensors

### Component List

| Ref | Part | Package | Description |
|-----|------|---------|-------------|
| U9 | DRV5053VAQDBZR | SOT-23 | Hall effect sensor |
| U10 | TMP117AIDRVR | SOT-563 | I2C temperature |
| R30-R33 | 10kΩ | 0402 | I2C pullups |

### Connections

```
HALL EFFECT SENSOR (Dock Detection)
───────────────────────────────────

U9: DRV5053
  VCC  ← 3V3
  OUT  → GPIO22 (analog capable)
  GND  ← GND

Triggers when magnetic field detected (orb docked)


TEMPERATURE SENSOR
──────────────────

U10: TMP117 (±0.1°C accuracy)
  VCC  ← 3V3
  SDA  ↔ I2C_SDA
  SCL  ← I2C_SCL
  ALERT → GPIO23
  GND  ← GND

Address: 0x48

I2C BUS SUMMARY
───────────────

Address | Device        | Function
────────┼───────────────┼─────────────────────
0x48    | TMP117        | Temperature
0x55    | BQ25895       | Charger
0x55    | BQ40Z50       | Fuel gauge (SMBus)
0x35    | ReSpeaker     | DSP configuration
```

---

## PCB Stackup

| Layer | Name | Purpose |
|-------|------|---------|
| L1 | Top | Components, high-speed signals |
| L2 | GND | Solid ground plane |
| L3 | PWR | Split power planes (5V, 3V3, 1V8) |
| L4 | Bottom | Components, routing |

---

## Design Rules

| Parameter | Value |
|-----------|-------|
| Min trace width | 0.15mm (6 mil) |
| Min trace spacing | 0.15mm (6 mil) |
| Min via diameter | 0.3mm |
| Min via drill | 0.15mm |
| USB differential impedance | 90Ω ±10% |
| Power trace width | 0.5mm minimum |

---

## Output Files

```
apps/hub/kagami-orb/pcb/
├── kagami_orb.kicad_pro     # Project file
├── kagami_orb.kicad_sch     # Schematic (7 sheets)
├── kagami_orb.kicad_pcb     # PCB layout
├── gerbers/
│   ├── kagami_orb-F_Cu.gbr
│   ├── kagami_orb-B_Cu.gbr
│   ├── kagami_orb-F_Mask.gbr
│   ├── kagami_orb-B_Mask.gbr
│   ├── kagami_orb-F_Silkscreen.gbr
│   ├── kagami_orb-B_Silkscreen.gbr
│   ├── kagami_orb-Edge_Cuts.gbr
│   ├── kagami_orb.drl
│   └── kagami_orb-job.gbrjob
├── bom/
│   └── kagami_orb_bom.csv
└── assembly/
    ├── kagami_orb-top.pos
    └── kagami_orb-bottom.pos
```

---

```
鏡

h(x) ≥ 0. Always.

Every net has purpose.
Every component has reason.
The schematic is the truth.
```
